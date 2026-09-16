from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lume.budgets.models import BudgetCategoryLimit, BudgetPeriod
from lume.budgets.schemas import BudgetResponse, CategoryBudgetResponse, percentage
from lume.categories.models import Category
from lume.transactions.models import Transaction


def next_month(month_start: date) -> date:
    if month_start.month == 12:
        return date(month_start.year + 1, 1, 1)
    return date(month_start.year, month_start.month + 1, 1)


def parse_month(value: str) -> date:
    try:
        parsed = date.fromisoformat(f"{value}-01")
    except ValueError as error:
        raise ValueError("month must use YYYY-MM") from error
    if len(value) != 7:
        raise ValueError("month must use YYYY-MM")
    return parsed


def expense_total(
    session: Session, user_id: str, month_start: date, category_id: str | None = None
) -> Decimal:
    statement = select(func.coalesce(func.sum(Transaction.amount), Decimal("0.0000"))).where(
        Transaction.user_id == user_id,
        Transaction.kind == "expense",
        Transaction.voided_at.is_(None),
        Transaction.effective_date >= month_start,
        Transaction.effective_date < next_month(month_start),
    )
    if category_id is not None:
        statement = statement.where(Transaction.category_id == category_id)
    return Decimal(session.scalar(statement) or 0)


def budget_response(session: Session, period: BudgetPeriod) -> BudgetResponse:
    spent = expense_total(session, period.user_id, period.month_start)
    rows = session.execute(
        select(BudgetCategoryLimit, Category.name)
        .join(Category, Category.id == BudgetCategoryLimit.category_id)
        .where(BudgetCategoryLimit.budget_period_id == period.id)
        .order_by(Category.name)
    ).all()
    category_responses: list[CategoryBudgetResponse] = []
    for category_limit, category_name in rows:
        category_spent = expense_total(
            session, period.user_id, period.month_start, category_limit.category_id
        )
        category_responses.append(
            CategoryBudgetResponse(
                category_id=category_limit.category_id,
                category_name=category_name,
                limit_amount=category_limit.limit_amount,
                spent=category_spent,
                remaining=category_limit.limit_amount - category_spent,
                percentage_used=percentage(category_spent, category_limit.limit_amount),
            )
        )
    return BudgetResponse(
        id=period.id,
        month=period.month_start.strftime("%Y-%m"),
        currency=period.currency,
        total_limit=period.total_limit,
        spent=spent,
        remaining=period.total_limit - spent,
        percentage_used=percentage(spent, period.total_limit),
        categories=category_responses,
    )
