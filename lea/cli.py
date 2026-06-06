"""Lea CLI — minimal entry point."""

import argparse
import sys

from .config import load_config, DEFAULT_CONFIG_PATH
from .agent import run_events, list_sessions
from .render import render_to_stdout


def main():
    parser = argparse.ArgumentParser(
        description="Lea — a minimal Lean 4 formalization agent",
    )
    parser.add_argument(
        "task",
        nargs="?",
        help="Math statement to formalize (or reads from stdin if omitted).",
    )
    parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG_PATH),
        help=f"Path to a YAML config, overlaid on the defaults (default: {DEFAULT_CONFIG_PATH}).",
    )
    parser.add_argument(
        "-m", "--model", default=None,
        help="Model to use as LiteLLM 'provider/model' (overrides config).",
    )
    parser.add_argument(
        "--max-turns", type=int, default=None, help="Max agent turns (overrides config).",
    )
    parser.add_argument(
        "--sketch", action="store_true", help="Use the sketch prompt (produce a proof skeleton with sorry's).",
    )
    parser.add_argument(
        "--fill", action="store_true", help="Use the fill prompt (fill sorry's in an existing file).",
    )
    parser.add_argument(
        "--resume", nargs="?", const=True, default=False,
        help="Resume a session. Pass a session ID, or omit to resume the most recent.",
    )
    parser.add_argument(
        "--sessions", action="store_true", help="List recent sessions and exit.",
    )

    args = parser.parse_args()

    if args.sessions:
        sessions = list_sessions()
        if not sessions:
            print("No sessions found.")
        for s in sessions:
            print(f"  {s['id']}  {s['model']:30s}  {s['turns']:>3} turns  {s['task']}")
        return

    task = args.task
    if not task and not args.resume:
        if sys.stdin.isatty():
            parser.print_help()
            sys.exit(1)
        task = sys.stdin.read().strip()

    # Build config, then apply CLI overrides (flag beats file).
    config = load_config(args.config)
    if args.model:
        config.model_name = args.model
    if args.max_turns is not None:
        config.max_turns = args.max_turns
    if args.sketch:
        config.prompt_variant = "sketch"
    elif args.fill:
        config.prompt_variant = "fill"

    text, _ = render_to_stdout(run_events(config, task or "", resume=args.resume))
    print(text)


if __name__ == "__main__":
    main()
