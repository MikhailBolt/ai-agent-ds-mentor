import json
import random
import re
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path


@dataclass(frozen=True)
class Question:
    id: str
    prompt: str
    answer: str
    aliases: tuple[str, ...] = ()
    competency_id: str | None = None
    difficulty: int = 1
    hint: str | None = None

    def matches(self, user_answer: str) -> bool:
        a = normalize(user_answer)
        if not a:
            return False
        candidates = [normalize(self.answer)] + [normalize(x) for x in self.aliases]
        if any(a == c for c in candidates if c):
            return True
        min_len = 12
        for c in candidates:
            if len(c) >= min_len and c in a:
                return True
        return False


def normalize(s: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation (keeps letters and digits, all scripts)."""
    t = (s or "").strip().casefold()
    t = re.sub(r"[^\w\s]+", " ", t, flags=re.UNICODE)
    return " ".join(t.split())


def default_questions_path() -> str:
    return str(resources.files("mentor.data").joinpath("questions.json"))


def load_questions(
    path: str,
    *,
    valid_competency_ids: set[str] | None = None,
) -> list[Question]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("questions json must be a list")

    out: list[Question] = []
    seen: set[str] = set()
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
        comp_raw = item.get("competency_id")
        competency_id = str(comp_raw).strip() if comp_raw else None
        if competency_id == "":
            competency_id = None
        if competency_id and valid_competency_ids is not None:
            if competency_id not in valid_competency_ids:
                raise ValueError(f"unknown competency_id {competency_id!r} in question {qid}")

        diff_raw = item.get("difficulty", 1)
        try:
            difficulty = max(1, min(3, int(diff_raw)))
        except (TypeError, ValueError):
            difficulty = 1

        hint_raw = item.get("hint")
        hint = str(hint_raw).strip() if hint_raw else None
        if hint == "":
            hint = None

        if prompt and answer:
            if qid in seen:
                raise ValueError(f"duplicate question id: {qid}")
            seen.add(qid)
            out.append(
                Question(
                    id=qid,
                    prompt=prompt,
                    answer=answer,
                    aliases=aliases,
                    competency_id=competency_id,
                    difficulty=difficulty,
                    hint=hint,
                )
            )
    if not out:
        raise ValueError("no valid questions loaded")
    return out


def pick_next(
    questions: Iterable[Question],
    exclude_id: str | None,
    *,
    competency_filter: str | None = None,
    competency_weights: dict[str, float] | None = None,
) -> Question:
    qs = list(questions)
    if competency_filter is not None:
        qs = [q for q in qs if q.competency_id == competency_filter]
    if exclude_id is not None:
        qs = [q for q in qs if q.id != exclude_id]
    if not qs:
        raise ValueError("no questions available for selection")

    if competency_weights:
        weights: list[float] = []
        for q in qs:
            cid = q.competency_id or ""
            weights.append(max(0.1, competency_weights.get(cid, 1.0)))
        return random.choices(qs, weights=weights, k=1)[0]

    return random.choice(qs)


def find_by_id(questions: Iterable[Question], qid: str) -> Question | None:
    for q in questions:
        if q.id == qid:
            return q
    return None


def competency_weights_for_practice(
    stats: dict[str, tuple[int, int]],
    competency_ids: Iterable[str],
) -> dict[str, float]:
    """Higher weight = more likely to be quizzed (weak or unseen competencies)."""
    weights: dict[str, float] = {}
    for cid in competency_ids:
        correct, total = stats.get(cid, (0, 0))
        if total == 0:
            weights[cid] = 3.0
        else:
            acc = correct / total
            weights[cid] = 1.0 + 2.0 * (1.0 - acc)
    return weights
