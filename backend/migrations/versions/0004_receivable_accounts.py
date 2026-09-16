"""Add receivable account type.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_accounts_account_type"), "accounts", type_="check")
    op.create_check_constraint(
        op.f("ck_accounts_account_type"),
        "accounts",
        "account_type IN ('checking','cash','savings','credit_card','receivable','other')",
    )


def downgrade() -> None:
    op.execute("UPDATE accounts SET account_type = 'other' WHERE account_type = 'receivable'")
    op.drop_constraint(op.f("ck_accounts_account_type"), "accounts", type_="check")
    op.create_check_constraint(
        op.f("ck_accounts_account_type"),
        "accounts",
        "account_type IN ('checking','cash','savings','credit_card','other')",
    )
