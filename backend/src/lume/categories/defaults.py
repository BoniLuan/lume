from dataclasses import dataclass

from sqlalchemy.orm import Session

from lume.categories.models import Category


@dataclass(frozen=True)
class DefaultCategory:
    name: str
    kind: str
    icon: str


DEFAULT_CATEGORIES = (
    DefaultCategory("Salary", "income", "wallet-cards"),
    DefaultCategory("Other income", "income", "circle-plus"),
    DefaultCategory("Housing", "expense", "house"),
    DefaultCategory("Food", "expense", "utensils"),
    DefaultCategory("Transport", "expense", "bus"),
    DefaultCategory("Health", "expense", "heart-pulse"),
    DefaultCategory("Education", "expense", "graduation-cap"),
    DefaultCategory("Leisure", "expense", "ticket"),
    DefaultCategory("Shopping", "expense", "shopping-bag"),
    DefaultCategory("Bills", "expense", "receipt-text"),
    DefaultCategory("Other expense", "expense", "circle-minus"),
)


def seed_default_categories(session: Session, user_id: str) -> None:
    session.add_all(
        Category(user_id=user_id, name=item.name, kind=item.kind, icon=item.icon)
        for item in DEFAULT_CATEGORIES
    )
