import os
import re
import json
import time
import sqlite3
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
from functools import wraps

import requests
from apscheduler.schedulers.background import BackgroundScheduler


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
ENABLE_ACHIEVEMENTS = os.getenv("ENABLE_ACHIEVEMENTS", "true").lower() == "true"

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set.")

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# =========================
# Decorators & Utils
# =========================
def retry_on_failure(max_retries: int = MAX_RETRIES, delay: int = 2):
    """Decorator for retrying failed operations"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))
                        logging.warning(f"Retry {attempt + 1}/{max_retries} for {func.__name__}: {e}")
                    else:
                        logging.error(f"Failed after {max_retries} attempts: {e}")
            raise last_error
        return wrapper
    return decorator


def safe_parse_int(value: Any, default: int = 0) -> int:
    """Safely parse integer from various types"""
    try:
        if isinstance(value, str):
            return int(value.strip())
        elif isinstance(value, (int, float)):
            return int(value)
        return default
    except (ValueError, TypeError):
        return default


def format_duration(minutes: int) -> str:
    """Format minutes into human-readable string"""
    if minutes < 60:
        return f"{minutes} минут"
    hours = minutes // 60
    mins = minutes % 60
    if mins == 0:
        return f"{hours} час(ов)"
    return f"{hours} час(ов) {mins} минут"


# =========================
# Database (Enhanced)
# =========================
def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db_connection()
    cur = conn.cursor()

    # Users table (enhanced)
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
        current_plan TEXT DEFAULT '',
        total_study_minutes INTEGER DEFAULT 0,
        streak_days INTEGER DEFAULT 0,
        last_study_date TEXT,
        preferred_topics_json TEXT DEFAULT '[]',
        notifications_enabled INTEGER DEFAULT 1,
        language TEXT DEFAULT 'ru',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Quiz sessions table (enhanced)
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

    # Quiz answers table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS quiz_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_session_id INTEGER NOT NULL,
        question_index INTEGER NOT NULL,
        user_answer TEXT,
        correct_answer TEXT,
        is_correct INTEGER,
        feedback TEXT,
        response_time INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Study history table (enhanced)
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

    # Achievements table
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

    # Daily goals tracking
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

    # Learning resources
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

    # Notes
    cur.execute("""
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        topic TEXT,
        tags_json TEXT DEFAULT '[]',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Insert some default resources
    cur.execute("SELECT COUNT(*) FROM learning_resources")
    if cur.fetchone()[0] == 0:
        default_resources = [
            ("Python", "course", "Python для Data Science", "https://www.datacamp.com/courses/intro-to-python-for-data-science", "Основы Python для анализа данных", "beginner"),
            ("Pandas", "documentation", "Pandas Documentation", "https://pandas.pydata.org/docs/", "Официальная документация Pandas", "intermediate"),
            ("Machine Learning", "book", "Hands-On ML", "https://www.oreilly.com/library/view/hands-on-machine-learning/9781492032632/", "Практическое машинное обучение", "advanced"),
            ("Statistics", "course", "Statistics for Data Science", "https://www.khanacademy.org/math/statistics-probability", "Основы статистики", "beginner"),
        ]
        for resource in default_resources:
            cur.execute("""
            INSERT INTO learning_resources (topic, resource_type, title, url, description, difficulty)
            VALUES (?, ?, ?, ?, ?, ?)
            """, resource)

    conn.commit()
    conn.close()


# Enhanced database functions
def update_study_time(user_id: int, minutes: int, topic: str = "") -> None:
    """Update user's total study time and streak"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    today = datetime.now().date().isoformat()
    
    # Update total study minutes
    cur.execute("""
    UPDATE users 
    SET total_study_minutes = total_study_minutes + ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE user_id = ?
    """, (minutes, user_id))
    
    # Update daily goal
    cur.execute("""
    INSERT INTO daily_goals (user_id, goal_date, target_minutes, actual_minutes)
    VALUES (?, ?, 
        (SELECT daily_minutes FROM users WHERE user_id = ?),
        ?)
    ON CONFLICT(user_id, goal_date) DO UPDATE SET
        actual_minutes = actual_minutes + ?
    """, (user_id, today, user_id, minutes, minutes))
    
    # Update streak
    cur.execute("SELECT last_study_date, streak_days FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    
    if row:
        last_date = row["last_study_date"]
        streak = row["streak_days"] or 0
        
        if last_date:
            last_study = datetime.fromisoformat(last_date).date()
            yesterday = datetime.now().date() - timedelta(days=1)
            
            if last_study == yesterday:
                streak += 1
            elif last_study < yesterday:
                streak = 1
        
        cur.execute("""
        UPDATE users 
        SET last_study_date = ?, streak_days = ?
        WHERE user_id = ?
        """, (today, streak, user_id))
        
        # Check streak achievement
        if ENABLE_ACHIEVEMENTS and streak >= 7:
            check_and_award_achievement(user_id, "streak_7", "7 дней обучения подряд")
        if ENABLE_ACHIEVEMENTS and streak >= 30:
            check_and_award_achievement(user_id, "streak_30", "30 дней обучения подряд")
    
    conn.commit()
    conn.close()


def check_and_award_achievement(user_id: int, achievement_type: str, achievement_name: str) -> bool:
    """Award achievement to user if not already awarded"""
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


def get_user_achievements(user_id: int) -> List[Dict[str, Any]]:
    """Get all achievements for a user"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT achievement_type, achievement_name, achieved_at
    FROM achievements
    WHERE user_id = ?
    ORDER BY achieved_at DESC
    """, (user_id,))
    achievements = [dict(row) for row in cur.fetchall()]
    conn.close()
    return achievements


def get_daily_stats(user_id: int) -> Dict[str, Any]:
    """Get daily statistics for user"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    today = datetime.now().date().isoformat()
    
    cur.execute("""
    SELECT target_minutes, actual_minutes
    FROM daily_goals
    WHERE user_id = ? AND goal_date = ?
    """, (user_id, today))
    
    row = cur.fetchone()
    conn.close()
    
    if row:
        return {
            "target": row["target_minutes"],
            "actual": row["actual_minutes"],
            "remaining": max(0, row["target_minutes"] - row["actual_minutes"]),
            "completed": row["actual_minutes"] >= row["target_minutes"]
        }
    
    return {"target": 30, "actual": 0, "remaining": 30, "completed": False}


def add_note(user_id: int, title: str, content: str, topic: str = "", tags: List[str] = None) -> int:
    """Add a learning note"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    tags_json = json.dumps(tags or [], ensure_ascii=False)
    
    cur.execute("""
    INSERT INTO notes (user_id, title, content, topic, tags_json)
    VALUES (?, ?, ?, ?, ?)
    """, (user_id, title, content, topic, tags_json))
    
    note_id = cur.lastrowid
    conn.commit()
    conn.close()
    return note_id


def get_notes(user_id: int, topic: str = None) -> List[Dict[str, Any]]:
    """Get user's notes, optionally filtered by topic"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    if topic:
        cur.execute("""
        SELECT id, title, content, topic, tags_json, created_at, updated_at
        FROM notes
        WHERE user_id = ? AND topic = ?
        ORDER BY updated_at DESC
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


# =========================
# Enhanced Telegram API
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
    payload = {
        "chat_id": chat_id,
        "text": text[:4000],
        "parse_mode": parse_mode,
    }
    response = requests.post(
        f"{TELEGRAM_API_BASE}/sendMessage",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()


def telegram_send_typing(chat_id: int) -> None:
    """Send typing action to Telegram"""
    try:
        requests.post(
            f"{TELEGRAM_API_BASE}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"},
            timeout=5,
        )
    except Exception:
        pass


# =========================
# Enhanced LLM helpers
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
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
            }
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
# Enhanced Agent prompts
# =========================
PLANNER_SYSTEM = """
You are Planner Agent, an expert Data Science learning path designer.
Create concise, practical, and personalized learning plans.
Always adapt to the user's goal, level, daily time, strengths, and weak topics.
Include specific resources, projects, and milestones.
"""

TUTOR_SYSTEM = """
You are Tutor Agent, an expert Data Science educator.
Explain topics clearly with real-world examples and practical intuition.
Use analogies and visual descriptions when helpful.
Keep explanations engaging and structured.
"""

QUIZ_SYSTEM = """
You are Quiz Agent, an expert assessment designer.
Create short, focused quizzes that test understanding, not just memorization.
Include a mix of theoretical and practical questions.
Questions must be clear, unambiguous, and appropriate for the user's level.
"""

REVIEWER_SYSTEM = """
You are Reviewer Agent, a constructive learning coach.
Evaluate answers, explain mistakes thoroughly, and provide actionable next steps.
Always encourage growth mindset and highlight learning opportunities.
Be specific and practical in your feedback.
"""

PROGRESS_SYSTEM = """
You are Progress Agent, an analytical learning coach.
Analyze learner's journey, identify patterns, strengths, and growth areas.
Provide data-driven insights and personalized recommendations.
Focus on actionable next steps and celebrate achievements.
"""


# =========================
# Enhanced Agent logic
# =========================
def planner_agent(user_row: sqlite3.Row) -> Dict[str, Any]:
    strengths = json.loads(user_row["strengths_json"] or "[]")
    weak_topics = json.loads(user_row["weak_topics_json"] or "[]")
    completed_topics = json.loads(user_row["completed_topics_json"] or "[]")
    
    prompt = f"""
Create a personalized 4-week Data Science learning plan as JSON.

Return ONLY valid JSON with this structure:
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
                "tuesday": "string"
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

Requirements:
- Make it practical and project-based
- Include both theory and practice
- Focus on high-value DS skills
- Be realistic about time constraints
"""
    return llm_json(prompt, PLANNER_SYSTEM)


def tutor_agent(topic: str, user_row: sqlite3.Row, subtopic: str = "") -> Dict[str, Any]:
    prompt = f"""
Explain this Data Science topic in detail as JSON.

Return ONLY valid JSON with this structure:
{{
    "title": "string",
    "overview": "string",
    "key_concepts": ["concept1", "concept2"],
    "detailed_explanation": "string",
    "real_world_example": "string",
    "code_example": "string",
    "common_pitfalls": ["pitfall1", "pitfall2"],
    "practice_exercises": ["exercise1", "exercise2"],
    "key_takeaways": ["takeaway1", "takeaway2", "takeaway3"],
    "further_resources": ["resource1", "resource2"]
}}

Topic: {topic}
{f"Subtopic: {subtopic}" if subtopic else ""}

User:
- Goal: {user_row["goal"]}
- Level: {user_row["level"]}

Requirements:
- Use clear, accessible language
- Include practical examples
- Add code snippets if relevant
- Keep total length manageable but comprehensive
"""
    return llm_json(prompt, TUTOR_SYSTEM)


def quiz_agent(topic: str, user_row: sqlite3.Row, num_questions: int = 5, difficulty: str = "medium") -> List[Dict[str, Any]]:
    prompt = f"""
Generate a Data Science quiz with varying difficulty.

Return ONLY valid JSON as an array with this schema:
[
  {{
    "question": "string",
    "options": ["A", "B", "C", "D"],
    "correct_answer": "one option exactly",
    "explanation": "string",
    "difficulty": "easy|medium|hard",
    "topic": "string",
    "hint": "string"
  }}
]

User:
- Goal: {user_row["goal"]}
- Level: {user_row["level"]}

Topic: {topic}
Number of questions: {num_questions}
Target difficulty: {difficulty}

Rules:
- Mix of theoretical and practical questions
- Exactly 4 options per question
- 1 correct answer only
- Plausible distractors
- Clear, helpful explanations
- Include hints for difficult questions
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
            "difficulty": item.get("difficulty", "medium"),
            "hint": item.get("hint", ""),
        })

    if not cleaned:
        raise ValueError("No valid quiz questions generated.")

    return cleaned[:num_questions]


def reviewer_agent(
    question: str,
    correct_answer: str,
    explanation: str,
    user_answer: str,
) -> Tuple[bool, str, Dict[str, Any]]:
    normalized_user = user_answer.strip().lower()
    normalized_correct = correct_answer.strip().lower()

    is_correct = normalized_user == normalized_correct

    prompt = f"""
Evaluate the learner's answer and provide detailed feedback as JSON.

Return ONLY valid JSON with this structure:
{{
    "is_correct": boolean,
    "feedback": "string",
    "explanation_of_mistake": "string",
    "improvement_tips": ["tip1", "tip2"],
    "related_concepts": ["concept1", "concept2"],
    "encouragement": "string"
}}

Question: {question}
Correct answer: {correct_answer}
Expected explanation: {explanation}
Learner answer: {user_answer}

Requirements:
- Be specific and constructive
- Explain why the answer is right or wrong
- Provide clear improvement suggestions
- Include encouragement for learning
"""
    
    try:
        result = llm_json(prompt, REVIEWER_SYSTEM)
        feedback = result.get("feedback", "")
        return is_correct, feedback, result
    except:
        # Fallback to simple feedback
        feedback = f"{'✅ Правильно!' if is_correct else '❌ Неправильно.'}\n\nПравильный ответ: {correct_answer}\n\n{explanation}"
        return is_correct, feedback, {}


def progress_agent(user_row: sqlite3.Row) -> Dict[str, Any]:
    conn = get_db_connection()
    cur = conn.cursor()

    # Get study statistics
    cur.execute("""
    SELECT 
        COUNT(*) as total_sessions,
        SUM(duration_minutes) as total_minutes,
        AVG(duration_minutes) as avg_duration,
        COUNT(DISTINCT topic) as unique_topics
    FROM study_history
    WHERE user_id = ? AND event_type IN ('topic_explained', 'quiz_completed')
    """, (user_row["user_id"],))
    
    stats = dict(cur.fetchone())
    
    # Get topic performance
    cur.execute("""
    SELECT topic, COUNT(*) as count
    FROM study_history
    WHERE user_id = ? AND topic != ''
    GROUP BY topic
    ORDER BY count DESC
    LIMIT 5
    """, (user_row["user_id"],))
    
    top_topics = [dict(row) for row in cur.fetchall()]
    
    # Get quiz performance
    cur.execute("""
    SELECT 
        AVG(CAST(score AS FLOAT) / json_array_length(questions_json)) as avg_score
    FROM quiz_sessions
    WHERE user_id = ? AND status = 'completed'
    """, (user_row["user_id"],))
    
    quiz_stats = cur.fetchone()
    
    # Get recent activity
    cur.execute("""
    SELECT event_type, topic, created_at
    FROM study_history
    WHERE user_id = ?
    ORDER BY created_at DESC
    LIMIT 10
    """, (user_row["user_id"],))
    
    recent_activity = [dict(row) for row in cur.fetchall()]
    
    conn.close()
    
    strengths = json.loads(user_row["strengths_json"] or "[]")
    weak_topics = json.loads(user_row["weak_topics_json"] or "[]")
    
    prompt = f"""
Analyze learner progress and provide insights as JSON.

Return ONLY valid JSON with this structure:
{{
    "progress_summary": "string",
    "total_learning_time": "string",
    "strengths_identified": ["strength1", "strength2"],
    "areas_for_improvement": ["area1", "area2"],
    "learning_pace": "string",
    "recommendations": ["recommendation1", "recommendation2", "recommendation3"],
    "achievements_to_celebrate": ["achievement1", "achievement2"],
    "next_milestones": ["milestone1", "milestone2"]
}}

User profile:
- Goal: {user_row["goal"]}
- Level: {user_row["level"]}
- Daily minutes: {user_row["daily_minutes"]}
- Current strengths: {strengths}
- Weak topics: {weak_topics}
- Total study minutes: {stats.get('total_minutes', 0)}
- Average quiz score: {quiz_stats['avg_score'] if quiz_stats and quiz_stats['avg_score'] else 'N/A'}
- Top studied topics: {top_topics}
- Recent activity: {recent_activity}

Requirements:
- Be encouraging and specific
- Provide actionable recommendations
- Celebrate progress and achievements
- Suggest concrete next steps
"""
    return llm_json(prompt, PROGRESS_SYSTEM)


# =========================
# Enhanced Command handlers
# =========================
def format_help() -> str:
    return """
<b>🤖 AI Agent DS Mentor - Справка</b>

<b>📚 Основные команды:</b>
/start - начать работу с ботом
/help - показать эту справку

<b>⚙️ Настройка профиля:</b>
/setgoal &lt;текст&gt; - установить цель обучения
/setlevel &lt;beginner|junior|middle|advanced&gt; - установить уровень
/settime &lt;минуты&gt; - установить ежедневное время обучения
/profile - показать профиль и статистику

<b>📖 Обучение:</b>
/plan - построить персональный план обучения
/topic &lt;тема&gt; - объяснить тему
/topic &lt;тема&gt; &lt;подтема&gt; - объяснить подтему
/quiz &lt;тема&gt; - начать квиз по теме
/quiz &lt;тема&gt; &lt;сложность&gt; - квиз с указанием сложности
/answer &lt;вариант&gt; - ответить на вопрос квиза
/progress - показать прогресс обучения

<b>📝 Заметки и ресурсы:</b>
/note &lt;название&gt; | &lt;содержание&gt; - создать заметку
/mynotes - показать мои заметки
/resources &lt;тема&gt; - найти ресурсы по теме

<b>📊 Статистика:</b>
/stats - подробная статистика обучения
/daily - статистика за сегодня
/achievements - мои достижения

<b>🎯 Мотивация:</b>
/reminder - настроить напоминания
/streak - показать серию обучения
/challenge - получить задание на сегодня
"""


def format_profile(user_row: sqlite3.Row) -> str:
    strengths = json.loads(user_row["strengths_json"] or "[]")
    weak_topics = json.loads(user_row["weak_topics_json"] or "[]")
    completed = json.loads(user_row["completed_topics_json"] or "[]")
    
    daily_stats = get_daily_stats(user_row["user_id"])
    
    profile_text = f"""
<b>📊 Ваш профиль обучения</b>

<b>🎯 Цель:</b> {user_row["goal"] or "Не указана"}
<b>📈 Уровень:</b> {user_row["level"] or "Не указан"}
<b>⏰ Ежедневное время:</b> {format_duration(user_row["daily_minutes"] or 30)}

<b>📚 Статистика:</b>
• Всего времени: {format_duration(user_row["total_study_minutes"] or 0)}
• Серия дней: {user_row["streak_days"] or 0} 🔥
• Сегодня: {daily_stats['actual']}/{daily_stats['target']} минут

<b>💪 Сильные стороны:</b>
{', '.join(strengths) if strengths else "Пока не определены"}

<b>📖 Темы для изучения:</b>
{', '.join(weak_topics) if weak_topics else "Пока не определены"}

<b>✅ Изученные темы:</b>
{len(completed)} тем изучено
"""
    return profile_text


def handle_start(chat_id: int, user_id: int, first_name: str, last_name: str = "") -> None:
    text = (
        f"Привет, {first_name}! 👋\n\n"
        "Я <b>AI Agent для развития компетенций в Data Science</b>.\n\n"
        "Я могу помочь тебе:\n"
        "🎯 Создать персональный план обучения\n"
        "📖 Объяснять сложные темы простым языком\n"
        "📝 Проверять знания через квизы\n"
        "📊 Отслеживать прогресс\n"
        "💡 Давать практические советы\n\n"
        "<b>🚀 Быстрый старт:</b>\n"
        "1. /setgoal Хочу стать Data Scientist\n"
        "2. /setlevel junior\n"
        "3. /settime 60\n"
        "4. /plan\n\n"
        "Напиши /help для просмотра всех команд"
    )
    telegram_send_message(chat_id, text)


def handle_profile(chat_id: int, user_id: int) -> None:
    user_row = get_user(user_id)
    if user_row is None:
        telegram_send_message(chat_id, "Сначала напиши /start")
        return
    
    profile_text = format_profile(user_row)
    telegram_send_message(chat_id, profile_text)


def handle_daily_stats(chat_id: int, user_id: int) -> None:
    daily_stats = get_daily_stats(user_id)
    user_row = get_user(user_id)
    
    if daily_stats["completed"]:
        status = "✅ Цель выполнена!"
    else:
        status = f"⚠️ Осталось {format_duration(daily_stats['remaining'])}"
    
    text = f"""
<b>📊 Статистика за сегодня</b>

Цель: {format_duration(daily_stats['target'])}
Выполнено: {format_duration(daily_stats['actual'])}
{status}

Серия обучения: {user_row['streak_days'] if user_row else 0} дней 🔥

Продолжай в том же духе! 💪
"""
    telegram_send_message(chat_id, text)


def handle_achievements(chat_id: int, user_id: int) -> None:
    achievements = get_user_achievements(user_id)
    
    if not achievements:
        text = "🎯 У вас пока нет достижений. Продолжайте учиться, и они появятся!"
    else:
        text = "<b>🏆 Ваши достижения:</b>\n\n"
        for ach in achievements:
            text += f"✅ {ach['achievement_name']}\n"
            text += f"   <i>{ach['achieved_at'][:10]}</i>\n\n"
    
    telegram_send_message(chat_id, text)


def handle_note(chat_id: int, user_id: int, args: str) -> None:
    if "|" not in args:
        telegram_send_message(chat_id, "Используй: /note <название> | <содержание>\nПример: /note Pandas basics | Метод groupby используется для...")
        return
    
    title, content = args.split("|", 1)
    title = title.strip()
    content = content.strip()
    
    if not title or not content:
        telegram_send_message(chat_id, "Название и содержание не могут быть пустыми")
        return
    
    note_id = add_note(user_id, title, content)
    telegram_send_message(chat_id, f"✅ Заметка '{title}' сохранена! (ID: {note_id})")
    log_study_event(user_id, "note_created", payload={"title": title, "note_id": note_id})


def handle_my_notes(chat_id: int, user_id: int, topic: str = "") -> None:
    notes = get_notes(user_id, topic if topic else None)
    
    if not notes:
        telegram_send_message(chat_id, "📝 У вас пока нет заметок. Создайте первую с помощью /note")
        return
    
    text = "<b>📝 Ваши заметки:</b>\n\n"
    for note in notes[:10]:  # Show last 10
        text += f"<b>{note['title']}</b>\n"
        text += f"{note['content'][:100]}...\n"
        text += f"<i>Тема: {note['topic'] or 'Общая'}</i>\n\n"
    
    if len(notes) > 10:
        text += f"<i>... и еще {len(notes) - 10} заметок</i>"
    
    telegram_send_message(chat_id, text)


def handle_resources(chat_id: int, user_id: int, topic: str) -> None:
    if not topic:
        telegram_send_message(chat_id, "Используй: /resources <тема>\nПример: /resources pandas")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT resource_type, title, url, description, difficulty
    FROM learning_resources
    WHERE topic LIKE ? OR description LIKE ?
    LIMIT 5
    """, (f"%{topic}%", f"%{topic}%"))
    
    resources = [dict(row) for row in cur.fetchall()]
    conn.close()
    
    if not resources:
        telegram_send_message(chat_id, f"Не найдено ресурсов по теме '{topic}'")
        return
    
    text = f"<b>📚 Ресурсы по теме '{topic}':</b>\n\n"
    for res in resources:
        text += f"<b>{res['title']}</b>\n"
        text += f"Тип: {res['resource_type']} | Сложность: {res['difficulty']}\n"
        text += f"{res['description']}\n"
        if res['url']:
            text += f"🔗 {res['url']}\n"
        text += "\n"
    
    telegram_send_message(chat_id, text)


def handle_stats(chat_id: int, user_id: int) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get comprehensive stats
    cur.execute("""
    SELECT 
        COUNT(DISTINCT date(created_at)) as active_days,
        COUNT(CASE WHEN event_type = 'quiz_completed' THEN 1 END) as quizzes_taken,
        COUNT(CASE WHEN event_type = 'topic_explained' THEN 1 END) as topics_studied,
        AVG(CASE WHEN event_type = 'quiz_completed' THEN 1 ELSE 0 END) as quiz_completion_rate
    FROM study_history
    WHERE user_id = ?
    """, (user_id,))
    
    stats = dict(cur.fetchone())
    
    # Get weekly activity
    cur.execute("""
    SELECT 
        date(created_at) as study_date,
        SUM(duration_minutes) as minutes
    FROM study_history
    WHERE user_id = ? AND created_at >= date('now', '-7 days')
    GROUP BY date(created_at)
    ORDER BY study_date DESC
    """, (user_id,))
    
    weekly = [dict(row) for row in cur.fetchall()]
    conn.close()
    
    user_row = get_user(user_id)
    
    text = f"""
<b>📊 Детальная статистика обучения</b>

<b>Общая информация:</b>
• Всего времени: {format_duration(user_row['total_study_minutes'] if user_row else 0)}
• Активных дней: {stats.get('active_days', 0)}
• Серия: {user_row['streak_days'] if user_row else 0} дней 🔥

<b>Активность:</b>
• Пройдено квизов: {stats.get('quizzes_taken', 0)}
• Изучено тем: {stats.get('topics_studied', 0)}
• Успешность квизов: {stats.get('quiz_completion_rate', 0) * 100:.0f}%

<b>📅 Последние 7 дней:</b>
"""
    for day in weekly[:7]:
        text += f"• {day['study_date']}: {format_duration(day['minutes'])}\n"
    
    telegram_send_message(chat_id, text)


def handle_challenge(chat_id: int, user_id: int) -> None:
    user_row = get_user(user_id)
    if not user_row:
        telegram_send_message(chat_id, "Сначала напиши /start")
        return
    
    prompt = f"""
Generate a daily learning challenge for a Data Science student.

User level: {user_row['level']}
Goal: {user_row['goal']}

Return ONLY valid JSON with this structure:
{{
    "challenge": "string",
    "topic": "string",
    "estimated_time": "string",
    "steps": ["step1", "step2", "step3"],
    "resources_needed": ["resource1", "resource2"],
    "success_criteria": "string"
}}
"""
    
    try:
        challenge = llm_json(prompt)
        text = f"""
<b>🎯 Ежедневный вызов!</b>

<b>{challenge.get('challenge', 'Практическое задание')}</b>

Тема: {challenge.get('topic', 'Data Science')}
Время: {challenge.get('estimated_time', '30 минут')}

<b>Шаги:</b>
{chr(10).join(f'{i+1}. {step}' for i, step in enumerate(challenge.get('steps', [])))}

<b>Критерии успеха:</b>
{challenge.get('success_criteria', 'Выполните все шаги')}

Готов проверить свои силы? 💪
"""
        telegram_send_message(chat_id, text)
        log_study_event(user_id, "challenge_received", payload=challenge)
    except Exception as e:
        telegram_send_message(chat_id, "Не удалось сгенерировать задание. Попробуйте позже.")


# Enhanced existing handlers
def handle_set_goal(chat_id: int, user_id: int, text: str) -> None:
    goal = text.strip()
    if not goal:
        telegram_send_message(chat_id, "Используй: /setgoal <твоя цель>\nПример: /setgoal Хочу стать Data Scientist в fintech")
        return

    update_user_profile(user_id, goal=goal)
    log_study_event(user_id, "set_goal", payload={"goal": goal})
    
    # Generate initial recommendations based on goal
    telegram_send_message(chat_id, f"✅ Цель сохранена!\n\n{goal}\n\nОтлично! Теперь укажи свой уровень: /setlevel")


def handle_set_level(chat_id: int, user_id: int, text: str) -> None:
    level = text.strip().lower()
    allowed = {"beginner", "junior", "middle", "advanced"}

    if level not in allowed:
        telegram_send_message(chat_id, "Используй: /setlevel beginner|junior|middle|advanced\n\n"
                                      "• beginner - начинающий\n"
                                      "• junior - начальный уровень\n"
                                      "• middle - средний уровень\n"
                                      "• advanced - продвинутый")
        return

    update_user_profile(user_id, level=level)
    log_study_event(user_id, "set_level", payload={"level": level})
    telegram_send_message(chat_id, f"✅ Уровень сохранён: {level}\n\nТеперь установи ежедневное время: /settime")


def handle_set_time(chat_id: int, user_id: int, text: str) -> None:
    text = text.strip()
    if not text.isdigit():
        telegram_send_message(chat_id, "Используй: /settime 60\n\nУкажи количество минут (от 15 до 480)")
        return

    minutes = int(text)
    if minutes < 15 or minutes > 480:
        telegram_send_message(chat_id, "Укажи разумное количество минут (от 15 до 480)")
        return

    update_user_profile(user_id, daily_minutes=minutes)
    log_study_event(user_id, "set_time", payload={"daily_minutes": minutes})
    telegram_send_message(chat_id, f"✅ Ежедневное время: {format_duration(minutes)}\n\nТеперь можно создать план: /plan")


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

    telegram_send_typing(chat_id)
    telegram_send_message(chat_id, "🧠 Строю персональный план обучения... ⏳")
    
    try:
        plan = planner_agent(user_row)
        update_user_profile(user_id, current_plan=json.dumps(plan, ensure_ascii=False))
        log_study_event(user_id, "plan_generated", payload={"plan": plan})
        
        # Format plan nicely
        text = f"<b>📚 Ваш персональный план обучения</b>\n\n"
        text += f"<b>Обзор:</b> {plan.get('overview', '')}\n\n"
        
        for week in plan.get('weeks', []):
            text += f"<b>Неделя {week.get('week')}: {week.get('focus')}</b>\n"
            text += f"Темы: {', '.join(week.get('topics', []))}\n"
            text += f"Проекты: {', '.join(week.get('projects', []))}\n\n"
        
        text += f"<b>🏆 Вехи:</b>\n"
        for milestone in plan.get('milestones', []):
            text += f"• {milestone}\n"
        
        telegram_send_message(chat_id, text[:4000])
    except Exception as e:
        logging.error(f"Plan generation failed: {e}")
        telegram_send_message(chat_id, "Не удалось сгенерировать план. Попробуйте позже.")


def handle_topic(chat_id: int, user_id: int, args: str) -> None:
    parts = args.split(" ", 1)
    topic = parts[0].strip()
    subtopic = parts[1].strip() if len(parts) > 1 else ""

    if not topic:
        telegram_send_message(chat_id, "Используй: /topic pandas\nили /topic pandas groupby")
        return

    user_row = get_user(user_id)
    if user_row is None:
        telegram_send_message(chat_id, "Сначала напиши /start")
        return

    telegram_send_typing(chat_id)
    telegram_send_message(chat_id, f"📖 Готовлю объяснение по теме: {topic}... ⏳")
    
    try:
        explanation = tutor_agent(topic, user_row, subtopic)
        log_study_event(user_id, "topic_explained", topic=topic, subtopic=subtopic, duration_minutes=10)
        update_study_time(user_id, 10, topic)
        
        text = f"<b>{explanation.get('title', topic)}</b>\n\n"
        text += f"{explanation.get('detailed_explanation', '')}\n\n"
        
        if explanation.get('code_example'):
            text += f"<b>💻 Пример кода:</b>\n<code>{explanation.get('code_example')}</code>\n\n"
        
        text += f"<b>🎯 Ключевые выводы:</b>\n"
        for takeaway in explanation.get('key_takeaways', []):
            text += f"• {takeaway}\n"
        
        telegram_send_message(chat_id, text[:4000])
    except Exception as e:
        logging.error(f"Topic explanation failed: {e}")
        telegram_send_message(chat_id, "Не удалось объяснить тему. Попробуйте позже.")


def handle_quiz(chat_id: int, user_id: int, args: str) -> None:
    parts = args.split()
    topic = parts[0].strip() if parts else ""
    difficulty = parts[1].strip() if len(parts) > 1 else "medium"

    if not topic:
        telegram_send_message(chat_id, "Используй: /quiz pandas\nили /quiz pandas hard")
        return

    user_row = get_user(user_id)
    if user_row is None:
        telegram_send_message(chat_id, "Сначала напиши /start")
        return

    telegram_send_typing(chat_id)
    telegram_send_message(chat_id, f"📝 Генерирую квиз по теме: {topic} (сложность: {difficulty})... ⏳")
    
    try:
        questions = quiz_agent(topic, user_row, num_questions=5, difficulty=difficulty)
        session_id = create_quiz_session(user_id, topic, questions)
        log_study_event(user_id, "quiz_started", topic=topic, payload={"session_id": session_id, "difficulty": difficulty})
        
        # Store difficulty in session (would need to update schema)
        send_next_quiz_question(chat_id, user_id)
    except Exception as e:
        logging.error(f"Quiz generation failed: {e}")
        telegram_send_message(chat_id, "Не удалось сгенерировать квиз. Попробуйте позже.")


def handle_progress(chat_id: int, user_id: int) -> None:
    user_row = get_user(user_id)
    if user_row is None:
        telegram_send_message(chat_id, "Сначала напиши /start")
        return

    telegram_send_typing(chat_id)
    telegram_send_message(chat_id, "📊 Анализирую прогресс... ⏳")
    
    try:
        report = progress_agent(user_row)
        
        text = f"<b>📈 Анализ прогресса</b>\n\n"
        text += f"{report.get('progress_summary', '')}\n\n"
        
        text += f"<b>💪 Сильные стороны:</b>\n"
        for strength in report.get('strengths_identified', []):
            text += f"• {strength}\n"
        
        text += f"\n<b>📚 Рекомендации:</b>\n"
        for rec in report.get('recommendations', []):
            text += f"• {rec}\n"
        
        if report.get('achievements_to_celebrate'):
            text += f"\n<b>🏆 Достижения:</b>\n"
            for ach in report.get('achievements_to_celebrate'):
                text += f"• {ach}\n"
        
        telegram_send_message(chat_id, text[:4000])
    except Exception as e:
        logging.error(f"Progress analysis failed: {e}")
        telegram_send_message(chat_id, "Не удалось проанализировать прогресс. Попробуйте позже.")


# =========================
# Router (Enhanced)
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

    upsert_user(user_id, username, first_name)

    command, args = parse_command(text)

    try:
        if command == "/start":
            handle_start(chat_id, user_id, first_name, last_name)
        elif command == "/help":
            telegram_send_message(chat_id, format_help())
        elif command == "/setgoal":
            handle_set_goal(chat_id, user_id, args)
        elif command == "/setlevel":
            handle_set_level(chat_id, user_id, args)
        elif command == "/settime":
            handle_set_time(chat_id, user_id, args)
        elif command == "/profile":
            handle_profile(chat_id, user_id)
        elif command == "/plan":
            handle_plan(chat_id, user_id)
        elif command == "/topic":
            handle_topic(chat_id, user_id, args)
        elif command == "/quiz":
            handle_quiz(chat_id, user_id, args)
        elif command == "/answer":
            handle_answer(chat_id, user_id, args)  # Keep existing handle_answer
        elif command == "/progress":
            handle_progress(chat_id, user_id)
        elif command == "/stats":
            handle_stats(chat_id, user_id)
        elif command == "/daily":
            handle_daily_stats(chat_id, user_id)
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
            user_row = get_user(user_id)
            streak = user_row["streak_days"] if user_row else 0
            telegram_send_message(chat_id, f"🔥 Ваша серия обучения: {streak} дней!\n\nПродолжайте в том же духе!")
        else:
            # Handle unknown commands with a helpful message
            telegram_send_message(
                chat_id,
                "Я не знаю эту команду.\n\n"
                "Попробуйте:\n"
                "/help - список всех команд\n"
                "/topic <тема> - изучить тему\n"
                "/quiz <тема> - проверить знания"
            )
    except Exception as e:
        logging.exception("Error while handling message")
        telegram_send_message(chat_id, f"❌ Произошла ошибка: {str(e)[:200]}\n\nПопробуйте позже.")


# =========================
# Reminder Scheduler
# =========================
def send_daily_reminders():
    """Send daily learning reminders to users"""
    if not ENABLE_REMINDERS:
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get users who have notifications enabled and haven't completed today's goal
    cur.execute("""
    SELECT u.user_id, u.first_name, u.daily_minutes, d.actual_minutes
    FROM users u
    LEFT JOIN daily_goals d ON u.user_id = d.user_id AND d.goal_date = date('now')
    WHERE u.notifications_enabled = 1 
    AND (d.actual_minutes IS NULL OR d.actual_minutes < u.daily_minutes)
    """)
    
    users_to_remind = cur.fetchall()
    conn.close()
    
    for user in users_to_remind:
        try:
            remaining = user["daily_minutes"] - (user["actual_minutes"] or 0)
            text = f"🔔 <b>Напоминание об обучении!</b>\n\n"
            text += f"Сегодня вы изучили {format_duration(user['actual_minutes'] or 0)} из {format_duration(user['daily_minutes'])}\n"
            text += f"Осталось: {format_duration(remaining)}\n\n"
            text += f"Готовы продолжить? Напишите /topic или /quiz чтобы начать! 💪"
            
            telegram_send_message(user["user_id"], text)
        except Exception as e:
            logging.error(f"Failed to send reminder to {user['user_id']}: {e}")


# =========================
# Main loop
# =========================
def run_bot() -> None:
    init_db()
    logging.info("Bot started.")
    
    # Setup scheduler for reminders
    scheduler = BackgroundScheduler()
    if ENABLE_REMINDERS:
        scheduler.add_job(send_daily_reminders, 'cron', hour=19, minute=0)  # 7 PM daily
        scheduler.start()
        logging.info("Reminder scheduler started")

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