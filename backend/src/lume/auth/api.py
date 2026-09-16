from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from lume.auth.dependencies import CsrfAuth, CurrentAuth
from lume.auth.models import AuthSession
from lume.auth.rate_limit import login_rate_limiter
from lume.auth.schemas import SessionCreate, SessionListItem, SessionResponse
from lume.auth.service import authenticate_user, create_session
from lume.core.config import Settings, get_settings
from lume.core.database import get_db
from lume.core.security import derive_csrf_token
from lume.core.time import utc_now
from lume.users.schemas import UserResponse

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def login(
    payload: SessionCreate,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionResponse:
    client_ip = request.client.host if request.client is not None else "unknown"
    rate_key = login_rate_limiter.key(str(payload.email), client_ip)
    retry_after = login_rate_limiter.retry_after(rate_key)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )
    user = authenticate_user(db, str(payload.email), payload.password)
    if user is None:
        login_rate_limiter.record_failure(rate_key)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    login_rate_limiter.clear(rate_key)
    created = create_session(db, user, payload.transport, payload.device_label)
    db.commit()
    csrf_token: str | None = None
    bearer_token: str | None = None
    if payload.transport == "cookie":
        csrf_token = derive_csrf_token(created.token, settings.resolved_session_secret)
        response.set_cookie(
            key=settings.session_cookie_name,
            value=created.token,
            max_age=30 * 24 * 60 * 60,
            secure=settings.secure_cookies,
            httponly=True,
            samesite="lax",
            path="/",
        )
    else:
        bearer_token = created.token
    return SessionResponse(
        session_id=created.record.id,
        user=UserResponse.model_validate(user),
        transport=payload.transport,
        expires_at=created.record.absolute_expires_at,
        csrf_token=csrf_token,
        token=bearer_token,
    )


@router.get("/session", response_model=SessionResponse)
def current_session(
    auth: CurrentAuth,
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionResponse:
    csrf_token = None
    if auth.session.transport == "cookie":
        csrf_token = derive_csrf_token(auth.raw_token, settings.resolved_session_secret)
    return SessionResponse(
        session_id=auth.session.id,
        user=UserResponse.model_validate(auth.user),
        transport=auth.session.transport,
        expires_at=auth.session.absolute_expires_at,
        csrf_token=csrf_token,
    )


@router.get("/sessions", response_model=list[SessionListItem])
def list_sessions(
    auth: CurrentAuth, db: Annotated[Session, Depends(get_db)]
) -> list[SessionListItem]:
    now = utc_now()
    records = db.scalars(
        select(AuthSession)
        .where(
            AuthSession.user_id == auth.user.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.absolute_expires_at > now,
        )
        .order_by(AuthSession.created_at.desc())
    ).all()
    return [
        SessionListItem(
            id=record.id,
            transport=record.transport,
            device_label=record.device_label,
            created_at=record.created_at,
            last_seen_at=record.last_seen_at,
            absolute_expires_at=record.absolute_expires_at,
            current=record.id == auth.session.id,
        )
        for record in records
    ]


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    auth.session.revoked_at = utc_now()
    db.commit()
    if auth.session.transport == "cookie":
        response.delete_cookie(settings.session_cookie_name, path="/")


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: str,
    request: Request,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    del request
    record = db.scalar(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id == auth.user.id,
            AuthSession.revoked_at.is_(None),
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")
    record.revoked_at = utc_now()
    db.commit()
