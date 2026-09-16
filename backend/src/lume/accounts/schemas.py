from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lume.core.money import Money

AccountType = Literal["checking", "cash", "savings", "credit_card", "other"]
AccountClass = Literal["asset", "liability"]


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    account_type: AccountType
    account_class: AccountClass
    opening_balance: Money = Decimal("0.0000")
    opened_on: date

    @model_validator(mode="after")
    def validate_credit_card_class(self) -> AccountCreate:
        if self.account_type == "credit_card" and self.account_class != "liability":
            raise ValueError("credit cards must be liability accounts")
        return self


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    account_type: AccountType | None = None
    account_class: AccountClass | None = None
    opening_balance: Money | None = None
    opened_on: date | None = None


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    account_type: AccountType
    account_class: AccountClass
    currency: str
    opening_balance: Money
    current_balance: Money
    opened_on: date
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
