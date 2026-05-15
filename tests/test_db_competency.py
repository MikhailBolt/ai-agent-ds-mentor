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


def test_reset_clears_competency_stats(conn: sqlite3.Connection) -> None:
    mentor_db.record_quiz_result(conn, 1, True, competency_id="a")
    mentor_db.reset_user(conn, 1)
    assert mentor_db.get_competency_stats(conn, 1) == {}
