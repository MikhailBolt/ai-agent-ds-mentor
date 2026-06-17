import sqlite3

import pytest

from mentor import db as mentor_db


@pytest.fixture()
def conn(tmp_path) -> sqlite3.Connection:
    c = mentor_db.connect(str(tmp_path / "t.db"))
    mentor_db.ensure_schema(c)
    mentor_db.touch_user(c, 1)
    return c


def test_record_competency_stats(conn: sqlite3.Connection) -> None:
    mentor_db.record_quiz_result(conn, 1, True, competency_id="ml-metrics")
    mentor_db.record_quiz_result(conn, 1, False, competency_id="ml-metrics")
    stats = mentor_db.get_competency_stats(conn, 1)
    assert stats["ml-metrics"] == (1, 2)


def test_quiz_streak(conn: sqlite3.Connection) -> None:
    mentor_db.touch_user(conn, 1)
    assert mentor_db.record_quiz_result(conn, 1, True) == 1
    assert mentor_db.record_quiz_result(conn, 1, True) == 2
    assert mentor_db.record_quiz_result(conn, 1, False) == 0
    assert mentor_db.record_quiz_result(conn, 1, True) == 1


def test_reset_clears_streak(conn: sqlite3.Connection) -> None:
    mentor_db.record_quiz_result(conn, 1, True)
    mentor_db.reset_user(conn, 1)
    assert mentor_db.get_streak(conn, 1) == 0


def test_streak_column_migrated_on_old_db(tmp_path) -> None:
    db_path = tmp_path / "legacy.db"
    c = sqlite3.connect(db_path)
    c.execute(
        """
        CREATE TABLE users (
          chat_id INTEGER PRIMARY KEY,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
          quiz_correct INTEGER NOT NULL DEFAULT 0,
          quiz_total INTEGER NOT NULL DEFAULT 0,
          active_question_id TEXT
        )
        """
    )
    c.commit()
    c.close()
    c2 = mentor_db.connect(str(db_path))
    mentor_db.ensure_schema(c2)
    cols = {row[1] for row in c2.execute("PRAGMA table_info(users)").fetchall()}
    assert "quiz_streak" in cols
    c2.close()


def test_reset_clears_competency_stats(conn: sqlite3.Connection) -> None:
    mentor_db.record_quiz_result(conn, 1, True, competency_id="a")
    mentor_db.record_question_attempt(conn, 1, "q1", is_correct=True)
    mentor_db.reset_user(conn, 1)
    assert mentor_db.get_competency_stats(conn, 1) == {}
    assert mentor_db.get_seen_question_ids(conn, 1) == set()


def test_best_streak_tracked(conn: sqlite3.Connection) -> None:
    mentor_db.touch_user(conn, 1)
    mentor_db.record_quiz_result(conn, 1, True)
    mentor_db.record_quiz_result(conn, 1, True)
    assert mentor_db.get_best_streak(conn, 1) == 2
    mentor_db.record_quiz_result(conn, 1, False)
    mentor_db.record_quiz_result(conn, 1, True)
    assert mentor_db.get_streak(conn, 1) == 1
    assert mentor_db.get_best_streak(conn, 1) == 2


def test_retry_question_id(conn: sqlite3.Connection) -> None:
    mentor_db.set_active_question(conn, 1, "q1")
    mentor_db.set_retry_question_id(conn, 1, "q1")
    assert mentor_db.get_retry_question_id(conn, 1) == "q1"
    mentor_db.set_active_question(conn, 1, None)
    assert mentor_db.get_retry_question_id(conn, 1) is None


def test_daily_answer_count_resets_by_date(conn: sqlite3.Connection) -> None:
    mentor_db.touch_user(conn, 1)
    mentor_db.record_quiz_result(conn, 1, True)
    assert mentor_db.get_daily_answer_count(conn, 1) == 1
    conn.execute(
        "UPDATE users SET daily_answer_date='2000-01-01' WHERE chat_id=1",
    )
    conn.commit()
    assert mentor_db.get_daily_answer_count(conn, 1) == 0


def test_mastered_question_ids(conn: sqlite3.Connection) -> None:
    mentor_db.record_question_attempt(conn, 1, "q1", is_correct=False)
    mentor_db.record_question_attempt(conn, 1, "q1", is_correct=True)
    mentor_db.record_question_attempt(conn, 1, "q2", is_correct=False)
    mastered = mentor_db.get_mastered_question_ids(conn, 1)
    assert mastered == {"q1"}


def test_review_question_ids(conn: sqlite3.Connection) -> None:
    mentor_db.record_question_attempt(conn, 1, "q1", is_correct=False)
    mentor_db.record_question_attempt(conn, 1, "q2", is_correct=True)
    ids = mentor_db.get_review_question_ids(conn, 1)
    assert ids == ["q1"]


def test_question_history_attempts(conn: sqlite3.Connection) -> None:
    mentor_db.record_question_attempt(conn, 1, "q1", is_correct=False)
    mentor_db.record_question_attempt(conn, 1, "q1", is_correct=True)
    assert mentor_db.get_seen_question_ids(conn, 1) == {"q1"}
