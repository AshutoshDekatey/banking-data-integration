# CDC and Kafka

The connector uses PostgreSQL `pgoutput`, publication `banking_cdc`, logical slot `banking_cdc` and snapshot mode `initial`. A first startup captures then-existing rows as `r` events and continues with WAL changes. Resume relies on Connect offsets and the existing slot. The connector forwards only `bank.transactions`. PostgreSQL `REPLICA IDENTITY FULL` provides the old row on a delete.

| Envelope operation | Fields consumed | Target behavior |
| --- | --- | --- |
| `r`, `c`, `u` | `after` and row version | Insert or advance the active row |
| `d` | `before` and row version | Persist the deletion marker |
| Null value | Transaction key | Record tombstone receipt |
| Invalid input | Raw broker data | Save quarantine plus receipt |

The key is JSON with `transaction_id`. Kafka Connect partitions identical serialized keys together. The topic keeps three partitions, one replica, and seven days of delete-based retention. Retain a stable topic/partition layout and keep topic storage and target receipts on the same lifecycle. Never recreate a topic under the same name and reuse its old receipts. The receipt identity includes topic name, partition, and offset. Connect keeps separate internal configuration, status, and source-offset topics.

The consumer uses group `banking-sink-v1` and synchronous explicit commits. A crash after SQL commit and before Kafka commit can redeliver a record. A failed SQL write leaves the offset outstanding; transient failures get four attempts with bounded backoff, then the service exits so it can restart. Poison schema failures are quarantined transactionally. This gives at-least-once delivery within retained history and idempotent effects for a single source-ID lifecycle. Cross-system exactly-once would require a different protocol.

A new group starts at offset zero only where complete history remains. Expired checkpoints fail closed. For ordinary validation, use a separate group as documented in the runbook. If history expired, reconcile against source and plan a coordinated rebootstrap into a fresh target rather than skipping ahead blindly. Backfill covers active rows, so unavailable delete history can require a fresh snapshot and target rebuild.
