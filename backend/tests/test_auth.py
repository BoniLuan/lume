from fastapi.testclient import TestClient
from sqlalchemy import func, select

from lume.auth.models import AuthSession
from lume.categories.models import Category
from lume.core.database import SessionFactory
from lume.users.models import User


def test_cookie_login_and_csrf_logout(client: TestClient, user: User) -> None:
    response = client.post(
        "/api/v1/auth/sessions",
        json={"email": user.email, "password": "correct horse battery staple"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["transport"] == "cookie"
    assert body["token"] is None
    assert body["csrf_token"]
    assert "lume_session" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    with SessionFactory() as session:
        stored = session.scalar(select(AuthSession))
        assert stored is not None
        assert stored.token_hash != client.cookies.get("lume_session")

    current = client.get("/api/v1/auth/session")
    assert current.status_code == 200
    assert current.json()["user"]["email"] == user.email

    rejected = client.delete("/api/v1/auth/session")
    assert rejected.status_code == 403

    logout = client.delete(
        "/api/v1/auth/session",
        headers={"Origin": "http://127.0.0.1:15173", "X-CSRF-Token": body["csrf_token"]},
    )
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/session").status_code == 401


def test_bearer_session_never_returns_csrf(client: TestClient, user: User) -> None:
    login = client.post(
        "/api/v1/auth/sessions",
        json={
            "email": user.email,
            "password": "correct horse battery staple",
            "transport": "bearer",
        },
    )
    token = login.json()["token"]

    current = client.get("/api/v1/auth/session", headers={"Authorization": f"Bearer {token}"})

    assert current.status_code == 200
    assert current.json()["csrf_token"] is None


def test_invalid_credentials_are_generic(client: TestClient, user: User) -> None:
    del user
    response = client.post(
        "/api/v1/auth/sessions",
        json={"email": "owner@example.com", "password": "incorrect password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_fixture_seeds_user_owned_categories(user: User) -> None:
    with SessionFactory() as session:
        count = session.scalar(
            select(func.count()).select_from(Category).where(Category.user_id == user.id)
        )
    assert count == 11
