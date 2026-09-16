import base64
import hashlib
import hmac
import secrets

from pwdlib import PasswordHash

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_and_update_password(password: str, password_hash: str) -> tuple[bool, str | None]:
    return password_hasher.verify_and_update(password, password_hash)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def derive_csrf_token(token: str, secret: bytes) -> str:
    digest = hmac.new(secret, f"csrf:{token}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def csrf_token_matches(provided: str, token: str, secret: bytes) -> bool:
    return hmac.compare_digest(provided, derive_csrf_token(token, secret))
