# Skill: proving with the Lean LSP tools

You have live Lean language-server tools (from the `lean-lsp-mcp` server). Use
them instead of guessing:

- **Start from the goal.** Call `lean_goal` at the proof position to see exactly
  what must be proved, and re-check it after every tactic.
- **Confirm names before using them.** Check a lemma exists with
  `lean_local_search`; to *discover* lemmas, use `lean_loogle` (by type
  signature) or `lean_leansearch` (natural language). Respect their rate limits —
  search deliberately, not in a loop.
- **Trial tactics without editing the file** via `lean_multi_attempt`; read the
  resulting goal states and keep the one that closes or simplifies the goal.
- **Verify a complete attempt** with `lean_run_code` (include all `import`s). The
  proof is done only when its `diagnostics` array is empty.
- **Work in small, checkable steps.** After each change, look at the diagnostics
  before moving on.
