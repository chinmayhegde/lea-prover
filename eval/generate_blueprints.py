"""Generate natural-language proof outlines (blueprints) for FQB problems.

The outlines are meant as high-level guides that `run_fqb_best_of_n.py
--blueprint-dir <dir>` can inject into the task. Non-committing by design:
the prover agent is told to verify any named Mathlib lemma before using it.

Usage:
    uv run python -m eval.generate_blueprints --out blueprints/
    uv run python -m eval.generate_blueprints --problems DLOQuantifierElimination --out blueprints/
    uv run python -m eval.generate_blueprints --model claude-opus-4-7 --out blueprints/ --overwrite
"""
import argparse
import os
import sys
import time
from pathlib import Path

from eval.run_fqb_best_of_n import discover_problems, read_problem

DEFAULT_MODEL = "claude-opus-4-7"
MAX_TOKENS = 2000

PROMPT_TEMPLATE = """You are a research mathematician writing a proof outline for a graduate student who will formalize the proof in Lean 4 + Mathlib.

THEOREM:
```lean
{statement}
```

Write a natural-language proof outline (300-500 words, 3-7 numbered steps). Your goal is to give the student a roadmap, not a formal proof.

Guidelines:
- Describe math moves at a medium abstraction level. Example: "apply the intermediate value theorem to f on [0, 1]", NOT "exact Real.intermediate_value_Icc ...".
- Refer to well-known results by their standard mathematical name ("Baire category theorem", "Hahn-Banach", "Zorn's lemma"), NOT by Mathlib identifier.
- If Mathlib may lack a prerequisite, say so explicitly: "Mathlib may not have X; the student may need to prove a helper version."
- If the proof is genuinely deep (multi-page argument), acknowledge this and still give the highest-level sketch you can. Do not fabricate a short proof.
- If you believe the theorem as stated is false, open, or known to be unprovable without additional axioms, say so.
- Do NOT cite specific Mathlib lemma names. The student will search for them.

Output format: only the outline. No preamble like "Here is the outline" or a title header. Start directly with step 1.
"""


def generate_blueprint(client, model: str, statement: str) -> tuple[str, int, int]:
    resp = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(statement=statement)}],
    )
    text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text").strip()
    return text, resp.usage.input_tokens, resp.usage.output_tokens


def main():
    parser = argparse.ArgumentParser(description="Generate proof-outline blueprints for FQB problems")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--problems", nargs="+", default=None,
                        help="Specific problem names. Default: all FQB problems.")
    parser.add_argument("--out", required=True, type=str,
                        help="Output directory for <ProblemName>.md files.")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing blueprint files.")
    args = parser.parse_args()

    try:
        import anthropic
    except ImportError:
        sys.exit("Error: `anthropic` package not installed. Run `uv add anthropic`.")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Error: ANTHROPIC_API_KEY not set.")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    client = anthropic.Anthropic()
    problems = discover_problems(args.problems)
    print(f"Generating blueprints for {len(problems)} problems → {out_dir}")
    print(f"Model: {args.model}\n", flush=True)

    total_in = total_out = skipped = 0
    for problem_dir in problems:
        name, statement = read_problem(problem_dir)
        out_path = out_dir / f"{name}.md"
        if out_path.exists() and not args.overwrite:
            print(f"[{name}] skip (exists)", flush=True)
            skipped += 1
            continue

        print(f"[{name}] generating...", end=" ", flush=True)
        start = time.time()
        try:
            text, in_tok, out_tok = generate_blueprint(client, args.model, statement)
        except Exception as e:
            print(f"ERROR: {e}", flush=True)
            continue
        elapsed = time.time() - start
        total_in += in_tok
        total_out += out_tok

        out_path.write_text(text + "\n")
        print(f"{len(text)} chars, {out_tok} out-tokens, {elapsed:.1f}s", flush=True)

    print(f"\nDone. Wrote {len(problems) - skipped} blueprints, skipped {skipped}.")
    print(f"Tokens: {total_in} in, {total_out} out.")


if __name__ == "__main__":
    main()
