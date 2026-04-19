# Lea

A minimal Lean 4 theorem proving agent, inspired by [pi](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent).

Lea translates natural-language math statements into Lean 4 proofs that compile with zero errors and zero `sorry`s.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and at least one API key.

```bash
# Install elan (Lean version manager — provides lean, lake, etc.)
curl https://elan.lean-lang.org/elan-init.sh -sSf | sh

# Set your API key
export GOOGLE_API_KEY=...     # for Gemini models (default)
export ANTHROPIC_API_KEY=...  # for Claude models
export OPENAI_API_KEY=...     # for GPT/o-series models

# Build the Lean workspace (downloads Mathlib — takes a while the first time)
cd workspace && lake build && cd ..

# That's it. Run:
uv run lea "Prove that the square root of 2 is irrational"
```

## Example

Define the Ackermann function, prove it's strictly monotone and grows faster than its argument, and compute `ackermann 4 1 = 65533`:

```bash
uv run lea "Define the Ackermann function using well-founded recursion. Prove that \
  for all m n, ackermann m n > n. Prove that for all m n, \
  ackermann m (n+1) > ackermann m n. Prove ackermann 4 1 = 65533. Do not use Mathlib."
```

See [examples/](examples/) for generated proofs.

## How it works

Lea runs a simple loop:

1. Write a `.lean` file with a first-attempt proof
2. Compile with `lean_check`
3. If it compiles — done. If not — read the errors, edit, retry.
4. If stuck, search Mathlib for relevant lemmas, or use `bash` to explore.

Six tools: `read_file`, `write_file`, `edit_file`, `lean_check`, `search_mathlib`, `bash`. Supports Gemini, Anthropic, and OpenAI models. See [USAGE.md](USAGE.md) for full CLI reference.

## Eval results

Lea v1 with Gemini 3.1 Pro, single-pass (no retries), default prompts:

| Benchmark | Pass rate | Problems | Avg cost | Avg time | Total time |
|-----------|-----------|----------|----------|----------|------------|
| [miniF2F](https://github.com/yangky11/miniF2F-lean4) validation | **211/244 (86.5%)** | Competition math (AMC, AIME, IMO) | $0.13 | 1m 43s | 7h 0m |
| [FormalQualBench](https://github.com/math-inc/FormalQualBench) | **3/23 (13%)** | Graduate-level (PhD qualifying exam) | $2.60 | 9m 21s | 3h 35m |

FQB problems solved: De Bruijn-Erdős theorem, Quillen-Suslin theorem. Jordan derangement theorem solved in a standalone run but not reproduced in the batch eval (nondeterminism).

### Running evals

```bash
# Clone benchmarks
git clone https://github.com/yangky11/miniF2F-lean4
git clone https://github.com/math-inc/FormalQualBench

# Build each (downloads Mathlib)
cd miniF2F-lean4 && lake exe cache get && lake build && cd ..
cd FormalQualBench && lake exe cache get && lake build && cd ..

# Run miniF2F validation split
uv run python -m eval.run_minif2f --split valid

# Run FormalQualBench
uv run python -m eval.run_fqb

# Check progress while running
cat eval/results/valid_*.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{d[\"passed\"]}/{d[\"total\"]} ({d[\"pass_rate\"]}%)')"
```

Results are saved to `eval/results/` with per-problem transcripts. Use `--resume <path>` to continue a partial run.

## Customization

Drop a `lea.md` file in your working directory or workspace root to add project-specific instructions to the system prompt (preferred tactics, import conventions, etc.).
