from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from lume.auth.dependencies import CsrfAuth, CurrentAuth
from lume.categories.models import Category
from lume.categories.schemas import CategoryCreate, CategoryResponse, CategoryUpdate
from lume.core.database import get_db
from lume.core.time import utc_now

router = APIRouter(prefix="/api/v1/categories", tags=["categories"])


def _owned_category(db: Session, user_id: str, category_id: str) -> Category:
    category = db.scalar(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    )
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    auth: CurrentAuth,
    db: Annotated[Session, Depends(get_db)],
    kind: Annotated[Literal["income", "expense"] | None, Query()] = None,
    include_archived: Annotated[bool, Query()] = False,
) -> list[Category]:
    statement = select(Category).where(Category.user_id == auth.user.id)
    if kind is not None:
        statement = statement.where(Category.kind == kind)
    if not include_archived:
        statement = statement.where(Category.archived_at.is_(None))
    return list(db.scalars(statement.order_by(Category.kind, Category.name)).all())


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> Category:
    category = Category(user_id=auth.user.id, **payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: str,
    payload: CategoryUpdate,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> Category:
    category = _owned_category(db, auth.user.id, category_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category


@router.post("/{category_id}/archive", response_model=CategoryResponse)
def archive_category(
    category_id: str,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> Category:
    category = _owned_category(db, auth.user.id, category_id)
    category.archived_at = utc_now()
    db.commit()
    return category


@router.post("/{category_id}/restore", response_model=CategoryResponse)
def restore_category(
    category_id: str,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> Category:
    category = _owned_category(db, auth.user.id, category_id)
    category.archived_at = None
    db.commit()
    return category
