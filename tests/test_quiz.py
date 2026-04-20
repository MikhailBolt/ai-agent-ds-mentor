import json
from pathlib import Path

from mentor import quiz as qz


def test_normalize_strips_and_casefold() -> None:
    assert qz.normalize("  Hello   World  ") == "hello world"


def test_matches_exact_and_substring() -> None:
    q = qz.Question(
        id="t1",
        prompt="p",
        answer="когда модель хорошо запоминает обучающие данные",
        aliases=(),
    )
    assert q.matches("когда модель хорошо запоминает обучающие данные")
    assert q.matches("Ответ: когда модель хорошо запоминает обучающие данные, это переобучение.")


def test_load_questions_minimal(tmp_path: Path) -> None:
    p = tmp_path / "q.json"
    p.write_text(
        json.dumps([{"id": "a", "prompt": "Q?", "answer": "yes"}]),
        encoding="utf-8",
    )
    qs = qz.load_questions(str(p))
    assert len(qs) == 1
    assert qs[0].id == "a"
    assert qs[0].matches("YES")
