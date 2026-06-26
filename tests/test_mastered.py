from mentor.competencies import Competency, format_mastered_summary, format_weaktopic_tip


def test_format_mastered_summary() -> None:
    comps = [
        Competency(id="a", title="A", description=""),
        Competency(id="b", title="B", description=""),
    ]
    text = format_mastered_summary(
        comps,
        {"a": (2, 5), "b": (0, 3)},
    )
    assert "A — 2/5" in text
    assert "Итого: 2/8" in text
    assert "/map" in text


def test_format_weaktopic_tip() -> None:
    tip = Competency(id="ml-metrics", title="Метрики", description="")
    text = format_weaktopic_tip(tip)
    assert "ml-metrics" in text
    assert "/practice" in text
    assert "тренировались" in format_weaktopic_tip(None)
