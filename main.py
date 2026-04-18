import logging
import os
import random
import signal
import sqlite3
import time
from typing import Any, Optional

import requests
from dotenv import load_dotenv

from mentor import db as mentor_db
from mentor import quiz as mentor_quiz


POLL_TIMEOUT_S = 30
HTTP_TIMEOUT_S = POLL_TIMEOUT_S + 10
MAX_BACKOFF_S = 30


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(
            f"Missing env var {name}. Create a .env file or export it before запуском."
        )
    return value


def command_prefix(text: str) -> Optional[str]:
    """`/cmd` или `/cmd@BotUsername` → нормализованный префикс `/cmd` в нижнем регистре."""
    t = (text or "").strip()
    if not t.startswith("/"):
        return None
    head = t.split(maxsplit=1)[0]
    return head.split("@", 1)[0].lower()


class TelegramAPI:
    def __init__(self, token: str) -> None:
        self._base = f"https://api.telegram.org/bot{token}"
        self._s = requests.Session()

    def request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base}/{method}"
        attempts = 0
        while True:
            try:
                r = self._s.post(url, json=payload, timeout=HTTP_TIMEOUT_S)
            except (requests.RequestException, ValueError) as e:
                raise RuntimeError(f"HTTP/JSON error calling {method}: {e}") from e

            if r.status_code == 429:
                attempts += 1
                if attempts > 8:
                    raise RuntimeError("Telegram API: too many 429 responses for " + method)
                retry = r.headers.get("Retry-After")
                try:
                    wait_s = float(retry) if retry is not None else min(5.0 * attempts, 60.0)
                except ValueError:
                    wait_s = min(5.0 * attempts, 60.0)
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
        self.request("sendMessage", {"chat_id": chat_id, "text": text})

    def get_updates(self, offset: Optional[int]) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": POLL_TIMEOUT_S,
            "allowed_updates": ["message"],
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
        "/quiz — задать вопрос\n"
        "/skip или /cancel — пропустить текущий вопрос\n"
        "/stats — статистика\n"
        "/reset — сбросить прогресс\n"
        "/help — помощь\n\n"
        "Если бот задал вопрос — просто ответь сообщением."
    )


def _format_question(q: mentor_quiz.Question) -> str:
    return f"Вопрос ({q.id}):\n{q.prompt}\n\nОтветь одним сообщением."


def handle_text(
    api: TelegramAPI,
    conn: sqlite3.Connection,
    questions: list[mentor_quiz.Question],
    chat_id: int,
    text: str,
) -> None:
    text = (text or "").strip()

    mentor_db.touch_user(conn, chat_id)

    cmd = command_prefix(text)
    if cmd in {"/start", "/help"}:
        api.send_message(chat_id, _help_text())
        return

    if cmd == "/stats":
        st = mentor_db.get_stats(conn, chat_id)
        acc = (st.correct / st.total * 100.0) if st.total else 0.0
        api.send_message(
            chat_id,
            f"Статистика:\nВерно: {st.correct}\nВсего: {st.total}\nТочность: {acc:.1f}%",
        )
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
        prev = mentor_db.get_active_question(conn, chat_id)
        q = mentor_quiz.pick_next(questions, exclude_id=prev)
        mentor_db.set_active_question(conn, chat_id, q.id)
        api.send_message(chat_id, _format_question(q))
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
        mentor_db.record_quiz_result(conn, chat_id, is_correct=is_correct)
        mentor_db.set_active_question(conn, chat_id, None)
        if is_correct:
            api.send_message(chat_id, "Верно. Отлично! Напиши /quiz для следующего вопроса.")
        else:
            api.send_message(
                chat_id,
                f"Пока не зачтено.\nОжидаемый ответ (пример): {q.answer}\n\nНапиши /quiz для следующего вопроса.",
            )
        return

    api.send_message(chat_id, "Команда не распознана. Напиши /help")


def main() -> None:
    load_dotenv()
    token = _require_env("TELEGRAM_BOT_TOKEN")
    db_path = os.getenv("DB_PATH", "bot.db")
    questions_path = os.getenv("QUESTIONS_PATH", os.path.join("data", "questions.json"))

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    log = logging.getLogger("ai-agent-ds-mentor")

    api = TelegramAPI(token)
    conn = mentor_db.connect(db_path)
    mentor_db.ensure_schema(conn)
    questions = mentor_quiz.load_questions(questions_path)

    offset: Optional[int] = None
    backoff_s = 1.0

    running = True

    def stop_running(*_: Any) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop_running)
    try:
        signal.signal(signal.SIGTERM, stop_running)
    except (AttributeError, ValueError):
        pass

    log.info("Bot started (polling)")
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
                if not isinstance(msg, dict):
                    continue
                chat = msg.get("chat")
                if not isinstance(chat, dict):
                    continue
                chat_id = chat.get("id")
                if not isinstance(chat_id, int):
                    continue

                text = msg.get("text")
                if not isinstance(text, str):
                    continue

                try:
                    handle_text(api, conn, questions, chat_id, text)
                except Exception:
                    log.exception("Failed to handle message")
    except KeyboardInterrupt:
        log.info("Keyboard interrupt; stopping")
    finally:
        conn.close()
        log.info("SQLite connection closed")


if __name__ == "__main__":
    main()
