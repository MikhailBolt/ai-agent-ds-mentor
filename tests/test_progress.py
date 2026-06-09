from mentor import progress as prog
from mentor.competencies import Competency


def test_collect_achievement_labels_empty() -> None:
    assert prog.collect_achievement_labels(
        total=0,
        correct=0,
        best_streak=0,
        bank_total=10,
        bank_mastered=0,
    ) == []


def test_collect_achievement_labels_milestones() -> None:
    labels = prog.collect_achievement_labels(
        total=25,
        correct=20,
        best_streak=10,
        bank_total=20,
        bank_mastered=20,
    )
    assert "Первый ответ" in labels
    assert "20 верных ответов" in labels
    assert "Серия 10+" in labels
    assert "Весь банк освоен" in labels


def test_format_start_welcome_new_user() -> None:
    text = prog.format_start_welcome(
        total=0,
        streak=0,
        bank_mastered=0,
        bank_total=10,
        tip=None,
    )
    assert "Привет" in text
    assert "/quiz" in text


def test_daily_goal_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=10,
        correct=8,
        best_streak=3,
        bank_total=20,
        bank_mastered=5,
        daily_count=5,
        daily_goal=5,
    )
    assert "Дневная цель" in labels


def test_format_daily_goal_line() -> None:
    assert "выполнена" in prog.format_daily_goal_line(5, 5)
    assert "3/5" in prog.format_daily_goal_line(3, 5)


def test_format_start_welcome_returning() -> None:
    tip = Competency(id="ml-metrics", title="Метрики", description="")
    text = prog.format_start_welcome(
        total=5,
        streak=2,
        bank_mastered=3,
        bank_total=10,
        tip=tip,
    )
    assert "С возвращением" in text
    assert "ml-metrics" in text
