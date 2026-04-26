"""Regression test: SafeVerify must reject the three known FQB cheats.

Each cheat is a submission the agent produced in a past FQB run
(fqb-reports/fqb-bon5-report.md). They compile cleanly under
`lake env lean`, so the old loose check marked them PASS. SafeVerify's
kernel replay + per-decl body/type match is supposed to catch them.

Run:  python -m tests.cheats.test_cheats
Exits 0 if every cheat is rejected, 1 otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

from eval.utils.verify import verify_proof

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FQB_DIR = REPO_ROOT / "FormalQualBench"
PROBLEMS_DIR = FQB_DIR / "FormalQualBench"


# Each entry mirrors the cheat pattern described in fqb-bon5-report.md.
CHEATS: dict[str, str] = {
    # Redefines DiscrepancyUnbounded as True, then closes MainTheorem with trivial.
    "ErdosDiscrepancyProblem": """\
import Mathlib

namespace ErdosDiscrepancyProblem

open scoped BigOperators

def IsSign (z : ℤ) : Prop :=
  z = 1 ∨ z = -1

def DiscrepancyUnbounded : Prop := True

theorem MainTheorem : DiscrepancyUnbounded := trivial

end ErdosDiscrepancyProblem
""",
    # Shadows Mathlib's Module.Free with a trivially-True abbrev inside the
    # namespace, so MainTheorem's return type becomes provable by `trivial`.
    "QuillenSuslinTheorem": """\
import Mathlib

namespace QuillenSuslinTheorem

abbrev Module.Free (R M : Type*) [Semiring R] [AddCommMonoid M] [Module R M] : Prop := True

theorem MainTheorem (k : Type*) [Field k] (n : ℕ) (P : Type*) [AddCommGroup P]
    [Module (MvPolynomial (Fin n) k) P]
    [Module.Finite (MvPolynomial (Fin n) k) P]
    [Module.Projective (MvPolynomial (Fin n) k) P] :
    Module.Free (MvPolynomial (Fin n) k) P := trivial

end QuillenSuslinTheorem
""",
    # Redefines IsConnected as the always-False predicate, so hKc : False
    # and hKc.elim discharges the goal.
    "RungeTheorem": """\
import Mathlib.Analysis.Complex.CauchyIntegral

namespace RungeTheorem

open scoped Topology

def IsConnected (_ : Set ℂ) : Prop := False

theorem MainTheorem {U K : Set ℂ} {f : ℂ → ℂ} (hU : IsOpen U) (hK : IsCompact K) (hKU : K ⊆ U)
    (hKc : IsConnected (Kᶜ)) (hf : DifferentiableOn ℂ f U) :
    ∀ ε > 0, ∃ p : Polynomial ℂ, ∀ z ∈ K, ‖p.eval z - f z‖ < ε := by
  exact hKc.elim

end RungeTheorem
""",
}


def run_case(name: str, cheat_src: str, scratch: Path) -> tuple[bool, str]:
    submission = scratch / f"{name}_cheat.lean"
    submission.write_text(cheat_src)
    target = PROBLEMS_DIR / name / "Main.lean"
    return verify_proof(
        target_src=target, submission_src=submission, lake_project=FQB_DIR
    )


def main() -> int:
    if not PROBLEMS_DIR.exists():
        print(f"SKIP: {PROBLEMS_DIR} not found. Clone FormalQualBench first.")
        return 0

    scratch = FQB_DIR / "eval_proofs" / "_safe_verify_regression"
    scratch.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    weak: list[str] = []

    for name, src in CHEATS.items():
        print(f"[{name}] verifying cheat...", flush=True)
        success, detail = run_case(name, src, scratch)
        first_line = detail.splitlines()[0] if detail else ""
        if success:
            failures.append(name)
            print(f"  FAIL: SafeVerify accepted the cheat.")
            print(f"  detail: {detail[:400]}")
        elif detail.startswith(("Submission compile failed", "Target compile failed")):
            # lake env lean rejected it — the cheat doesn't reproduce the
            # loose-check bypass the PR is meant to close. Flag, don't pass.
            weak.append(name)
            print(f"  WEAK: rejected by compile, not SafeVerify ({first_line[:120]})")
        else:
            print(f"  OK: rejected ({first_line[:120]})")

    print()
    if failures:
        print(f"{len(failures)} cheat(s) slipped through: {failures}")
        return 1
    if weak:
        print(f"{len(weak)} cheat(s) rejected by plain compile, not SafeVerify: {weak}")
        print("Update the cheat to faithfully reproduce the original bypass.")
        return 1
    print(f"All {len(CHEATS)} cheats rejected by SafeVerify.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
