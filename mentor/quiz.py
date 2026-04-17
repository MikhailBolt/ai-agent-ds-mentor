import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


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
        if a == normalize(self.answer):
            return True
        return any(a == normalize(x) for x in self.aliases)


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
        qid = str(item.get("id") or f"q{i+1}")
        prompt = str(item.get("prompt") or "").strip()
        answer = str(item.get("answer") or "").strip()
        aliases_raw = item.get("aliases") or []
        aliases: tuple[str, ...] = tuple(str(x) for x in aliases_raw) if isinstance(aliases_raw, list) else ()
        if prompt and answer:
            out.append(Question(id=qid, prompt=prompt, answer=answer, aliases=aliases))
    if not out:
        raise ValueError("no valid questions loaded")
    return out


def pick_next(questions: Iterable[Question], exclude_id: Optional[str]) -> Question:
    qs = list(questions)
    if not qs:
        raise ValueError("empty question bank")
    if exclude_id is None:
        return random.choice(qs)
    filtered = [q for q in qs if q.id != exclude_id]
    return random.choice(filtered or qs)


def find_by_id(questions: Iterable[Question], qid: str) -> Optional[Question]:
    for q in questions:
        if q.id == qid:
            return q
    return None

