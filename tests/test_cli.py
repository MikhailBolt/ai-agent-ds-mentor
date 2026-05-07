import json
import os
from pathlib import Path

import pytest

from mentor import __version__ as package_version
from mentor._version import __version__ as version_module_version
from mentor.cli import apply_env_override, apply_run_token_env, main


def test_version_matches_package() -> None:
    assert package_version == version_module_version


def test_apply_run_token_env_copies_to_standard_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("MY_BOT_TOKEN", "abc123")
    apply_run_token_env("MY_BOT_TOKEN")
    assert os.environ.get("TELEGRAM_BOT_TOKEN") == "abc123"


def test_apply_env_override_sets_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("X_TEST", raising=False)
    apply_env_override("X_TEST", "1")
    assert os.environ["X_TEST"] == "1"


def test_run_dry_run_validates_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    rc = main(["run", "--dry-run"])
    assert rc == 0


def test_check_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "q.json"
    p.write_text(json.dumps([{"id": "a", "prompt": "Q?", "answer": "yes"}]), encoding="utf-8")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    rc = main(["check", "--skip-token", "--questions", str(p)])
    assert rc == 0


def test_check_init_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    q = tmp_path / "q.json"
    q.write_text(json.dumps([{"id": "a", "prompt": "Q?", "answer": "yes"}]), encoding="utf-8")
    db = tmp_path / "bot.db"
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    rc = main(["check", "--skip-token", "--questions", str(q), "--db-path", str(db), "--init-db"])
    assert rc == 0
    assert db.exists()


def test_check_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "missing.json"
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    rc = main(["check", "--skip-token", "--questions", str(missing)])
    assert rc == 2


def test_check_requires_token_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    rc = main(["check", "--questions", "mentor/data/questions.json"])
    assert rc == 2
