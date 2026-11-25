"""Integration assertions against real broker offsets and PostgreSQL databases."""
import argparse
import os
import time

import psycopg
from confluent_kafka import Consumer, TopicPartition

from banking.bootstrap import TOPIC
from banking.config import dsn
from banking.reconcile import reconcile

TOTALS = """
SELECT (created_at AT TIME ZONE 'UTC')::date, currency, count(*), sum(amount_minor),
       count(*) FILTER (WHERE status = 'settled'),
       coalesce(sum(amount_minor) FILTER (WHERE status = 'settled'), 0),
       count(*) FILTER (WHERE status = 'failed')
FROM bank.transactions GROUP BY 1, 2 ORDER BY 1, 2
"""
MART_TOTALS = """
SELECT d.created_date, d.currency, d.transaction_count, d.total_minor,
       coalesce(s.settled_count, 0), coalesce(s.settled_minor, 0), f.failed_count
FROM analytics.daily_totals d
LEFT JOIN analytics.settled_payments s USING (created_date, currency)
JOIN analytics.failed_payments f USING (created_date, currency)
ORDER BY 1, 2
"""


ACCOUNT_TOTALS = """
SELECT account_id, currency, count(*), sum(amount_minor),
       coalesce(sum(amount_minor) FILTER (WHERE status = 'settled'), 0)
FROM bank.transactions GROUP BY 1, 2 ORDER BY 1, 2
"""
MART_ACCOUNT_TOTALS = """
SELECT account_id, currency, transaction_count, total_minor, settled_minor
FROM analytics.account_totals ORDER BY 1, 2
"""


def wait_for_group(group: str, timeout: int = 120) -> None:
    consumer = Consumer({
        "bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP", "broker:29092"),
        "group.id": group,
        "enable.auto.commit": False,
    })
    partitions = [TopicPartition(TOPIC, index) for index in range(3)]
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            committed = consumer.committed(partitions, timeout=10)
            high = [consumer.get_watermark_offsets(p, timeout=10)[1] for p in partitions]
            if any(high) and all(c.offset == end or (end == 0 and c.offset < 0)
                                 for c, end in zip(committed, high, strict=True)):
                print(f"group={group} caught up offsets={high}", flush=True)
                return
            time.sleep(2)
    finally:
        consumer.close()
    raise TimeoutError(f"Consumer group {group} did not catch up")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("check", choices=["state", "aggregates", "offsets", "poison"])
    args = parser.parse_args()
    if args.check == "offsets":
        wait_for_group(os.environ.get("CDC_GROUP", "banking-sink-v1"))
    elif args.check == "aggregates":
        with psycopg.connect(dsn("source")) as source, psycopg.connect(dsn("target")) as target:
            assert source.execute(TOTALS).fetchall() == target.execute(MART_TOTALS).fetchall()
            assert source.execute(ACCOUNT_TOTALS).fetchall() == target.execute(MART_ACCOUNT_TOTALS).fetchall()
        print("Source and dbt totals match")
    elif args.check == "poison":
        with psycopg.connect(dsn("target")) as target:
            assert target.execute(
                "SELECT count(*) FROM ingest.quarantine WHERE raw_value = %s", (b"invalid-json",)
            ).fetchone() == (1,)
    else:
        deadline = time.monotonic() + 120
        while reconcile()["exception_count"]:
            if time.monotonic() >= deadline:
                raise AssertionError("Target state differs from source")
            time.sleep(2)


if __name__ == "__main__":
    main()
