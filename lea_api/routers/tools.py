"""Tool endpoints — reflect the live tool registry (design §4.4).

Importing ``lea.tools`` registers the six built-ins into ``registry.REGISTRY``.
Reading the registry here means that once ``tool_modules`` / MCP tools register
dynamically (v2/v3), the same endpoints surface them with no change.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

import lea.tools  # noqa: F401 — import side effect: registers built-in tools
from lea.registry import REGISTRY, _ORDER

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("")
def list_tools() -> dict:
    return {"tools": [REGISTRY[name].schema for name in _ORDER]}


@router.get("/{name}")
def get_tool(name: str) -> dict:
    tool = REGISTRY.get(name)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {name}")
    return tool.schema
