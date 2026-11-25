select transaction_id, source_row, target_row
from {{ source('ingest', 'reconciliation_exceptions') }}
