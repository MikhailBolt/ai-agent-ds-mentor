import sqlite3

import pytest

from mentor import db as mentor_db


@pytest.fixture()
def conn(tmp_path) -> sqlite3.Connection:
    c = mentor_db.connect(str(tmp_path / "t.db"))
    mentor_db.ensure_schema(c)
    return c


def test_verify_schema_ok(conn: sqlite3.Connection) -> None:
    mentor_db.verify_schema(conn)


def test_verify_schema_missing_table(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE message_revisions")
    conn.commit()
    with pytest.raises(ValueError, match="missing tables"):
        mentor_db.verify_schema(conn)
