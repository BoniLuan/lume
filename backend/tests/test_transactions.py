from datetime import date
from typing import cast
from uuid import uuid7

from fastapi.testclient import TestClient
from sqlalchemy import select

from lume.accounts.models import Account
from lume.categories.models import Category
from lume.core.database import SessionFactory
from lume.core.security import hash_password
from lume.users.models import User


def _create_account(
    client: TestClient,
    headers: dict[str, str],
    name: str,
    account_type: str = "checking",
    account_class: str = "asset",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "name": name,
            "account_type": account_type,
            "account_class": account_class,
            "opening_balance": "0.0000",
            "opened_on": "2026-09-01",
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, object], response.json())


def _category_id(user_id: str, kind: str) -> str:
    with SessionFactory() as session:
        category = session.scalar(
            select(Category).where(Category.user_id == user_id, Category.kind == kind)
        )
        assert category is not None
        return category.id


def test_income_expense_transfer_and_void_reconcile_balances(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    checking = _create_account(client, auth_headers, "Checking")
    savings = _create_account(client, auth_headers, "Savings", "savings")
    income_category = _category_id(user.id, "income")
    expense_category = _category_id(user.id, "expense")

    income = client.post(
        "/api/v1/transactions",
        headers=auth_headers,
        json={
            "kind": "income",
            "account_id": checking["id"],
            "category_id": income_category,
            "amount": "1000.0000",
            "description": "Salary",
            "effective_date": "2026-09-10",
        },
    )
    expense = client.post(
        "/api/v1/transactions",
        headers=auth_headers,
        json={
            "kind": "expense",
            "account_id": checking["id"],
            "category_id": expense_category,
            "amount": "47.9000",
            "description": "Lunch",
            "effective_date": "2026-09-11",
        },
    )
    transfer = client.post(
        "/api/v1/transactions",
        headers=auth_headers,
        json={
            "kind": "transfer",
            "account_id": checking["id"],
            "destination_account_id": savings["id"],
            "amount": "200.0000",
            "description": "Move to savings",
            "effective_date": "2026-09-12",
        },
    )

    assert income.status_code == expense.status_code == transfer.status_code == 201
    assert expense.json()["amount"] == "47.9000"
    accounts = {item["name"]: item for item in client.get("/api/v1/accounts").json()}
    assert accounts["Checking"]["current_balance"] == "752.1000"
    assert accounts["Savings"]["current_balance"] == "200.0000"

    voided = client.post(f"/api/v1/transactions/{expense.json()['id']}/void", headers=auth_headers)
    assert voided.status_code == 200
    checking_after = client.get(f"/api/v1/accounts/{checking['id']}").json()
    assert checking_after["current_balance"] == "800.0000"


def test_transaction_creation_is_retry_safe(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    account = _create_account(client, auth_headers, "Cash", "cash")
    request_id = str(uuid7())
    body = {
        "kind": "expense",
        "account_id": account["id"],
        "category_id": _category_id(user.id, "expense"),
        "amount": "12.3400",
        "description": "Coffee",
        "effective_date": date(2026, 9, 16).isoformat(),
        "client_request_id": request_id,
    }

    first = client.post("/api/v1/transactions", headers=auth_headers, json=body)
    second = client.post("/api/v1/transactions", headers=auth_headers, json=body)

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


def test_float_money_is_rejected(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    account = _create_account(client, auth_headers, "Cash", "cash")
    response = client.post(
        "/api/v1/transactions",
        headers=auth_headers,
        json={
            "kind": "expense",
            "account_id": account["id"],
            "category_id": _category_id(user.id, "expense"),
            "amount": 12.34,
            "description": "Float attempt",
            "effective_date": "2026-09-16",
        },
    )
    assert response.status_code == 422


def test_cross_owner_account_is_rejected(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    with SessionFactory.begin() as session:
        other = User(
            email="other@example.com",
            normalized_email="other@example.com",
            password_hash=hash_password("another correct horse battery staple"),
            display_name="Other",
            base_currency="BRL",
            locale="en",
            timezone="America/Sao_Paulo",
        )
        session.add(other)
        session.flush()
        foreign_account = Account(
            user_id=other.id,
            name="Foreign account",
            account_type="checking",
            account_class="asset",
            currency="BRL",
            opening_balance="0.0000",
            opened_on=date(2026, 9, 1),
        )
        session.add(foreign_account)
        session.flush()
        foreign_id = foreign_account.id

    response = client.post(
        "/api/v1/transactions",
        headers=auth_headers,
        json={
            "kind": "expense",
            "account_id": foreign_id,
            "category_id": _category_id(user.id, "expense"),
            "amount": "10.0000",
            "description": "Forbidden",
            "effective_date": "2026-09-16",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "source account is unavailable"


def test_account_type_and_class_can_be_corrected(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    account = _create_account(client, auth_headers, "Mistaken account", "other", "liability")

    corrected = client.patch(
        f"/api/v1/accounts/{account['id']}",
        headers=auth_headers,
        json={"account_type": "checking", "account_class": "asset"},
    )

    assert corrected.status_code == 200
    assert corrected.json()["account_type"] == "checking"
    assert corrected.json()["account_class"] == "asset"


def test_credit_card_must_be_a_liability(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "name": "Card",
            "account_type": "credit_card",
            "account_class": "asset",
            "opening_balance": "0.0000",
            "opened_on": "2026-09-01",
        },
    )
    assert response.status_code == 422


def test_receivable_and_credit_card_transfers_do_not_double_count(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    checking = _create_account(client, auth_headers, "Checking")
    receivable = _create_account(client, auth_headers, "Money owed", "receivable", "asset")
    card = _create_account(client, auth_headers, "Credit card", "credit_card", "liability")
    expense_category = _category_id(user.id, "expense")

    income = client.post(
        "/api/v1/transactions",
        headers=auth_headers,
        json={
            "kind": "income",
            "account_id": checking["id"],
            "category_id": _category_id(user.id, "income"),
            "amount": "1000.0000",
            "description": "Salary",
            "effective_date": "2026-09-01",
        },
    )
    loan = client.post(
        "/api/v1/transactions",
        headers=auth_headers,
        json={
            "kind": "transfer",
            "account_id": checking["id"],
            "destination_account_id": receivable["id"],
            "amount": "150.0000",
            "description": "Loan to friend",
            "effective_date": "2026-09-02",
        },
    )
    repayment = client.post(
        "/api/v1/transactions",
        headers=auth_headers,
        json={
            "kind": "transfer",
            "account_id": receivable["id"],
            "destination_account_id": checking["id"],
            "amount": "150.0000",
            "description": "Friend repayment",
            "effective_date": "2026-09-03",
        },
    )
    purchase = client.post(
        "/api/v1/transactions",
        headers=auth_headers,
        json={
            "kind": "expense",
            "account_id": card["id"],
            "category_id": expense_category,
            "amount": "100.0000",
            "description": "Groceries",
            "effective_date": "2026-09-04",
        },
    )
    payment = client.post(
        "/api/v1/transactions",
        headers=auth_headers,
        json={
            "kind": "transfer",
            "account_id": checking["id"],
            "destination_account_id": card["id"],
            "amount": "100.0000",
            "description": "Card payment",
            "effective_date": "2026-09-05",
        },
    )
    assert all(item.status_code == 201 for item in (income, loan, repayment, purchase, payment))

    balances = {
        item["name"]: item["current_balance"] for item in client.get("/api/v1/accounts").json()
    }
    assert balances == {"Checking": "900.0000", "Money owed": "0.0000", "Credit card": "0.0000"}
    dashboard = client.get("/api/v1/dashboard?month=2026-09").json()
    assert dashboard["income"] == "1000.0000"
    assert dashboard["expense"] == "100.0000"
    assert dashboard["net"] == "900.0000"


def test_receivable_must_be_an_asset(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "name": "Invalid receivable",
            "account_type": "receivable",
            "account_class": "liability",
            "opening_balance": "0.0000",
            "opened_on": "2026-09-01",
        },
    )
    assert response.status_code == 422
