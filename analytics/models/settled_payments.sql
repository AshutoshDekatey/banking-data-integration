select created_date, currency, count(*) as settled_count,
       sum(amount_minor) as settled_minor
from {{ ref('transactions') }}
where status = 'settled'
group by created_date, currency
