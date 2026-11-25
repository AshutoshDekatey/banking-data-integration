import os

import psycopg
import pytest

from banking.config import dsn
from banking.sink import persist
from test_events import FIXTURE, KEY, envelope

pytestmark = pytest.mark.skipif(os.environ.get("BANKING_TEST_SQL") != "1",
                                reason="Requires disposable target PostgreSQL")


def test_state_and_receipt_are_atomic() -> None:
    with psycopg.connect(dsn("target")) as conn:
        conn.execute("TRUNCATE ingest.quarantine, ingest.receipts, ingest.transaction_state")
        topic = "fixture"
        identify = lambda offset: (topic, 0, offset)
        updated = FIXTURE | {"version": 2, "amount_minor": 3500, "status": "settled"}
        assert persist(conn, identify(1), KEY, envelope("u", updated)) == "applied"
        assert persist(conn, identify(1), KEY, envelope("u", updated)) == "duplicate"
        assert persist(conn, identify(2), KEY, envelope("u", updated)) == "stale"
        assert persist(conn, identify(3), KEY, envelope("c", FIXTURE)) == "stale"
        assert persist(conn, identify(4), KEY, envelope("d", updated)) == "applied"
        assert persist(conn, identify(5), KEY, envelope("u", updated)) == "stale"
        assert persist(conn, identify(6), KEY, None) == "tombstone"
        assert persist(conn, identify(7), KEY, b"invalid") == "quarantined"
        assert conn.execute("SELECT amount_minor, version, deleted FROM ingest.transaction_state").fetchone() == (
            3500, 2, True
        )
        assert conn.execute("SELECT count(*) FROM ingest.quarantine").fetchone() == (1,)

        conn.execute("""
            ALTER TABLE ingest.transaction_state ADD CONSTRAINT injected_failure CHECK (version < 3)
        """)
        with pytest.raises(psycopg.errors.CheckViolation):
            persist(conn, identify(8), KEY, envelope("u", updated | {"version": 3}))
        assert conn.execute("SELECT count(*) FROM ingest.receipts WHERE offset_id = 8").fetchone() == (0,)
        conn.execute("ALTER TABLE ingest.transaction_state DROP CONSTRAINT injected_failure")
        assert persist(conn, identify(8), KEY, envelope("u", updated | {"version": 3})) == "applied"
        conn.rollback()
