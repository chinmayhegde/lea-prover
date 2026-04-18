# Usage

## CLI reference

```bash
uv run lea "Prove that for all natural numbers n, n + 0 = n"

# Use a different model
uv run lea -m claude-sonnet-4-20250514 "Prove that 2 + 3 = 5"
uv run lea -m gpt-4o "Prove that every prime greater than 2 is odd"

# Explicit provider (auto-detected from model name by default)
uv run lea -p anthropic -m claude-opus-4-20250514 "..."

# Session management
uv run lea --sessions                 # list recent sessions
uv run lea --resume                   # resume most recent session
uv run lea --resume 20260418-031200   # resume a specific session

# Safety valve
uv run lea --max-turns 20 "..."       # limit turns (default: unlimited)
```

## Supported providers

| Provider | Models | Env var |
|----------|--------|---------|
| Gemini | `gemini-3.1-pro-preview`, `gemini-2.5-pro`, `gemini-2.5-flash`, ... | `GOOGLE_API_KEY` |
| Anthropic | `claude-opus-4-*`, `claude-sonnet-4-*`, ... | `ANTHROPIC_API_KEY` |
| OpenAI | `gpt-4o`, `o3`, `o4-mini`, ... | `OPENAI_API_KEY` |

Provider is auto-detected from the model name, or set explicitly with `-p`.

## Session persistence

Every run is saved to `~/.lea/sessions/`. Use `--resume` to continue a failed proof attempt, optionally adding a follow-up instruction:

```bash
uv run lea --resume "Try a different approach using induction on the structure"
```

## Customization

Drop a `lea.md` file in your working directory or the `workspace/` root. Its contents are appended to the system prompt. Use it for project-specific tactics, import conventions, or proof strategies.
