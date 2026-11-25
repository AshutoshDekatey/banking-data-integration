from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Amount = Annotated[int, Field(strict=True, ge=1, le=10**12)]
Currency = Literal["USD", "INR", "EUR"]
Status = Literal["pending", "settled", "failed", "reversed", "cancelled"]


class CreateTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transaction_id: UUID
    account_id: UUID
    amount_minor: Amount
    currency: Currency


class UpdateTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Annotated[int, Field(strict=True, ge=1, lt=2**63)]
    amount_minor: Amount | None = None
    status: Status | None = None

    @model_validator(mode="after")
    def require_change(self) -> "UpdateTransaction":
        if self.amount_minor is None and self.status is None:
            raise ValueError("Provide amount_minor or status")
        return self


class TransactionRow(CreateTransaction):
    status: Status
    created_at: AwareDatetime
    updated_at: AwareDatetime
    version: Annotated[int, Field(strict=True, ge=1, lt=2**63)]

    @model_validator(mode="before")
    @classmethod
    def timestamp_strings(cls, data: object) -> object:
        if isinstance(data, dict):
            for field in ("created_at", "updated_at"):
                if not isinstance(data.get(field), (datetime, str)):
                    raise ValueError("Expected an ISO timestamp")
        return data

    @model_validator(mode="after")
    def validate_order(self) -> "TransactionRow":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at precedes created_at")
        return self
