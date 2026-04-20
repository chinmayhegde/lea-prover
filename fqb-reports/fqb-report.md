# Lea on FormalQualBench — Single-pass baseline

*April 2026 · Lea v1 + Gemini 3.1 Pro · [github.com/chinmayhegde/lea-prover](https://github.com/chinmayhegde/lea-prover)*

We ran [Lea](https://github.com/chinmayhegde/lea-prover), a minimal theorem-proving agent (~300 lines of Python, 6 tools, one system prompt), on [FormalQualBench](https://github.com/math-inc/FormalQualBench) — 23 graduate-level theorems in Lean 4 spanning topology, algebra, analysis, combinatorics, and number theory. These are results at the level of a math PhD qualifying exam whose proofs are not in Mathlib and must be constructed from scratch.

The agent has no proof decomposition, no tree search, no reinforcement learning. It runs a single loop: write a proof, compile, read errors, edit, repeat. The model decides everything.

| Solved | Total cost | Total time | Tokens |
|--------|-----------|-----------|--------|
| 2/23 | $34 | 3.6h | 26.5M |

## Results

| | Problem | Domain | Turns | Time | Cost | Mode |
|--|--|--|--|--|--|--|
| ❌ | BanachStoneTheorem | Topology / functional analysis | 99 | 13m | $2.63 | Wrong path |
| ❌ | BorsukUlamTheorem | Topology / geometry | 47 | 8m | $0.91 | Near-miss |
| ❌ | BurnsidePrimeDegreeTheorem | Algebra / group theory | 60 | 7m | $1.59 | Near-miss |
| ❌ | CollatzMapAlmostBoundedValues | Arithmetic dynamics | 3 | 24s | $0.01 | Gave up early |
| ❌ | ColorfulCaratheodoryTheorem | Combinatorial / convex geometry | 0 | 41m | $0.00 | Gave up early |
| ❌ | DLOQuantifierElimination | Logic / model theory | 209 | 41m | $19.19 | Near-miss |
| ✅ | DeBruijnErdos | Combinatorics / graph theory | 28 | 3m | $0.34 | Solved |
| ❌ | ErdosDiscrepancyProblem | Additive combinatorics | 12 | 3m | $0.07 | Wrong path |
| ❌ | GleasonKahaneZelazkoTheorem | Complex analysis | 49 | 13m | $1.71 | Wrong path |
| ❌ | GreenTaoTheorem | Analytic number theory | 25 | 5m | $0.37 | Wrong path |
| ❌ | Hilbert17thProblem | Real algebraic geometry | 31 | 4m | $0.53 | Wrong path |
| ❌ | JordanCycleTheorem | Algebra / group theory | 34 | 12m | $1.50 | Wrong path |
| ❌ | JordanDerangementTheorem | Algebra / group theory | 0 | 6m | $0.00 | Gave up early |
| ❌ | KakeyaTheorem3D | Geometric measure theory | 4 | 42s | $0.02 | Gave up early |
| ❌ | MaynardTaoBoundedPrimeGaps | Number theory | 32 | 8m | $0.43 | Near-miss |
| ❌ | ParisHarringtonPrinciple | Logic / Ramsey theory | 39 | 8m | $0.83 | Near-miss |
| ❌ | PontryaginDuality | Harmonic analysis | 39 | 7m | $0.61 | Wrong path |
| ✅ | QuillenSuslinTheorem | Commutative algebra | 60 | 9m | $0.96 | Solved |
| ❌ | RungeTheorem | Complex analysis | 0 | 4m | $0.00 | Gave up early |
| ❌ | SchauderFixedPointTheorem | Fixed point theory | 61 | 8m | $1.27 | Wrong path |
| ❌ | SkolemMahlerLechTheorem | Arithmetic dynamics | 37 | 8m | $0.76 | Near-miss |
| ❌ | TernaryGoldbachTheorem | Number theory | 16 | 3m | $0.08 | Near-miss |
| ❌ | VonNeumannDoubleCommutantTheorem | Operator algebras | 38 | 4m | $0.53 | Near-miss |

## Failure modes

The failures cluster into four patterns.

**Search spiral.** The agent spent 50%+ of turns grepping Mathlib source files, hoping to find the theorem pre-built. On Banach-Stone it did 99 turns with 67 greps and only 10 compilation attempts. This misunderstands the benchmark: FQB specifically tests theorems whose proofs must be constructed from scratch.

**Near-miss (sorry remaining).** The agent built a proof structure — definitions, intermediate lemmas, the right imports — but left one or two `sorry`s unfilled. It had no mechanism to step back and reconsider if the decomposition was wrong.

**Gave up early.** The agent recognized the theorem was deep and stopped within 5 turns. Sometimes reasonable (Kakeya 3D, Collatz), sometimes premature (Runge).

**Wrong path.** The agent wrote a proof file to a different location than expected. An infrastructure issue.

## What it solved

**DeBruijnErdos** — 28 turns · 196s · $0.34

If every finite subgraph of an infinite graph is k-colorable, then the whole graph is k-colorable. A compactness argument. The agent found the right Mathlib infrastructure and closed the proof in 28 turns.

**QuillenSuslinTheorem** — 60 turns · 537s · $0.96

Every finitely generated projective module over a polynomial ring is free (Serre's conjecture). A major result in commutative algebra. The agent worked through 60 turns.

## Observations

**The model knows the mathematics.** In almost every case, the agent's final message correctly identifies the theorem, its history, and the proof strategy in natural language. The failure is in translation to Lean, not in mathematical understanding.

**The dominant failure is strategic, not technical.** Most failures are search spirals or near-misses — problems where the agent either never committed to a proof structure or committed to the wrong one and couldn't adapt.

**Cost is heavy-tailed.** One problem (DLO Quantifier Elimination, 209 turns) consumed 33% of the total budget. A turn budget or spiral detection would dramatically reduce cost with minimal impact on solve rate.

**Nondeterminism matters.** Jordan's derangement theorem was solved in one run and failed in another. Best-of-N sampling at the outer level would improve the effective solve rate.

**"Not in Mathlib" ≠ "unprovable."** The agent frequently concluded that a theorem was impossible because it couldn't find it in Mathlib. FQB specifically targets theorems that require building proofs from scratch. The prompt must make this expectation explicit.

---
*Generated 2026-04-20 · Lea v1 + Gemini 3.1 Pro*
