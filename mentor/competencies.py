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
