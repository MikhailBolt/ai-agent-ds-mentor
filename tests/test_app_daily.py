import pytest

from mentor.app import parse_daily_goal


def test_parse_daily_goal_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DAILY_GOAL", raising=False)
    assert parse_daily_goal() == 5


def test_parse_daily_goal_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_GOAL", "0")
    assert parse_daily_goal() is None


def test_parse_daily_goal_custom(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DAILY_GOAL", "10")
    assert parse_daily_goal() == 10
