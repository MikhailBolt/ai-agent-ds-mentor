"""Pure helpers for parsing user text (easy to unit-test, no I/O)."""

from __future__ import annotations


def command_prefix(text: str) -> str | None:
    """`/cmd` или `/cmd@BotUsername` → нормализованный префикс `/cmd` в нижнем регистре."""
    t = (text or "").strip()
    if not t.startswith("/"):
        return None
    head = t.split(maxsplit=1)[0]
    return head.split("@", 1)[0].lower()
