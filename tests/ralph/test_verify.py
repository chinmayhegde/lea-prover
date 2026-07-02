"""Phase-2 gate test for Lea-Ralph.

Two parts:
  1. Pure unit tests for the `#print axioms` parser (no build).
  2. Full `done()` composition against a v4.28 Lake project (the FQB project,
     which matches SafeVerify's toolchain). All cases use core Lean — NO Mathlib
     import — so each compiles in ~seconds:
       - genuine proof            -> done TRUE
       - leftover sorry           -> FALSE (no_sorry gate)
       - stray custom axiom       -> FALSE (axioms gate)
       - namespace-shadow cheat   -> FALSE (faithful gate)  <- anti-cheat backstop

Run:  python -m tests.ralph.test_verify
Exits 0 if every assertion holds, 1 otherwise. SKIPs (exit 0) if the FQB Lake
project isn't present.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from lea.ralph import state, verify

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FQB_DIR = REPO_ROOT / "FormalQualBench"          # v4.28, matches SafeVerify
# SafeVerify's `lake env lean -o` requires sources INSIDE the project root, so
# the run dirs must live under FQB_DIR (mirrors the real layout: run dir inside
# the workspace Lake project).
SCRATCH = FQB_DIR / "eval_proofs" / "_ralph_phase2"


# ------- case sources (core Lean, no Mathlib) -------

GENUINE_TARGET = "theorem foo : 1 + 1 = 2 := sorry\n"
GENUINE_WORK = "theorem foo : 1 + 1 = 2 := rfl\n"

SORRY_WORK = "theorem foo : 1 + 1 = 2 := by sorry\n"

AXIOM_WORK = "axiom bar : 1 + 1 = 2\ntheorem foo : 1 + 1 = 2 := bar\n"

# Core-only reproduction of the namespace-shadow cheat: `P` is redefined so the
# goal collapses to `True`. SafeVerify must reject on the type mismatch.
SHADOW_TARGET = "def P : Prop := ∀ n : Nat, n + 0 = n\ntheorem foo : P := sorry\n"
SHADOW_WORK = "def P : Prop := True\ntheorem foo : P := trivial\n"


def _unit_parser_checks(check) -> None:
    p = verify._parse_axioms
    check(p("'foo' does not depend on any axioms") == set(), "parser: no axioms -> empty set")
    check(p("'foo' depends on axioms: [propext, Classical.choice, Quot.sound]")
          == {"propext", "Classical.choice", "Quot.sound"}, "parser: standard three")
    check(p("'foo' depends on axioms: [sorryAx]") == {"sorryAx"}, "parser: sorryAx surfaced")
    check(p("'foo' depends on axioms: [bar]") == {"bar"}, "parser: single custom axiom")
    check(p("some unrelated error output") is None, "parser: unrecognized -> None")


def _make_run(tmp: Path, name: str, target_src: str, work_src: str,
              allowed=None) -> Path:
    target_file = tmp / f"{name}_target.lean"
    target_file.write_text(target_src)
    # run dir must be under the Lake project (SafeVerify constraint), but the
    # nested git repo + worklist are otherwise self-contained.
    run = state.init_run(
        target_file, "foo", workspace=FQB_DIR, allowed_axioms=allowed,
        runs_root=SCRATCH, timestamp=name,
    )
    state.work_path(run).write_text(work_src)   # override work with the case
    return run


def main() -> int:
    fails: list[str] = []

    def check(cond: bool, msg: str) -> None:
        (print(f"  ok:   {msg}") if cond else
         (fails.append(msg), print(f"  FAIL: {msg}")))

    print("[unit] axioms parser")
    _unit_parser_checks(check)

    if not (FQB_DIR / "lakefile.lean").exists() and not (FQB_DIR / "lakefile.toml").exists():
        print(f"\nSKIP integration: no Lake project at {FQB_DIR}")
        return 1 if fails else 0

    shutil.rmtree(SCRATCH, ignore_errors=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    try:
      with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        print("[int] genuine proof -> done TRUE")
        run = _make_run(tmp, "genuine", GENUINE_TARGET, GENUINE_WORK)
        ok, rep = verify.done(run, FQB_DIR)
        check(ok, f"genuine: done TRUE (gates={ {k: v['pass'] for k, v in rep['gates'].items()} })")

        print("[int] leftover sorry -> done FALSE (no_sorry gate)")
        run = _make_run(tmp, "sorrycase", GENUINE_TARGET, SORRY_WORK)
        ok, rep = verify.done(run, FQB_DIR)
        check(not ok and rep["gates"]["no_sorry"]["pass"] is False,
              "sorry: rejected at no_sorry gate")

        print("[int] stray custom axiom -> done FALSE (axioms gate)")
        run = _make_run(tmp, "axiomcase", GENUINE_TARGET, AXIOM_WORK)
        ok, rep = verify.done(run, FQB_DIR)
        check(not ok and rep["gates"].get("axioms", {}).get("pass") is False,
              "axiom: rejected at axioms gate (bar ⊄ allowed)")

        print("[int] namespace-shadow cheat -> done FALSE (faithful gate)  [backstop]")
        run = _make_run(tmp, "shadowcase", SHADOW_TARGET, SHADOW_WORK)
        ok, rep = verify.done(run, FQB_DIR)
        # It must be rejected; ideally by the faithful gate (SafeVerify).
        gate = rep["gates"]
        rejected_by_faithful = gate.get("faithful", {}).get("pass") is False
        check(not ok, "shadow: rejected (not done)")
        check(rejected_by_faithful,
              f"shadow: rejected specifically by SafeVerify (gates={ {k: v['pass'] for k, v in gate.items()} })")
    finally:
        shutil.rmtree(SCRATCH, ignore_errors=True)

    if fails:
        print(f"\n{len(fails)} check(s) failed.")
        return 1
    print("\nAll Phase-2 gate checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
