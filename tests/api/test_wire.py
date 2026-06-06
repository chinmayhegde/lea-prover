"""The event wire format is a versioned public schema — pin it with golden frames."""

from lea.events import (
    AssistantTextDelta,
    SessionResumed,
    ToolCalled,
    ToolResulted,
    TurnStarted,
    UsageUpdated,
)
from lea_api import wire

from .conftest import make_finished


def test_each_event_maps_to_its_frame():
    rid = "run_abc"
    assert wire.to_frame(SessionResumed("s", 12), rid) == {
        "type": "session_resumed", "session_id": "s", "message_count": 12}
    assert wire.to_frame(TurnStarted(3), rid) == {"type": "turn_started", "turn": 3}
    assert wire.to_frame(AssistantTextDelta("hi"), rid) == {
        "type": "assistant_text_delta", "text": "hi"}
    assert wire.to_frame(ToolCalled("lean_check", {"p": 1}), rid) == {
        "type": "tool_called", "name": "lean_check", "args": {"p": 1}}
    assert wire.to_frame(ToolResulted("t", "full", "prev"), rid) == {
        "type": "tool_resulted", "name": "t", "content": "full", "preview": "prev"}
    assert wire.to_frame(UsageUpdated(5, 6, 0.02), rid) == {
        "type": "usage_updated", "input_tokens": 5, "output_tokens": 6, "cost": 0.02}


def test_finished_links_transcript_and_omits_it():
    frame = wire.to_frame(make_finished(), "run_xyz")
    assert frame["type"] == "finished"
    assert frame["transcript_url"] == "/v1/runs/run_xyz/transcript"
    assert "transcript" not in frame          # the large dict is linked, not inlined
    assert frame["usage"] == {"input_tokens": 100, "output_tokens": 20}


def test_stamp_adds_seq_and_schema_version():
    stamped = wire.stamp({"type": "turn_started", "turn": 1}, 7)
    assert stamped["seq"] == 7
    assert stamped["schema_version"] == wire.SCHEMA_VERSION


def test_cancelled_frame_is_terminal_finished():
    f = wire.cancelled_frame("run_1", "m", "sess", 4, {"input_tokens": 1, "output_tokens": 2}, 0.0)
    assert f["type"] == "finished" and f["reason"] == "cancelled"
    assert f["type"] in wire.TERMINAL_TYPES
