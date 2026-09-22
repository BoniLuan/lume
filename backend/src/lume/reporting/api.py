import csv
from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from lume.accounts.models import Account
from lume.auth.dependencies import CsrfAuth, CurrentAuth
from lume.budgets.models import BudgetPeriod
from lume.budgets.service import budget_response, next_month, parse_month
from lume.categories.models import Category
from lume.core.database import get_db
from lume.recurring.models import RecurringTemplate
from lume.recurring.schemas import RecurringResponse
from lume.reporting.schemas import (
    AccountLedgerEntry,
    AccountLedgerResponse,
    AccountReconciliationRequest,
    AccountReconciliationResponse,
    CategorySpending,
    DashboardResponse,
    MonthlyTrendPoint,
    SpendingAccountRow,
    SpendingCategoryRow,
    SpendingInsightsResponse,
)
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


def _account_effect(record: Transaction, account_id: str) -> Decimal:
    if record.destination_account_id == account_id:
        return record.amount
    if record.account_id == account_id:
        return record.amount if record.kind == "income" else -record.amount
    return Decimal("0.0000")


@router.get("/reports/account-ledger", response_model=AccountLedgerResponse)
def account_ledger(
    auth: CurrentAuth,
    db: Annotated[Session, Depends(get_db)],
    account_id: Annotated[str, Query()],
    start_date: Annotated[date, Query()],
    end_date: Annotated[date, Query()],
) -> AccountLedgerResponse:
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="End date cannot precede start date")
    if (end_date - start_date).days > 366:
        raise HTTPException(status_code=422, detail="Report range cannot exceed 366 days")
    account = db.scalar(
        select(Account).where(Account.id == account_id, Account.user_id == auth.user.id)
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    account_filter = or_(
        Transaction.account_id == account.id,
        Transaction.destination_account_id == account.id,
    )
    prior_records = db.scalars(
        select(Transaction).where(
            Transaction.user_id == auth.user.id,
            Transaction.voided_at.is_(None),
            Transaction.effective_date < start_date,
            account_filter,
        )
    ).all()
    records = db.scalars(
        select(Transaction)
        .where(
            Transaction.user_id == auth.user.id,
            Transaction.voided_at.is_(None),
            Transaction.effective_date >= start_date,
            Transaction.effective_date <= end_date,
            account_filter,
        )
        .order_by(Transaction.effective_date, Transaction.created_at, Transaction.id)
    ).all()

    activity_before = sum(
        (_account_effect(record, account.id) for record in prior_records),
        Decimal("0.0000"),
    )
    running = account.opening_balance + activity_before
    income = Decimal("0.0000")
    expense = Decimal("0.0000")
    transfers_in = Decimal("0.0000")
    transfers_out = Decimal("0.0000")

    related_account_ids = {
        related_id
        for record in records
        for related_id in (record.account_id, record.destination_account_id)
        if related_id is not None and related_id != account.id
    }
    account_names = (
        {
            related_id: name
            for related_id, name in db.execute(
                select(Account.id, Account.name).where(
                    Account.user_id == auth.user.id,
                    Account.id.in_(related_account_ids),
                )
            ).tuples()
        }
        if related_account_ids
        else {}
    )
    category_ids = {record.category_id for record in records if record.category_id is not None}
    category_names = (
        {
            category_id: name
            for category_id, name in db.execute(
                select(Category.id, Category.name).where(
                    Category.user_id == auth.user.id,
                    Category.id.in_(category_ids),
                )
            ).tuples()
        }
        if category_ids
        else {}
    )

    entries: list[AccountLedgerEntry] = []
    for record in records:
        change = _account_effect(record, account.id)
        running += change
        incoming = change > 0
        if record.kind == "income":
            income += record.amount
        elif record.kind == "expense":
            expense += record.amount
        elif incoming:
            transfers_in += record.amount
        else:
            transfers_out += record.amount
        other_account_id = (
            record.account_id
            if record.destination_account_id == account.id
            else record.destination_account_id
        )
        entries.append(
            AccountLedgerEntry(
                transaction_id=record.id,
                effective_date=record.effective_date.isoformat(),
                kind=record.kind,
                description=record.description,
                category_name=(
                    category_names.get(record.category_id)
                    if record.category_id is not None
                    else None
                ),
                counterparty_account_name=(
                    account_names.get(other_account_id) if other_account_id is not None else None
                ),
                direction="in" if incoming else "out",
                amount=record.amount,
                balance_change=change,
                running_balance=running,
            )
        )

    period_change = income + transfers_in - expense - transfers_out
    return AccountLedgerResponse(
        account_id=account.id,
        account_name=account.name,
        account_type=account.account_type,
        account_class=account.account_class,
        currency=account.currency,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        account_opening_balance=account.opening_balance,
        activity_before_period=activity_before,
        starting_balance=account.opening_balance + activity_before,
        income=income,
        expense=expense,
        transfers_in=transfers_in,
        transfers_out=transfers_out,
        period_change=period_change,
        closing_balance=running,
        entries=entries,
    )


@router.post("/reports/account-reconciliation", response_model=AccountReconciliationResponse)
def account_reconciliation(
    payload: AccountReconciliationRequest,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> AccountReconciliationResponse:
    account = db.scalar(
        select(Account).where(Account.id == payload.account_id, Account.user_id == auth.user.id)
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if payload.as_of_date < account.opened_on:
        raise HTTPException(status_code=422, detail="Date cannot precede account opening")
    if payload.as_of_date > datetime.now(ZoneInfo(auth.user.timezone)).date():
        raise HTTPException(status_code=422, detail="Date cannot be in the future")
    is_source = Transaction.account_id == account.id
    is_destination = Transaction.destination_account_id == account.id
    amount = Transaction.amount
    zero = Decimal("0.0000")
    totals = db.execute(
        select(
            func.coalesce(
                func.sum(case((is_source & (Transaction.kind == "income"), amount), else_=zero)),
                zero,
            ),
            func.coalesce(
                func.sum(case((is_source & (Transaction.kind == "expense"), amount), else_=zero)),
                zero,
            ),
            func.coalesce(
                func.sum(
                    case((is_destination & (Transaction.kind == "transfer"), amount), else_=zero)
                ),
                zero,
            ),
            func.coalesce(
                func.sum(case((is_source & (Transaction.kind == "transfer"), amount), else_=zero)),
                zero,
            ),
            func.count(Transaction.id),
        ).where(
            Transaction.user_id == auth.user.id,
            Transaction.voided_at.is_(None),
            Transaction.effective_date <= payload.as_of_date,
            or_(is_source, is_destination),
        )
    ).one()
    income, expense, transfers_in, transfers_out = (Decimal(value) for value in totals[:4])
    calculated = account.opening_balance + income + transfers_in - expense - transfers_out
    return AccountReconciliationResponse(
        account_id=account.id,
        account_name=account.name,
        account_class=account.account_class,
        currency=account.currency,
        as_of_date=payload.as_of_date.isoformat(),
        opening_balance=account.opening_balance,
        income=income,
        expense=expense,
        transfers_in=transfers_in,
        transfers_out=transfers_out,
        calculated_balance=calculated,
        actual_balance=payload.actual_balance,
        difference=payload.actual_balance - calculated,
        movement_count=int(totals[4]),
    )


@router.get("/reports/spending-insights", response_model=SpendingInsightsResponse)
def spending_insights(
    auth: CurrentAuth,
    db: Annotated[Session, Depends(get_db)],
    month: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
) -> SpendingInsightsResponse:
    try:
        month_start = parse_month(month)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    previous_start = _shift_month(month_start, -1)
    month_end = next_month(month_start)
    amount = Transaction.amount
    current_amount = func.sum(case((Transaction.effective_date >= month_start, amount), else_=0))
    previous_amount = func.sum(case((Transaction.effective_date < month_start, amount), else_=0))
    common = (
        Transaction.user_id == auth.user.id,
        Transaction.kind == "expense",
        Transaction.voided_at.is_(None),
        Transaction.effective_date >= previous_start,
        Transaction.effective_date < month_end,
    )
    category_rows = db.execute(
        select(Category.id, Category.name, current_amount, previous_amount)
        .join(Transaction, Transaction.category_id == Category.id)
        .where(*common)
        .group_by(Category.id, Category.name)
        .order_by(current_amount.desc(), previous_amount.desc(), Category.name)
    ).all()
    account_rows = db.execute(
        select(Account.id, Account.name, func.sum(amount), func.count(Transaction.id))
        .join(Transaction, Transaction.account_id == Account.id)
        .where(
            Transaction.user_id == auth.user.id,
            Transaction.kind == "expense",
            Transaction.voided_at.is_(None),
            Transaction.effective_date >= month_start,
            Transaction.effective_date < month_end,
        )
        .group_by(Account.id, Account.name)
        .order_by(func.sum(amount).desc(), Account.name)
    ).all()
    categories = [
        SpendingCategoryRow(
            category_id=category_id,
            category_name=name,
            amount=Decimal(current),
            previous_amount=Decimal(previous),
            change=Decimal(current) - Decimal(previous),
        )
        for category_id, name, current, previous in category_rows
    ]
    expense = sum((row.amount for row in categories), Decimal("0.0000"))
    previous_expense = sum((row.previous_amount for row in categories), Decimal("0.0000"))
    return SpendingInsightsResponse(
        month=month,
        currency=auth.user.base_currency,
        expense=expense,
        previous_expense=previous_expense,
        change=expense - previous_expense,
        accounts=[
            SpendingAccountRow(
                account_id=account_id, account_name=name, amount=Decimal(total), count=int(count)
            )
            for account_id, name, total, count in account_rows
        ],
        categories=categories,
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
