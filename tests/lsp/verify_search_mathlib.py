"""Smoke-test the new semantic search_mathlib (LeanExplore) via lea.tools.

Requires:
    - `lean-explore` installed in the env (see docs/vllm_runs.md or pyproject.toml)
    - export LEANEXPLORE_API_KEY=...   (get one at https://www.leanexplore.com)

If running through singularity exec, propagate the key with:
    SINGULARITYENV_LEANEXPLORE_API_KEY="$LEANEXPLORE_API_KEY" /scratch/spp9399/env/lea/run.sh ...
"""
import os, sys, time
from lea.tools import search_mathlib

if not os.environ.get("LEANEXPLORE_API_KEY"):
    print("ERROR: LEANEXPLORE_API_KEY is not set. `export LEANEXPLORE_API_KEY=...` first.")
    sys.exit(1)

CASES = [
    ("Sylow p-subgroup is normal when unique", 5),
    ("a transitive group action on a set of prime cardinality is primitive", 5),
    ("Borsuk-Ulam theorem", 3),
    ("",  3),                            # empty-query guard test
    ("blahblahnonsense_qzxywv_no_match", 3),  # no-results test
]

for q, limit in CASES:
    print(f"\n=== query={q!r}  limit={limit} ===", flush=True)
    t = time.time()
    out = search_mathlib(q, limit)
    print(f"  wall={time.time()-t:.2f}s", flush=True)
    # truncate long output
    print(out if len(out) < 2000 else out[:2000] + "\n... [truncated]")
