# Lea — Design Document

A minimal Lean 4 theorem proving agent, inspired by [Pi](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent).

## Philosophy

Lea follows Pi's ethos of radical minimalism: if we don't need it, we don't build it. The agent should be transparent, observable, and simple enough to understand in a single sitting.

- **Minimal tools**: the smallest set of tools that lets an LLM write and verify Lean proofs.
- **Full observability**: every tool call, result, and model response is visible. No hidden orchestration.
- **Trust over guardrails**: no permission prompts. The agent has full access to files and shell.
- **Simple prompts**: frontier models already know how to be coding agents. Keep the system prompt short.
- **Collaborator, not oracle**: Lea is a tool for mathematicians, not a replacement. Legibility, insight, and the ability to intervene matter as much as raw solve rate.

## Architecture

```
User task (CLI) → agent loop → tool calls → Lean compilation → repeat until proof compiles
```

### Tools (6)

| Tool | Purpose |
|------|---------|
| `read_file` | Read file contents |
| `write_file` | Create or overwrite a file |
| `edit_file` | Replace an exact substring in a file |
| `lean_check` | Compile a `.lean` file via `lake env lean`, return diagnostics |
| `search_mathlib` | Grep Mathlib source for lemma names / type patterns |
| `bash` | Run a shell command (for `exact?`, `apply?`, `lake build`, etc.) |

### Implemented features

1. **Streaming output** — all model output streams in real time. Every tool call and result is visible as it happens.
2. **Multi-provider support** — Gemini, Anthropic, OpenAI via a thin provider abstraction in `providers.py`. Auto-detected from model name or set with `-p`.
3. **No default turn limit** — the agent runs until the model stops calling tools. `--max-turns` available as an optional safety valve.
4. **Bash tool** — the agent can run arbitrary shell commands, enabling `exact?`, `apply?`, `grep`, `lake build`, etc.
5. **Project-level prompt customization** — drop a `lea.md` file in the workspace to append project-specific instructions to the system prompt.
6. **Session persistence** — full conversation history saved to `~/.lea/sessions/` after each run. Resume with `--resume`.
7. **Cost and token tracking** — cumulative input/output tokens and estimated cost printed at the end of each run.

### Evaluation

Eval harness at `eval/run_minif2f.py` runs Lea against the [miniF2F](https://github.com/yangky11/miniF2F-lean4) benchmark (488 competition-level problems). Per-problem transcripts with timestamps saved to `eval/results/`. Early results: ~84% on the validation split with Gemini 3.1 Pro.

---

## Limitations of the current design

Lea's single-loop architecture -- write proof, compile, read errors, fix, repeat -- works well on competition math where proofs are short (less than 50 lines). 

But my guess is that this breaks down on harder, graduate-level mathematics:

1. **No proof structure.** The agent tries to write the entire proof in one shot. For a theorem requiring intermediate lemmas (which is most real mathematics), it either produces an unmanageable monolith or gets lost.

2. **Blind retries.** When a proof attempt fails, the agent sees only compiler errors. It has no mechanism to step back and reconsider its strategy; it just edits the same broken proof. This leads to loops where the agent makes the same mistake repeatedly.

3. **No awareness of proof state.** The agent doesn't know what it needs to prove at each `sorry`. It guesses from error messages rather than inspecting the actual goal. Lean has tools for this (`exact?`, `apply?`, `#check`) but the current prompt does not guide the agent to use them.

4. **Single strategy.** Every problem gets the same approach: try simple tactics, if this fails then start searching Mathlib. There is no mechanism to try fundamentally different or involved proof strategies or to reflect upon failed attempts.

## Observed failure modes (from FormalQualBench baseline)

Lea v1 was run on FormalQualBench (23 graduate-level theorems) with no turn limit. The failures clustered into three patterns:

**1. Search spiraling (Banach-Stone: 99 turns, 0 proofs)**
The agent spent 80%+ of turns grepping Mathlib with increasingly desperate queries, hoping to find the theorem pre-built. Only 10 of 99 turns were actual proof attempts. It never committed to a proof structure.

**2. Near-misses (Borsuk-Ulam: 47 turns, Burnside: 60 turns)**
The agent wrote a reasonable proof with a single `sorry` remaining — it built the structure but couldn't close one subgoal. It never stepped back to ask "can I restructure to avoid this hard subgoal?"

**3. No decomposition (Burnside Prime Degree: 60 turns)**
The agent wrote the correct theorem statement but never decomposed the proof into intermediate lemmas. It attempted the whole thing monolithically and failed.

**Context bloat**: Banach-Stone accumulated 2M input tokens across 99 turns. The agent didn't get dumber — it was never effective — but the growing context wasted money re-reading old failed attempts.

## Insights from Armstrong-Kempe (De Giorgi-Nash-Moser formalization)

Armstrong and Kempe formalized 56,000 lines of PDE regularity theory in two weeks using LLMs, with no human hands on the Lean files. Key lessons:

- **Blueprints drive everything.** The humans wrote detailed natural-language proof plans. The LLM translated them to Lean. Without blueprints, the LLM wandered.
- **File decomposition is the architecture.** Their 56K lines are split across ~30 files in a dependency graph. The file structure IS the proof strategy. Each file is a self-contained module (~1,800 lines average).
- **Glue lemmas are the hard part.** The most effort went into "wrapper lemmas" converting between representations — not the main theorems themselves.
- **Supervision, not autonomy.** The workflow was interactive: blueprint → LLM attempt → human review → correction. The LLM needed guidance on strategy, not just error messages.

## Planned features: sketch–fill–reflect

Inspired by [DeltaProver](https://arxiv.org/html/2507.15225) (95.9% miniF2F), [DeepSeek-Prover-V2](https://arxiv.org/html/2504.21801v1), and the Armstrong-Kempe workflow.

### The core idea

Each phase addresses a specific failure mode:

- **Sketch** fixes "no decomposition" — forces the agent to commit to a proof structure early, before spending turns on details. Produces a `.lean` file with `have` statements and `sorry`s that compiles (with sorry warnings).
- **Fill** fixes "search spiraling" — each sorry is an independent, focused sub-problem. The agent uses `exact?`, `apply?` via bash instead of grepping. Fresh context per sorry (no bloat).
- **Reflect** fixes "near-misses" — when sorrys can't be filled, the agent analyzes why and produces a new sketch with a different decomposition. The failing subgoals and error messages feed into the re-sketch.

### The loop

```
┌─────────────────────────────────────────────────┐
│                                                 │
│   1. SKETCH                                     │
│      Write a proof skeleton:                    │
│        have h1 : ... := sorry                   │
│        have h2 : ... := sorry                   │
│        exact combine h1 h2                      │
│      Compile to verify the skeleton type-checks │
│      Save to foo.sketch.N.lean                  │
│                                                 │
│   2. FILL                                       │
│      For each sorry, run a Lea proving loop:    │
│        - try simple tactics (norm_num, simp)    │
│        - use exact?, apply? via bash            │
│        - search Mathlib if needed               │
│      Each sorry is a fresh run() call with      │
│      its own context (no bloat from prior work) │
│                                                 │
│   3. CHECK                                      │
│      If all sorry's filled and proof compiles:  │
│        → DONE                                   │
│      If some sorry's remain:                    │
│        → continue to REFLECT                    │
│                                                 │
│   4. REFLECT                                    │
│      Analyze: which subgoals failed and why.    │
│      Write analysis to foo.reflect.N.md         │
│      Decide: resketch (→ go to 1) or give up.   │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Implementation plan

The upgrade has three layers. Each layer is independently useful and testable.

**Layer 1: Better prompting (prompt.py only)**

No code changes to the agent loop. Just update the system prompt to:
- Tell the agent about the sketch strategy: "For hard theorems, write a skeleton with `have` + `sorry` first, compile it, then fill each sorry."
- Tell it to use `exact?` and `apply?` via bash instead of grepping Mathlib source files.
- Tell it to reflect when stuck: "If you've failed 3+ times on the same sorry, stop and reconsider: is the decomposition wrong?"

This alone should help on FQB problems by steering the agent away from search-spiraling. We test this by re-running the FQB baseline and comparing.

**Layer 2: Orchestrated sketch-fill-reflect (new `prove_hard` function)**

A new function in `agent.py` (~50 lines) that calls `run()` with phase-specific prompts:

1. Call `run(task, prompt=SKETCH_PROMPT)` → agent writes a `.lean` file with sorrys
2. Parse the file to find sorry locations (simple regex on `sorry`)
3. For each sorry, call `run(fill_task, prompt=FILL_PROMPT)` with the sorry's context — the surrounding lemma statement and any available hypotheses
4. Compile the assembled file
5. If sorrys remain, call `run(reflect_task, prompt=REFLECT_PROMPT)` with the list of failed subgoals
6. Loop back to step 1 with the reflection as additional context

Each fill call gets a fresh context; no accumulated history from prior fills or sketches. This directly addresses the context bloat problem.

The sketch prompt should guide the model to produce a natural-language proof plan alongside the Lean skeleton. This serves as a readable blueprint that a mathematician can inspect.

**Layer 3: Multi-file decomposition (for research-level proofs)**

For very hard proofs, the sketch should produce a **file plan** rather than a single-file `have` chain:

```
Sketch for Schauder Fixed Point Theorem:
  File 1: ApproximationLemma.lean — finite-dim approximation of compact maps
  File 2: BrouwerApplication.lean — apply Brouwer to finite-dim approximations
  File 3: SchauderFixedPoint.lean — take limit, main theorem
```

Each file gets its own fill phase. The sketch is a dependency graph of files, not just a linear chain of `have` statements.

This layer is only needed for the hardest FQB problems and is optional. We implement it only if Layer 2 proves insufficient.

### Prompts (drafts)

**SKETCH_PROMPT:**
```
You are writing a proof skeleton for a Lean 4 theorem. Your job is to decompose
the proof into intermediate steps, NOT to fill in details.

Write a .lean file where:
- The main theorem uses `have` statements for intermediate results
- Each `have` body is `sorry`
- The final step combines the intermediate results
- The file MUST compile (sorry warnings are OK, errors are NOT)

Before writing Lean, briefly explain your proof strategy in a comment:
what is the mathematical approach, and why this decomposition?

Do NOT try to fill any sorry. Do NOT search Mathlib for lemmas yet.
Focus only on the proof structure.
```

**FILL_PROMPT:**
```
You are filling in a single sorry in an existing Lean 4 proof.

The sorry you need to fill is:
  have {name} : {type} := sorry

Context (preceding hypotheses and imports) is in the file.

Strategy:
1. First try: exact?, apply?, simp, norm_num, omega, linarith, decide via bash
2. If those fail: read the goal type carefully and search for relevant Mathlib lemmas
3. Do NOT modify anything outside this sorry
4. Do NOT add new sorrys
```

**REFLECT_PROMPT:**
```
A proof attempt failed. Some subgoals could not be proved.

Failed subgoals:
{list of sorry names, their types, and the errors encountered}

Successful subgoals:
{list of filled sorrys}

Analyze:
1. Why did the failed subgoals fail? Were they too hard, ill-typed, or unnecessary?
2. Is there a different decomposition that avoids the hard subgoals?
3. Should we try a completely different proof strategy?

Write your analysis, then write a NEW proof skeleton with `have` + `sorry`.
The new skeleton must compile.
```

### CLI and strategy selection

The CLI stays the same: `lea "prove XYZ"`. The model decides whether to decompose or prove directly. Simple theorems get proved in one shot; hard theorems get sketched, filled, and reflected.

Optional hooks for interactive use:
- `lea --sketch "task"` — produce the sketch and stop for human review.
- `lea --fill path/to/sketch.lean` — fill sorrys in an existing file.

### Observability

Every phase leaves artifacts on disk:

```
workspace/proofs/
  foo.lean                  # final proof (or latest attempt)
  foo.sketch.1.lean         # first sketch (with proof strategy comment)
  foo.sketch.2.lean         # re-sketch after reflection (if any)
  foo.reflect.1.md          # reflection: what failed and why
```

The sketch files are valid (incomplete) Lean — they compile with sorry warnings. The reflect files are natural-language analysis. A mathematician can read the full sequence to understand the agent's reasoning process.

### Evaluation plan

1. **Layer 1 test**: update prompt only, re-run FQB baseline. Compare search-vs-prove turn ratio.
2. **Layer 2 test**: implement `prove_hard`, run on FQB. Compare pass rate, turns, and tokens vs. baseline.
3. **Regression check**: run Layer 2 on miniF2F to verify no regression on easy problems.
4. Target: solve 4+ of 23 FQB problems (vs. current 1/23 baseline with Jordan Derangement).
