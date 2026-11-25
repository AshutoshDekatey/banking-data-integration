import json

import pytest
from fastapi.testclient import TestClient

from banking.api import app
from banking.events import decode
from banking.generate import rows

FIXTURE = rows(1, 42)[0] | {
    "status": "pending",
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:00:00Z",
    "version": 1,
}
KEY = json.dumps({"transaction_id": FIXTURE["transaction_id"]}).encode()


def envelope(operation: str, row: dict) -> bytes:
    return json.dumps({
        "source": {"schema": "bank", "table": "transactions"},
        "op": operation,
        "before" if operation == "d" else "after": row,
    }).encode()


@pytest.mark.parametrize("operation", ["c", "u", "r", "d"])
def test_decodes_debezium_operation(operation: str) -> None:
    change = decode(KEY, envelope(operation, FIXTURE))
    assert change is not None and change.deleted == (operation == "d")
    assert change.row.version == 1


@pytest.mark.parametrize("change", [
    {"amount_minor": 12.5}, {"amount_minor": True}, {"amount_minor": -1},
    {"currency": "JPY"}, {"status": "unknown"}, {"version": "2"},
    {"updated_at": "2024-01-01T00:00:00Z"}, {"created_at": 100},
    {"transaction_id": "00000000-0000-0000-0000-000000000000"},
])
def test_rejects_invalid_rows(change: dict) -> None:
    with pytest.raises(ValueError):
        decode(KEY, envelope("u", FIXTURE | change))


def test_tombstone_and_malformed_payload() -> None:
    assert decode(KEY, None) is None
    with pytest.raises(ValueError):
        decode(KEY, b"not-json")
    with pytest.raises(ValueError):
        decode(b"[]", None)


def test_generator_repeatability() -> None:
    assert rows(120, 42) == rows(120, 42)
    assert len({row["transaction_id"] for row in rows(120, 42)}) == 120
    assert rows(1, 42) != rows(1, 43)


def test_api_validates_before_database_access() -> None:
    client = TestClient(app)
    row = rows(1, 42)[0]
    assert client.post("/transactions", json=row | {"amount_minor": "10"}).status_code == 422
    assert client.patch(f"/transactions/{row['transaction_id']}",
                        json={"expected_version": 1}).status_code == 422
