import csv
from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lume.accounts.models import Account
from lume.auth.dependencies import CurrentAuth
from lume.budgets.models import BudgetPeriod
from lume.budgets.service import budget_response, next_month, parse_month
from lume.categories.models import Category
from lume.core.database import get_db
from lume.recurring.models import RecurringTemplate
from lume.recurring.schemas import RecurringResponse
from lume.reporting.schemas import CategorySpending, DashboardResponse, MonthlyTrendPoint
from lume.transactions.models import Transaction
from lume.transactions.schemas import TransactionResponse

router = APIRouter(prefix="/api/v1", tags=["reporting"])


def _spreadsheet_safe(value: str | None) -> str:
    if value is None:
        return ""
    return f"'{value}" if value.startswith(("=", "+", "-", "@")) else value


def _kind_total(db: Session, user_id: str, kind: str, start: date, end: date) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), Decimal("0.0000"))).where(
            Transaction.user_id == user_id,
            Transaction.kind == kind,
            Transaction.voided_at.is_(None),
            Transaction.effective_date >= start,
            Transaction.effective_date < end,
        )
    )
    return Decimal(value or 0)


def _shift_month(month_start: date, delta: int) -> date:
    index = month_start.year * 12 + month_start.month - 1 + delta
    year, month_zero = divmod(index, 12)
    return date(year, month_zero + 1, 1)


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    auth: CurrentAuth,
    db: Annotated[Session, Depends(get_db)],
    month: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
) -> DashboardResponse:
    try:
        month_start = parse_month(month)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    month_end = next_month(month_start)
    income = _kind_total(db, auth.user.id, "income", month_start, month_end)
    expense = _kind_total(db, auth.user.id, "expense", month_start, month_end)
    budget = db.scalar(
        select(BudgetPeriod).where(
            BudgetPeriod.user_id == auth.user.id,
            BudgetPeriod.month_start == month_start,
        )
    )
    category_rows = db.execute(
        select(
            Category.id,
            Category.name,
            func.sum(Transaction.amount).label("amount"),
        )
        .join(Transaction, Transaction.category_id == Category.id)
        .where(
            Transaction.user_id == auth.user.id,
            Transaction.kind == "expense",
            Transaction.voided_at.is_(None),
            Transaction.effective_date >= month_start,
            Transaction.effective_date < month_end,
        )
        .group_by(Category.id, Category.name)
        .order_by(func.sum(Transaction.amount).desc(), Category.id)
        .limit(10)
    ).all()
    largest = db.scalars(
        select(Transaction)
        .where(
            Transaction.user_id == auth.user.id,
            Transaction.kind == "expense",
            Transaction.voided_at.is_(None),
            Transaction.effective_date >= month_start,
            Transaction.effective_date < month_end,
        )
        .order_by(Transaction.amount.desc(), Transaction.effective_date.desc())
        .limit(5)
    ).all()
    trend: list[MonthlyTrendPoint] = []
    for delta in range(-5, 1):
        trend_start = _shift_month(month_start, delta)
        trend_end = next_month(trend_start)
        trend.append(
            MonthlyTrendPoint(
                month=trend_start.strftime("%Y-%m"),
                income=_kind_total(db, auth.user.id, "income", trend_start, trend_end),
                expense=_kind_total(db, auth.user.id, "expense", trend_start, trend_end),
            )
        )
    today = datetime.now(ZoneInfo(auth.user.timezone)).date()
    recurring = db.scalars(
        select(RecurringTemplate)
        .where(
            RecurringTemplate.user_id == auth.user.id,
            RecurringTemplate.active.is_(True),
            RecurringTemplate.archived_at.is_(None),
            RecurringTemplate.next_due_on <= today,
        )
        .order_by(RecurringTemplate.next_due_on, RecurringTemplate.id)
        .limit(10)
    ).all()
    return DashboardResponse(
        month=month,
        currency=auth.user.base_currency,
        income=income,
        expense=expense,
        net=income - expense,
        budget=budget_response(db, budget) if budget is not None else None,
        categories=[
            CategorySpending(
                category_id=category_id,
                category_name=category_name,
                amount=Decimal(amount),
            )
            for category_id, category_name, amount in category_rows
        ],
        trend=trend,
        largest_expenses=[TransactionResponse.model_validate(item) for item in largest],
        recurring_due=[RecurringResponse.model_validate(item) for item in recurring],
    )


@router.get("/reports/transactions.csv", response_class=Response)
def export_transactions(
    auth: CurrentAuth,
    db: Annotated[Session, Depends(get_db)],
    start_date: Annotated[date, Query()],
    end_date: Annotated[date, Query()],
) -> Response:
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="End date cannot precede start date")
    if (end_date - start_date).days > 366:
        raise HTTPException(status_code=422, detail="Export range cannot exceed 366 days")
    records = db.scalars(
        select(Transaction)
        .where(
            Transaction.user_id == auth.user.id,
            Transaction.voided_at.is_(None),
            Transaction.effective_date >= start_date,
            Transaction.effective_date <= end_date,
        )
        .order_by(Transaction.effective_date, Transaction.id)
    ).all()
    account_ids = {
        account_id
        for record in records
        for account_id in (record.account_id, record.destination_account_id)
        if account_id is not None
    }
    category_ids = {record.category_id for record in records if record.category_id is not None}
    account_names: dict[str, str] = {}
    if account_ids:
        account_names = {
            account_id: name
            for account_id, name in db.execute(
                select(Account.id, Account.name).where(Account.id.in_(account_ids))
            ).tuples()
        }
    category_names: dict[str, str] = {}
    if category_ids:
        category_names = {
            category_id: name
            for category_id, name in db.execute(
                select(Category.id, Category.name).where(Category.id.in_(category_ids))
            ).tuples()
        }
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        ("date", "type", "description", "amount", "account", "destination", "category", "notes")
    )
    for record in records:
        writer.writerow(
            (
                record.effective_date.isoformat(),
                record.kind,
                _spreadsheet_safe(record.description),
                str(record.amount),
                _spreadsheet_safe(account_names.get(record.account_id, "")),
                _spreadsheet_safe(
                    account_names.get(record.destination_account_id, "")
                    if record.destination_account_id is not None
                    else ""
                ),
                _spreadsheet_safe(
                    category_names.get(record.category_id, "")
                    if record.category_id is not None
                    else ""
                ),
                _spreadsheet_safe(record.notes),
            )
        )
    filename = f"lume-transactions-{start_date.isoformat()}-{end_date.isoformat()}.csv"
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
