# Lea-Ralph — design doc (v1)

A never-die ("Ralph") loop that runs **one target theorem to a sorry-free,
faithful proof, unattended**. No human blueprint (Lea decomposes autonomously);
no Claude Code / human in the loop (the supervisor is deterministic Python; the
only LLM calls are per-leaf `lea` dispatches). Branch: `lea-ralph`.

This is the **deep single-target** counterpart to lea-prover's broad-benchmark
mode (FQB / miniF2F + best-of-N). Pour hours into one hard theorem; resume
across crashes; escalate on plateaus; stop only when the kernel agrees.

## Thesis

> Given `theorem T : <statement> := sorry` and an allowed-axiom line, a
> deterministic loop that repeatedly (a) picks an open `sorry`, (b) asks a
> fresh-context `lea` to either **close** it or **decompose** it into typechecked
> sub-`have`s, (c) keeps only kernel-verified progress, and (d) escalates when
> stuck — will drive `T` to sorry-free, or stall in a way that tells us exactly
> what's missing.

The bet under test: **persisted depth + forced decomposition beats parallel
width** (best-of-N), on the hard nodes where the decomposition itself is the
unknown. Autonomous decompose is the headline risk — agents under-decompose
(documented: the `propose_lemmas` experiment died on exactly this) — so the
loop *forces and gates* decomposition rather than hoping for it.

## Non-goals (v1)

- **No evolutionary / MAP-Elites population.** Single working proof tree. (We
  lose parallel fallback decompositions → backtracking is Q3.)
- **No human-authored blueprint.** Fully autonomous decomposition.
- **No Claude Code / human in the loop.** One launch command, then unattended.
- **Not a benchmark runner.** That stays lea-prover + best-of-N.

## Rides existing rails (minimalism)

| Need | Already in lea-prover |
|---|---|
| Decompose a goal | `lea --sketch` → skeleton with `sorry`s |
| Close a goal | `lea --fill` → fill a `sorry` in place |
| Per-leaf dispatch | `lea.agent.run(task, prompt_variant=..., model=..., max_turns=...)` |
| Read open leaves | `lea.sketch.extract_sorrys(path)` → `[{line, name, type, context}]` |
| Faithfulness gate | `eval/utils/verify.py:verify_proof(target, submission, lake_project)` (SafeVerify: kernel replay + per-decl type/body match + axiom whitelist) |
| Kernel gate | `lake env lean` (compiles, `sorry`s allowed mid-flight) |

New code is the **loop, state, notes, escalation** — a few hundred LoC.

## Core idea: the work file *is* the state

```
run_dir/
  target.lean      # FROZEN at launch: T's exact signature. Never edited. Gate compares against this.
  work.lean        # T + its evolving proof. Open `sorry`s = open leaves.
  worklist.json    # sidecar: per-leaf metadata (attempts, stuck_count, status, last_error)
  notes.md         # distilled failure-memory (NOT transcripts)
  heartbeat.json   # liveness/progress
  checkpoints/     # one git commit per accepted change
  log/             # raw per-iteration transcripts (debug only; never fed back raw)
```

The `sorry`s in `work.lean` are the source of truth for open goals
(`extract_sorrys`). `worklist.json` only annotates them (attempt/stuck counts),
keyed by a stable id = hash of `(enclosing-name, normalized-type)` (Q6).

## The loop (one iteration = one leaf, fresh context)

```python
init:
    target.lean = freeze(T)                  # exact signature, allowed-axiom line recorded
    work.lean   = T_with_single_top_sorry

while not done(work.lean) and within_budget():
    leaves = extract_sorrys(work.lean)
    leaf   = pick(leaves, worklist)          # easiest-first (Q2)
    mode   = decide_mode(leaf, worklist)     # close | decompose | forced-decompose

    patch  = lea.agent.run(                   # FRESH context + distilled notes
                task=leaf_prompt(leaf, notes.md),
                prompt_variant=mode, model=model_for(leaf))
    cand   = apply(work.lean, leaf, patch)

    if kernel_ok(cand):                       # `lake env lean` compiles (sorrys ok)
        if mode == "close"     and faithful_leaf(cand, leaf):  commit(cand)
        elif mode == "decompose" and grew_leaves(cand):        commit(cand)
        else:                                  reject(leaf, "no-progress/cheat")
    else:
        record_failure(leaf, error); bump_stuck(leaf)

    if stuck(leaf) >= K: escalate(leaf)       # ladder below

done_gate(work.lean, target.lean); report()
```

`commit` = a git commit of `work.lean` + `worklist.json` (the checkpoint).
Resume = reopen the run dir and continue. API/build errors → exponential
backoff (lifted from your `ralph_loop.py`).

## The autonomous decompose/close contract (the lever)

The agent may pick its mode, but **acceptance is gated by mode** — this is what
forces real decomposition instead of a top-level `sorry` or a cheat:

- **`decompose`** (`--sketch`): accept iff (a) skeleton compiles with `sorry`s,
  (b) leaf count strictly increased, (c) no new leaf is verbatim the parent goal
  (anti-no-op). Sub-`have`s become new leaves via `extract_sorrys`.
- **`close`** (`--fill`): accept iff the targeted `sorry` is gone, file compiles,
  **and** SafeVerify passes on the affected declaration (no shadow/tautology/⊤).
- **`forced-decompose`**: after K failed closes, the next iteration on that leaf
  *must* `--sketch`; a `close` is rejected unseen.

## Two verification gates

1. **Kernel** (every iteration, cheap): `lake env lean` compiles. `sorry`s
   permitted while the tree is still growing.
2. **Faithfulness** (per leaf-close + at `done`): `verify_proof(target.lean,
   work.lean, workspace)`. Catches the full cheat catalogue. Without this,
   "run until formalized" degrades to "run until the statement is gamed."

### `done()` — all of:

- `work.lean` compiles clean;
- `count_sorrys(work.lean) == 0`;
- `#print axioms T ⊆` the frozen allowed-axiom line;
- SafeVerify passes `work.lean` vs `target.lean`.

Only then halt + write the report.

## Escalation ladder (per-leaf `stuck_count`)

1. **1–2** — retry, fresh context + notes.
2. **3** — **force-decompose** (no `close` accepted this turn).
3. **4** — switch model / bump reasoning effort (Opus ↔ Fable-5 / higher).
4. **5** — **axiomatize-with-label** (loud, recorded) *or* halt-for-review, so
   one hard leaf doesn't block the rest of the tree. This is your RegLip / ORP
   "defensible fallback," made autonomous — gated by an importance threshold
   (Q5) so it can never silently gut the keystone and declare victory.

Global: **all open leaves stuck past K → halt and report** (don't burn budget).

## Failure-memory (`notes.md`) — highest-leverage, riskiest

Raw transcript feedback *hurt* at the bon5 level (`--feedback` was removed). So
notes are **distilled, structured, append-only facts**, capped in size, injected
into every leaf prompt:

```
- DEAD: `Finset.sum_fiberwise'` does not exist (iter 7)
- TIMEOUT: `nlinarith` on the R² goal — clear denominators first (iter 12)
- ROUTE: decomposed indep_fillers via fiber-count; stage2 is the hard counting kernel
- CHEAT-REJECTED: `:= True` shadow on stage2 (iter 19)
```

Written by the agent into a constrained "what I learned" output field per
iteration (preferred — no extra LLM call), or a cheap summarizer pass. Format
and cap are make-or-break → prototype before building the full loop.

## Self-contained launch (no orchestrator)

```bash
bash scripts/ralph.sh path/to/target.lean TheoremName \
     [--allowed-axioms propext,Classical.choice,Quot.sound] \
     [--hours 24] [--model claude-opus-4-7] [--max-budget 200]
```

→ `nohup` supervisor, `heartbeat.json`, `log/`. Runs to `done`, budget, or
all-stuck. (Dashboard/tunnel like your xcelsa stack is a later add, not v1.)

## Module layout

```
lea/ralph/
  loop.py       # never-die supervisor: sessions, resume, backoff, done-gate
  state.py      # run-dir layout, worklist.json, atomic json, git checkpoint (lift ralph/state.py)
  attempt.py    # one leaf dispatch: mode decision + lea.agent.run + apply patch
  verify.py     # kernel gate + faithfulness gate (wraps eval/utils/verify.py) + #print axioms check
  notes.py      # distilled failure-memory read/write
  escalate.py   # stuck ladder + axiomatize-with-label
scripts/ralph.sh
RALPH.md        # this doc
```

## Open questions (resolve before / during coding)

1. **Cold-start decomposition.** The first split of a fresh target (one top
   `sorry` → useful sub-`have`s) is the single hardest step *and* has no notes
   yet. May need a dedicated "cold-start sketch" prompt. **This is where
   fully-autonomous mode lives or dies — watch it first.**
2. **Leaf selection, no fitness gradient.** Easiest-first (builds notes early)
   vs structural/hardest-first (unblocks the tree). Default: easiest-first.
3. **Bad-decomposition backtracking.** A sub-`have` that's false or harder than
   its parent. Detect via subgoal `stuck_count` → revert the parent's
   decomposition, re-sketch differently. Ping-pong risk; needs a revert budget.
4. **Notes format / owner / cap.** The make-or-break component. Prototype the
   format on real failures before wiring the loop.
5. **Autonomous-axiomatize policy.** Must never axiomatize the *keystone* and
   declare `done` against a gutted axiom line (RegLip honesty lesson). Needs an
   importance/budget threshold + a loud report entry.
6. **Stable leaf identity** across edits (have-names churn). Hash of
   `(enclosing-name, normalized-type)`?
7. **Frozen-statement fidelity.** `target.lean` must capture the exact signature
   incl. binders/universes; mind SafeVerify's universe-alpha caveat
   (`verify.py:_universe_alpha_equiv`).
8. **Budget ceiling + the 3× cost-report bug.** Hard wall-clock/$ cap; remember
   reported Lea cost overestimates ~3×.

## v1 milestone (what proves/refutes the thesis)

Run autonomous Ralph on **one node with a known hand proof as ground truth** —
`independence_fillers` (lea-frontier) is ideal (we know the fiber-count
decomposition by hand). Outcome is binary-useful:

- **Reaches sorry-free vs the frozen statement** → the bet pays; scale up.
- **Stalls** → *where* and *why* it stalls (cold-start? backtracking? notes?) is
  itself the finding, and tells us the next lever.

Either way, log cost + trajectory and compare against best-of-5 on the same node.
