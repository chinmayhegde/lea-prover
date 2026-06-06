"""Standalone proof verification — single-file compile + axiom listing.

Design §4.5's verify takes ``{ proof, imports, target }`` and returns
``{ verified, diagnostics, axioms, elapsed_ms }``. This is *single-file*
checking, distinct from the comparison-style SafeVerify in ``eval/utils`` (which
diffs a submission against a target file). We build it on the agent's existing
``lean_check`` (which already uses the LSP fast path when available) and add the
one thing neither path returns: the axiom list, via ``#print axioms``.

The file is written into the workspace Lake project so Mathlib resolves.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from lea.tools import WORKSPACE, lean_check

# `#print axioms foo` prints e.g.:  'foo' depends on axioms: [propext, Classical.choice, Quot.sound]
# or:  'foo' does not depend on any axioms
_AXIOMS_RE = re.compile(r"depends on axioms:\s*\[([^\]]*)\]")
_NO_AXIOMS_RE = re.compile(r"does not depend on any axioms")

_TOOLCHAIN_MISSING = "lean` or `lake` not found"


class ToolchainUnavailable(RuntimeError):
    """Raised when no Lean toolchain is installed, so verify cannot run."""


def _build_source(proof: str, imports: list[str], target: str | None) -> str:
    lines = [f"import {i}" for i in imports]
    parts = ["\n".join(lines)] if lines else []
    parts.append(proof.strip())
    if target:
        parts.append(f"#print axioms {target}")
    return "\n\n".join(parts) + "\n"


def _parse_axioms(output: str) -> list[str]:
    if _NO_AXIOMS_RE.search(output):
        return []
    m = _AXIOMS_RE.search(output)
    if not m:
        return []
    return [a.strip() for a in m.group(1).split(",") if a.strip()]


def _is_verified(output: str) -> bool:
    low = output.lower()
    if output.startswith("OK"):
        return True
    # lean_check returns raw diagnostics on failure; an "error:" means it failed.
    return "error:" not in low and "error " not in low


def verify(proof: str, imports: list[str] | None = None,
           target: str | None = None) -> dict:
    """Compile a single proof file and report verification + axioms.

    Returns ``{ verified, diagnostics, axioms, elapsed_ms }``. Raises
    ``ToolchainUnavailable`` if Lean/Lake is not installed (the caller maps that
    to 502).
    """
    imports = imports if imports is not None else ["Mathlib"]
    source = _build_source(proof, imports, target)

    scratch = WORKSPACE / ".api_verify"
    scratch.mkdir(parents=True, exist_ok=True)
    path = scratch / "ApiVerify.lean"
    path.write_text(source)

    start = time.time()
    try:
        diagnostics = lean_check(str(path))
    finally:
        try:
            path.unlink(missing_ok=True)   # best-effort cleanup; never fail the request on it
        except OSError:
            pass
    elapsed_ms = int((time.time() - start) * 1000)

    if _TOOLCHAIN_MISSING in diagnostics:
        raise ToolchainUnavailable(diagnostics)

    verified = _is_verified(diagnostics)
    return {
        "verified": verified,
        "diagnostics": [] if diagnostics.startswith("OK") else [diagnostics],
        "axioms": _parse_axioms(diagnostics) if verified else [],
        "elapsed_ms": elapsed_ms,
    }
