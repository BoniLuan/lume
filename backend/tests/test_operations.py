from fastapi.testclient import TestClient
from sqlalchemy import func, select

from lume.categories.models import Category
from lume.cli import create_user, reset_password
from lume.core.database import SessionFactory
from lume.core.security import verify_and_update_password
from lume.users.models import User


def test_operator_create_and_reset_user() -> None:
    with SessionFactory.begin() as session:
        created = create_user(
            session,
            email="New.Owner@example.com",
            display_name="New Owner",
            password="long secure first password",  # noqa: S106 - isolated test credential
        )
        user_id = created.id

    with SessionFactory() as session:
        user = session.get(User, user_id)
        assert user is not None
        assert user.normalized_email == "new.owner@example.com"
        assert user.timezone == "America/Sao_Paulo"
        assert (
            session.scalar(
                select(func.count()).select_from(Category).where(Category.user_id == user.id)
            )
            == 11
        )

    with SessionFactory.begin() as session:
        reset = reset_password(session, "NEW.OWNER@example.com", "different secure password")
        new_hash = reset.password_hash
    valid, _ = verify_and_update_password("different secure password", new_hash)
    assert valid


def test_login_is_throttled_after_repeated_failures(client: TestClient, user: User) -> None:
    for _ in range(5):
        response = client.post(
            "/api/v1/auth/sessions",
            json={"email": user.email, "password": "definitely incorrect"},
        )
        assert response.status_code == 401

    blocked = client.post(
        "/api/v1/auth/sessions",
        json={"email": user.email, "password": "correct horse battery staple"},
    )
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


def test_request_id_and_private_metrics(client: TestClient) -> None:
    health = client.get("/healthz", headers={"X-Request-ID": "test-request-42"})
    assert health.headers["X-Request-ID"] == "test-request-42"

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "lume_http_requests_total" in metrics.text
    assert 'route="/healthz"' in metrics.text


def test_csv_export_is_scoped_and_spreadsheet_safe(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    account = client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "name": "Checking",
            "account_type": "checking",
            "account_class": "asset",
            "opening_balance": "0.0000",
            "opened_on": "2026-09-01",
        },
    ).json()
    with SessionFactory() as session:
        category_id = session.scalar(
            select(Category.id).where(Category.user_id == user.id, Category.kind == "expense")
        )
        assert category_id is not None
    created = client.post(
        "/api/v1/transactions",
        headers=auth_headers,
        json={
            "kind": "expense",
            "account_id": account["id"],
            "category_id": category_id,
            "amount": "19.9000",
            "description": '=HYPERLINK("bad")',
            "effective_date": "2026-09-16",
        },
    )
    assert created.status_code == 201

    exported = client.get(
        "/api/v1/reports/transactions.csv?start_date=2026-09-01&end_date=2026-09-30"
    )
    assert exported.status_code == 200
    assert exported.headers["content-disposition"].startswith("attachment;")
    assert "'=HYPERLINK" in exported.text
    assert "19.9000" in exported.text
