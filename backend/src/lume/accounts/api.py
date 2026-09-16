from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from lume.accounts.models import Account
from lume.accounts.schemas import AccountCreate, AccountResponse, AccountUpdate
from lume.accounts.service import account_balance
from lume.auth.dependencies import CsrfAuth, CurrentAuth
from lume.core.database import get_db
from lume.core.time import utc_now

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


def _owned_account(db: Session, user_id: str, account_id: str) -> Account:
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user_id))
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


def _response(db: Session, account: Account) -> AccountResponse:
    return AccountResponse.model_validate(
        {**account.__dict__, "current_balance": account_balance(db, account)}
    )


@router.get("", response_model=list[AccountResponse])
def list_accounts(
    auth: CurrentAuth,
    db: Annotated[Session, Depends(get_db)],
    include_archived: Annotated[bool, Query()] = False,
) -> list[AccountResponse]:
    statement = select(Account).where(Account.user_id == auth.user.id)
    if not include_archived:
        statement = statement.where(Account.archived_at.is_(None))
    accounts = db.scalars(statement.order_by(Account.created_at, Account.id)).all()
    return [_response(db, account) for account in accounts]


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    payload: AccountCreate,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> AccountResponse:
    account = Account(
        user_id=auth.user.id,
        currency=auth.user.base_currency,
        **payload.model_dump(),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return _response(db, account)


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: str,
    auth: CurrentAuth,
    db: Annotated[Session, Depends(get_db)],
) -> AccountResponse:
    return _response(db, _owned_account(db, auth.user.id, account_id))


@router.patch("/{account_id}", response_model=AccountResponse)
def update_account(
    account_id: str,
    payload: AccountUpdate,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> AccountResponse:
    account = _owned_account(db, auth.user.id, account_id)
    values = {**account.__dict__, **payload.model_dump(exclude_unset=True)}
    if values["account_type"] == "credit_card" and values["account_class"] != "liability":
        raise HTTPException(status_code=422, detail="Credit cards must be liability accounts")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return _response(db, account)


@router.post("/{account_id}/archive", response_model=AccountResponse)
def archive_account(
    account_id: str,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> AccountResponse:
    account = _owned_account(db, auth.user.id, account_id)
    account.archived_at = utc_now()
    db.commit()
    return _response(db, account)


@router.post("/{account_id}/restore", response_model=AccountResponse)
def restore_account(
    account_id: str,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> AccountResponse:
    account = _owned_account(db, auth.user.id, account_id)
    account.archived_at = None
    db.commit()
    return _response(db, account)
