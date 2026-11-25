# Local runbook

Commands after the Windows setup use Bash in Ubuntu or another WSL 2 distro. Run Compose commands from the repository root. Expected results describe a successful run.

## 1. Install Docker Desktop and enable WSL integration

In Windows PowerShell, inspect WSL and install Ubuntu if needed. Reboot if Windows requests it, then launch Ubuntu once to create your Linux user.

```powershell
wsl --update
wsl --list --verbose
wsl --install -d Ubuntu
```

If the distro appears as version 1, run `wsl --set-version Ubuntu 2` (use the distro name as shown). Install and launch [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/). In Docker Desktop select **Settings → General → Use the WSL 2 based engine**, then **Settings → Resources → WSL Integration** and enable Ubuntu. Select **Apply**. If the integration screen is missing, switch Docker Desktop to Linux containers. [Docker WSL integration guide](https://docs.docker.com/desktop/features/wsl/)

In Ubuntu, install Git and curl if required, then verify both the Docker client and engine.

```bash
sudo apt-get update
sudo apt-get install -y git curl
docker version
docker compose version
```

Expect client and server versions, plus Compose v2. If the server is unavailable, start Docker Desktop and reopen WSL.

## 2. Clone

```bash
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/AshutoshDekatey/banking-data-integration.git
cd banking-data-integration
git switch feat/banking-streaming-platform
cp .env.example .env
```

The feature branch has the implementation during PR review. Keep `.env` local. Use a new clone or a fresh seed for a new workload.

## 3. Inspect Compose

```bash
docker compose config --quiet
docker compose config --services
docker compose config --profiles
```

The first command exits silently on success. Services include both PostgreSQL instances, broker, Connect, bootstrap, API, and consumer. Optional profiles are tools, analytics, and orchestration.

## 4. Start PostgreSQL

```bash
docker compose up -d --wait source target
docker compose exec -T source psql -U bank -d source -c 'SHOW wal_level;'
docker compose exec -T target psql -U bank -d target -c '\dt ingest.*'
```

Expect logical WAL and the ingest tables. Source stores operating rows. Target stores the analytical replica, receipts, quarantine, and reconciliation.

## 5. Start Redpanda

```bash
docker compose up -d --wait broker
docker compose exec -T broker rpk cluster info -X brokers=localhost:29092
```

Expect one broker. The broker stores Kafka records and group offsets.

## 6. Start Debezium and register the connector

```bash
docker compose up -d --wait --wait-timeout 210 connect
docker compose run --rm --build bootstrap
curl -fsS http://127.0.0.1:8083/connectors/banking-source/status
```

Bootstrap creates the three-partition topic and registers the connector if absent. Expect `banking-source connector and task RUNNING`. Debezium streams committed WAL changes. On a failed task, check Connect logs and the status trace.

## 7. Start the source API

```bash
docker compose up -d --build --wait api
curl -fsS http://127.0.0.1:8000/health
```

Expect `{"status":"ok"}`. Open [Swagger UI](http://localhost:8000/docs) to try versioned inserts, updates, and deletes.

## 8. Generate the transaction workload

```bash
docker compose run --rm tools python -m banking.generate create --count 120 --seed 42
docker compose run --rm tools python -m banking.generate mutate --count 120 --seed 42
docker compose exec -T source psql -U bank -d source -c 'SELECT status, count(*) FROM bank.transactions GROUP BY status ORDER BY status;'
```

Expect 108 current rows after 12 deletes. Mutations correct amounts, settle, fail, cancel, or reverse payments. Reusing the same create seed yields duplicate ID conflicts.

## 9. Inspect broker records

```bash
docker compose exec -T broker rpk topic describe banking.bank.transactions -X brokers=localhost:29092
docker compose exec -T broker rpk topic consume banking.bank.transactions --offset start --num 3 -X brokers=localhost:29092
```

Expect three partitions and JSON records with transaction keys and Debezium envelopes. For deletes, look for operation `d` and a subsequent null value. This inspection does not change the sink group's offsets.

## 10. Start the Python consumer

```bash
docker compose up -d --wait --wait-timeout 180 consumer
docker compose run --rm tools python -m banking.verify state
```

Expect a healthy consumer and `exception_count: 0` after catch-up. It tracks source row versions and commits Kafka offsets after PostgreSQL writes.

## 11. Inspect the analytical database

```bash
docker compose exec -T target psql -U bank -d target -c 'SELECT deleted, count(*) FROM ingest.transaction_state GROUP BY deleted;'
docker compose exec -T target psql -U bank -d target -c 'SELECT outcome, count(*) FROM ingest.receipts GROUP BY outcome;'
```

The demonstration workload yields 108 active rows and 12 deletion markers. Receipt counts include Kafka tombstones.

## 12. Build and test dbt models

```bash
docker compose run --rm dbt build
docker compose run --rm tools python -m banking.verify aggregates
docker compose exec -T target psql -U bank -d target -c 'SELECT * FROM analytics.settled_payments ORDER BY currency;'
```

Expect passing dbt tests and `Source and dbt totals match`. When dbt cannot reach `target`, check the target container and use the Compose service command from this directory.

## 13. Run the Airflow reconciliation workflow

```bash
docker compose --profile orchestration up -d --build --wait --wait-timeout 300 airflow
docker compose exec -T airflow airflow dags list
docker compose exec -T airflow airflow dags unpause banking_reconciliation
docker compose exec -T airflow airflow dags trigger banking_reconciliation
docker compose exec -T airflow airflow dags list-runs -d banking_reconciliation
```

Expect the run to move from queued to running to success on a drained pipeline. Open [Airflow](http://localhost:8080) and find the generated admin password in `docker compose logs airflow` if needed. For an on-demand backfill, unpause and trigger `banking_backfill` with the same commands. Inspect exception rows before attempting a repair.

## 14. Simulate outages and restart

```bash
docker compose kill -s SIGKILL consumer
docker compose stop target
docker compose run --rm tools python -m banking.generate create --count 20 --seed 43
docker compose up -d --no-deps consumer
docker compose logs --tail=25 consumer
docker compose up -d --wait target
docker compose run --rm tools python -m banking.verify state
docker compose stop broker
docker compose run --rm tools python -m banking.generate create --count 20 --seed 44
docker compose up -d --wait broker
docker compose run --rm bootstrap
docker compose run --rm tools python -m banking.verify state
```

`--no-deps` keeps target PostgreSQL stopped during the drill. To see `write_retry`, allow time for the consumer to reach the queued records before bringing target back. Retained PostgreSQL and broker data allow the workers to recover. If Connect reports a failed task after a broker outage, inspect and restart it after confirming the cause.

## 15. Verify replay and idempotency

Run after source writes have stopped and state has converged. Use a new replay group name for repeat drills.

```bash
docker compose stop consumer
docker compose run -d --name banking-replay-check -e CDC_GROUP=banking-replay-check consumer
docker compose run --rm -e CDC_GROUP=banking-replay-check tools python -m banking.verify offsets
docker rm -f banking-replay-check
docker compose start consumer
docker compose run --rm tools python -m banking.reconcile --strict
docker compose run --rm tools python -m banking.verify aggregates
```

Expect the replay group to catch up, zero exceptions, and totals equal to source. If offsets have expired, consult [CDC recovery](CDC_KAFKA.md).

## 16. Inspect logs, metrics, and lag

```bash
docker compose logs --tail=50 api consumer connect
curl -fsS http://127.0.0.1:9100/metrics | grep '^banking_cdc_'
docker compose exec -T broker rpk group describe banking-sink-v1 -X brokers=localhost:29092
docker compose exec -T source psql -U bank -d source -c "SELECT slot_name, active, pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS retained_wal FROM pg_replication_slots;"
```

The consumer logs coordinate and outcome in JSON. Prometheus metrics cover outcomes, failures, readiness, and lag sampled when records commit. The broker group description is the on-demand checkpoint and lag check.

## 17. Run the automated integration suite

```bash
docker compose --profile orchestration down
bash scripts/integration.sh
```

Expect unit/SQL test results followed by CDC and reconciliation checks, ending with `PASS: CDC, restart, outage, broker reconnect, quarantine, dbt, replay, and backfill`. To inspect a failed stack, use `KEEP_STACK=1 bash scripts/integration.sh` and follow the printed cleanup command. See [evidence](EVIDENCE.md) for executions already performed.

## 18. Shut down and keep volumes

```bash
docker compose --profile orchestration down
```

This stops the demo and keeps database contents, connector offsets, and Kafka records for the next startup.

## 19. Destructive reset of this demo only

Confirm project and volume names first. The second command deletes this Compose project's declared volumes and permanently discards its local synthetic data and offsets.

```bash
docker volume ls --filter label=com.docker.compose.project=banking-streaming
docker compose -p banking-streaming --profile orchestration down --volumes
```

Integration stacks use their own `banking-it-<pid>` project name. When retaining an integration stack, use its printed project command. Avoid global Docker prune commands for this reset.
