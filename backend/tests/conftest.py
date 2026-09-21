from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from lume.accounts.models import Account
from lume.auth.models import AuthSession
from lume.auth.rate_limit import login_rate_limiter
from lume.budgets.models import BudgetCategoryLimit, BudgetPeriod
from lume.categories.defaults import seed_default_categories
from lume.categories.models import Category
from lume.core.database import SessionFactory
from lume.core.security import hash_password
from lume.imports.models import ImportCategoryRule
from lume.main import app
from lume.recurring.models import RecurringOccurrence, RecurringTemplate
from lume.transactions.models import Transaction
from lume.users.models import User


@pytest.fixture(autouse=True)
def clean_database() -> Generator[None]:
    login_rate_limiter.reset()
    with SessionFactory.begin() as session:
        session.execute(delete(RecurringOccurrence))
        session.execute(delete(RecurringTemplate))
        session.execute(delete(BudgetCategoryLimit))
        session.execute(delete(BudgetPeriod))
        session.execute(delete(Transaction))
        session.execute(delete(Account))
        session.execute(delete(AuthSession))
        session.execute(delete(ImportCategoryRule))
        session.execute(delete(Category))
        session.execute(delete(User))
    yield
    with SessionFactory.begin() as session:
        session.execute(delete(RecurringOccurrence))
        session.execute(delete(RecurringTemplate))
        session.execute(delete(BudgetCategoryLimit))
        session.execute(delete(BudgetPeriod))
        session.execute(delete(Transaction))
        session.execute(delete(Account))
        session.execute(delete(AuthSession))
        session.execute(delete(ImportCategoryRule))
        session.execute(delete(Category))
        session.execute(delete(User))


@pytest.fixture
def user() -> User:
    with SessionFactory.begin() as session:
        record = User(
            email="owner@example.com",
            normalized_email="owner@example.com",
            password_hash=hash_password("correct horse battery staple"),
            display_name="Lume Owner",
            base_currency="BRL",
            locale="en",
            timezone="America/Sao_Paulo",
        )
        session.add(record)
        session.flush()
        seed_default_categories(session, record.id)
        session.expunge(record)
    return record


@pytest.fixture
def client() -> Generator[TestClient]:
    with TestClient(app, base_url="http://127.0.0.1:15173") as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client: TestClient, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/sessions",
        json={"email": user.email, "password": "correct horse battery staple"},
    )
    assert response.status_code == 201
    return {
        "Origin": "http://127.0.0.1:15173",
        "X-CSRF-Token": response.json()["csrf_token"],
    }
