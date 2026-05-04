from __future__ import annotations

import argparse
import os
import sys

from mentor._version import __version__
from mentor.app import run as run_bot
from mentor.quiz import default_questions_path, load_questions


def apply_run_token_env(token_env_name: str) -> None:
    """Copy token from arbitrary env var into TELEGRAM_BOT_TOKEN for the app."""
    val = os.getenv(token_env_name)
    if val:
        os.environ["TELEGRAM_BOT_TOKEN"] = val


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mentor",
        description="AI Agent DS Mentor bot utilities",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    p.add_argument(
        "--token-env",
        dest="run_token_env",
        default="TELEGRAM_BOT_TOKEN",
        metavar="NAME",
        help=(
            "Environment variable that holds the bot token for `run` "
            "(default: TELEGRAM_BOT_TOKEN). Value is copied into TELEGRAM_BOT_TOKEN."
        ),
    )
    sub = p.add_subparsers(dest="command", required=False)

    sub.add_parser("run", help="Run Telegram bot (default)")

    check = sub.add_parser("check", help="Validate configuration and question bank")
    check.add_argument(
        "--questions",
        default=os.getenv("QUESTIONS_PATH", default_questions_path()),
        help="Path to questions JSON (default: QUESTIONS_PATH or packaged questions.json)",
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
        apply_run_token_env(getattr(args, "run_token_env", "TELEGRAM_BOT_TOKEN"))
        run_bot()
        return 0

    if args.command == "check":
        return cmd_check(args)

    parser.print_help()
    return 2


def entrypoint() -> None:
    raise SystemExit(main(sys.argv[1:]))
