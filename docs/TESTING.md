# Testing

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
bash -n scripts/integration.sh
```

Unit coverage includes CDC operations, input validation, deterministic generation, write-before-commit behavior, and transient retry. The optional PostgreSQL fixture regression uses a rolled-back transaction with truncation and a temporary constraint. Run it only against a disposable test database with `BANKING_TEST_SQL=1`.

Run `bash scripts/integration.sh` with Docker to start a separate project. Stop the main demo first to free ports. The script uses real PostgreSQL, Redpanda and Debezium, generates and mutates 120 payments, kills the consumer, interrupts both target PostgreSQL and the broker in separate drills, adds a poison record, rebuilds dbt views, reconsumes the retained topic with another group, and repairs an intentionally removed active row. It asserts source equality, committed broker offsets, quarantine, and currency-level financial aggregate equality. It removes its own volumes on exit unless `KEEP_STACK=1`. GitHub Actions runs this path and the standalone unit job.

The PostgreSQL fixture covers an update before insert, same-coordinate replay, logical duplicate at a new coordinate, delete precedence, tombstones, invalid input and transaction rollback on write rejection. For manual live verification see steps 14–17 in the runbook.
