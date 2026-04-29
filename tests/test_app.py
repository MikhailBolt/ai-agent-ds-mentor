from mentor import db as mentor_db
from mentor.app import format_status_text


def test_format_status_text_contains_expected_fields() -> None:
    stats = mentor_db.Stats(correct=3, total=5)
    text = format_status_text(
        started_at=100.0,
        now=160.0,
        question_count=4,
        stats=stats,
    )
    assert "Статус бота:" in text
    assert "Версия:" in text
    assert "Uptime: 00:01:00" in text
    assert "Вопросов в банке: 4" in text
    assert "Твоя статистика: 3/5 (60.0%)" in text


def test_format_status_text_when_no_answers() -> None:
    stats = mentor_db.Stats(correct=0, total=0)
    text = format_status_text(
        started_at=10.0,
        now=10.0,
        question_count=2,
        stats=stats,
    )
    assert "Твоя статистика: 0/0 (0.0%)" in text
