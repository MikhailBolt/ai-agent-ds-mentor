from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from mentor._version import __version__
from mentor.app import DEFAULT_REPO_URL
from mentor.app import run as run_bot
from mentor.competencies import default_competencies_path, load_competencies
from mentor.db import connect, ensure_schema, verify_schema
from mentor.quiz import (
    default_questions_path,
    load_questions,
    question_counts_by_difficulty,
    validate_competency_coverage,
)


def apply_run_token_env(token_env_name: str) -> None:
    """Copy token from arbitrary env var into TELEGRAM_BOT_TOKEN for the app."""
    val = os.getenv(token_env_name)
    if val:
        os.environ["TELEGRAM_BOT_TOKEN"] = val


def apply_env_override(env_name: str, value: str | None) -> None:
    if value is None:
        return
    os.environ[env_name] = value


def load_project_dotenv() -> None:
    """Load `.env` from the current working directory when present."""
    env_file = Path.cwd() / ".env"
    if env_file.is_file():
        load_dotenv(env_file)
    else:
        load_dotenv()


def namespace_for_run_dry_run(args: argparse.Namespace) -> argparse.Namespace:
    """Full check namespace after env overrides (matches `mentor check` defaults)."""
    token_env_name = getattr(args, "run_token_env", "TELEGRAM_BOT_TOKEN")
    return argparse.Namespace(
        questions=os.getenv("QUESTIONS_PATH", default_questions_path()),
        competencies=os.getenv("COMPETENCIES_PATH", default_competencies_path()),
        db_path=os.getenv("DB_PATH", "bot.db"),
        init_db=False,
        print_config=False,
        skip_token=False,
        token_env=token_env_name,
    )


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

    run = sub.add_parser("run", help="Run Telegram bot (default)")
    run.add_argument(
        "--questions",
        default=None,
        help="Override QUESTIONS_PATH for this run",
    )
    run.add_argument(
        "--db-path",
        default=None,
        help="Override DB_PATH for this run",
    )
    run.add_argument(
        "--log-level",
        default=None,
        help="Override LOG_LEVEL for this run (e.g. INFO, DEBUG)",
    )
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and exit without starting polling",
    )

    check = sub.add_parser("check", help="Validate configuration and question bank")
    check.add_argument(
        "--list-questions",
        action="store_true",
        help="List question ids grouped by competency (implies validation)",
    )
    check.add_argument(
        "--questions",
        default=os.getenv("QUESTIONS_PATH", default_questions_path()),
        help="Path to questions JSON (default: QUESTIONS_PATH or packaged questions.json)",
    )
    check.add_argument(
        "--competencies",
        default=os.getenv("COMPETENCIES_PATH", default_competencies_path()),
        help="Path to competencies JSON (default: COMPETENCIES_PATH or packaged file)",
    )
    check.add_argument(
        "--db-path",
        default=os.getenv("DB_PATH", "bot.db"),
        help="SQLite path to initialize/check (default: DB_PATH or bot.db)",
    )
    check.add_argument(
        "--init-db",
        action="store_true",
        help="Create/upgrade SQLite schema in DB_PATH (safe operation)",
    )
    check.add_argument(
        "--verify-db",
        action="store_true",
        help="Verify SQLite schema in DB_PATH (requires existing database file)",
    )
    check.add_argument(
        "--print-config",
        action="store_true",
        help="Print resolved configuration and exit (still validates questions)",
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
    token_present = bool(os.getenv(args.token_env))
    if not args.skip_token and not token_present:
        print(f"Missing env var {args.token_env}", file=sys.stderr)
        return 2

    comp_path = args.competencies
    try:
        competencies = load_competencies(comp_path)
        comp_ids = {c.id for c in competencies}
        qs = load_questions(args.questions, valid_competency_ids=comp_ids)
        validate_competency_coverage(qs, comp_ids)
    except Exception as e:
        print(f"Config load failed: {e}", file=sys.stderr)
        return 2

    if getattr(args, "list_questions", False):
        by_comp: dict[str, list[str]] = {cid: [] for cid in comp_ids}
        for q in qs:
            if q.competency_id:
                by_comp.setdefault(q.competency_id, []).append(q.id)
        for c in competencies:
            ids = ", ".join(by_comp.get(c.id, []))
            print(f"{c.id}\t{c.title}\t{ids}")
        return 0

    if getattr(args, "init_db", False):
        try:
            conn = connect(args.db_path)
            try:
                ensure_schema(conn)
            finally:
                conn.close()
        except Exception as e:
            print(f"DB init failed: {e}", file=sys.stderr)
            return 2

    if getattr(args, "verify_db", False):
        db_file = Path(args.db_path)
        if not db_file.is_file():
            print(f"Database file missing: {args.db_path}", file=sys.stderr)
            return 2
        try:
            conn = connect(args.db_path)
            try:
                verify_schema(conn)
            finally:
                conn.close()
        except Exception as e:
            print(f"DB verify failed: {e}", file=sys.stderr)
            return 2

    if getattr(args, "print_config", False):
        print(f"version={__version__}")
        print(f"questions_path={args.questions}")
        print(f"competencies_path={comp_path}")
        print(f"competency_count={len(competencies)}")
        print(f"question_count={len(qs)}")
        diff_counts = question_counts_by_difficulty(qs)
        for level in sorted(diff_counts):
            print(f"questions_difficulty_{level}={diff_counts[level]}")
        print(f"db_path={args.db_path}")
        print(f"log_level={os.getenv('LOG_LEVEL', 'INFO')}")
        print(f"project_repo_url={os.getenv('PROJECT_REPO_URL', DEFAULT_REPO_URL)}")
        print(f"token_env={args.token_env}")
        print(f"token_present={'1' if token_present else '0'}")
        print(f"init_db={'1' if getattr(args, 'init_db', False) else '0'}")
        print(f"verify_db={'1' if getattr(args, 'verify_db', False) else '0'}")
        return 0

    msg = f"OK: loaded {len(qs)} questions from {args.questions}"
    if getattr(args, "init_db", False):
        msg += f"; db schema ok at {args.db_path}"
    if getattr(args, "verify_db", False):
        msg += f"; db verified at {args.db_path}"
    print(msg)
    return 0


def main(argv: list[str] | None = None) -> int:
    load_project_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)

    # Default command: run
    if args.command in (None, "run"):
        apply_run_token_env(getattr(args, "run_token_env", "TELEGRAM_BOT_TOKEN"))
        apply_env_override("QUESTIONS_PATH", getattr(args, "questions", None))
        apply_env_override("DB_PATH", getattr(args, "db_path", None))
        apply_env_override("LOG_LEVEL", getattr(args, "log_level", None))

        if getattr(args, "dry_run", False):
            return cmd_check(namespace_for_run_dry_run(args))

        run_bot()
        return 0

    if args.command == "check":
        return cmd_check(args)

    parser.print_help()
    return 2


def entrypoint() -> None:
    raise SystemExit(main(sys.argv[1:]))
