"""Bearer-token auth — optional in v1.

If ``LEA_API_KEYS`` is set, every route guarded by ``require_auth`` needs a
matching ``Authorization: Bearer <key>`` header. If it's empty (the default),
auth is disabled and the dependency is a no-op, so local development needs no
keys. Per-key rate limits and spend caps (design §5) are a v3 concern.

Model-provider credentials (GOOGLE_API_KEY, ANTHROPIC_API_KEY, ...) are never
accepted over the API — they stay server-side environment config.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request


def require_auth(request: Request, authorization: str | None = Header(default=None)) -> None:
    settings = request.app.state.settings
    if not settings.auth_enabled:
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    token = authorization.split(" ", 1)[1].strip()
    if token not in settings.key_set:
        raise HTTPException(status_code=401, detail="Invalid API key.")


AuthDep = Depends(require_auth)
