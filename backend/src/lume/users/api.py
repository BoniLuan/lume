from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from lume.auth.dependencies import CsrfAuth, CurrentAuth
from lume.auth.models import AuthSession
from lume.core.config import Settings, get_settings
from lume.core.database import get_db
from lume.core.security import hash_password, verify_and_update_password
from lume.core.time import utc_now
from lume.users.schemas import PasswordChange, UserResponse, UserUpdate

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


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChange,
    response: Response,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    valid, _ = verify_and_update_password(payload.current_password, auth.user.password_hash)
    if not valid:
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    auth.user.password_hash = hash_password(payload.new_password)
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == auth.user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    db.commit()
    if auth.session.transport == "cookie":
        response.delete_cookie(settings.session_cookie_name, path="/")
