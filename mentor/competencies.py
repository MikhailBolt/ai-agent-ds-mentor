from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path


@dataclass(frozen=True)
class Competency:
    id: str
    title: str
    description: str


def default_competencies_path() -> str:
    return str(resources.files("mentor.data").joinpath("competencies.json"))


def load_competencies(path: str) -> list[Competency]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("competencies json must be a list")

    out: list[Competency] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        cid = str(item.get("id") or f"c{i + 1}")
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        if title:
            if cid in seen:
                raise ValueError(f"duplicate competency id: {cid}")
            seen.add(cid)
            out.append(Competency(id=cid, title=title, description=description))
    if not out:
        raise ValueError("no valid competencies loaded")
    return out


def competency_by_id(competencies: list[Competency]) -> dict[str, Competency]:
    return {c.id: c for c in competencies}


def progress_bar(accuracy: float, width: int = 5) -> str:
    acc = max(0.0, min(100.0, accuracy))
    filled = int(round(acc / 100.0 * width))
    return "▓" * filled + "░" * (width - filled)


def suggest_practice_competency(
    competencies: list[Competency],
    stats: dict[str, tuple[int, int]],
) -> Competency | None:
    """Pick an unseen topic first, otherwise the weakest by accuracy."""
    unseen = [c for c in competencies if stats.get(c.id, (0, 0))[1] == 0]
    if unseen:
        return unseen[0]
    weakest_acc = 2.0
    pick: Competency | None = None
    for c in competencies:
        correct, total = stats.get(c.id, (0, 0))
        if total == 0:
            continue
        acc = correct / total
        if acc < weakest_acc:
            weakest_acc = acc
            pick = c
    return pick


def format_stats_summary(
    *,
    correct: int,
    total: int,
    streak: int,
    best_streak: int,
    bank_total: int,
    bank_seen: int,
    bank_mastered: int,
    competencies: list[Competency],
    comp_stats: dict[str, tuple[int, int]],
    achievement_lines: list[str] | None = None,
    daily_count: int = 0,
    daily_goal: int | None = None,
) -> str:
    acc = (correct / total * 100.0) if total else 0.0
    bank_pct = (bank_seen / bank_total * 100.0) if bank_total else 0.0
    mastered_pct = (bank_mastered / bank_total * 100.0) if bank_total else 0.0
    lines = [
        "Статистика",
        f"Верно: {correct} · всего: {total} · точность: {acc:.1f}%",
        f"Текущая серия: {streak} · лучшая: {best_streak}",
        f"Банк: встречено {bank_seen}/{bank_total} ({bank_pct:.0f}%)",
        f"Освоено (хотя бы 1 верный): {bank_mastered}/{bank_total} ({mastered_pct:.0f}%)",
    ]
    if daily_goal:
        if daily_count >= daily_goal:
            lines.append(f"Дневная цель: {daily_count}/{daily_goal} — выполнена!")
        else:
            lines.append(f"Дневная цель: {daily_count}/{daily_goal} ответов сегодня")
    if achievement_lines:
        lines.append("")
        lines.append("Достижения:")
        lines.extend(f"• {line}" for line in achievement_lines)
    tip = suggest_practice_competency(competencies, comp_stats)
    if tip is not None:
        _, tip_total = comp_stats.get(tip.id, (0, 0))
        if tip_total == 0:
            lines.append(f"Рекомендация: начни с «{tip.title}» — /quiz {tip.id}")
        else:
            c_ok, c_tot = comp_stats[tip.id]
            tip_acc = c_ok / c_tot * 100.0
            lines.append(
                f"Рекомендация: подтянуть «{tip.title}» ({tip_acc:.0f}%) — /quiz {tip.id}",
            )
    lines.append("")
    lines.append("По темам:")
    for c in competencies:
        c_ok, c_tot = comp_stats.get(c.id, (0, 0))
        if c_tot == 0:
            lines.append(f"• {c.title} — ещё не решал")
        else:
            c_acc = c_ok / c_tot * 100.0
            lines.append(f"• {c.title} — {c_ok}/{c_tot} ({c_acc:.0f}%)")
    lines.append("")
    lines.append("/map — карта · /quiz или /next — вопрос · /review — ошибки")
    return "\n".join(lines)


def format_search_results(questions: list, query: str) -> str:
    if not query.strip():
        return "Укажи слово для поиска: /search precision"
    if not questions:
        return f"По запросу «{query}» ничего не найдено. /bank — обзор банка"
    lines = [f"Найдено ({len(questions)}):", ""]
    for q in questions:
        preview = q.prompt if len(q.prompt) <= 60 else q.prompt[:57] + "..."
        lines.append(f"• {q.id} — {preview}")
    lines.append("")
    lines.append("Открыть: /question <id>")
    return "\n".join(lines)


def format_bank_summary(
    *,
    total: int,
    diff_counts: dict[int, int],
    competencies: list[Competency],
    bank_counts: dict[str, int],
) -> str:
    lines = [
        f"Банк вопросов: {total}",
        "",
        "По сложности:",
    ]
    stars = {1: "★☆☆", 2: "★★☆", 3: "★★★"}
    for level in sorted(diff_counts):
        lines.append(f"• {stars.get(level, str(level))} — {diff_counts[level]}")
    lines.append("")
    lines.append("По темам:")
    for c in competencies:
        n = bank_counts.get(c.id, 0)
        lines.append(f"• {c.title} ({c.id}) — {n}")
    lines.append("")
    lines.append("/search <слово> · /question <id> · /new")
    return "\n".join(lines)


def format_topics_list(
    competencies: list[Competency],
    bank_counts: dict[str, int] | None = None,
    unseen_counts: dict[str, int] | None = None,
) -> str:
    lines = ["Темы (id для /quiz):", ""]
    for c in competencies:
        n = bank_counts.get(c.id, 0) if bank_counts else 0
        suffix = f" — {n} вопр. в банке" if n else ""
        if unseen_counts is not None and c.id in unseen_counts:
            suffix += f", новых: {unseen_counts[c.id]}"
        lines.append(f"• {c.id}: {c.title}{suffix}")
    lines.append("")
    lines.append("/map — прогресс · /practice — слабая тема")
    return "\n".join(lines)


def format_competency_map(
    competencies: list[Competency],
    stats: dict[str, tuple[int, int]],
    *,
    title: str = "Карта компетенций (Data Science)",
    bank_counts: dict[str, int] | None = None,
    bank_mastery: dict[str, tuple[int, int]] | None = None,
) -> str:
    """stats: competency_id -> (correct, total)."""
    lines = [title, ""]
    for c in competencies:
        correct, total = stats.get(c.id, (0, 0))
        bank_n = bank_counts.get(c.id, 0) if bank_counts else 0
        bank_s = f" · в банке {bank_n}" if bank_n else ""
        if bank_mastery and c.id in bank_mastery:
            m_ok, m_tot = bank_mastery[c.id]
            bank_s += f" · освоено {m_ok}/{m_tot}"
        if total == 0:
            bar = progress_bar(0)
            detail = "ещё не решал"
        else:
            acc = correct / total * 100.0
            bar = progress_bar(acc)
            detail = f"{correct}/{total} ({acc:.0f}%)"
        lines.append(f"• {c.title} — {detail} {bar}{bank_s}")
        if c.description:
            lines.append(f"  {c.description}")
        lines.append(f"  id: {c.id}")
    lines.append("")
    lines.append("/practice — тренировка слабой темы")
    lines.append("/quiz <id> — вопрос по теме · /topics — список id")
    return "\n".join(lines)
