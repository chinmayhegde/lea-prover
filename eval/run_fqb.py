"""Evaluate Lea on the FormalQualBench benchmark.

Usage:
    python -m eval.run_fqb                              # run all 23 problems
    python -m eval.run_fqb --limit 5                    # first 5 problems
    python -m eval.run_fqb --problems GreenTaoTheorem   # specific problem(s)
    python -m eval.run_fqb --resume results.json        # resume a partial run
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
FQB_DIR = REPO_ROOT / "FormalQualBench"
PROBLEMS_DIR = FQB_DIR / "FormalQualBench"
RESULTS_DIR = REPO_ROOT / "eval" / "results"


def discover_problems(names: list[str] | None = None) -> list[Path]:
    """Return sorted list of problem directories."""
    if not PROBLEMS_DIR.exists():
        sys.exit(f"Error: {PROBLEMS_DIR} not found. Clone FormalQualBench first.")

    all_dirs = sorted([
        d for d in PROBLEMS_DIR.iterdir()
        if d.is_dir() and (d / "Main.lean").exists()
    ])

    if names:
        selected = []
        for name in names:
            match = [d for d in all_dirs if d.name == name]
            if not match:
                sys.exit(f"Error: problem '{name}' not found. Available: {[d.name for d in all_dirs]}")
            selected.extend(match)
        return selected

    return all_dirs


def read_problem(problem_dir: Path) -> tuple[str, str]:
    """Read a problem's Main.lean and return (name, full statement without sorry)."""
    name = problem_dir.name
    text = (problem_dir / "Main.lean").read_text()
    statement = text.replace(":= by\n  sorry", "").replace(":= by sorry", "").strip()
    return name, statement


def verify_proof(proof_path: Path) -> tuple[bool, str]:
    """Compile a proof file against the FormalQualBench Lake project."""
    if not proof_path.exists():
        return False, "Proof file not found"

    content = proof_path.read_text()
    if "sorry" in content:
        return False, "Proof contains sorry"
    for banned in ["axiom ", "native_decide", "exact?", "apply?", "simp?", "decide?"]:
        if banned in content:
            return False, f"Proof contains disallowed '{banned.strip()}'"
    if re.search(r"^\s*import\s+FormalQualBench\.\w+", content, re.MULTILINE):
        return False, "Proof imports FormalQualBench.* (benchmark canonical module; contains target as sorry)"

    try:
        result = subprocess.run(
            ["lake", "env", "lean", str(proof_path)],
            capture_output=True, text=True, timeout=600,
            cwd=str(FQB_DIR),
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        if result.returncode != 0:
            return False, output if output else f"Exit code {result.returncode}"
        # Check for sorry in compiler output (apply?/exact? leave sorry behind)
        if "declaration uses `sorry`" in output or "uses 'sorry'" in output:
            return False, "Proof uses sorry (via tactic query)"
        if "error" in output.lower():
            return False, output
        return True, output if output else "OK"
    except subprocess.TimeoutExpired:
        return False, "Compilation timed out (600s)"


def run_agent(problem_name: str, statement: str, model: str, max_turns: int | None,
              proof_dir: Path, transcript_dir: Path) -> dict:
    """Run Lea on a single FQB problem."""
    from lea.agent import run

    proof_dir.mkdir(parents=True, exist_ok=True)
    transcript_dir.mkdir(parents=True, exist_ok=True)
    proof_path = proof_dir / f"{problem_name}.lean"

    task = (
        f"Prove the following Lean 4 theorem. Write the complete proof "
        f"(including all imports, namespace, and the theorem) to: {proof_path}\n\n"
        f"```lean\n{statement}\n```\n\n"
        f"The file must compile with `lake env lean` in the FormalQualBench project "
        f"with zero errors, no `sorry`, and no custom `axiom` declarations.\n\n"
        f"This is a research-level theorem. If you need intermediate lemmas, define them "
        f"in the same file within the namespace. Use `exact?`, `apply?`, and `search_mathlib` "
        f"to find relevant Mathlib lemmas. Think carefully about the proof strategy before writing code."
    )

    started_at = datetime.now(timezone.utc).isoformat()
    start = time.time()
    transcript = None
    try:
        agent_output, transcript = run(
            task, model=model, max_turns=max_turns, return_transcript=True
        )
    except Exception as e:
        agent_output = f"Agent error: {e}"
    elapsed = time.time() - start
    finished_at = datetime.now(timezone.utc).isoformat()

    # Verify
    success, verify_output = verify_proof(proof_path)

    # Save transcript
    transcript_data = {
        "problem": problem_name,
        "started_at": started_at,
        "finished_at": finished_at,
        "time_s": round(elapsed, 1),
        "success": success,
        "verify_output": verify_output[:1000],
    }
    if transcript:
        transcript_data["turns"] = transcript["turns"]
        transcript_data["usage"] = transcript["usage"]
        transcript_data["messages"] = transcript["messages"]
    else:
        transcript_data["agent_output"] = agent_output[:2000] if isinstance(agent_output, str) else ""

    transcript_path = transcript_dir / f"{problem_name}.json"
    transcript_path.write_text(json.dumps(transcript_data, indent=2))

    return {
        "problem": problem_name,
        "success": success,
        "time_s": round(elapsed, 1),
        "turns": transcript["turns"] if transcript else 0,
        "usage": transcript["usage"] if transcript else {},
        "verify_output": verify_output[:500],
        "agent_output": agent_output[:500] if isinstance(agent_output, str) else "",
    }


def load_results(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def main():
    parser = argparse.ArgumentParser(description="Evaluate Lea on FormalQualBench")
    parser.add_argument("--model", default="gemini-3.1-pro-preview")
    parser.add_argument("--max-turns", type=int, default=None, help="Max turns per problem (default: unlimited)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--problems", nargs="+", default=None, help="Specific problem names to run")
    parser.add_argument("--resume", type=str, default=None)
    args = parser.parse_args()

    problems = discover_problems(args.problems)
    if args.limit:
        problems = problems[:args.limit]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_name = f"fqb_{timestamp}"
    results_path = Path(args.resume) if args.resume else RESULTS_DIR / f"{run_name}.json"
    transcript_dir = RESULTS_DIR / f"{run_name}_transcripts"

    existing = load_results(results_path) if args.resume else {}
    completed = set(existing.get("completed", {}).keys())
    if args.resume:
        transcript_dir = results_path.parent / f"{results_path.stem}_transcripts"

    proof_dir = FQB_DIR / "eval_proofs"

    results = existing.get("completed", {})
    passed = sum(1 for r in results.values() if r["success"])
    total = len(results)

    print(f"FormalQualBench eval: {len(problems)} problems, model={args.model}, max_turns={args.max_turns}")
    print(f"Transcripts: {transcript_dir}")
    if completed:
        print(f"Resuming: {len(completed)} already done ({passed}/{total} passed)")
    print()

    for problem_dir in problems:
        name = problem_dir.name
        if name in completed:
            continue

        problem_name, statement = read_problem(problem_dir)

        print(f"[{total + 1}/{len(problems)}] {name}", flush=True)

        result = run_agent(problem_name, statement, args.model, args.max_turns,
                           proof_dir, transcript_dir)
        results[name] = result
        total += 1

        if result["success"]:
            passed += 1
            print(f"  PASS ({result['time_s']}s, {result['turns']} turns)")
        else:
            print(f"  FAIL ({result['time_s']}s, {result['turns']} turns) — {result['verify_output'][:100]}")

        print(f"  Running: {passed}/{total} ({100*passed/total:.1f}%)\n", flush=True)

        output = {
            "benchmark": "FormalQualBench",
            "model": args.model,
            "max_turns": args.max_turns,
            "passed": passed,
            "total": total,
            "pass_rate": round(100 * passed / total, 1) if total else 0,
            "completed": results,
        }
        results_path.write_text(json.dumps(output, indent=2))

    print(f"\n{'='*50}")
    print(f"FormalQualBench: {passed}/{total} ({100*passed/total:.1f}%)")
    print(f"Results: {results_path}")
    print(f"Transcripts: {transcript_dir}")


if __name__ == "__main__":
    main()
