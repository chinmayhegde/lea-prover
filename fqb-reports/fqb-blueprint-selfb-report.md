# FormalQualBench: Blueprint + Selective Feedback (run aborted)

**Run tag:** `gemini_selfb_bp_2026-04-25`
**Model:** `gemini-3.1-pro-preview`
**Mode:** best-of-5, `--feedback` (selective), `--blueprint-dir blueprints/`
**Status:** Killed at 14.47h after 16/23 problems, on PontryaginDuality attempt 2.
**Final result:** 4/16 PASS (all 4 audited legit). Net **−1 vs baseline** (5/23).

## TL;DR

The run produced strong evidence that **blueprints in their current form are net negative** and that **selective feedback is essentially a no-op**. Two regressions vs baseline (GleasonKahaneZelazko, ParisHarrington), one improvement (ColorfulCaratheodory: cheat → legit). $442 spent to confirm one fewer legit solve.

The killed run is sufficient to answer the question we asked: should we ship blueprints + feedback? The answer is no, not in this form.

## Final tally (16/23 problems run)

| | Result | Attempts | Total turns | Total time | Note |
|---|---|---|---|---|---|
| BanachStoneTheorem | **PASS @1** | 1 | 199 | 35 min | Held vs baseline. Followed blueprint Step 4 (lattice route). 728-line proof. |
| BorsukUlamTheorem | FAIL | 5 | 289 | 46 min | Failed in baseline too. |
| BurnsidePrimeDegreeTheorem | FAIL | 5 | 366 | 47 min | Failed in baseline too. |
| CollatzMapAlmostBoundedValues | FAIL | 5 | 32 | 11 min | Disengaged (avg 6 turns/attempt). |
| ColorfulCaratheodoryTheorem | **PASS @3** | 3 | 612 | 205 min | **Improvement**: prior runs cheated via `cp`; this run is 461 lines of legit work. |
| DLOQuantifierElimination | FAIL | 5 | 432 | 70 min | Blueprint backfired — see below. |
| DeBruijnErdos | **PASS @1** | 1 | 51 | 5 min | Held vs baseline. |
| ErdosDiscrepancyProblem | FAIL | 5 | 39 | 8 min | Disengaged. |
| GleasonKahaneZelazkoTheorem | FAIL | 5 | 715 | 246 min | **REGRESSION** — baseline @1, this run 5×fail. Attempt 4 logged 0 turns (likely API stall). |
| GreenTaoTheorem | FAIL | 5 | 37 | 11 min | Disengaged. |
| Hilbert17thProblem | FAIL | 5 | 195 | 34 min | Failed in baseline too. |
| JordanCycleTheorem | FAIL | 5 | 361 | 48 min | Failed in baseline too. |
| JordanDerangementTheorem | **PASS @1** | 1 | 68 | 7 min | Held vs baseline. |
| KakeyaTheorem3D | FAIL | 5 | 29 | 4 min | Disengaged. Selective feedback fired here once. |
| MaynardTaoBoundedPrimeGaps | FAIL | 5 | 50 | 6 min | Disengaged. |
| ParisHarringtonPrinciple | FAIL | 5 | 463 | 85 min | **REGRESSION** — baseline @5, this run 5×deep-fail (68-119 turns each). Selective feedback never fired. |
| PontryaginDuality | (partial) | 1+ | — | — | Killed mid-run. |

**Cheat audit (3 PASSes):** All clean — no namespace shadowing, no `import FormalQualBench.*`, no `:= True/False` trivializations, no admission language in transcripts. ColorfulCaratheodory specifically (historical contamination point) was 461 lines of real work; eval_proofs/ scratch was nuked before the run, and the import-sorry verifier reject (added 2026-04-24) was active.

## Regression analysis

**Two confirmed regressions, both baseline solves:**

1. **GleasonKahaneZelazko** — baseline @1 (226-line proof in clean-env baseline). This run: 5×fail, 246 min, deepest attempt 361 turns. Attempt 4 anomaly: 1521s with 0 turns logged, suggesting a stream timeout that ate budget without producing work.

2. **ParisHarrington** — baseline @5. This run: 5 deep failures (68-119 turns each, 13-21 min each). Critically, **all 5 attempts tagged `[blueprint]` only** (never `[feedback+blueprint]`), so selective feedback was inert — attempts ran independently, exactly as the design intended. **The regression is purely on blueprints**, not on feedback.

**One gain:** ColorfulCaratheodory cheat → legit. This is genuinely the import-sorry reject working: prior runs solved this problem by `cp`'ing pre-existing proofs from `eval_proofs/`, which no longer existed and which the verifier would have caught anyway.

**Net:** 4 baseline holds (BanachStone, DeBruijn, JordanDerangement, ColorfulCaratheodory in cheat→legit form) − 2 regressions (GKZ, PH) = **−1 legit solve at $442 cost vs $300-400 baseline**.

## Selective feedback observations

The `_is_near_miss` predicate fired **exactly once** across the entire run:

```
[KakeyaTheorem3D] attempt 3/5 [feedback+blueprint]    # the only firing
```

That attempt still failed. Across 16 problems × ≤5 attempts × 4 inter-attempt gates ≈ 64 opportunities for the predicate to fire, it triggered once.

This is the design working: selective feedback was built specifically to fix the prior `--feedback` run's PH regression by gating on near-miss. PH this run had 5 deep failures with high error counts (>3 errors/attempt), so the predicate correctly returned False → independent trials. PH still failed, but for blueprint reasons, not feedback reasons.

**Conclusion: the feature is essentially a no-op.** It correctly avoids the harm of vanilla feedback (good), but provides no observable benefit (predicate never finds a true near-miss in practice). 30 LoC + a CLI flag for one inert firing.

## Blueprint observations

**Where blueprints helped:** BanachStoneTheorem. The 728-line proof followed Step 4 of the Opus-generated outline ("avoiding extreme-point machinery, use lattice/algebra route"). The agent explicitly built `IsExtremePoint`, `S_equiv`, `list_inf` helpers consistent with the blueprint's prescription. This is the clearest case of a blueprint adding signal.

**Where blueprints hurt:** DLO, ParisHarrington, plausibly GKZ.

**The DLO failure mode is the headline finding:**
- Attempt 1 (141 turns): "Mathlib does not currently contain..." → no file written
- Attempt 2 (51 turns): "this is a known multi-page formal proof that isn't currently..."
- Attempt 3 (48 turns): 91-line skeleton with sorry
- Attempt 4 (139 turns): "this is a known sizable project... Mathlib currently lacks..."
- Attempt 5 (53 turns): "...completely from scratch is a massive project"

The blueprint's honest "Mathlib may lack X; the student may need to formalize a helper" became permission to abandon. 4 of 5 DLO attempts produced no file at all. Opus's honesty (which we praised when generating the outlines) inverted into Gemini's compliance with "this is too hard to attempt."

**Disengagement pattern:** Kakeya3D, MaynardTao, ErdosDiscrepancy, GreenTao all show very short attempts (avg 5-10 turns) — the agent wrote a few lines, hit errors, gave up. Whether this is blueprint-mediated or independent of blueprints can't be cleanly separated without an A/B run.

**Net blueprint impact:** +1 deep solve (BanachStone), at least 2 documented regressions (PH, plausibly GKZ), 1 known disaster pattern (DLO). Cost: turn counts 2-3× higher across the board.

## Leaderboard context (fetched 2026-04-25)

- OpenGauss: 8/23 (Skills + lean-lsp-mcp + Opus 4.6)
- Aristotle: 6/23 (unaudited)
- Claude Code (Skills), Codex, opencode (Skills+MCP): 5/23 each
- Claude Code: 4/23
- Claude Code (MCP), Codex (Skills+MCP CLI): 3/23

**Lea baseline at 5/23 sits in the same tier as Codex and opencode.** All agents at 5+ except Codex use Skills or MCP; the `+Skills` delta on the same Claude Code is +1 problem.

**DLO specifically:** solved by 4 agents (OpenGauss, Claude Code Skills, Codex, Codex Skills+MCP CLI). All 4 have grounding tools we don't. **Prompt-only blueprints will not crack DLO.** This is now a tooling question.

## Cost

- $442.44 over 14.47h on 16 problems = **$27.65/problem average**
- Baseline (no blueprint, no feedback): ~$300-400 across 23 problems = **$15-17/problem**
- Blueprint+feedback runs cost ~1.7-1.8× per problem mostly due to deeper attempts (more turns, more bash/lean_check calls)
- Anthropic cost-tracking bug does not affect Gemini runs (no caching events in usage)

## Recommendations

**Pre–multi-model rollback (ahead of next experiment):**
1. **Delete `--feedback` and `_is_near_miss`.** The predicate fired once in 16 problems with no observable benefit. ~30 LoC.
2. **Don't pass `--blueprint-dir` for the multi-model run.** Keep the `blueprints/` directory and the `--blueprint-dir` machinery in the codebase for future re-test, but don't ship blueprints by default. They're net-negative as currently generated.
3. **Keep the import-sorry reject** (real win — converted ColorfulCaratheodory).
4. **Keep the lean4-skills prompt patches**, except note that only the "use `search_mathlib` not bash grep" rule has empirical signal; the rest are unproven and future A/B candidates.

**Next experiment direction (not in this report):**
- **Multi-model ensemble** (Gemini + Opus + GPT bon5 each, union legit solves) — likely path to 6-7/23.
- **Goal-state grounding** as v3 question. Leaderboard shows clean +1 from Skills; grounding tooling is now the highest-leverage open direction.

**Blueprint v2 (if revisited):**
- Generator prompt needs strong "BUT TRY ANYWAY" framing so "Mathlib may lack X" doesn't become "give up."
- Consider opt-in per-problem rather than blanket injection.
- A/B test against no-blueprint baseline before adopting.

## Artifacts

Run artifacts (proofs, transcripts, log, results JSON, scratch from workspace) archived under tag `gemini_selfb_bp_2026-04-25`. 19 MB total.
