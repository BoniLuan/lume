from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from lume.auth.dependencies import CsrfAuth, CurrentAuth
from lume.core.database import get_db
from lume.users.schemas import UserResponse, UserUpdate

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
def get_me(auth: CurrentAuth) -> UserResponse:
    return UserResponse.model_validate(auth.user)


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UserUpdate,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(auth.user, field, value)
    db.commit()
    db.refresh(auth.user)
    return UserResponse.model_validate(auth.user)
