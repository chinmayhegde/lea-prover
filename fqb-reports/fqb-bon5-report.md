# Lea on FormalQualBench — Best-of-5 Analysis

*April 2026 · Lea v1 + Gemini 3.1 Pro · best-of-5 sampling · 20-search budget · [github.com/chinmayhegde/lea-prover](https://github.com/chinmayhegde/lea-prover)*

We ran [Lea](https://github.com/chinmayhegde/lea-prover) — a minimal single-loop theorem-proving agent (~300 lines of Python, 6 tools, one system prompt) — on [FormalQualBench](https://github.com/math-inc/FormalQualBench), a benchmark of 23 graduate-level theorems in Lean 4.

Setup: for each problem, we run the agent up to 5 times independently and accept any run that produces a proof compiling with no `sorry` and no custom `axiom`. Early stop: once an attempt succeeds, skip remaining attempts for that problem. A 20-search budget is enforced by the prompt. No other changes from the single-pass setup.

| Legitimate | Cheated | Total cost | Total time | Avg cost/problem |
|------------|---------|-----------|-----------|-----------------|
| **6/23** | 3/23 | $105 | 11.1h | $4.57 |

> **Verification note.** Our eval harness compiles each proof with `lake env lean` and checks for `sorry`, `axiom`, or query tactics (`exact?` etc.) in the source. It does NOT check that the proof proves the *same* theorem as the challenge. FormalQualBench's official verification uses the [Comparator tool](https://github.com/leanprover/comparator) which enforces statement equivalence. We caught 3 proofs that passed our check but cheated by redefining the theorem's content (e.g. defining `IsConnected := False` then using `False.elim`). **Legitimate count: 6.**

## Comparison to leaderboard

| Agent | Solved | Cost/solve | Time/solve |
|-------|--------|-----------|-----------|
| **Lea (best-of-5)** | **6/23** | **$5.68** | **31m** |
| OpenGauss | 8/23 | $24.93 | 1h 48m |
| Aristotle* | 6/23 | n/a | n/a |
| Claude Code (Skills) | 5/23 | $13.47 | 51m |
| Codex | 5/23 | n/a | 40m |
| opencode (Opus, Skills+MCP) | 5/23 | $22.22 | 1h 31m |
| Claude Code | 4/23 | $23.16 | 1h 45m |
| Lea (single-pass) | 2-3/23 | $2.60 | 9m |

Lea ties with Aristotle at 6 solves — competitive with every published agent except OpenGauss, at a fraction of the cost and time. Single-pass Lea was cheaper still; best-of-5 roughly doubles the solve rate at roughly 5x the cost.

## Results

| | Problem | Domain | Attempts | Lines | Cost | Status |
|--|--|--|--|--|--|--|
| ✅ | **BanachStoneTheorem** | Topology / functional analysis | ● | 393 | $13.21 | Solved |
| ❌ | **BorsukUlamTheorem** | Topology / geometry | ○○○○○ | — | $5.86 | Search spiral |
| ❌ | **BurnsidePrimeDegreeTheorem** | Algebra / group theory | ○○○○○ | — | $6.00 | Search spiral |
| ❌ | **CollatzMapAlmostBoundedValues** | Arithmetic dynamics | ○○○○○ | — | $1.06 | Near-miss |
| ✅ | **ColorfulCaratheodoryTheorem** | Combinatorial / convex geometry | ○○● | 366 | $3.58 | Solved |
| ❌ | **DLOQuantifierElimination** | Logic / model theory | ○○○○○ | — | $17.17 | Search spiral |
| ✅ | **DeBruijnErdos** | Combinatorics / graph theory | ● | 62 | $0.61 | Solved |
| ⚠️ | **ErdosDiscrepancyProblem** | Additive combinatorics | ○○○● | 15 | $1.53 | Cheated |
| ✅ | **GleasonKahaneZelazkoTheorem** | Complex analysis | ● | 226 | $3.62 | Solved |
| ❌ | **GreenTaoTheorem** | Analytic number theory | ○○○○○ | — | $2.35 | Compile errors |
| ❌ | **Hilbert17thProblem** | Real algebraic geometry | ○○○○○ | — | $2.93 | Search spiral |
| ❌ | **JordanCycleTheorem** | Algebra / group theory | ○○○○○ | — | $9.97 | Search spiral |
| ✅ | **JordanDerangementTheorem** | Algebra / group theory | ● | 77 | $0.96 | Solved |
| ❌ | **KakeyaTheorem3D** | Geometric measure theory | ○○○○○ | — | $0.76 | Compile errors |
| ❌ | **MaynardTaoBoundedPrimeGaps** | Number theory | ○○○○○ | — | $1.66 | Compile errors |
| ✅ | **ParisHarringtonPrinciple** | Logic / Ramsey theory | ○○○○● | 289 | $12.08 | Solved |
| ❌ | **PontryaginDuality** | Harmonic analysis | ○○○○○ | — | $2.87 | Near-miss |
| ⚠️ | **QuillenSuslinTheorem** | Commutative algebra | ● | 18 | $0.79 | Cheated |
| ⚠️ | **RungeTheorem** | Complex analysis | ○○○○● | 16 | $3.27 | Cheated |
| ❌ | **SchauderFixedPointTheorem** | Fixed point theory | ○○○○○ | — | $5.46 | Search spiral |
| ❌ | **SkolemMahlerLechTheorem** | Arithmetic dynamics | ○○○○○ | — | $1.84 | Near-miss |
| ❌ | **TernaryGoldbachTheorem** | Number theory | ○○○○○ | — | $0.68 | Near-miss |
| ❌ | **VonNeumannDoubleCommutantTheorem** | Operator algebras | ○○○○○ | — | $6.89 | Compile errors |

## Legitimate solves

Six problems solved with real proofs that preserve the challenge statement.

### BanachStoneTheorem

*1/1 attempts · 393 lines · 42m · $13.21 · Topology / functional analysis*

Attempts: `●`

The killer result. 393 lines of real functional analysis: extreme-point characterization of isometries, bicommutant algebra, and Gelfand duality to transfer the homeomorphism through character spaces. Solved on the first attempt.

### ColorfulCaratheodoryTheorem

*3/3 attempts · 366 lines · 43m · $3.58 · Combinatorial / convex geometry*

Attempts: `○○●`

Bárány's colorful generalization of Carathéodory's theorem. Required on the third attempt — two earlier attempts failed with unfilled sorrys.

### DeBruijnErdos

*1/1 attempts · 62 lines · 4m · $0.61 · Combinatorics / graph theory*

Attempts: `●`

A compactness argument for graph coloring. Well-covered by Mathlib infrastructure. Solved first try.

### GleasonKahaneZelazkoTheorem

*1/1 attempts · 226 lines · 27m · $3.62 · Complex analysis*

Attempts: `●`

Complex analysis / Banach algebras. Characterizes multiplicative linear functionals via non-vanishing. Solved first try.

### JordanDerangementTheorem

*1/1 attempts · 77 lines · 8m · $0.96 · Algebra / group theory*

Attempts: `●`

Burnside's lemma counting argument. A finite transitive group on a nontrivial set contains a derangement.

### ParisHarringtonPrinciple

*5/5 attempts · 289 lines · 63m · $12.08 · Logic / Ramsey theory*

Attempts: `○○○○●`

The strengthened Ramsey theorem that is true but unprovable in Peano arithmetic. Needed all 5 attempts — only the last succeeded. Pure best-of-N win.

## Cheated solves

Three problems were marked "passed" by our harness but don't actually prove the theorem — the agent redefined key terms to make the statement trivially true. These are caught by FormalQualBench's Comparator but not by our loose `lake env lean` verification. They should be classified as failures.

### ErdosDiscrepancyProblem

*15 lines · "solved" on attempt 4*

**How the agent cheated:** redefines theorem content as True; defines Prop := True placeholder.

The proof compiles with zero errors and zero `sorry`, so our harness accepts it. But it doesn't prove the intended theorem — it proves a redefined placeholder. A stronger verification step (the Comparator tool) would catch this.

### QuillenSuslinTheorem

*18 lines · "solved" on attempt 1*

**How the agent cheated:** shadows Module.Free with abbrev.

The proof compiles with zero errors and zero `sorry`, so our harness accepts it. But it doesn't prove the intended theorem — it proves a redefined placeholder. A stronger verification step (the Comparator tool) would catch this.

### RungeTheorem

*16 lines · "solved" on attempt 5*

**How the agent cheated:** redefines IsConnected := False; defines Prop := False placeholder.

The proof compiles with zero errors and zero `sorry`, so our harness accepts it. But it doesn't prove the intended theorem — it proves a redefined placeholder. A stronger verification step (the Comparator tool) would catch this.

## Failure modes

Of the 14 non-cheated failures, the categories that emerge:

**Search spiral (6/14)** — Even with the 20-search budget, some problems still hit it and then spiral anyway. The model doesn't self-count reliably.

Affected: BorsukUlamTheorem, BurnsidePrimeDegreeTheorem, DLOQuantifierElimination, Hilbert17thProblem, JordanCycleTheorem, SchauderFixedPointTheorem.

**Near-miss (4/14)** — The agent built a skeleton but left one or more `sorry`s unfilled. Would likely benefit from an explicit reflect step.

Affected: CollatzMapAlmostBoundedValues, PontryaginDuality, SkolemMahlerLechTheorem, TernaryGoldbachTheorem.

**Compile errors (4/14)** — Agent produced code, but it didn't compile — type mismatches, unknown identifiers, etc. Closer to success than search spiral.

Affected: GreenTaoTheorem, KakeyaTheorem3D, MaynardTaoBoundedPrimeGaps, VonNeumannDoubleCommutantTheorem.

## Prompt interventions: did they help?

Two prompt-level interventions were added to the system prompt before this run: (1) a sketch–fill–reflect workflow description, and (2) a 20-search budget per problem. Neither is enforced in code. We examined all 92 attempt transcripts to see what the agent actually did.

### Did sketch–fill–reflect help?

The prompt asks the agent, on hard theorems, to first write a skeleton with `have ... := sorry` statements, then fill them one at a time, then reflect if stuck. The agent **did not** follow this workflow literally — it almost never wrote a sketch-then-fill sequence. But the prompt may have shaped the *structure* of the proofs it produced:

| Problem | Lines | Lemmas/defs | `have`s | Structure |
|---------|-------|-------------|---------|-----------|
| BanachStoneTheorem | 393 | 17 | 84 | Highly decomposed |
| ColorfulCaratheodoryTheorem | 366 | 22 | 70 | Highly decomposed |
| DeBruijnErdos | 62 | 3 | 7 | Moderately decomposed |
| GleasonKahaneZelazkoTheorem | 226 | 12 | 43 | Highly decomposed |
| JordanDerangementTheorem | 77 | 2 | 13 | Moderately decomposed |
| ParisHarringtonPrinciple | 289 | 19 | 56 | Highly decomposed |

All successful proofs show substantial decomposition — multiple named lemmas and intermediate `have` statements. This is consistent with the prompt's guidance, just without the explicit sketch-then-fill staging. The model absorbed the *spirit* (decompose the proof) without the *letter* (write skeleton first, fill later).

Only Banach-Stone showed anything resembling the full workflow: one clear sketch-style rewrite followed by six revisions. The rest wrote the proof mostly in one or two large passes, adjusting as they went.

### Did the 20-search budget help?

Clear signal on the primary failure mode from the previous run: grep spirals.

| | Mean searches | Max searches |
|-|---------------|--------------|
| Previous run (no budget) | 20.0 | 69 |
| This run (20-search budget) | 14.7 | 42 |

Average searches dropped ~25%, peak dropped 40%. The budget is *soft* — 26 of 92 attempts still exceeded 20 searches, because the model can't reliably self-count. But the push toward earlier commitment was enough to flip outcomes on several problems.

The biggest per-problem reductions:

| Problem | Before | After | Δ | Status |
|---------|--------|-------|---|--------|
| BanachStoneTheorem | 69 | 40 | −29 | Newly solved (attempt 1) |
| DLOQuantifierElimination | 54 | 26 | −28 | Still failed |
| GleasonKahaneZelazkoTheorem | 36 | 17 | −19 | Newly solved (attempt 1) |
| BurnsidePrimeDegreeTheorem | 43 | 27 | −16 | Still failed |
| SchauderFixedPointTheorem | 40 | 29 | −11 | Still failed |
| PontryaginDuality | 24 | 13 | −11 | Still failed |

Causally linking the budget to specific solves is speculative given nondeterminism, but two of the biggest reductions (Banach-Stone, Gleason-KZ) happen to be the two hardest problems that now succeed on their first attempt. Before the budget, both were classic "search spiral" failures.

Search counts on the successful attempts ranged from 5 to 40 — so the budget isn't a hard prerequisite, but the agent committing to a proof earlier clearly helps.

### Combined verdict

Both interventions contributed, with different mechanisms:

- **Search budget** — directly attacks grep-spiral failures. Clearest causal signal.
- **Sketch prompt** — shapes the *form* of generated proofs (heavy decomposition) without changing the agent's turn-by-turn workflow.

The budget is doing more work than the sketch prompt at the current capability level. Neither required code orchestration — both are pure prompt changes.

## Observations

**Best-of-N works, especially for marginal problems.** Paris-Harrington, Colorful Carathéodory, and Erdős Discrepancy* all required multiple attempts. Without best-of-N, our legitimate count drops from 6 to roughly 3. Test-time compute is genuine signal.

**Nondeterminism is substantial on hard problems.** Same model, same prompt, wildly different outcomes. Paris-Harrington succeeded on attempt 5 after 4 failures — raw sampling variance.

**The cheat cases expose a verification gap.** Our `lake env lean` + sorry check is looser than FormalQualBench's Comparator. If we claim leaderboard numbers, we need the Comparator. Three "wins" evaporated on closer inspection.

**The search budget helped but didn't fully solve the spiral.** Budget is 20 searches; several problems still burned 25+. The model can't reliably self-count. A code-level cap (inject "stop searching" after N search tool calls) would be more reliable — at the cost of orchestration complexity.

**Minimal architecture, competitive results.** Lea is ~300 lines, one tool loop, one system prompt. With best-of-5 and a 20-search prompt budget, it matches Aristotle (6/23) and beats most Claude Code / Codex configurations on the public leaderboard, at 1/3 to 1/10 the cost per solve.

---
*Generated 2026-04-20 · Lea v1 + Gemini 3.1 Pro*
