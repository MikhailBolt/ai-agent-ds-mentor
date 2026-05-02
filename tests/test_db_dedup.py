import sqlite3

import pytest

from mentor import db as mentor_db


@pytest.fixture()
def conn(tmp_path) -> sqlite3.Connection:
    db_path = str(tmp_path / "t.db")
    c = mentor_db.connect(db_path)
    mentor_db.ensure_schema(c)
    return c


def test_claim_message_revision_allows_first_seen(conn: sqlite3.Connection) -> None:
    assert mentor_db.claim_message_revision(conn, 1, 10, None) is True


def test_claim_message_revision_skips_exact_retry(conn: sqlite3.Connection) -> None:
    assert mentor_db.claim_message_revision(conn, 1, 10, None) is True
    assert mentor_db.claim_message_revision(conn, 1, 10, None) is False


def test_claim_message_revision_allows_edit_updates(conn: sqlite3.Connection) -> None:
    assert mentor_db.claim_message_revision(conn, 1, 10, None) is True
    assert mentor_db.claim_message_revision(conn, 1, 10, 100) is True
    assert mentor_db.claim_message_revision(conn, 1, 10, 100) is False
    assert mentor_db.claim_message_revision(conn, 1, 10, 101) is True
