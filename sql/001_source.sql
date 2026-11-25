BEGIN;
CREATE SCHEMA bank;
CREATE TABLE bank.transactions (
    transaction_id uuid PRIMARY KEY,
    account_id uuid NOT NULL,
    amount_minor bigint NOT NULL CHECK (amount_minor BETWEEN 1 AND 1000000000000),
    currency text NOT NULL CHECK (currency IN ('USD', 'INR', 'EUR')),
    status text NOT NULL CHECK (status IN ('pending', 'settled', 'failed', 'reversed', 'cancelled')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    version bigint NOT NULL DEFAULT 1 CHECK (version > 0)
);
-- Registry survives deletion so a transaction ID never starts a second lifecycle.
CREATE TABLE bank.transaction_ids (transaction_id uuid PRIMARY KEY);
CREATE FUNCTION bank.guard_transaction() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO bank.transaction_ids VALUES (NEW.transaction_id);
        NEW.version := 1;
    ELSE
        IF (NEW.transaction_id, NEW.account_id, NEW.currency, NEW.created_at)
            IS DISTINCT FROM (OLD.transaction_id, OLD.account_id, OLD.currency, OLD.created_at) THEN
            RAISE EXCEPTION 'Immutable transaction attributes changed' USING ERRCODE = '23514';
        END IF;
        IF NEW.status <> OLD.status AND NOT (
            (OLD.status = 'pending' AND NEW.status IN ('settled', 'failed', 'cancelled'))
            OR (OLD.status = 'settled' AND NEW.status = 'reversed')
        ) THEN
            RAISE EXCEPTION 'Invalid status transition' USING ERRCODE = '23514';
        END IF;
        NEW.version := OLD.version + 1;
        NEW.updated_at := GREATEST(OLD.updated_at, clock_timestamp());
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER guard_transaction BEFORE INSERT OR UPDATE ON bank.transactions
FOR EACH ROW EXECUTE FUNCTION bank.guard_transaction();
CREATE INDEX transactions_account_created ON bank.transactions (account_id, created_at);
ALTER TABLE bank.transactions REPLICA IDENTITY FULL;
CREATE PUBLICATION banking_cdc FOR TABLE bank.transactions;
COMMIT;
