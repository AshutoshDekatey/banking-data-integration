select account_id, currency, count(*) as transaction_count,
       sum(amount_minor) as total_minor,
       coalesce(sum(amount_minor) filter (where status = 'settled'), 0) as settled_minor
from {{ ref('transactions') }}
group by account_id, currency
