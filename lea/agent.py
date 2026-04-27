"""Lea agent — the core loop. Model calls tools until done."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .prompt import load_system_prompt
from .providers import stream, detect_provider, TextDelta, ToolCall, Done, _ToolMeta, Usage
from .tools import TOOLS_SCHEMA, TOOL_HANDLERS

SESSIONS_DIR = Path.home() / ".lea" / "sessions"

DEFAULT_MODEL = "gemini-3.1-pro-preview"

# Per-million-token pricing (input, output). Best-effort estimates.
MODEL_PRICING = {
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-3-pro-preview": (1.25, 10.0),
    "gemini-3.1-pro-preview": (1.25, 10.0),
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-opus-4-20250514": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-7": (15.0, 75.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "gpt-4o": (2.50, 10.0),
    "gpt-5.4-pro-2026-03-05": (2.5, 15.0),
    "o3": (2.0, 8.0),
    "o4-mini": (1.10, 4.40),
}
DEFAULT_PRICING = (2.0, 10.0)


def _save_session(session_id: str, model: str, messages: list, usage: Usage):
    """Persist conversation to disk."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = SESSIONS_DIR / f"{session_id}.json"
    # Strip raw_part (non-serializable provider objects) from messages
    clean_messages = []
    for msg in messages:
        if msg["role"] == "assistant" and isinstance(msg["content"], list):
            clean_content = [
                {k: v for k, v in item.items() if k != "raw_part"}
                for item in msg["content"]
            ]
            clean_messages.append({"role": msg["role"], "content": clean_content})
        else:
            clean_messages.append(msg)
    data = {
        "id": session_id,
        "model": model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "usage": {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
        "messages": clean_messages,
    }
    path.write_text(json.dumps(data, indent=2))


def _load_session(session_id: str | None) -> dict:
    """Load a session by ID, or the most recent one if ID is None."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    if session_id:
        path = SESSIONS_DIR / f"{session_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")
        return json.loads(path.read_text())
    # Find most recent
    sessions = sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not sessions:
        raise FileNotFoundError("No sessions found.")
    return json.loads(sessions[0].read_text())


def list_sessions() -> list[dict]:
    """Return a list of session summaries."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    sessions = sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    summaries = []
    for path in sessions[:20]:
        data = json.loads(path.read_text())
        # Extract the original task from the first user message
        task = data["messages"][0]["content"] if data["messages"] else ""
        if isinstance(task, str) and len(task) > 80:
            task = task[:80] + "..."
        summaries.append({
            "id": data["id"],
            "timestamp": data.get("timestamp", ""),
            "model": data.get("model", ""),
            "task": task,
            "turns": len([m for m in data["messages"] if m["role"] == "assistant"]),
        })
    return summaries


def run(
    task: str,
    model: str = DEFAULT_MODEL,
    max_turns: int | None = None,
    provider: str | None = None,
    resume: str | bool = False,
    return_transcript: bool = False,
    prompt_variant: str = "default",
) -> str | tuple[str, dict]:
    """Run the agent on a formalization task.

    Returns the final assistant message, or (message, transcript_dict) if
    return_transcript is True.
    """
    system = load_system_prompt(prompt_variant)

    if resume:
        session_id_to_load = resume if isinstance(resume, str) else None
        session = _load_session(session_id_to_load)
        messages = session["messages"]
        model = session.get("model", model)
        session_id = session["id"]
        total_usage = Usage(
            session.get("usage", {}).get("input_tokens", 0),
            session.get("usage", {}).get("output_tokens", 0),
        )
        # Append the new task as a follow-up message
        if task:
            messages.append({"role": "user", "content": task})
        print(f"Resuming session {session_id} ({len(messages)} messages)", flush=True)
    else:
        session_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        messages = [{"role": "user", "content": task}]
        total_usage = Usage()

    provider_name = provider or detect_provider(model)

    def _result(text: str, turns: int):
        if return_transcript:
            # Build a clean transcript (no raw_part)
            clean = []
            for msg in messages:
                if msg["role"] == "assistant" and isinstance(msg["content"], list):
                    clean.append({"role": "assistant", "content": [
                        {k: v for k, v in item.items() if k != "raw_part"}
                        for item in msg["content"]
                    ]})
                else:
                    clean.append(msg)
            transcript = {
                "session_id": session_id,
                "model": model,
                "turns": turns,
                "usage": {"input_tokens": total_usage.input_tokens, "output_tokens": total_usage.output_tokens},
                "messages": clean,
            }
            return text, transcript
        return text

    turn = 0
    while True:
        turn += 1
        if max_turns and turn > max_turns:
            _save_session(session_id, model, messages, total_usage)
            _print_usage(model, turn - 1, total_usage)
            return _result("Error: max turns reached without completing the proof.", turn - 1)

        print(f"\n--- turn {turn} ---", flush=True)

        # Collect events from the stream
        assistant_parts = []  # list of {"type": "text"/"tool_call", ...}
        current_text = ""
        tool_calls = []  # list of (name, args, id_or_none)

        for event in stream(model, system, messages, TOOLS_SCHEMA, provider_name):
            if isinstance(event, TextDelta):
                sys.stdout.write(event.text)
                sys.stdout.flush()
                current_text += event.text
            elif isinstance(event, ToolCall):
                if current_text:
                    assistant_parts.append({"type": "text", "text": current_text})
                    current_text = ""
                print(f"\n  -> {event.name}({event.args})", flush=True)
                tool_calls.append({"name": event.name, "args": event.args, "id": None, "raw_part": event.raw_part})
            elif isinstance(event, _ToolMeta):
                # Attach the provider-specific ID to the last tool call
                if tool_calls:
                    tool_calls[-1]["id"] = event.tool_use_id
            elif isinstance(event, Done):
                total_usage.input_tokens += event.usage.input_tokens
                total_usage.output_tokens += event.usage.output_tokens

        if current_text:
            assistant_parts.append({"type": "text", "text": current_text})

        # Build assistant content with tool calls
        for tc in tool_calls:
            assistant_parts.append({
                "type": "tool_call",
                "name": tc["name"],
                "args": tc["args"],
                "id": tc["id"],
                "raw_part": tc.get("raw_part"),
            })

        messages.append({"role": "assistant", "content": assistant_parts})

        # If no tool calls, we're done
        if not tool_calls:
            print()
            _save_session(session_id, model, messages, total_usage)
            _print_usage(model, turn, total_usage)
            text = "".join(p["text"] for p in assistant_parts if p["type"] == "text")
            return _result(text or "(no response)", turn)

        # Execute tool calls and build results
        tool_results = []
        for tc in tool_calls:
            handler = TOOL_HANDLERS.get(tc["name"])
            if handler:
                try:
                    result = handler(tc["args"])
                except Exception as e:
                    result = f"Error: tool '{tc['name']}' raised {type(e).__name__}: {e}"
            else:
                result = f"Error: unknown tool '{tc['name']}'"

            preview = result[:200] + "..." if len(result) > 200 else result
            print(f"  <- {preview}", flush=True)

            tool_result = {"type": "tool_result", "tool_name": tc["name"], "content": result}
            # Attach provider-specific IDs for message reconstruction
            if tc["id"]:
                tool_result["tool_use_id"] = tc["id"]
                tool_result["tool_call_id"] = tc["id"]
            tool_results.append(tool_result)

        messages.append({"role": "user", "content": tool_results})
        _save_session(session_id, model, messages, total_usage)


def _print_usage(model: str, turns: int, usage: Usage):
    """Print a summary line with token counts and estimated cost."""
    price_in, price_out = MODEL_PRICING.get(model, DEFAULT_PRICING)
    cost = (usage.input_tokens * price_in + usage.output_tokens * price_out) / 1_000_000
    total = usage.input_tokens + usage.output_tokens
    print(f"\n--- {turns} turns, {total:,} tokens (in: {usage.input_tokens:,}, out: {usage.output_tokens:,}), ~${cost:.4f} ---", flush=True)
