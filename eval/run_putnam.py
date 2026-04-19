"""Evaluate Lea on the Putnam 2025 problem set.

Usage:
    python -m eval.run_putnam                       # run all Putnam 2025 problems
    python -m eval.run_putnam --limit 5             # first 5 problems
    python -m eval.run_putnam --resume results.json # resume a partial run
"""

import argparse
import json
import os
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
PUTNAM_DIR = REPO_ROOT / "putnam-lean4"
PROBLEMS_DIR = PUTNAM_DIR / "problems"
RESULTS_DIR = REPO_ROOT / "eval" / "results"

# Axioms Lean considers foundational; anything else is a user-introduced cheat.
ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}


def discover_problems() -> list[Path]:
    """Return sorted list of .lean problem files in the Putnam 2025 set."""
    if not PROBLEMS_DIR.exists():
        sys.exit(f"Error: {PROBLEMS_DIR} not found.")
    return sorted(PROBLEMS_DIR.glob("*.lean"))


def extract_theorem(path: Path) -> tuple[str, str]:
    """Extract the theorem name and full statement (without sorry) from a problem file."""
    text = path.read_text()

    # Extract theorem name
    match = re.search(r"theorem\s+(\w+)", text)
    name = match.group(1) if match else path.stem

    # Extract just the theorem statement (everything from 'theorem' to 'sorry')
    # We give the agent the full file context (imports, opens) plus the theorem
    statement = text.replace(":= by sorry", "").replace(":= sorry", "").strip()

    return name, statement


def _check_axioms(proof_path: Path, theorem_name: str) -> tuple[bool, str]:
    """Run `#print axioms` on the proved theorem. Fail if it depends on any axiom
    outside ALLOWED_AXIOMS (catches agent-introduced `axiom`, `opaque`, `sorryAx`, etc.,
    even across files since `#print axioms` is transitive through imports)."""
    probe_path = proof_path.with_suffix(".axcheck.lean")
    probe_path.write_text(proof_path.read_text() + f"\n\n#print axioms {theorem_name}\n")
    try:
        result = subprocess.run(
            ["lake", "env", "lean", str(probe_path)],
            capture_output=True, text=True, timeout=300,
            cwd=str(PUTNAM_DIR),
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        if "does not depend on any axioms" in output:
            return True, "no axioms"
        m = re.search(r"depends on axioms:\s*\[(.*?)\]", output, re.DOTALL)
        if not m:
            return False, f"could not parse #print axioms output: {output[:200]}"
        axioms = [a.strip() for a in m.group(1).split(",") if a.strip()]
        forbidden = [a for a in axioms if a not in ALLOWED_AXIOMS]
        if forbidden:
            return False, f"forbidden axioms: {forbidden}"
        return True, f"axioms OK: {axioms}"
    except subprocess.TimeoutExpired:
        return False, "Axiom check timed out"
    finally:
        probe_path.unlink(missing_ok=True)


def verify_proof(proof_path: Path, theorem_name: str) -> tuple[bool, str]:
    """Compile a proof file against the putnam-lean4 Lake project. Returns (success, output)."""
    if not proof_path.exists():
        return False, "Proof file not found"

    # Check for sorry in the proof
    content = proof_path.read_text()
    if "sorry" in content:
        return False, "Proof contains sorry"

    try:
        result = subprocess.run(
            ["lake", "env", "lean", str(proof_path)],
            capture_output=True, text=True, timeout=300,
            cwd=str(PUTNAM_DIR),
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        if result.returncode != 0 or "error" in output.lower():
            return False, output if output else f"Exit code {result.returncode}"
    except subprocess.TimeoutExpired:
        return False, "Compilation timed out (300s)"

    # Compile succeeded — verify the proof doesn't sneak in extra axioms.
    ok, ax_msg = _check_axioms(proof_path, theorem_name)
    if not ok:
        return False, ax_msg
    return True, f"OK ({ax_msg})"


def run_agent(theorem_name: str, statement: str, model: str, max_turns: int,
              proof_dir: Path, transcript_dir: Path) -> dict:
    """Run Lea on a single problem. Returns result dict."""
    from lea.agent import run

    proof_dir.mkdir(parents=True, exist_ok=True)
    transcript_dir.mkdir(parents=True, exist_ok=True)
    proof_path = proof_dir / f"{theorem_name}.lean"

    task = (
        f"Prove the following Lean 4 theorem. Write the complete proof "
        f"(including all imports and opens) to: {proof_path}\n\n"
        f"```lean\n{statement}\n```\n\n"
        f"The file must compile with `lake env lean` in the putnam-lean4 project "
        f"with zero errors and no `sorry`."
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
    success, verify_output = verify_proof(proof_path, theorem_name)

    # Save per-problem transcript
    transcript_data = {
        "theorem": theorem_name,
        "started_at": started_at,
        "finished_at": finished_at,
        "time_s": round(elapsed, 1),
        "success": success,
        "verify_output": verify_output[:500],
    }
    if transcript:
        transcript_data["turns"] = transcript["turns"]
        transcript_data["usage"] = transcript["usage"]
        transcript_data["messages"] = transcript["messages"]
    else:
        transcript_data["agent_output"] = agent_output[:2000] if isinstance(agent_output, str) else ""

    transcript_path = transcript_dir / f"{theorem_name}.json"
    transcript_path.write_text(json.dumps(transcript_data, indent=2))

    return {
        "theorem": theorem_name,
        "success": success,
        "time_s": round(elapsed, 1),
        "turns": transcript["turns"] if transcript else 0,
        "usage": transcript["usage"] if transcript else {},
        "verify_output": verify_output[:500],
        "agent_output": agent_output[:500] if isinstance(agent_output, str) else "",
    }


def load_results(path: Path) -> dict:
    """Load existing results for resuming."""
    if path.exists():
        return json.loads(path.read_text())
    return {}


def main():
    parser = argparse.ArgumentParser(description="Evaluate Lea on Putnam 2025")
    parser.add_argument("--model", default="gemini-3.1-pro-preview")
    parser.add_argument("--max-turns", type=int, default=250)
    parser.add_argument("--limit", type=int, default=None, help="Max problems to attempt")
    parser.add_argument("--resume", type=str, default=None, help="Resume from a results JSON file")
    parser.add_argument("--timeout", type=int, default=600, help="Per-problem timeout in seconds")
    args = parser.parse_args()

    problems = discover_problems()
    if args.limit:
        problems = problems[:args.limit]

    # Set up results and transcript directories
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_name = f"putnam2025_{timestamp}"
    results_path = Path(args.resume) if args.resume else RESULTS_DIR / f"{run_name}.json"
    transcript_dir = RESULTS_DIR / f"{run_name}_transcripts"

    # Load existing results for resuming
    existing = load_results(results_path) if args.resume else {}
    completed = set(existing.get("completed", {}).keys())
    if args.resume:
        # Derive transcript dir from existing results file name
        transcript_dir = results_path.parent / f"{results_path.stem}_transcripts"

    # Proof scratch directory
    proof_dir = PUTNAM_DIR / "eval_proofs"

    # cd into the Lake project so load_system_prompt() picks up putnam-lean4/lea.md
    os.chdir(PUTNAM_DIR)

    results = existing.get("completed", {})
    passed = sum(1 for r in results.values() if r["success"])
    total = len(results)

    print(f"Putnam 2025 eval: {len(problems)} problems, model={args.model}")
    print(f"Transcripts: {transcript_dir}")
    if completed:
        print(f"Resuming: {len(completed)} already done ({passed}/{total} passed)")
    print()

    for i, problem_path in enumerate(problems):
        name = problem_path.stem
        if name in completed:
            continue

        theorem_name, statement = extract_theorem(problem_path)

        print(f"[{total + 1}/{len(problems)}] {name}", flush=True)

        result = run_agent(theorem_name, statement, args.model, args.max_turns,
                           proof_dir, transcript_dir)
        results[name] = result
        total += 1

        if result["success"]:
            passed += 1
            print(f"  PASS ({result['time_s']}s, {result['turns']} turns)")
        else:
            print(f"  FAIL ({result['time_s']}s, {result['turns']} turns) — {result['verify_output'][:100]}")

        print(f"  Running: {passed}/{total} ({100*passed/total:.1f}%)\n", flush=True)

        # Save after each problem (crash-safe)
        output = {
            "split": "putnam2025",
            "model": args.model,
            "max_turns": args.max_turns,
            "passed": passed,
            "total": total,
            "pass_rate": round(100 * passed / total, 1) if total else 0,
            "completed": results,
        }
        results_path.write_text(json.dumps(output, indent=2))

    # Final summary
    print(f"\n{'='*50}")
    print(f"Putnam 2025: {passed}/{total} ({100*passed/total:.1f}%)")
    print(f"Results: {results_path}")
    print(f"Transcripts: {transcript_dir}")


if __name__ == "__main__":
    main()
