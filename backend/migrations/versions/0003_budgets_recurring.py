"""Create budgets and recurring expectations.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_TYPE = sa.CHAR(length=36, collation="ascii_bin")


def upgrade() -> None:
    op.create_unique_constraint("uq_transactions_id_user_id", "transactions", ["id", "user_id"])
    op.create_table(
        "budget_periods",
        sa.Column("user_id", UUID_TYPE, nullable=False),
        sa.Column("month_start", sa.Date(), nullable=False),
        sa.Column("total_limit", sa.Numeric(19, 4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("id", UUID_TYPE, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "DAY(month_start) = 1", name=op.f("ck_budget_periods_budget_month_first_day")
        ),
        sa.CheckConstraint("total_limit > 0", name=op.f("ck_budget_periods_budget_total_positive")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_budget_periods_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_budget_periods")),
        sa.UniqueConstraint("id", "user_id", name="uq_budget_periods_id_user_id"),
        sa.UniqueConstraint("user_id", "month_start", name="uq_budget_periods_user_month"),
    )
    op.create_table(
        "budget_category_limits",
        sa.Column("budget_period_id", UUID_TYPE, nullable=False),
        sa.Column("user_id", UUID_TYPE, nullable=False),
        sa.Column("category_id", UUID_TYPE, nullable=False),
        sa.Column("limit_amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("id", UUID_TYPE, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "limit_amount > 0",
            name=op.f("ck_budget_category_limits_budget_category_limit_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id", "user_id"],
            ["categories.id", "categories.user_id"],
            name="fk_budget_category_category_owner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["budget_period_id", "user_id"],
            ["budget_periods.id", "budget_periods.user_id"],
            name="fk_budget_category_period_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_budget_category_limits")),
        sa.UniqueConstraint(
            "budget_period_id", "category_id", name="uq_budget_category_period_category"
        ),
    )
    op.create_index(
        "ix_budget_category_user", "budget_category_limits", ["user_id", "budget_period_id"]
    )
    op.create_table(
        "recurring_templates",
        sa.Column("user_id", UUID_TYPE, nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("account_id", UUID_TYPE, nullable=False),
        sa.Column("category_id", UUID_TYPE, nullable=False),
        sa.Column("amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("description", sa.String(length=160), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("frequency", sa.String(length=16), nullable=False),
        sa.Column("interval_count", sa.Integer(), nullable=False),
        sa.Column("start_on", sa.Date(), nullable=False),
        sa.Column("next_due_on", sa.Date(), nullable=False),
        sa.Column("end_on", sa.Date(), nullable=True),
        sa.Column("anchor_month", sa.Integer(), nullable=False),
        sa.Column("anchor_day", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("id", UUID_TYPE, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "amount > 0", name=op.f("ck_recurring_templates_recurring_amount_positive")
        ),
        sa.CheckConstraint(
            "frequency IN ('weekly','monthly','yearly')",
            name=op.f("ck_recurring_templates_recurring_frequency"),
        ),
        sa.CheckConstraint(
            "interval_count BETWEEN 1 AND 99",
            name=op.f("ck_recurring_templates_recurring_interval"),
        ),
        sa.CheckConstraint(
            "kind IN ('income','expense')", name=op.f("ck_recurring_templates_recurring_kind")
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["accounts.id", "accounts.user_id"],
            name="fk_recurring_account_owner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["category_id", "user_id"],
            ["categories.id", "categories.user_id"],
            name="fk_recurring_category_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recurring_templates")),
        sa.UniqueConstraint("id", "user_id", name="uq_recurring_templates_id_user_id"),
    )
    op.create_index(
        "ix_recurring_user_due", "recurring_templates", ["user_id", "active", "next_due_on"]
    )
    op.create_table(
        "recurring_occurrences",
        sa.Column("template_id", UUID_TYPE, nullable=False),
        sa.Column("user_id", UUID_TYPE, nullable=False),
        sa.Column("scheduled_for", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("transaction_id", UUID_TYPE, nullable=True),
        sa.Column("id", UUID_TYPE, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('recorded','skipped')",
            name=op.f("ck_recurring_occurrences_recurring_occurrence_status"),
        ),
        sa.CheckConstraint(
            "(status = 'recorded' AND transaction_id IS NOT NULL) OR "
            "(status = 'skipped' AND transaction_id IS NULL)",
            name=op.f("ck_recurring_occurrences_recurring_occurrence_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["template_id", "user_id"],
            ["recurring_templates.id", "recurring_templates.user_id"],
            name="fk_recurring_occurrence_template_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id", "user_id"],
            ["transactions.id", "transactions.user_id"],
            name="fk_recurring_occurrence_transaction_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recurring_occurrences")),
        sa.UniqueConstraint("template_id", "scheduled_for", name="uq_recurring_occurrence_date"),
    )


def downgrade() -> None:
    op.drop_table("recurring_occurrences")
    op.drop_index("ix_recurring_user_due", table_name="recurring_templates")
    op.drop_table("recurring_templates")
    op.drop_index("ix_budget_category_user", table_name="budget_category_limits")
    op.drop_table("budget_category_limits")
    op.drop_table("budget_periods")
    op.drop_constraint("uq_transactions_id_user_id", "transactions", type_="unique")
