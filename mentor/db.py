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

CREATE TABLE IF NOT EXISTS question_history (
  chat_id INTEGER NOT NULL,
  question_id TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 1,
  correct_count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (chat_id, question_id)
);
"""

EXPECTED_TABLES = ("users", "message_revisions", "competency_stats", "question_history")


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # WAL improves crash recovery and concurrent readers; busy_timeout avoids rare lock errors.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _migrate_users(conn: sqlite3.Connection) -> None:
    cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "quiz_streak" not in cols:
        conn.execute(
            "ALTER TABLE users ADD COLUMN quiz_streak INTEGER NOT NULL DEFAULT 0",
        )
    if "best_streak" not in cols:
        conn.execute(
            "ALTER TABLE users ADD COLUMN best_streak INTEGER NOT NULL DEFAULT 0",
        )
    if "daily_answer_date" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN daily_answer_date TEXT")
    if "daily_answer_count" not in cols:
        conn.execute(
            "ALTER TABLE users ADD COLUMN daily_answer_count INTEGER NOT NULL DEFAULT 0",
        )
    if "quiz_retry_question_id" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN quiz_retry_question_id TEXT")
    if "last_question_id" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN last_question_id TEXT")


def _migrate_question_history(conn: sqlite3.Connection) -> None:
    cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(question_history)").fetchall()}
    if "last_attempt_at" not in cols:
        conn.execute("ALTER TABLE question_history ADD COLUMN last_attempt_at TEXT")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    _migrate_users(conn)
    _migrate_question_history(conn)
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
        """
        UPDATE users
        SET active_question_id=?, quiz_retry_question_id=NULL
        WHERE chat_id=?
        """,
        (qid, chat_id),
    )
    conn.commit()


def get_retry_question_id(conn: sqlite3.Connection, chat_id: int) -> str | None:
    row = conn.execute(
        "SELECT quiz_retry_question_id FROM users WHERE chat_id=?",
        (chat_id,),
    ).fetchone()
    if row is None:
        return None
    qid = row["quiz_retry_question_id"]
    return str(qid) if qid is not None else None


def set_retry_question_id(conn: sqlite3.Connection, chat_id: int, qid: str) -> None:
    conn.execute(
        "UPDATE users SET quiz_retry_question_id=? WHERE chat_id=?",
        (qid, chat_id),
    )
    conn.commit()


def set_last_question_id(conn: sqlite3.Connection, chat_id: int, qid: str | None) -> None:
    conn.execute(
        "UPDATE users SET last_question_id=? WHERE chat_id=?",
        (qid, chat_id),
    )
    conn.commit()


def get_last_question_id(conn: sqlite3.Connection, chat_id: int) -> str | None:
    row = conn.execute(
        "SELECT last_question_id FROM users WHERE chat_id=?",
        (chat_id,),
    ).fetchone()
    if row is None:
        return None
    qid = row["last_question_id"]
    return str(qid) if qid is not None else None


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
) -> int:
    """Record answer; return current streak after update."""
    if is_correct:
        conn.execute(
            """
            UPDATE users
            SET quiz_total = quiz_total + 1,
                quiz_correct = quiz_correct + 1,
                quiz_streak = quiz_streak + 1,
                best_streak = MAX(best_streak, quiz_streak + 1)
            WHERE chat_id = ?
            """,
            (chat_id,),
        )
    else:
        conn.execute(
            """
            UPDATE users
            SET quiz_total = quiz_total + 1,
                quiz_streak = 0
            WHERE chat_id = ?
            """,
            (chat_id,),
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
    conn.execute(
        """
        UPDATE users
        SET daily_answer_count = CASE
              WHEN daily_answer_date = date('now') THEN daily_answer_count + 1
              ELSE 1
            END,
            daily_answer_date = date('now')
        WHERE chat_id = ?
        """,
        (chat_id,),
    )
    conn.commit()
    return get_streak(conn, chat_id)


def get_daily_answer_count(conn: sqlite3.Connection, chat_id: int) -> int:
    row = conn.execute(
        """
        SELECT daily_answer_count, daily_answer_date
        FROM users WHERE chat_id=?
        """,
        (chat_id,),
    ).fetchone()
    if row is None:
        return 0
    today = str(
        conn.execute("SELECT date('now')").fetchone()[0],
    )
    if str(row["daily_answer_date"] or "") != today:
        return 0
    return int(row["daily_answer_count"])


def get_best_streak(conn: sqlite3.Connection, chat_id: int) -> int:
    row = conn.execute(
        "SELECT best_streak FROM users WHERE chat_id=?",
        (chat_id,),
    ).fetchone()
    if row is None:
        return 0
    return int(row["best_streak"])


def get_streak(conn: sqlite3.Connection, chat_id: int) -> int:
    row = conn.execute(
        "SELECT quiz_streak FROM users WHERE chat_id=?",
        (chat_id,),
    ).fetchone()
    if row is None:
        return 0
    return int(row["quiz_streak"])


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


@dataclass(frozen=True)
class HistoryRow:
    question_id: str
    attempts: int
    correct_count: int


def record_question_attempt(
    conn: sqlite3.Connection,
    chat_id: int,
    question_id: str,
    *,
    is_correct: bool,
) -> None:
    conn.execute(
        """
        INSERT INTO question_history (
            chat_id, question_id, attempts, correct_count, last_attempt_at
        )
        VALUES (?, ?, 1, ?, datetime('now'))
        ON CONFLICT(chat_id, question_id) DO UPDATE SET
          attempts = attempts + 1,
          correct_count = correct_count + excluded.correct_count,
          last_attempt_at = datetime('now')
        """,
        (chat_id, question_id, 1 if is_correct else 0),
    )
    conn.commit()


def get_recent_history_rows(
    conn: sqlite3.Connection,
    chat_id: int,
    *,
    limit: int = 8,
) -> list[HistoryRow]:
    rows = conn.execute(
        """
        SELECT question_id, attempts, correct_count
        FROM question_history
        WHERE chat_id=?
        ORDER BY COALESCE(last_attempt_at, '') DESC, attempts DESC
        LIMIT ?
        """,
        (chat_id, limit),
    ).fetchall()
    return [
        HistoryRow(
            question_id=str(r["question_id"]),
            attempts=int(r["attempts"]),
            correct_count=int(r["correct_count"]),
        )
        for r in rows
    ]


@dataclass(frozen=True)
class MistakeRow:
    question_id: str
    wrong: int
    attempts: int


def get_mistake_rows(
    conn: sqlite3.Connection,
    chat_id: int,
    *,
    limit: int = 10,
) -> list[MistakeRow]:
    rows = conn.execute(
        """
        SELECT question_id, attempts, correct_count
        FROM question_history
        WHERE chat_id=? AND attempts > correct_count
        ORDER BY (attempts - correct_count) DESC, attempts DESC
        LIMIT ?
        """,
        (chat_id, limit),
    ).fetchall()
    out: list[MistakeRow] = []
    for r in rows:
        attempts = int(r["attempts"])
        correct = int(r["correct_count"])
        out.append(
            MistakeRow(
                question_id=str(r["question_id"]),
                wrong=attempts - correct,
                attempts=attempts,
            )
        )
    return out


def get_review_question_ids(
    conn: sqlite3.Connection,
    chat_id: int,
    *,
    limit: int = 20,
) -> list[str]:
    """Question ids where the user missed at least once (attempts > correct_count)."""
    rows = conn.execute(
        """
        SELECT question_id
        FROM question_history
        WHERE chat_id=? AND attempts > correct_count
        ORDER BY (attempts - correct_count) DESC, attempts DESC
        LIMIT ?
        """,
        (chat_id, limit),
    ).fetchall()
    return [str(r["question_id"]) for r in rows]


def get_mastered_question_ids(conn: sqlite3.Connection, chat_id: int) -> set[str]:
    """Questions answered correctly at least once."""
    rows = conn.execute(
        """
        SELECT question_id
        FROM question_history
        WHERE chat_id=? AND correct_count >= 1
        """,
        (chat_id,),
    ).fetchall()
    return {str(r["question_id"]) for r in rows}


def get_seen_question_ids(conn: sqlite3.Connection, chat_id: int) -> set[str]:
    rows = conn.execute(
        "SELECT question_id FROM question_history WHERE chat_id=?",
        (chat_id,),
    ).fetchall()
    return {str(r["question_id"]) for r in rows}


def reset_user(conn: sqlite3.Connection, chat_id: int) -> None:
    conn.execute(
        """
        UPDATE users
        SET quiz_correct=0, quiz_total=0, quiz_streak=0,
            best_streak=0, daily_answer_count=0, daily_answer_date=NULL,
            quiz_retry_question_id=NULL, last_question_id=NULL,
            active_question_id=NULL
        WHERE chat_id=?
        """,
        (chat_id,),
    )
    conn.execute("DELETE FROM competency_stats WHERE chat_id=?", (chat_id,))
    conn.execute("DELETE FROM question_history WHERE chat_id=?", (chat_id,))
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
