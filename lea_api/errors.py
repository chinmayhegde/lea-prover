"""Map the ``LeaError`` hierarchy to HTTP status codes + a structured body.

One place owns the table from design §4 so a typed agent exception becomes a
predictable HTTP response:

    { "error": { "type": "...", "message": "...", "field": "..."? } }

``field`` is included for config-value errors when we can recover it from the
message (the config validators already name ``section.key``).
"""

from __future__ import annotations

import re

from fastapi import Request
from fastapi.responses import JSONResponse

from lea.errors import (
    ConfigFormatError,
    InvalidConfigValueError,
    LeaError,
    McpError,
    MissingConfigKeyError,
    SkillError,
    ToolError,
    UnknownConfigKeyError,
)

# Exception type -> HTTP status. Order matters: most specific first.
_STATUS: list[tuple[type, int]] = [
    (ConfigFormatError, 400),
    (UnknownConfigKeyError, 422),
    (MissingConfigKeyError, 422),
    (InvalidConfigValueError, 422),
    (SkillError, 422),
    (ToolError, 422),   # unknown tool selected / bad tool_module; tool *runtime* failure is 502
    (McpError, 424),
]

# Pull a `section.key` mention out of a config error message, e.g.
# "'model.stream' must be a boolean, got str." -> "model.stream".
_FIELD_RE = re.compile(r"'([a-zA-Z_][\w.]*\.[\w.]+)'")


def status_for(exc: LeaError) -> int:
    for cls, code in _STATUS:
        if isinstance(exc, cls):
            return code
    return 500  # unknown LeaError subclass


def to_body(exc: LeaError) -> dict:
    body: dict = {"type": type(exc).__name__, "message": str(exc)}
    if isinstance(exc, (InvalidConfigValueError, MissingConfigKeyError, UnknownConfigKeyError)):
        m = _FIELD_RE.search(str(exc))
        if m:
            body["field"] = m.group(1)
    return body


async def lea_error_handler(request: Request, exc: LeaError) -> JSONResponse:
    return JSONResponse(status_code=status_for(exc), content={"error": to_body(exc)})
