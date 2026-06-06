"""Lea agent — the core loop. Model calls tools until done.

`run_events()` is the generator core: it yields a typed event stream and never
prints. `run()` is a backward-compatible wrapper that drains those events through
the default stdout renderer and returns the final text (and optional transcript),
so existing callers (CLI, eval) keep working unchanged.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import LeaConfig, load_config
from .prompt import load_system_prompt
from .providers import stream, TextDelta, ToolCall, Done, _ToolMeta, Usage
from . import tools as _tools  # noqa: F401 — importing registers the built-in tools
from .registry import build_toolset, import_tool_modules
from .events import (
    SessionResumed,
    TurnStarted,
    AssistantTextDelta,
    ToolCalled,
    ToolResulted,
    UsageUpdated,
    Finished,
)
from .render import render_to_stdout

SESSIONS_DIR = Path.home() / ".lea" / "sessions"

_UNSET = object()  # sentinel: distinguishes "caller omitted arg" from an explicit None


_NARRATE_TOOL_STEPS_INSTRUCTION = """

When you are about to call one or more tools, first write a concise progress
summary for the user. Keep it to one or two sentences, use Markdown when helpful,
and include mathematical notation in normal LaTeX delimiters when useful. Explain
what you are trying next and why, then call the tool. Do not narrate after every
minor token or repeat boilerplate; summarize the meaningful proof step.
"""


_FORCED_TOOL_NARRATION_INSTRUCTION = """

You are Lea explaining the next proof action to the user. The main model turn
selected a tool call without first writing user-facing narration. Write the
missing narration now.

Rules:
- Write one concise paragraph unless the mathematical plan genuinely benefits
  from a short numbered list.
- Explain the mathematical or Lean proof move being attempted and why it is the
  next useful step.
- Use Markdown and ordinary LaTeX delimiters when helpful.
- Do not mention JSON, API internals, or hidden/private reasoning.
- Do not call tools. Return only the narration text.
"""


def _tool_call_for_prompt(name: str, args: dict) -> dict:
    """Compact a tool call enough to show a narration-only model pass."""
    compact: dict = {}
    for key, value in args.items():
        if isinstance(value, str):
            if key == "content" and len(value) > 1600:
                compact[key] = value[:1600] + "\n... [truncated]"
            elif len(value) > 800:
                compact[key] = value[:800] + "... [truncated]"
            else:
                compact[key] = value
        else:
            compact[key] = value
    return {"name": name, "args": compact}


def _forced_tool_narration(
    *,
    model: str,
    system: str,
    messages: list,
    tool_name: str,
    tool_args: dict,
    config: LeaConfig,
):
    """Ask the model for narration when a tool-only turn would otherwise be silent."""
    narration_messages = messages + [{
        "role": "user",
        "content": (
            "Write the user-facing narration that should appear immediately "
            "before this Lea tool call:\n"
            f"{json.dumps(_tool_call_for_prompt(tool_name, tool_args), ensure_ascii=False, indent=2)}"
        ),
    }]
    text = ""
    usage = Usage()
    cost = 0.0
    try:
        for event in stream(
            model,
            system + _FORCED_TOOL_NARRATION_INSTRUCTION,
            narration_messages,
            [],
            config.model_kwargs,
            streaming=config.stream,
        ):
            if isinstance(event, TextDelta):
                text += event.text
                yield event
            elif isinstance(event, Done):
                usage.input_tokens += event.usage.input_tokens
                usage.output_tokens += event.usage.output_tokens
                cost += event.cost
    except Exception:
        fallback = _fallback_tool_narration(tool_name, tool_args)
        text += fallback
        yield TextDelta(fallback)
    return text.strip(), usage, cost


def _fallback_tool_narration(tool_name: str, args: dict) -> str:
    path = args.get("path")
    if tool_name == "write_file":
        if isinstance(path, str) and path:
            return f"I will write the next Lean proof attempt in `{path}` and then check whether it compiles."
        return "I will write the next Lean proof attempt and then check whether it compiles."
    if tool_name == "edit_file":
        if isinstance(path, str) and path:
            return f"I will revise `{path}` to address the previous Lean feedback, then re-run the checker."
        return "I will revise the Lean proof to address the previous checker feedback, then re-run it."
    if tool_name == "lean_check":
        if isinstance(path, str) and path:
            return f"I will run Lean on `{path}` to verify the current proof and inspect any errors."
        return "I will run Lean to verify the current proof and inspect any errors."
    if tool_name == "search_mathlib":
        query = args.get("query")
        if isinstance(query, str) and query:
            return f"I will search Mathlib for lemmas related to `{query}` so the next proof step can use existing results."
        return "I will search Mathlib for a relevant lemma before continuing the proof."
    return f"I will use `{tool_name}` for the next proof step and then use its result to continue."


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


def run_events(config: LeaConfig, task: str, *, resume: str | bool = False):
    """Core loop as a generator: yields typed events, never prints.

    Yields SessionResumed?, then per turn: TurnStarted, AssistantTextDelta*,
    ToolCalled*, UsageUpdated, ToolResulted*, and finally Finished.

    Owns MCP lifecycle: starts configured servers (which register their tools)
    before the inner loop resolves the toolset, and stops them when the event
    stream ends or is closed.
    """
    mcp_manager = None
    if config.mcp_servers:
        from .mcp import MCPManager
        mcp_manager = MCPManager(config.mcp_servers)
        mcp_manager.start()
    try:
        yield from _run_events_inner(config, task, resume=resume)
    finally:
        if mcp_manager is not None:
            mcp_manager.stop()


def _run_events_inner(config: LeaConfig, task: str, *, resume: str | bool = False):
    system = load_system_prompt(config.prompt_variant, config.skills)
    if config.narrate_tool_steps:
        system += _NARRATE_TOOL_STEPS_INSTRUCTION
    model = config.model_name

    # Resolve the active toolset once: import any user tool modules so their
    # tools register, then select per config (None → all registered tools).
    import_tool_modules(config.tool_modules)
    tools_schema, tool_handlers = build_toolset(config.tools)

    if resume:
        session = _load_session(resume if isinstance(resume, str) else None)
        messages = session["messages"]
        model = session.get("model", model)
        session_id = session["id"]
        total_usage = Usage(
            session.get("usage", {}).get("input_tokens", 0),
            session.get("usage", {}).get("output_tokens", 0),
        )
        if task:
            messages.append({"role": "user", "content": task})
        yield SessionResumed(session_id, len(messages))
    else:
        session_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        messages = [{"role": "user", "content": task}]
        total_usage = Usage()

    total_cost = 0.0

    def transcript(turns: int) -> dict:
        clean = []
        for msg in messages:
            if msg["role"] == "assistant" and isinstance(msg["content"], list):
                clean.append({"role": "assistant", "content": [
                    {k: v for k, v in item.items() if k != "raw_part"}
                    for item in msg["content"]
                ]})
            else:
                clean.append(msg)
        return {
            "session_id": session_id,
            "model": model,
            "turns": turns,
            "usage": {"input_tokens": total_usage.input_tokens, "output_tokens": total_usage.output_tokens},
            "messages": clean,
        }

    turn = 0
    while True:
        turn += 1
        if config.max_turns and turn > config.max_turns:
            _save_session(session_id, model, messages, total_usage)
            yield Finished("max_turns", "Error: max turns reached without completing the proof.",
                           turn - 1, session_id, model, total_usage, total_cost, transcript(turn - 1))
            return

        yield TurnStarted(turn)

        assistant_parts = []
        current_text = ""
        tool_calls = []
        forced_narration_emitted = False

        for event in stream(model, system, messages, tools_schema, config.model_kwargs, streaming=config.stream):
            if isinstance(event, TextDelta):
                current_text += event.text
                yield AssistantTextDelta(event.text)
            elif isinstance(event, ToolCall):
                if config.narrate_tool_steps and not forced_narration_emitted and not current_text and not any(
                    part.get("type") == "text" and part.get("text") for part in assistant_parts
                ):
                    narration = _forced_tool_narration(
                        model=model,
                        system=system,
                        messages=messages,
                        tool_name=event.name,
                        tool_args=event.args,
                        config=config,
                    )
                    try:
                        while True:
                            narration_event = next(narration)
                            current_text += narration_event.text
                            yield AssistantTextDelta(narration_event.text)
                    except StopIteration as result:
                        _, narration_usage, narration_cost = result.value
                        total_usage.input_tokens += narration_usage.input_tokens
                        total_usage.output_tokens += narration_usage.output_tokens
                        total_cost += narration_cost
                        if narration_usage.input_tokens or narration_usage.output_tokens or narration_cost:
                            yield UsageUpdated(
                                narration_usage.input_tokens,
                                narration_usage.output_tokens,
                                narration_cost,
                            )
                    forced_narration_emitted = True
                if current_text:
                    assistant_parts.append({"type": "text", "text": current_text})
                    current_text = ""
                yield ToolCalled(event.name, event.args)
                tool_calls.append({"name": event.name, "args": event.args, "id": None, "raw_part": event.raw_part})
            elif isinstance(event, _ToolMeta):
                if tool_calls:
                    tool_calls[-1]["id"] = event.tool_use_id
            elif isinstance(event, Done):
                total_usage.input_tokens += event.usage.input_tokens
                total_usage.output_tokens += event.usage.output_tokens
                total_cost += event.cost
                yield UsageUpdated(event.usage.input_tokens, event.usage.output_tokens, event.cost)

        if current_text:
            assistant_parts.append({"type": "text", "text": current_text})
        for tc in tool_calls:
            assistant_parts.append({
                "type": "tool_call",
                "name": tc["name"],
                "args": tc["args"],
                "id": tc["id"],
                "raw_part": tc.get("raw_part"),
            })
        messages.append({"role": "assistant", "content": assistant_parts})

        if not tool_calls:
            _save_session(session_id, model, messages, total_usage)
            text = "".join(p["text"] for p in assistant_parts if p["type"] == "text")
            yield Finished("completed", text or "(no response)", turn, session_id, model,
                           total_usage, total_cost, transcript(turn))
            return

        tool_results = []
        for tc in tool_calls:
            handler = tool_handlers.get(tc["name"])
            if handler:
                try:
                    result = handler(tc["args"])
                except Exception as e:
                    result = f"Error: tool '{tc['name']}' raised {type(e).__name__}: {e}"
            else:
                result = f"Error: unknown tool '{tc['name']}'"

            preview = result[:200] + "..." if len(result) > 200 else result
            yield ToolResulted(tc["name"], result, preview)

            tool_result = {"type": "tool_result", "tool_name": tc["name"], "content": result}
            if tc["id"]:
                tool_result["tool_use_id"] = tc["id"]
                tool_result["tool_call_id"] = tc["id"]
            tool_results.append(tool_result)

        messages.append({"role": "user", "content": tool_results})
        _save_session(session_id, model, messages, total_usage)


def run(
    task: str,
    model: str | None = None,
    max_turns=_UNSET,
    provider: str | None = None,  # accepted for back-compat; LiteLLM routes by model name
    resume: str | bool = False,
    return_transcript: bool = False,
    prompt_variant: str | None = None,
) -> str | tuple[str, dict]:
    """Backward-compatible wrapper: run the agent and render to stdout.

    Builds a LeaConfig from defaults + any explicit overrides, drains the event
    stream through the default renderer, and returns the final text (and the
    transcript dict if return_transcript is True).
    """
    config = load_config(None)
    if model is not None:
        config.model_name = model
    if prompt_variant is not None:
        config.prompt_variant = prompt_variant
    if max_turns is not _UNSET:
        config.max_turns = max_turns

    text, transcript = render_to_stdout(run_events(config, task or "", resume=resume))
    return (text, transcript) if return_transcript else text
