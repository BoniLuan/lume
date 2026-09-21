from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from lume.core.money import Money


class StatementPreviewRequest(BaseModel):
    account_id: str
    filename: str = Field(max_length=150)
    content: str = Field(max_length=1_000_000)


class StatementRow(BaseModel):
    row_key: str
    effective_date: date
    description: str
    kind: Literal["income", "expense"]
    amount: Money
    source_id: str | None
    matched_transaction_id: str | None
    suggested_category_id: str | None


class StatementPreviewResponse(BaseModel):
    rows: list[StatementRow]
    format: Literal["csv", "ofx"]
    account_id: str


class StatementDecision(BaseModel):
    row_key: str
    action: Literal["skip", "create"]
    kind: Literal["income", "expense", "transfer"] | None = None
    category_id: str | None = None
    counterparty_account_id: str | None = None
    remember_category: bool = False
    allow_possible_match: bool = False


class StatementCommitRequest(StatementPreviewRequest):
    decisions: list[StatementDecision] = Field(max_length=500)


class StatementCommitResponse(BaseModel):
    created: int
    skipped: int
    matched: int
