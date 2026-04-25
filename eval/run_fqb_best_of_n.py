"""Evaluate Lea on FormalQualBench with best-of-N sampling.

Runs each problem N times independently, records which attempts succeed,
and reports the best-of-N pass rate.

Usage:
    python -m eval.run_fqb_best_of_n                          # default: 5 attempts
    python -m eval.run_fqb_best_of_n --n 3                    # 3 attempts per problem
    python -m eval.run_fqb_best_of_n --model gpt-4o           # try a different model
    python -m eval.run_fqb_best_of_n --problems DeBruijnErdos # specific problem
    python -m eval.run_fqb_best_of_n --resume results.json    # resume partial run
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FQB_DIR = REPO_ROOT / "FormalQualBench"
PROBLEMS_DIR = FQB_DIR / "FormalQualBench"
RESULTS_DIR = REPO_ROOT / "eval" / "results"

NEAR_MISS_MAX_ERRORS = 3


def _is_near_miss(verify_output: str) -> bool:
    """Feed a prior failed attempt's output forward only if it's close to
    compiling. `declaration uses sorry` (tactic-query leak) or ≤3 compile
    errors count as near-misses. Everything else (banned-token rejects,
    many errors, timeouts) indicates a strategy reset is better than retry
    with feedback."""
    if not verify_output:
        return False
    if "declaration uses `sorry`" in verify_output or "uses 'sorry'" in verify_output:
        return True
    error_count = sum(1 for line in verify_output.splitlines() if "error:" in line.lower())
    return 1 <= error_count <= NEAR_MISS_MAX_ERRORS


def discover_problems(names: list[str] | None = None) -> list[Path]:
    all_dirs = sorted([
        d for d in PROBLEMS_DIR.iterdir()
        if d.is_dir() and (d / "Main.lean").exists()
    ])
    if names:
        selected = []
        for name in names:
            match = [d for d in all_dirs if d.name == name]
            if not match:
                sys.exit(f"Error: problem '{name}' not found.")
            selected.extend(match)
        return selected
    return all_dirs


def read_problem(problem_dir: Path) -> tuple[str, str]:
    name = problem_dir.name
    text = (problem_dir / "Main.lean").read_text()
    statement = text.replace(":= by\n  sorry", "").replace(":= by sorry", "").strip()
    return name, statement


def verify_proof(proof_path: Path) -> tuple[bool, str]:
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
        if "declaration uses `sorry`" in output or "uses 'sorry'" in output:
            return False, "Proof uses sorry (via tactic query)"
        if "error" in output.lower():
            return False, output
        return True, output if output else "OK"
    except subprocess.TimeoutExpired:
        return False, "Compilation timed out (600s)"


def run_single_attempt(problem_name: str, statement: str, model: str,
                       max_turns: int | None, proof_dir: Path,
                       transcript_dir: Path, attempt: int,
                       prev_failure: str | None = None,
                       blueprint: str | None = None) -> dict:
    from lea.agent import run

    proof_dir.mkdir(parents=True, exist_ok=True)
    transcript_dir.mkdir(parents=True, exist_ok=True)
    proof_path = proof_dir / f"{problem_name}_attempt{attempt}.lean"

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

    if blueprint:
        task += (
            f"\n\n## Proof outline (human-provided guide)\n"
            f"Use this outline as a high-level guide. Translate its ideas to Lean 4, "
            f"but VERIFY any Mathlib lemma names it mentions with `search_mathlib` before using them — "
            f"outlines may reference lemmas that don't exist or are named differently in this Mathlib version.\n\n"
            f"{blueprint}"
        )

    if prev_failure:
        task += (
            f"\n\n## Your previous attempt was close but failed\n"
            f"Final `lean_check` / verifier output from the previous attempt:\n"
            f"```\n{prev_failure[:500]}\n```\n"
            f"This is attempt {attempt}. Fix the specific issues above. "
            f"Do not repeat the same mistake."
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

    success, verify_output = verify_proof(proof_path)

    # Save transcript
    transcript_data = {
        "problem": problem_name,
        "attempt": attempt,
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

    transcript_path = transcript_dir / f"{problem_name}_attempt{attempt}.json"
    transcript_path.write_text(json.dumps(transcript_data, indent=2))

    return {
        "attempt": attempt,
        "success": success,
        "time_s": round(elapsed, 1),
        "turns": transcript["turns"] if transcript else 0,
        "usage": transcript["usage"] if transcript else {},
        "verify_output": verify_output[:500],
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate Lea on FQB with best-of-N")
    parser.add_argument("--n", type=int, default=5, help="Number of attempts per problem")
    parser.add_argument("--model", default="gemini-3.1-pro-preview")
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--problems", nargs="+", default=None)
    parser.add_argument("--resume", type=str, default=None)
    parser.add_argument("--feedback", action="store_true",
                        help="Feed the previous failed attempt's output forward, but only on near-misses "
                             "(compile-error count ≤ 3, or tactic-query sorry leak). Non-near-miss failures "
                             "get independent trials.")
    parser.add_argument("--blueprint-dir", type=str, default=None,
                        help="Directory containing per-problem proof outlines (<ProblemName>.md). "
                             "When present, the outline is injected into the task.")
    args = parser.parse_args()

    problems = discover_problems(args.problems)
    blueprint_dir = Path(args.blueprint_dir) if args.blueprint_dir else None
    if blueprint_dir and not blueprint_dir.is_dir():
        sys.exit(f"Error: blueprint dir not found: {blueprint_dir}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if args.resume:
        results_path = Path(args.resume)
        run_name = results_path.stem
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        run_name = f"fqb_best{args.n}_{timestamp}"
        results_path = RESULTS_DIR / f"{run_name}.json"
    transcript_dir = RESULTS_DIR / f"{run_name}_transcripts"
    proof_dir = FQB_DIR / f"eval_proofs_bon_{run_name}"

    existing = {}
    if args.resume and results_path.exists():
        existing = json.loads(results_path.read_text())

    results = existing.get("problems", {})

    print(f"FormalQualBench best-of-{args.n}: {len(problems)} problems, model={args.model}")
    print(f"Transcripts: {transcript_dir}")
    if results:
        done = sum(1 for r in results.values() if r.get("all_done"))
        print(f"Resuming: {done} problems fully done")
    print()

    for problem_dir in problems:
        name = problem_dir.name

        # Check if this problem is fully done
        if name in results and results[name].get("all_done"):
            continue

        problem_name, statement = read_problem(problem_dir)

        blueprint = None
        if blueprint_dir:
            bp_path = blueprint_dir / f"{problem_name}.md"
            if bp_path.exists():
                blueprint = bp_path.read_text()

        # Figure out which attempts are already done
        existing_attempts = results.get(name, {}).get("attempts", [])
        done_attempt_nums = {a["attempt"] for a in existing_attempts}
        # Seed prev_failure from the most recent completed failed attempt (for resume).
        # Under selective feedback, only feed forward if the prior failure was a near-miss.
        prev_failure = None
        if args.feedback and existing_attempts:
            last_fail = next((a for a in reversed(existing_attempts) if not a.get("success")), None)
            if last_fail:
                candidate = last_fail.get("verify_output") or None
                if candidate and _is_near_miss(candidate):
                    prev_failure = candidate

        for attempt in range(1, args.n + 1):
            if attempt in done_attempt_nums:
                continue

            tags = []
            if args.feedback and prev_failure:
                tags.append("feedback")
            if blueprint:
                tags.append("blueprint")
            tag_str = f" [{'+'.join(tags)}]" if tags else ""
            print(f"[{name}] attempt {attempt}/{args.n}{tag_str}", flush=True)

            result = run_single_attempt(
                problem_name, statement, args.model, args.max_turns,
                proof_dir, transcript_dir, attempt,
                prev_failure=prev_failure if args.feedback else None,
                blueprint=blueprint,
            )
            if args.feedback:
                out = result.get("verify_output") if not result["success"] else None
                prev_failure = out if (out and _is_near_miss(out)) else None

            if name not in results:
                results[name] = {"attempts": [], "all_done": False}
            results[name]["attempts"].append(result)

            status = "PASS" if result["success"] else "FAIL"
            print(f"  {status} ({result['time_s']}s, {result['turns']} turns)", flush=True)

            # Early stop: if we got a pass, skip remaining attempts
            if result["success"]:
                print(f"  Solved on attempt {attempt}! Skipping remaining.", flush=True)
                break

        results[name]["all_done"] = True
        any_pass = any(a["success"] for a in results[name]["attempts"])
        results[name]["solved"] = any_pass

        # Aggregate stats
        total_solved = sum(1 for r in results.values() if r.get("solved"))
        total_done = sum(1 for r in results.values() if r.get("all_done"))
        print(f"  Best-of-{args.n}: {total_solved}/{total_done} solved so far\n", flush=True)

        # Save after each problem
        from lea.agent import MODEL_PRICING, DEFAULT_PRICING
        in_price, out_price = MODEL_PRICING.get(args.model, DEFAULT_PRICING)
        total_cost = 0
        total_time = 0
        for r in results.values():
            for a in r.get("attempts", []):
                usage = a.get("usage", {})
                total_cost += (usage.get("input_tokens", 0) * in_price + usage.get("output_tokens", 0) * out_price) / 1_000_000
                total_time += a.get("time_s", 0)

        output = {
            "benchmark": "FormalQualBench",
            "mode": f"best-of-{args.n}",
            "model": args.model,
            "max_turns": args.max_turns,
            "solved": total_solved,
            "total": total_done,
            "pass_rate": round(100 * total_solved / total_done, 1) if total_done else 0,
            "total_cost": round(total_cost, 2),
            "total_time_s": round(total_time, 1),
            "problems": results,
        }
        results_path.write_text(json.dumps(output, indent=2))

    # Final summary
    total_solved = sum(1 for r in results.values() if r.get("solved"))
    print(f"\n{'='*50}")
    print(f"FormalQualBench best-of-{args.n}: {total_solved}/{len(problems)} ({100*total_solved/len(problems):.1f}%)")
    print(f"Results: {results_path}")
    print(f"Transcripts: {transcript_dir}")


if __name__ == "__main__":
    main()
