from mentor import progress as prog
from mentor.competencies import Competency


def test_collect_achievement_labels_empty() -> None:
    assert (
        prog.collect_achievement_labels(
            total=0,
            correct=0,
            best_streak=0,
            bank_total=10,
            bank_mastered=0,
        )
        == []
    )


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


def test_hundred_answers_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=100,
        correct=70,
        best_streak=5,
        bank_total=50,
        bank_mastered=20,
    )
    assert "100 ответов" in labels


def test_format_remaining_summary() -> None:
    text = prog.format_remaining_summary(
        bank_total=48,
        bank_unseen=10,
        review_count=3,
        bank_mastered=20,
    )
    assert "Новых вопросов: 10/48" in text
    assert "/new" in text
    done = prog.format_remaining_summary(
        bank_total=10,
        bank_unseen=0,
        review_count=1,
        bank_mastered=10,
    )
    assert "встречались" in done


def test_all_topics_started_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=20,
        correct=15,
        best_streak=3,
        bank_total=30,
        bank_mastered=10,
        comp_stats={
            "a": (2, 3),
            "b": (1, 2),
        },
        all_competency_ids={"a", "b"},
    )
    assert "Все темы начаты" in labels


def test_fifty_correct_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=60,
        correct=50,
        best_streak=5,
        bank_total=30,
        bank_mastered=10,
    )
    assert "50 верных ответов" in labels


def test_format_accuracy_summary() -> None:
    empty = prog.format_accuracy_summary(correct=0, total=0)
    assert "Пока нет ответов" in empty
    text = prog.format_accuracy_summary(correct=18, total=20)
    assert "90.0%" in text
    assert "/challenge" in text


def test_format_due_summary() -> None:
    empty = prog.format_due_summary(review_ids=[])
    assert "Нет вопросов" in empty
    text = prog.format_due_summary(review_ids=["ml-001", "ml-002"])
    assert "2 вопросов" in text
    assert "/fix" in text


def test_accuracy_90_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=20,
        correct=18,
        best_streak=3,
        bank_total=30,
        bank_mastered=10,
    )
    assert "Точность 90%+" in labels


def test_format_count_summary() -> None:
    text = prog.format_count_summary(
        correct=8,
        total=10,
        streak=3,
        best_streak=5,
        bank_unseen=12,
        review_count=2,
    )
    assert "80%" in text
    assert "Новых вопросов: 12" in text


def test_streak_20_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=30,
        correct=25,
        best_streak=20,
        bank_total=50,
        bank_mastered=10,
    )
    assert "Серия 20+" in labels


def test_format_today_summary() -> None:
    text = prog.format_today_summary(count=2, goal=5, streak=3)
    assert "Осталось ответов: 3" in text
    assert "Текущая серия: 3" in text
    done = prog.format_today_summary(count=5, goal=5, streak=0)
    assert "выполнена" in done


def test_format_streak_summary() -> None:
    text = prog.format_streak_summary(streak=3, best=7)
    assert "Текущая: 3" in text
    assert "До рекорда: 4" in text


def test_format_mistakes_summary_empty() -> None:
    text = prog.format_mistakes_summary([])
    assert "Ошибок пока нет" in text


def test_format_mistakes_summary_with_rows() -> None:
    text = prog.format_mistakes_summary([("ml-001", 2, 3)])
    assert "ml-001" in text
    assert "/review" in text


def test_accuracy_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=10,
        correct=8,
        best_streak=2,
        bank_total=20,
        bank_mastered=5,
    )
    assert "Точность 80%+" in labels


def test_format_progress_export() -> None:
    comp = Competency(id="a", title="A", description="")
    text = prog.format_progress_export(
        version="0.4.8",
        correct=3,
        total=5,
        streak=1,
        best_streak=2,
        bank_total=10,
        bank_seen=4,
        bank_mastered=2,
        review_count=1,
        daily_count=2,
        daily_goal=5,
        competencies=[comp],
        comp_stats={"a": (2, 3)},
        achievements=["Первый ответ"],
    )
    assert "Отчёт AI DS Mentor" in text
    assert "Не встречалось" in text
    assert "Первый ответ" in text


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


def test_competency_topic_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=5,
        correct=4,
        best_streak=2,
        bank_total=4,
        bank_mastered=2,
        bank_mastery={"ml-metrics": (2, 2), "stats-basics": (1, 2)},
        competency_titles={"ml-metrics": "Метрики", "stats-basics": "Статистика"},
    )
    assert "Освоена тема: Метрики" in labels
    assert "Освоена тема: Статистика" not in labels


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
