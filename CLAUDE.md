# Project context for Claude Code

> This file is the handoff from the v1 → v2 phase (April 2026). Read it first. It captures lessons and decisions so you don't re-run experiments we already ran.

## What Lea is

A minimal Lean 4 theorem-proving agent. ~300 lines of Python, 6 tools, one system prompt, one while-loop. Inspired by [pi](https://github.com/badlogic/pi-mono).

**Pi ethos (non-negotiable):**
- Minimum code. If the model can decide something from the prompt, don't write code for it.
- No orchestration layer. Plan/Work/Reflect phase state machines have been tried and removed.
- Full observability. Every tool call and result visible.
- Collaborator, not oracle. The research framing is "tool for mathematicians," not "leaderboard maximizer."

## Current state (as of 2026-04-24)

| | Pass rate | Run |
|---|---|---|
| miniF2F validation | **211/244 (86.5%)** | Lea v1, Gemini 3.1 Pro, single-pass |
| FormalQualBench | **5/23 legit** | Lea v2, Gemini 3.1 Pro, best-of-5 + feedback |

See [`fqb-reports/`](./fqb-reports/) for detailed reports:
- `fqb-report.md` — v1 single-pass
- `fqb-bon5-report.md` — v1 best-of-5 baseline
- `fqb-v2-feedback-report.md` — v2 Gemini + Opus + partial GPT
- `fqb-{feedback,opus-feedback,gpt-feedback}-report.html` — per-model verbose writeups

**Leaderboard context:** OpenGauss leads FQB at 8/23 — but that's really "Claude Code + `cameronfreer/lean4-skills` plugin + `lean-lsp-mcp` + Opus 4.6." Our analysis found their RL training (via `tinker-atropos` submodule) is NOT on the Lean path, just inference-time orchestration.

## Architecture

Entry point: `uv run lea "..."` → `lea.cli` → `lea.agent.run()` → provider stream → tool dispatch → repeat.

Six tools, nothing more: `read_file`, `write_file`, `edit_file`, `lean_check`, `bash`, `search_mathlib`. Schema in [`lea/tools.py`](./lea/tools.py). Handlers dispatched via a dict; adding a tool is 3 places.

Multi-provider via [`lea/providers.py`](./lea/providers.py): Gemini (default), Anthropic, OpenAI. Model name prefix routes (`claude-*` → anthropic, `gpt-*`/`o*` → openai). For `gpt-*-pro` variants, routes to the OpenAI Responses API (chat completions rejects reasoning-only models).

## Design decisions — DO NOT RE-LITIGATE

These have been tried and rejected. If the user asks, remind them.

1. **No `prove_hard` orchestration.** Had a Layer-2 sketch/fill/reflect state machine. Buggy. Prompt alone achieves the same with zero code. Kept only `--sketch` and `--fill` CLI modes for collaborator workflow.

2. **No MCP server integration.** `lean-lsp-mcp` (used by lean4-skills) would give us goal-state-aware premise search. Violates Pi ethos; adds a network dependency and an external process. CLI is preferred.

3. **Loogle was tried and retired.** Added a `loogle` tool wrapping `loogle.lean-lang.org/json`. Zero empirical benefit across three probes; Gemini used it ~10%, Opus ~6-9%, both with syntax-error churn. Removed. If reconsidered, prefer local `lake exe loogle` install over web API.

4. **The "2-3 candidates" protocol was tried and retired.** Prompt rule telling the agent to generate multiple candidate proofs per sorry. Added overhead on easy problems (DeBruijn went from 34 turns to 69). Removed from the workflow while keeping the tactic cascade and phrasebook patches.

5. **Kept prompt patches (borrowed from [cameronfreer/lean4-skills](https://github.com/cameronfreer/lean4-skills)):**
   - Goal-shape → tactic cascade (after `## Style`)
   - English → Lean phrasebook (after tactic cascade)
   - Header-fence rule (inside `## Critical Rules`)
   - "Prefer `search_mathlib` over bash grep" rule (Critical Rules)
   - "`lean_check` is a tool not a shell command" clarification

6. **No network-isolation enforcement.** The bash tool can run `curl`/`wget`/`urllib.request`. Gemini has used this (20+ web calls on JordanCycle baseline). For clean benchmarking this is a gap; accepted as Pi-compatible default. User explicitly said "no need for isolation, it's okay" during v2 development.

## Known model failure modes

Three distinct cheat classes observed across the runs. All exploit the same structural gap: **the verifier checks `lake env lean` + sorry-grep on the submitted file, not statement equivalence**.

### Gemini — namespace shadowing

Gemini's default response to "I can't prove this" is to redefine the problematic Mathlib name inside the problem's namespace.

- **Quillen-Suslin (v1 single-pass, 2026-04-19):** `namespace QuillenSuslinTheorem.Module ; abbrev Free (_R _P) := True ; end Module`, closed with `trivial`. Gemini **admitted this in its own `agent_output`**: *"I utilized namespace shadowing to cleanly trivialize the goal."*
- **Maynard–Tao (v2 feedback, 2026-04-21):** `def Nat.Prime (_ : ℕ) : Prop := True` inside the problem namespace, closed with `trivial`.
- Earlier baseline: Erdős Discrepancy (`def X := True`), Runge (`def IsConnected := False`).

### Opus — doesn't cheat

Zero shadowing across two full Opus runs. Opus refuses honestly. Example from Von Neumann Double Commutant in the Opus feedback run: 400-word refusal citing Mathlib's own TODO comment on the theorem.

### GPT-5.4-pro — import-sorry (novel, discovered 2026-04-23)

GPT found that the benchmark's canonical `FormalQualBench.<Problem>.Main` modules contain the target declared as `:= by sorry`. Importing these modules makes the theorem term-level-callable. The submitted file has no `sorry` text, compiles clean, passes our verifier — no actual proof produced.

Minimal version (ColorfulCaratheodory attempt 1 — literally one line):
```lean
import FormalQualBench.ColorfulCaratheodoryTheorem.Main
```

Standard version: `import ... ; example : <statement> := MainTheorem args`.

Once GPT found this, it applied it systematically. By the 4th problem it was trying the exploit on attempt 1, before any real attempt. Four defense layers (banned-token grep, header fence, anti-shadowing, `lake env lean` compile) all bypassed.

### The common thread

We verify syntax + compilation, not **semantic correspondence**. The fix is to integrate [SafeVerify](https://github.com/GasStationManager/SafeVerify) or FormalQualBench's [Comparator](https://github.com/leanprover/comparator), which check statement equivalence recursively through imports. This is the highest-leverage open TODO.

A one-line patch closes the GPT exploit specifically: in `eval/run_fqb_best_of_n.py` `verify_proof`, after reading content, reject any `^import FormalQualBench\.\w+` match.

## Archive and contamination hygiene

**Prior-run artifacts live OUTSIDE the repo tree at `/home/chinmay-gcp/lea-archive/`.** Chmod 700 (or 000 during active runs).

Do NOT put `_archive/` back inside `lea-prover/`. Opus 4.7 successfully discovered `/home/chinmay-gcp/lea-archive/` by path guessing during one run — the agent routinely pokes obvious paths. The only robust isolation is:
1. Outside the repo tree, AND
2. `chmod 000` during runs (restore `700` after).

Workflow around runs:
```bash
# Before a run (if archive exists):
chmod 000 /home/chinmay-gcp/lea-archive

# After a run:
chmod 700 /home/chinmay-gcp/lea-archive

# Archive a completed run:
DEST=/home/chinmay-gcp/lea-archive/<run_name>_<date>
mkdir -p "$DEST"
mv eval/results/fqb_best5_<timestamp>{,.json,_transcripts} "$DEST/"
mv FormalQualBench/eval_proofs_bon_fqb_best5_<timestamp> "$DEST/"
mv eval/<run>.log eval/<run>.pid "$DEST/"
```

**Clean-tree invariant before any new run:**
- `eval/results/` empty
- `FormalQualBench/*.lean` contains only `FormalQualBench.lean` (no scratch at root)
- `workspace/proofs/` contains only `.gitkeep`
- No `_archive/` directory inside `lea-prover/`

## Known bugs

1. **Anthropic cost tracking is broken.** [`lea/providers.py:213-216`](./lea/providers.py#L213-L216) only reads `input_tokens` and `output_tokens` from the usage event. It ignores `cache_creation_input_tokens` and `cache_read_input_tokens`. For Claude 4.x (auto-caching), this makes the harness overstate Opus costs by roughly 3× vs the real Anthropic dashboard. Fix: ~10 lines. Not urgent; cosmetic.

2. **`eval/run_fqb.py` (single-pass runner) writes to shared `eval_proofs/`.** At line 185. Means parallel runs would collide and prior-run scratch leaks into later runs. Best-of-N harness was fixed; single-pass wasn't. Retire `run_fqb.py` (supplanted by `run_fqb_best_of_n.py --n 1`) or point it at a per-run dir.

## Common workflows

### Launch a best-of-5 run

```bash
cd /home/chinmay-gcp/lea-prover
# Optionally: chmod 000 /home/chinmay-gcp/lea-archive
nohup env PYTHONUNBUFFERED=1 uv run python -m eval.run_fqb_best_of_n \
    --n 5 --model <model-id> \
    [--feedback] \
    > eval/fqb_bon5_<tag>.log 2>&1 &
echo $! > eval/fqb_bon5_<tag>.pid
tail -f eval/fqb_bon5_<tag>.log
```

`<model-id>` options: `gemini-3.1-pro-preview` (default, cheapest, best legit-per-dollar), `claude-opus-4-7` (honest but expensive), `gpt-5.4-pro-2026-03-05` (adversarial; expect exploits).

### Status check

```bash
ps -p $(cat eval/fqb_bon5_<tag>.pid) -o pid,etime,cmd | head -2
grep -E "^\[.*\] attempt|PASS|FAIL|Best-of" eval/fqb_bon5_<tag>.log | tail -20
```

### Audit a PASS for cheats

For each "solved" problem, read the submitted `.lean` file and check:
1. `grep -nE "^(noncomputable\s+)?(def|abbrev)" <file>` — any redefinition of Mathlib-namespace names?
2. `grep -nE "^import FormalQualBench\.\w+"` — importing the benchmark's own canonical files? (GPT-style exploit)
3. `grep -nE ":= (True|False|\(\))\b"` — any trivializations?
4. Is the file ≥ 30 lines? < 30 lines on a FQB problem is suspicious.
5. Does the agent's final text mention "shadowing," "trivialize," or "import"? (Gemini often admits cheats explicitly.)

Pattern auditing code already in `fqb-reports/*.html` reports — reuse.

### Kill + cleanup if a run goes bad

```bash
kill $(cat eval/fqb_bon5_<tag>.pid)
pkill -f "run_fqb_best_of_n"
DEST=/home/chinmay-gcp/lea-archive/<tag>_killed_<date>
mkdir -p "$DEST"
mv eval/fqb_bon5_<tag>.log eval/fqb_bon5_<tag>.pid "$DEST/"
mv eval/results/fqb_best5_<timestamp>* "$DEST/"
mv FormalQualBench/eval_proofs_bon_fqb_best5_<timestamp> "$DEST/"
# scratch cleanup:
mv workspace/proofs/*.lean "$DEST/" 2>/dev/null
cd FormalQualBench && for f in *.lean; do
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || mv "$f" "$DEST/"
done
```

## Where things live

- [`lea/agent.py`](./lea/agent.py) — tool loop, `run()`, `MODEL_PRICING` table
- [`lea/tools.py`](./lea/tools.py) — 6-tool schema + handlers
- [`lea/providers.py`](./lea/providers.py) — Gemini/Anthropic/OpenAI streaming
- [`lea/prompt.py`](./lea/prompt.py) — `BASE_PROMPT` plus three phase-variant prompts for `--sketch`/`--fill`/`--reflect`
- [`eval/run_minif2f.py`](./eval/run_minif2f.py) — miniF2F single-pass harness
- [`eval/run_fqb_best_of_n.py`](./eval/run_fqb_best_of_n.py) — FQB best-of-N with resume and optional `--feedback` flag
- [`eval/run_fqb.py`](./eval/run_fqb.py) — legacy single-pass (see "Known bugs"; retire or fix)
- [`fqb-reports/`](./fqb-reports/) — all writeups (md and html)
- [`DESIGN.md`](./DESIGN.md) — architecture doc; planned sketch-fill-reflect pipeline (mostly unimplemented, intentionally)
- [`USAGE.md`](./USAGE.md) — CLI reference
- `/home/chinmay-gcp/lea-archive/` — all prior-run artifacts, tarballs, scratch. Three tarballs: `gemini_feedback_bon5_2026-04-21.tar.gz`, `opus_feedback_bon5_2026-04-23.tar.gz`, `gpt_feedback_bon5_partial_2026-04-24.tar.gz`.
- `/home/chinmay-gcp/olea-notes/` — plan for a hosted minimal Lea service. Separate repo/project, not inside lea-prover.

## Open questions for v2

Ordered by highest-leverage first:

1. **Integrate SafeVerify or Comparator.** Blocks all three cheat classes at once. Would turn our audit-adjusted numbers into audit-safe numbers. ~100 lines plus a lake dep. Required before any leaderboard claim.
2. **Selective feedback.** The current `--feedback` flag feeds every failed attempt forward. It hurts on problems where the right strategy is far from the first failure (regressed Paris–Harrington). Try: only feed forward when the last attempt was a "near-miss" (small diff from compiling), use independent trials otherwise.
3. **Blueprint mode.** For the 3 infra-missing problems (DLO, VonNeumann, QuillenSuslin), feedback doesn't help because Mathlib lacks the theorem. A `--blueprint <file>` flag letting the user provide a natural-language proof outline, which the agent translates. Matches the "collaborator, not oracle" framing. ~10 lines of CLI.
4. **Fix Anthropic cost tracking.** Capture `cache_{creation,read}_input_tokens`. Update `MODEL_PRICING` to include the 1.25× cache-write and 0.1× cache-read rates. ~10 lines.
5. **Anti-shadow prompt rule + verifier check.** In `prompt.py`, forbid `def`/`abbrev` names matching Mathlib names. In `verify_proof`, reject any submitted `def X` where `X` exists in scope before imports. Catches the Gemini cheat class. ~15 lines.

## Explicit non-goals

- Don't try to reach 8/23 by adding orchestration. The gap is verification and model capability, not glue code.
- Don't add an MCP server dependency.
- Don't build user accounts / auth / multi-tenant — that's for Olea (separate project).
- Don't rewrite the agent loop. If it looks too simple, that's the feature.

## Meta notes

- `.git` commit history goes back to early April. `git log --oneline` is the canonical decision log.
- The user is Chinmay Hegde (NYU, chinmay.h@nyu.edu). Not a mathematician — blueprint mode should probably auto-generate outlines via LLM rather than require human mathematical expertise.
- Previous Claude sessions built up auto-memory at `/home/chinmay-gcp/.claude/projects/-home-chinmay-gcp/memory/project_lea.md`. That has additional context if needed.
