import psycopg

from banking.events import decode

UPSERT = """
INSERT INTO ingest.transaction_state AS current
    (transaction_id, account_id, amount_minor, currency, status, created_at, updated_at,
     version, deleted)
VALUES (%(transaction_id)s, %(account_id)s, %(amount_minor)s, %(currency)s,
        %(status)s, %(created_at)s, %(updated_at)s, %(version)s, %(deleted)s)
ON CONFLICT (transaction_id) DO UPDATE SET
    account_id = EXCLUDED.account_id,
    amount_minor = EXCLUDED.amount_minor,
    currency = EXCLUDED.currency,
    status = EXCLUDED.status,
    created_at = EXCLUDED.created_at,
    updated_at = EXCLUDED.updated_at,
    version = EXCLUDED.version,
    deleted = EXCLUDED.deleted
WHERE (EXCLUDED.version, EXCLUDED.deleted) > (current.version, current.deleted)
"""


def persist(conn: psycopg.Connection, coordinate: tuple[str, int, int],
            key: bytes | None, value: bytes | None) -> str:
    reason = None
    change = None
    try:
        change = decode(key, value)
        outcome = "tombstone" if change is None else "accepted"
    except ValueError as error:
        outcome = "quarantined"
        # Validation errors can include raw fields. Store the category in the reason.
        reason = type(error).__name__

    with conn.transaction():
        inserted = conn.execute("""
            INSERT INTO ingest.receipts VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING RETURNING 1
        """, (*coordinate, outcome)).fetchone()
        if inserted is None:
            return "duplicate"
        if reason is not None:
            conn.execute("""
                INSERT INTO ingest.quarantine
                    (topic, partition_id, offset_id, raw_key, raw_value, reason)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (*coordinate, key, value, reason))
        if change is not None:
            applied = conn.execute(UPSERT, change.row.model_dump() | {"deleted": change.deleted})
            return "applied" if applied.rowcount else "stale"
    return outcome
