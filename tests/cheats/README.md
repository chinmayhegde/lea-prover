# SafeVerify cheat regression test

Reproduces the three known FQB "cheat" submissions (ErdosDiscrepancyProblem,
QuillenSuslinTheorem, RungeTheorem — see `fqb-reports/fqb-bon5-report.md`)
and asserts `eval/utils/verify.py` rejects each one. The submissions compile
cleanly under `lake env lean`, so the older loose check marked them PASS —
this test is what validates that the SafeVerify-backed grader closes that gap.

## Prereqs

- `FormalQualBench/` cloned at the repo root.
- `third_party/SafeVerify/` built (`cd third_party/SafeVerify && lake update && lake build`).
- Mathlib available in `FormalQualBench/` (Lake will build on first run).

## Run

```bash
python -m tests.cheats.test_cheats
```

Exit code 0 on full pass, 1 if any cheat slipped through or was rejected by
plain compile (which would mean the cheat no longer faithfully reproduces
the loose-check bypass).

## Current output

```
[ErdosDiscrepancyProblem] verifying cheat...
  OK: rejected (Currently running on Lean v4.28.0)
[QuillenSuslinTheorem] verifying cheat...
  OK: rejected (Currently running on Lean v4.28.0)
[RungeTheorem] verifying cheat...
  OK: rejected (Currently running on Lean v4.28.0)

All 3 cheats rejected by SafeVerify.
```

The `OK: rejected (...)` line prints SafeVerify's first stdout line (its
banner). The actual failure codes (`defnCheck` for Erdős, `thmType` for
Quillen–Suslin / Runge) live deeper in SafeVerify's report.
