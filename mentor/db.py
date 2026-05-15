from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
  chat_id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
  quiz_correct INTEGER NOT NULL DEFAULT 0,
  quiz_total INTEGER NOT NULL DEFAULT 0,
  active_question_id TEXT
);

CREATE TABLE IF NOT EXISTS message_revisions (
  chat_id INTEGER NOT NULL,
  message_id INTEGER NOT NULL,
  last_edit_date INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (chat_id, message_id)
);

CREATE TABLE IF NOT EXISTS competency_stats (
  chat_id INTEGER NOT NULL,
  competency_id TEXT NOT NULL,
  correct INTEGER NOT NULL DEFAULT 0,
  total INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (chat_id, competency_id)
);
"""

EXPECTED_TABLES = ("users", "message_revisions", "competency_stats")


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # WAL improves crash recovery and concurrent readers; busy_timeout avoids rare lock errors.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def verify_schema(conn: sqlite3.Connection) -> None:
    """Raise ValueError if required tables are missing."""
    names = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    missing = [name for name in EXPECTED_TABLES if name not in names]
    if missing:
        raise ValueError("missing tables: " + ", ".join(missing))


def touch_user(conn: sqlite3.Connection, chat_id: int) -> None:
    conn.execute(
        """
        INSERT INTO users (chat_id) VALUES (?)
        ON CONFLICT(chat_id) DO UPDATE SET last_seen_at=datetime('now')
        """,
        (chat_id,),
    )
    conn.commit()


def set_active_question(conn: sqlite3.Connection, chat_id: int, qid: str | None) -> None:
    conn.execute(
        "UPDATE users SET active_question_id=? WHERE chat_id=?",
        (qid, chat_id),
    )
    conn.commit()


def get_active_question(conn: sqlite3.Connection, chat_id: int) -> str | None:
    row = conn.execute(
        "SELECT active_question_id FROM users WHERE chat_id=?",
        (chat_id,),
    ).fetchone()
    if row is None:
        return None
    qid = row["active_question_id"]
    return str(qid) if qid is not None else None


def record_quiz_result(
    conn: sqlite3.Connection,
    chat_id: int,
    is_correct: bool,
    *,
    competency_id: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE users
        SET quiz_total = quiz_total + 1,
            quiz_correct = quiz_correct + ?
        WHERE chat_id = ?
        """,
        (1 if is_correct else 0, chat_id),
    )
    if competency_id:
        conn.execute(
            """
            INSERT INTO competency_stats (chat_id, competency_id, correct, total)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(chat_id, competency_id) DO UPDATE SET
              correct = correct + excluded.correct,
              total = total + 1
            """,
            (chat_id, competency_id, 1 if is_correct else 0),
        )
    conn.commit()


def get_competency_stats(conn: sqlite3.Connection, chat_id: int) -> dict[str, tuple[int, int]]:
    rows = conn.execute(
        """
        SELECT competency_id, correct, total
        FROM competency_stats
        WHERE chat_id=?
        """,
        (chat_id,),
    ).fetchall()
    return {str(r["competency_id"]): (int(r["correct"]), int(r["total"])) for r in rows}


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
    conn.execute("DELETE FROM competency_stats WHERE chat_id=?", (chat_id,))
    conn.commit()


def claim_message_revision(
    conn: sqlite3.Connection,
    chat_id: int,
    message_id: int,
    edit_date: int | None,
) -> bool:
    """Return True if this Telegram message revision should be processed.

    Telegram retries may duplicate the same update; edited_message shares message_id with the
    original message but carries a newer edit_date — those revisions must still be processed.
    """
    rev = int(edit_date) if edit_date is not None else 0

    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            """
            SELECT last_edit_date
            FROM message_revisions
            WHERE chat_id=? AND message_id=?
            """,
            (chat_id, message_id),
        ).fetchone()

        if row is None:
            conn.execute(
                """
                INSERT INTO message_revisions (chat_id, message_id, last_edit_date)
                VALUES (?, ?, ?)
                """,
                (chat_id, message_id, rev),
            )
            conn.commit()
            return True

        last = int(row["last_edit_date"])
        if rev > last:
            conn.execute(
                """
                UPDATE message_revisions
                SET last_edit_date=?
                WHERE chat_id=? AND message_id=?
                """,
                (rev, chat_id, message_id),
            )
            conn.commit()
            return True

        conn.commit()
        return False
    except Exception:
        conn.rollback()
        raise
