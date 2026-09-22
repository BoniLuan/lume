from fastapi.testclient import TestClient
from sqlalchemy import select

from lume.categories.models import Category
from lume.core.database import SessionFactory
from lume.users.models import User


def _account(client: TestClient, headers: dict[str, str], name: str, card: bool = False) -> str:
    response = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "name": name,
            "account_type": "credit_card" if card else "checking",
            "account_class": "liability" if card else "asset",
            "opening_balance": "0.00",
            "opened_on": "2026-08-01",
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _expense_category(user_id: str) -> str:
    with SessionFactory() as db:
        category = db.scalar(
            select(Category).where(Category.user_id == user_id, Category.kind == "expense")
        )
        assert category is not None
        return category.id


def test_card_reconciliation_respects_cutoff_and_sign(
    client: TestClient, user: User, auth_headers: dict[str, str]
) -> None:
    bank = _account(client, auth_headers, "Bank")
    card = _account(client, auth_headers, "NuCard", card=True)
    category = _expense_category(user.id)
    expense = client.post(
        "/api/v1/transactions",
        headers=auth_headers,
        json={
            "kind": "expense",
            "account_id": card,
            "category_id": category,
            "amount": "200.00",
            "description": "Groceries",
            "effective_date": "2026-09-10",
        },
    )
    assert expense.status_code == 201, expense.text
    payment = client.post(
        "/api/v1/transactions",
        headers=auth_headers,
        json={
            "kind": "transfer",
            "account_id": bank,
            "destination_account_id": card,
            "amount": "250.00",
            "description": "Invoice payment",
            "effective_date": "2026-09-12",
        },
    )
    assert payment.status_code == 201, payment.text
    before = client.post(
        "/api/v1/reports/account-reconciliation",
        headers=auth_headers,
        json={"account_id": card, "as_of_date": "2026-09-11", "actual_balance": "-200.00"},
    )
    assert before.status_code == 200, before.text
    assert before.json()["calculated_balance"] == "-200.0000"
    assert before.json()["difference"] == "0.0000"
    after = client.post(
        "/api/v1/reports/account-reconciliation",
        headers=auth_headers,
        json={"account_id": card, "as_of_date": "2026-09-12", "actual_balance": "0.00"},
    )
    assert after.status_code == 200, after.text
    assert after.json()["calculated_balance"] == "50.0000"
    assert after.json()["difference"] == "-50.0000"
    assert after.json()["transfers_in"] == "250.0000"
    assert after.json()["movement_count"] == 2
    assert client.get(f"/api/v1/accounts/{bank}").json()["current_balance"] == "-250.0000"
    spending = client.get("/api/v1/reports/spending-insights?month=2026-09")
    assert spending.json()["expense"] == "200.0000"


def test_spending_insights_include_previous_month_and_account_split(
    client: TestClient, user: User, auth_headers: dict[str, str]
) -> None:
    bank = _account(client, auth_headers, "Bank")
    card = _account(client, auth_headers, "NuCard", card=True)
    category = _expense_category(user.id)
    for account, amount, posted in (
        (bank, "30.00", "2026-08-10"),
        (bank, "40.00", "2026-09-10"),
        (card, "60.00", "2026-09-11"),
    ):
        response = client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "kind": "expense",
                "account_id": account,
                "category_id": category,
                "amount": amount,
                "description": "Shopping",
                "effective_date": posted,
            },
        )
        assert response.status_code == 201, response.text
    report = client.get("/api/v1/reports/spending-insights?month=2026-09")
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["expense"] == "100.0000"
    assert body["previous_expense"] == "30.0000"
    assert body["change"] == "70.0000"
    assert {row["account_name"]: row["amount"] for row in body["accounts"]} == {
        "Bank": "40.0000",
        "NuCard": "60.0000",
    }
    assert body["categories"][0]["change"] == "70.0000"
    assert (
        client.post(
            "/api/v1/reports/account-reconciliation",
            headers=auth_headers,
            json={"account_id": card, "as_of_date": "2026-07-31", "actual_balance": "0.00"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/reports/account-reconciliation",
            headers=auth_headers,
            json={
                "account_id": "does-not-exist",
                "as_of_date": "2026-09-30",
                "actual_balance": "0.00",
            },
        ).status_code
        == 404
    )
