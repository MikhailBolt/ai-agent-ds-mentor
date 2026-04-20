import json
import random
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Question:
    id: str
    prompt: str
    answer: str
    aliases: tuple[str, ...] = ()

    def matches(self, user_answer: str) -> bool:
        a = normalize(user_answer)
        if not a:
            return False
        candidates = [normalize(self.answer)] + [normalize(x) for x in self.aliases]
        if any(a == c for c in candidates if c):
            return True
        # Длинный эталон может быть частью развёрнутого ответа пользователя.
        min_len = 12
        for c in candidates:
            if len(c) >= min_len and c in a:
                return True
        return False


def normalize(s: str) -> str:
    return " ".join((s or "").strip().casefold().split())


def load_questions(path: str) -> list[Question]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("questions json must be a list")

    out: list[Question] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        qid = str(item.get("id") or f"q{i + 1}")
        prompt = str(item.get("prompt") or "").strip()
        answer = str(item.get("answer") or "").strip()
        aliases_raw = item.get("aliases") or []
        aliases: tuple[str, ...] = (
            tuple(str(x) for x in aliases_raw) if isinstance(aliases_raw, list) else ()
        )
        if prompt and answer:
            out.append(Question(id=qid, prompt=prompt, answer=answer, aliases=aliases))
    if not out:
        raise ValueError("no valid questions loaded")
    return out


def pick_next(questions: Iterable[Question], exclude_id: str | None) -> Question:
    qs = list(questions)
    if not qs:
        raise ValueError("empty question bank")
    if exclude_id is None:
        return random.choice(qs)
    filtered = [q for q in qs if q.id != exclude_id]
    return random.choice(filtered or qs)


def find_by_id(questions: Iterable[Question], qid: str) -> Question | None:
    for q in questions:
        if q.id == qid:
            return q
    return None
