"""Phase-1 state scaffold test for Lea-Ralph (no LLM, no Lean build).

Exercises the run-dir lifecycle on a synthetic target:
  init -> leaves populated from sorrys -> simulate a decompose (skeleton with
  sub-haves) -> sync grows leaves -> simulate a fill -> sync closes a leaf ->
  checkpoints accumulate in the nested git repo.

Run:  python -m tests.ralph.test_state
Exits 0 if every assertion holds, 1 otherwise.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from lea.ralph import state

# A target with one top-level sorry — the cold-start shape Ralph starts from.
TARGET = """\
import Mathlib

theorem smoke (n : Nat) : n + 0 = n := by
  sorry
"""

# A "decompose" step: the top proof now leans on two sub-haves, each a sorry.
DECOMPOSED = """\
import Mathlib

theorem smoke (n : Nat) : n + 0 = n := by
  have h1 : n + 0 = n := by sorry
  have h2 : True := by sorry
  exact h1
"""

# A "fill" step: h1 closed; h2 still open.
ONE_FILLED = """\
import Mathlib

theorem smoke (n : Nat) : n + 0 = n := by
  have h1 : n + 0 = n := Nat.add_zero n
  have h2 : True := by sorry
  exact h1
"""


def _commit_count(run: Path) -> int:
    out = state._git(run, "rev-list", "--count", "HEAD")
    return int(out.stdout.strip() or "0")


def main() -> int:
    fails: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            fails.append(msg)
            print(f"  FAIL: {msg}")
        else:
            print(f"  ok:   {msg}")

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "workspace"
        (ws / "proofs").mkdir(parents=True)
        target_file = Path(td) / "smoke.lean"
        target_file.write_text(TARGET)

        # --- init ---
        run = state.init_run(
            target_file, "smoke", workspace=ws, timestamp="20260101-000000",
        )
        check(run.exists(), "run dir created")
        check(state.target_path(run).read_text() == TARGET, "target.lean frozen == source")
        check(state.work_path(run).read_text() == TARGET, "work.lean starts == target")
        check((run / ".git").is_dir(), "nested git repo initialised")
        check(_commit_count(run) == 1, "init produced one checkpoint")

        wl = state.load_worklist(run)
        check(wl["target"] == "smoke", "worklist records target name")
        check(wl["allowed_axioms"] == state.DEFAULT_AXIOMS, "default axioms recorded")
        check(len(state.open_leaves(run)) == 1, "one open leaf at cold start")
        top_id = next(iter(state.open_leaves(run)))

        # --- decompose: work.lean grows two sub-haves ---
        state.work_path(run).write_text(DECOMPOSED)
        state.sync_worklist(run)
        opens = state.open_leaves(run)
        # top theorem `smoke` no longer has a direct sorry -> closed; h1,h2 open.
        check(len(opens) == 2, "decompose -> two open leaves (h1, h2)")
        names = sorted(l["name"] for l in opens.values())
        check(names == ["h1", "h2"], f"leaf names are h1,h2 (got {names})")
        check(state.load_worklist(run)["leaves"][top_id]["status"] == "closed",
              "top leaf marked closed once its direct sorry is gone")
        state.checkpoint(run, "decompose: +h1 +h2")
        check(_commit_count(run) == 2, "decompose checkpoint recorded")

        # --- counts persist across sync ---
        h1_id = state.leaf_id("h1", "n + 0 = n")
        state.bump(run, h1_id, "attempts")
        state.update_leaf(run, h1_id, last_error="nlinarith timeout")
        state.sync_worklist(run)
        h1 = state.load_worklist(run)["leaves"][h1_id]
        check(h1["attempts"] == 1, "attempts survive a sync")
        check(h1["last_error"] == "nlinarith timeout", "last_error survives a sync")

        # --- fill h1: its sorry disappears -> closed ---
        state.work_path(run).write_text(ONE_FILLED)
        state.sync_worklist(run)
        opens = state.open_leaves(run)
        check(len(opens) == 1 and next(iter(opens.values()))["name"] == "h2",
              "fill h1 -> only h2 open")
        check(state.load_worklist(run)["leaves"][h1_id]["status"] == "closed",
              "h1 closed after fill")

        # --- heartbeat round-trips ---
        state.heartbeat(run, status="running", session=3)
        hb = state.read_json(state.heartbeat_path(run))
        check(hb["status"] == "running" and hb["session"] == 3 and "ts" in hb,
              "heartbeat round-trips with ts")

    if fails:
        print(f"\n{len(fails)} check(s) failed.")
        return 1
    print("\nAll Phase-1 state checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
