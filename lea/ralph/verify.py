"""Verification gates for the Lea-Ralph loop.

Two gates, cheap -> expensive, plus the composite stop-oracle `done()`:

  kernel_ok(work, lake_project)          # `lake env lean` compiles (sorrys OK)
  axioms_of / axioms_ok(...)             # `#print axioms` ⊆ allowed line
  faithful(work, target, lake_project)   # SafeVerify: statement match, no sorry,
                                         #   no shadow/tautology (wraps eval.utils.verify)
  done(run, lake_project) -> (bool, report)

`done()` is the anti-cheat backstop. It rejects the cheat catalogue by:
  (a) requiring zero `sorry` (text pre-filter + `sorryAx` via the axioms gate),
  (b) an explicit `#print axioms ⊆ allowed` check (stray/cited axioms),
  (c) SafeVerify against the FROZEN target (type/body match — kills namespace
      shadow, statement tautologization, ⊤-weakening, import-sorry).

Toolchain note: SafeVerify is built against a specific Lean (currently v4.28.0);
`lake_project` MUST use the same toolchain or the olean handoff mismatches. Pass
a v4.28 project, not the v4.29 `workspace/`. See RALPH.md.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from eval.utils.verify import verify_proof
from lea.ralph import state
from lea.sketch import count_sorrys


def _tail(s: str, n: int = 800) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else "…" + s[-n:]


# --------------------------------- kernel gate --------------------------------

def kernel_ok(work: Path, lake_project: Path, timeout: int = 600) -> tuple[bool, str]:
    """True iff `work` type-checks under `lake env lean`. `sorry`s are allowed
    (they compile with a warning) — this is the 'skeleton is valid' gate used
    while the proof tree is still growing."""
    try:
        r = subprocess.run(
            ["lake", "env", "lean", str(Path(work).resolve())],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(lake_project),
        )
    except subprocess.TimeoutExpired:
        return False, f"compile timed out ({timeout}s)"
    return (r.returncode == 0), (r.stdout + "\n" + r.stderr).strip()


# --------------------------------- axioms gate --------------------------------

_AX_LIST_RE = re.compile(r"depends on axioms:\s*\[([^\]]*)\]", re.DOTALL)


def _parse_axioms(output: str) -> set[str] | None:
    """Parse `#print axioms X` output → the axiom set, or None if the
    declaration was not found / output unrecognized."""
    if "does not depend on any axioms" in output:
        return set()
    m = _AX_LIST_RE.search(output)
    if not m:
        return None
    body = m.group(1)
    return {a.strip() for a in body.split(",") if a.strip()}


def axioms_of(theorem: str, work: Path, lake_project: Path,
              timeout: int = 600) -> tuple[set[str] | None, str]:
    """Run `#print axioms <theorem>` by appending it to a copy of `work` and
    compiling. Returns (axiom_set_or_None, raw_output). A transitive `sorry`
    shows up as `sorryAx`, so this doubles as the kernel-level sorry check."""
    work = Path(work)
    probe = work.parent / f".axcheck_{work.stem}.lean"
    probe.write_text(work.read_text() + f"\n\n#print axioms {theorem}\n")
    try:
        r = subprocess.run(
            ["lake", "env", "lean", str(probe.resolve())],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(lake_project),
        )
        out = (r.stdout + "\n" + r.stderr).strip()
        return _parse_axioms(out), out
    except subprocess.TimeoutExpired:
        return None, f"axioms probe timed out ({timeout}s)"
    finally:
        probe.unlink(missing_ok=True)


def axioms_ok(theorem: str, work: Path, lake_project: Path,
              allowed: list[str], timeout: int = 600) -> tuple[bool, str]:
    ax, out = axioms_of(theorem, work, lake_project, timeout)
    if ax is None:
        return False, f"could not read axioms of {theorem}: {_tail(out, 300)}"
    extra = ax - set(allowed)
    if extra:
        return False, f"disallowed axioms: {sorted(extra)}"
    return True, "axioms ⊆ allowed"


# ------------------------------ faithfulness gate -----------------------------

def faithful(work: Path, target: Path, lake_project: Path,
             timeout: int = 600) -> tuple[bool, str]:
    """SafeVerify `work` against the frozen `target` (statement match, no sorry,
    no shadow/tautology). Thin wrapper over eval.utils.verify.verify_proof."""
    return verify_proof(
        target_src=Path(target), submission_src=Path(work),
        lake_project=Path(lake_project),
        compile_timeout=timeout, safe_verify_timeout=timeout,
    )


# ------------------------------- the stop oracle ------------------------------

def done(run: Path, lake_project: Path, timeout: int = 600) -> tuple[bool, dict]:
    """Composite stop oracle. Runs the gates cheap->expensive with early exit;
    returns (all_passed, report) where report['gates'] records each gate's
    verdict for the heartbeat / final report."""
    run = Path(run)
    wl = state.load_worklist(run)
    theorem = wl["target"]
    allowed = wl.get("allowed_axioms", state.DEFAULT_AXIOMS)
    work, target = state.work_path(run), state.target_path(run)
    report: dict = {"theorem": theorem, "gates": {}}

    def record(name: str, ok: bool, detail: str) -> None:
        report["gates"][name] = {"pass": ok, "detail": _tail(detail, 400)}

    # 1. no sorry (text pre-filter — instant)
    n = count_sorrys(work)
    record("no_sorry", n == 0, f"{n} sorry token(s)")
    if n != 0:
        return False, report

    # 2. compiles
    ok, out = kernel_ok(work, lake_project, timeout)
    record("kernel", ok, out)
    if not ok:
        return False, report

    # 3. axioms ⊆ allowed (also catches sorryAx)
    ok, msg = axioms_ok(theorem, work, lake_project, allowed, timeout)
    record("axioms", ok, msg)
    if not ok:
        return False, report

    # 4. SafeVerify vs frozen target
    ok, detail = faithful(work, target, lake_project, timeout)
    record("faithful", ok, detail)
    return ok, report
