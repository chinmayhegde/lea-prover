"""Smoke test: run the Lea agent on a trivial bash-tool task for each provider.

Usage:
    uv run python -m eval.probe_providers
    uv run python -m eval.probe_providers --models gemini-3.1-pro-preview claude-opus-4-7

Verifies: streaming, tool-call round-trip, usage reporting. Cost < $0.05 total.
"""

import argparse
import os
import sys
import time

from lea.agent import run

DEFAULT_MODELS = [
    "gemini-3.1-pro-preview",
    "claude-opus-4-7",
    "gpt-5.4-pro-2026-03-05",
]

TASK = (
    "Use the bash tool to run `echo 42`, then reply with a single sentence "
    "telling me what it printed. Do not use any other tool."
)

REQUIRED_ENV = {
    "gemini": "GOOGLE_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "gpt": "OPENAI_API_KEY",
}


def required_env_for(model: str) -> str:
    for prefix, key in REQUIRED_ENV.items():
        if model.startswith(prefix):
            return key
    return ""


def probe(model: str) -> dict:
    key = required_env_for(model)
    if key and not os.environ.get(key):
        return {"model": model, "ok": False, "reason": f"{key} not set in env"}

    start = time.time()
    try:
        _, transcript = run(
            TASK, model=model, max_turns=5, return_transcript=True
        )
    except Exception as e:
        return {"model": model, "ok": False, "reason": f"{type(e).__name__}: {e}"}
    elapsed = time.time() - start

    msgs = transcript["messages"]
    tool_calls = sum(
        1
        for m in msgs
        if m["role"] == "assistant"
        and isinstance(m["content"], list)
        for item in m["content"]
        if item.get("type") == "tool_call"
    )
    final_text = ""
    for m in reversed(msgs):
        if m["role"] == "assistant" and isinstance(m["content"], list):
            for item in m["content"]:
                if item.get("type") == "text" and item.get("text"):
                    final_text = item["text"]
                    break
            if final_text:
                break

    usage = transcript.get("usage", {})
    has_42 = "42" in final_text
    ok = tool_calls >= 1 and has_42 and (usage.get("input_tokens", 0) > 0)
    return {
        "model": model,
        "ok": ok,
        "elapsed_s": round(elapsed, 1),
        "tool_calls": tool_calls,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "final_text": final_text[:200],
        "reason": "" if ok else (
            f"tool_calls={tool_calls} has_42={has_42} usage={usage}"
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    args = parser.parse_args()

    results = []
    for m in args.models:
        print(f"--- Probing {m} ---", flush=True)
        r = probe(m)
        results.append(r)
        status = "OK " if r["ok"] else "FAIL"
        print(f"  [{status}] {r}\n", flush=True)

    print("=" * 60)
    for r in results:
        mark = "+" if r["ok"] else "-"
        print(f"  {mark} {r['model']:40s} {'ok' if r['ok'] else r['reason']}")
    if not all(r["ok"] for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
