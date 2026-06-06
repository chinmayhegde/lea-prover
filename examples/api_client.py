#!/usr/bin/env python3
"""Tiny client for the Lea API: start a run and pretty-print the streamed events.

Uses only the standard library, so it needs no extra deps.

Examples:
    # default model (needs GOOGLE_API_KEY on the server)
    python examples/api_client.py "Prove that for all natural numbers n, n + 0 = n"

    # point at a different host / override the model per-run
    LEA_API_BASE=http://localhost:8000 \\
    LEA_MODEL=anthropic/claude-sonnet-4-20250514 \\
    python examples/api_client.py "Prove that 2 + 3 = 5"

    # if the server has auth enabled (LEA_API_KEYS set), pass a key
    LEA_API_KEY=secret python examples/api_client.py "..."

Env:
    LEA_API_BASE   base URL of the API           (default http://localhost:8000)
    LEA_MODEL      override config.model.name    (optional)
    LEA_API_KEY    bearer token                  (only if the server enforces auth)
"""

import json
import os
import sys
import urllib.request

BASE = os.environ.get("LEA_API_BASE", "http://localhost:8000").rstrip("/")
KEY = os.environ.get("LEA_API_KEY")
MODEL = os.environ.get("LEA_MODEL")


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if KEY:
        h["Authorization"] = f"Bearer {KEY}"
    return h


def start_run(task: str) -> dict:
    body: dict = {"task": task}
    if MODEL:
        # Partial config overlay: only model.name is overridden; stream and
        # model_kwargs come from the server's default.yaml.
        body["config"] = {"model": {"name": MODEL}}
    req = urllib.request.Request(
        f"{BASE}/v1/runs", data=json.dumps(body).encode(),
        headers=_headers(), method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def stream(run_id: str) -> None:
    req = urllib.request.Request(f"{BASE}/v1/runs/{run_id}/events", headers=_headers())
    with urllib.request.urlopen(req) as r:
        event = None
        for raw in r:                       # HTTPResponse iterates line by line
            line = raw.decode("utf-8").rstrip("\n")
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                render(event, json.loads(line[6:]))
            # blank lines (frame separators) and ": keep-alive" comments are ignored


def render(event: str | None, d: dict) -> None:
    if event == "turn_started":
        print(f"\n\033[2m--- turn {d['turn']} ---\033[0m")
    elif event == "assistant_text_delta":
        sys.stdout.write(d["text"])
        sys.stdout.flush()
    elif event == "tool_called":
        args = json.dumps(d["args"])
        print(f"\n\033[36m[tool] {d['name']}({args[:140]})\033[0m")
    elif event == "tool_resulted":
        print(f"\033[33m[result] {d['preview']}\033[0m")
    elif event == "usage_updated":
        print(f"\033[2m[usage] +{d['input_tokens']} in / {d['output_tokens']} out  "
              f"${d['cost']:.4f}\033[0m")
    elif event == "session_resumed":
        print(f"\033[2m[resumed session {d['session_id']} — {d['message_count']} msgs]\033[0m")
    elif event == "finished":
        print(f"\n\033[32m=== finished: {d['reason']} | {d['turns']} turns | "
              f"${d['cost']:.4f} ===\033[0m")
        print(d["text"])
        print(f"\033[2mtranscript: {BASE}{d['transcript_url']}\033[0m")
    elif event == "error":
        print(f"\n\033[31m!!! error: {d['error']}\033[0m")


def main() -> None:
    task = sys.argv[1] if len(sys.argv) > 1 else \
        "Prove that for all natural numbers n, n + 0 = n"
    info = start_run(task)
    print(f"run_id = {info['run_id']}   status = {info['status']}")
    stream(info["run_id"])


if __name__ == "__main__":
    main()
