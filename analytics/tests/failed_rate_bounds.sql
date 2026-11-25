select created_date, currency
from {{ ref('failed_payments') }}
where failure_rate not between 0 and 1
