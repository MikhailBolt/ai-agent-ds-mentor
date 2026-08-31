"""User progress helpers (achievements, welcome) — pure logic, easy to test."""

from __future__ import annotations

import random

from mentor.competencies import Competency


def format_streak_summary(*, streak: int, best: int) -> str:
    lines = [
        "Серия верных ответов",
        f"Текущая: {streak}",
        f"Лучшая: {best}",
    ]
    if streak == 0:
        lines.append("")
        lines.append("Напиши /quiz чтобы начать серию.")
    elif streak < best:
        lines.append(f"До рекорда: {best - streak}")
    return "\n".join(lines)


def format_daily_goal_line(count: int, goal: int) -> str:
    if count >= goal:
        return f"Дневная цель: {count}/{goal} — выполнена!"
    return f"Дневная цель: {count}/{goal} ответов сегодня"


def format_today_summary(*, count: int, goal: int, streak: int) -> str:
    lines = ["Сегодня", format_daily_goal_line(count, goal)]
    if count < goal:
        lines.append(f"Осталось ответов: {goal - count}")
        lines.append("")
        lines.append("/quiz — следующий вопрос")
    else:
        lines.append("")
        lines.append("Цель выполнена! /stats — полная статистика")
    if streak > 0:
        lines.append(f"Текущая серия: {streak}")
    return "\n".join(lines)


def format_remaining_summary(
    *,
    bank_total: int,
    bank_unseen: int,
    review_count: int,
    bank_mastered: int,
) -> str:
    lines = [
        "Осталось в банке",
        f"Новых вопросов: {bank_unseen}/{bank_total}",
        f"Освоено (≥1 верный): {bank_mastered}/{bank_total}",
        f"Для повтора (/review): {review_count}",
        "",
    ]
    if bank_unseen:
        lines.append("/new — новый вопрос · /quiz — любой")
    else:
        lines.append("Все вопросы банка уже встречались — /review или /quiz")
    return "\n".join(lines)


def format_count_summary(
    *,
    correct: int,
    total: int,
    streak: int,
    best_streak: int,
    bank_unseen: int,
    review_count: int,
) -> str:
    acc = (correct / total * 100.0) if total else 0.0
    lines = [
        f"Ответов: {total} · верно: {correct} ({acc:.0f}%)",
        f"Серия: {streak} · лучшая: {best_streak}",
        f"Новых вопросов: {bank_unseen} · на повтор: {review_count}",
        "",
        "/quiz · /new · /stats",
    ]
    return "\n".join(lines)


def format_accuracy_summary(*, correct: int, total: int) -> str:
    if total == 0:
        return "Пока нет ответов. Напиши /quiz!"
    acc = correct / total * 100.0
    lines = [f"Точность: {correct}/{total} ({acc:.1f}%)"]
    if acc < 70:
        lines.append("/practice — слабая тема · /review — ошибки")
    elif acc >= 90:
        lines.append("/challenge — сложный вопрос · /stats — детали")
    else:
        lines.append("/quiz — продолжить · /stats — детали")
    return "\n".join(lines)


def format_due_summary(*, review_ids: list[str]) -> str:
    if not review_ids:
        return "Нет вопросов на повтор — /quiz или /new"
    lines = [f"На повтор: {len(review_ids)} вопросов", ""]
    for qid in review_ids[:5]:
        lines.append(f"• {qid}")
    if len(review_ids) > 5:
        lines.append(f"… и ещё {len(review_ids) - 5}")
    lines.append("")
    lines.append("/review или /fix — начать повтор")
    return "\n".join(lines)


def format_level_summary(
    *,
    total: int,
    bank_mastered: int,
    bank_total: int,
) -> str:
    if total == 0:
        return "Уровень: Новичок\nНапиши /quiz чтобы начать!"
    if bank_total and bank_mastered >= bank_total:
        level = "Мастер банка"
    elif total >= 100 or (bank_total and bank_mastered * 2 >= bank_total):
        level = "Продвинутый"
    elif total >= 30:
        level = "Практик"
    else:
        level = "Новичок"
    pct = bank_mastered / bank_total * 100.0 if bank_total else 0.0
    return (
        f"Уровень: {level}\n"
        f"Ответов: {total} · освоено банка: {bank_mastered}/{bank_total} ({pct:.0f}%)\n"
        "/stats · /map · /achievements"
    )


def format_seen_summary(*, bank_seen: int, bank_total: int) -> str:
    unseen = max(0, bank_total - bank_seen)
    pct = bank_seen / bank_total * 100.0 if bank_total else 0.0
    lines = [
        f"Встречено из банка: {bank_seen}/{bank_total} ({pct:.0f}%)",
        f"Ещё не видели: {unseen}",
        "",
    ]
    if unseen:
        lines.append("/new или /unseen — новый вопрос")
    else:
        lines.append("Весь банк просмотрен — /review")
    return "\n".join(lines)


def format_record_summary(
    *,
    correct: int,
    total: int,
    best_streak: int,
    bank_mastered: int,
    bank_total: int,
) -> str:
    acc = (correct / total * 100.0) if total else 0.0
    return (
        "Рекорды:\n"
        f"Лучшая серия: {best_streak}\n"
        f"Точность: {correct}/{total} ({acc:.0f}%)\n"
        f"Освоение банка: {bank_mastered}/{bank_total}\n"
        "/streak · /accuracy · /mastered"
    )


def format_plan_summary(
    *,
    bank_unseen: int,
    review_count: int,
    daily_count: int,
    daily_goal: int | None,
    tip_title: str | None = None,
    tip_id: str | None = None,
) -> str:
    lines = ["План на сейчас:", ""]
    step = 1
    if daily_goal and daily_count < daily_goal:
        lines.append(f"{step}. Дневная цель: ещё {daily_goal - daily_count} ответов (/quiz)")
        step += 1
    if review_count:
        lines.append(f"{step}. Повтор ошибок: {review_count} вопросов (/review)")
        step += 1
    if bank_unseen:
        lines.append(f"{step}. Новые вопросы: {bank_unseen} в банке (/new)")
    elif tip_id and tip_title:
        lines.append(f"{step}. Тренировать: {tip_title} (/topic {tip_id})")
    else:
        lines.append(f"{step}. /challenge — сложный вопрос")
    lines.append("")
    lines.append("/count — сводка · /map — прогресс")
    return "\n".join(lines)


def format_tip_summary(
    *,
    bank_unseen: int,
    review_count: int,
    daily_count: int,
    daily_goal: int | None,
    tip_title: str | None = None,
    tip_id: str | None = None,
) -> str:
    if daily_goal and daily_count < daily_goal:
        left = daily_goal - daily_count
        return f"Совет: закрой дневную цель — осталось {left} ответов.\n/quiz · /today"
    if review_count:
        return f"Совет: повтори ошибки — в очереди {review_count}.\n/review или /due"
    if bank_unseen:
        return f"Совет: открой новый вопрос — ещё {bank_unseen} не встречались.\n/new или /remain"
    if tip_id and tip_title:
        return f"Совет: потренируй тему «{tip_title}».\n/focus · /topic {tip_id}"
    return "Совет: возьми сложный вопрос.\n/challenge или /hard"


def format_session_summary(
    *,
    daily_count: int,
    daily_goal: int | None,
    streak: int,
    review_count: int,
    bank_unseen: int,
) -> str:
    lines = ["Сессия сейчас:"]
    if daily_goal:
        lines.append(format_daily_goal_line(daily_count, daily_goal))
    else:
        lines.append(f"Ответов сегодня: {daily_count}")
    lines.append(f"Текущая серия: {streak}")
    lines.append(f"На повтор: {review_count} · новых: {bank_unseen}")
    lines.append("")
    if daily_goal and daily_count < daily_goal:
        lines.append("/quiz — закрыть цель")
    elif review_count:
        lines.append("/review — разобрать ошибки")
    elif bank_unseen:
        lines.append("/new — новый вопрос")
    else:
        lines.append("/challenge — сложный вопрос")
    return "\n".join(lines)


def format_compare_summary(
    *,
    weak_title: str | None,
    weak_id: str | None,
    weak_acc: float | None,
    strong_title: str | None,
    strong_id: str | None,
    strong_acc: float | None,
) -> str:
    if weak_id is None and strong_id is None:
        return "Пока мало данных для сравнения. Напиши /quiz!"
    lines = ["Сравнение тем:", ""]
    if weak_id and weak_title is not None:
        if weak_acc is None:
            lines.append(f"Слабая/новая: {weak_title} ({weak_id}) — ещё не решал")
        else:
            lines.append(f"Слабая: {weak_title} ({weak_id}) — {weak_acc:.0f}%")
    if strong_id and strong_title is not None and strong_acc is not None:
        lines.append(f"Сильная: {strong_title} ({strong_id}) — {strong_acc:.0f}%")
    lines.append("")
    if weak_id:
        lines.append(f"/focus · /topic {weak_id}")
    else:
        lines.append("/map — карта компетенций")
    return "\n".join(lines)


def format_history_summary(rows: list[tuple[str, int, int]]) -> str:
    """rows: (question_id, attempts, correct_count)."""
    if not rows:
        return "История пуста — напиши /quiz!"
    lines = ["Последние вопросы:", ""]
    for qid, attempts, correct in rows:
        mark = "✓" if correct >= 1 else "·"
        lines.append(f"{mark} {qid} — {correct}/{attempts} верных попыток")
    lines.append("")
    lines.append("/question <id> · /last · /review")
    return "\n".join(lines)


def format_brief_summary(
    *,
    correct: int,
    total: int,
    streak: int,
    bank_unseen: int,
    review_count: int,
    daily_count: int,
    daily_goal: int | None,
) -> str:
    acc = (correct / total * 100.0) if total else 0.0
    lines = [
        f"{correct}/{total} ({acc:.0f}%) · серия {streak}",
        f"новых {bank_unseen} · повтор {review_count}",
    ]
    if daily_goal:
        lines.append(format_daily_goal_line(daily_count, daily_goal))
    lines.append("")
    if review_count:
        lines.append("/review · /warmup · /quiz")
    elif bank_unseen:
        lines.append("/warmup · /new · /quiz")
    else:
        lines.append("/quiz · /challenge")
    return "\n".join(lines)


def format_gaps_summary(
    competencies: list[Competency],
    bank_mastery: dict[str, tuple[int, int]],
    *,
    limit: int = 5,
) -> str:
    gaps: list[tuple[float, str, str, int, int]] = []
    for c in competencies:
        mastered, bank_n = bank_mastery.get(c.id, (0, 0))
        if bank_n == 0:
            continue
        ratio = mastered / bank_n
        gaps.append((ratio, c.title, c.id, mastered, bank_n))
    gaps.sort(key=lambda x: (x[0], x[3], x[2]))
    if not gaps:
        return "Нет данных по пробелам. /quiz!"
    lines = ["Пробелы по темам:", ""]
    for ratio, title, cid, mastered, bank_n in gaps[:limit]:
        if mastered == 0:
            status = "не начато"
        else:
            status = f"{mastered}/{bank_n} ({ratio * 100:.0f}%)"
        lines.append(f"• {title} ({cid}) — {status}")
    lines.append("")
    first = gaps[0]
    lines.append(f"/topic {first[2]} · /focus · /roadmap")
    return "\n".join(lines)


def format_sprint_summary(
    *,
    review_count: int,
    bank_unseen: int,
    tip_title: str | None,
    tip_id: str | None,
) -> str:
    if review_count:
        return f"Спринт: повтор ошибок ({review_count}).\n/review или /fix"
    if bank_unseen:
        return f"Спринт: новые вопросы ({bank_unseen}).\n/new или /warmup"
    if tip_id and tip_title:
        return f"Спринт: тема «{tip_title}».\n/topic {tip_id} · /focus"
    return "Спринт: сложный вопрос.\n/challenge или /hard"


def format_done_summary(
    *,
    daily_count: int,
    daily_goal: int | None,
    streak: int,
    review_count: int,
    bank_unseen: int,
) -> str:
    lines = ["Итог дня:"]
    if daily_goal:
        lines.append(format_daily_goal_line(daily_count, daily_goal))
        if daily_count >= daily_goal:
            lines.append("Отличная работа — цель закрыта!")
        else:
            lines.append(f"До цели: {daily_goal - daily_count}")
    else:
        lines.append(f"Ответов сегодня: {daily_count}")
    lines.append(f"Серия: {streak}")
    lines.append("")
    if daily_goal and daily_count < daily_goal:
        lines.append("/quiz — добить цель")
    elif review_count:
        lines.append(f"/review — ещё {review_count} на повтор")
    elif bank_unseen:
        lines.append(f"/new — ещё {bank_unseen} новых")
    else:
        lines.append("/challenge · /stats")
    return "\n".join(lines)


def format_balance_summary(
    *,
    bank_by_diff: dict[int, int],
    seen_by_diff: dict[int, int],
) -> str:
    stars = {1: "★☆☆", 2: "★★☆", 3: "★★★"}
    lines = ["Баланс по сложности:", ""]
    for level in (1, 2, 3):
        bank_n = bank_by_diff.get(level, 0)
        seen_n = seen_by_diff.get(level, 0)
        if bank_n == 0:
            continue
        lines.append(f"• {stars[level]} — встречено {seen_n}/{bank_n}")
    lines.append("")
    lines.append("/easy · /medium · /hard · /warmup")
    return "\n".join(lines)


def format_nextup_summary(
    *,
    bank_unseen: int,
    review_count: int,
    daily_count: int,
    daily_goal: int | None,
    tip_id: str | None = None,
) -> str:
    if daily_goal and daily_count < daily_goal:
        left = daily_goal - daily_count
        return f"Следующий шаг: закрыть цель ({left}) — /quiz или /pace"
    if review_count:
        return f"Следующий шаг: /review ({review_count} ошибок)"
    if bank_unseen:
        return f"Следующий шаг: /new или /grind ({bank_unseen} новых)"
    if tip_id:
        return f"Следующий шаг: /topic {tip_id} · /focus"
    return "Следующий шаг: /challenge или /hard"


def format_strengths_summary(
    competencies: list[Competency],
    comp_stats: dict[str, tuple[int, int]],
    *,
    min_attempts: int = 2,
    limit: int = 5,
) -> str:
    ranked: list[tuple[float, str, str, int, int]] = []
    for c in competencies:
        correct, total = comp_stats.get(c.id, (0, 0))
        if total < min_attempts:
            continue
        acc = correct / total * 100.0
        ranked.append((acc, c.title, c.id, correct, total))
    ranked.sort(key=lambda x: (-x[0], -x[4], x[2]))
    if not ranked:
        return "Пока мало данных — решай /quiz по разным темам!"
    lines = ["Сильные темы:", ""]
    for acc, title, cid, correct, total in ranked[:limit]:
        lines.append(f"• {title} ({cid}) — {acc:.0f}% ({correct}/{total})")
    lines.append("")
    lines.append("/compare · /challenge · /deep")
    return "\n".join(lines)


def format_ratio_summary(
    competencies: list[Competency],
    comp_stats: dict[str, tuple[int, int]],
) -> str:
    lines = ["Точность по темам:", ""]
    for c in competencies:
        correct, total = comp_stats.get(c.id, (0, 0))
        if total == 0:
            lines.append(f"• {c.title} ({c.id}) — —")
        else:
            acc = correct / total * 100.0
            lines.append(f"• {c.title} ({c.id}) — {acc:.0f}% ({correct}/{total})")
    lines.append("")
    lines.append("/focus · /weaklist · /strengths")
    return "\n".join(lines)


def format_weaklist_summary(
    competencies: list[Competency],
    comp_stats: dict[str, tuple[int, int]],
    *,
    limit: int = 5,
) -> str:
    unseen: list[tuple[str, str]] = []
    started: list[tuple[float, str, str, int, int]] = []
    for c in competencies:
        correct, total = comp_stats.get(c.id, (0, 0))
        if total == 0:
            unseen.append((c.title, c.id))
        else:
            acc = correct / total * 100.0
            started.append((acc, c.title, c.id, correct, total))
    started.sort(key=lambda x: (x[0], x[4], x[2]))
    if not unseen and not started:
        return "Нет данных — напиши /quiz!"
    lines = ["Слабые темы:", ""]
    for title, cid in unseen[:limit]:
        lines.append(f"• {title} ({cid}) — не начато")
    remaining = max(0, limit - len(unseen[:limit]))
    for acc, title, cid, correct, total in started[:remaining]:
        lines.append(f"• {title} ({cid}) — {acc:.0f}% ({correct}/{total})")
    lines.append("")
    if unseen:
        lines.append(f"/topic {unseen[0][1]} · /focus")
    elif started:
        lines.append(f"/topic {started[0][2]} · /practice")
    else:
        lines.append("/gaps · /roadmap")
    return "\n".join(lines)


def format_momentum_summary(
    *,
    streak: int,
    daily_count: int,
    daily_goal: int | None,
    recent_rows: list[tuple[str, int, int]],
) -> str:
    lines = ["Импульс:", ""]
    if daily_goal:
        lines.append(format_daily_goal_line(daily_count, daily_goal))
    else:
        lines.append(f"Ответов сегодня: {daily_count}")
    lines.append(f"Серия: {streak}")
    if recent_rows:
        sample = recent_rows[:5]
        hits = sum(1 for _, _, ok in sample if ok >= 1)
        marks = "".join("✓" if ok >= 1 else "·" for _, _, ok in sample)
        lines.append(f"Последние {len(sample)}: {marks} ({hits} с верным)")
    lines.append("")
    if streak >= 5:
        lines.append("Хороший ритм — /challenge · /deep")
    elif daily_goal and daily_count < daily_goal:
        lines.append("/quiz — продолжить цель")
    else:
        lines.append("/nextup · /sprint")
    return "\n".join(lines)


def format_coverage_summary(
    competencies: list[Competency],
    bank_seen: dict[str, tuple[int, int]],
    bank_mastery: dict[str, tuple[int, int]],
) -> str:
    lines = ["Покрытие банка:", ""]
    for c in competencies:
        seen_n, bank_n = bank_seen.get(c.id, (0, 0))
        mastered_n, _ = bank_mastery.get(c.id, (0, 0))
        if bank_n == 0:
            continue
        lines.append(
            f"• {c.title} ({c.id}) — встречено {seen_n}/{bank_n}, освоено {mastered_n}/{bank_n}"
        )
    if len(lines) == 2:
        return "Нет данных по банку. /quiz!"
    lines.append("")
    lines.append("/gaps · /probe · /remain")
    return "\n".join(lines)


def format_outlook_summary(
    *,
    daily_count: int,
    daily_goal: int | None,
    review_count: int,
    bank_unseen: int,
    lowest_title: str | None = None,
    lowest_id: str | None = None,
    lowest_seen: int = 0,
    lowest_bank: int = 0,
) -> str:
    lines = ["Обзор тренировки:", ""]
    if daily_goal:
        lines.append(format_daily_goal_line(daily_count, daily_goal))
    else:
        lines.append(f"Ответов сегодня: {daily_count}")
    lines.append(f"На повтор: {review_count} · новых: {bank_unseen}")
    if lowest_id and lowest_title and lowest_bank:
        lines.append(f"Слабое покрытие: {lowest_title} ({lowest_id}) — {lowest_seen}/{lowest_bank}")
    lines.append("")
    if daily_goal and daily_count < daily_goal:
        lines.append("/quiz · /fill")
    elif review_count:
        lines.append("/review · /spot")
    elif bank_unseen:
        lines.append("/fill · /probe · /new")
    else:
        lines.append("/challenge · /deep")
    return "\n".join(lines)


def suggest_lowest_coverage(
    competencies: list[Competency],
    bank_seen: dict[str, tuple[int, int]],
) -> tuple[Competency, int, int] | None:
    best: tuple[Competency, int, int] | None = None
    best_ratio = 2.0
    for c in competencies:
        seen_n, bank_n = bank_seen.get(c.id, (0, 0))
        if bank_n == 0:
            continue
        ratio = seen_n / bank_n
        if (
            best is None
            or ratio < best_ratio
            or (ratio == best_ratio and bank_n - seen_n > best[2] - best[1])
        ):
            best_ratio = ratio
            best = (c, seen_n, bank_n)
    return best


def format_digest_summary(
    *,
    correct: int,
    total: int,
    streak: int,
    daily_count: int,
    daily_goal: int | None,
    review_count: int,
    bank_unseen: int,
) -> str:
    acc = (correct / total * 100.0) if total else 0.0
    lines = [
        "Дайджест:",
        f"{correct}/{total} ({acc:.0f}%) · серия {streak}",
    ]
    if daily_goal:
        lines.append(format_daily_goal_line(daily_count, daily_goal))
    else:
        lines.append(f"Сегодня: {daily_count}")
    lines.append(f"Повтор: {review_count} · новых: {bank_unseen}")
    lines.append("")
    if review_count:
        lines.append("/review · /spot · /rotate")
    elif daily_goal and daily_count < daily_goal:
        lines.append("/quiz · /rotate")
    elif bank_unseen:
        lines.append("/fill · /new · /rotate")
    else:
        lines.append("/challenge · /deep")
    return "\n".join(lines)


def next_rotate_competency(
    competencies: list[Competency],
    current_id: str | None,
) -> Competency | None:
    if not competencies:
        return None
    if not current_id:
        return competencies[0]
    ids = [c.id for c in competencies]
    try:
        idx = ids.index(current_id)
    except ValueError:
        return competencies[0]
    return competencies[(idx + 1) % len(competencies)]


def format_delta_summary(
    *,
    daily_count: int,
    daily_goal: int | None,
    review_count: int,
    bank_unseen: int,
    bank_mastered: int,
    bank_total: int,
) -> str:
    lines = ["Осталось:", ""]
    if daily_goal:
        left = max(0, daily_goal - daily_count)
        if left:
            lines.append(f"• до цели дня: {left}")
        else:
            lines.append("• дневная цель закрыта")
    lines.append(f"• на повтор: {review_count}")
    lines.append(f"• новых в банке: {bank_unseen}")
    if bank_total:
        lines.append(f"• неосвоено: {max(0, bank_total - bank_mastered)}/{bank_total}")
    lines.append("")
    if daily_goal and daily_count < daily_goal:
        lines.append("/quiz · /anchor")
    elif review_count:
        lines.append("/review · /spot")
    elif bank_unseen:
        lines.append("/new · /fill · /anchor")
    else:
        lines.append("/challenge · /deep")
    return "\n".join(lines)


def format_checkpoint_summary(
    *,
    correct: int,
    total: int,
    streak: int,
    daily_count: int,
    daily_goal: int | None,
    review_count: int,
    bank_unseen: int,
    tip_title: str | None = None,
    tip_id: str | None = None,
) -> str:
    acc = (correct / total * 100.0) if total else 0.0
    lines = [
        "Чекпоинт:",
        f"{correct}/{total} ({acc:.0f}%) · серия {streak}",
    ]
    if daily_goal:
        lines.append(format_daily_goal_line(daily_count, daily_goal))
    else:
        lines.append(f"Сегодня: {daily_count}")
    lines.append(f"Повтор {review_count} · новых {bank_unseen}")
    if tip_id and tip_title:
        lines.append(f"Фокус: {tip_title} ({tip_id})")
    lines.append("")
    if review_count:
        lines.append("/review · /switch")
    elif daily_goal and daily_count < daily_goal:
        lines.append("/quiz · /anchor")
    elif bank_unseen:
        lines.append("/switch · /fill · /new")
    else:
        lines.append("/challenge · /deep")
    return "\n".join(lines)


def suggest_switch_competency(
    competencies: list[Competency],
    current_id: str | None,
    comp_stats: dict[str, tuple[int, int]],
) -> Competency | None:
    candidates = [c for c in competencies if c.id != current_id] or list(competencies)
    if not candidates:
        return None
    unseen = [c for c in candidates if comp_stats.get(c.id, (0, 0))[1] == 0]
    if unseen:
        return unseen[0]
    weakest: Competency | None = None
    worst = 2.0
    for c in candidates:
        ok, tot = comp_stats.get(c.id, (0, 0))
        if tot == 0:
            continue
        acc = ok / tot
        if acc < worst:
            worst = acc
            weakest = c
    return weakest or candidates[0]


def format_lap_summary(
    *,
    daily_count: int,
    daily_goal: int | None,
    streak: int,
    review_count: int,
    bank_unseen: int,
) -> str:
    lines = ["Круг тренировки:", ""]
    if daily_goal:
        lines.append(format_daily_goal_line(daily_count, daily_goal))
    else:
        lines.append(f"Сегодня: {daily_count}")
    lines.append(f"Серия: {streak}")
    lines.append(f"Повтор {review_count} · новых {bank_unseen}")
    lines.append("")
    if daily_goal and daily_count < daily_goal:
        lines.append("/quiz · /climb")
    elif review_count:
        lines.append("/review · /spot")
    elif bank_unseen:
        lines.append("/climb · /new · /fill")
    else:
        lines.append("/challenge · /deep")
    return "\n".join(lines)


def next_climb_difficulty(current: int | None) -> int:
    if current is None or current < 1:
        return 1
    return min(3, current + 1)


def next_ease_difficulty(current: int | None) -> int:
    if current is None or current < 1:
        return 1
    return max(1, current - 1)


def format_radar_summary(
    *,
    review_count: int,
    bank_unseen: int,
    weak_title: str | None = None,
    weak_id: str | None = None,
    lowest_title: str | None = None,
    lowest_id: str | None = None,
    lowest_seen: int = 0,
    lowest_bank: int = 0,
) -> str:
    lines = ["Радар:", ""]
    lines.append(f"Повтор: {review_count} · новых: {bank_unseen}")
    if weak_id and weak_title:
        lines.append(f"Слабая тема: {weak_title} ({weak_id})")
    if lowest_id and lowest_title and lowest_bank:
        lines.append(f"Слабое покрытие: {lowest_title} ({lowest_id}) — {lowest_seen}/{lowest_bank}")
    lines.append("")
    if review_count:
        lines.append("/review · /spot")
    elif weak_id:
        lines.append(f"/topic {weak_id} · /focus · /fill")
    elif bank_unseen:
        lines.append("/new · /probe · /fill")
    else:
        lines.append("/challenge · /climb")
    return "\n".join(lines)


def hold_difficulty(current: int | None) -> int:
    if current is None or current < 1:
        return 2
    return max(1, min(3, current))


def format_signal_summary(
    *,
    streak: int,
    daily_count: int,
    daily_goal: int | None,
    review_count: int,
    bank_unseen: int,
) -> str:
    if daily_goal and daily_count < daily_goal:
        left = daily_goal - daily_count
        return f"Сигнал: серия {streak} · до цели {left} — /quiz"
    if review_count:
        return f"Сигнал: серия {streak} · повтор {review_count} — /review"
    if bank_unseen:
        return f"Сигнал: серия {streak} · новых {bank_unseen} — /hold или /new"
    return f"Сигнал: серия {streak} · банк закрыт — /challenge"


def format_gauge_summary(
    *,
    correct: int,
    total: int,
    bank_mastered: int,
    bank_total: int,
) -> str:
    acc = (correct / total * 100.0) if total else 0.0
    bank_pct = (bank_mastered / bank_total * 100.0) if bank_total else 0.0
    if total == 0:
        level = "Новичок"
    elif bank_total and bank_mastered >= bank_total:
        level = "Мастер"
    elif total >= 100 or (bank_total and bank_mastered * 2 >= bank_total):
        level = "Продвинутый"
    elif total >= 30:
        level = "Практик"
    else:
        level = "Новичок"
    return f"Шкала: {level} · {acc:.0f}% · банк {bank_pct:.0f}%\n/level · /stats · /signal"


def pick_drift_difficulty(
    current: int | None,
    *,
    rng: random.Random | None = None,
) -> int:
    r = rng or random
    options = [d for d in (1, 2, 3) if d != current]
    if not options:
        return 2
    return r.choice(options)


def collect_achievement_labels(
    *,
    total: int,
    correct: int,
    best_streak: int,
    bank_total: int,
    bank_mastered: int,
    daily_count: int = 0,
    daily_goal: int | None = None,
    bank_mastery: dict[str, tuple[int, int]] | None = None,
    competency_titles: dict[str, str] | None = None,
    comp_stats: dict[str, tuple[int, int]] | None = None,
    all_competency_ids: set[str] | None = None,
    bank_seen: int = 0,
) -> list[str]:
    labels: list[str] = []
    if total >= 1:
        labels.append("Первый ответ")
    if total >= 100:
        labels.append("100 ответов")
    if total >= 200:
        labels.append("200 ответов")
    if total >= 300:
        labels.append("300 ответов")
    if total >= 400:
        labels.append("400 ответов")
    if total >= 500:
        labels.append("500 ответов")
    if total >= 600:
        labels.append("600 ответов")
    if total >= 700:
        labels.append("700 ответов")
    if total >= 800:
        labels.append("800 ответов")
    if total >= 900:
        labels.append("900 ответов")
    if total >= 1000:
        labels.append("1000 ответов")
    if total >= 1100:
        labels.append("1100 ответов")
    if total >= 1200:
        labels.append("1200 ответов")
    if total >= 1300:
        labels.append("1300 ответов")
    if correct >= 5:
        labels.append("5 верных ответов")
    if correct >= 10:
        labels.append("10 верных ответов")
    if correct >= 20:
        labels.append("20 верных ответов")
    if correct >= 30:
        labels.append("30 верных ответов")
    if correct >= 40:
        labels.append("40 верных ответов")
    if correct >= 50:
        labels.append("50 верных ответов")
    if correct >= 60:
        labels.append("60 верных ответов")
    if correct >= 70:
        labels.append("70 верных ответов")
    if correct >= 80:
        labels.append("80 верных ответов")
    if correct >= 90:
        labels.append("90 верных ответов")
    if correct >= 100:
        labels.append("100 верных ответов")
    if correct >= 110:
        labels.append("110 верных ответов")
    if correct >= 120:
        labels.append("120 верных ответов")
    if correct >= 130:
        labels.append("130 верных ответов")
    if correct >= 140:
        labels.append("140 верных ответов")
    if correct >= 150:
        labels.append("150 верных ответов")
    if correct >= 160:
        labels.append("160 верных ответов")
    if correct >= 170:
        labels.append("170 верных ответов")
    if correct >= 180:
        labels.append("180 верных ответов")
    if best_streak >= 5:
        labels.append("Серия 5+")
    if best_streak >= 10:
        labels.append("Серия 10+")
    if best_streak >= 15:
        labels.append("Серия 15+")
    if best_streak >= 20:
        labels.append("Серия 20+")
    if best_streak >= 25:
        labels.append("Серия 25+")
    if best_streak >= 30:
        labels.append("Серия 30+")
    if best_streak >= 35:
        labels.append("Серия 35+")
    if best_streak >= 40:
        labels.append("Серия 40+")
    if best_streak >= 45:
        labels.append("Серия 45+")
    if best_streak >= 50:
        labels.append("Серия 50+")
    if best_streak >= 55:
        labels.append("Серия 55+")
    if best_streak >= 60:
        labels.append("Серия 60+")
    if best_streak >= 65:
        labels.append("Серия 65+")
    if best_streak >= 70:
        labels.append("Серия 70+")
    if best_streak >= 75:
        labels.append("Серия 75+")
    if total >= 10 and correct / total >= 0.7:
        labels.append("Точность 70%+")
    if total >= 10 and correct / total >= 0.8:
        labels.append("Точность 80%+")
    if total >= 20 and correct / total >= 0.9:
        labels.append("Точность 90%+")
    if bank_total > 0 and bank_mastered >= bank_total:
        labels.append("Весь банк освоен")
    elif bank_total > 0 and bank_mastered * 4 >= bank_total * 3:
        labels.append("75% банка")
    elif bank_total > 0 and bank_mastered * 2 >= bank_total:
        labels.append("Половина банка")
    elif bank_total > 0 and bank_mastered * 4 >= bank_total:
        labels.append("25% банка")
    if bank_total > 0 and bank_seen * 10 >= bank_total * 9:
        labels.append("90% банка встречено")
    elif bank_total > 0 and bank_seen * 2 >= bank_total:
        labels.append("Половина банка встречена")
    if daily_goal and daily_count >= daily_goal:
        labels.append("Дневная цель")
    if all_competency_ids and comp_stats:
        if all(comp_stats.get(cid, (0, 0))[1] > 0 for cid in all_competency_ids):
            labels.append("Все темы начаты")
    if bank_mastery and competency_titles:
        for cid, (mastered, total) in bank_mastery.items():
            if total > 0 and mastered >= total:
                title = competency_titles.get(cid, cid)
                labels.append(f"Освоена тема: {title}")
    return labels


def format_achievements_text(labels: list[str]) -> str:
    if not labels:
        return "Достижения:\nПока нет — напиши /quiz!"
    lines = ["Достижения:"]
    lines.extend(f"• {label}" for label in labels)
    return "\n".join(lines)


def format_start_welcome(
    *,
    total: int,
    streak: int,
    bank_mastered: int,
    bank_total: int,
    tip: Competency | None,
    daily_count: int = 0,
    daily_goal: int | None = None,
) -> str:
    if total == 0:
        return (
            "Привет! Я AI DS Mentor — квиз по Data Science.\n\n"
            "Начни с /quiz или /practice (слабая/новая тема).\n"
            "/map — карта компетенций · /topics — id тем · /help — все команды"
        )

    lines = [
        "С возвращением!",
        f"Ответов: {total} · серия: {streak}",
    ]
    if bank_total:
        lines.append(f"Освоено вопросов банка: {bank_mastered}/{bank_total}")
    if daily_goal:
        lines.append(format_daily_goal_line(daily_count, daily_goal))
    if tip is not None:
        lines.append(f"Сейчас полезно: /practice или /quiz {tip.id}")
    lines.append("")
    lines.append("/next — новый вопрос · /stats — прогресс · /plan — что дальше")
    return "\n".join(lines)


def format_progress_export(
    *,
    version: str,
    correct: int,
    total: int,
    streak: int,
    best_streak: int,
    bank_total: int,
    bank_seen: int,
    bank_mastered: int,
    review_count: int,
    daily_count: int,
    daily_goal: int | None,
    competencies: list[Competency],
    comp_stats: dict[str, tuple[int, int]],
    achievements: list[str],
) -> str:
    acc = (correct / total * 100.0) if total else 0.0
    lines = [
        f"Отчёт AI DS Mentor v{version}",
        "",
        f"Ответов: {total} · верно: {correct} ({acc:.1f}%)",
        f"Серия: {streak} · лучшая: {best_streak}",
        f"Банк: встречено {bank_seen}/{bank_total}, освоено {bank_mastered}/{bank_total}",
        f"Не встречалось: {max(0, bank_total - bank_seen)} вопросов",
        f"Вопросов с ошибками для /review: {review_count}",
    ]
    if daily_goal:
        lines.append(format_daily_goal_line(daily_count, daily_goal))
    if achievements:
        lines.append("")
        lines.append("Достижения: " + ", ".join(achievements))
    lines.append("")
    lines.append("По темам:")
    for c in competencies:
        c_ok, c_tot = comp_stats.get(c.id, (0, 0))
        if c_tot == 0:
            lines.append(f"• {c.title} ({c.id}) — ещё не решал")
        else:
            c_acc = c_ok / c_tot * 100.0
            lines.append(f"• {c.title} ({c.id}) — {c_ok}/{c_tot} ({c_acc:.0f}%)")
    return "\n".join(lines)


def format_mistakes_summary(
    rows: list[tuple[str, int, int]],
    *,
    limit: int = 8,
) -> str:
    """rows: (question_id, wrong_count, total_attempts)."""
    if not rows:
        return "Ошибок пока нет — отлично!\nНапиши /quiz или /new для новых вопросов."
    lines = [f"Вопросы с ошибками ({len(rows)}):", ""]
    for qid, wrong, attempts in rows[:limit]:
        lines.append(f"• {qid} — {wrong} ошибок из {attempts} попыток")
    if len(rows) > limit:
        lines.append(f"… и ещё {len(rows) - limit}")
    lines.append("")
    lines.append("/review — повторить · /question <id> — открыть вопрос")
    return "\n".join(lines)
