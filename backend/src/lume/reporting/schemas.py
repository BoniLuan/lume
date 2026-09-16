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
