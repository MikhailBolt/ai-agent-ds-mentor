"""Pure helpers for parsing user text (easy to unit-test, no I/O)."""

from __future__ import annotations


def command_prefix(text: str) -> str | None:
    """`/cmd` или `/cmd@BotUsername` → нормализованный префикс `/cmd` в нижнем регистре."""
    t = (text or "").strip()
    if not t.startswith("/"):
        return None
    head = t.split(maxsplit=1)[0]
    return head.split("@", 1)[0].lower()


_DIFFICULTY_WORDS: dict[str, int] = {
    "easy": 1,
    "легко": 1,
    "medium": 2,
    "средне": 2,
    "hard": 3,
    "сложно": 3,
}


def parse_quiz_args(
    text: str,
    *,
    valid_competency_ids: set[str] | None = None,
) -> tuple[str, int | None]:
    """`/quiz [topic] [1-3|easy|hard]` → competency filter and optional difficulty."""
    if command_prefix(text) != "/quiz":
        raise ValueError("not a quiz command")
    parts = (text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        return "", None

    comp = ""
    difficulty: int | None = None
    for tok in parts[1].strip().lower().split():
        if tok in _DIFFICULTY_WORDS:
            difficulty = _DIFFICULTY_WORDS[tok]
        elif tok in ("1", "2", "3"):
            difficulty = int(tok)
        elif valid_competency_ids and tok in valid_competency_ids:
            comp = tok
        elif valid_competency_ids is None:
            comp = tok
        elif not comp and difficulty is None:
            comp = tok
    return comp, difficulty


def quiz_competency_arg(text: str) -> str:
    """For `/quiz` or `/quiz@bot [id]`, return competency id or '' for any topic."""
    comp, _ = parse_quiz_args(text)
    return comp


def reset_is_confirmed(text: str) -> bool:
    if command_prefix(text) != "/reset":
        raise ValueError("not a reset command")
    parts = (text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        return False
    return parts[1].strip().lower() in {"confirm", "yes", "да"}


def parse_search_query(text: str) -> str:
    if command_prefix(text) != "/search":
        raise ValueError("not a search command")
    parts = (text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


def parse_new_topic_arg(text: str) -> str:
    """`/new` or `/new ml-metrics` → optional competency id."""
    if command_prefix(text) != "/new":
        raise ValueError("not a new command")
    parts = (text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip().lower()


def parse_topic_arg(text: str) -> str:
    """`/topic ml-metrics` → competency id."""
    if command_prefix(text) != "/topic":
        raise ValueError("not a topic command")
    parts = (text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip().lower()


def parse_question_id_arg(text: str) -> str:
    """`/question ml-001` or `/q ml-001` → question id."""
    cmd = command_prefix(text)
    if cmd not in {"/question", "/q"}:
        raise ValueError("not a question command")
    parts = (text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip().lower()
