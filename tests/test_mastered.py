from mentor.competencies import Competency, format_mastered_summary


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
