select created_date, currency,
       count(*) filter (where status = 'failed') as failed_count,
       count(*) as transaction_count,
       (count(*) filter (where status = 'failed'))::numeric / count(*) as failure_rate
from {{ ref('transactions') }}
group by created_date, currency
