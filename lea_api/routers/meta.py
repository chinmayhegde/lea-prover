"""Meta endpoints — liveness, version, capability discovery (design §4.10)."""

from __future__ import annotations

import shutil
import subprocess

from fastapi import APIRouter, Request

from ..wire import SCHEMA_VERSION

router = APIRouter(tags=["meta"])

try:  # package version, best-effort
    from importlib.metadata import version as _pkg_version
    _VERSION = _pkg_version("lea-prover")
except Exception:  # noqa: BLE001
    _VERSION = "0.1.0"


def _git_sha() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=2)
        return out.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "lean_available": bool(shutil.which("lean") or shutil.which("lake"))}


@router.get("/version")
def version() -> dict:
    return {"version": _VERSION, "git_sha": _git_sha(), "schema_version": SCHEMA_VERSION}


@router.get("/capabilities")
def capabilities(request: Request) -> dict:
    settings = request.app.state.settings
    return {
        "schema_version": SCHEMA_VERSION,
        "transports": ["sse"],          # websocket: v1.x follow-up
        "auth_required": settings.auth_enabled,
        "limits": {"max_concurrent_runs": settings.max_concurrent_runs},
        "endpoints": {
            "runs": True, "verify": True, "config_validate": True, "tools": True,
            "sessions": False, "configs": False, "models": False,   # v2
            "skills": False, "mcp": False, "eval": False,           # v3
        },
    }
