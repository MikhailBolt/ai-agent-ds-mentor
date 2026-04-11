import os
import re
import json
import time
import sqlite3
import logging
from typing import Any, Dict, List, Optional, Tuple

import requests


# =========================
# Config
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3").strip()
DB_PATH = os.getenv("DB_PATH", "app.db").strip()
POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "2"))
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "120"))

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set.")

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# =========================
# Database
# =========================
def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        goal TEXT DEFAULT '',
        level TEXT DEFAULT '',
        daily_minutes INTEGER DEFAULT 30,
        strengths_json TEXT DEFAULT '[]',
        weak_topics_json TEXT DEFAULT '[]',
        completed_topics_json TEXT DEFAULT '[]',
        current_plan TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS quiz_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        topic TEXT NOT NULL,
        questions_json TEXT NOT NULL,
        current_index INTEGER DEFAULT 0,
        score INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS quiz_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_session_id INTEGER NOT NULL,
        question_index INTEGER NOT NULL,
        user_answer TEXT,
        correct_answer TEXT,
        is_correct INTEGER,
        feedback TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS study_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        topic TEXT DEFAULT '',
        payload_json TEXT DEFAULT '{}',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


def upsert_user(user_id: int, username: str, first_name: str) -> None:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO users (user_id, username, first_name, updated_at)
    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(user_id) DO UPDATE SET
        username = excluded.username,
        first_name = excluded.first_name,
        updated_at = CURRENT_TIMESTAMP
    """, (user_id, username, first_name))

    conn.commit()
    conn.close()


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def update_user_profile(
    user_id: int,
    goal: Optional[str] = None,
    level: Optional[str] = None,
    daily_minutes: Optional[int] = None,
    strengths: Optional[List[str]] = None,
    weak_topics: Optional[List[str]] = None,
    completed_topics: Optional[List[str]] = None,
    current_plan: Optional[str] = None,
) -> None:
    conn = get_db_connection()
    cur = conn.cursor()

    fields = []
    values: List[Any] = []

    if goal is not None:
        fields.append("goal = ?")
        values.append(goal)

    if level is not None:
        fields.append("level = ?")
        values.append(level)

    if daily_minutes is not None:
        fields.append("daily_minutes = ?")
        values.append(daily_minutes)

    if strengths is not None:
        fields.append("strengths_json = ?")
        values.append(json.dumps(strengths, ensure_ascii=False))

    if weak_topics is not None:
        fields.append("weak_topics_json = ?")
        values.append(json.dumps(weak_topics, ensure_ascii=False))

    if completed_topics is not None:
        fields.append("completed_topics_json = ?")
        values.append(json.dumps(completed_topics, ensure_ascii=False))

    if current_plan is not None:
        fields.append("current_plan = ?")
        values.append(current_plan)

    fields.append("updated_at = CURRENT_TIMESTAMP")

    if not fields:
        conn.close()
        return

    values.append(user_id)
    query = f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?"
    cur.execute(query, values)
    conn.commit()
    conn.close()


def log_study_event(user_id: int, event_type: str, topic: str = "", payload: Optional[Dict[str, Any]] = None) -> None:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO study_history (user_id, event_type, topic, payload_json)
    VALUES (?, ?, ?, ?)
    """, (user_id, event_type, topic, json.dumps(payload or {}, ensure_ascii=False)))

    conn.commit()
    conn.close()


def create_quiz_session(user_id: int, topic: str, questions: List[Dict[str, Any]]) -> int:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO quiz_sessions (user_id, topic, questions_json, current_index, score, status)
    VALUES (?, ?, ?, 0, 0, 'active')
    """, (user_id, topic, json.dumps(questions, ensure_ascii=False)))

    session_id = cur.lastrowid
    conn.commit()
    conn.close()
    return session_id


def get_active_quiz_session(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT * FROM quiz_sessions
    WHERE user_id = ? AND status = 'active'
    ORDER BY id DESC
    LIMIT 1
    """, (user_id,))

    row = cur.fetchone()
    conn.close()
    return row


def update_quiz_session(session_id: int, current_index: int, score: int, status: str) -> None:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    UPDATE quiz_sessions
    SET current_index = ?, score = ?, status = ?
    WHERE id = ?
    """, (current_index, score, status, session_id))

    conn.commit()
    conn.close()


def save_quiz_answer(
    quiz_session_id: int,
    question_index: int,
    user_answer: str,
    correct_answer: str,
    is_correct: bool,
    feedback: str,
) -> None:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO quiz_answers (
        quiz_session_id, question_index, user_answer, correct_answer, is_correct, feedback
    ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        quiz_session_id,
        question_index,
        user_answer,
        correct_answer,
        1 if is_correct else 0,
        feedback,
    ))

    conn.commit()
    conn.close()


# =========================
# Telegram API
# =========================
def telegram_get_updates(offset: Optional[int] = None, timeout: int = 30) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset

    response = requests.get(
        f"{TELEGRAM_API_BASE}/getUpdates",
        params=params,
        timeout=timeout + 10,
    )
    response.raise_for_status()
    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(f"Telegram getUpdates error: {data}")

    return data.get("result", [])


def telegram_send_message(chat_id: int, text: str) -> None:
    payload = {
        "chat_id": chat_id,
        "text": text[:4000],
    }
    response = requests.post(
        f"{TELEGRAM_API_BASE}/sendMessage",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()


# =========================
# LLM helpers
# =========================
def call_ollama(prompt: str, system: Optional[str] = None) -> str:
    full_prompt = prompt if not system else f"{system}\n\n{prompt}"

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": full_prompt,
            "stream": False,
        },
        timeout=LLM_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    return str(data.get("response", "")).strip()


def extract_json_from_text(text: str) -> Any:
    text = text.strip()

    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[len("```"):].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise


def llm_json(prompt: str, system: Optional[str] = None, retries: int = 3) -> Any:
    last_error: Optional[Exception] = None

    for _ in range(retries):
        raw = call_ollama(prompt=prompt, system=system)
        try:
            return extract_json_from_text(raw)
        except Exception as e:
            last_error = e
            prompt = "Return ONLY valid JSON. No markdown fences.\n\n" + prompt

    raise ValueError(f"LLM did not return valid JSON: {last_error}")


# =========================
# Agent prompts
# =========================
PLANNER_SYSTEM = """
You are Planner Agent.
You create concise, practical Data Science learning plans.
Always adapt to the user's goal, level, daily time, strengths, and weak topics.
"""

TUTOR_SYSTEM = """
You are Tutor Agent.
You explain Data Science topics clearly, with examples and short practical intuition.
Keep explanations readable and structured.
"""

QUIZ_SYSTEM = """
You are Quiz Agent.
You create short, focused quizzes for Data Science learning.
Questions must be clear and unambiguous.
"""

REVIEWER_SYSTEM = """
You are Reviewer Agent.
You evaluate learner answers, explain mistakes, and suggest next steps.
Be constructive and specific.
"""

PROGRESS_SYSTEM = """
You are Progress Agent.
You infer strengths, weak topics, and next recommendations from the learner's recent activity.
Return concise and useful feedback.
"""


# =========================
# Agent logic
# =========================
def planner_agent(user_row: sqlite3.Row) -> str:
    strengths = json.loads(user_row["strengths_json"] or "[]")
    weak_topics = json.loads(user_row["weak_topics_json"] or "[]")
    completed_topics = json.loads(user_row["completed_topics_json"] or "[]")

    prompt = f"""
Build a 2-week personalized Data Science study plan.

Return plain text only.

User profile:
- Goal: {user_row["goal"]}
- Level: {user_row["level"]}
- Daily minutes: {user_row["daily_minutes"]}
- Strengths: {strengths}
- Weak topics: {weak_topics}
- Completed topics: {completed_topics}

Requirements:
- Make it practical
- Split by days
- Include theory + practice
- Focus on high-value DS skills
- Keep it concise
"""
    return call_ollama(prompt, PLANNER_SYSTEM)


def tutor_agent(topic: str, user_row: sqlite3.Row) -> str:
    prompt = f"""
Explain this Data Science topic for the user:

Topic: {topic}

User:
- Goal: {user_row["goal"]}
- Level: {user_row["level"]}

Requirements:
- Use simple language
- Include intuition
- Include one short example
- Include 3 bullet takeaways at the end
- Keep it under 350 words
"""
    return call_ollama(prompt, TUTOR_SYSTEM)


def quiz_agent(topic: str, user_row: sqlite3.Row, num_questions: int = 5) -> List[Dict[str, Any]]:
    prompt = f"""
Generate a Data Science quiz.

Return ONLY valid JSON as an array with this schema:
[
  {{
    "question": "string",
    "options": ["A", "B", "C", "D"],
    "correct_answer": "one option exactly",
    "explanation": "string"
  }}
]

User:
- Goal: {user_row["goal"]}
- Level: {user_row["level"]}

Topic: {topic}
Questions: {num_questions}

Rules:
- Questions must match the user's level
- Exactly 4 options
- 1 correct answer
- Plausible distractors
- Short explanation
"""
    data = llm_json(prompt, QUIZ_SYSTEM)

    if not isinstance(data, list):
        raise ValueError("Quiz Agent returned invalid format.")

    cleaned: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue

        question = str(item.get("question", "")).strip()
        options = item.get("options", [])
        correct_answer = str(item.get("correct_answer", "")).strip()
        explanation = str(item.get("explanation", "")).strip()

        if not question or not isinstance(options, list) or len(options) != 4:
            continue
        if correct_answer not in options:
            continue

        cleaned.append({
            "question": question,
            "options": [str(x).strip() for x in options],
            "correct_answer": correct_answer,
            "explanation": explanation,
        })

    if not cleaned:
        raise ValueError("No valid quiz questions generated.")

    return cleaned[:num_questions]


def reviewer_agent(
    question: str,
    correct_answer: str,
    explanation: str,
    user_answer: str,
) -> Tuple[bool, str]:
    normalized_user = user_answer.strip().lower()
    normalized_correct = correct_answer.strip().lower()

    is_correct = normalized_user == normalized_correct

    prompt = f"""
Evaluate the learner's answer.

Question: {question}
Correct answer: {correct_answer}
Explanation: {explanation}
Learner answer: {user_answer}

Return plain text only.

Requirements:
- First line: Correct or Incorrect
- Then explain why
- Then give one short improvement suggestion
- Keep it under 120 words
"""
    feedback = call_ollama(prompt, REVIEWER_SYSTEM)
    return is_correct, feedback


def progress_agent(user_row: sqlite3.Row) -> str:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT event_type, topic, payload_json, created_at
    FROM study_history
    WHERE user_id = ?
    ORDER BY id DESC
    LIMIT 20
    """, (user_row["user_id"],))

    history = [dict(row) for row in cur.fetchall()]
    conn.close()

    prompt = f"""
Analyze learner progress.

Return plain text only.

User profile:
- Goal: {user_row["goal"]}
- Level: {user_row["level"]}
- Daily minutes: {user_row["daily_minutes"]}
- Strengths: {user_row["strengths_json"]}
- Weak topics: {user_row["weak_topics_json"]}
- Completed topics: {user_row["completed_topics_json"]}

Recent history:
{json.dumps(history, ensure_ascii=False, indent=2)}

Requirements:
- Summarize current progress
- Mention strong topics
- Mention weak topics
- Give next 3 recommendations
- Keep it concise
"""
    return call_ollama(prompt, PROGRESS_SYSTEM)


# =========================
# Command handlers
# =========================
def format_help() -> str:
    return (
        "🤖 AI Agent DS Mentor\n\n"
        "Commands:\n"
        "/start - start the bot\n"
        "/help - show help\n"
        "/setgoal <text> - set your learning goal\n"
        "/setlevel <beginner|junior|middle> - set your level\n"
        "/settime <minutes> - set daily study time\n"
        "/plan - build a personal study plan\n"
        "/topic <topic> - explain a DS topic\n"
        "/quiz <topic> - start a quiz on a topic\n"
        "/answer <option text> - answer current quiz question\n"
        "/progress - show your current progress\n"
    )


def handle_start(chat_id: int, user_id: int, first_name: str) -> None:
    text = (
        f"Привет, {first_name}! 👋\n\n"
        "Я AI agent для развития компетенций в Data Science.\n"
        "Я могу:\n"
        "- строить персональный план обучения\n"
        "- объяснять темы\n"
        "- генерировать квизы\n"
        "- проверять ответы\n"
        "- отслеживать прогресс\n\n"
        "Начни с:\n"
        "/setgoal Хочу подготовиться к DS интервью\n"
        "/setlevel junior\n"
        "/settime 60\n\n"
        "Потом вызови /plan"
    )
    telegram_send_message(chat_id, text)


def handle_set_goal(chat_id: int, user_id: int, text: str) -> None:
    goal = text.strip()
    if not goal:
        telegram_send_message(chat_id, "Используй: /setgoal <твоя цель>")
        return

    update_user_profile(user_id, goal=goal)
    log_study_event(user_id, "set_goal", payload={"goal": goal})
    telegram_send_message(chat_id, f"Цель сохранена ✅\n\n{goal}")


def handle_set_level(chat_id: int, user_id: int, text: str) -> None:
    level = text.strip().lower()
    allowed = {"beginner", "junior", "middle", "advanced"}

    if level not in allowed:
        telegram_send_message(chat_id, "Используй: /setlevel beginner|junior|middle|advanced")
        return

    update_user_profile(user_id, level=level)
    log_study_event(user_id, "set_level", payload={"level": level})
    telegram_send_message(chat_id, f"Уровень сохранён ✅\n\n{level}")


def handle_set_time(chat_id: int, user_id: int, text: str) -> None:
    text = text.strip()
    if not text.isdigit():
        telegram_send_message(chat_id, "Используй: /settime 60")
        return

    minutes = int(text)
    if minutes <= 0 or minutes > 600:
        telegram_send_message(chat_id, "Укажи разумное количество минут, например 30, 60 или 90.")
        return

    update_user_profile(user_id, daily_minutes=minutes)
    log_study_event(user_id, "set_time", payload={"daily_minutes": minutes})
    telegram_send_message(chat_id, f"Ежедневное время сохранено ✅\n\n{minutes} минут")


def handle_plan(chat_id: int, user_id: int) -> None:
    user_row = get_user(user_id)
    if user_row is None:
        telegram_send_message(chat_id, "Сначала напиши /start")
        return

    if not user_row["goal"] or not user_row["level"]:
        telegram_send_message(
            chat_id,
            "Сначала задай цель и уровень:\n"
            "/setgoal ...\n"
            "/setlevel junior"
        )
        return

    telegram_send_message(chat_id, "Строю персональный план... ⏳")
    plan = planner_agent(user_row)
    update_user_profile(user_id, current_plan=plan)
    log_study_event(user_id, "plan_generated", payload={"plan": plan})
    telegram_send_message(chat_id, plan[:4000])


def handle_topic(chat_id: int, user_id: int, topic: str) -> None:
    topic = topic.strip()
    if not topic:
        telegram_send_message(chat_id, "Используй: /topic pandas")
        return

    user_row = get_user(user_id)
    if user_row is None:
        telegram_send_message(chat_id, "Сначала напиши /start")
        return

    telegram_send_message(chat_id, f"Готовлю объяснение по теме: {topic} ⏳")
    answer = tutor_agent(topic, user_row)
    log_study_event(user_id, "topic_explained", topic=topic, payload={"topic": topic})
    telegram_send_message(chat_id, answer[:4000])


def handle_quiz(chat_id: int, user_id: int, topic: str) -> None:
    topic = topic.strip()
    if not topic:
        telegram_send_message(chat_id, "Используй: /quiz pandas")
        return

    user_row = get_user(user_id)
    if user_row is None:
        telegram_send_message(chat_id, "Сначала напиши /start")
        return

    telegram_send_message(chat_id, f"Генерирую квиз по теме: {topic} ⏳")
    questions = quiz_agent(topic, user_row, num_questions=5)
    session_id = create_quiz_session(user_id, topic, questions)

    log_study_event(user_id, "quiz_started", topic=topic, payload={"session_id": session_id})

    send_next_quiz_question(chat_id, user_id)


def send_next_quiz_question(chat_id: int, user_id: int) -> None:
    session = get_active_quiz_session(user_id)
    if session is None:
        telegram_send_message(chat_id, "У тебя нет активного квиза. Запусти: /quiz <topic>")
        return

    questions = json.loads(session["questions_json"])
    current_index = int(session["current_index"])

    if current_index >= len(questions):
        score = int(session["score"])
        total = len(questions)
        update_quiz_session(session["id"], current_index, score, "completed")
        telegram_send_message(
            chat_id,
            f"Квиз завершён ✅\n\nРезультат: {score}/{total}"
        )
        log_study_event(
            user_id,
            "quiz_completed",
            topic=session["topic"],
            payload={"score": score, "total": total}
        )
        return

    q = questions[current_index]
    options_text = "\n".join([f"- {opt}" for opt in q["options"]])

    text = (
        f"Вопрос {current_index + 1}/{len(questions)}\n"
        f"Тема: {session['topic']}\n\n"
        f"{q['question']}\n\n"
        f"{options_text}\n\n"
        f"Ответь командой:\n"
        f"/answer <вариант>"
    )
    telegram_send_message(chat_id, text)


def handle_answer(chat_id: int, user_id: int, user_answer: str) -> None:
    user_answer = user_answer.strip()
    if not user_answer:
        telegram_send_message(chat_id, "Используй: /answer <твой вариант>")
        return

    session = get_active_quiz_session(user_id)
    if session is None:
        telegram_send_message(chat_id, "Нет активного квиза. Запусти: /quiz <topic>")
        return

    questions = json.loads(session["questions_json"])
    current_index = int(session["current_index"])

    if current_index >= len(questions):
        telegram_send_message(chat_id, "Квиз уже завершён.")
        return

    q = questions[current_index]
    correct_answer = q["correct_answer"]
    explanation = q["explanation"]

    is_correct, feedback = reviewer_agent(
        question=q["question"],
        correct_answer=correct_answer,
        explanation=explanation,
        user_answer=user_answer,
    )

    new_score = int(session["score"]) + (1 if is_correct else 0)
    new_index = current_index + 1
    new_status = "completed" if new_index >= len(questions) else "active"

    save_quiz_answer(
        quiz_session_id=session["id"],
        question_index=current_index,
        user_answer=user_answer,
        correct_answer=correct_answer,
        is_correct=is_correct,
        feedback=feedback,
    )

    update_quiz_session(
        session_id=session["id"],
        current_index=new_index,
        score=new_score,
        status=new_status,
    )

    log_study_event(
        user_id,
        "quiz_answered",
        topic=session["topic"],
        payload={
            "question": q["question"],
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "is_correct": is_correct,
        }
    )

    telegram_send_message(chat_id, feedback[:4000])

    if new_status == "completed":
        total = len(questions)
        telegram_send_message(chat_id, f"Квиз завершён ✅\n\nИтог: {new_score}/{total}")
    else:
        send_next_quiz_question(chat_id, user_id)


def handle_progress(chat_id: int, user_id: int) -> None:
    user_row = get_user(user_id)
    if user_row is None:
        telegram_send_message(chat_id, "Сначала напиши /start")
        return

    telegram_send_message(chat_id, "Анализирую прогресс... ⏳")
    report = progress_agent(user_row)
    telegram_send_message(chat_id, report[:4000])


# =========================
# Router
# =========================
def parse_command(text: str) -> Tuple[str, str]:
    if not text.startswith("/"):
        return "", text

    parts = text.split(" ", 1)
    command = parts[0].strip().lower()
    args = parts[1].strip() if len(parts) > 1 else ""
    return command, args


def handle_message(message: Dict[str, Any]) -> None:
    chat = message.get("chat", {})
    chat_id = chat.get("id")

    from_user = message.get("from", {})
    user_id = from_user.get("id")
    username = from_user.get("username", "") or ""
    first_name = from_user.get("first_name", "") or "friend"

    text = message.get("text", "")
    if not chat_id or not user_id or not text:
        return

    upsert_user(user_id, username, first_name)

    command, args = parse_command(text)

    try:
        if command == "/start":
            handle_start(chat_id, user_id, first_name)
        elif command == "/help":
            telegram_send_message(chat_id, format_help())
        elif command == "/setgoal":
            handle_set_goal(chat_id, user_id, args)
        elif command == "/setlevel":
            handle_set_level(chat_id, user_id, args)
        elif command == "/settime":
            handle_set_time(chat_id, user_id, args)
        elif command == "/plan":
            handle_plan(chat_id, user_id)
        elif command == "/topic":
            handle_topic(chat_id, user_id, args)
        elif command == "/quiz":
            handle_quiz(chat_id, user_id, args)
        elif command == "/answer":
            handle_answer(chat_id, user_id, args)
        elif command == "/progress":
            handle_progress(chat_id, user_id)
        else:
            telegram_send_message(
                chat_id,
                "Я пока понимаю команды.\n\nНапиши /help"
            )
    except Exception as e:
        logging.exception("Error while handling message")
        telegram_send_message(chat_id, f"Произошла ошибка: {e}")


# =========================
# Main loop
# =========================
def run_bot() -> None:
    init_db()
    logging.info("Bot started.")

    offset: Optional[int] = None

    while True:
        try:
            updates = telegram_get_updates(offset=offset, timeout=30)

            for update in updates:
                offset = update["update_id"] + 1

                message = update.get("message")
                if not message:
                    continue

                handle_message(message)

        except requests.RequestException as e:
            logging.exception("Network error: %s", e)
            time.sleep(5)
        except Exception as e:
            logging.exception("Unexpected error: %s", e)
            time.sleep(5)

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_bot()