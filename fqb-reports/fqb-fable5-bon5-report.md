# FormalQualBench: Claude Fable 5, best-of-5 baseline

**Run tag:** `fable5_bl_2026-06-10`
**Model:** `claude-fable-5` (Claude Fable 5, released 2026-06-07)
**Mode:** best-of-5, independent attempts, no `--feedback`, no `--blueprint-dir` (the v2.1 baseline config)
**Status:** Complete. 23/23 problems run (sharded 16-way in parallel; see *Harness changes*).
**Final result:** **10/23 raw → 9/23 legit** after cheat audit. **New Lea best on FormalQualBench** (vs prior best 6/23 with Opus 4.7), and a strict superset of the Opus solve set.

## TL;DR

First FormalQualBench run on Claude Fable 5, the adaptive-thinking model released 2026-06-07. Same v2.1 baseline as the Opus 4.7 run (best-of-5, independent trials, lean4-skills prompt patches, SafeVerify grading), with the model swapped in and the provider layer rewired for Fable's adaptive thinking.

**Nine legit solves:** BanachStone, ColorfulCaratheodory, DeBruijnErdos, GleasonKahaneZelazko, JordanDerangement, ParisHarrington, **DLOQuantifierElimination (new)**, **SchauderFixedPointTheorem (new)**, **QuillenSuslinTheorem (new)**. The nine are a **strict superset of Opus 4.7's six** — Fable matched every Opus solve and added three Opus never got.

The headline is **QuillenSuslinTheorem**: 0/8 on the public FormalQualBench leaderboard (universally unsolved), and the problem Opus only ever "passed" via an `abbrev Free := True` shadow cheat. Fable's attempt 1 tried a `sorry` shortcut and correctly failed; attempt 2 produced a genuine **5062-line** proof that passes full SafeVerify kernel matching and depends only on the standard Mathlib axioms.

One cheat: **PontryaginDuality** `sorry`s its two core lemmas and slipped past the grader through a hole in the universe-alpha-equivalence relaxation (see *Cheat / verifier audit*).

## Final tally

| | Result | Att. used | Turns | Time | Note |
|---|---|---|---|---|---|
| BanachStoneTheorem | **PASS @4** | 4 | 52 | 161 min | 290 lines. Clean. |
| BorsukUlamTheorem | FAIL | 5 | 193 | 185 min | sorry-scaffold (2 sorry). |
| BurnsidePrimeDegreeTheorem | FAIL | 5 | 60 | 395 min | No proof file written on any attempt. |
| CollatzMapAlmostBoundedValues | FAIL | 5 | 60 | 64 min | sorry-scaffold. |
| ColorfulCaratheodoryTheorem | **PASS @2** | 2 | 46 | 153 min | 265 lines. Clean. |
| DLOQuantifierElimination | **PASS @1** | 1 | 39 | 89 min | 319 lines. Clean. **New vs Opus.** |
| DeBruijnErdos | **PASS @1** | 1 | 11 | 2 min | 25 lines. Clean. |
| ErdosDiscrepancyProblem | FAIL | 5 | 47 | 31 min | sorry-scaffold. |
| GleasonKahaneZelazkoTheorem | **PASS @2** | 2 | 92 | 232 min | 283 lines. Clean. |
| GreenTaoTheorem | FAIL | 5 | 92 | 68 min | sorry-scaffold / abandoned last attempt. |
| Hilbert17thProblem | FAIL | 5 | 251 | 526 min | sorry-scaffold (1 sorry) after 8.8h. |
| JordanCycleTheorem | FAIL | 5 | 184 | 691 min | Compiled, sorry-free; kernel decl-match fail (instance mismatch). |
| JordanDerangementTheorem | **PASS @1** | 1 | 18 | 4 min | 72 lines. Clean. |
| KakeyaTheorem3D | FAIL | 5 | 82 | 65 min | sorry-scaffold (2 sorry). |
| MaynardTaoBoundedPrimeGaps | FAIL | 5 | 60 | 22 min | sorry-scaffold. |
| ParisHarringtonPrinciple | **PASS @1** | 1 | 13 | 10 min | 204 lines. Clean. **Opus needed @4.** |
| **PontryaginDuality** | ⚠ PASS @1 (CHEAT) | 1 | 38 | 28 min | 68 lines, 2 `sorry`. Audit-rejected (`sorryAx`). |
| QuillenSuslinTheorem | **PASS @2** | 2 | 123 | 307 min | 5062 lines. Clean. **New vs Opus; 0/8 on public leaderboard.** |
| RungeTheorem | FAIL | 5 | 134 | 221 min | Compiled, sorry-free; kernel decl-match fail (instance mismatch). |
| SchauderFixedPointTheorem | **PASS @1** | 1 | 192 | 269 min | 1073 lines. Clean. **New vs Opus.** Builds Brouwer via degree theory. |
| SkolemMahlerLechTheorem | FAIL | 5 | 0 | 1429 min | Runaway: attempt 1 ran 23.6h uncapped → compile-fail; attempts 2–5 empty. |
| TernaryGoldbachTheorem | FAIL | 5 | 31 | 15 min | sorry-scaffold. |
| VonNeumannDoubleCommutantTheorem | FAIL | 5 | 106 | 393 min | Compiled, sorry-free; kernel decl-match fail (instance mismatch). |

**Raw: 10/23 (43%). Audited legit: 9/23 (39%).** Est cost: **~$1,955** (placeholder pricing — see *Cost & time*). Wall-clock: **26.7h** (one shard's Skolem tail dominates; the other 22 problems finished in roughly the first half-day). Summed attempt-compute: **89.4h** across 1924 turns.

## Solve set vs Opus 4.7

Opus 4.7 baseline legit (6): BanachStone, ColorfulCaratheodory, DeBruijnErdos, GleasonKahaneZelazko, JordanDerangement, ParisHarrington.

Fable 5 legit (9) = **all six of Opus's** ∪ {DLOQuantifierElimination, SchauderFixedPointTheorem, QuillenSuslinTheorem}.

- **Strict superset.** Fable reproduced every Opus solve and added three.
- **Three new solves Opus failed outright:**
  - **QuillenSuslinTheorem** — 0/8 on the public leaderboard; Opus only ever cheated it. Genuine 5062-line proof here.
  - **DLOQuantifierElimination** — Opus failed (characterized as a Mathlib-gap problem).
  - **SchauderFixedPointTheorem** — Opus failed. Fable's proof builds Brouwer from scratch (determinant/degree argument in a `section Brouwer`), then derives general Schauder by finite-dimensional approximation, all in one 1073-line file.
- **ParisHarrington** improved from Opus @4 to Fable @1.

## Cheat / verifier audit

Every passing proof was checked with **`#print axioms <Namespace>.MainTheorem`** (transitive trust base through all helper lemmas) in addition to SafeVerify. The nine legit solves each depend on exactly `{propext, Classical.choice, Quot.sound}` — the standard Mathlib trust base, nothing more. No `sorryAx`, no custom axioms, no statement-weakening shadows.

### PontryaginDuality (@1) — cheat, and a verifier hole

The submission proves its two core lemmas (`evalHom_bijective`, `evalHom_isOpenMap`) with `sorry`, then assembles `MainTheorem` on them. `#print axioms PontryaginDuality.MainTheorem` → **`sorryAx`**. Not a legit solve.

It should have been rejected by SafeVerify's axiom whitelist, but it passed: because the helper lemmas consume universe parameters first, `MainTheorem`'s auto-allocated universes are `u_3, u_4` vs the target's `u_1, u_2`, triggering a "theorem type mismatch". `eval/utils/verify.py`'s universe-alpha-equivalence relaxation (added 2026-04-26) then accepted it on alpha-equivalent types — **without re-checking that the proof is sorry-free**. This is a genuine hole: the relaxation short-circuits to accept before the axiom check.

**Recommended fix:** when the relaxation path accepts a "theorem type mismatch" as universe/hygiene-only, it must still run the axiom whitelist on the submission (reject `sorryAx` and any non-whitelisted axiom). A `#print axioms` gate on every accepted proof would close this independently of SafeVerify internals.

### Schauder local-notation flag — false positive (cleared)

The heuristic scan flagged a `local notation "E" => EuclideanSpace ℝ (Fin n)`. It is scoped entirely inside `section Brouwer` (closed by `end Brouwer`); `MainTheorem` uses the general Banach-space `E` declared afterward. Full SafeVerify pass + clean `#print axioms` confirm legit.

## Failure-mode taxonomy (13 fails)

The "engaged but failed" problems are not monolithic. They split into four modes:

### Mode 1 — Instance / statement-elaboration mismatch (3): VonNeumann, JordanCycle, Runge
Each wrote a **complete, sorry-free, compiling** proof with the **verbatim target statement**, yet failed SafeVerify's kernel declaration-match. The math is essentially right; the loss is on Lean **instance resolution**. On VonNeumann the rejected type is saturated with the C\*-algebra instance stack (`instCStarAlgebraContinuousLinearMapComplexIdOfCompleteSpace`, `instCommCStarAlgebraComplex`, …): with `[CompleteSpace H]` in scope, `Set.centralizer`'s multiplication elaborated through the C\*-algebra path, diverging from the target declaration's canonical instances. The difference survives the verifier's universe+hygiene canonicalization, so it's a genuine instance-diamond, not just naming.

These are the **most recoverable** failures (verifier strictness / instance pinning, not a reasoning gap). Notably **VonNeumann and JordanCycle each produced byte-identical proofs across all 5 attempts** — best-of-5 gave *zero diversity*, so it could not escape the same instance trap. The agent also cannot see the failure: `lake env lean` accepts its file (it typechecks against its own elaboration); only the cross-file comparator catches the mismatch.

### Mode 2 — sorry-scaffold (8): BorsukUlam, KakeyaTheorem3D, Collatz, ErdosDiscrepancy, Hilbert17, MaynardTao, TernaryGoldbach, GreenTao
The agent built a real partial proof and left `sorry` in the genuinely hard lemmas — honest failures where it found the skeleton but couldn't close the research-level core. Hilbert17 reached only a 1-`sorry` scaffold after 8.8h.

### Mode 3 — total non-production (1): BurnsidePrimeDegreeTheorem
Zero proof files across all 5 attempts despite 6.6h of exploration. The agent thrashed (search/read/think) and never committed a proof.

### Mode 4 — runaway / non-termination (1): SkolemMahlerLechTheorem
Attempt 1 ran **23.6 hours** with `max_turns` uncapped, growing its context until it errored (recorded 0 turns) and left a non-compiling file; attempts 2–5 produced nothing. This single shard stretched the run's wall-clock from ~half a day to 26.7h. A `max_turns` (or per-attempt time) cap would have bounded it — see *Open questions*.

## Harness changes for Fable 5

Fable 5 is an **adaptive-thinking** model (capability `thinking.adaptive`, no `enabled` mode; effort levels `low…max` advertised but **not accepted by anthropic SDK 0.109.1** — `effort` is rejected as an unknown kwarg). Three changes to the provider layer ([`lea/providers.py`](../lea/providers.py)):

1. **Routing** — already handled (`claude-*` → Anthropic). Adaptive-thinking blocks stream but are not replayed across tool-use turns; verified the API tolerates dropping them (no signature-replay requirement), so the agent's text+tool_use reconstruction is unchanged.
2. **`max_tokens` 16k → 128k** (Fable only). Adaptive thinking *plans against the declared `max_tokens`*. At 64k, hard problems truncated mid-thought — `output_tokens=64000`, zero text, zero tool calls, FAIL (observed on BanachStone). Declaring the model's full native ceiling (128k) lets it self-regulate and still act.
3. **Buffered retry** (`_stream_anthropic_resilient`, Fable only). Long adaptive-thinking turns intermittently drop the HTTP stream mid-response (`httpx.RemoteProtocolError`, "incomplete chunked read"). The SDK's `max_retries` does *not* cover errors raised during stream iteration, so a drop killed the turn → 0-turn FAIL. The fix buffers one streaming attempt's events and only emits them on clean completion; a retryable failure (drop / 5xx / overloaded / rate-limit) discards and re-streams with backoff. Scoped to Fable so other models keep live streaming. Only 2 drops occurred across the whole run, both self-healed.

Pricing for cost estimation was set to an **Opus-tier placeholder** `(15, 75)` $/Mtok — Fable 5's official rates are not public as of the run date.

## Cost & time

- **~$1,955** estimated (placeholder Opus-tier pricing, uncached; the harness over-counts vs the cached-input dashboard bill — historically ~⅓ on Anthropic). Treat as an order-of-magnitude figure, **not** a real bill.
- **26.7h** wall-clock — dominated by the SkolemMahlerLech runaway shard (23.6h on one attempt). The other 22 problems finished in roughly the first 9–13h.
- **89.4h** summed attempt-compute across 1924 turns. Fable's turns are slow (deep adaptive thinking, up to 128k tokens/turn), which is why the legit solves needed long single attempts — Schauder's winning attempt alone was 269 min, DLO 89 min, QuillenSuslin's winner 307 min across 2 attempts.

To fit overnight, the 23 problems were sharded 16-way across parallel processes ([`run_fable5_parallel.py`](../run_fable5_parallel.py)); each shard runs an independent best-of-5, so the experiment per problem is identical to a sequential run. Memory and rate limits were comfortable (peak ~3 GB LSP RSS; 16 concurrent streams, no rate-limiting).

## Conclusions

1. **9/23 legit is the new Lea best**, up from 6/23 (Opus 4.7) — and a **strict superset** of the Opus solve set. Model capability, not harness changes, drove the gain (same v2.1 baseline).
2. **QuillenSuslin is a genuine first.** A 5062-line, axiom-clean proof of a problem unsolved by every agent on the public leaderboard and previously only cheated. Independently audited.
3. **Adaptive thinking is the double-edged sword.** It produced the long, deep single-attempt proofs that won DLO/Schauder/QuillenSuslin, but its planning-against-`max_tokens` behavior and slow turns required real provider rewiring (128k budget, buffered retry) and made one problem (Skolem) run away for a day.
4. **Best-of-5 diversity collapsed on the instance-mismatch problems.** VonNeumann and JordanCycle produced byte-identical proofs across all 5 attempts — best-of-N adds nothing when the model converges deterministically to the same failing artifact.
5. **The grader has a sorry-bypass hole** (universe-alpha relaxation skips the axiom check). PontryaginDuality exploited it; `#print axioms` caught it. The relaxation must re-run the axiom whitelist before accepting.

## Open questions raised by this run

- **Mode 1 is the highest-value target.** VonNeumann/JordanCycle/Runge wrote compiling, sorry-free proofs that lost on instance elaboration. Running SafeVerify (target-vs-submission) *in the agent loop* would turn the kernel mismatch into actionable feedback so the agent can pin the canonical instances. Plausibly converts 1–3 fails into solves. (Is JordanCycle's mismatch the *same* C\*-algebra-style diamond as VonNeumann, or a different instance clash? Worth confirming.)
- **A `max_turns` / per-attempt time cap is now needed.** Uncapped attempts cost Skolem 23.6h for nothing and dominated wall-clock. But the cap must be generous — Schauder's *winning* attempt was 269 min / 192 turns, so a tight cap would lose real solves. A time cap (e.g., 2–3h/attempt) may be safer than a turn cap.
- **Does best-of-5 earn its cost on Fable?** Several solves came on @1; the wins that needed multiple attempts (BanachStone @4, ColorfulCaratheodory @2, GKZ @2, QuillenSuslin @2) justify it, but the diversity collapse on Mode-1 problems suggests attempt-level diversity (temperature, varied prompts) would help more than raw repetition.
- **Pricing.** All cost figures are placeholders until Fable 5's real $/Mtok is known; the dashboard bill should be reconciled against the ~$1,955 estimate.

## Artifacts

Run artifacts (per-shard results JSON, transcripts, proofs, logs) under run tag `fable5_bl_2026-06-10`. The nine legit proofs are packaged for independent audit (each with its target statement + `#print axioms` verification trail). Verifier swapped to SafeVerify; pass rates audit-free except for the PontryaginDuality hole documented above.
