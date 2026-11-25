select created_date, currency, count(*) as transaction_count,
       sum(amount_minor) as total_minor
from {{ ref('transactions') }}
group by created_date, currency
