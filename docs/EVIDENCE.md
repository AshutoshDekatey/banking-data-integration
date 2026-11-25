# Verification evidence

## Executed in the authoring workspace

- Python 3.12 and PostgreSQL 16.2 with the repository SQL applied to two disposable instances. All 25 Pytest cases passed, including transactional receipt rollback, duplicate and out-of-order changes, delete precedence, and poison quarantine.
- FastAPI and PostgreSQL lifecycle smoke test with 120 synthetic transactions. Duplicate and stale writes were rejected. Source-to-target comparison found 108 missing active rows, and repeatable backfill brought exceptions to zero.
- dbt Core 1.9.8 with PostgreSQL adapter 1.9.0. All six views built, all 12 data tests passed, and source SQL matched the daily, settled, failed, and account aggregates.
- Python compilation, Bash syntax, and Compose YAML parsing passed.

The Docker engine is unavailable in the authoring workspace. Check the PR for the separate Docker Compose/Redpanda integration result. The [runbook](RUNBOOK.md) gives reproduction commands.
