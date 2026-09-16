from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from lume.auth.models import AuthSession
from lume.core.config import Settings, get_settings
from lume.core.database import get_db
from lume.core.security import csrf_token_matches, hash_session_token
from lume.core.time import utc_now
from lume.users.models import User


@dataclass(frozen=True)
class AuthContext:
    session: AuthSession
    user: User
    raw_token: str


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_auth_context(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> AuthContext:
    cookie_token = request.cookies.get(settings.session_cookie_name)
    bearer_token: str | None = None
    if authorization is not None:
        scheme, separator, value = authorization.partition(" ")
        if separator and scheme.casefold() == "bearer" and value:
            bearer_token = value
        else:
            raise _unauthorized()
    if cookie_token is not None and bearer_token is not None:
        raise HTTPException(status_code=400, detail="Use one authentication transport")
    raw_token = bearer_token or cookie_token
    if raw_token is None:
        raise _unauthorized()

    record = db.scalar(
        select(AuthSession)
        .options(joinedload(AuthSession.user))
        .where(AuthSession.token_hash == hash_session_token(raw_token))
    )
    now = utc_now()
    if (
        record is None
        or record.revoked_at is not None
        or record.idle_expires_at <= now
        or record.absolute_expires_at <= now
        or record.user.disabled_at is not None
    ):
        raise _unauthorized()
    expected_transport = "bearer" if bearer_token is not None else "cookie"
    if record.transport != expected_transport:
        raise _unauthorized()
    if record.last_seen_at <= now - timedelta(minutes=5):
        record.last_seen_at = now
        record.idle_expires_at = min(now + timedelta(days=7), record.absolute_expires_at)
        db.commit()
    request.state.auth = record.id
    return AuthContext(session=record, user=record.user, raw_token=raw_token)


CurrentAuth = Annotated[AuthContext, Depends(get_auth_context)]


def require_csrf(
    request: Request,
    auth: CurrentAuth,
    settings: Annotated[Settings, Depends(get_settings)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> AuthContext:
    if auth.session.transport == "bearer":
        return auth
    if request.headers.get("origin") != settings.public_origin:
        raise HTTPException(status_code=403, detail="Invalid request origin")
    if csrf_token is None or not csrf_token_matches(
        csrf_token, auth.raw_token, settings.resolved_session_secret
    ):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    return auth


CsrfAuth = Annotated[AuthContext, Depends(require_csrf)]
