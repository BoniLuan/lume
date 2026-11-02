from sqlalchemy import (
    CHAR,
    JSON,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from lume.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ImportCategoryRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_category_rules"
    __table_args__ = (
        ForeignKeyConstraint(
            ["category_id", "user_id"],
            ["categories.id", "categories.user_id"],
            name="fk_import_rules_category_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint("user_id", "kind", "merchant_key", name="uq_import_rules_owner_kind_key"),
        Index("ix_import_rules_owner_kind", "user_id", "kind"),
    )

    user_id: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    merchant_key: Mapped[str] = mapped_column(String(160), nullable=False)
    category_id: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"), nullable=False)


class ImportReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["accounts.id", "accounts.user_id"],
            name="fk_import_review_account_owner",
            ondelete="CASCADE",
        ),
        UniqueConstraint("user_id", "account_id", "fingerprint", name="uq_import_review_file"),
        Index("ix_import_reviews_owner_updated", "user_id", "updated_at"),
    )
    user_id: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"), nullable=False)
    account_id: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"), nullable=False)
    filename: Mapped[str] = mapped_column(String(150), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(
        Text().with_variant(MEDIUMTEXT(), "mysql", "mariadb"), nullable=False
    )
    decisions: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ImportRowResolution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_row_resolutions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["statement_account_id", "user_id"],
            ["accounts.id", "accounts.user_id"],
            name="fk_import_resolution_statement_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["ledger_account_id", "user_id"],
            ["accounts.id", "accounts.user_id"],
            name="fk_import_resolution_ledger_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["transaction_id", "user_id"],
            ["transactions.id", "transactions.user_id"],
            name="fk_import_resolution_transaction_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("user_id", "row_key", name="uq_import_resolution_row"),
        UniqueConstraint(
            "user_id", "transaction_id", "ledger_account_id", name="uq_import_resolution_leg"
        ),
    )
    user_id: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"), nullable=False)
    row_key: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"), nullable=False)
    statement_account_id: Mapped[str] = mapped_column(
        CHAR(36, collation="ascii_bin"), nullable=False
    )
    ledger_account_id: Mapped[str] = mapped_column(CHAR(36, collation="ascii_bin"), nullable=False)
    transaction_id: Mapped[str | None] = mapped_column(CHAR(36, collation="ascii_bin"))
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    original_description: Mapped[str] = mapped_column(
        Text().with_variant(MEDIUMTEXT(), "mysql", "mariadb"), nullable=False
    )
