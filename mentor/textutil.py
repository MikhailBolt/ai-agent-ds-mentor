"""Pure helpers for parsing user text (easy to unit-test, no I/O)."""

from __future__ import annotations


def command_prefix(text: str) -> str | None:
    """`/cmd` или `/cmd@BotUsername` → нормализованный префикс `/cmd` в нижнем регистре."""
    t = (text or "").strip()
    if not t.startswith("/"):
        return None
    head = t.split(maxsplit=1)[0]
    return head.split("@", 1)[0].lower()


def quiz_competency_arg(text: str) -> str:
    """For `/quiz` or `/quiz@bot [id]`, return competency id or '' for any topic."""
    if command_prefix(text) != "/quiz":
        raise ValueError("not a quiz command")
    parts = (text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip().lower()
