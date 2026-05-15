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


def test_competency_weights_favor_weak() -> None:
    stats = {"strong": (9, 10), "weak": (1, 10)}
    weights = qz.competency_weights_for_practice(stats, ["strong", "weak"])
    assert weights["weak"] > weights["strong"]
