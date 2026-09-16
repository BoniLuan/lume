"""Create accounts and transactions.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_TYPE = sa.CHAR(length=36, collation="ascii_bin")


def upgrade() -> None:
    op.create_check_constraint(
        "ck_categories_category_kind", "categories", "kind IN ('income','expense')"
    )
    op.create_table(
        "accounts",
        sa.Column("user_id", UUID_TYPE, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("account_type", sa.String(length=20), nullable=False),
        sa.Column("account_class", sa.String(length=16), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("opening_balance", sa.Numeric(19, 4), nullable=False),
        sa.Column("opened_on", sa.Date(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("id", UUID_TYPE, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "account_type IN ('checking','cash','savings','credit_card','other')",
            name=op.f("ck_accounts_account_type"),
        ),
        sa.CheckConstraint(
            "account_class IN ('asset','liability')", name=op.f("ck_accounts_account_class")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_accounts_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
        sa.UniqueConstraint("id", "user_id", name="uq_accounts_id_user_id"),
    )
    op.create_index("ix_accounts_user_archived", "accounts", ["user_id", "archived_at"])
    op.create_table(
        "transactions",
        sa.Column("user_id", UUID_TYPE, nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("account_id", UUID_TYPE, nullable=False),
        sa.Column("destination_account_id", UUID_TYPE, nullable=True),
        sa.Column("category_id", UUID_TYPE, nullable=True),
        sa.Column("amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("description", sa.String(length=160), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("client_request_id", UUID_TYPE, nullable=True),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.Column("id", UUID_TYPE, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount > 0", name=op.f("ck_transactions_transaction_amount_positive")),
        sa.CheckConstraint(
            "kind IN ('income','expense','transfer')",
            name=op.f("ck_transactions_transaction_kind"),
        ),
        sa.CheckConstraint(
            "(kind IN ('income','expense') AND category_id IS NOT NULL "
            "AND destination_account_id IS NULL) OR "
            "(kind = 'transfer' AND category_id IS NULL "
            "AND destination_account_id IS NOT NULL "
            "AND destination_account_id <> account_id)",
            name=op.f("ck_transactions_transaction_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id", "user_id"],
            ["categories.id", "categories.user_id"],
            name="fk_transactions_category_owner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["destination_account_id", "user_id"],
            ["accounts.id", "accounts.user_id"],
            name="fk_transactions_destination_account_owner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["accounts.id", "accounts.user_id"],
            name="fk_transactions_source_account_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
        sa.UniqueConstraint("user_id", "client_request_id", name="uq_transactions_user_request"),
    )
    op.create_index(
        "ix_transactions_user_account_date",
        "transactions",
        ["user_id", "account_id", "effective_date"],
    )
    op.create_index(
        "ix_transactions_user_category_date",
        "transactions",
        ["user_id", "category_id", "effective_date"],
    )
    op.create_index(
        "ix_transactions_user_date_id",
        "transactions",
        ["user_id", "effective_date", "id"],
    )
    op.create_index(
        "ix_transactions_user_destination_date",
        "transactions",
        ["user_id", "destination_account_id", "effective_date"],
    )
    op.create_index(
        "ix_transactions_user_kind_date",
        "transactions",
        ["user_id", "kind", "effective_date"],
    )


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_index("ix_accounts_user_archived", table_name="accounts")
    op.drop_table("accounts")
    op.drop_constraint("ck_categories_category_kind", "categories", type_="check")
