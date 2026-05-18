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
from mentor import quiz as mentor_quiz
from mentor.telegram import iter_chunks
from mentor.textutil import command_prefix, quiz_competency_arg

POLL_TIMEOUT_S = 30
HTTP_TIMEOUT_S = POLL_TIMEOUT_S + 10
MAX_BACKOFF_S = 30

DEFAULT_REPO_URL = "https://github.com/MikhailBolt/ai-agent-ds-mentor"

BOT_COMMANDS: tuple[tuple[str, str], ...] = (
    ("start", "Начать и помощь"),
    ("quiz", "Новый вопрос"),
    ("practice", "Вопрос по слабой теме"),
    ("map", "Карта компетенций"),
    ("topics", "Список тем (id)"),
    ("hint", "Подсказка к вопросу"),
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
        commands = [
            {"command": name, "description": desc} for name, desc in BOT_COMMANDS
        ]
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
        "/quiz <id> — вопрос по теме, напр. /quiz ml-metrics\n"
        "/practice — вопрос по самой слабой/новой теме\n"
        "/map — карта компетенций и прогресс\n"
        "/topics — список id тем\n"
        "/skip или /cancel — пропустить текущий вопрос\n"
        "/stats, /progress — статистика и прогресс по банку\n"
        "/hint — подсказка к текущему вопросу\n"
        "/status — состояние бота\n"
        "/about — версия и ссылка на проект\n"
        "/reset — сбросить прогресс\n"
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
    return f"{meta}\n{q.prompt}\n\nОтветь одним сообщением."


def streak_bonus_message(streak: int) -> str:
    if streak in (3, 5, 10):
        return f" Серия верных ответов: {streak}!"
    return ""


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
    lines.append("\nНапиши /quiz или /practice для следующего вопроса.")
    return "\n".join(lines)


def deliver_quiz_question(
    api: TelegramAPI,
    conn: sqlite3.Connection,
    chat_id: int,
    questions: list[mentor_quiz.Question],
    competencies: list[mentor_comp.Competency],
    *,
    comp_filter: str = "",
    intro: str | None = None,
) -> None:
    comp_index = mentor_comp.competency_by_id(competencies)
    if comp_filter and comp_filter not in comp_index:
        ids = ", ".join(c.id for c in competencies)
        api.send_message(
            chat_id,
            f"Неизвестная компетенция «{comp_filter}».\n"
            f"Доступные id: {ids}\n/topics — список тем",
        )
        return

    prev = mentor_db.get_active_question(conn, chat_id)
    seen_ids = mentor_db.get_seen_question_ids(conn, chat_id)
    comp_stats = mentor_db.get_competency_stats(conn, chat_id)
    weights = mentor_quiz.competency_weights_for_practice(
        comp_stats,
        (c.id for c in competencies),
    )
    try:
        q = mentor_quiz.pick_next(
            questions,
            prev,
            competency_filter=comp_filter or None,
            competency_weights=weights if not comp_filter else None,
            seen_ids=seen_ids,
        )
    except ValueError:
        api.send_message(
            chat_id,
            "Нет вопросов по этой теме. Попробуй /map или /quiz без аргумента.",
        )
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


def format_status_text(
    *,
    started_at: float,
    now: float,
    question_count: int,
    stats: mentor_db.Stats,
    streak: int = 0,
    best_streak: int = 0,
    bank_seen: int = 0,
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
    ]
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

    if cmd in {"/start", "/help"}:
        api.send_message(chat_id, _help_text())
        return

    if cmd in {"/map", "/competencies"}:
        comp_stats = mentor_db.get_competency_stats(conn, chat_id)
        api.send_message(
            chat_id,
            mentor_comp.format_competency_map(
                competencies,
                comp_stats,
                bank_counts=bank_counts,
            ),
        )
        return

    if cmd == "/topics":
        api.send_message(
            chat_id,
            mentor_comp.format_topics_list(competencies, bank_counts),
        )
        return

    if cmd in {"/practice", "/weak"}:
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

    if cmd in {"/stats", "/progress"}:
        st = mentor_db.get_stats(conn, chat_id)
        streak = mentor_db.get_streak(conn, chat_id)
        best = mentor_db.get_best_streak(conn, chat_id)
        seen = mentor_db.get_seen_question_ids(conn, chat_id)
        comp_stats = mentor_db.get_competency_stats(conn, chat_id)
        api.send_message(
            chat_id,
            mentor_comp.format_stats_summary(
                correct=st.correct,
                total=st.total,
                streak=streak,
                best_streak=best,
                bank_total=len(questions),
                bank_seen=len(seen),
                competencies=competencies,
                comp_stats=comp_stats,
            ),
        )
        return

    if cmd == "/hint":
        active = mentor_db.get_active_question(conn, chat_id)
        if active is None:
            api.send_message(chat_id, "Сейчас нет активного вопроса. Напиши /quiz.")
            return
        q = mentor_quiz.find_by_id(questions, active)
        if q is None or not q.hint:
            api.send_message(chat_id, "Для этого вопроса подсказки нет.")
            return
        api.send_message(chat_id, f"Подсказка: {q.hint}")
        return

    if cmd == "/status":
        st = mentor_db.get_stats(conn, chat_id)
        streak = mentor_db.get_streak(conn, chat_id)
        best = mentor_db.get_best_streak(conn, chat_id)
        seen = len(mentor_db.get_seen_question_ids(conn, chat_id))
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
                active_question_id=active,
            ),
        )
        return

    if cmd == "/about":
        api.send_message(chat_id, about_message_text())
        return

    if cmd == "/reset":
        mentor_db.reset_user(conn, chat_id)
        api.send_message(chat_id, "Готово. Прогресс сброшен. Напиши /quiz чтобы начать заново.")
        return

    if cmd in {"/skip", "/cancel"}:
        active = mentor_db.get_active_question(conn, chat_id)
        if active is None:
            api.send_message(chat_id, "Сейчас нет активного вопроса. Напиши /quiz.")
            return
        mentor_db.set_active_question(conn, chat_id, None)
        api.send_message(chat_id, "Ок, пропустили. Напиши /quiz чтобы получить следующий вопрос.")
        return

    if cmd == "/quiz":
        try:
            comp_filter = quiz_competency_arg(text)
        except ValueError:
            comp_filter = ""
        deliver_quiz_question(
            api,
            conn,
            chat_id,
            questions,
            competencies,
            comp_filter=comp_filter,
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

        is_correct = q.matches(text)
        streak = mentor_db.record_quiz_result(
            conn,
            chat_id,
            is_correct=is_correct,
            competency_id=q.competency_id,
        )
        mentor_db.record_question_attempt(
            conn, chat_id, q.id, is_correct=is_correct
        )
        mentor_db.set_active_question(conn, chat_id, None)
        if is_correct:
            bonus = streak_bonus_message(streak)
            seen = mentor_db.get_seen_question_ids(conn, chat_id)
            bank_done = ""
            if len(seen) >= len(questions):
                bank_done = "\nТы прошёл все вопросы банка — дальше будут повторы."
            api.send_message(
                chat_id,
                f"Верно. Отлично!{bonus}{bank_done}\nНапиши /quiz или /map.",
            )
        else:
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
