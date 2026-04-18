"""Lea CLI — minimal entry point."""

import argparse
import sys

from .agent import run, DEFAULT_MODEL, MAX_TURNS


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
        "-m", "--model", default=DEFAULT_MODEL, help=f"Model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--max-turns", type=int, default=MAX_TURNS, help=f"Max agent turns (default: {MAX_TURNS})",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print each turn's tool calls and results.",
    )

    args = parser.parse_args()

    task = args.task
    if not task:
        if sys.stdin.isatty():
            parser.print_help()
            sys.exit(1)
        task = sys.stdin.read().strip()

    result = run(task, model=args.model, max_turns=args.max_turns, verbose=args.verbose)
    print(result)


if __name__ == "__main__":
    main()
