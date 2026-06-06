"""Declarative tool registry — the single place a tool's schema and handler live.

Every tool is one `Tool` record (model-facing schema + a `dict[args] -> str`
handler). Built-in tools register themselves when `lea.tools` is imported;
custom tools register from user modules named in `agent.tool_modules`; MCP tools
(a later step) will register here too. The agent loop never imports tools
directly — it asks `build_toolset(selected)` for exactly the tools config wants.

Public API for custom tools:

    from lea.registry import tool

    @tool(name="sympy", description="...", input_schema={...})
    def sympy(args: dict) -> str:
        ...
"""

import importlib
from dataclasses import dataclass
from typing import Callable

from .errors import ToolError

Handler = Callable[[dict], str]


@dataclass(frozen=True)
class Tool:
    """A registered tool: its model-facing schema and its handler.

    `schema` is the JSON object sent to the model (name/description/input_schema).
    `handler` takes the raw arguments dict and returns a string result.
    """

    name: str
    schema: dict
    handler: Handler


# name -> Tool, plus registration order so an unfiltered toolset is deterministic
# (and reproduces today's TOOLS_SCHEMA order for the built-ins).
REGISTRY: dict[str, Tool] = {}
_ORDER: list[str] = []


def register(tool: Tool) -> Tool:
    """Add a Tool to the registry. Raises ToolError on a duplicate name."""
    if tool.name in REGISTRY:
        raise ToolError(f"tool {tool.name!r} is already registered")
    REGISTRY[tool.name] = tool
    _ORDER.append(tool.name)
    return tool


def unregister(name: str) -> None:
    """Remove a tool from the registry (no-op if absent).

    Used to tear down dynamically-registered tools (e.g. MCP tools when their
    manager stops) so a later run can re-register them without a duplicate clash.
    """
    REGISTRY.pop(name, None)
    if name in _ORDER:
        _ORDER.remove(name)


def tool(*, name: str, description: str, input_schema: dict):
    """Decorator: register a `dict[args] -> str` function as a Tool.

    The function becomes the handler; the schema is assembled from the arguments.
    """

    schema = {"name": name, "description": description, "input_schema": input_schema}

    def decorator(fn: Handler) -> Handler:
        register(Tool(name=name, schema=schema, handler=fn))
        return fn

    return decorator


def import_tool_modules(modules: list[str]) -> None:
    """Import each module so its @tool/register side effects run.

    Used for `agent.tool_modules` — a user points at Python modules that register
    custom tools. Raises ToolError if a module can't be imported.
    """
    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as e:  # ImportError, or an error raised at import time
            raise ToolError(f"could not import tool module {name!r}: {e}") from e


def build_toolset(selected: list[str] | None) -> tuple[list[dict], dict[str, Handler]]:
    """Resolve a config selection into what the loop needs: (schemas, handlers).

    `selected is None` → every registered tool, in registration order (the
    default; reproduces today's behavior). A list → exactly those tools, in that
    order (so the list both filters and orders). An unknown name raises ToolError.
    """
    names = list(_ORDER) if selected is None else selected
    schemas: list[dict] = []
    handlers: dict[str, Handler] = {}
    for name in names:
        t = REGISTRY.get(name)
        if t is None:
            raise ToolError(
                f"unknown tool {name!r}; registered tools: {', '.join(sorted(REGISTRY))}"
            )
        schemas.append(t.schema)
        handlers[name] = t.handler
    return schemas, handlers
