"""Add benefit account type.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_accounts_account_type"), "accounts", type_="check")
    op.create_check_constraint(
        op.f("ck_accounts_account_type"),
        "accounts",
        "account_type IN "
        "('checking','cash','savings','benefit','credit_card','receivable','other')",
    )


def downgrade() -> None:
    op.execute("UPDATE accounts SET account_type = 'other' WHERE account_type = 'benefit'")
    op.drop_constraint(op.f("ck_accounts_account_type"), "accounts", type_="check")
    op.create_check_constraint(
        op.f("ck_accounts_account_type"),
        "accounts",
        "account_type IN ('checking','cash','savings','credit_card','receivable','other')",
    )
