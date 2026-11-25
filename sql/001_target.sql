BEGIN;
CREATE SCHEMA ingest;
CREATE TABLE ingest.transaction_state (
    transaction_id uuid PRIMARY KEY,
    account_id uuid NOT NULL,
    amount_minor bigint NOT NULL CHECK (amount_minor BETWEEN 1 AND 1000000000000),
    currency text NOT NULL CHECK (currency IN ('USD', 'INR', 'EUR')),
    status text NOT NULL CHECK (status IN ('pending', 'settled', 'failed', 'reversed', 'cancelled')),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL CHECK (updated_at >= created_at),
    version bigint NOT NULL CHECK (version > 0),
    deleted boolean NOT NULL
);
CREATE TABLE ingest.receipts (
    topic text NOT NULL,
    partition_id integer NOT NULL,
    offset_id bigint NOT NULL,
    outcome text NOT NULL CHECK (outcome IN ('accepted', 'quarantined', 'tombstone')),
    PRIMARY KEY (topic, partition_id, offset_id)
);
CREATE TABLE ingest.quarantine (
    topic text NOT NULL,
    partition_id integer NOT NULL,
    offset_id bigint NOT NULL,
    raw_key bytea,
    raw_value bytea,
    reason text NOT NULL,
    received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (topic, partition_id, offset_id),
    FOREIGN KEY (topic, partition_id, offset_id) REFERENCES ingest.receipts
);
CREATE TABLE ingest.reconciliation_exceptions (
    transaction_id uuid PRIMARY KEY,
    source_row jsonb,
    target_row jsonb
);
CREATE TABLE ingest.reconciliation_runs (
    run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    checked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    source_count bigint NOT NULL,
    target_count bigint NOT NULL,
    exception_count bigint NOT NULL
);
COMMIT;
