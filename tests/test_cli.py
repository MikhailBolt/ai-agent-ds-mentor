import json
from pathlib import Path

import pytest

from mentor import __version__ as package_version
from mentor._version import __version__ as version_module_version
from mentor.cli import main


def test_version_matches_package() -> None:
    assert package_version == version_module_version


def test_check_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "q.json"
    p.write_text(json.dumps([{"id": "a", "prompt": "Q?", "answer": "yes"}]), encoding="utf-8")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    rc = main(["check", "--skip-token", "--questions", str(p)])
    assert rc == 0


def test_check_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "missing.json"
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    rc = main(["check", "--skip-token", "--questions", str(missing)])
    assert rc == 2


def test_check_requires_token_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    rc = main(["check", "--questions", "data/questions.json"])
    assert rc == 2
