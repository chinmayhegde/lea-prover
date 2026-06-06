"""Verification endpoint — standalone single-file proof checking (design §4.5)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import verify as _verify

router = APIRouter(tags=["verify"])


class VerifyRequest(BaseModel):
    proof: str
    imports: list[str] = ["Mathlib"]
    target: str | None = None


@router.post("/verify")
def verify(req: VerifyRequest) -> dict:
    try:
        return _verify.verify(req.proof, req.imports, req.target)
    except _verify.ToolchainUnavailable as e:
        # No Lean/Lake installed: an upstream/server capability gap, not client error.
        raise HTTPException(status_code=502, detail=f"Lean toolchain unavailable: {e}") from e
