import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
  chat_id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
  quiz_correct INTEGER NOT NULL DEFAULT 0,
  quiz_total INTEGER NOT NULL DEFAULT 0,
  active_question_id TEXT
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def touch_user(conn: sqlite3.Connection, chat_id: int) -> None:
    conn.execute(
        """
        INSERT INTO users (chat_id) VALUES (?)
        ON CONFLICT(chat_id) DO UPDATE SET last_seen_at=datetime('now')
        """,
        (chat_id,),
    )
    conn.commit()


def set_active_question(conn: sqlite3.Connection, chat_id: int, qid: Optional[str]) -> None:
    conn.execute(
        "UPDATE users SET active_question_id=? WHERE chat_id=?",
        (qid, chat_id),
    )
    conn.commit()


def get_active_question(conn: sqlite3.Connection, chat_id: int) -> Optional[str]:
    row = conn.execute(
        "SELECT active_question_id FROM users WHERE chat_id=?",
        (chat_id,),
    ).fetchone()
    if row is None:
        return None
    qid = row["active_question_id"]
    return str(qid) if qid is not None else None


def record_quiz_result(conn: sqlite3.Connection, chat_id: int, is_correct: bool) -> None:
    conn.execute(
        """
        UPDATE users
        SET quiz_total = quiz_total + 1,
            quiz_correct = quiz_correct + ?
        WHERE chat_id = ?
        """,
        (1 if is_correct else 0, chat_id),
    )
    conn.commit()


@dataclass(frozen=True)
class Stats:
    correct: int
    total: int


def get_stats(conn: sqlite3.Connection, chat_id: int) -> Stats:
    row = conn.execute(
        "SELECT quiz_correct, quiz_total FROM users WHERE chat_id=?",
        (chat_id,),
    ).fetchone()
    if row is None:
        return Stats(correct=0, total=0)
    return Stats(correct=int(row["quiz_correct"]), total=int(row["quiz_total"]))


def reset_user(conn: sqlite3.Connection, chat_id: int) -> None:
    conn.execute(
        """
        UPDATE users
        SET quiz_correct=0, quiz_total=0, active_question_id=NULL
        WHERE chat_id=?
        """,
        (chat_id,),
    )
    conn.commit()

