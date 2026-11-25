from datetime import timedelta

import pendulum
from airflow.decorators import dag, task

from banking.reconcile import reconcile


@task(retries=2, retry_delay=timedelta(seconds=30))
def compare(backfill: bool = False) -> dict[str, int]:
    return reconcile(backfill)


@task
def check_quality(result: dict[str, int]) -> None:
    if result["exception_count"]:
        raise ValueError(f"Reconciliation exceptions: {result['exception_count']}")


@task
def report(result: dict[str, int]) -> None:
    print(result)


@dag(schedule="*/15 * * * *", start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
     catchup=False, max_active_runs=1)
def banking_reconciliation():
    result = compare()
    report(result)
    check_quality(result)


@dag(schedule=None, start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
     catchup=False, max_active_runs=1)
def banking_backfill():
    result = compare(True)
    report(result)
    check_quality(result)


banking_reconciliation()
banking_backfill()
