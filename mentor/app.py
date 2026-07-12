from __future__ import annotations

import logging
import os
import random
import signal
import sqlite3
import time
from typing import Any

import requests
from dotenv import load_dotenv

from mentor import __version__
from mentor import competencies as mentor_comp
from mentor import db as mentor_db
from mentor import progress as mentor_progress
from mentor import quiz as mentor_quiz
from mentor.telegram import iter_chunks
from mentor.textutil import (
    command_prefix,
    parse_new_topic_arg,
    parse_question_id_arg,
    parse_quiz_args,
    parse_search_query,
    parse_topic_arg,
    reset_is_confirmed,
)

POLL_TIMEOUT_S = 30
HTTP_TIMEOUT_S = POLL_TIMEOUT_S + 10
MAX_BACKOFF_S = 30

DEFAULT_REPO_URL = "https://github.com/MikhailBolt/ai-agent-ds-mentor"


def parse_daily_goal() -> int | None:
    raw = os.getenv("DAILY_GOAL", "5").strip()
    try:
        goal = int(raw)
    except ValueError:
        return 5
    return None if goal <= 0 else goal


BOT_COMMANDS: tuple[tuple[str, str], ...] = (
    ("start", "Начать и помощь"),
    ("quiz", "Новый вопрос"),
    ("new", "Вопрос, который ещё не встречался"),
    ("next", "Следующий вопрос"),
    ("go", "Следующий вопрос (алиас)"),
    ("topic", "Вопрос по теме"),
    ("practice", "Вопрос по слабой теме"),
    ("focus", "Фокус на слабой теме"),
    ("challenge", "Сложный вопрос"),
    ("hard", "Сложный вопрос (алиас)"),
    ("medium", "Средний вопрос"),
    ("easy", "Лёгкий вопрос"),
    ("last", "Последний вопрос"),
    ("today", "Дневная цель"),
    ("due", "Очередь на повтор"),
    ("remain", "Сколько нового осталось"),
    ("count", "Краткая сводка"),
    ("level", "Уровень ученика"),
    ("plan", "План тренировки"),
    ("tip", "Совет на сейчас"),
    ("record", "Личные рекорды"),
    ("seen", "Встреченные вопросы"),
    ("mastered", "Освоение по темам"),
    ("export", "Экспорт прогресса"),
    ("search", "Поиск по банку"),
    ("bank", "Обзор банка"),
    ("streak", "Серия ответов"),
    ("current", "Текущий вопрос"),
    ("map", "Карта компетенций"),
    ("topics", "Список тем (id)"),
    ("hint", "Подсказка к вопросу"),
    ("explain", "Пояснение к вопросу"),
    ("review", "Повтор ошибок"),
    ("mistakes", "Список ошибок"),
    ("achievements", "Достижения"),
    ("stats", "Статистика и прогресс"),
    ("progress", "Прогресс по банку"),
    ("skip", "Пропустить вопрос"),
    ("reset", "Сброс прогресса"),
    ("about", "Версия и репозиторий"),
)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(
            f"Missing env var {name}. Create a .env file or export it before starting."
        )
    return value


class TelegramAPI:
    def __init__(self, token: str) -> None:
        self._base = f"https://api.telegram.org/bot{token}"
        self._s = requests.Session()

    def request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base}/{method}"
        rate_limit_attempts = 0
        server_error_attempts = 0
        while True:
            try:
                r = self._s.post(url, json=payload, timeout=HTTP_TIMEOUT_S)
            except (requests.RequestException, ValueError) as e:
                raise RuntimeError(f"HTTP/JSON error calling {method}: {e}") from e

            if r.status_code == 429:
                rate_limit_attempts += 1
                if rate_limit_attempts > 8:
                    raise RuntimeError("Telegram API: too many 429 responses for " + method)
                retry = r.headers.get("Retry-After")
                try:
                    wait_s = (
                        float(retry) if retry is not None else min(5.0 * rate_limit_attempts, 60.0)
                    )
                except ValueError:
                    wait_s = min(5.0 * rate_limit_attempts, 60.0)
                time.sleep(wait_s)
                continue

            if 500 <= r.status_code < 600:
                server_error_attempts += 1
                if server_error_attempts <= 6:
                    wait_s = (
                        min(
                            2.0 * (2 ** (server_error_attempts - 1)),
                            30.0,
                        )
                        + random.random() * 0.25
                    )
                    time.sleep(wait_s)
                    continue

            try:
                r.raise_for_status()
                data = r.json()
            except (requests.RequestException, ValueError) as e:
                raise RuntimeError(f"HTTP/JSON error calling {method}: {e}") from e

            if not isinstance(data, dict) or not data.get("ok", False):
                description = data.get("description") if isinstance(data, dict) else None
                raise RuntimeError(f"Telegram API error calling {method}: {description}")
            return data

    def send_message(self, chat_id: int, text: str) -> None:
        for chunk in iter_chunks(text):
            self.request("sendMessage", {"chat_id": chat_id, "text": chunk})

    def set_my_commands(self) -> None:
        commands = [{"command": name, "description": desc} for name, desc in BOT_COMMANDS]
        self.request("setMyCommands", {"commands": commands})

    def get_updates(self, offset: int | None) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": POLL_TIMEOUT_S,
            "allowed_updates": ["message", "edited_message"],
        }
        if offset is not None:
            payload["offset"] = offset
        data = self.request("getUpdates", payload)
        result = data.get("result", [])
        return result if isinstance(result, list) else []


def _help_text() -> str:
    return (
        "AI DS Mentor запущен.\n\n"
        "Команды:\n"
        "/quiz — вопрос (приоритет слабым темам)\n"
        "/random или /next или /go — случайный вопрос\n"
        "/new или /unseen — вопрос, который вы ещё не видели\n"
        "/new ml-metrics — новый вопрос по теме\n"
        "/topic ml-metrics — вопрос по теме\n"
        "/quiz <id> — вопрос по теме, напр. /quiz ml-metrics\n"
        "/quiz 2 или /quiz hard — по сложности (1–3)\n"
        "/practice — вопрос по слабой теме · /learn — то же самое\n"
        "/focus — сразу фокус на слабой теме\n"
        "/tip — один совет, что делать дальше\n"
        "/count — краткая сводка прогресса\n"
        "/level — уровень по ответам и банку\n"
        "/record — личные рекорды\n"
        "/plan — что тренировать дальше\n"
        "/seen — сколько вопросов банка встречалось\n"
        "/question <id>, /id или /open — конкретный вопрос\n"
        "/challenge или /hard — случайный сложный вопрос (★★★)\n"
        "/medium — средний вопрос (★★☆)\n"
        "/easy — лёгкий вопрос (★☆☆)\n"
        "/last, /repeat или /again — повторить последний вопрос\n"
        "/today, /daily или /goal — дневная цель\n"
        "/due или /queue — вопросы на повтор\n"
        "/accuracy — точность ответов\n"
        "/remain — сколько новых вопросов осталось\n"
        "/mastered — освоение банка по темам\n"
        "/mistakes — список вопросов с ошибками\n"
        "/export — текстовый отчёт о прогрессе\n"
        "/search или /find <слово> — поиск вопроса в банке\n"
        "/bank — обзор банка (темы и сложность)\n"
        "/streak — текущая и лучшая серия\n"
        "/current или /show — информация о текущем вопросе\n"
        "/review, /wrong, /fix или /retry — повторить вопрос с ошибкой\n"
        "/explain — пояснение к текущему вопросу\n"
        "/map — карта компетенций и прогресс\n"
        "/topics — список id тем\n"
        "/skip, /cancel или /pass — пропустить (без штрафа)\n"
        "/giveup — показать ответ и завершить вопрос\n"
        "/stats, /progress, /score или /me — статистика и прогресс по банку\n"
        "/achievements или /badges — достижения\n"
        "/hint — подсказка к текущему вопросу\n"
        "/status или /info — состояние бота\n"
        "/about — версия и ссылка на проект\n"
        "/reset — запрос подтверждения; /reset confirm — сброс прогресса\n"
        "/help — помощь\n\n"
        "Если бот задал вопрос — ответь сообщением "
        "(можно поправить текст после отправки — учтём правку)."
    )


def about_message_text() -> str:
    repo = os.getenv("PROJECT_REPO_URL", DEFAULT_REPO_URL)
    return f"AI DS Mentor v{__version__}\nИсходники: {repo}\n/help — список команд"


def _format_question(
    q: mentor_quiz.Question,
    *,
    competency_title: str | None = None,
) -> str:
    stars = "★" * q.difficulty + "☆" * (3 - q.difficulty)
    meta = f"Вопрос ({q.id}) · сложность {stars}"
    if competency_title:
        meta += f"\nТема: {competency_title}"
    return f"{meta}\n{q.prompt}\n\nОтветь одним сообщением.\n/hint · /giveup · /skip"


def streak_bonus_message(streak: int) -> str:
    if streak in (3, 5, 7, 10, 15):
        return f" Серия верных ответов: {streak}!"
    return ""


def finish_wrong_answer(
    api: TelegramAPI,
    conn: sqlite3.Connection,
    chat_id: int,
    q: mentor_quiz.Question,
    comp_index: dict[str, mentor_comp.Competency],
) -> None:
    mentor_db.record_quiz_result(
        conn,
        chat_id,
        is_correct=False,
        competency_id=q.competency_id,
    )
    mentor_db.record_question_attempt(conn, chat_id, q.id, is_correct=False)
    mentor_db.set_active_question(conn, chat_id, None)
    mentor_db.set_last_question_id(conn, chat_id, q.id)
    comp_title = None
    comp_id = q.competency_id
    if comp_id and comp_id in comp_index:
        comp_title = comp_index[comp_id].title
    api.send_message(
        chat_id,
        format_wrong_answer_message(
            q,
            competency_title=comp_title,
            competency_id=comp_id,
        ),
    )


def format_wrong_answer_message(
    q: mentor_quiz.Question,
    *,
    competency_title: str | None = None,
    competency_id: str | None = None,
) -> str:
    lines = [
        "Пока не зачтено.",
        f"Ожидаемый ответ (пример): {q.answer}",
    ]
    if q.explanation:
        lines.append(f"Пояснение: {q.explanation}")
    elif q.hint:
        lines.append(f"Подсказка: {q.hint}")
    if competency_title and competency_id:
        lines.append(f"Тема: {competency_title} — /quiz {competency_id} или /practice")
    lines.append("\n/review — повтор ошибок · /quiz или /practice — новый вопрос")
    return "\n".join(lines)


def deliver_quiz_question(
    api: TelegramAPI,
    conn: sqlite3.Connection,
    chat_id: int,
    questions: list[mentor_quiz.Question],
    competencies: list[mentor_comp.Competency],
    *,
    comp_filter: str = "",
    difficulty_filter: int | None = None,
    only_ids: set[str] | None = None,
    intro: str | None = None,
) -> None:
    comp_index = mentor_comp.competency_by_id(competencies)
    if comp_filter and comp_filter not in comp_index:
        ids = ", ".join(c.id for c in competencies)
        api.send_message(
            chat_id,
            f"Неизвестная компетенция «{comp_filter}».\nДоступные id: {ids}\n/topics — список тем",
        )
        return

    prev = mentor_db.get_active_question(conn, chat_id)
    seen_ids = mentor_db.get_seen_question_ids(conn, chat_id)
    comp_stats = mentor_db.get_competency_stats(conn, chat_id)
    review_ids = set(mentor_db.get_review_question_ids(conn, chat_id))
    weights = mentor_quiz.competency_weights_for_practice(
        comp_stats,
        (c.id for c in competencies),
    )
    try:
        q = mentor_quiz.pick_next(
            questions,
            prev,
            competency_filter=comp_filter or None,
            difficulty_filter=difficulty_filter,
            competency_weights=weights if not comp_filter and not only_ids else None,
            seen_ids=seen_ids if only_ids is None else None,
            only_ids=only_ids,
            boost_ids=review_ids if not only_ids and not comp_filter else None,
        )
    except ValueError:
        hint = "Попробуй /map или /quiz без аргумента."
        if difficulty_filter:
            hint = f"Нет вопросов сложности {difficulty_filter}. {hint}"
        api.send_message(chat_id, f"Нет подходящих вопросов. {hint}")
        return

    title = None
    if q.competency_id and q.competency_id in comp_index:
        title = comp_index[q.competency_id].title
    mentor_db.set_active_question(conn, chat_id, q.id)
    body = _format_question(q, competency_title=title)
    if q.id in seen_ids:
        body = f"Повтор вопроса.\n\n{body}"
    if intro:
        body = f"{intro}\n\n{body}"
    api.send_message(chat_id, body)


def start_question_by_id(
    api: TelegramAPI,
    conn: sqlite3.Connection,
    chat_id: int,
    questions: list[mentor_quiz.Question],
    competencies: list[mentor_comp.Competency],
    question_id: str,
) -> None:
    q = mentor_quiz.find_by_id(questions, question_id)
    if q is None:
        api.send_message(
            chat_id,
            f"Вопрос «{question_id}» не найден. /topics — темы, /quiz — случайный.",
        )
        return
    comp_index = mentor_comp.competency_by_id(competencies)
    title = None
    if q.competency_id and q.competency_id in comp_index:
        title = comp_index[q.competency_id].title
    mentor_db.set_active_question(conn, chat_id, q.id)
    api.send_message(chat_id, _format_question(q, competency_title=title))


def format_status_text(
    *,
    started_at: float,
    now: float,
    question_count: int,
    stats: mentor_db.Stats,
    streak: int = 0,
    best_streak: int = 0,
    bank_seen: int = 0,
    bank_mastered: int = 0,
    daily_count: int = 0,
    daily_goal: int | None = None,
    last_question_id: str | None = None,
    active_question_id: str | None = None,
) -> str:
    uptime_sec = max(0, int(now - started_at))
    uptime_min, sec = divmod(uptime_sec, 60)
    hours, minutes = divmod(uptime_min, 60)
    acc = (stats.correct / stats.total * 100.0) if stats.total else 0.0
    lines = [
        "Статус бота:",
        f"Версия: {__version__}",
        f"Uptime: {hours:02d}:{minutes:02d}:{sec:02d}",
        f"Вопросов в банке: {question_count}",
        f"Твоя статистика: {stats.correct}/{stats.total} ({acc:.1f}%)",
        f"Серия верных: {streak} (лучшая: {best_streak})",
        f"Встречено вопросов из банка: {bank_seen}/{question_count}",
        f"Освоено банка (≥1 верный): {bank_mastered}/{question_count}",
    ]
    if daily_goal:
        lines.append(mentor_progress.format_daily_goal_line(daily_count, daily_goal))
    if last_question_id:
        lines.append(f"Последний вопрос: {last_question_id} — /last")
    if active_question_id:
        lines.append(f"Активный вопрос: {active_question_id}")
    return "\n".join(lines)


def handle_text(
    api: TelegramAPI,
    conn: sqlite3.Connection,
    questions: list[mentor_quiz.Question],
    competencies: list[mentor_comp.Competency],
    bank_counts: dict[str, int],
    started_at: float,
    chat_id: int,
    text: str,
) -> None:
    text = (text or "").strip()

    mentor_db.touch_user(conn, chat_id)

    cmd = command_prefix(text)
    comp_index = mentor_comp.competency_by_id(competencies)

    if cmd == "/help":
        api.send_message(chat_id, _help_text())
        return

    if cmd == "/start":
        st = mentor_db.get_stats(conn, chat_id)
        streak = mentor_db.get_streak(conn, chat_id)
        mastered = len(mentor_db.get_mastered_question_ids(conn, chat_id))
        daily_goal = parse_daily_goal()
        daily_count = mentor_db.get_daily_answer_count(conn, chat_id)
        comp_stats = mentor_db.get_competency_stats(conn, chat_id)
        tip = mentor_comp.suggest_practice_competency(competencies, comp_stats)
        api.send_message(
            chat_id,
            mentor_progress.format_start_welcome(
                total=st.total,
                streak=streak,
                bank_mastered=mastered,
                bank_total=len(questions),
                tip=tip,
                daily_count=daily_count,
                daily_goal=daily_goal,
            ),
        )
        return

    if cmd in {"/achievements", "/badges"}:
        st = mentor_db.get_stats(conn, chat_id)
        best = mentor_db.get_best_streak(conn, chat_id)
        mastered_ids = mentor_db.get_mastered_question_ids(conn, chat_id)
        bank_mastery = mentor_quiz.competency_mastery_counts(questions, mastered_ids)
        comp_titles = {c.id: c.title for c in competencies}
        daily_goal = parse_daily_goal()
        daily_count = mentor_db.get_daily_answer_count(conn, chat_id)
        labels = mentor_progress.collect_achievement_labels(
            total=st.total,
            correct=st.correct,
            best_streak=best,
            bank_total=len(questions),
            bank_mastered=len(mastered_ids),
            daily_count=daily_count,
            daily_goal=daily_goal,
            bank_mastery=bank_mastery,
            competency_titles=comp_titles,
            comp_stats=mentor_db.get_competency_stats(conn, chat_id),
            all_competency_ids={c.id for c in competencies},
        )
        api.send_message(chat_id, mentor_progress.format_achievements_text(labels))
        return

    if cmd in {"/map", "/competencies"}:
        comp_stats = mentor_db.get_competency_stats(conn, chat_id)
        mastered_ids = mentor_db.get_mastered_question_ids(conn, chat_id)
        bank_mastery = mentor_quiz.competency_mastery_counts(questions, mastered_ids)
        api.send_message(
            chat_id,
            mentor_comp.format_competency_map(
                competencies,
                comp_stats,
                bank_counts=bank_counts,
                bank_mastery=bank_mastery,
            ),
        )
        return

    if cmd == "/topics":
        seen = mentor_db.get_seen_question_ids(conn, chat_id)
        unseen_counts: dict[str, int] = {}
        for c in competencies:
            unseen_counts[c.id] = sum(
                1 for q in questions if q.competency_id == c.id and q.id not in seen
            )
        api.send_message(
            chat_id,
            mentor_comp.format_topics_list(
                competencies,
                bank_counts,
                unseen_counts=unseen_counts,
            ),
        )
        return

    if cmd == "/bank":
        diff_counts = mentor_quiz.question_counts_by_difficulty(questions)
        api.send_message(
            chat_id,
            mentor_comp.format_bank_summary(
                total=len(questions),
                diff_counts=diff_counts,
                competencies=competencies,
                bank_counts=bank_counts,
            ),
        )
        return

    if cmd in {"/search", "/find"}:
        try:
            query = parse_search_query(text)
        except ValueError:
            query = ""
        found = mentor_quiz.search_questions(
            questions,
            query,
            competency_titles={c.id: c.title for c in competencies},
            competency_descriptions={c.id: c.description for c in competencies},
        )
        api.send_message(
            chat_id,
            mentor_comp.format_search_results(found, query),
        )
        return

    if cmd == "/streak":
        streak = mentor_db.get_streak(conn, chat_id)
        best = mentor_db.get_best_streak(conn, chat_id)
        api.send_message(
            chat_id,
            mentor_progress.format_streak_summary(streak=streak, best=best),
        )
        return

    if cmd in {"/challenge", "/hard"}:
        deliver_quiz_question(
            api,
            conn,
            chat_id,
            questions,
            competencies,
            difficulty_filter=3,
            intro="Челлендж: сложный вопрос",
        )
        return

    if cmd in {"/last", "/repeat", "/again"}:
        last_q = mentor_db.get_last_question_id(conn, chat_id)
        if not last_q:
            api.send_message(
                chat_id,
                "Пока нет последнего вопроса. Напиши /quiz.",
            )
            return
        start_question_by_id(api, conn, chat_id, questions, competencies, last_q)
        return

    if cmd == "/count":
        st = mentor_db.get_stats(conn, chat_id)
        streak = mentor_db.get_streak(conn, chat_id)
        best = mentor_db.get_best_streak(conn, chat_id)
        seen = mentor_db.get_seen_question_ids(conn, chat_id)
        unseen = len(mentor_quiz.unseen_question_ids(questions, seen))
        review_count = len(mentor_db.get_review_question_ids(conn, chat_id))
        api.send_message(
            chat_id,
            mentor_progress.format_count_summary(
                correct=st.correct,
                total=st.total,
                streak=streak,
                best_streak=best,
                bank_unseen=unseen,
                review_count=review_count,
            ),
        )
        return

    if cmd == "/accuracy":
        st = mentor_db.get_stats(conn, chat_id)
        api.send_message(
            chat_id,
            mentor_progress.format_accuracy_summary(correct=st.correct, total=st.total),
        )
        return

    if cmd in {"/due", "/queue"}:
        review_ids = mentor_db.get_review_question_ids(conn, chat_id)
        api.send_message(
            chat_id,
            mentor_progress.format_due_summary(review_ids=review_ids),
        )
        return

    if cmd == "/level":
        st = mentor_db.get_stats(conn, chat_id)
        mastered = len(mentor_db.get_mastered_question_ids(conn, chat_id))
        api.send_message(
            chat_id,
            mentor_progress.format_level_summary(
                total=st.total,
                bank_mastered=mastered,
                bank_total=len(questions),
            ),
        )
        return

    if cmd == "/seen":
        seen = len(mentor_db.get_seen_question_ids(conn, chat_id))
        api.send_message(
            chat_id,
            mentor_progress.format_seen_summary(
                bank_seen=seen,
                bank_total=len(questions),
            ),
        )
        return

    if cmd == "/record":
        st = mentor_db.get_stats(conn, chat_id)
        best = mentor_db.get_best_streak(conn, chat_id)
        mastered = len(mentor_db.get_mastered_question_ids(conn, chat_id))
        api.send_message(
            chat_id,
            mentor_progress.format_record_summary(
                correct=st.correct,
                total=st.total,
                best_streak=best,
                bank_mastered=mastered,
                bank_total=len(questions),
            ),
        )
        return

    if cmd == "/tip":
        seen = mentor_db.get_seen_question_ids(conn, chat_id)
        unseen = len(mentor_quiz.unseen_question_ids(questions, seen))
        review_count = len(mentor_db.get_review_question_ids(conn, chat_id))
        daily_goal = parse_daily_goal()
        daily_count = mentor_db.get_daily_answer_count(conn, chat_id)
        tip = mentor_comp.suggest_practice_competency(
            competencies,
            mentor_db.get_competency_stats(conn, chat_id),
        )
        api.send_message(
            chat_id,
            mentor_progress.format_tip_summary(
                bank_unseen=unseen,
                review_count=review_count,
                daily_count=daily_count,
                daily_goal=daily_goal,
                tip_title=tip.title if tip else None,
                tip_id=tip.id if tip else None,
            ),
        )
        return

    if cmd == "/plan":
        seen = mentor_db.get_seen_question_ids(conn, chat_id)
        unseen = len(mentor_quiz.unseen_question_ids(questions, seen))
        review_count = len(mentor_db.get_review_question_ids(conn, chat_id))
        daily_goal = parse_daily_goal()
        daily_count = mentor_db.get_daily_answer_count(conn, chat_id)
        comp_stats = mentor_db.get_competency_stats(conn, chat_id)
        tip = mentor_comp.suggest_practice_competency(competencies, comp_stats)
        api.send_message(
            chat_id,
            mentor_progress.format_plan_summary(
                bank_unseen=unseen,
                review_count=review_count,
                daily_count=daily_count,
                daily_goal=daily_goal,
                tip_title=tip.title if tip else None,
                tip_id=tip.id if tip else None,
            ),
        )
        return

    if cmd in {"/today", "/daily", "/goal"}:
        daily_goal = parse_daily_goal()
        daily_count = mentor_db.get_daily_answer_count(conn, chat_id)
        streak = mentor_db.get_streak(conn, chat_id)
        api.send_message(
            chat_id,
            mentor_progress.format_today_summary(
                count=daily_count,
                goal=daily_goal,
                streak=streak,
            ),
        )
        return

    if cmd == "/easy":
        deliver_quiz_question(
            api,
            conn,
            chat_id,
            questions,
            competencies,
            difficulty_filter=1,
            intro="Лёгкий вопрос",
        )
        return

    if cmd == "/medium":
        deliver_quiz_question(
            api,
            conn,
            chat_id,
            questions,
            competencies,
            difficulty_filter=2,
            intro="Средний вопрос",
        )
        return

    if cmd == "/export":
        st = mentor_db.get_stats(conn, chat_id)
        streak = mentor_db.get_streak(conn, chat_id)
        best = mentor_db.get_best_streak(conn, chat_id)
        seen = mentor_db.get_seen_question_ids(conn, chat_id)
        mastered = mentor_db.get_mastered_question_ids(conn, chat_id)
        review_count = len(mentor_db.get_review_question_ids(conn, chat_id))
        daily_goal = parse_daily_goal()
        daily_count = mentor_db.get_daily_answer_count(conn, chat_id)
        comp_stats = mentor_db.get_competency_stats(conn, chat_id)
        achievements = mentor_progress.collect_achievement_labels(
            total=st.total,
            correct=st.correct,
            best_streak=best,
            bank_total=len(questions),
            bank_mastered=len(mastered),
            daily_count=daily_count,
            daily_goal=daily_goal,
            comp_stats=comp_stats,
            all_competency_ids={c.id for c in competencies},
        )
        api.send_message(
            chat_id,
            mentor_progress.format_progress_export(
                version=__version__,
                correct=st.correct,
                total=st.total,
                streak=streak,
                best_streak=best,
                bank_total=len(questions),
                bank_seen=len(seen),
                bank_mastered=len(mastered),
                review_count=review_count,
                daily_count=daily_count,
                daily_goal=daily_goal,
                competencies=competencies,
                comp_stats=comp_stats,
                achievements=achievements,
            ),
        )
        return

    if cmd in {"/current", "/show"}:
        active = mentor_db.get_active_question(conn, chat_id)
        if active is None:
            api.send_message(chat_id, "Сейчас нет активного вопроса. Напиши /quiz.")
            return
        q = mentor_quiz.find_by_id(questions, active)
        if q is None:
            api.send_message(chat_id, "Вопрос не найден. Напиши /quiz.")
            return
        title = None
        if q.competency_id and q.competency_id in comp_index:
            title = comp_index[q.competency_id].title
        api.send_message(chat_id, _format_question(q, competency_title=title))
        return

    if cmd == "/weaktopic":
        comp_stats = mentor_db.get_competency_stats(conn, chat_id)
        tip = mentor_comp.suggest_practice_competency(competencies, comp_stats)
        api.send_message(chat_id, mentor_comp.format_weaktopic_tip(tip))
        return

    if cmd == "/focus":
        comp_stats = mentor_db.get_competency_stats(conn, chat_id)
        tip = mentor_comp.suggest_practice_competency(competencies, comp_stats)
        if tip is None:
            api.send_message(chat_id, "Нет тем для фокуса. /quiz — любой вопрос.")
            return
        deliver_quiz_question(
            api,
            conn,
            chat_id,
            questions,
            competencies,
            comp_filter=tip.id,
            intro=f"Фокус: {tip.title}",
        )
        return

    if cmd in {"/practice", "/weak", "/learn"}:
        comp_stats = mentor_db.get_competency_stats(conn, chat_id)
        tip = mentor_comp.suggest_practice_competency(competencies, comp_stats)
        if tip is None:
            api.send_message(chat_id, "Нет тем для тренировки.")
            return
        deliver_quiz_question(
            api,
            conn,
            chat_id,
            questions,
            competencies,
            comp_filter=tip.id,
            intro=f"Тренировка: {tip.title}",
        )
        return

    if cmd in {"/stats", "/progress", "/score", "/me"}:
        st = mentor_db.get_stats(conn, chat_id)
        streak = mentor_db.get_streak(conn, chat_id)
        best = mentor_db.get_best_streak(conn, chat_id)
        seen = mentor_db.get_seen_question_ids(conn, chat_id)
        mastered_ids = mentor_db.get_mastered_question_ids(conn, chat_id)
        bank_mastery = mentor_quiz.competency_mastery_counts(questions, mastered_ids)
        comp_titles = {c.id: c.title for c in competencies}
        daily_goal = parse_daily_goal()
        daily_count = mentor_db.get_daily_answer_count(conn, chat_id)
        comp_stats = mentor_db.get_competency_stats(conn, chat_id)
        achievements = mentor_progress.collect_achievement_labels(
            total=st.total,
            correct=st.correct,
            best_streak=best,
            bank_total=len(questions),
            bank_mastered=len(mastered_ids),
            daily_count=daily_count,
            daily_goal=daily_goal,
            bank_mastery=bank_mastery,
            competency_titles=comp_titles,
            comp_stats=comp_stats,
            all_competency_ids={c.id for c in competencies},
        )
        api.send_message(
            chat_id,
            mentor_comp.format_stats_summary(
                correct=st.correct,
                total=st.total,
                streak=streak,
                best_streak=best,
                bank_total=len(questions),
                bank_seen=len(seen),
                bank_mastered=len(mastered_ids),
                competencies=competencies,
                comp_stats=comp_stats,
                achievement_lines=achievements,
                daily_count=daily_count,
                daily_goal=daily_goal,
            ),
        )
        return

    if cmd in {"/hint", "/explain"}:
        active = mentor_db.get_active_question(conn, chat_id)
        if active is None:
            api.send_message(chat_id, "Сейчас нет активного вопроса. Напиши /quiz.")
            return
        q = mentor_quiz.find_by_id(questions, active)
        if q is None:
            api.send_message(chat_id, "Вопрос не найден. Напиши /quiz.")
            return
        if cmd == "/explain":
            if q.explanation:
                api.send_message(chat_id, f"Пояснение: {q.explanation}")
            elif q.hint:
                api.send_message(chat_id, f"Подсказка: {q.hint}")
            else:
                api.send_message(chat_id, "Пояснения для этого вопроса нет.")
            return
        if not q.hint:
            api.send_message(chat_id, "Для этого вопроса подсказки нет.")
            return
        api.send_message(chat_id, f"Подсказка: {q.hint}")
        return

    if cmd == "/mistakes":
        rows = mentor_db.get_mistake_rows(conn, chat_id, limit=20)
        summary_rows = [(r.question_id, r.wrong, r.attempts) for r in rows]
        api.send_message(
            chat_id,
            mentor_progress.format_mistakes_summary(summary_rows),
        )
        return

    if cmd in {"/review", "/wrong", "/fix", "/retry"}:
        review_ids = mentor_db.get_review_question_ids(conn, chat_id)
        if not review_ids:
            api.send_message(
                chat_id,
                "Пока нет вопросов с ошибками. Напиши /quiz чтобы потренироваться.",
            )
            return
        deliver_quiz_question(
            api,
            conn,
            chat_id,
            questions,
            competencies,
            only_ids=set(review_ids),
            intro="Повтор вопроса, где была ошибка",
        )
        return

    if cmd == "/mastered":
        mastered_ids = mentor_db.get_mastered_question_ids(conn, chat_id)
        bank_mastery = mentor_quiz.competency_mastery_counts(questions, mastered_ids)
        api.send_message(
            chat_id,
            mentor_comp.format_mastered_summary(competencies, bank_mastery),
        )
        return

    if cmd in {"/remain", "/left"}:
        seen = mentor_db.get_seen_question_ids(conn, chat_id)
        unseen = len(mentor_quiz.unseen_question_ids(questions, seen))
        mastered = len(mentor_db.get_mastered_question_ids(conn, chat_id))
        review_count = len(mentor_db.get_review_question_ids(conn, chat_id))
        api.send_message(
            chat_id,
            mentor_progress.format_remaining_summary(
                bank_total=len(questions),
                bank_unseen=unseen,
                review_count=review_count,
                bank_mastered=mastered,
            ),
        )
        return

    if cmd in {"/status", "/info"}:
        st = mentor_db.get_stats(conn, chat_id)
        streak = mentor_db.get_streak(conn, chat_id)
        best = mentor_db.get_best_streak(conn, chat_id)
        seen = len(mentor_db.get_seen_question_ids(conn, chat_id))
        mastered = len(mentor_db.get_mastered_question_ids(conn, chat_id))
        daily_goal = parse_daily_goal()
        daily_count = mentor_db.get_daily_answer_count(conn, chat_id)
        last_q = mentor_db.get_last_question_id(conn, chat_id)
        active = mentor_db.get_active_question(conn, chat_id)
        api.send_message(
            chat_id,
            format_status_text(
                started_at=started_at,
                now=time.time(),
                question_count=len(questions),
                stats=st,
                streak=streak,
                best_streak=best,
                bank_seen=seen,
                bank_mastered=mastered,
                daily_count=daily_count,
                daily_goal=daily_goal,
                last_question_id=last_q,
                active_question_id=active,
            ),
        )
        return

    if cmd == "/about":
        api.send_message(chat_id, about_message_text())
        return

    if cmd == "/reset":
        try:
            confirmed = reset_is_confirmed(text)
        except ValueError:
            confirmed = False
        if not confirmed:
            api.send_message(
                chat_id,
                "Сбросить весь прогресс (статистика, серии, история)?\n"
                "Напиши /reset confirm чтобы подтвердить.",
            )
            return
        mentor_db.reset_user(conn, chat_id)
        api.send_message(chat_id, "Готово. Прогресс сброшен. Напиши /quiz чтобы начать заново.")
        return

    if cmd == "/giveup":
        active = mentor_db.get_active_question(conn, chat_id)
        if active is None:
            api.send_message(chat_id, "Сейчас нет активного вопроса. Напиши /quiz.")
            return
        q = mentor_quiz.find_by_id(questions, active)
        if q is None:
            mentor_db.set_active_question(conn, chat_id, None)
            api.send_message(chat_id, "Вопрос не найден. Напиши /quiz.")
            return
        finish_wrong_answer(api, conn, chat_id, q, comp_index)
        return

    if cmd in {"/skip", "/cancel", "/pass"}:
        active = mentor_db.get_active_question(conn, chat_id)
        if active is None:
            api.send_message(chat_id, "Сейчас нет активного вопроса. Напиши /quiz.")
            return
        mentor_db.set_active_question(conn, chat_id, None)
        api.send_message(chat_id, "Ок, пропустили. Напиши /quiz чтобы получить следующий вопрос.")
        return

    if cmd in {"/new", "/unseen"}:
        try:
            topic = parse_new_topic_arg(text)
        except ValueError:
            topic = ""
        if topic and topic not in comp_index:
            ids = ", ".join(c.id for c in competencies)
            api.send_message(
                chat_id,
                f"Неизвестная тема «{topic}».\nДоступные id: {ids}\n/topics — список",
            )
            return
        seen = mentor_db.get_seen_question_ids(conn, chat_id)
        unseen = mentor_quiz.unseen_question_ids(questions, seen)
        if topic:
            unseen = {q.id for q in questions if q.id in unseen and q.competency_id == topic}
        if not unseen:
            hint = "Все вопросы банка уже встречались."
            if topic:
                hint = f"Новых вопросов по теме «{comp_index[topic].title}» не осталось."
            api.send_message(chat_id, f"{hint} /quiz — повторы, /review — ошибки.")
            return
        intro = "Новый вопрос из банка"
        if topic:
            intro = f"Новый вопрос: {comp_index[topic].title}"
        deliver_quiz_question(
            api,
            conn,
            chat_id,
            questions,
            competencies,
            only_ids=unseen,
            intro=intro,
        )
        return

    if cmd in {"/question", "/q", "/id", "/open"}:
        try:
            qid = parse_question_id_arg(text)
        except ValueError:
            qid = ""
        if not qid:
            api.send_message(
                chat_id,
                "Укажи id вопроса: /question ml-001\n/topics — темы, /map — карта",
            )
            return
        start_question_by_id(api, conn, chat_id, questions, competencies, qid)
        return

    if cmd == "/topic":
        try:
            topic = parse_topic_arg(text)
        except ValueError:
            topic = ""
        if not topic:
            api.send_message(
                chat_id,
                "Укажи тему: /topic ml-metrics\n/topics — список id",
            )
            return
        if topic not in comp_index:
            ids = ", ".join(c.id for c in competencies)
            api.send_message(
                chat_id,
                f"Неизвестная тема «{topic}».\nДоступные id: {ids}",
            )
            return
        deliver_quiz_question(
            api,
            conn,
            chat_id,
            questions,
            competencies,
            comp_filter=topic,
            intro=f"Тема: {comp_index[topic].title}",
        )
        return

    if cmd in {"/quiz", "/next", "/random", "/go"}:
        comp_filter, difficulty = "", None
        if cmd == "/quiz":
            try:
                comp_filter, difficulty = parse_quiz_args(
                    text,
                    valid_competency_ids=set(comp_index),
                )
            except ValueError:
                pass
        deliver_quiz_question(
            api,
            conn,
            chat_id,
            questions,
            competencies,
            comp_filter=comp_filter,
            difficulty_filter=difficulty,
        )
        return

    # If there's an active question, treat message as an answer.
    active_id = mentor_db.get_active_question(conn, chat_id)
    if active_id is not None:
        q = mentor_quiz.find_by_id(questions, active_id)
        if q is None:
            mentor_db.set_active_question(conn, chat_id, None)
            api.send_message(chat_id, "Похоже, банк вопросов обновился. Напиши /quiz.")
            return

        if not mentor_quiz.normalize(text):
            api.send_message(
                chat_id,
                "Пустой ответ не засчитывается. Напиши развёрнуто или /hint.",
            )
            return

        is_correct = q.matches(text)
        if not is_correct:
            retry_q = mentor_db.get_retry_question_id(conn, chat_id)
            if retry_q != active_id:
                mentor_db.set_retry_question_id(conn, chat_id, active_id)
                api.send_message(
                    chat_id,
                    "Пока не зачтено. Ещё одна попытка — /hint, /giveup или /skip.",
                )
                return
            finish_wrong_answer(api, conn, chat_id, q, comp_index)
            return

        had_retry = mentor_db.get_retry_question_id(conn, chat_id) == active_id
        streak = mentor_db.record_quiz_result(
            conn,
            chat_id,
            is_correct=True,
            competency_id=q.competency_id,
        )
        mentor_db.record_question_attempt(conn, chat_id, q.id, is_correct=True)
        mentor_db.set_last_question_id(conn, chat_id, q.id)
        mentor_db.set_active_question(conn, chat_id, None)
        bonus = streak_bonus_message(streak)
        retry_note = " (со второй попытки)" if had_retry else ""
        seen = mentor_db.get_seen_question_ids(conn, chat_id)
        bank_done = ""
        if len(seen) >= len(questions):
            bank_done = "\nТы прошёл все вопросы банка — дальше будут повторы."
        api.send_message(
            chat_id,
            f"Верно. Отлично!{retry_note}{bonus}{bank_done}\nНапиши /quiz или /map.",
        )
        return

    api.send_message(chat_id, "Команда не распознана. Напиши /help")


def run() -> None:
    load_dotenv()
    token = _require_env("TELEGRAM_BOT_TOKEN")
    db_path = os.getenv("DB_PATH", "bot.db")
    questions_path = os.getenv("QUESTIONS_PATH", mentor_quiz.default_questions_path())
    competencies_path = os.getenv(
        "COMPETENCIES_PATH",
        mentor_comp.default_competencies_path(),
    )

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    log = logging.getLogger("ai-agent-ds-mentor")

    api = TelegramAPI(token)
    conn = mentor_db.connect(db_path)
    mentor_db.ensure_schema(conn)
    competencies = mentor_comp.load_competencies(competencies_path)
    comp_ids = {c.id for c in competencies}
    questions = mentor_quiz.load_questions(questions_path, valid_competency_ids=comp_ids)
    mentor_quiz.validate_competency_coverage(questions, comp_ids)
    bank_counts = mentor_quiz.question_counts_by_competency(questions)

    try:
        api.set_my_commands()
    except Exception:
        log.warning("setMyCommands failed", exc_info=True)

    log.info(
        "Starting bot version=%s questions=%s (%d) competencies=%s (%d) db=%s",
        __version__,
        questions_path,
        len(questions),
        competencies_path,
        len(competencies),
        db_path,
    )

    offset: int | None = None
    backoff_s = 1.0
    started_at = time.time()

    running = True

    def stop_running(*_: Any) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop_running)
    try:
        signal.signal(signal.SIGTERM, stop_running)
    except (AttributeError, ValueError):
        pass

    log.info("Polling Telegram (long polling)")
    try:
        while running:
            try:
                updates = api.get_updates(offset)
                backoff_s = 1.0
            except Exception:
                log.exception("Polling error; backing off")
                sleep_s = min(MAX_BACKOFF_S, backoff_s) + random.random()
                time.sleep(sleep_s)
                backoff_s = min(MAX_BACKOFF_S, backoff_s * 2)
                continue

            for u in updates:
                update_id = u.get("update_id")
                if isinstance(update_id, int):
                    offset = update_id + 1

                msg = u.get("message")
                edited = u.get("edited_message")
                if not isinstance(msg, dict):
                    msg = edited
                if not isinstance(msg, dict):
                    continue
                is_edit = isinstance(edited, dict)
                chat = msg.get("chat")
                if not isinstance(chat, dict):
                    continue
                chat_id = chat.get("id")
                if not isinstance(chat_id, int):
                    continue

                msg_id = msg.get("message_id")
                if not isinstance(msg_id, int):
                    continue

                edit_date = msg.get("edit_date") if is_edit else None

                text = msg.get("text")
                if not isinstance(text, str):
                    continue

                try:
                    if not mentor_db.claim_message_revision(conn, chat_id, msg_id, edit_date):
                        continue
                    handle_text(
                        api,
                        conn,
                        questions,
                        competencies,
                        bank_counts,
                        started_at,
                        chat_id,
                        text,
                    )
                except Exception:
                    log.exception("Failed to handle message")
    except KeyboardInterrupt:
        log.info("Keyboard interrupt; stopping")
    finally:
        conn.close()
        log.info("SQLite connection closed")
