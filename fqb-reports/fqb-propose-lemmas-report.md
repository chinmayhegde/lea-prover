# FormalQualBench: `propose_lemmas` tool experiment (reverted)

**Run tag:** `propose_lemmas_2026-05-04`
**Tool:** `propose_lemmas(path, line, timeout=60)` — goal-aware Mathlib lemma suggestion via Lean's `exact?`.
**Mode:** ad-hoc single-problem dispatches across two repos (lea-prover FQB, lea-hadamard).
**Status:** Implemented, tested across 3 stages, **reverted** per pre-committed acceptance gate.
**Final result:** 9 tool calls, 1 useful suggestion returned, 0 incorporated into a successful proof, 0 problems closed. Per spec gate (matched against the loogle-removal precedent), reverted.

## TL;DR

Built the goal-aware lemma-suggestion tool I'd identified in the previous session as the highest-leverage gap in Lea's tool surface (closes the lemma-search-bound failure mode that grep/loogle don't address). Tool worked mechanically; agent adopted it spontaneously on lemma-search-bound problems; **but no test problem was closed and no returned suggestion was demonstrably incorporated into a successful proof.** Per the empirical bar set by the loogle precedent, retired.

**The interesting finding came out of failure mode, not capability mode:** the agent (both Opus and Gemini) doesn't reliably write intermediate `have ... := sorry` skeletons where `propose_lemmas` would fire. On `lem:weak-comparison`, Opus went directly from "search Mathlib 12 times" to "write top-level `sorry`" in 14 turns, skipping any decomposition phase. Without decomposition first, even a perfect goal-aware lemma-suggestion tool has nothing to suggest *for*. **The bottleneck is workflow, not search quality.**

## The hypothesis

In the previous session's diagnostic of why Lea is stuck on `lem:weak-comparison` (Lindeberg comparison, third-derivative form), I identified four capability gaps relative to Aristotle-class systems, ranked by leverage:

1. Goal-state grounding via LSP (highest)
2. Premise selection via embeddings, not grep
3. Tree search over proof attempts
4. Fine-tuning on Lean traces

`propose_lemmas` is the cheap version of (1) without an MCP dependency: a CLI tool that substitutes Lean's `exact?` at a chosen `sorry`, runs the file, parses suggestions, returns them. ~100 LoC. Pi-ethos compatible — no orchestration, no external service, no fine-tuning. Hypothesized to close 2 layer-0 stucks in lea-hadamard (`lem:weak-comparison` and `lem:cubic`), where the failure mode looks like "I have the goal, I just need the Mathlib name."

## The spec (acceptance gate)

Pre-committed before any test: retain the tool **only** if at least one of:
- (a) Stage 3 problem closed where prior baseline did not, OR
- (b) Tool was called ≥3 times across Stages 2-3 with at least one suggestion accepted into the proof.

Mirrors the loogle removal pattern (zero benefit on three probes → retired).

## Implementation (~100 LoC in `lea/tools.py`)

- New tool `propose_lemmas(path, line, timeout=60)` returning goal type + up-to-10 suggestions.
- Term-mode vs tactic-mode `sorry` substitution detected by walking back from the target to the most recent `:=` (heuristic: if next non-whitespace is `by`, tactic mode → substitute `exact?`; else term mode → substitute `by exact?`). Necessary because `:= sorry` and `... ; sorry` need different replacement tokens to elaborate.
- Temp file lives in the same directory as the source so `lake`'s olean cache hits (≈30-60s saved per call vs `/tmp`).
- Parsing handles two `exact?` output formats: single-line `Try this: exact ...` and continuation-line `Try this:\n  [apply] exact ...` (the format Lean v4.28 currently emits). Strips the `[apply]`/`[exact]`/`[refine]` annotation marker.
- Graceful timeout, missing-file, missing-`sorry`-on-line, and unknown-line errors. No exceptions raised to caller.

Prompt updated in three places (workflow step 3, tactic-cascade reference, "use propose_lemmas before search_mathlib" critical rule).

## Stage 1 — local smoke (no agent, no cost)

Hand-written 3-example file probing tactic-mode, term-mode, and a goal `exact?` cannot close.

| Test | Goal | Expected | Got |
|---|---|---|---|
| Tactic-mode | `0 < Real.exp x` | suggestion | `exact Real.exp_pos x` ✓ |
| Term-mode | `n + 0 = n` | suggestion | `exact Nat.add_eq_left.mpr rfl` ✓ |
| Hard | `∃ x, f x = f x` (with continuity hypothesis) | no suggestions | `no suggestions found` ✓ |
| Out-of-range line | line 99 of 12-line file | error | `Error: line 99 out of range` ✓ |
| Missing file | `does_not_exist.lean` | error | `Error: ... does not exist` ✓ |

Mechanics good. Initial parse missed continuation-line suggestions (`Try this:` on its own line, `[apply] exact ...` indented below); patched. After the patch, all five tests pass.

## Stage 2 — BanachStone (Opus, max-turns 60, best-of-1)

Two parallel runs landed (process-management mistake — first launch's CD failed but the nohup'd process did fire; both ran). Distinct results files / transcripts / proof dirs. Useful as a tiny variance datapoint.

| Run | Turns | Time | Cost (reported) | Tool calls (propose / search / lean_check) | Outcome |
|---|---|---|---|---|---|
| 000601 | 21 | 154.8s | $4.93 | **3** / 14 / 1 | FAIL — honest sorry |
| 000614 | 14 | 137.6s | $3.47 | 0 / 22 / 1 | FAIL — honest sorry |

**Adoption variance.** One run called `propose_lemmas` 3 times, the other zero. Same model, same prompt, same problem. Single-run conclusions on tool adoption are noisy.

**Suggestion outcomes (run 000601):**
- Call 1 (line 14): error — no `sorry` on that line. Run 000614 had moved the sorry mid-attempt.
- Call 2 (line 15): no suggestions. Surfaced a useful diagnostic: agent's submitted file imported `Mathlib.Analysis.NormedSpace.WeakDual` (stale path; the module is now at `Mathlib.Analysis.Normed.Module.WeakDual`).
- Call 3 (line 13): no suggestions.

**Outcome:** both runs honest-sorry'd. Expected — BanachStone is research-level, not lemma-search-bound. This was a smoke test of mechanics, not a value test. Confirmed: tool doesn't crash, doesn't catastrophically eat the turn budget, integrates cleanly.

## Stage 3 — GleasonKahaneZelazko (Gemini, max-turns 100, best-of-1)

Hypothesized highest-value problem: Gemini failed it across all prior baseline runs; lemma-search-bound; the kind of problem where `exact?`-grade suggestions could close a sub-step.

| Turns | Time | Cost | Tool calls (propose / search / bash / lean_check / write_file) | Outcome |
|---|---|---|---|---|
| 100 | 1056s (17.6 min) | $4.83 | **6** / 32 / 56 / 2 / 4 | FAIL — "Proof file not found" |

**Adoption real.** 6 spontaneous `propose_lemmas` calls, including 4 on Gemini's own scratch decomposition files (`GKZ_analytic3.lean` through `GKZ_analytic6.lean`) and 2 on the canonical attempt file. Workflow: Gemini sketched analytic sub-lemmas, called `propose_lemmas` on the resulting sorries, mostly got "no suggestions" back, abandoned each path, repeated.

**Suggestion outcomes:**
- Call 1 (`GKZ_analytic3.lean:7`): **`exact spectrum.units_conjugate`** — real suggestion.
- Calls 2-6: "no suggestions found" or diagnostic about `unexpected token 'by'` (a Gemini scratch-file syntax issue).

The single useful suggestion (`spectrum.units_conjugate`) appears exactly once in the entire transcript — in the tool-result message. Gemini did not incorporate it, did not reference it later, abandoned the analytic3 path entirely.

**Failure mode.** "Proof file not found" — Gemini wrote its final attempt to `FormalQualBench/GleasonKahaneZelazkoTheorem_attempt1.lean` instead of the dispatcher-specified `eval_proofs_bon_fqb_best1_*/GleasonKahaneZelazkoTheorem_attempt1.lean`. The misplaced file contains only `intro φ h1 hinv; sorry`. **Path-following bug, unrelated to the tool.** Even with correct path, the proof was just `sorry`.

## Stage 3b — `lem:weak-comparison` retry (Opus, max-turns 200, lea-hadamard)

The single highest-conviction probe. Predicted in the previous session as the place `propose_lemmas` would specifically help: Lindeberg comparison, exact?-shaped Mathlib targets (`taylor_mean_remainder_lagrange`, etc.), prior Lea retries explicitly diagnosed missing infrastructure as the blocker.

Dispatched via `tools/dispatcher.py` → `uv run lea` (the patched lea-prover) → lea-hadamard project root.

| Turns | Time | Cost | Tool calls (propose / search / bash / write_file) | Outcome |
|---|---|---|---|---|
| 14 | ~3 min | $3.45 | **0** / 12 / many / 1 | honest sorry — same as prior retry |

**Zero `propose_lemmas` calls.** This was the surprise.

**Workflow trace (turns 1-14):**
- Turns 1-4: scope out workspace, find lakefile, list directories.
- Turns 5-11: 12 `search_mathlib` calls hunting for Rademacher / Gaussian / `iIndepFun` / `gaussianReal` / `taylor_mean_remainder_lagrange` machinery.
- Turn 12: write a single file with the theorem statement + extensive header docstring listing what's missing + top-level `sorry`. No intermediate `have ... := sorry` decomposition.
- Turns 13-14: minor tidy-up, exit.

**The bottleneck is workflow, not search.** The agent decided early that the proof needs Lindeberg machinery not in Mathlib, then went straight to honest-sorry on the top-level theorem. It never wrote intermediate sub-goals where `propose_lemmas` could fire. The tool's value is conditional on the agent being in a "I have a sorry on a leaf-level intermediate step that should be one Mathlib call away" state. Opus on weak-comparison skipped that state entirely.

## Cumulative tally + gate decision

| | Stage 2 (×2 parallel) | Stage 3 | Stage 3b | Total |
|---|---|---|---|---|
| `propose_lemmas` calls | 3 + 0 | 6 | 0 | **9** |
| Suggestions returned | 0 | 1 | 0 | **1** |
| Suggestions incorporated | 0 | 0 | 0 | **0** |
| Problems closed | 0 / 1 | 0 / 1 | 0 / 1 | **0 / 3** |
| Cost (reported) | $4.93 + $3.47 | $4.83 | $3.45 | **$16.68** |

**Gate (a) Stage 3 problem closed where baseline didn't:** ✗ — GleasonKahane failed identically to baseline.
**Gate (b) ≥3 calls AND ≥1 suggestion accepted:** ✗ — calls met (9 ≥ 3), but no suggestion was incorporated into a successful proof.

**Gate FAIL on both criteria. Reverted.**

## What we learned (the real finding)

`propose_lemmas` adoption is **conditional on the agent's decomposition strategy**, not on the prompt's tool description. Specifically:

- **Gemini decomposes more** (Stage 3: wrote 4 scratch sub-files, called `propose_lemmas` on each). Adoption real but suggestions returned mostly nothing — the sub-goals Gemini chose were too abstract for `exact?` to close.
- **Opus decomposes less** (Stage 2: 3 calls in one of two parallel runs; Stage 3b: zero). Opus's instinct on hard problems is to either close-or-give-up on the top-level theorem rather than work bottom-up through a `have`-skeleton. This is *good* for honesty (no-cheat record) and *bad* for tools that fire on intermediate sorries.

**The diagnosis from the previous session was correct in direction but optimistic in magnitude.** Goal-state grounding *is* the highest-leverage missing capability, but unlocking it requires fixing two things at once:
1. The retrieval mechanism (this experiment, ✓ implemented).
2. **The decomposition workflow** — the agent must reliably reach a state where retrieval has a chance to fire.

Without (2), (1) alone has nothing to act on.

## Loogle precedent comparison

| | Loogle (retired 2026-04-21) | `propose_lemmas` (this experiment) |
|---|---|---|
| Probes | 3 problems | 3 stages × 1 problem each |
| Adoption rate | ~6-10% of tool calls | ~12% of tool calls (varies wildly across runs) |
| Suggestions returned | non-zero, with syntax-error churn | 1 of 9 calls |
| Suggestions incorporated | 0 | 0 |
| Problems closed | 0 | 0 |
| Cost | network-dep + prompt bloat | ~$17 across stages |
| Decision | retired | retired |

`propose_lemmas` is **slightly better than loogle** on adoption cleanliness (no syntax-error churn — Lean's elaborator is the validator) and on the correctness of the goal grounding (real elaborated goal type vs string-shaped query). But the headline metric — "did it close a problem that didn't close before, or did its suggestions actually get used" — is identical to loogle's: **no**.

## Recommendations

**Immediate:**
1. **Reverted** — `lea/tools.py` and `lea/prompt.py` back to baseline. Logs preserved at `lea-prover/eval/proposetool_logs/` (untracked).
2. **Update CLAUDE.md** "Design decisions — DO NOT RE-LITIGATE" with item 7: `propose_lemmas` tried 2026-05-04, retired. Conditions for revisit: must come bundled with a forced-decomposition workflow change, not stand-alone.

**For the broader question (when to revisit):**
3. **The decomposition-first prompt experiment.** Add a rule like "for any theorem where the proof body is more than a single tactic, ALWAYS write a `have ... := sorry` skeleton before attempting any leaf." Re-add `propose_lemmas`. Re-run Stages 2/3/3b. The hypothesis: forcing decomposition increases the call rate AND the suggestion-acceptance rate.
4. **If (3) shows signal, *then* the goal-state grounding leverage from the previous session's diagnostic is real.** If (3) doesn't, the gap to Aristotle-class is in the workflow / fine-tuning axis, not the search axis, and the entire (1)→(2)→(3)→(4) ranking from that diagnostic needs revision.

**Not recommended:**
5. **Don't re-run with hint engineering.** "Add propose_lemmas to the prompt's critical rules" was already done — the issue isn't visibility.
6. **Don't escalate to LSP/MCP** before (3) is run. If forced decomposition still doesn't unlock value from `propose_lemmas`, the more elaborate LSP-based version will not either.

## Cost

- Stage 1 (local smoke): $0
- Stage 2 (Opus, BanachStone, ×2 parallel): ~$8.40 reported, ~$2.80 actual (Anthropic 3× cost-tracking bug per CLAUDE.md known issues)
- Stage 3 (Gemini, GleasonKahane): ~$4.83 (Gemini, no caching, real)
- Stage 3b (Opus, weak-comparison): ~$3.45 reported, ~$1.15 actual

**Total experiment cost: ~$8-9 actual.** Cheap probe.

## Artifacts

- Tool implementation: `lea/tools.py` + `lea/prompt.py` (reverted; full diff visible in git history if reconstructed from this report).
- FQB run logs: `eval/proposetool_logs/banachstone_opus.log`, `eval/proposetool_logs/gleason_gemini.log`.
- Stage 3b dispatcher logs: `lea-hadamard/runs/stage3b_logs/`.
- Stage 3b tracker: `lea-hadamard/runs/stage3b_weak_comparison_propose_tracker.json`.
- Transcripts (FQB): `eval/results/fqb_best1_20260504-{000601,000614,001317}_transcripts/`.

All artifacts retained; no archival to `/home/chinmay-gcp/lea-archive/` since experiment was small and the diagnostic value is in the report itself.
