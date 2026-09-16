from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from lume.auth.dependencies import CsrfAuth, CurrentAuth
from lume.core.database import get_db
from lume.core.pagination import decode_transaction_cursor, encode_transaction_cursor
from lume.core.time import utc_now
from lume.transactions.models import Transaction
from lume.transactions.schemas import (
    TransactionCreate,
    TransactionPage,
    TransactionResponse,
    TransactionUpdate,
    TransactionValues,
)
from lume.transactions.service import validate_transaction_references

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])


def _owned_transaction(db: Session, user_id: str, transaction_id: str) -> Transaction:
    transaction = db.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        )
    )
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


def _validated_values(data: dict[str, object]) -> TransactionValues:
    try:
        return TransactionValues.model_validate(data)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()) from error


@router.get("", response_model=TransactionPage)
def list_transactions(
    auth: CurrentAuth,
    db: Annotated[Session, Depends(get_db)],
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    kind: Annotated[Literal["income", "expense", "transfer"] | None, Query()] = None,
    account_id: Annotated[str | None, Query()] = None,
    category_id: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TransactionPage:
    statement = select(Transaction).where(
        Transaction.user_id == auth.user.id,
        Transaction.voided_at.is_(None),
    )
    if start_date is not None:
        statement = statement.where(Transaction.effective_date >= start_date)
    if end_date is not None:
        statement = statement.where(Transaction.effective_date <= end_date)
    if kind is not None:
        statement = statement.where(Transaction.kind == kind)
    if account_id is not None:
        statement = statement.where(
            or_(
                Transaction.account_id == account_id,
                Transaction.destination_account_id == account_id,
            )
        )
    if category_id is not None:
        statement = statement.where(Transaction.category_id == category_id)
    if search:
        statement = statement.where(Transaction.description.like(f"%{search}%"))
    if cursor:
        try:
            cursor_date, cursor_id = decode_transaction_cursor(cursor)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        statement = statement.where(
            or_(
                Transaction.effective_date < cursor_date,
                and_(
                    Transaction.effective_date == cursor_date,
                    Transaction.id < cursor_id,
                ),
            )
        )
    records = list(
        db.scalars(
            statement.order_by(Transaction.effective_date.desc(), Transaction.id.desc()).limit(
                limit + 1
            )
        ).all()
    )
    has_more = len(records) > limit
    page = records[:limit]
    next_cursor = None
    if has_more and page:
        next_cursor = encode_transaction_cursor(page[-1].effective_date, page[-1].id)
    return TransactionPage(
        items=[TransactionResponse.model_validate(item) for item in page],
        next_cursor=next_cursor,
    )


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> Transaction:
    if payload.client_request_id is not None:
        existing = db.scalar(
            select(Transaction).where(
                Transaction.user_id == auth.user.id,
                Transaction.client_request_id == str(payload.client_request_id),
            )
        )
        if existing is not None:
            return existing
    values = _validated_values(payload.model_dump(exclude={"client_request_id"}))
    try:
        validate_transaction_references(db, auth.user.id, values)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    transaction = Transaction(
        user_id=auth.user.id,
        client_request_id=(
            str(payload.client_request_id) if payload.client_request_id is not None else None
        ),
        **values.model_dump(),
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: str,
    auth: CurrentAuth,
    db: Annotated[Session, Depends(get_db)],
) -> Transaction:
    return _owned_transaction(db, auth.user.id, transaction_id)


@router.patch("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: str,
    payload: TransactionUpdate,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> Transaction:
    transaction = _owned_transaction(db, auth.user.id, transaction_id)
    data = {
        "kind": transaction.kind,
        "account_id": transaction.account_id,
        "destination_account_id": transaction.destination_account_id,
        "category_id": transaction.category_id,
        "amount": transaction.amount,
        "description": transaction.description,
        "notes": transaction.notes,
        "effective_date": transaction.effective_date,
        **payload.model_dump(exclude_unset=True),
    }
    values = _validated_values(data)
    try:
        validate_transaction_references(db, auth.user.id, values)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    for field, value in values.model_dump().items():
        setattr(transaction, field, value)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.post("/{transaction_id}/void", response_model=TransactionResponse)
def void_transaction(
    transaction_id: str,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> Transaction:
    transaction = _owned_transaction(db, auth.user.id, transaction_id)
    transaction.voided_at = utc_now()
    db.commit()
    return transaction


@router.post("/{transaction_id}/restore", response_model=TransactionResponse)
def restore_transaction(
    transaction_id: str,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> Transaction:
    transaction = _owned_transaction(db, auth.user.id, transaction_id)
    transaction.voided_at = None
    db.commit()
    return transaction
