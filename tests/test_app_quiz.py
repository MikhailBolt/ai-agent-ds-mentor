from mentor import quiz as qz
from mentor.app import format_wrong_answer_message


def test_format_wrong_answer_prefers_explanation() -> None:
    q = qz.Question(
        id="1",
        prompt="p",
        answer="a",
        hint="hint text",
        explanation="because",
    )
    text = format_wrong_answer_message(q)
    assert "Пояснение: because" in text
    assert "hint text" not in text


def test_format_wrong_answer_falls_back_to_hint() -> None:
    q = qz.Question(id="1", prompt="p", answer="a", hint="hint only")
    text = format_wrong_answer_message(q)
    assert "Подсказка: hint only" in text


def test_question_counts_by_competency() -> None:
    qs = [
        qz.Question(id="1", prompt="p", answer="a", competency_id="x"),
        qz.Question(id="2", prompt="p", answer="b", competency_id="x"),
        qz.Question(id="3", prompt="p", answer="c", competency_id="y"),
    ]
    assert qz.question_counts_by_competency(qs) == {"x": 2, "y": 1}
