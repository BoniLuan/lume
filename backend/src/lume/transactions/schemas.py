from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lume.core.money import Money

TransactionKind = Literal["income", "expense", "transfer"]


class TransactionValues(BaseModel):
    kind: TransactionKind
    account_id: str
    destination_account_id: str | None = None
    category_id: str | None = None
    amount: Money = Field(gt=0)
    description: str = Field(min_length=1, max_length=160)
    notes: str | None = Field(default=None, max_length=2000)
    effective_date: date

    @model_validator(mode="after")
    def validate_shape(self) -> TransactionValues:
        if self.kind == "transfer":
            if self.destination_account_id is None or self.category_id is not None:
                raise ValueError("transfers require a destination and no category")
            if self.destination_account_id == self.account_id:
                raise ValueError("transfer accounts must be different")
        elif self.category_id is None or self.destination_account_id is not None:
            raise ValueError("income and expenses require a category and no destination")
        return self


class TransactionCreate(TransactionValues):
    client_request_id: UUID | None = None


class TransactionUpdate(BaseModel):
    kind: TransactionKind | None = None
    account_id: str | None = None
    destination_account_id: str | None = None
    category_id: str | None = None
    amount: Money | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, min_length=1, max_length=160)
    notes: str | None = Field(default=None, max_length=2000)
    effective_date: date | None = None


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: TransactionKind
    account_id: str
    destination_account_id: str | None
    category_id: str | None
    amount: Money
    description: str
    notes: str | None
    effective_date: date
    client_request_id: str | None
    voided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TransactionPage(BaseModel):
    items: list[TransactionResponse]
    next_cursor: str | None
