#!/usr/bin/env bash
set -euo pipefail
[[ -f .env ]] || cp .env.example .env
project="banking-it-$$"
dc() { docker compose -p "$project" "$@"; }
cleanup() {
    if [[ "${KEEP_STACK:-0}" == 1 ]]; then
        echo "Stack retained. Remove it with docker compose -p $project down --volumes"
    else
        dc down --volumes --remove-orphans
    fi
}
trap cleanup EXIT
trap 'dc logs --tail=60 api consumer broker connect >&2' ERR

# PostgreSQL-only regressions run before CDC so no fixture data can leak into the demo.
dc up -d --wait source target
dc run --rm -e BANKING_TEST_SQL=1 tools python -m pytest -q
dc up --build -d --wait --wait-timeout 240 api broker connect
# Rows inserted before connector registration exercise the initial snapshot.
dc run --rm tools python -m banking.generate create --count 20 --seed 40
dc run --rm bootstrap
dc up -d --wait consumer
dc run --rm tools python -m banking.verify state
dc run --rm tools python -m banking.generate create --count 120
dc run --rm tools python -m banking.verify state

# Crash the consumer and mutate the source while the analytical database is down.
dc kill -s SIGKILL consumer
dc stop target
dc run --rm tools python -m banking.generate mutate --count 120
# Bypass the startup dependency so Compose leaves target offline.
dc up -d --no-deps consumer
for attempt in {1..30}; do
    if dc logs consumer 2>&1 | grep 'write_retry' >/dev/null; then
        break
    fi
    if [[ "$attempt" == 30 ]]; then
        echo "Consumer did not observe the target outage" >&2
        exit 1
    fi
    sleep 2
done
dc up -d --wait target
dc run --rm tools python -m banking.verify state

# The broker disconnects without deleting its storage.
dc stop broker
dc run --rm tools python -m banking.generate create --count 20 --seed 43
dc up -d --wait broker
dc run --rm bootstrap
dc run --rm tools python -m banking.verify state

# Invalid CDC record must be durably quarantined before acknowledgement.
printf 'invalid-json\n' | dc exec -T broker rpk topic produce banking.bank.transactions \
    -k '{"transaction_id":"00000000-0000-0000-0000-000000000001"}' -X brokers=localhost:29092
dc run --rm tools python -m banking.verify offsets
dc run --rm tools python -m banking.verify poison
dc run --rm dbt build
dc run --rm tools python -m banking.verify aggregates

# Reprocess all retained records using a separate group, then compare again.
dc stop consumer
dc run -d --name "$project-replay" -e CDC_GROUP="$project-replay" consumer
dc run --rm -e CDC_GROUP="$project-replay" tools python -m banking.verify offsets
docker rm -f "$project-replay"
dc start consumer
dc run --rm tools python -m banking.verify state
dc run --rm tools python -m banking.verify aggregates

# Delete a replica row and repair it without changing CDC offsets.
dc exec -T target psql -U bank -d target -v ON_ERROR_STOP=1 -c \
    "DELETE FROM ingest.transaction_state WHERE transaction_id = (SELECT min(transaction_id::text)::uuid FROM ingest.transaction_state WHERE NOT deleted)"
if dc run --rm tools python -m banking.reconcile --strict; then
    echo "Missing target row was not detected" >&2
    exit 1
fi
dc run --rm tools python -m banking.reconcile --backfill --strict
dc run --rm tools python -m banking.verify aggregates
echo "PASS: CDC, restart, outage, broker reconnect, quarantine, dbt, replay, and backfill"
