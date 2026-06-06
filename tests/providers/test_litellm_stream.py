"""Unit test for the LiteLLM streaming wrapper (providers.stream).

Mocks litellm.completion (canned chunks) and litellm.cost_per_token so the
event mapping, tool-call assembly, and cost are verified without any network.

Run:  uv run python -m tests.providers.test_litellm_stream
Exits 0 if every check passes, 1 otherwise.
"""

import sys
import types

import lea.providers as providers
from lea.providers import TextDelta, ToolCall, Done, _ToolMeta, Usage

_FAILURES: list[str] = []
_CAPTURED: dict = {}


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _FAILURES.append(name)


def ns(**kw):
    return types.SimpleNamespace(**kw)


def _choice(content=None, tool_calls=None, finish_reason=None):
    return ns(delta=ns(content=content, tool_calls=tool_calls), finish_reason=finish_reason)


def _chunk(choices, usage=None):
    return ns(choices=choices, usage=usage)


def fake_completion(**kwargs):
    _CAPTURED.update(kwargs)
    return [
        _chunk([_choice(content="Hello ")]),
        _chunk([_choice(content="world")]),
        _chunk([_choice(tool_calls=[ns(index=0, id="call_1",
                                       function=ns(name="lean_check", arguments='{"path":'))])]),
        _chunk([_choice(tool_calls=[ns(index=0, id=None,
                                       function=ns(name=None, arguments=' "/x.lean"}'))])]),
        _chunk([_choice(finish_reason="tool_calls")]),
        _chunk([], usage=ns(prompt_tokens=100, completion_tokens=50)),
    ]


def fake_cost_per_token(model, prompt_tokens, completion_tokens):
    return (0.001, 0.002)


def fake_completion_blocking(**kwargs):
    _CAPTURED.update(kwargs)
    message = ns(
        content="Hello world",
        tool_calls=[ns(id="call_1", function=ns(name="lean_check", arguments='{"path": "/x.lean"}'))],
    )
    return ns(choices=[ns(message=message)], usage=ns(prompt_tokens=100, completion_tokens=50))


TOOLS = [{
    "name": "lean_check",
    "description": "check a Lean file",
    "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
}]
MESSAGES = [{"role": "user", "content": "prove it"}]


def test_blocking_mode():
    providers.litellm.completion = fake_completion_blocking
    providers.litellm.cost_per_token = fake_cost_per_token
    events = list(providers.stream("gemini/test-model", "SYS", MESSAGES, TOOLS, {"max_tokens": 100}, streaming=False))
    check("blocking: TextDelta whole content", events[0] == TextDelta("Hello world"))
    check("blocking: ToolCall assembled", events[1] == ToolCall("lean_check", {"path": "/x.lean"}))
    check("blocking: _ToolMeta id", events[2] == _ToolMeta("call_1"))
    check("blocking: Done usage", isinstance(events[-1], Done) and events[-1].usage == Usage(100, 50))
    check("blocking: Done cost", abs(events[-1].cost - 0.003) < 1e-9)


def main():
    print("providers (LiteLLM stream) tests:")
    providers.litellm.completion = fake_completion
    providers.litellm.cost_per_token = fake_cost_per_token

    tools = TOOLS
    messages = MESSAGES
    events = list(providers.stream("gemini/test-model", "SYS", messages, tools, {"max_tokens": 100}))

    # Event sequence
    check("event[0] TextDelta 'Hello '", events[0] == TextDelta("Hello "))
    check("event[1] TextDelta 'world'", events[1] == TextDelta("world"))
    check("event[2] ToolCall assembled args", events[2] == ToolCall("lean_check", {"path": "/x.lean"}))
    check("event[3] _ToolMeta id", events[3] == _ToolMeta("call_1"))
    check("last event is Done", isinstance(events[-1], Done))
    check("no duplicate tool calls", sum(isinstance(e, ToolCall) for e in events) == 1)

    done = events[-1]
    check("Done.usage", done.usage == Usage(100, 50))
    check("Done.cost == 0.003", abs(done.cost - 0.003) < 1e-9)

    # Converters fed LiteLLM the right thing
    check("model passed through", _CAPTURED.get("model") == "gemini/test-model")
    check("stream=True", _CAPTURED.get("stream") is True)
    check("max_tokens from model_kwargs", _CAPTURED.get("max_tokens") == 100)
    msgs = _CAPTURED.get("messages", [])
    check("system message first", msgs and msgs[0] == {"role": "system", "content": "SYS"})
    sent_tools = _CAPTURED.get("tools") or []
    check("openai function-tool shape",
          bool(sent_tools) and sent_tools[0]["type"] == "function"
          and sent_tools[0]["function"]["name"] == "lean_check")

    test_blocking_mode()

    print()
    if _FAILURES:
        print(f"FAILED ({len(_FAILURES)}): {', '.join(_FAILURES)}")
        sys.exit(1)
    print("All providers tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
