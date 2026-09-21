from sqlalchemy import CHAR, ForeignKeyConstraint, Index, String, UniqueConstraint
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
