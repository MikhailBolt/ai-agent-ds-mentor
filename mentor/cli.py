from __future__ import annotations

import argparse
import os
import sys

from mentor.app import run as run_bot
from mentor.quiz import load_questions


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mentor", description="AI Agent DS Mentor bot utilities")
    sub = p.add_subparsers(dest="command", required=False)

    run = sub.add_parser("run", help="Run Telegram bot (default)")
    run.add_argument(
        "--token-env",
        default="TELEGRAM_BOT_TOKEN",
        help="Environment variable name with Telegram bot token",
    )

    check = sub.add_parser("check", help="Validate configuration and question bank")
    check.add_argument(
        "--questions",
        default=os.getenv("QUESTIONS_PATH", os.path.join("data", "questions.json")),
        help="Path to questions JSON (default: QUESTIONS_PATH or data/questions.json)",
    )
    check.add_argument(
        "--skip-token",
        action="store_true",
        help="Skip Telegram token presence check (useful in CI)",
    )
    check.add_argument(
        "--token-env",
        default="TELEGRAM_BOT_TOKEN",
        help="Environment variable name with Telegram bot token",
    )

    return p


def cmd_check(args: argparse.Namespace) -> int:
    if not args.skip_token and not os.getenv(args.token_env):
        print(f"Missing env var {args.token_env}", file=sys.stderr)
        return 2

    try:
        qs = load_questions(args.questions)
    except Exception as e:
        print(f"Questions load failed: {e}", file=sys.stderr)
        return 2

    print(f"OK: loaded {len(qs)} questions from {args.questions}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Default command: run
    if args.command in (None, "run"):
        run_bot()
        return 0

    if args.command == "check":
        return cmd_check(args)

    parser.print_help()
    return 2
