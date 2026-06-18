import json
from pathlib import Path

import pytest

from mentor import quiz as qz


def test_normalize_strips_and_casefold() -> None:
    assert qz.normalize("  Hello   World  ") == "hello world"


def test_normalize_strips_punctuation() -> None:
    assert qz.normalize("Yes!!!") == "yes"
    assert qz.normalize("переобучение, ") == "переобучение"
    assert qz.normalize("a — b") == "a b"


def test_matches_exact_and_substring() -> None:
    q = qz.Question(
        id="t1",
        prompt="p",
        answer="когда модель хорошо запоминает обучающие данные",
        aliases=(),
    )
    assert q.matches("когда модель хорошо запоминает обучающие данные")
    assert q.matches("Ответ: когда модель хорошо запоминает обучающие данные, это переобучение.")


def test_matches_word_overlap_free_form() -> None:
    q = qz.Question(
        id="t3",
        prompt="p",
        answer="когда модель хорошо запоминает обучающие данные но плохо обобщает",
        aliases=(),
    )
    loose = (
        "думаю это когда модель запоминает обучающие данные и при этом "
        "плохо обобщает на новые примеры"
    )
    assert q.matches(loose)
    assert not q.matches("ок")


def test_token_overlap_not_for_short_reference() -> None:
    assert not qz.token_overlap_match(
        qz.normalize("tp fp ratio"),
        qz.normalize("tp divided by fp"),
    )


def test_token_overlap_false_when_too_few_words() -> None:
    ref = "one two three four"
    assert not qz.token_overlap_match(qz.normalize("wrong wrong wrong"), qz.normalize(ref))


def test_matches_ignores_punctuation_on_short_answers() -> None:
    q = qz.Question(id="t2", prompt="p", answer="overfitting", aliases=("переобучение",))
    assert q.matches("Overfitting!!!")
    assert q.matches("  overfitting, ")
    assert q.matches("«Переобучение»")


def test_unseen_question_ids() -> None:
    qs = [
        qz.Question(id="a", prompt="p", answer="x"),
        qz.Question(id="b", prompt="p", answer="y"),
    ]
    assert qz.unseen_question_ids(qs, {"a"}) == {"b"}


def test_pick_next_boosts_mistake_ids() -> None:
    qs = [
        qz.Question(id="mistake", prompt="p", answer="a"),
        qz.Question(id="other", prompt="p", answer="b"),
    ]
    counts = {"mistake": 0, "other": 0}
    for _ in range(40):
        picked = qz.pick_next(qs, None, boost_ids={"mistake"})
        counts[picked.id] += 1
    assert counts["mistake"] > counts["other"]


def test_competency_mastery_counts() -> None:
    qs = [
        qz.Question(id="1", prompt="p", answer="a", competency_id="x"),
        qz.Question(id="2", prompt="p", answer="b", competency_id="x"),
        qz.Question(id="3", prompt="p", answer="c", competency_id="y"),
    ]
    counts = qz.competency_mastery_counts(qs, {"1", "3"})
    assert counts == {"x": (1, 2), "y": (1, 1)}


def test_question_counts_by_difficulty() -> None:
    qs = [
        qz.Question(id="1", prompt="p", answer="a", difficulty=1),
        qz.Question(id="2", prompt="p", answer="b", difficulty=3),
        qz.Question(id="3", prompt="p", answer="c", difficulty=3),
    ]
    assert qz.question_counts_by_difficulty(qs) == {1: 1, 3: 2}


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


def test_load_questions_with_competency_and_hint(tmp_path: Path) -> None:
    p = tmp_path / "q.json"
    p.write_text(
        json.dumps(
            [
                {
                    "id": "a",
                    "prompt": "Q?",
                    "answer": "yes",
                    "competency_id": "c1",
                    "difficulty": 2,
                    "hint": "think",
                }
            ]
        ),
        encoding="utf-8",
    )
    qs = qz.load_questions(str(p), valid_competency_ids={"c1"})
    assert qs[0].competency_id == "c1"
    assert qs[0].difficulty == 2
    assert qs[0].hint == "think"


def test_load_questions_with_explanation(tmp_path: Path) -> None:
    p = tmp_path / "q.json"
    p.write_text(
        json.dumps(
            [
                {
                    "id": "a",
                    "prompt": "Q?",
                    "answer": "yes",
                    "explanation": "because",
                }
            ]
        ),
        encoding="utf-8",
    )
    qs = qz.load_questions(str(p))
    assert qs[0].explanation == "because"


def test_load_questions_rejects_duplicate_ids(tmp_path: Path) -> None:
    p = tmp_path / "q.json"
    p.write_text(
        json.dumps(
            [
                {"id": "dup", "prompt": "Q1?", "answer": "a"},
                {"id": "dup", "prompt": "Q2?", "answer": "b"},
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as e:
        qz.load_questions(str(p))
    assert "duplicate" in str(e.value)
