"""Unit tests for the event contract (events.py) and the stdout renderer (render.py).

Asserts the renderer reproduces Lea's output (including per-turn cost) from a
synthetic event stream — no model or network needed.

Run:  uv run python -m tests.render.test_render
Exits 0 if every check passes, 1 otherwise.
"""

import io
import sys
from contextlib import redirect_stdout
from dataclasses import FrozenInstanceError

from lea.providers import Usage
from lea.render import render_to_stdout
from lea.events import (
    SessionResumed,
    TurnStarted,
    AssistantTextDelta,
    ToolCalled,
    ToolResulted,
    UsageUpdated,
    Finished,
)

_FAILURES: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _FAILURES.append(name)


def check_eq(name: str, got, want) -> None:
    if got == want:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}\n    got:  {got!r}\n    want: {want!r}")
        _FAILURES.append(name)


def render_capture(events) -> tuple[str, tuple]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = render_to_stdout(iter(events))
    return buf.getvalue(), result


def test_frozen():
    e = TurnStarted(1)
    try:
        e.turn = 2
    except FrozenInstanceError:
        check("events are frozen/immutable", True)
    else:
        check("events are frozen/immutable", False)


def test_completed_parity_with_per_turn_cost():
    events = [
        TurnStarted(1),
        AssistantTextDelta("Hello "),
        AssistantTextDelta("world"),
        ToolCalled("lean_check", {"path": "/x.lean"}),
        UsageUpdated(100, 50, 0.0042),
        ToolResulted("lean_check", "OK", "OK"),
        TurnStarted(2),
        AssistantTextDelta("Done."),
        UsageUpdated(20, 10, 0.0008),
        Finished(
            reason="completed", text="Done.", turns=2, session_id="sid",
            model="gemini/gemini-2.5-flash", usage=Usage(120, 60), cost=0.005,
            transcript={"k": "v"},
        ),
    ]
    expected = (
        "\n--- turn 1 ---\n"
        "Hello world"
        "\n  -> lean_check({'path': '/x.lean'})\n"
        "  [turn 1: 150 tok · $0.004200 | total: 150 tok · $0.004200]\n"
        "  <- OK\n"
        "\n--- turn 2 ---\n"
        "Done."
        "  [turn 2: 30 tok · $0.000800 | total: 180 tok · $0.005000]\n"
        "\n"
        "\n--- 2 turns, 180 tokens (in: 120, out: 60), ~$0.0050 ---\n"
    )
    out, (text, transcript) = render_capture(events)
    check_eq("completed: stdout byte-for-byte", out, expected)
    check_eq("completed: returned text", text, "Done.")
    check_eq("completed: returned transcript", transcript, {"k": "v"})


def test_max_turns_no_blank_line():
    events = [
        TurnStarted(1),
        AssistantTextDelta("partial"),
        Finished(
            reason="max_turns", text="Error: max turns reached without completing the proof.",
            turns=1, session_id="sid", model="gemini/gemini-2.5-flash",
            usage=Usage(10, 5), cost=0.0, transcript={},
        ),
    ]
    expected = (
        "\n--- turn 1 ---\n"
        "partial"
        "\n--- 1 turns, 15 tokens (in: 10, out: 5), ~$0.0000 ---\n"
    )
    out, (text, _) = render_capture(events)
    check_eq("max_turns: stdout (no blank line before usage)", out, expected)
    check_eq("max_turns: returned text", text, "Error: max turns reached without completing the proof.")


def test_session_resumed():
    events = [
        SessionResumed("20260602-000000", 3),
        TurnStarted(1),
        AssistantTextDelta("hi"),
        UsageUpdated(1, 1, 0.0),
        Finished(
            reason="completed", text="hi", turns=1, session_id="20260602-000000",
            model="gemini/gemini-2.5-flash", usage=Usage(1, 1), cost=0.0, transcript={},
        ),
    ]
    out, _ = render_capture(events)
    check("session resumed line printed", out.startswith("Resuming session 20260602-000000 (3 messages)\n"))


def main():
    print("events + render tests:")
    test_frozen()
    test_completed_parity_with_per_turn_cost()
    test_max_turns_no_blank_line()
    test_session_resumed()
    print()
    if _FAILURES:
        print(f"FAILED ({len(_FAILURES)}): {', '.join(_FAILURES)}")
        sys.exit(1)
    print("All render tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
