from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from lume.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BudgetPeriod(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "budget_periods"
    __table_args__ = (
        CheckConstraint("DAY(month_start) = 1", name="budget_month_first_day"),
        CheckConstraint("total_limit > 0", name="budget_total_positive"),
        UniqueConstraint("user_id", "month_start", name="uq_budget_periods_user_month"),
        UniqueConstraint("id", "user_id", name="uq_budget_periods_id_user_id"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    month_start: Mapped[date] = mapped_column(Date, nullable=False)
    total_limit: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)


class BudgetCategoryLimit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "budget_category_limits"
    __table_args__ = (
        CheckConstraint("limit_amount > 0", name="budget_category_limit_positive"),
        ForeignKeyConstraint(
            ["budget_period_id", "user_id"],
            ["budget_periods.id", "budget_periods.user_id"],
            name="fk_budget_category_period_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["category_id", "user_id"],
            ["categories.id", "categories.user_id"],
            name="fk_budget_category_category_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "budget_period_id", "category_id", name="uq_budget_category_period_category"
        ),
        Index("ix_budget_category_user", "user_id", "budget_period_id"),
    )

    budget_period_id: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"))
    user_id: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"))
    category_id: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"))
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
