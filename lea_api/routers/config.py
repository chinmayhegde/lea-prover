"""Config endpoints — validate (pure) and default template (design §4.3)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from .. import config_support

router = APIRouter(prefix="/config", tags=["config"])


class ValidateRequest(BaseModel):
    config: dict[str, Any] | None = None


@router.post("/validate")
def validate(req: ValidateRequest) -> dict:
    """Validate a config payload; return the resolved LeaConfig or a typed error.

    No run, no disk write. A ConfigError propagates to the global handler, which
    renders the typed body with the right status (400/422).
    """
    cfg = config_support.resolve(req.config)
    return {"valid": True, "config": config_support.to_public(cfg)}


@router.get("/default")
def default() -> dict:
    """The shipped default.yaml as the base template clients overlay onto."""
    return config_support.default_raw()
