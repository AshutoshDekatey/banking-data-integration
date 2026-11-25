import json
from dataclasses import dataclass
from uuid import UUID

from banking.models import TransactionRow


@dataclass(frozen=True)
class Change:
    row: TransactionRow
    deleted: bool


def decode(key: bytes | None, value: bytes | None) -> Change | None:
    if key is None:
        raise ValueError("CDC key missing")
    key_fields = json.loads(key)
    if not isinstance(key_fields, dict) or not isinstance(key_fields.get("transaction_id"), str):
        raise ValueError("Invalid CDC key")
    transaction_id = UUID(key_fields["transaction_id"])
    if value is None:
        return None
    event = json.loads(value)
    if not isinstance(event, dict) or event.get("op") not in ("c", "u", "r", "d"):
        raise ValueError("Unsupported CDC operation")
    source = event.get("source")
    if not isinstance(source, dict) or (source.get("schema"), source.get("table")) != (
        "bank", "transactions"
    ):
        raise ValueError("Unexpected CDC source")
    deleted = event["op"] == "d"
    row = TransactionRow.model_validate(event.get("before" if deleted else "after"))
    if row.transaction_id != transaction_id:
        raise ValueError("CDC key and row disagree")
    return Change(row, deleted)
