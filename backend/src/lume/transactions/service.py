from sqlalchemy import select
from sqlalchemy.orm import Session

from lume.accounts.models import Account
from lume.categories.models import Category
from lume.transactions.schemas import TransactionValues


def validate_transaction_references(
    session: Session, user_id: str, values: TransactionValues
) -> None:
    account = session.scalar(
        select(Account).where(Account.id == values.account_id, Account.user_id == user_id)
    )
    if account is None or account.archived_at is not None:
        raise ValueError("source account is unavailable")

    if values.kind == "transfer":
        destination = session.scalar(
            select(Account).where(
                Account.id == values.destination_account_id,
                Account.user_id == user_id,
            )
        )
        if destination is None or destination.archived_at is not None:
            raise ValueError("destination account is unavailable")
        if account.currency != destination.currency:
            raise ValueError("transfer accounts must use the same currency")
        return

    category = session.scalar(
        select(Category).where(Category.id == values.category_id, Category.user_id == user_id)
    )
    if category is None or category.archived_at is not None:
        raise ValueError("category is unavailable")
    if category.kind != values.kind:
        raise ValueError("category kind does not match transaction kind")
