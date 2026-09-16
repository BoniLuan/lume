from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from lume.auth.models import AuthSession
from lume.core.security import (
    hash_password,
    hash_session_token,
    new_session_token,
    verify_and_update_password,
)
from lume.core.time import utc_now
from lume.users.models import User


@dataclass(frozen=True)
class CreatedSession:
    record: AuthSession
    token: str


def normalize_email(email: str) -> str:
    return email.strip().casefold()


_DUMMY_PASSWORD_HASH = hash_password("lume-dummy-password-for-timing-equalization")


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.normalized_email == normalize_email(email)))
    candidate_hash = (
        user.password_hash
        if user is not None and user.disabled_at is None
        else _DUMMY_PASSWORD_HASH
    )
    valid, updated_hash = verify_and_update_password(password, candidate_hash)
    if user is None or user.disabled_at is not None or not valid:
        return None
    if updated_hash is not None:
        user.password_hash = updated_hash
    return user


def create_session(
    session: Session, user: User, transport: str, device_label: str | None
) -> CreatedSession:
    now = utc_now()
    token = new_session_token()
    record = AuthSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        transport=transport,
        device_label=device_label,
        created_at=now,
        last_seen_at=now,
        idle_expires_at=now + timedelta(days=7),
        absolute_expires_at=now + timedelta(days=30),
    )
    session.add(record)
    session.flush()
    return CreatedSession(record=record, token=token)
