import argparse
import getpass
from collections.abc import Sequence
from pathlib import Path

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from lume.auth.models import AuthSession
from lume.auth.service import normalize_email
from lume.categories.defaults import seed_default_categories
from lume.core.database import SessionFactory
from lume.core.security import hash_password
from lume.core.time import utc_now
from lume.users.models import User

email_adapter = TypeAdapter(EmailStr)


def create_user(session: Session, email: str, display_name: str, password: str) -> User:
    try:
        validated_email = str(email_adapter.validate_python(email))
    except ValidationError as error:
        raise ValueError("email address is invalid") from error
    if len(password) < 12 or len(password) > 128:
        raise ValueError("password must contain between 12 and 128 characters")
    normalized = normalize_email(validated_email)
    if session.scalar(select(User.id).where(User.normalized_email == normalized)) is not None:
        raise ValueError("a user with this email already exists")
    user = User(
        email=validated_email,
        normalized_email=normalized,
        password_hash=hash_password(password),
        display_name=display_name.strip(),
        base_currency="BRL",
        locale="en",
        timezone="America/Sao_Paulo",
    )
    if not user.display_name:
        raise ValueError("display name cannot be empty")
    session.add(user)
    session.flush()
    seed_default_categories(session, user.id)
    return user


def reset_password(session: Session, email: str, password: str) -> User:
    if len(password) < 12 or len(password) > 128:
        raise ValueError("password must contain between 12 and 128 characters")
    user = session.scalar(select(User).where(User.normalized_email == normalize_email(email)))
    if user is None:
        raise ValueError("user not found")
    user.password_hash = hash_password(password)
    session.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    return user


def _password(path: str | None) -> str:
    if path is not None:
        return Path(path).read_text(encoding="utf-8").rstrip("\r\n")
    return getpass.getpass("Password: ")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="lume-admin")
    commands = root.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-user", help="Create an owner and default categories")
    create.add_argument("--email", required=True)
    create.add_argument("--display-name", required=True)
    create.add_argument("--password-file", help="Read the password from a private file")
    reset = commands.add_parser("reset-password", help="Set a new password and revoke sessions")
    reset.add_argument("--email", required=True)
    reset.add_argument("--password-file", help="Read the password from a private file")
    return root


def main(arguments: Sequence[str] | None = None) -> int:
    options = parser().parse_args(arguments)
    try:
        with SessionFactory.begin() as session:
            if options.command == "create-user":
                user = create_user(
                    session,
                    email=options.email,
                    display_name=options.display_name,
                    password=_password(options.password_file),
                )
                message = f"Created user {user.email} ({user.id})"
            else:
                user = reset_password(
                    session,
                    email=options.email,
                    password=_password(options.password_file),
                )
                message = f"Reset password and revoked sessions for {user.email}"
    except ValueError as error:
        parser().error(str(error))
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
