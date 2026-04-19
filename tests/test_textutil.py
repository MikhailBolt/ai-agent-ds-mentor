import pytest

from mentor.textutil import command_prefix


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("/quiz", "/quiz"),
        ("/QUIZ", "/quiz"),
        ("/quiz@MyDSMentorBot", "/quiz"),
        ("/start@bot  extra", "/start"),
        ("  /help@x  ", "/help"),
        ("not a command", None),
        ("", None),
    ],
)
def test_command_prefix(raw: str, expected: str | None) -> None:
    assert command_prefix(raw) == expected
