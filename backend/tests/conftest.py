from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from lume.auth.models import AuthSession
from lume.categories.defaults import seed_default_categories
from lume.categories.models import Category
from lume.core.database import SessionFactory
from lume.core.security import hash_password
from lume.main import app
from lume.users.models import User


@pytest.fixture(autouse=True)
def clean_database() -> Generator[None]:
    with SessionFactory.begin() as session:
        session.execute(delete(AuthSession))
        session.execute(delete(Category))
        session.execute(delete(User))
    yield
    with SessionFactory.begin() as session:
        session.execute(delete(AuthSession))
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
