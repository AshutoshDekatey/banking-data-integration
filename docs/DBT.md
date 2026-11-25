# dbt

Run `docker compose run --rm dbt build` after starting target PostgreSQL. This builds PostgreSQL views in `analytics` and executes generic and business-constraint tests. Views serve the current state as the consumer commits new data.

| Model | Grain |
| --- | --- |
| `transactions` | One active payment |
| `daily_totals` | UTC creation day and currency |
| `settled_payments` | UTC creation day and currency with settled payments |
| `failed_payments` | UTC creation day and currency |
| `account_totals` | Account and currency |
| `reconciliation_exceptions` | One mismatched transaction from the latest run |

Settled counts remove reversals and deletes. Failed payment rate divides failed active payments by all active payments in the group. Reporting uses creation dates and UTC. It does not represent historical end-of-day balances or settlement-date cash flow. Use `python -m banking.verify aggregates` via the tools container to compare independent source SQL with dbt outputs.
