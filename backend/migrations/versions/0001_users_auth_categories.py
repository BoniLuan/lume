"""Create users, authentication sessions, and categories.

Revision ID: 0001
Revises:
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("normalized_email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("disabled_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.CHAR(length=36, collation="ascii_bin"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("normalized_email", name=op.f("uq_users_normalized_email")),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("user_id", sa.CHAR(length=36, collation="ascii_bin"), nullable=False),
        sa.Column("token_hash", sa.BINARY(length=32), nullable=False),
        sa.Column("transport", sa.String(length=16), nullable=False),
        sa.Column("device_label", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.CHAR(length=36, collation="ascii_bin"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_auth_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_auth_sessions_token_hash")),
    )
    op.create_index(
        "ix_auth_sessions_user_active", "auth_sessions", ["user_id", "revoked_at"], unique=False
    )
    op.create_table(
        "categories",
        sa.Column("user_id", sa.CHAR(length=36, collation="ascii_bin"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("icon", sa.String(length=40), nullable=True),
        sa.Column("color", sa.String(length=16), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.CHAR(length=36, collation="ascii_bin"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_categories_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("id", "user_id", name="uq_categories_id_user_id"),
    )
    op.create_index("ix_categories_user_kind", "categories", ["user_id", "kind"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_categories_user_kind", table_name="categories")
    op.drop_table("categories")
    op.drop_index("ix_auth_sessions_user_active", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("users")
