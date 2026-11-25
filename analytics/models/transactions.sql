select
    transaction_id, account_id, amount_minor, currency, status, version,
    (created_at at time zone 'UTC')::date as created_date,
    created_at, updated_at
from {{ source('ingest', 'transaction_state') }}
where not deleted
