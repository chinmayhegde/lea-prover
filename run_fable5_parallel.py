"""Launch the FQB best-of-5 Fable 5 run sharded across N parallel processes.

Each shard runs `eval.run_fqb_best_of_n` on a disjoint subset of problems with
its own results file (eval/results/fable5_shardK.json) and proof/transcript
dirs — the experiment per problem is identical (best-of-5, default effort), only
wall-clock shrinks. Merge the shard JSONs afterward for the report.
"""
import os
import subprocess
import sys
from pathlib import Path

REPO = Path("/home/chinmay-gcp/lea-prover")
N_SHARDS = int(sys.argv[1]) if len(sys.argv) > 1 else 8

PROBLEMS = [
    "BanachStoneTheorem", "BorsukUlamTheorem", "BurnsidePrimeDegreeTheorem",
    "CollatzMapAlmostBoundedValues", "ColorfulCaratheodoryTheorem",
    "DLOQuantifierElimination", "DeBruijnErdos", "ErdosDiscrepancyProblem",
    "GleasonKahaneZelazkoTheorem", "GreenTaoTheorem", "Hilbert17thProblem",
    "JordanCycleTheorem", "JordanDerangementTheorem", "KakeyaTheorem3D",
    "MaynardTaoBoundedPrimeGaps", "ParisHarringtonPrinciple", "PontryaginDuality",
    "QuillenSuslinTheorem", "RungeTheorem", "SchauderFixedPointTheorem",
    "SkolemMahlerLechTheorem", "TernaryGoldbachTheorem",
    "VonNeumannDoubleCommutantTheorem",
]

# Round-robin assignment interleaves alphabetically-scattered hard problems
# across shards for rough load balancing.
shards = [[] for _ in range(N_SHARDS)]
for i, p in enumerate(PROBLEMS):
    shards[i % N_SHARDS].append(p)

env = dict(os.environ)
env["PATH"] = f"{Path.home()}/.elan/bin:" + env.get("PATH", "")
# LSP daemon stays ENABLED (fast turns); each shard gets its own daemon.

pids = []
for k, probs in enumerate(shards):
    if not probs:
        continue
    log = open(f"/tmp/fable_shard{k}.log", "w")
    results = REPO / "eval" / "results" / f"fable5_shard{k}.json"
    cmd = [
        str(REPO / ".venv/bin/python"), "-u", "-m", "eval.run_fqb_best_of_n",
        "--n", "5", "--model", "claude-fable-5",
        "--resume", str(results),
        "--problems", *probs,
    ]
    proc = subprocess.Popen(
        cmd, cwd=str(REPO), env=env, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True,  # detach so it survives the launcher exit
    )
    pids.append((k, proc.pid, probs))

for k, pid, probs in pids:
    print(f"shard {k}: pid {pid}  ({len(probs)}) {','.join(probs)}")
print(f"\nLaunched {len(pids)} shards. Logs: /tmp/fable_shard*.log  Results: eval/results/fable5_shard*.json")
