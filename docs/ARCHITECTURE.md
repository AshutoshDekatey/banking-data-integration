# Architecture

The source instance owns `bank.transactions` and its immutable ID registry. API writes use optimistic locking. PostgreSQL assigns versions and enforces accepted currencies, amount bounds, immutable attributes, and status transitions. The synthetic API allows physical deletion for CDC drills. A real banking ledger would normally preserve immutable postings and express corrections as compensating entries.

The target instance owns `ingest.transaction_state`, `receipts`, and `quarantine`. A receipt and the state change or quarantine row commit together. A pure Kafka tombstone gets a receipt without altering state. The source ID registry and target soft-delete marker preserve a single version timeline. A target row advances by the lexicographic tuple `(version, deleted)`, so a delete dominates the final update at the same version.

The consumer processes one record at a time. PostgreSQL uniqueness prevents overlapping workers from applying the same coordinate twice, and the row predicate handles duplicate logical events at different coordinates. Each row mutation converges independently. Source multi-row transactions may be visible one row at a time in the target. There is no global event ordering across partitions.

Airflow schedules reconciliation, checks exceptions, reports row counts, and runs a bounded portfolio-scale repair of active source rows. The scheduled comparison can observe cross-database skew and may report transient mismatches while ingestion is moving. Stop source writes and wait for the consumer before using a run as audit evidence. See [Airflow](AIRFLOW.md) for backfill scope.

The single broker, PostgreSQL instances, and app containers are local infrastructure. They exercise real failure boundaries with replication factor one and no high-availability guarantee. PostgreSQL init scripts apply on fresh volumes. For future schema changes to existing volumes, add ordered migrations with explicit upgrade instructions.
