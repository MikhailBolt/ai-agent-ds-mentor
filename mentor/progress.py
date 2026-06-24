"""User progress helpers (achievements, welcome) — pure logic, easy to test."""

from __future__ import annotations

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
) -> list[str]:
    labels: list[str] = []
    if total >= 1:
        labels.append("Первый ответ")
    if correct >= 5:
        labels.append("5 верных ответов")
    if correct >= 20:
        labels.append("20 верных ответов")
    if correct >= 50:
        labels.append("50 верных ответов")
    if best_streak >= 5:
        labels.append("Серия 5+")
    if best_streak >= 10:
        labels.append("Серия 10+")
    if best_streak >= 15:
        labels.append("Серия 15+")
    if total >= 10 and correct / total >= 0.8:
        labels.append("Точность 80%+")
    if bank_total > 0 and bank_mastered >= bank_total:
        labels.append("Весь банк освоен")
    elif bank_total > 0 and bank_mastered * 2 >= bank_total:
        labels.append("Половина банка")
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
    lines.append("/next — новый вопрос · /stats — прогресс · /help — команды")
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
        return (
            "Ошибок пока нет — отлично!\n"
            "Напиши /quiz или /new для новых вопросов."
        )
    lines = [f"Вопросы с ошибками ({len(rows)}):", ""]
    for qid, wrong, attempts in rows[:limit]:
        lines.append(f"• {qid} — {wrong} ошибок из {attempts} попыток")
    if len(rows) > limit:
        lines.append(f"… и ещё {len(rows) - limit}")
    lines.append("")
    lines.append("/review — повторить · /question <id> — открыть вопрос")
    return "\n".join(lines)
