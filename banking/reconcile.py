import argparse
import json

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from banking.config import dsn
from banking.logging import log
from banking.sink import UPSERT

COLUMNS = "transaction_id, account_id, amount_minor, currency, status, created_at, updated_at, version"


def reconcile(backfill: bool = False) -> dict[str, int]:
    with psycopg.connect(dsn("target"), row_factory=dict_row) as target:
        target.execute("SELECT pg_advisory_xact_lock(82141)")
        with psycopg.connect(dsn("source"), row_factory=dict_row) as source:
            source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            source_rows = {
                row["transaction_id"]: row
                for row in source.execute(f"SELECT {COLUMNS} FROM bank.transactions")
            }
        if backfill:
            with target.cursor() as cursor:
                cursor.executemany(
                    UPSERT, (row | {"deleted": False} for row in source_rows.values())
                )
        target_rows = {
            row["transaction_id"]: row
            for row in target.execute(f"SELECT {COLUMNS} FROM ingest.transaction_state WHERE NOT deleted")
        }
        exceptions = [
            (key, Jsonb(source_rows[key], dumps=as_json) if key in source_rows else None,
             Jsonb(target_rows[key], dumps=as_json) if key in target_rows else None)
            for key in sorted(source_rows.keys() | target_rows.keys())
            if source_rows.get(key) != target_rows.get(key)
        ]
        target.execute("DELETE FROM ingest.reconciliation_exceptions")
        with target.cursor() as cursor:
            cursor.executemany("INSERT INTO ingest.reconciliation_exceptions VALUES (%s, %s, %s)", exceptions)
        result = {
            "source_count": len(source_rows),
            "target_count": len(target_rows),
            "exception_count": len(exceptions),
        }
        target.execute("""
            INSERT INTO ingest.reconciliation_runs (source_count, target_count, exception_count)
            VALUES (%(source_count)s, %(target_count)s, %(exception_count)s)
        """, result)
    log("reconciliation_complete", backfill=backfill, **result)
    return result


def as_json(value: dict) -> str:
    return json.dumps(value, default=str)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    result = reconcile(args.backfill)
    if args.strict and result["exception_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
