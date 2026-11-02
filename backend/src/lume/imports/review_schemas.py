from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lume.core.money import Money
from lume.imports.schemas import StatementRow


class ReviewDecision(BaseModel):
    row_key: str
    action: Literal["pending", "skip", "create", "link"] = "pending"
    kind: Literal["income", "expense", "transfer"] | None = None
    category_id: str | None = None
    counterparty_account_id: str | None = None
    remember_category: bool = False
    allow_possible_match: bool = False
    account_id: str | None = None
    transaction_id: str | None = None
    description: str | None = Field(default=None, max_length=160)


class ReviewUpdate(BaseModel):
    version: int = Field(ge=1)
    decisions: list[ReviewDecision] = Field(max_length=500)


class MatchCandidate(BaseModel):
    transaction_id: str
    description: str
    effective_date: date
    amount: Money
    kind: Literal["income", "expense", "transfer"]
    account_id: str
    account_name: str
    destination_account_id: str | None
    destination_account_name: str | None
    category_name: str | None
    ledger_account_id: str
    reasons: list[str]
    already_linked: bool


class ReviewRow(StatementRow):
    candidates: list[MatchCandidate]
    suggested_kind: Literal["income", "expense", "transfer"]
    suggested_counterparty_account_id: str | None
    resolved_action: Literal["create", "link", "skip"] | None
    resolved_transaction_id: str | None
    resolution_warning: str | None
    invalid_transaction_id: str | None = None


class StatementMetadata(BaseModel):
    institution: str | None = None
    account_type: str | None = None
    currency: str | None = None
    account_last_four: str | None = None
    start_date: date
    end_date: date
    closing_balance: Money | None = None
    balance_date: date | None = None
    inferred_opening_balance: Money | None = None


class ReviewBalance(BaseModel):
    account_id: str
    account_name: str
    balance_date: date
    current_balance: Money
    projected_balance: Money
    statement_closing_balance: Money | None = None
    difference: Money | None = None


class ReviewSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    account_id: str
    updated_at: datetime
    version: int


class ReviewResponse(ReviewSummary):
    rows: list[ReviewRow]
    decisions: list[ReviewDecision]
    metadata: StatementMetadata
    balances: list[ReviewBalance]
    opening_lume_balance: Money
    opening_difference: Money | None
    unmatched_transactions: list[MatchCandidate]


class ReviewApplyResponse(BaseModel):
    created: int
    linked: int
    ignored: int
    pending: int
    review: ReviewResponse
