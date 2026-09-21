"""Add persistent category suggestions for reviewed imports.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_TYPE = sa.CHAR(length=36, collation="ascii_bin")


def upgrade() -> None:
    op.create_table(
        "import_category_rules",
        sa.Column("user_id", UUID_TYPE, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("merchant_key", sa.String(160), nullable=False),
        sa.Column("category_id", UUID_TYPE, nullable=False),
        sa.Column("id", UUID_TYPE, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id", "user_id"],
            ["categories.id", "categories.user_id"],
            name="fk_import_rules_category_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_category_rules")),
        sa.UniqueConstraint(
            "user_id", "kind", "merchant_key", name="uq_import_rules_owner_kind_key"
        ),
    )
    op.create_index("ix_import_rules_owner_kind", "import_category_rules", ["user_id", "kind"])


def downgrade() -> None:
    op.drop_index("ix_import_rules_owner_kind", table_name="import_category_rules")
    op.drop_table("import_category_rules")
