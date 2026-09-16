from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from lume.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RecurringTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recurring_templates"
    __table_args__ = (
        CheckConstraint("kind IN ('income','expense')", name="recurring_kind"),
        CheckConstraint("frequency IN ('weekly','monthly','yearly')", name="recurring_frequency"),
        CheckConstraint("amount > 0", name="recurring_amount_positive"),
        CheckConstraint("interval_count BETWEEN 1 AND 99", name="recurring_interval"),
        ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["accounts.id", "accounts.user_id"],
            name="fk_recurring_account_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["category_id", "user_id"],
            ["categories.id", "categories.user_id"],
            name="fk_recurring_category_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "user_id", name="uq_recurring_templates_id_user_id"),
        Index("ix_recurring_user_due", "user_id", "active", "next_due_on"),
    )

    user_id: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"))
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    account_id: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"))
    category_id: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"))
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    description: Mapped[str] = mapped_column(String(160), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    frequency: Mapped[str] = mapped_column(String(16), nullable=False)
    interval_count: Mapped[int] = mapped_column(Integer, nullable=False)
    start_on: Mapped[date] = mapped_column(Date, nullable=False)
    next_due_on: Mapped[date] = mapped_column(Date, nullable=False)
    end_on: Mapped[date | None] = mapped_column(Date)
    anchor_month: Mapped[int] = mapped_column(Integer, nullable=False)
    anchor_day: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(nullable=False, default=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class RecurringOccurrence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recurring_occurrences"
    __table_args__ = (
        CheckConstraint("status IN ('recorded','skipped')", name="recurring_occurrence_status"),
        CheckConstraint(
            "(status = 'recorded' AND transaction_id IS NOT NULL) OR "
            "(status = 'skipped' AND transaction_id IS NULL)",
            name="recurring_occurrence_shape",
        ),
        ForeignKeyConstraint(
            ["template_id", "user_id"],
            ["recurring_templates.id", "recurring_templates.user_id"],
            name="fk_recurring_occurrence_template_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["transaction_id", "user_id"],
            ["transactions.id", "transactions.user_id"],
            name="fk_recurring_occurrence_transaction_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("template_id", "scheduled_for", name="uq_recurring_occurrence_date"),
    )

    template_id: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"))
    user_id: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"))
    scheduled_for: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    transaction_id: Mapped[str | None] = mapped_column(CHAR(36, collation="ascii_bin"))
