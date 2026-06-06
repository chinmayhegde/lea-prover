"""Live smoke test: real Gemini call through the LiteLLM provider wrapper.

Exercises the actual API end-to-end at the provider layer — streaming text, a
tool call, token usage, and LiteLLM cost — WITHOUT the agent loop (which is
mid-refactor). Needs a real key in the environment.

Run:  GEMINI_API_KEY="$(cat .gemini_key)" uv run python -m tests.providers.live_smoke [model]
Default model: gemini/gemini-2.5-flash  (cheap + fast for a smoke test)
"""

import sys

from lea.providers import stream, TextDelta, ToolCall, Done, _ToolMeta
from lea.tools import TOOLS_SCHEMA

MODEL = sys.argv[1] if len(sys.argv) > 1 else "gemini/gemini-2.5-flash"

SYSTEM = "You are a terse assistant. First say in one short sentence what you will do, then call the bash tool."
MESSAGES = [{"role": "user", "content": "Use the bash tool to run: echo hello"}]


def main():
    print(f"=== live smoke: {MODEL} ===\n")
    n_text = n_tools = 0
    done = None
    print("[stream] ", end="", flush=True)
    for event in stream(MODEL, SYSTEM, MESSAGES, TOOLS_SCHEMA, model_kwargs={"max_tokens": 512}):
        if isinstance(event, TextDelta):
            sys.stdout.write(event.text)
            sys.stdout.flush()
            n_text += 1
        elif isinstance(event, ToolCall):
            n_tools += 1
            print(f"\n[tool call] {event.name}({event.args})", flush=True)
        elif isinstance(event, _ToolMeta):
            pass
        elif isinstance(event, Done):
            done = event

    print("\n\n=== result ===")
    print(f"text deltas: {n_text}")
    print(f"tool calls : {n_tools}")
    if done:
        u = done.usage
        print(f"usage      : in={u.input_tokens}, out={u.output_tokens}")
        print(f"cost       : ${done.cost:.6f}")
    ok = n_text > 0 and done is not None
    print("\nSMOKE OK" if ok else "\nSMOKE INCOMPLETE")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
