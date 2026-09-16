from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from lume.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("kind IN ('income','expense','transfer')", name="transaction_kind"),
        CheckConstraint("amount > 0", name="transaction_amount_positive"),
        CheckConstraint(
            "(kind IN ('income','expense') AND category_id IS NOT NULL "
            "AND destination_account_id IS NULL) OR "
            "(kind = 'transfer' AND category_id IS NULL "
            "AND destination_account_id IS NOT NULL "
            "AND destination_account_id <> account_id)",
            name="transaction_shape",
        ),
        ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["accounts.id", "accounts.user_id"],
            name="fk_transactions_source_account_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["destination_account_id", "user_id"],
            ["accounts.id", "accounts.user_id"],
            name="fk_transactions_destination_account_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["category_id", "user_id"],
            ["categories.id", "categories.user_id"],
            name="fk_transactions_category_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("user_id", "client_request_id", name="uq_transactions_user_request"),
        UniqueConstraint("id", "user_id", name="uq_transactions_id_user_id"),
        Index("ix_transactions_user_date_id", "user_id", "effective_date", "id"),
        Index("ix_transactions_user_kind_date", "user_id", "kind", "effective_date"),
        Index("ix_transactions_user_account_date", "user_id", "account_id", "effective_date"),
        Index("ix_transactions_user_category_date", "user_id", "category_id", "effective_date"),
        Index(
            "ix_transactions_user_destination_date",
            "user_id",
            "destination_account_id",
            "effective_date",
        ),
    )

    user_id: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    account_id: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"), nullable=False)
    destination_account_id: Mapped[str | None] = mapped_column(CHAR(36, collation="ascii_bin"))
    category_id: Mapped[str | None] = mapped_column(CHAR(36, collation="ascii_bin"))
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    description: Mapped[str] = mapped_column(String(160), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    client_request_id: Mapped[str | None] = mapped_column(CHAR(36, collation="ascii_bin"))
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
