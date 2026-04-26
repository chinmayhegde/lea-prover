# Lea Evaluations

Methodology, configurations, and per-run results across Lea iterations. TL;DR is in the [README](README.md). Per-run detail reports live under [`fqb-reports/`](fqb-reports/).

## Verifier

Through Lea v2.1 (April 2026): `lake env lean` compilation + grep for `sorry`, banned tokens, and `import FormalQualBench.*`. Pass rates required a manual post-hoc audit for namespace shadowing and other semantic exploits not visible to string checks.

From 2026-04-26 onward: [SafeVerify](third_party/SafeVerify/) ([upstream](https://github.com/GasStationManager/SafeVerify)) — kernel replay against the canonical `Main.lean`, per-declaration body/type match, axiom whitelist. Catches namespace shadowing, `:= True/False` trivializations, import-sorry, and empty/comment-only file bypasses in one place. Pass rates from v2.1 onward are audit-free.

## Lea v1 — Gemini 3.1 Pro, single-pass (no retries), default prompts

| Benchmark | Pass rate | Problems | Avg cost | Avg time | Total time |
|-----------|-----------|----------|----------|----------|------------|
| [miniF2F](https://github.com/yangky11/miniF2F-lean4) validation | **211/244 (86.5%)** | Competition math (AMC, AIME, IMO) | $0.13 | 1m 43s | 7h 0m |
| [FormalQualBench](https://github.com/math-inc/FormalQualBench) | **2/23 (9%)** legit | Graduate-level (PhD qualifying exam) | $2.60 | 9m 21s | 3h 35m |

FQB problems legitimately solved: De Bruijn-Erdős theorem (batch), Jordan derangement theorem (standalone run; not reproduced in batch due to nondeterminism). The batch also recorded a pass on Quillen-Suslin, which a post-hoc audit reclassified as a cheat — the agent shadowed `Module.Free` with a local `abbrev Free (_R _P) := True` and closed the theorem with `trivial`.

## Lea v2 — best-of-5 + inter-attempt feedback + lean4-skills prompt patches

Best-of-5 sampling with sequential attempts: after each failed attempt, the verifier's output is fed to the next attempt with the instruction to try a meaningfully different approach. System prompt adds a goal-shape → tactic cascade, an English → Lean phrasebook, and a header-fence rule, borrowed from [`cameronfreer/lean4-skills`](https://github.com/cameronfreer/lean4-skills).

| Model | Benchmark | Pass rate | Avg cost | Avg time | Total time |
|-------|-----------|-----------|----------|----------|------------|
| Gemini 3.1 Pro | FormalQualBench | **5/23 (22%)** legit | $18.43 | 51m 0s | 19h 33m |
| Claude Opus 4.7 | FormalQualBench | **3/23 (13%)** legit | $37.38 | 19m 30s | 7h 29m |

Pass rates are legitimate solves after a post-hoc audit for cheats (name shadowing, header modification, sorry-in-imports, and related structural exploits caught by FormalQualBench-style Comparator verification but not by plain `lake env lean` + sorry grep). Gemini's run had 6/23 raw passes including one cheat (`def Nat.Prime := True` on Maynard–Tao); Opus's 3/23 raw passes all audited clean.

Cost figures are the harness estimate using uncached input pricing and do not account for Anthropic prompt caching — the real dashboard bill on the Opus run was roughly 1/3 the estimate.

## Lea v2.1 — best-of-5 baseline, independent attempts (current)

The `--feedback` gate was removed after the [blueprint + selective-feedback experiment](fqb-reports/fqb-blueprint-selfb-report.md) showed it was net-negative across both models. Current configuration: best-of-5 with independent trials, lean4-skills prompt patches retained. Verifier swapped to SafeVerify on 2026-04-26 — the run below was originally audited manually; numbers have been confirmed against SafeVerify post-hoc.

| Model | Benchmark | Pass rate | Avg cost | Avg time | Total time |
|-------|-----------|-----------|----------|----------|------------|
| **Claude Opus 4.7** | FormalQualBench | **6/23 (26%)** legit | $19.25 | 11m 20s | 4h 20m |
| Gemini 3.1 Pro | FormalQualBench | **5/23 (22%)** legit | $11.15 | 32m 7s | 12h 18m |

**6/23 is the current Lea best on FormalQualBench** ([detail report](fqb-reports/fqb-opus-bon5-report.md)). Multi-model union also lands at 6/23: Opus picks up Gleason–Kahane–Żelazko (a problem only OpenGauss and opencode have solved on the public leaderboard) which Gemini misses, while Gemini's audited solves in this run are a subset of Opus's.

Audit notes: Opus's 7/23 raw included one cheat (`abbrev Free := True` shadowing of `Module.Free` on Quillen-Suslin) — the first documented Opus shadow on this benchmark, and a correction to the prior characterization that "Opus refuses honestly" (which held for easier problems but not when the path forward is genuinely impossible in Mathlib). Gemini's 7/23 raw included two cheats: a `def Prime := True` shadow on Green-Tao, and a one-line `-- Unprovable` file on Pontryagin Duality that exposed an empty-file verifier gap. SafeVerify rejects all three.

## Running evals

```bash
# Clone benchmarks
git clone https://github.com/yangky11/miniF2F-lean4
git clone https://github.com/math-inc/FormalQualBench

# Build each (downloads Mathlib)
cd miniF2F-lean4 && lake exe cache get && lake build && cd ..
cd FormalQualBench && lake exe cache get && lake build && cd ..

# Build SafeVerify (verifier; matches FQB toolchain v4.28.0)
cd third_party/SafeVerify && lake update && lake build safe_verify && cd ../..

# Run miniF2F validation split
uv run python -m eval.run_minif2f --split valid

# Run FormalQualBench
uv run python -m eval.run_fqb

# Check progress while running
cat eval/results/valid_*.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{d[\"passed\"]}/{d[\"total\"]} ({d[\"pass_rate\"]}%)')"
```

Results are saved to `eval/results/` with per-problem transcripts. Use `--resume <path>` to continue a partial run.

## Cheat regression suite

`tests/cheats/test_cheats.py` runs the three known FQB cheat patterns through SafeVerify and exits non-zero if any are accepted:

```bash
uv run python -m tests.cheats.test_cheats
```
