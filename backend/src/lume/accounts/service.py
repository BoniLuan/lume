from decimal import Decimal

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from lume.accounts.models import Account
from lume.transactions.models import Transaction


def account_balance(session: Session, account: Account) -> Decimal:
    effect = case(
        (
            Transaction.account_id == account.id,
            case(
                (Transaction.kind == "income", Transaction.amount),
                (Transaction.kind.in_(("expense", "transfer")), -Transaction.amount),
                else_=Decimal("0.0000"),
            ),
        ),
        (
            (Transaction.destination_account_id == account.id) & (Transaction.kind == "transfer"),
            Transaction.amount,
        ),
        else_=Decimal("0.0000"),
    )
    movement = session.scalar(
        select(func.coalesce(func.sum(effect), Decimal("0.0000"))).where(
            Transaction.user_id == account.user_id,
            Transaction.voided_at.is_(None),
            or_(
                Transaction.account_id == account.id,
                Transaction.destination_account_id == account.id,
            ),
        )
    )
    return account.opening_balance + Decimal(movement or 0)
