"""A tiny stdio MCP server used by tests/mcp/test_mcp.py.

Launched as a subprocess by MCPManager (command=python, args=[this file]). Exposes
two trivial tools so the test can verify the full connect → list → call round-trip
over real MCP stdio, with no network and no node/npx dependency.
"""

from mcp.server.fastmcp import FastMCP

server = FastMCP("stub")


@server.tool()
def secret() -> str:
    """Return the secret value (known only via this MCP server)."""
    return "MCP-SECRET-9"


@server.tool()
def echo(text: str) -> str:
    """Echo the provided text back, prefixed."""
    return f"stub-echo: {text}"


@server.tool()
def bash(command: str) -> str:
    """A tool whose name deliberately collides with the built-in `bash`."""
    return f"stub-bash: {command}"


if __name__ == "__main__":
    server.run()  # stdio transport by default
