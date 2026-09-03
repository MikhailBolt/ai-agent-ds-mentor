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


def test_format_nextup_summary() -> None:
    daily = prog.format_nextup_summary(
        bank_unseen=10,
        review_count=2,
        daily_count=1,
        daily_goal=5,
        tip_id="ml-metrics",
    )
    assert "цель" in daily
    review = prog.format_nextup_summary(
        bank_unseen=10,
        review_count=2,
        daily_count=5,
        daily_goal=5,
    )
    assert "/review" in review


def test_sixty_correct_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=70,
        correct=60,
        best_streak=5,
        bank_total=90,
        bank_mastered=30,
    )
    assert "60 верных ответов" in labels


def test_seventy_correct_and_streak_30_achievements() -> None:
    labels = prog.collect_achievement_labels(
        total=80,
        correct=70,
        best_streak=30,
        bank_total=96,
        bank_mastered=40,
    )
    assert "70 верных ответов" in labels
    assert "Серия 30+" in labels


def test_format_strengths_summary() -> None:
    from mentor.competencies import Competency

    comps = [
        Competency(id="a", title="Alpha", description=""),
        Competency(id="b", title="Beta", description=""),
    ]
    stats = {"a": (4, 5), "b": (1, 5)}
    text = prog.format_strengths_summary(comps, stats)
    assert "Alpha" in text
    assert "80%" in text


def test_format_ratio_and_weaklist_summary() -> None:
    from mentor.competencies import Competency

    comps = [
        Competency(id="a", title="Alpha", description=""),
        Competency(id="b", title="Beta", description=""),
    ]
    stats = {"a": (2, 4), "b": (0, 0)}
    ratio = prog.format_ratio_summary(comps, stats)
    assert "50%" in ratio
    assert "— —" in ratio
    weak = prog.format_weaklist_summary(comps, stats)
    assert "не начато" in weak
    assert "20%" in weak or "50%" in weak


def test_three_hundred_and_eighty_achievements() -> None:
    labels = prog.collect_achievement_labels(
        total=300,
        correct=80,
        best_streak=10,
        bank_total=99,
        bank_mastered=50,
    )
    assert "300 ответов" in labels
    assert "80 верных ответов" in labels


def test_four_hundred_ninety_and_streak_35_achievements() -> None:
    labels = prog.collect_achievement_labels(
        total=400,
        correct=90,
        best_streak=35,
        bank_total=102,
        bank_mastered=60,
    )
    assert "400 ответов" in labels
    assert "90 верных ответов" in labels
    assert "Серия 35+" in labels


def test_format_momentum_summary() -> None:
    text = prog.format_momentum_summary(
        streak=6,
        daily_count=3,
        daily_goal=5,
        recent_rows=[("q1", 1, 1), ("q2", 2, 0), ("q3", 1, 1)],
    )
    assert "Серия: 6" in text
    assert "✓" in text
    assert "/challenge" in text


def test_format_coverage_summary() -> None:
    from mentor.competencies import Competency

    comps = [
        Competency(id="a", title="Alpha", description=""),
        Competency(id="b", title="Beta", description=""),
    ]
    text = prog.format_coverage_summary(
        comps,
        {"a": (2, 5), "b": (0, 4)},
        {"a": (1, 5), "b": (0, 4)},
    )
    assert "встречено 2/5" in text
    assert "освоено 1/5" in text
    assert "/probe" in text


def test_five_hundred_and_hundred_correct_achievements() -> None:
    labels = prog.collect_achievement_labels(
        total=500,
        correct=100,
        best_streak=10,
        bank_total=105,
        bank_mastered=70,
    )
    assert "500 ответов" in labels
    assert "100 верных ответов" in labels


def test_six_hundred_outlook_and_fill_helpers() -> None:
    from mentor.competencies import Competency

    labels = prog.collect_achievement_labels(
        total=600,
        correct=110,
        best_streak=40,
        bank_total=108,
        bank_mastered=80,
    )
    assert "600 ответов" in labels
    assert "110 верных ответов" in labels
    assert "Серия 40+" in labels

    comps = [
        Competency(id="a", title="Alpha", description=""),
        Competency(id="b", title="Beta", description=""),
    ]
    lowest = prog.suggest_lowest_coverage(comps, {"a": (4, 5), "b": (1, 5)})
    assert lowest is not None
    assert lowest[0].id == "b"
    outlook = prog.format_outlook_summary(
        daily_count=2,
        daily_goal=5,
        review_count=3,
        bank_unseen=10,
        lowest_title="Beta",
        lowest_id="b",
        lowest_seen=1,
        lowest_bank=5,
    )
    assert "Слабое покрытие" in outlook
    assert "/quiz" in outlook


def test_digest_rotate_and_700_achievements() -> None:
    from mentor.competencies import Competency

    labels = prog.collect_achievement_labels(
        total=700,
        correct=120,
        best_streak=45,
        bank_total=111,
        bank_mastered=90,
    )
    assert "700 ответов" in labels
    assert "120 верных ответов" in labels
    assert "Серия 45+" in labels

    digest = prog.format_digest_summary(
        correct=12,
        total=20,
        streak=3,
        daily_count=2,
        daily_goal=5,
        review_count=1,
        bank_unseen=8,
    )
    assert "60%" in digest
    assert "/review" in digest

    comps = [
        Competency(id="a", title="Alpha", description=""),
        Competency(id="b", title="Beta", description=""),
    ]
    assert prog.next_rotate_competency(comps, "a").id == "b"
    assert prog.next_rotate_competency(comps, "b").id == "a"
    assert prog.next_rotate_competency(comps, None).id == "a"


def test_delta_and_800_achievements() -> None:
    labels = prog.collect_achievement_labels(
        total=800,
        correct=130,
        best_streak=50,
        bank_total=114,
        bank_mastered=100,
    )
    assert "800 ответов" in labels
    assert "130 верных ответов" in labels
    assert "Серия 50+" in labels

    text = prog.format_delta_summary(
        daily_count=2,
        daily_goal=5,
        review_count=3,
        bank_unseen=12,
        bank_mastered=40,
        bank_total=114,
    )
    assert "до цели дня: 3" in text
    assert "на повтор: 3" in text
    assert "/quiz" in text


def test_checkpoint_switch_and_900_achievements() -> None:
    from mentor.competencies import Competency

    labels = prog.collect_achievement_labels(
        total=900,
        correct=140,
        best_streak=55,
        bank_total=117,
        bank_mastered=105,
    )
    assert "900 ответов" in labels
    assert "140 верных ответов" in labels
    assert "Серия 55+" in labels

    text = prog.format_checkpoint_summary(
        correct=8,
        total=10,
        streak=4,
        daily_count=2,
        daily_goal=5,
        review_count=1,
        bank_unseen=6,
        tip_title="Alpha",
        tip_id="a",
    )
    assert "80%" in text
    assert "Фокус: Alpha" in text
    assert "/review" in text

    comps = [
        Competency(id="a", title="Alpha", description=""),
        Competency(id="b", title="Beta", description=""),
        Competency(id="c", title="Gamma", description=""),
    ]
    switched = prog.suggest_switch_competency(comps, "a", {"a": (5, 5), "b": (1, 4), "c": (0, 0)})
    assert switched is not None
    assert switched.id == "c"


def test_lap_climb_and_1000_achievements() -> None:
    labels = prog.collect_achievement_labels(
        total=1000,
        correct=150,
        best_streak=60,
        bank_total=120,
        bank_mastered=110,
    )
    assert "1000 ответов" in labels
    assert "150 верных ответов" in labels
    assert "Серия 60+" in labels

    lap = prog.format_lap_summary(
        daily_count=2,
        daily_goal=5,
        streak=3,
        review_count=0,
        bank_unseen=10,
    )
    assert "Серия: 3" in lap
    assert "/quiz" in lap
    assert prog.next_climb_difficulty(None) == 1
    assert prog.next_climb_difficulty(1) == 2
    assert prog.next_climb_difficulty(2) == 3
    assert prog.next_climb_difficulty(3) == 3


def test_ease_radar_and_1100_achievements() -> None:
    labels = prog.collect_achievement_labels(
        total=1100,
        correct=160,
        best_streak=65,
        bank_total=123,
        bank_mastered=115,
    )
    assert "1100 ответов" in labels
    assert "160 верных ответов" in labels
    assert "Серия 65+" in labels

    assert prog.next_ease_difficulty(None) == 1
    assert prog.next_ease_difficulty(3) == 2
    assert prog.next_ease_difficulty(2) == 1
    assert prog.next_ease_difficulty(1) == 1

    radar = prog.format_radar_summary(
        review_count=2,
        bank_unseen=8,
        weak_title="Alpha",
        weak_id="a",
        lowest_title="Beta",
        lowest_id="b",
        lowest_seen=1,
        lowest_bank=5,
    )
    assert "Слабая тема: Alpha" in radar
    assert "/review" in radar


def test_hold_signal_and_1200_achievements() -> None:
    labels = prog.collect_achievement_labels(
        total=1200,
        correct=170,
        best_streak=70,
        bank_total=126,
        bank_mastered=120,
    )
    assert "1200 ответов" in labels
    assert "170 верных ответов" in labels
    assert "Серия 70+" in labels

    assert prog.hold_difficulty(None) == 2
    assert prog.hold_difficulty(1) == 1
    assert prog.hold_difficulty(3) == 3

    signal = prog.format_signal_summary(
        streak=4,
        daily_count=1,
        daily_goal=5,
        review_count=0,
        bank_unseen=10,
    )
    assert "до цели 4" in signal
    assert "/quiz" in signal


def test_gauge_drift_and_1300_achievements() -> None:
    import random

    labels = prog.collect_achievement_labels(
        total=1300,
        correct=180,
        best_streak=75,
        bank_total=129,
        bank_mastered=125,
    )
    assert "1300 ответов" in labels
    assert "180 верных ответов" in labels
    assert "Серия 75+" in labels

    gauge = prog.format_gauge_summary(
        correct=40,
        total=50,
        bank_mastered=60,
        bank_total=129,
    )
    assert "80%" in gauge
    assert "Шкала:" in gauge

    rng = random.Random(0)
    assert prog.pick_drift_difficulty(2, rng=rng) in {1, 3}
    assert prog.pick_drift_difficulty(1, rng=rng) in {2, 3}


def test_trail_surge_and_1400_achievements() -> None:
    labels = prog.collect_achievement_labels(
        total=1400,
        correct=190,
        best_streak=80,
        bank_total=132,
        bank_mastered=128,
    )
    assert "1400 ответов" in labels
    assert "190 верных ответов" in labels
    assert "Серия 80+" in labels

    trail = prog.format_trail_summary([("q1", 1, 1), ("q2", 2, 0)])
    assert "След (2):" in trail
    assert "q1" in trail
    assert "/history" in trail


def test_compass_steady_and_1500_achievements() -> None:
    labels = prog.collect_achievement_labels(
        total=1500,
        correct=200,
        best_streak=85,
        bank_total=135,
        bank_mastered=130,
    )
    assert "1500 ответов" in labels
    assert "200 верных ответов" in labels
    assert "Серия 85+" in labels

    compass = prog.format_compass_summary(
        review_count=0,
        bank_unseen=12,
        daily_count=0,
        daily_goal=None,
        tip_title="ML Metrics",
        tip_id="ml-metrics",
    )
    assert "Компас:" in compass
    assert "ml-metrics" in compass
    assert "/focus" in compass

    assert prog.hold_difficulty(2) == 2
    assert prog.hold_difficulty(None) == 2


def test_bearing_pivot_and_1600_achievements() -> None:
    labels = prog.collect_achievement_labels(
        total=1600,
        correct=210,
        best_streak=90,
        bank_total=138,
        bank_mastered=133,
    )
    assert "1600 ответов" in labels
    assert "210 верных ответов" in labels
    assert "Серия 90+" in labels

    bearing = prog.format_bearing_summary(
        correct=40,
        total=50,
        streak=6,
        review_count=0,
        bank_unseen=8,
    )
    assert "Курс:" in bearing
    assert "80%" in bearing
    assert "/pivot" in bearing or "/climb" in bearing

    assert prog.hold_difficulty(3) == 3


def test_format_balance_summary() -> None:
    text = prog.format_balance_summary(
        bank_by_diff={1: 10, 2: 20, 3: 5},
        seen_by_diff={1: 4, 2: 10, 3: 1},
    )
    assert "встречено 4/10" in text
    assert "/easy" in text


def test_half_bank_seen_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=30,
        correct=20,
        best_streak=3,
        bank_total=100,
        bank_mastered=10,
        bank_seen=50,
    )
    assert "Половина банка встречена" in labels
    assert "Половина банка" not in labels


def test_format_done_summary() -> None:
    text = prog.format_done_summary(
        daily_count=2,
        daily_goal=5,
        streak=3,
        review_count=1,
        bank_unseen=4,
    )
    assert "Итог дня" in text
    assert "До цели: 3" in text
    done = prog.format_done_summary(
        daily_count=5,
        daily_goal=5,
        streak=4,
        review_count=0,
        bank_unseen=2,
    )
    assert "цель закрыта" in done


def test_forty_correct_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=50,
        correct=40,
        best_streak=5,
        bank_total=80,
        bank_mastered=20,
    )
    assert "40 верных ответов" in labels


def test_format_gaps_summary() -> None:
    comps = [
        Competency(id="a", title="A", description=""),
        Competency(id="b", title="B", description=""),
    ]
    text = prog.format_gaps_summary(
        comps,
        {"a": (0, 5), "b": (4, 5)},
    )
    assert "не начато" in text
    assert "/topic a" in text


def test_format_sprint_summary() -> None:
    text = prog.format_sprint_summary(
        review_count=3,
        bank_unseen=10,
        tip_title="Метрики",
        tip_id="ml-metrics",
    )
    assert "повтор ошибок" in text
    fresh = prog.format_sprint_summary(
        review_count=0,
        bank_unseen=4,
        tip_title=None,
        tip_id=None,
    )
    assert "новые вопросы" in fresh


def test_streak_25_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=40,
        correct=30,
        best_streak=25,
        bank_total=80,
        bank_mastered=20,
    )
    assert "Серия 25+" in labels


def test_format_brief_summary() -> None:
    text = prog.format_brief_summary(
        correct=8,
        total=10,
        streak=3,
        bank_unseen=5,
        review_count=1,
        daily_count=2,
        daily_goal=5,
    )
    assert "80%" in text
    assert "новых 5" in text
    assert "/review" in text


def test_thirty_correct_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=40,
        correct=30,
        best_streak=5,
        bank_total=80,
        bank_mastered=20,
    )
    assert "30 верных ответов" in labels


def test_format_history_summary() -> None:
    empty = prog.format_history_summary([])
    assert "История пуста" in empty
    text = prog.format_history_summary([("ml-001", 2, 1), ("ml-002", 1, 0)])
    assert "ml-001" in text
    assert "/question" in text


def test_bank_seen_90_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=50,
        correct=40,
        best_streak=5,
        bank_total=100,
        bank_mastered=30,
        bank_seen=90,
    )
    assert "90% банка встречено" in labels


def test_format_session_summary() -> None:
    text = prog.format_session_summary(
        daily_count=2,
        daily_goal=5,
        streak=3,
        review_count=1,
        bank_unseen=8,
    )
    assert "Дневная цель" in text
    assert "На повтор: 1" in text
    assert "/quiz" in text


def test_format_compare_summary() -> None:
    empty = prog.format_compare_summary(
        weak_title=None,
        weak_id=None,
        weak_acc=None,
        strong_title=None,
        strong_id=None,
        strong_acc=None,
    )
    assert "мало данных" in empty
    text = prog.format_compare_summary(
        weak_title="Метрики",
        weak_id="ml-metrics",
        weak_acc=40.0,
        strong_title="Python",
        strong_id="python-ds",
        strong_acc=90.0,
    )
    assert "Слабая: Метрики" in text
    assert "Сильная: Python" in text


def test_ten_correct_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=12,
        correct=10,
        best_streak=3,
        bank_total=70,
        bank_mastered=20,
    )
    assert "10 верных ответов" in labels


def test_accuracy_70_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=10,
        correct=7,
        best_streak=2,
        bank_total=20,
        bank_mastered=5,
    )
    assert "Точность 70%+" in labels
    assert "Точность 80%+" not in labels


def test_format_tip_summary() -> None:
    text = prog.format_tip_summary(
        bank_unseen=5,
        review_count=0,
        daily_count=5,
        daily_goal=5,
    )
    assert "новый вопрос" in text
    daily = prog.format_tip_summary(
        bank_unseen=5,
        review_count=2,
        daily_count=1,
        daily_goal=5,
    )
    assert "дневную цель" in daily


def test_bank_25_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=20,
        correct=15,
        best_streak=3,
        bank_total=60,
        bank_mastered=15,
    )
    assert "25% банка" in labels


def test_format_record_summary() -> None:
    text = prog.format_record_summary(
        correct=18,
        total=20,
        best_streak=7,
        bank_mastered=30,
        bank_total=60,
    )
    assert "Лучшая серия: 7" in text
    assert "90%" in text


def test_format_plan_summary() -> None:
    text = prog.format_plan_summary(
        bank_unseen=10,
        review_count=2,
        daily_count=1,
        daily_goal=5,
        tip_title="Метрики",
        tip_id="ml-metrics",
    )
    assert "Дневная цель" in text
    assert "Повтор ошибок" in text
    assert "Новые вопросы" in text


def test_two_hundred_answers_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=200,
        correct=150,
        best_streak=10,
        bank_total=60,
        bank_mastered=40,
    )
    assert "200 ответов" in labels


def test_format_level_summary() -> None:
    newbie = prog.format_level_summary(total=0, bank_mastered=0, bank_total=60)
    assert "Новичок" in newbie
    text = prog.format_level_summary(total=35, bank_mastered=10, bank_total=60)
    assert "Практик" in text
    master = prog.format_level_summary(total=80, bank_mastered=60, bank_total=60)
    assert "Мастер банка" in master


def test_format_seen_summary() -> None:
    text = prog.format_seen_summary(bank_seen=40, bank_total=60)
    assert "40/60" in text
    assert "/new" in text
    done = prog.format_seen_summary(bank_seen=60, bank_total=60)
    assert "/review" in done


def test_bank_75_achievement() -> None:
    labels = prog.collect_achievement_labels(
        total=50,
        correct=40,
        best_streak=5,
        bank_total=60,
        bank_mastered=45,
    )
    assert "75% банка" in labels
    assert "Половина банка" not in labels


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
