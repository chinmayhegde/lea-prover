"""Event wire format — the public, versioned JSON schema.

Maps each frozen dataclass in ``lea/events.py`` to a JSON frame matching design
§3. Two fields the dataclasses lack are added here: ``schema_version`` (constant)
and ``seq`` (a monotonic counter assigned by the run bridge, *not* here — see
jobs.py, which calls ``stamp_seq``).

The one non-mechanical mapping: the ``Finished`` frame is serialized *without*
its large ``transcript`` dict and *with* a ``transcript_url`` instead — the
stream links the transcript rather than inlining it (design §3, §4.1).

Keeping the whole mapping in one file makes the "event JSON is a versioned wire
format" guarantee enforceable: additive changes only within a version.
"""

from __future__ import annotations

from dataclasses import asdict

from lea.events import (
    AssistantTextDelta,
    Finished,
    SessionResumed,
    ToolCalled,
    ToolResulted,
    TurnStarted,
    UsageUpdated,
)

SCHEMA_VERSION = "1"

# Frame `type` values that terminate a stream. A stream ends with exactly one.
TERMINAL_TYPES = {"finished", "error"}


def to_frame(ev, run_id: str) -> dict:
    """Serialize one agent event to a wire frame (without ``seq``).

    ``run_id`` is needed only to build the Finished ``transcript_url``.
    """
    if isinstance(ev, SessionResumed):
        return {"type": "session_resumed", "session_id": ev.session_id,
                "message_count": ev.message_count}
    if isinstance(ev, TurnStarted):
        return {"type": "turn_started", "turn": ev.turn}
    if isinstance(ev, AssistantTextDelta):
        return {"type": "assistant_text_delta", "text": ev.text}
    if isinstance(ev, ToolCalled):
        return {"type": "tool_called", "name": ev.name, "args": ev.args}
    if isinstance(ev, ToolResulted):
        return {"type": "tool_resulted", "name": ev.name,
                "content": ev.content, "preview": ev.preview}
    if isinstance(ev, UsageUpdated):
        return {"type": "usage_updated", "input_tokens": ev.input_tokens,
                "output_tokens": ev.output_tokens, "cost": ev.cost}
    if isinstance(ev, Finished):
        return {
            "type": "finished",
            "reason": ev.reason,
            "text": ev.text,
            "turns": ev.turns,
            "session_id": ev.session_id,
            "model": ev.model,
            "usage": asdict(ev.usage),
            "cost": ev.cost,
            "transcript_url": f"/v1/runs/{run_id}/transcript",
        }
    raise TypeError(f"unknown event type: {type(ev).__name__}")


def cancelled_frame(run_id: str, model: str, session_id: str | None,
                    turns: int, usage: dict, cost: float) -> dict:
    """A synthesized terminal frame for a cancelled run.

    ``run_events`` does not yield a ``Finished`` when its generator is closed,
    so the bridge synthesizes one so the contract ("ends with exactly one
    finished/error frame") still holds.
    """
    return {
        "type": "finished",
        "reason": "cancelled",
        "text": "Run cancelled.",
        "turns": turns,
        "session_id": session_id,
        "model": model,
        "usage": usage,
        "cost": cost,
        "transcript_url": f"/v1/runs/{run_id}/transcript",
    }


def error_frame(error_type: str, message: str, field: str | None = None) -> dict:
    """A terminal error frame (mirrors the HTTP error body shape)."""
    err: dict = {"type": error_type, "message": message}
    if field is not None:
        err["field"] = field
    return {"type": "error", "error": err}


def stamp(frame: dict, seq: int) -> dict:
    """Attach the bridge-assigned ``seq`` and the constant ``schema_version``."""
    return {**frame, "seq": seq, "schema_version": SCHEMA_VERSION}
