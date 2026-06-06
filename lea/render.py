"""Default renderer — turns the agent event stream back into Lea's stdout.

`run_events()` yields events; the CLI (and the backward-compatible `run()`
wrapper) drain them through `render_to_stdout`, which prints Lea's terminal
output (including live token streaming and per-turn cost) and returns the final
`(text, transcript)`. A UI would write its own consumer instead of this.
"""

import sys

from .events import (
    SessionResumed,
    TurnStarted,
    AssistantTextDelta,
    ToolCalled,
    ToolResulted,
    UsageUpdated,
    Finished,
)


def render_to_stdout(events) -> tuple[str, dict]:
    """Consume the event stream, print Lea's usual output, return (text, transcript)."""
    result: tuple[str, dict] = ("", {})
    current_turn = 0
    cum_in = cum_out = 0
    cum_cost = 0.0

    for event in events:
        if isinstance(event, AssistantTextDelta):
            sys.stdout.write(event.text)
            sys.stdout.flush()
        elif isinstance(event, TurnStarted):
            current_turn = event.turn
            print(f"\n--- turn {event.turn} ---", flush=True)
        elif isinstance(event, ToolCalled):
            print(f"\n  -> {event.name}({event.args})", flush=True)
        elif isinstance(event, ToolResulted):
            print(f"  <- {event.preview}", flush=True)
        elif isinstance(event, SessionResumed):
            print(f"Resuming session {event.session_id} ({event.message_count} messages)", flush=True)
        elif isinstance(event, UsageUpdated):
            cum_in += event.input_tokens
            cum_out += event.output_tokens
            cum_cost += event.cost
            turn_tok = event.input_tokens + event.output_tokens
            cum_tok = cum_in + cum_out
            print(
                f"  [turn {current_turn}: {turn_tok:,} tok · ${event.cost:.6f} "
                f"| total: {cum_tok:,} tok · ${cum_cost:.6f}]",
                flush=True,
            )
        elif isinstance(event, Finished):
            if event.reason == "completed":
                print()  # blank line before the usage summary
            total = event.usage.input_tokens + event.usage.output_tokens
            print(
                f"\n--- {event.turns} turns, {total:,} tokens "
                f"(in: {event.usage.input_tokens:,}, out: {event.usage.output_tokens:,}), "
                f"~${event.cost:.4f} ---",
                flush=True,
            )
            result = (event.text, event.transcript)
    return result
