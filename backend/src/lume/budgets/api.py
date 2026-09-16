from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from lume.auth.dependencies import CsrfAuth, CurrentAuth
from lume.budgets.models import BudgetCategoryLimit, BudgetPeriod
from lume.budgets.schemas import BudgetResponse, BudgetUpsert, CategoryLimitUpsert
from lume.budgets.service import budget_response, parse_month
from lume.categories.models import Category
from lume.core.database import get_db

router = APIRouter(prefix="/api/v1/budgets", tags=["budgets"])


def _period(db: Session, user_id: str, month: str) -> BudgetPeriod:
    try:
        month_start = parse_month(month)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    period = db.scalar(
        select(BudgetPeriod).where(
            BudgetPeriod.user_id == user_id,
            BudgetPeriod.month_start == month_start,
        )
    )
    if period is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    return period


@router.get("/{month}", response_model=BudgetResponse)
def get_budget(
    month: str,
    auth: CurrentAuth,
    db: Annotated[Session, Depends(get_db)],
) -> BudgetResponse:
    return budget_response(db, _period(db, auth.user.id, month))


@router.put("/{month}", response_model=BudgetResponse)
def put_budget(
    month: str,
    payload: BudgetUpsert,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> BudgetResponse:
    try:
        month_start = parse_month(month)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    period = db.scalar(
        select(BudgetPeriod).where(
            BudgetPeriod.user_id == auth.user.id,
            BudgetPeriod.month_start == month_start,
        )
    )
    if period is None:
        period = BudgetPeriod(
            user_id=auth.user.id,
            month_start=month_start,
            total_limit=payload.total_limit,
            currency=auth.user.base_currency,
        )
        db.add(period)
    else:
        period.total_limit = payload.total_limit
    db.commit()
    db.refresh(period)
    return budget_response(db, period)


@router.put("/{month}/categories/{category_id}", response_model=BudgetResponse)
def put_category_limit(
    month: str,
    category_id: str,
    payload: CategoryLimitUpsert,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> BudgetResponse:
    period = _period(db, auth.user.id, month)
    category = db.scalar(
        select(Category).where(
            Category.id == category_id,
            Category.user_id == auth.user.id,
            Category.kind == "expense",
            Category.archived_at.is_(None),
        )
    )
    if category is None:
        raise HTTPException(status_code=404, detail="Expense category not found")
    category_limit = db.scalar(
        select(BudgetCategoryLimit).where(
            BudgetCategoryLimit.budget_period_id == period.id,
            BudgetCategoryLimit.category_id == category.id,
        )
    )
    if category_limit is None:
        category_limit = BudgetCategoryLimit(
            budget_period_id=period.id,
            user_id=auth.user.id,
            category_id=category.id,
            limit_amount=payload.limit_amount,
        )
        db.add(category_limit)
    else:
        category_limit.limit_amount = payload.limit_amount
    db.commit()
    return budget_response(db, period)


@router.delete("/{month}/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category_limit(
    month: str,
    category_id: str,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    period = _period(db, auth.user.id, month)
    category_limit = db.scalar(
        select(BudgetCategoryLimit).where(
            BudgetCategoryLimit.budget_period_id == period.id,
            BudgetCategoryLimit.category_id == category_id,
            BudgetCategoryLimit.user_id == auth.user.id,
        )
    )
    if category_limit is None:
        raise HTTPException(status_code=404, detail="Category budget not found")
    db.delete(category_limit)
    db.commit()
