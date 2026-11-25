select transaction_id
from {{ ref('transactions') }}
where amount_minor not between 1 and 1000000000000
   or version < 1
   or updated_at < created_at
