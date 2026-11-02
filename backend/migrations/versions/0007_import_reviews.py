"""Save statement reviews and link bank rows to ledger transactions.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import MEDIUMTEXT

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
UUID = sa.CHAR(36, collation="ascii_bin")


def upgrade() -> None:
    op.create_table(
        "import_reviews",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("account_id", UUID, nullable=False),
        sa.Column("filename", sa.String(150), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("content", MEDIUMTEXT(), nullable=False),
        sa.Column("decisions", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["accounts.id", "accounts.user_id"],
            name="fk_import_review_account_owner",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "account_id", "fingerprint", name="uq_import_review_file"),
    )
    op.create_index("ix_import_reviews_owner_updated", "import_reviews", ["user_id", "updated_at"])
    op.create_table(
        "import_row_resolutions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("row_key", UUID, nullable=False),
        sa.Column("statement_account_id", UUID, nullable=False),
        sa.Column("ledger_account_id", UUID, nullable=False),
        sa.Column("transaction_id", UUID, nullable=True),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("original_description", MEDIUMTEXT(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["statement_account_id", "user_id"],
            ["accounts.id", "accounts.user_id"],
            name="fk_import_resolution_statement_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ledger_account_id", "user_id"],
            ["accounts.id", "accounts.user_id"],
            name="fk_import_resolution_ledger_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id", "user_id"],
            ["transactions.id", "transactions.user_id"],
            name="fk_import_resolution_transaction_owner",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("user_id", "row_key", name="uq_import_resolution_row"),
        sa.UniqueConstraint(
            "user_id", "transaction_id", "ledger_account_id", name="uq_import_resolution_leg"
        ),
    )


def downgrade() -> None:
    op.drop_table("import_row_resolutions")
    op.drop_index("ix_import_reviews_owner_updated", table_name="import_reviews")
    op.drop_table("import_reviews")
