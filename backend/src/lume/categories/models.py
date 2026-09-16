from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lume.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from lume.users.models import User


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_categories_id_user_id"),
        Index("ix_categories_user_kind", "user_id", "kind"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(40))
    color: Mapped[str | None] = mapped_column(String(16))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    user: Mapped[User] = relationship(back_populates="categories")
