from __future__ import annotations

from collections.abc import Iterable

TELEGRAM_MESSAGE_LIMIT = 4096


def split_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split message into Telegram-safe chunks.

    Prefers splitting by newline boundaries, then by spaces, and only then hard-splits.
    """
    if limit <= 0:
        raise ValueError("limit must be > 0")

    t = text or ""
    if len(t) <= limit:
        return [t]

    chunks: list[str] = []
    remaining = t
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        window = remaining[:limit]
        cut = window.rfind("\n")
        if cut <= 0:
            cut = window.rfind(" ")
        if cut <= 0:
            cut = limit

        part = remaining[:cut].rstrip()
        if not part:
            part = remaining[:limit]
            cut = len(part)
        chunks.append(part)
        remaining = remaining[cut:].lstrip("\n ").lstrip()

    return chunks


def iter_chunks(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> Iterable[str]:
    yield from split_message(text, limit=limit)
