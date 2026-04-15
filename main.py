import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv


load_dotenv()

# =========================
# Config
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3").strip()
DB_PATH = os.getenv("DB_PATH", "app.db").strip()
POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "2"))
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
ENABLE_REMINDERS = os.getenv("ENABLE_REMINDERS", "true").lower() == "true"
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "19"))
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "ru").strip().lower()

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set.")

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# =========================
# Utilities
# =========================
def retry_on_failure(max_retries: int = MAX_RETRIES, delay: int = 2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_error = exc
                    if attempt < max_retries - 1:
                        wait_time = delay * (attempt + 1)
                        logging.warning("Retry %s/%s for %s due to: %s", attempt + 1, max_retries, func.__name__, exc)
                        time.sleep(wait_time)
            raise last_error
        return wrapper
    return decorator


def safe_parse_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, str):
            return int(value.strip())
        if isinstance(value, (int, float)):
            return int(value)
    except (ValueError, TypeError):
        pass
    return default


def format_duration(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} мин"
    hours = minutes // 60
    rest = minutes % 60
    if rest == 0:
        return f"{hours} ч"
    return f"{hours} ч {rest} мин"


def trim_message(text: str, limit: int = 3900) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def json_loads_safe(text: str, default: Any) -> Any:
    try:
        return json.loads(text) if text else default
    except Exception:
        return default


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
        last_name TEXT,
        goal TEXT DEFAULT '',
        level TEXT DEFAULT '',
        daily_minutes INTEGER DEFAULT 30,
        strengths_json TEXT DEFAULT '[]',
        weak_topics_json TEXT DEFAULT '[]',
        completed_topics_json TEXT DEFAULT '[]',
        preferred_topics_json TEXT DEFAULT '[]',
        current_plan TEXT DEFAULT '',
        language TEXT DEFAULT 'ru',
        notifications_enabled INTEGER DEFAULT 1,
        total_study_minutes INTEGER DEFAULT 0,
        streak_days INTEGER DEFAULT 0,
        last_study_date TEXT,
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
        difficulty TEXT DEFAULT 'medium',
        status TEXT DEFAULT 'active',
        started_at TEXT DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT
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
        response_time INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS study_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        topic TEXT DEFAULT '',
        subtopic TEXT DEFAULT '',
        duration_minutes INTEGER DEFAULT 0,
        payload_json TEXT DEFAULT '{}',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        achievement_type TEXT NOT NULL,
        achievement_name TEXT NOT NULL,
        achieved_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, achievement_type)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        goal_date TEXT NOT NULL,
        target_minutes INTEGER DEFAULT 30,
        actual_minutes INTEGER DEFAULT 0,
        completed INTEGER DEFAULT 0,
        UNIQUE(user_id, goal_date)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        topic TEXT DEFAULT '',
        tags_json TEXT DEFAULT '[]',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS learning_resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        title TEXT NOT NULL,
        url TEXT,
        description TEXT,
        difficulty TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("SELECT COUNT(*) as cnt FROM learning_resources")
    if cur.fetchone()["cnt"] == 0:
        resources = [
            ("python", "course", "Python for Data Science", "https://www.datacamp.com/courses/intro-to-python-for-data-science", "Python basics for analytics", "beginner"),
            ("pandas", "documentation", "Pandas Documentation", "https://pandas.pydata.org/docs/", "Official docs for Pandas", "intermediate"),
            ("statistics", "course", "Khan Academy Statistics", "https://www.khanacademy.org/math/statistics-probability", "Statistics fundamentals", "beginner"),
            ("machine learning", "book", "Hands-On Machine Learning", "https://www.oreilly.com/library/view/hands-on-machine-learning/9781492032632/", "Practical machine learning book", "advanced"),
        ]
        cur.executemany("""
        INSERT INTO learning_resources (topic, resource_type, title, url, description, difficulty)
        VALUES (?, ?, ?, ?, ?, ?)
        """, resources)

    conn.commit()
    conn.close()


def upsert_user(user_id: int, username: str, first_name: str, last_name: str = "") -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO users (user_id, username, first_name, last_name, language, updated_at)
    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(user_id) DO UPDATE SET
        username = excluded.username,
        first_name = excluded.first_name,
        last_name = excluded.last_name,
        updated_at = CURRENT_TIMESTAMP
    """, (user_id, username, first_name, last_name, DEFAULT_LANGUAGE))
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
    preferred_topics: Optional[List[str]] = None,
    current_plan: Optional[str] = None,
    notifications_enabled: Optional[bool] = None,
    language: Optional[str] = None,
) -> None:
    fields: List[str] = []
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
    if preferred_topics is not None:
        fields.append("preferred_topics_json = ?")
        values.append(json.dumps(preferred_topics, ensure_ascii=False))
    if current_plan is not None:
        fields.append("current_plan = ?")
        values.append(current_plan)
    if notifications_enabled is not None:
        fields.append("notifications_enabled = ?")
        values.append(1 if notifications_enabled else 0)
    if language is not None:
        fields.append("language = ?")
        values.append(language)

    if not fields:
        return

    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(user_id)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?", values)
    conn.commit()
    conn.close()


def log_study_event(user_id: int, event_type: str, topic: str = "", subtopic: str = "", duration_minutes: int = 0, payload: Optional[Dict[str, Any]] = None) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO study_history (user_id, event_type, topic, subtopic, duration_minutes, payload_json)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, event_type, topic, subtopic, duration_minutes, json.dumps(payload or {}, ensure_ascii=False)))
    conn.commit()
    conn.close()


def update_study_time(user_id: int, minutes: int, topic: str = "") -> None:
    today = datetime.now().date().isoformat()
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    UPDATE users
    SET total_study_minutes = total_study_minutes + ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE user_id = ?
    """, (minutes, user_id))

    cur.execute("""
    INSERT INTO daily_goals (user_id, goal_date, target_minutes, actual_minutes, completed)
    VALUES (?, ?, (SELECT daily_minutes FROM users WHERE user_id = ?), ?, 0)
    ON CONFLICT(user_id, goal_date) DO UPDATE SET
        actual_minutes = actual_minutes + excluded.actual_minutes
    """, (user_id, today, user_id, minutes))

    cur.execute("""
    UPDATE daily_goals
    SET completed = CASE WHEN actual_minutes >= target_minutes THEN 1 ELSE 0 END
    WHERE user_id = ? AND goal_date = ?
    """, (user_id, today))

    cur.execute("SELECT last_study_date, streak_days FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    streak = 1
    if row:
        last_study_date = row["last_study_date"]
        current_streak = row["streak_days"] or 0
        if last_study_date:
            last_date = datetime.fromisoformat(last_study_date).date()
            today_date = datetime.now().date()
            if last_date == today_date:
                streak = current_streak
            elif last_date == today_date - timedelta(days=1):
                streak = current_streak + 1
            else:
                streak = 1

    cur.execute("""
    UPDATE users
    SET last_study_date = ?, streak_days = ?
    WHERE user_id = ?
    """, (today, streak, user_id))

    conn.commit()
    conn.close()

    if streak >= 7:
        check_and_award_achievement(user_id, "streak_7", "7 дней обучения подряд")
    if streak >= 30:
        check_and_award_achievement(user_id, "streak_30", "30 дней обучения подряд")
    if minutes >= 60:
        check_and_award_achievement(user_id, "study_60", "1 час обучения за день")


def create_quiz_session(user_id: int, topic: str, questions: List[Dict[str, Any]], difficulty: str = "medium") -> int:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO quiz_sessions (user_id, topic, questions_json, current_index, score, difficulty, status)
    VALUES (?, ?, ?, 0, 0, ?, 'active')
    """, (user_id, topic, json.dumps(questions, ensure_ascii=False), difficulty))
    session_id = cur.lastrowid
    conn.commit()
    conn.close()
    return session_id


def get_active_quiz_session(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT *
    FROM quiz_sessions
    WHERE user_id = ? AND status = 'active'
    ORDER BY id DESC
    LIMIT 1
    """, (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def update_quiz_session(session_id: int, current_index: int, score: int, status: str) -> None:
    completed_at = datetime.now().isoformat() if status == "completed" else None
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    UPDATE quiz_sessions
    SET current_index = ?,
        score = ?,
        status = ?,
        completed_at = CASE WHEN ? IS NOT NULL THEN ? ELSE completed_at END
    WHERE id = ?
    """, (current_index, score, status, completed_at, completed_at, session_id))
    conn.commit()
    conn.close()


def save_quiz_answer(
    quiz_session_id: int,
    question_index: int,
    user_answer: str,
    correct_answer: str,
    is_correct: bool,
    feedback: str,
    response_time: int = 0,
) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO quiz_answers (
        quiz_session_id, question_index, user_answer, correct_answer, is_correct, feedback, response_time
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        quiz_session_id,
        question_index,
        user_answer,
        correct_answer,
        1 if is_correct else 0,
        feedback,
        response_time,
    ))
    conn.commit()
    conn.close()


def check_and_award_achievement(user_id: int, achievement_type: str, achievement_name: str) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
        INSERT INTO achievements (user_id, achievement_type, achievement_name)
        VALUES (?, ?, ?)
        """, (user_id, achievement_type, achievement_name))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def maybe_award_quiz_achievements(user_id: int, score: int, total: int) -> List[str]:
    awarded = []

    if check_and_award_achievement(user_id, "first_quiz", "Первый завершённый квиз"):
        awarded.append("🏆 Первый завершённый квиз")

    if total > 0 and score == total:
        if check_and_award_achievement(user_id, "perfect_quiz", "Идеальный результат в квизе"):
            awarded.append("🏆 Идеальный результат в квизе")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT COUNT(*) as total_correct
    FROM quiz_answers qa
    JOIN quiz_sessions qs ON qa.quiz_session_id = qs.id
    WHERE qs.user_id = ? AND qa.is_correct = 1
    """, (user_id,))
    total_correct = cur.fetchone()["total_correct"]
    conn.close()

    if total_correct >= 10:
        if check_and_award_achievement(user_id, "correct_10", "10 правильных ответов"):
            awarded.append("🏆 10 правильных ответов")

    return awarded


def get_user_achievements(user_id: int) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT achievement_type, achievement_name, achieved_at
    FROM achievements
    WHERE user_id = ?
    ORDER BY achieved_at DESC
    """, (user_id,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_daily_stats(user_id: int) -> Dict[str, Any]:
    today = datetime.now().date().isoformat()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT target_minutes, actual_minutes, completed
    FROM daily_goals
    WHERE user_id = ? AND goal_date = ?
    """, (user_id, today))
    row = cur.fetchone()
    if row:
        conn.close()
        target = row["target_minutes"] or 0
        actual = row["actual_minutes"] or 0
        return {
            "target": target,
            "actual": actual,
            "remaining": max(0, target - actual),
            "completed": bool(row["completed"]),
        }

    cur.execute("SELECT daily_minutes FROM users WHERE user_id = ?", (user_id,))
    user_row = cur.fetchone()
    conn.close()
    target = user_row["daily_minutes"] if user_row else 30
    return {"target": target, "actual": 0, "remaining": target, "completed": False}


def add_note(user_id: int, title: str, content: str, topic: str = "", tags: Optional[List[str]] = None) -> int:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO notes (user_id, title, content, topic, tags_json)
    VALUES (?, ?, ?, ?, ?)
    """, (user_id, title, content, topic, json.dumps(tags or [], ensure_ascii=False)))
    note_id = cur.lastrowid
    conn.commit()
    conn.close()
    return note_id


def get_notes(user_id: int, topic: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    if topic:
        cur.execute("""
        SELECT id, title, content, topic, tags_json, created_at, updated_at
        FROM notes
        WHERE user_id = ? AND topic = ?
        ORDER BY updated_at DESC
        LIMIT 50
        """, (user_id, topic))
    else:
        cur.execute("""
        SELECT id, title, content, topic, tags_json, created_at, updated_at
        FROM notes
        WHERE user_id = ?
        ORDER BY updated_at DESC
        LIMIT 50
        """, (user_id,))
    notes = [dict(row) for row in cur.fetchall()]
    conn.close()
    return notes


def get_resources(topic: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT resource_type, title, url, description, difficulty
    FROM learning_resources
    WHERE lower(topic) LIKE ? OR lower(description) LIKE ?
    LIMIT 10
    """, (f"%{topic.lower()}%", f"%{topic.lower()}%"))
    items = [dict(row) for row in cur.fetchall()]
    conn.close()
    return items


# =========================
# Telegram API
# =========================
@retry_on_failure(max_retries=3)
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


@retry_on_failure(max_retries=3)
def telegram_send_message(chat_id: int, text: str, parse_mode: str = "HTML") -> None:
    payload = {"chat_id": chat_id, "text": trim_message(text), "parse_mode": parse_mode}
    response = requests.post(f"{TELEGRAM_API_BASE}/sendMessage", json=payload, timeout=30)
    response.raise_for_status()


def telegram_send_typing(chat_id: int) -> None:
    try:
        requests.post(
            f"{TELEGRAM_API_BASE}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"},
            timeout=5,
        )
    except Exception:
        pass


# =========================
# LLM helpers
# =========================
@retry_on_failure(max_retries=MAX_RETRIES)
def call_ollama(prompt: str, system: Optional[str] = None) -> str:
    full_prompt = prompt if not system else f"{system}\n\n{prompt}"
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": full_prompt,
            "stream": False,
            "options": {"temperature": 0.7, "top_p": 0.9},
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
    current_prompt = prompt

    for _ in range(retries):
        raw = call_ollama(prompt=current_prompt, system=system)
        try:
            return extract_json_from_text(raw)
        except Exception as exc:
            last_error = exc
            current_prompt = "Return ONLY valid JSON. No markdown fences.\n\n" + prompt

    raise ValueError(f"LLM did not return valid JSON: {last_error}")


# =========================
# Agent systems
# =========================
PLANNER_SYSTEM = """
You are Planner Agent, an expert Data Science learning path designer.
Create concise, practical, personalized, project-based study plans.
"""

TUTOR_SYSTEM = """
You are Tutor Agent, an expert Data Science educator.
Explain clearly, use intuition, practical examples, and simple structure.
"""

QUIZ_SYSTEM = """
You are Quiz Agent, an expert assessment designer.
Create focused questions that test understanding, not memorization only.
"""

REVIEWER_SYSTEM = """
You are Reviewer Agent, a constructive learning coach.
Explain mistakes clearly and encourage progress.
"""

PROGRESS_SYSTEM = """
You are Progress Agent, an analytical learning coach.
Summarize learner progress and recommend the next best actions.
"""

CHALLENGE_SYSTEM = """
You are Challenge Agent.
Generate one concise practical Data Science learning challenge for today.
"""


# =========================
# Agent logic
# =========================
def planner_agent(user_row: sqlite3.Row) -> Dict[str, Any]:
    strengths = json_loads_safe(user_row["strengths_json"], [])
    weak_topics = json_loads_safe(user_row["weak_topics_json"], [])
    completed_topics = json_loads_safe(user_row["completed_topics_json"], [])

    prompt = f"""
Create a personalized 2-week Data Science learning plan as JSON.

Return ONLY valid JSON:
{{
  "overview": "string",
  "weeks": [
    {{
      "week": 1,
      "focus": "string",
      "topics": ["topic1", "topic2"],
      "projects": ["project1"],
      "resources": ["resource1"],
      "daily_schedule": {{
        "monday": "string",
        "tuesday": "string",
        "wednesday": "string"
      }}
    }}
  ],
  "milestones": ["milestone1", "milestone2"],
  "success_criteria": ["criterion1", "criterion2"]
}}

User profile:
- Goal: {user_row["goal"]}
- Level: {user_row["level"]}
- Daily minutes: {user_row["daily_minutes"]}
- Strengths: {strengths}
- Weak topics: {weak_topics}
- Completed topics: {completed_topics}
"""
    return llm_json(prompt, PLANNER_SYSTEM)


def tutor_agent(topic: str, user_row: sqlite3.Row, subtopic: str = "") -> Dict[str, Any]:
    prompt = f"""
Explain this Data Science topic as JSON.

Return ONLY valid JSON:
{{
  "title": "string",
  "overview": "string",
  "key_concepts": ["concept1", "concept2"],
  "detailed_explanation": "string",
  "real_world_example": "string",
  "code_example": "string",
  "common_pitfalls": ["pitfall1", "pitfall2"],
  "practice_exercises": ["exercise1", "exercise2"],
  "key_takeaways": ["takeaway1", "takeaway2", "takeaway3"]
}}

Topic: {topic}
Subtopic: {subtopic}
User goal: {user_row["goal"]}
User level: {user_row["level"]}
"""
    return llm_json(prompt, TUTOR_SYSTEM)


def quiz_agent(topic: str, user_row: sqlite3.Row, num_questions: int = 5, difficulty: str = "medium") -> List[Dict[str, Any]]:
    prompt = f"""
Generate a quiz as JSON array.

Return ONLY valid JSON:
[
  {{
    "question": "string",
    "options": ["A", "B", "C", "D"],
    "correct_answer": "one option exactly",
    "explanation": "string",
    "difficulty": "easy|medium|hard",
    "hint": "string"
  }}
]

User goal: {user_row["goal"]}
User level: {user_row["level"]}
Topic: {topic}
Questions: {num_questions}
Difficulty: {difficulty}
"""
    data = llm_json(prompt, QUIZ_SYSTEM)
    if not isinstance(data, list):
        raise ValueError("Quiz Agent returned invalid format")

    cleaned: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        options = item.get("options", [])
        correct_answer = str(item.get("correct_answer", "")).strip()
        explanation = str(item.get("explanation", "")).strip()
        difficulty_value = str(item.get("difficulty", difficulty)).strip()
        hint = str(item.get("hint", "")).strip()

        if not question or not isinstance(options, list) or len(options) != 4:
            continue
        options = [str(x).strip() for x in options]
        if correct_answer not in options:
            continue

        cleaned.append({
            "question": question,
            "options": options,
            "correct_answer": correct_answer,
            "explanation": explanation,
            "difficulty": difficulty_value,
            "hint": hint,
        })

    if not cleaned:
        raise ValueError("No valid quiz questions generated")

    return cleaned[:num_questions]


def reviewer_agent(question: str, correct_answer: str, explanation: str, user_answer: str) -> Tuple[bool, str, Dict[str, Any]]:
    is_correct = user_answer.strip().lower() == correct_answer.strip().lower()

    prompt = f"""
Evaluate the learner answer and return JSON.

Return ONLY valid JSON:
{{
  "feedback": "string",
  "explanation_of_mistake": "string",
  "improvement_tips": ["tip1", "tip2"],
  "encouragement": "string"
}}

Question: {question}
Correct answer: {correct_answer}
Expected explanation: {explanation}
Learner answer: {user_answer}
"""
    try:
        payload = llm_json(prompt, REVIEWER_SYSTEM)
        feedback = payload.get("feedback", "")
        mistake = payload.get("explanation_of_mistake", "")
        encouragement = payload.get("encouragement", "")
        tips = payload.get("improvement_tips", [])
        tips_text = "\n".join([f"• {tip}" for tip in tips[:3]]) if isinstance(tips, list) else ""
        composed = f"{'✅ Правильно!' if is_correct else '❌ Неправильно.'}\n\n{feedback}\n\n{mistake}"
        if tips_text:
            composed += f"\n\nСоветы:\n{tips_text}"
        if encouragement:
            composed += f"\n\n{encouragement}"
        return is_correct, composed, payload
    except Exception:
        fallback = f"{'✅ Правильно!' if is_correct else '❌ Неправильно.'}\n\nПравильный ответ: {correct_answer}\n\n{explanation}"
        return is_correct, fallback, {}


def progress_agent(user_row: sqlite3.Row) -> Dict[str, Any]:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT COUNT(*) as total_sessions,
           COALESCE(SUM(duration_minutes), 0) as total_minutes,
           COUNT(DISTINCT topic) as unique_topics
    FROM study_history
    WHERE user_id = ?
    """, (user_row["user_id"],))
    stats = dict(cur.fetchone())

    cur.execute("""
    SELECT topic, COUNT(*) as count
    FROM study_history
    WHERE user_id = ? AND topic != ''
    GROUP BY topic
    ORDER BY count DESC
    LIMIT 5
    """, (user_row["user_id"],))
    top_topics = [dict(row) for row in cur.fetchall()]

    cur.execute("""
    SELECT AVG(CAST(score AS FLOAT) / CASE WHEN json_array_length(questions_json)=0 THEN 1 ELSE json_array_length(questions_json) END) as avg_score
    FROM quiz_sessions
    WHERE user_id = ? AND status = 'completed'
    """, (user_row["user_id"],))
    quiz_row = cur.fetchone()
    avg_score = quiz_row["avg_score"] if quiz_row and quiz_row["avg_score"] is not None else None

    cur.execute("""
    SELECT event_type, topic, created_at
    FROM study_history
    WHERE user_id = ?
    ORDER BY id DESC
    LIMIT 12
    """, (user_row["user_id"],))
    recent_activity = [dict(row) for row in cur.fetchall()]
    conn.close()

    prompt = f"""
Analyze learner progress and return JSON.

Return ONLY valid JSON:
{{
  "progress_summary": "string",
  "strengths_identified": ["strength1", "strength2"],
  "areas_for_improvement": ["area1", "area2"],
  "recommendations": ["recommendation1", "recommendation2", "recommendation3"],
  "achievements_to_celebrate": ["achievement1", "achievement2"],
  "next_milestones": ["milestone1", "milestone2"]
}}

User profile:
- Goal: {user_row["goal"]}
- Level: {user_row["level"]}
- Daily minutes: {user_row["daily_minutes"]}
- Strengths: {user_row["strengths_json"]}
- Weak topics: {user_row["weak_topics_json"]}
- Total study minutes: {stats.get('total_minutes', 0)}
- Average quiz score: {avg_score}
- Top topics: {top_topics}
- Recent activity: {recent_activity}
"""
    return llm_json(prompt, PROGRESS_SYSTEM)


def challenge_agent(user_row: sqlite3.Row) -> Dict[str, Any]:
    prompt = f"""
Generate one daily Data Science challenge as JSON.

Return ONLY valid JSON:
{{
  "challenge": "string",
  "topic": "string",
  "estimated_time": "string",
  "steps": ["step1", "step2", "step3"],
  "success_criteria": "string"
}}

User goal: {user_row["goal"]}
User level: {user_row["level"]}
"""
    return llm_json(prompt, CHALLENGE_SYSTEM)


# =========================
# Formatting helpers
# =========================
def format_help() -> str:
    return """
<b>🤖 AI Agent DS Mentor</b>

<b>Основные команды</b>
/start — начать
/help — справка
/profile — профиль
/progress — анализ прогресса
/stats — подробная статистика
/daily — статистика за сегодня
/achievements — достижения
/streak — серия обучения

<b>Настройка</b>
/setgoal &lt;текст&gt;
/setlevel &lt;beginner|junior|middle|advanced&gt;
/settime &lt;минуты&gt;
/notifications on|off

<b>Обучение</b>
/plan — персональный план
/topic &lt;тема&gt;
/topic &lt;тема&gt; &lt;подтема&gt;
/quiz &lt;тема&gt;
/quiz &lt;тема&gt; &lt;easy|medium|hard&gt;
/answer &lt;вариант&gt;
/hint — подсказка
/skip — пропустить вопрос
/challenge — задание на сегодня

<b>Заметки и ресурсы</b>
/note &lt;название&gt; | &lt;содержание&gt;
/mynotes
/resources &lt;тема&gt;
""".strip()


def format_profile(user_row: sqlite3.Row) -> str:
    strengths = json_loads_safe(user_row["strengths_json"], [])
    weak_topics = json_loads_safe(user_row["weak_topics_json"], [])
    completed = json_loads_safe(user_row["completed_topics_json"], [])
    daily = get_daily_stats(user_row["user_id"])

    return f"""
<b>📊 Профиль обучения</b>

<b>🎯 Цель:</b> {user_row["goal"] or "Не указана"}
<b>📈 Уровень:</b> {user_row["level"] or "Не указан"}
<b>⏰ В день:</b> {format_duration(user_row["daily_minutes"] or 30)}

<b>📚 Статистика</b>
• Всего времени: {format_duration(user_row["total_study_minutes"] or 0)}
• Серия: {user_row["streak_days"] or 0} дней 🔥
• Сегодня: {daily["actual"]}/{daily["target"]} мин

<b>💪 Сильные стороны:</b>
{", ".join(strengths) if strengths else "Пока не определены"}

<b>📖 Темы для роста:</b>
{", ".join(weak_topics) if weak_topics else "Пока не определены"}

<b>✅ Изученные темы:</b> {len(completed)}
""".strip()


def format_plan(plan: Dict[str, Any]) -> str:
    lines = ["<b>📚 Персональный план обучения</b>", ""]
    if plan.get("overview"):
        lines.append(plan["overview"])
        lines.append("")
    for week in plan.get("weeks", [])[:2]:
        lines.append(f"<b>Неделя {week.get('week')}: {week.get('focus', '')}</b>")
        topics = week.get("topics", [])
        if topics:
            lines.append(f"Темы: {', '.join(topics)}")
        projects = week.get("projects", [])
        if projects:
            lines.append(f"Проекты: {', '.join(projects)}")
        resources = week.get("resources", [])
        if resources:
            lines.append(f"Ресурсы: {', '.join(resources)}")
        daily_schedule = week.get("daily_schedule", {})
        if isinstance(daily_schedule, dict) and daily_schedule:
            lines.append("План по дням:")
            for day, item in list(daily_schedule.items())[:5]:
                lines.append(f"• {day}: {item}")
        lines.append("")
    milestones = plan.get("milestones", [])
    if milestones:
        lines.append("<b>🏁 Вехи</b>")
        lines.extend([f"• {m}" for m in milestones[:5]])
    return "\n".join(lines)


def format_topic_explanation(payload: Dict[str, Any]) -> str:
    lines = [f"<b>{payload.get('title', 'Тема')}</b>", ""]
    if payload.get("overview"):
        lines.append(payload["overview"])
        lines.append("")
    if payload.get("detailed_explanation"):
        lines.append(payload["detailed_explanation"])
        lines.append("")
    if payload.get("real_world_example"):
        lines.append("<b>📌 Пример из практики</b>")
        lines.append(payload["real_world_example"])
        lines.append("")
    if payload.get("code_example"):
        lines.append("<b>💻 Пример кода</b>")
        lines.append(f"<code>{payload['code_example']}</code>")
        lines.append("")
    takeaways = payload.get("key_takeaways", [])
    if takeaways:
        lines.append("<b>🎯 Главное</b>")
        lines.extend([f"• {x}" for x in takeaways[:5]])
    return "\n".join(lines)


def format_progress_report(report: Dict[str, Any]) -> str:
    lines = ["<b>📈 Анализ прогресса</b>", ""]
    if report.get("progress_summary"):
        lines.append(report["progress_summary"])
        lines.append("")
    strengths = report.get("strengths_identified", [])
    if strengths:
        lines.append("<b>💪 Сильные стороны</b>")
        lines.extend([f"• {x}" for x in strengths[:5]])
        lines.append("")
    weak = report.get("areas_for_improvement", [])
    if weak:
        lines.append("<b>📚 Что подтянуть</b>")
        lines.extend([f"• {x}" for x in weak[:5]])
        lines.append("")
    recs = report.get("recommendations", [])
    if recs:
        lines.append("<b>➡️ Следующие шаги</b>")
        lines.extend([f"• {x}" for x in recs[:5]])
    return "\n".join(lines)


def format_resources(topic: str, items: List[Dict[str, Any]]) -> str:
    lines = [f"<b>📚 Ресурсы по теме: {topic}</b>", ""]
    for item in items[:5]:
        lines.append(f"<b>{item['title']}</b>")
        lines.append(f"Тип: {item['resource_type']} | Сложность: {item['difficulty']}")
        if item.get("description"):
            lines.append(item["description"])
        if item.get("url"):
            lines.append(item["url"])
        lines.append("")
    return "\n".join(lines)


# =========================
# Quiz flow
# =========================
def send_next_quiz_question(chat_id: int, user_id: int) -> None:
    session = get_active_quiz_session(user_id)
    if session is None:
        telegram_send_message(chat_id, "У тебя нет активного квиза. Запусти /quiz <тема>")
        return

    questions = json_loads_safe(session["questions_json"], [])
    current_index = safe_parse_int(session["current_index"], 0)

    if current_index >= len(questions):
        score = safe_parse_int(session["score"], 0)
        total = len(questions)
        update_quiz_session(session["id"], current_index, score, "completed")
        achievements = maybe_award_quiz_achievements(user_id, score, total)
        text = f"✅ Квиз завершён!\n\nРезультат: {score}/{total}"
        if achievements:
            text += "\n\n" + "\n".join(achievements)
        telegram_send_message(chat_id, text)
        log_study_event(
            user_id,
            "quiz_completed",
            topic=session["topic"],
            duration_minutes=15,
            payload={"score": score, "total": total, "difficulty": session["difficulty"]},
        )
        update_study_time(user_id, 15, session["topic"])
        return

    question = questions[current_index]
    options_text = "\n".join([f"• {opt}" for opt in question["options"]])
    hint_text = "\nПодсказка: /hint" if question.get("hint") else ""

    text = (
        f"<b>Вопрос {current_index + 1}/{len(questions)}</b>\n"
        f"Тема: {session['topic']}\n"
        f"Сложность: {session['difficulty']}\n\n"
        f"{question['question']}\n\n"
        f"{options_text}\n\n"
        f"Ответь так:\n"
        f"/answer <вариант>\n"
        f"/skip — пропустить{hint_text}"
    )
    telegram_send_message(chat_id, text)


def handle_hint(chat_id: int, user_id: int) -> None:
    session = get_active_quiz_session(user_id)
    if session is None:
        telegram_send_message(chat_id, "Нет активного квиза.")
        return

    questions = json_loads_safe(session["questions_json"], [])
    current_index = safe_parse_int(session["current_index"], 0)
    if current_index >= len(questions):
        telegram_send_message(chat_id, "Квиз уже завершён.")
        return

    hint = questions[current_index].get("hint", "")
    if not hint:
        telegram_send_message(chat_id, "Для этого вопроса подсказка недоступна.")
        return

    telegram_send_message(chat_id, f"💡 Подсказка\n{hint}")


def handle_skip(chat_id: int, user_id: int) -> None:
    session = get_active_quiz_session(user_id)
    if session is None:
        telegram_send_message(chat_id, "Нет активного квиза.")
        return

    current_index = safe_parse_int(session["current_index"], 0)
    score = safe_parse_int(session["score"], 0)

    save_quiz_answer(
        quiz_session_id=session["id"],
        question_index=current_index,
        user_answer="__skipped__",
        correct_answer="",
        is_correct=False,
        feedback="Вопрос был пропущен.",
        response_time=0,
    )

    update_quiz_session(session["id"], current_index + 1, score, "active")
    telegram_send_message(chat_id, "⏭ Вопрос пропущен.")
    send_next_quiz_question(chat_id, user_id)


def handle_answer(chat_id: int, user_id: int, user_answer: str) -> None:
    answer = user_answer.strip()
    if not answer:
        telegram_send_message(chat_id, "Используй: /answer <вариант>")
        return

    session = get_active_quiz_session(user_id)
    if session is None:
        telegram_send_message(chat_id, "Нет активного квиза. Запусти /quiz <тема>")
        return

    questions = json_loads_safe(session["questions_json"], [])
    current_index = safe_parse_int(session["current_index"], 0)
    if current_index >= len(questions):
        telegram_send_message(chat_id, "Квиз уже завершён.")
        return

    question = questions[current_index]
    is_correct, feedback, review_meta = reviewer_agent(
        question=question["question"],
        correct_answer=question["correct_answer"],
        explanation=question["explanation"],
        user_answer=answer,
    )

    new_score = safe_parse_int(session["score"], 0) + (1 if is_correct else 0)
    new_index = current_index + 1
    new_status = "completed" if new_index >= len(questions) else "active"

    save_quiz_answer(
        quiz_session_id=session["id"],
        question_index=current_index,
        user_answer=answer,
        correct_answer=question["correct_answer"],
        is_correct=is_correct,
        feedback=feedback,
        response_time=0,
    )

    update_quiz_session(session["id"], new_index, new_score, new_status)
    log_study_event(
        user_id,
        "quiz_answered",
        topic=session["topic"],
        payload={
            "question": question["question"],
            "user_answer": answer,
            "correct_answer": question["correct_answer"],
            "is_correct": is_correct,
            "review_meta": review_meta,
        },
    )

    telegram_send_message(chat_id, feedback)
    send_next_quiz_question(chat_id, user_id)


# =========================
# Command handlers
# =========================
def handle_start(chat_id: int, user_id: int, first_name: str) -> None:
    text = (
        f"Привет, {first_name}! 👋\n\n"
        "Я <b>AI Agent для развития компетенций в Data Science</b>.\n\n"
        "Я могу:\n"
        "• строить персональный план обучения\n"
        "• объяснять темы\n"
        "• генерировать квизы\n"
        "• проверять ответы\n"
        "• отслеживать прогресс\n\n"
        "<b>Быстрый старт</b>\n"
        "/setgoal Хочу подготовиться к DS интервью\n"
        "/setlevel junior\n"
        "/settime 60\n"
        "/plan\n\n"
        "Список команд: /help"
    )
    telegram_send_message(chat_id, text)


def handle_set_goal(chat_id: int, user_id: int, text: str) -> None:
    goal = text.strip()
    if not goal:
        telegram_send_message(chat_id, "Используй: /setgoal <твоя цель>")
        return
    update_user_profile(user_id, goal=goal)
    log_study_event(user_id, "set_goal", payload={"goal": goal})
    telegram_send_message(chat_id, f"✅ Цель сохранена\n\n{goal}")


def handle_set_level(chat_id: int, user_id: int, text: str) -> None:
    level = text.strip().lower()
    allowed = {"beginner", "junior", "middle", "advanced"}
    if level not in allowed:
        telegram_send_message(chat_id, "Используй: /setlevel beginner|junior|middle|advanced")
        return
    update_user_profile(user_id, level=level)
    log_study_event(user_id, "set_level", payload={"level": level})
    telegram_send_message(chat_id, f"✅ Уровень сохранён: {level}")


def handle_set_time(chat_id: int, user_id: int, text: str) -> None:
    minutes = safe_parse_int(text.strip(), -1)
    if minutes < 15 or minutes > 480:
        telegram_send_message(chat_id, "Используй: /settime 60\nУкажи число от 15 до 480.")
        return
    update_user_profile(user_id, daily_minutes=minutes)
    log_study_event(user_id, "set_time", payload={"daily_minutes": minutes})
    telegram_send_message(chat_id, f"✅ Ежедневное время: {format_duration(minutes)}")


def handle_notifications(chat_id: int, user_id: int, args: str) -> None:
    mode = args.strip().lower()
    if mode not in {"on", "off"}:
        telegram_send_message(chat_id, "Используй: /notifications on|off")
        return
    enabled = mode == "on"
    update_user_profile(user_id, notifications_enabled=enabled)
    telegram_send_message(chat_id, f"✅ Напоминания {'включены' if enabled else 'выключены'}")


def handle_profile(chat_id: int, user_id: int) -> None:
    user = get_user(user_id)
    if user is None:
        telegram_send_message(chat_id, "Сначала напиши /start")
        return
    telegram_send_message(chat_id, format_profile(user))


def handle_plan(chat_id: int, user_id: int) -> None:
    user = get_user(user_id)
    if user is None:
        telegram_send_message(chat_id, "Сначала напиши /start")
        return
    if not user["goal"] or not user["level"]:
        telegram_send_message(chat_id, "Сначала задай цель и уровень: /setgoal и /setlevel")
        return

    telegram_send_typing(chat_id)
    telegram_send_message(chat_id, "🧠 Строю персональный план...")
    try:
        plan = planner_agent(user)
        update_user_profile(user_id, current_plan=json.dumps(plan, ensure_ascii=False))
        log_study_event(user_id, "plan_generated", payload=plan)
        telegram_send_message(chat_id, format_plan(plan))
    except Exception as exc:
        logging.exception("Plan generation failed: %s", exc)
        telegram_send_message(chat_id, "Не удалось сгенерировать план. Попробуй позже.")


def handle_topic(chat_id: int, user_id: int, args: str) -> None:
    args = args.strip()
    if not args:
        telegram_send_message(chat_id, "Используй: /topic pandas\nили /topic pandas groupby")
        return

    parts = args.split(" ", 1)
    topic = parts[0].strip()
    subtopic = parts[1].strip() if len(parts) > 1 else ""

    user = get_user(user_id)
    if user is None:
        telegram_send_message(chat_id, "Сначала напиши /start")
        return

    telegram_send_typing(chat_id)
    telegram_send_message(chat_id, f"📖 Готовлю объяснение по теме: {topic}")
    try:
        payload = tutor_agent(topic, user, subtopic)
        log_study_event(user_id, "topic_explained", topic=topic, subtopic=subtopic, duration_minutes=10, payload=payload)
        update_study_time(user_id, 10, topic)
        telegram_send_message(chat_id, format_topic_explanation(payload))
    except Exception as exc:
        logging.exception("Topic explanation failed: %s", exc)
        telegram_send_message(chat_id, "Не удалось объяснить тему. Попробуй позже.")


def handle_quiz(chat_id: int, user_id: int, args: str) -> None:
    args = args.strip()
    if not args:
        telegram_send_message(chat_id, "Используй: /quiz pandas\nили /quiz pandas hard")
        return

    parts = args.split()
    topic = parts[0].strip()
    difficulty = parts[1].strip().lower() if len(parts) > 1 else "medium"
    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"

    user = get_user(user_id)
    if user is None:
        telegram_send_message(chat_id, "Сначала напиши /start")
        return

    telegram_send_typing(chat_id)
    telegram_send_message(chat_id, f"📝 Генерирую квиз по теме: {topic} ({difficulty})")
    try:
        questions = quiz_agent(topic, user, num_questions=5, difficulty=difficulty)
        create_quiz_session(user_id, topic, questions, difficulty)
        log_study_event(user_id, "quiz_started", topic=topic, payload={"difficulty": difficulty})
        send_next_quiz_question(chat_id, user_id)
    except Exception as exc:
        logging.exception("Quiz generation failed: %s", exc)
        telegram_send_message(chat_id, "Не удалось сгенерировать квиз. Попробуй позже.")


def handle_progress(chat_id: int, user_id: int) -> None:
    user = get_user(user_id)
    if user is None:
        telegram_send_message(chat_id, "Сначала напиши /start")
        return
    telegram_send_typing(chat_id)
    telegram_send_message(chat_id, "📊 Анализирую прогресс...")
    try:
        report = progress_agent(user)
        telegram_send_message(chat_id, format_progress_report(report))
    except Exception as exc:
        logging.exception("Progress analysis failed: %s", exc)
        telegram_send_message(chat_id, "Не удалось проанализировать прогресс. Попробуй позже.")


def handle_stats(chat_id: int, user_id: int) -> None:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT COUNT(DISTINCT date(created_at)) as active_days,
           COUNT(CASE WHEN event_type = 'quiz_completed' THEN 1 END) as quizzes_taken,
           COUNT(CASE WHEN event_type = 'topic_explained' THEN 1 END) as topics_studied,
           COALESCE(SUM(duration_minutes), 0) as total_minutes
    FROM study_history
    WHERE user_id = ?
    """, (user_id,))
    stats = dict(cur.fetchone())

    cur.execute("""
    SELECT date(created_at) as study_date, COALESCE(SUM(duration_minutes), 0) as minutes
    FROM study_history
    WHERE user_id = ? AND created_at >= date('now', '-7 days')
    GROUP BY date(created_at)
    ORDER BY study_date DESC
    """, (user_id,))
    week = [dict(row) for row in cur.fetchall()]
    conn.close()

    user = get_user(user_id)
    streak = user["streak_days"] if user else 0

    lines = [
        "<b>📊 Детальная статистика</b>",
        "",
        f"• Всего времени: {format_duration(stats.get('total_minutes', 0))}",
        f"• Активных дней: {stats.get('active_days', 0)}",
        f"• Пройдено квизов: {stats.get('quizzes_taken', 0)}",
        f"• Изучено тем: {stats.get('topics_studied', 0)}",
        f"• Серия: {streak} дней 🔥",
        "",
        "<b>Последние 7 дней</b>",
    ]
    if week:
        lines.extend([f"• {row['study_date']}: {format_duration(row['minutes'])}" for row in week])
    else:
        lines.append("Пока нет активности.")
    telegram_send_message(chat_id, "\n".join(lines))


def handle_daily(chat_id: int, user_id: int) -> None:
    daily = get_daily_stats(user_id)
    status = "✅ Цель выполнена!" if daily["completed"] else f"Осталось: {format_duration(daily['remaining'])}"
    telegram_send_message(
        chat_id,
        f"<b>📅 Сегодня</b>\n\nЦель: {format_duration(daily['target'])}\nВыполнено: {format_duration(daily['actual'])}\n{status}"
    )


def handle_achievements(chat_id: int, user_id: int) -> None:
    achievements = get_user_achievements(user_id)
    if not achievements:
        telegram_send_message(chat_id, "🏆 Пока достижений нет. Продолжай учиться.")
        return

    lines = ["<b>🏆 Достижения</b>", ""]
    for item in achievements[:20]:
        lines.append(f"• {item['achievement_name']} — {item['achieved_at'][:10]}")
    telegram_send_message(chat_id, "\n".join(lines))


def handle_note(chat_id: int, user_id: int, args: str) -> None:
    if "|" not in args:
        telegram_send_message(chat_id, "Используй: /note <название> | <содержание>")
        return
    title, content = args.split("|", 1)
    title = title.strip()
    content = content.strip()
    if not title or not content:
        telegram_send_message(chat_id, "Название и содержание не должны быть пустыми.")
        return

    note_id = add_note(user_id, title, content)
    log_study_event(user_id, "note_created", payload={"title": title, "note_id": note_id})
    telegram_send_message(chat_id, f"✅ Заметка сохранена: {title}")


def handle_my_notes(chat_id: int, user_id: int, args: str) -> None:
    topic = args.strip() or None
    notes = get_notes(user_id, topic)
    if not notes:
        telegram_send_message(chat_id, "📝 У тебя пока нет заметок.")
        return

    lines = ["<b>📝 Мои заметки</b>", ""]
    for note in notes[:10]:
        preview = note["content"][:120] + ("..." if len(note["content"]) > 120 else "")
        lines.append(f"<b>{note['title']}</b>")
        lines.append(preview)
        if note["topic"]:
            lines.append(f"<i>Тема: {note['topic']}</i>")
        lines.append("")
    telegram_send_message(chat_id, "\n".join(lines))


def handle_resources(chat_id: int, user_id: int, args: str) -> None:
    topic = args.strip()
    if not topic:
        telegram_send_message(chat_id, "Используй: /resources <тема>")
        return
    items = get_resources(topic)
    if not items:
        telegram_send_message(chat_id, f"Ресурсы по теме '{topic}' не найдены.")
        return
    telegram_send_message(chat_id, format_resources(topic, items))


def handle_challenge(chat_id: int, user_id: int) -> None:
    user = get_user(user_id)
    if user is None:
        telegram_send_message(chat_id, "Сначала напиши /start")
        return
    telegram_send_typing(chat_id)
    try:
        challenge = challenge_agent(user)
        steps = "\n".join([f"{idx + 1}. {step}" for idx, step in enumerate(challenge.get("steps", [])[:5])])
        text = (
            f"<b>🎯 Вызов на сегодня</b>\n\n"
            f"<b>{challenge.get('challenge', 'Практическое задание')}</b>\n\n"
            f"Тема: {challenge.get('topic', 'Data Science')}\n"
            f"Время: {challenge.get('estimated_time', '30 минут')}\n\n"
            f"{steps}\n\n"
            f"<b>Критерий успеха:</b>\n{challenge.get('success_criteria', '')}"
        )
        log_study_event(user_id, "challenge_received", payload=challenge)
        telegram_send_message(chat_id, text)
    except Exception as exc:
        logging.exception("Challenge generation failed: %s", exc)
        telegram_send_message(chat_id, "Не удалось сгенерировать задание. Попробуй позже.")


def handle_streak(chat_id: int, user_id: int) -> None:
    user = get_user(user_id)
    streak = user["streak_days"] if user else 0
    telegram_send_message(chat_id, f"🔥 Текущая серия обучения: {streak} дней")


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
    last_name = from_user.get("last_name", "") or ""

    text = message.get("text", "")
    if not chat_id or not user_id or not text:
        return

    upsert_user(user_id, username, first_name, last_name)
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
        elif command == "/notifications":
            handle_notifications(chat_id, user_id, args)
        elif command == "/profile":
            handle_profile(chat_id, user_id)
        elif command == "/plan":
            handle_plan(chat_id, user_id)
        elif command == "/topic":
            handle_topic(chat_id, user_id, args)
        elif command == "/quiz":
            handle_quiz(chat_id, user_id, args)
        elif command == "/answer":
            handle_answer(chat_id, user_id, args)
        elif command == "/hint":
            handle_hint(chat_id, user_id)
        elif command == "/skip":
            handle_skip(chat_id, user_id)
        elif command == "/progress":
            handle_progress(chat_id, user_id)
        elif command == "/stats":
            handle_stats(chat_id, user_id)
        elif command == "/daily":
            handle_daily(chat_id, user_id)
        elif command == "/achievements":
            handle_achievements(chat_id, user_id)
        elif command == "/note":
            handle_note(chat_id, user_id, args)
        elif command == "/mynotes":
            handle_my_notes(chat_id, user_id, args)
        elif command == "/resources":
            handle_resources(chat_id, user_id, args)
        elif command == "/challenge":
            handle_challenge(chat_id, user_id)
        elif command == "/streak":
            handle_streak(chat_id, user_id)
        else:
            telegram_send_message(
                chat_id,
                "Я пока понимаю команды.\n\nНапиши /help, чтобы посмотреть доступные команды."
            )
    except Exception as exc:
        logging.exception("Error while handling message: %s", exc)
        telegram_send_message(chat_id, f"❌ Произошла ошибка.\n{str(exc)[:300]}")


# =========================
# Reminders
# =========================
def send_daily_reminders() -> None:
    if not ENABLE_REMINDERS:
        return

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT u.user_id, u.first_name, u.daily_minutes, COALESCE(d.actual_minutes, 0) as actual_minutes
    FROM users u
    LEFT JOIN daily_goals d
      ON u.user_id = d.user_id AND d.goal_date = date('now')
    WHERE u.notifications_enabled = 1
      AND COALESCE(d.actual_minutes, 0) < u.daily_minutes
    """)
    users = cur.fetchall()
    conn.close()

    for user in users:
        try:
            remaining = max(0, user["daily_minutes"] - user["actual_minutes"])
            text = (
                f"🔔 <b>Напоминание об обучении</b>\n\n"
                f"Сегодня: {format_duration(user['actual_minutes'])} из {format_duration(user['daily_minutes'])}\n"
                f"Осталось: {format_duration(remaining)}\n\n"
                f"Продолжим? Попробуй /topic или /quiz 💪"
            )
            telegram_send_message(user["user_id"], text)
        except Exception as exc:
            logging.error("Failed to send reminder to %s: %s", user["user_id"], exc)


# =========================
# Main loop
# =========================
def run_bot() -> None:
    init_db()
    logging.info("Bot started")

    scheduler = BackgroundScheduler()
    if ENABLE_REMINDERS:
        scheduler.add_job(send_daily_reminders, "cron", hour=REMINDER_HOUR, minute=0)
        scheduler.start()
        logging.info("Reminder scheduler started at %s:00", REMINDER_HOUR)

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
        except requests.RequestException as exc:
            logging.exception("Network error: %s", exc)
            time.sleep(5)
        except Exception as exc:
            logging.exception("Unexpected error: %s", exc)
            time.sleep(5)

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_bot()
