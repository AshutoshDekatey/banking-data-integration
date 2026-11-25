# Verification evidence

## Executed in the authoring workspace

- Python 3.12 and PostgreSQL 16.2 with the repository SQL applied to two disposable instances. All 26 Pytest cases passed, including transactional rollback, duplicate and out-of-order changes, delete precedence, poison quarantine, and Kafka topic registration.
- FastAPI and PostgreSQL lifecycle smoke test with 120 synthetic transactions. Duplicate and stale writes were rejected. Reconciliation detected 108 missing active rows. Backfill brought exceptions to zero, including on repeat execution.
- Native integration used PostgreSQL 16.2, Debezium PostgreSQL connector 3.1.2.Final, Apache Kafka 4.1.2, and the repository API and consumer. The initial snapshot loaded 20 rows. Live CDC and outage-recovery drills brought the workload to 160 created payments across all scenarios, with 148 current rows and 12 delete markers. The consumer retried the unavailable target, resumed after restart, and recovered after stopping and starting Kafka.
- Both consumer groups reached offsets `[118, 99, 81]` across the three partitions. Before and after replay, source and target state matched with zero exceptions and the same financial aggregates. The target retained 285 accepted receipts, 12 tombstone receipts, and one quarantined record.
- dbt Core 1.9.8 with PostgreSQL adapter 1.9.0. All six views built and all 12 data tests passed. Independent source SQL matched the daily, settled, failed, and account aggregates.
- Airflow 2.10.5 ran all tasks in both DAGs via `DAG.test()` using local metadata and real PostgreSQL source and target instances.

## Docker variant

The authoring environment lacked a Docker engine. The native integration used Apache Kafka. GitHub Actions runs the separate Compose suite with Redpanda. See the pull request checks for its status. The optional Airflow Compose deployment has its own startup instructions in the [runbook](RUNBOOK.md).
