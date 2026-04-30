import pytest

from mentor.telegram import TELEGRAM_MESSAGE_LIMIT, split_message


def test_split_message_short() -> None:
    assert split_message("hi") == ["hi"]


def test_split_message_exact_limit() -> None:
    s = "a" * TELEGRAM_MESSAGE_LIMIT
    assert split_message(s) == [s]


def test_split_message_long_splits() -> None:
    s = ("a" * (TELEGRAM_MESSAGE_LIMIT - 10)) + "\n" + ("b" * (TELEGRAM_MESSAGE_LIMIT - 10))
    parts = split_message(s)
    assert len(parts) == 2
    assert all(len(p) <= TELEGRAM_MESSAGE_LIMIT for p in parts)
    # split_message may trim boundary whitespace; content should be preserved.
    assert "".join(parts).replace("\n", "") == s.replace("\n", "")


def test_split_message_limit_validation() -> None:
    with pytest.raises(ValueError):
        split_message("x", limit=0)
