# Airflow

Airflow is optional and runs with LocalExecutor and its own metadata PostgreSQL in the `orchestration` profile. Start it with the [runbook](RUNBOOK.md). The streaming consumer runs as an independent Compose service.

| DAG | Schedule | Work |
| --- | --- | --- |
| `banking_reconciliation` | Every 15 minutes after unpausing | Compare row state, persist exceptions and a run record, report counts, fail the quality task if differences remain |
| `banking_backfill` | On demand | Repair missing or older active target rows with the same version guard as the consumer, then reconcile and report |

Backfill reads a repeatable-read source snapshot and never moves Kafka offsets. Existing newer rows and deletion markers are preserved. Target-only rows and same-version corruption remain exceptions for investigation. Use a source-write pause and drained broker lag for decisive comparisons. Full scans fit the synthetic workload. A larger deployment would reconcile indexed time ranges or checksums with an agreed watermark.
