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
    competencies: list[Competency],
    comp_stats: dict[str, tuple[int, int]],
) -> str:
    acc = (correct / total * 100.0) if total else 0.0
    lines = [
        "Статистика",
        f"Верно: {correct} · всего: {total} · точность: {acc:.1f}%",
        f"Текущая серия верных: {streak}",
    ]
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
    lines.append("/map — карта · /quiz — новый вопрос")
    return "\n".join(lines)


def format_competency_map(
    competencies: list[Competency],
    stats: dict[str, tuple[int, int]],
    *,
    title: str = "Карта компетенций (Data Science)",
) -> str:
    """stats: competency_id -> (correct, total)."""
    lines = [title, ""]
    for c in competencies:
        correct, total = stats.get(c.id, (0, 0))
        if total == 0:
            acc_s = "—"
            bar = progress_bar(0)
            detail = "ещё не решал"
        else:
            acc = correct / total * 100.0
            acc_s = f"{acc:.0f}%"
            bar = progress_bar(acc)
            detail = f"{correct}/{total} ({acc_s})"
        lines.append(f"• {c.title} — {detail} {bar}")
        if c.description:
            lines.append(f"  {c.description}")
    lines.append("")
    lines.append("Квиз по теме: /quiz <id>, например /quiz ml-metrics")
    lines.append("Случайный вопрос: /quiz")
    return "\n".join(lines)
