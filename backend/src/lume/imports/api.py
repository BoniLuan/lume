from datetime import timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from lume.accounts.models import Account
from lume.auth.dependencies import CsrfAuth
from lume.categories.models import Category
from lume.core.database import get_db
from lume.imports.models import ImportCategoryRule
from lume.imports.parser import merchant_key, parse_statement
from lume.imports.schemas import (
    StatementCommitRequest,
    StatementCommitResponse,
    StatementPreviewRequest,
    StatementPreviewResponse,
    StatementRow,
)
from lume.transactions.models import Transaction
from lume.transactions.schemas import TransactionValues
from lume.transactions.service import validate_transaction_references

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])


def _account(db: Session, user_id: str, account_id: str) -> Account:
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user_id))
    if account is None or account.archived_at is not None:
        raise HTTPException(status_code=422, detail="Choose an active account")
    return account


def _rows(payload: StatementPreviewRequest) -> tuple[str, list[StatementRow]]:
    try:
        return parse_statement(payload.account_id, payload.filename, payload.content)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _match(db: Session, user_id: str, account_id: str, row: StatementRow) -> str | None:
    window_start = row.effective_date - timedelta(days=2)
    window_end = row.effective_date + timedelta(days=2)
    candidates = db.scalars(
        select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.voided_at.is_(None),
            Transaction.amount == row.amount,
            Transaction.effective_date >= window_start,
            Transaction.effective_date <= window_end,
            or_(
                Transaction.account_id == account_id,
                Transaction.destination_account_id == account_id,
            ),
        )
    ).all()
    for candidate in candidates:
        effect = (
            candidate.amount
            if (candidate.kind == "income" or candidate.destination_account_id == account_id)
            else -candidate.amount
        )
        if (effect > 0) == (row.kind == "income") and merchant_key(
            candidate.description
        ) == merchant_key(row.description):
            return candidate.id
    return None


@router.post("/preview", response_model=StatementPreviewResponse)
def preview_statement(
    payload: StatementPreviewRequest,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> StatementPreviewResponse:
    _account(db, auth.user.id, payload.account_id)
    format_name, rows = _rows(payload)
    rules = {
        (rule.kind, rule.merchant_key): rule.category_id
        for rule in db.scalars(
            select(ImportCategoryRule).where(ImportCategoryRule.user_id == auth.user.id)
        ).all()
    }
    active_categories = {
        category.id
        for category in db.scalars(
            select(Category).where(Category.user_id == auth.user.id, Category.archived_at.is_(None))
        ).all()
    }
    for row in rows:
        row.matched_transaction_id = _match(db, auth.user.id, payload.account_id, row)
        suggestion = rules.get((row.kind, merchant_key(row.description)))
        row.suggested_category_id = suggestion if suggestion in active_categories else None
    return StatementPreviewResponse(rows=rows, format=format_name, account_id=payload.account_id)


@router.post("/commit", response_model=StatementCommitResponse, status_code=status.HTTP_201_CREATED)
def commit_statement(
    payload: StatementCommitRequest,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> StatementCommitResponse:
    _account(db, auth.user.id, payload.account_id)
    _, rows = _rows(payload)
    by_key = {row.row_key: row for row in rows}
    if len(payload.decisions) != len(rows) or {
        decision.row_key for decision in payload.decisions
    } != set(by_key):
        raise HTTPException(status_code=422, detail="Review every statement row exactly once")
    created = skipped = matched = 0
    for decision in payload.decisions:
        row = by_key[decision.row_key]
        existing = db.scalar(
            select(Transaction.id).where(
                Transaction.user_id == auth.user.id,
                Transaction.client_request_id == row.row_key,
            )
        )
        probable_match = _match(db, auth.user.id, payload.account_id, row)
        if decision.action == "skip":
            skipped += 1
            continue
        should_skip_match = probable_match is not None and not decision.allow_possible_match
        if existing is not None or should_skip_match:
            matched += 1
            continue
        kind = decision.kind or row.kind
        if kind == "transfer" and decision.counterparty_account_id is None:
            raise HTTPException(status_code=422, detail="Transfers require another account")
        if kind == "transfer" and decision.counterparty_account_id == payload.account_id:
            raise HTTPException(status_code=422, detail="Transfer accounts must differ")
        source_account_id = (
            decision.counterparty_account_id
            if kind == "transfer" and row.kind == "income"
            else payload.account_id
        )
        destination_account_id = (
            (payload.account_id if row.kind == "income" else decision.counterparty_account_id)
            if kind == "transfer"
            else None
        )
        try:
            values = TransactionValues(
                kind=kind,
                account_id=source_account_id,
                destination_account_id=destination_account_id,
                category_id=decision.category_id if kind != "transfer" else None,
                amount=Decimal(row.amount),
                description=row.description,
                effective_date=row.effective_date,
            )
        except ValidationError as error:
            raise HTTPException(
                status_code=422, detail="Invalid category, account, or transaction values"
            ) from error
        if kind != "transfer" and kind != row.kind:
            raise HTTPException(
                status_code=422, detail="Reclassify bank direction using a transfer or skip"
            )
        try:
            validate_transaction_references(db, auth.user.id, values)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        db.add(
            Transaction(
                user_id=auth.user.id,
                client_request_id=row.row_key,
                **values.model_dump(),
            )
        )
        created += 1
        if decision.remember_category and kind != "transfer" and decision.category_id is not None:
            key = merchant_key(row.description)
            rule = db.scalar(
                select(ImportCategoryRule).where(
                    ImportCategoryRule.user_id == auth.user.id,
                    ImportCategoryRule.kind == kind,
                    ImportCategoryRule.merchant_key == key,
                )
            )
            if rule is None:
                db.add(
                    ImportCategoryRule(
                        user_id=auth.user.id,
                        kind=kind,
                        merchant_key=key,
                        category_id=decision.category_id,
                    )
                )
            else:
                rule.category_id = decision.category_id
    db.commit()
    return StatementCommitResponse(created=created, skipped=skipped, matched=matched)
