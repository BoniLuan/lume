from pydantic import BaseModel

from lume.budgets.schemas import BudgetResponse
from lume.core.money import Money
from lume.recurring.schemas import RecurringResponse
from lume.transactions.schemas import TransactionResponse


class CategorySpending(BaseModel):
    category_id: str
    category_name: str
    amount: Money


class MonthlyTrendPoint(BaseModel):
    month: str
    income: Money
    expense: Money


class DashboardResponse(BaseModel):
    month: str
    currency: str
    income: Money
    expense: Money
    net: Money
    budget: BudgetResponse | None
    categories: list[CategorySpending]
    trend: list[MonthlyTrendPoint]
    largest_expenses: list[TransactionResponse]
    recurring_due: list[RecurringResponse]


class AccountLedgerEntry(BaseModel):
    transaction_id: str
    effective_date: str
    kind: str
    description: str
    category_name: str | None
    counterparty_account_name: str | None
    direction: str
    amount: Money
    balance_change: Money
    running_balance: Money


class AccountLedgerResponse(BaseModel):
    account_id: str
    account_name: str
    account_type: str
    account_class: str
    currency: str
    start_date: str
    end_date: str
    account_opening_balance: Money
    activity_before_period: Money
    starting_balance: Money
    income: Money
    expense: Money
    transfers_in: Money
    transfers_out: Money
    period_change: Money
    closing_balance: Money
    entries: list[AccountLedgerEntry]
