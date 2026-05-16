import json
from pathlib import Path

import pytest

from mentor import competencies as comp
from mentor import quiz as qz


def test_load_competencies(tmp_path: Path) -> None:
    p = tmp_path / "c.json"
    p.write_text(
        json.dumps([{"id": "a", "title": "A", "description": "desc"}]),
        encoding="utf-8",
    )
    cs = comp.load_competencies(str(p))
    assert len(cs) == 1
    assert cs[0].id == "a"


def test_format_competency_map() -> None:
    competencies = [
        comp.Competency(id="x", title="Topic X", description="d"),
    ]
    text = comp.format_competency_map(competencies, {"x": (2, 4)})
    assert "Topic X" in text
    assert "2/4" in text
    assert "▓" in text


def test_questions_require_valid_competency(tmp_path: Path) -> None:
    c = tmp_path / "c.json"
    c.write_text(json.dumps([{"id": "ok", "title": "T", "description": ""}]), encoding="utf-8")
    q = tmp_path / "q.json"
    q.write_text(
        json.dumps([{"id": "q1", "prompt": "Q?", "answer": "a", "competency_id": "bad"}]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown competency_id"):
        qz.load_questions(str(q), valid_competency_ids={"ok"})


def test_pick_next_filters_competency() -> None:
    qs = [
        qz.Question(id="1", prompt="p", answer="a", competency_id="ml-metrics"),
        qz.Question(id="2", prompt="p", answer="b", competency_id="other"),
    ]
    for _ in range(20):
        picked = qz.pick_next(qs, None, competency_filter="ml-metrics")
        assert picked.competency_id == "ml-metrics"


def test_format_stats_summary() -> None:
    competencies = [
        comp.Competency(id="a", title="A", description=""),
        comp.Competency(id="b", title="B", description=""),
    ]
    text = comp.format_stats_summary(
        correct=2,
        total=4,
        streak=1,
        competencies=competencies,
        comp_stats={"a": (1, 2), "b": (0, 0)},
    )
    assert "серия" in text.lower()
    assert "A" in text
    assert "ещё не решал" in text


def test_suggest_practice_prefers_unseen() -> None:
    competencies = [
        comp.Competency(id="done", title="Done", description=""),
        comp.Competency(id="new", title="New", description=""),
    ]
    pick = comp.suggest_practice_competency(competencies, {"done": (1, 1)})
    assert pick is not None
    assert pick.id == "new"


def test_competency_weights_favor_weak() -> None:
    stats = {"strong": (9, 10), "weak": (1, 10)}
    weights = qz.competency_weights_for_practice(stats, ["strong", "weak"])
    assert weights["weak"] > weights["strong"]


def test_validate_competency_coverage() -> None:
    qs = [qz.Question(id="1", prompt="p", answer="a", competency_id="x")]
    qz.validate_competency_coverage(qs, {"x"})
    with pytest.raises(ValueError, match="no questions for competencies"):
        qz.validate_competency_coverage(qs, {"x", "y"})
