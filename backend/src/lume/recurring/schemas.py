from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lume.core.money import Money


class RecurringCreate(BaseModel):
    kind: Literal["income", "expense"]
    account_id: str
    category_id: str
    amount: Money = Field(gt=0)
    description: str = Field(min_length=1, max_length=160)
    notes: str | None = Field(default=None, max_length=2000)
    frequency: Literal["weekly", "monthly", "yearly"]
    interval_count: int = Field(default=1, ge=1, le=99)
    start_on: date
    end_on: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> RecurringCreate:
        if self.end_on is not None and self.end_on < self.start_on:
            raise ValueError("end date cannot precede start date")
        return self


class RecurringUpdate(BaseModel):
    amount: Money | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, min_length=1, max_length=160)
    notes: str | None = Field(default=None, max_length=2000)
    end_on: date | None = None
    active: bool | None = None


class RecurringResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: Literal["income", "expense"]
    account_id: str
    category_id: str
    amount: Money
    description: str
    notes: str | None
    frequency: Literal["weekly", "monthly", "yearly"]
    interval_count: int
    start_on: date
    next_due_on: date
    end_on: date | None
    active: bool
    archived_at: datetime | None


class OccurrenceAction(BaseModel):
    scheduled_for: date


class OccurrenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    template_id: str
    scheduled_for: date
    status: Literal["recorded", "skipped"]
    transaction_id: str | None
