"""User progress helpers (achievements, welcome) — pure logic, easy to test."""

from __future__ import annotations

from mentor.competencies import Competency


def collect_achievement_labels(
    *,
    total: int,
    correct: int,
    best_streak: int,
    bank_total: int,
    bank_mastered: int,
) -> list[str]:
    labels: list[str] = []
    if total >= 1:
        labels.append("Первый ответ")
    if correct >= 5:
        labels.append("5 верных ответов")
    if correct >= 20:
        labels.append("20 верных ответов")
    if best_streak >= 5:
        labels.append("Серия 5+")
    if best_streak >= 10:
        labels.append("Серия 10+")
    if bank_total > 0 and bank_mastered >= bank_total:
        labels.append("Весь банк освоен")
    elif bank_total > 0 and bank_mastered * 2 >= bank_total:
        labels.append("Половина банка")
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
    if tip is not None:
        lines.append(f"Сейчас полезно: /practice или /quiz {tip.id}")
    lines.append("")
    lines.append("/next — новый вопрос · /stats — прогресс · /help — команды")
    return "\n".join(lines)
