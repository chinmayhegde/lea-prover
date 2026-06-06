"""MCP integration — connect to configured MCP servers and register their tools.

External MCP servers (filesystem, git, web search, a Lean server, ...) expose
tools we don't have to write. This manager connects to each server named in
`mcp.servers`, lists its tools, and registers each into the shared tool registry
as `<server>__<tool>` — after which they are ordinary tools to the loop.

Bridging sync ↔ async: the MCP SDK is asyncio-based and its client contexts use
anyio cancel scopes that must be entered and exited in the *same* task. So we run
one long-lived `_serve` coroutine on a private event loop in a background thread:
it opens every session, signals ready, then parks on a stop event (holding the
contexts open). Tool calls are dispatched onto that loop with
`run_coroutine_threadsafe`, giving the loop the plain `dict -> str` handlers it
expects. Shutdown sets the stop event so `_serve` unwinds the contexts itself.

A server that fails to start is warned-and-skipped (the run continues with the
other tools); it does not abort the agent.
"""

import asyncio
import os
import sys
import threading
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

from .errors import McpError
from .registry import REGISTRY, Tool, register, unregister


def _warn(msg: str) -> None:
    print(f"[mcp] {msg}", file=sys.stderr)


def _stringify(result) -> str:
    """Flatten an MCP CallToolResult into the string the loop expects."""
    parts = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        parts.append(text if text is not None else f"[{getattr(block, 'type', 'content')}]")
    out = "\n".join(parts) if parts else "(no content)"
    if getattr(result, "isError", False):
        out = "Error: " + out
    return out


class MCPManager:
    """Lifecycle owner for the configured MCP servers and their registered tools."""

    def __init__(self, servers: dict[str, dict]):
        self.servers = servers or {}
        self.tool_names: list[str] = []           # registry names we added (server__tool)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._sessions: dict[str, ClientSession] = {}
        self._stop_event: asyncio.Event | None = None
        self._serve_future = None
        self._loop_ready = threading.Event()
        self._started = threading.Event()         # set when _serve finished setup (or failed)

    # ---- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        """Start the background loop and connect every configured server (blocking
        until startup finishes). No-op when no servers are configured."""
        if not self.servers:
            return
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="lea-mcp")
        self._thread.start()
        self._loop_ready.wait()
        self._serve_future = asyncio.run_coroutine_threadsafe(self._serve(), self._loop)
        self._started.wait()

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop_ready.set()
        self._loop.run_forever()
        self._loop.close()

    async def _serve(self) -> None:
        """Open all sessions in THIS task, signal ready, park until stop, then the
        `async with` unwinds every context in this same task (anyio-safe)."""
        self._stop_event = asyncio.Event()
        try:
            async with AsyncExitStack() as stack:
                for name, spec in self.servers.items():
                    try:
                        await self._connect_one(stack, name, spec)
                    except Exception as e:
                        _warn(f"server {name!r} failed to start: {e}; continuing without its tools")
                self._started.set()
                await self._stop_event.wait()
        finally:
            self._started.set()  # ensure start() unblocks even if setup raised

    async def _connect_one(self, stack: AsyncExitStack, name: str, spec: dict) -> None:
        if "command" in spec:
            # Merge configured env over the inherited environment: the SDK uses
            # `env` verbatim when set (no inheritance), so passing only e.g.
            # LEAN_PROJECT_PATH would strip PATH and the command wouldn't be found.
            cfg_env = spec.get("env")
            env = {**os.environ, **cfg_env} if cfg_env else None
            params = StdioServerParameters(
                command=spec["command"],
                args=spec.get("args", []),
                env=env,
                cwd=spec.get("cwd"),
            )
            read, write = await stack.enter_async_context(stdio_client(params))
        else:  # url-based remote server
            url = spec["url"]
            headers = spec.get("headers")
            if spec.get("transport") == "sse":
                read, write = await stack.enter_async_context(sse_client(url, headers=headers))
            else:  # streamable HTTP (current standard); yields a 3-tuple
                read, write, _ = await stack.enter_async_context(
                    streamablehttp_client(url, headers=headers)
                )
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        listed = await session.list_tools()
        self._sessions[name] = session
        for t in listed.tools:
            # Expose the tool by its bare name (how models expect MCP tools, à la
            # Claude Desktop/Cursor). Only on a name clash do we prefix with
            # `<server>__` to disambiguate. The handler always calls the real MCP
            # tool name on the server, regardless of the registry display name.
            tname = t.name
            if tname in REGISTRY:
                prefixed = f"{name}__{t.name}"
                if prefixed in REGISTRY:
                    _warn(f"tool {t.name!r} from server {name!r} clashes even after prefixing; skipping")
                    continue
                _warn(f"tool {t.name!r} from server {name!r} clashes; exposing it as {prefixed!r}")
                tname = prefixed
            schema = {
                "name": tname,
                "description": t.description or "",
                "input_schema": t.inputSchema or {"type": "object", "properties": {}},
            }
            register(Tool(name=tname, schema=schema, handler=self._make_handler(name, t.name)))
            self.tool_names.append(tname)

    def stop(self) -> None:
        """Unregister our tools and unwind all sessions/loop. Safe to call once."""
        for n in self.tool_names:
            unregister(n)
        self.tool_names.clear()
        if self._loop is None:
            return
        if self._stop_event is not None:
            self._loop.call_soon_threadsafe(self._stop_event.set)
        if self._serve_future is not None:
            try:
                self._serve_future.result(timeout=10)
            except Exception as e:
                _warn(f"error during shutdown: {e}")
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._loop = None

    # ---- tool dispatch ------------------------------------------------------

    def _make_handler(self, server: str, tool: str):
        def handler(args: dict) -> str:
            if self._loop is None:
                raise McpError(f"MCP loop not running for {server}__{tool}")
            fut = asyncio.run_coroutine_threadsafe(self._acall(server, tool, args), self._loop)
            return fut.result()

        return handler

    async def _acall(self, server: str, tool: str, args: dict) -> str:
        session = self._sessions.get(server)
        if session is None:
            raise McpError(f"no live MCP session for server {server!r}")
        result = await session.call_tool(tool, args or {})
        return _stringify(result)
