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

### Lea v1 — Gemini 3.1 Pro, single-pass (no retries), default prompts

| Benchmark | Pass rate | Problems | Avg cost | Avg time | Total time |
|-----------|-----------|----------|----------|----------|------------|
| [miniF2F](https://github.com/yangky11/miniF2F-lean4) validation | **211/244 (86.5%)** | Competition math (AMC, AIME, IMO) | $0.13 | 1m 43s | 7h 0m |
| [FormalQualBench](https://github.com/math-inc/FormalQualBench) | **2/23 (9%)** legit | Graduate-level (PhD qualifying exam) | $2.60 | 9m 21s | 3h 35m |

FQB problems legitimately solved: De Bruijn-Erdős theorem (batch), Jordan derangement theorem (standalone run; not reproduced in batch due to nondeterminism). The batch also recorded a pass on Quillen-Suslin, which a post-hoc audit reclassified as a cheat — the agent shadowed `Module.Free` with a local `abbrev Free (_R _P) := True` and closed the theorem with `trivial`.

### Lea v2 — best-of-5 + inter-attempt feedback + lean4-skills prompt patches

Best-of-5 sampling with sequential attempts: after each failed attempt, the verifier's output is fed to the next attempt with the instruction to try a meaningfully different approach. System prompt adds a goal-shape → tactic cascade, an English → Lean phrasebook, and a header-fence rule, borrowed from [`cameronfreer/lean4-skills`](https://github.com/cameronfreer/lean4-skills).

| Model | Benchmark | Pass rate | Avg cost | Avg time | Total time |
|-------|-----------|-----------|----------|----------|------------|
| Gemini 3.1 Pro | FormalQualBench | **5/23 (22%)** legit | $18.43 | 51m 0s | 19h 33m |
| Claude Opus 4.7 | FormalQualBench | **3/23 (13%)** legit | $37.38 | 19m 30s | 7h 29m |

Pass rates are legitimate solves after a post-hoc audit for cheats (name shadowing, header modification, sorry-in-imports, and related structural exploits caught by FormalQualBench-style Comparator verification but not by plain `lake env lean` + sorry grep). Gemini's run had 6/23 raw passes including one cheat (`def Nat.Prime := True` on Maynard–Tao); Opus's 3/23 raw passes all audited clean.

Cost figures are the harness estimate using uncached input pricing and do not account for Anthropic prompt caching — the real dashboard bill on the Opus run was roughly 1/3 the estimate.

Detailed per-problem breakdowns, cheat analysis, and cross-model comparisons are in [`fqb-reports/`](fqb-reports/).

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
