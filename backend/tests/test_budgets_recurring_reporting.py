from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy import select

from lume.categories.models import Category
from lume.core.database import SessionFactory
from lume.users.models import User


def _create_account(client: TestClient, headers: dict[str, str], name: str) -> str:
    response = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "name": name,
            "account_type": "checking",
            "account_class": "asset",
            "opening_balance": "0.0000",
            "opened_on": "2026-09-01",
        },
    )
    assert response.status_code == 201
    return cast(str, response.json()["id"])


def _category(user_id: str, kind: str) -> Category:
    with SessionFactory() as session:
        category = session.scalar(
            select(Category).where(Category.user_id == user_id, Category.kind == kind)
        )
        assert category is not None
        session.expunge(category)
        return category


def _transaction(
    client: TestClient,
    headers: dict[str, str],
    account_id: str,
    category_id: str,
    kind: str,
    amount: str,
    description: str,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "kind": kind,
            "account_id": account_id,
            "category_id": category_id,
            "amount": amount,
            "description": description,
            "effective_date": "2026-09-16",
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, object], response.json())


def test_budget_usage_and_dashboard_reconcile(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    account_id = _create_account(client, auth_headers, "Checking")
    income = _category(user.id, "income")
    expense = _category(user.id, "expense")
    _transaction(client, auth_headers, account_id, income.id, "income", "2000.0000", "Salary")
    _transaction(client, auth_headers, account_id, expense.id, "expense", "47.9000", "Lunch")

    budget = client.put(
        "/api/v1/budgets/2026-09",
        headers=auth_headers,
        json={"total_limit": "1000.0000"},
    )
    category_budget = client.put(
        f"/api/v1/budgets/2026-09/categories/{expense.id}",
        headers=auth_headers,
        json={"limit_amount": "200.0000"},
    )
    dashboard = client.get("/api/v1/dashboard?month=2026-09")

    assert budget.status_code == category_budget.status_code == 200
    assert category_budget.json()["spent"] == "47.9000"
    assert category_budget.json()["remaining"] == "952.1000"
    assert category_budget.json()["categories"][0]["spent"] == "47.9000"
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["income"] == "2000.0000"
    assert body["expense"] == "47.9000"
    assert body["net"] == "1952.1000"
    assert body["categories"][0]["amount"] == "47.9000"
    assert body["largest_expenses"][0]["description"] == "Lunch"
    assert len(body["trend"]) == 6


def test_monthly_recurrence_preserves_the_31st_after_short_month(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    account_id = _create_account(client, auth_headers, "Checking")
    category = _category(user.id, "expense")
    created = client.post(
        "/api/v1/recurring-templates",
        headers=auth_headers,
        json={
            "kind": "expense",
            "account_id": account_id,
            "category_id": category.id,
            "amount": "100.0000",
            "description": "Monthly service",
            "frequency": "monthly",
            "interval_count": 1,
            "start_on": "2027-01-31",
        },
    )
    assert created.status_code == 201, created.text
    template_id = created.json()["id"]

    recorded = client.post(
        f"/api/v1/recurring-templates/{template_id}/occurrences",
        headers=auth_headers,
        json={"scheduled_for": "2027-01-31"},
    )
    assert recorded.status_code == 201
    assert recorded.json()["transaction_id"]
    after_record = client.get("/api/v1/recurring-templates").json()[0]
    assert after_record["next_due_on"] == "2027-02-28"

    skipped = client.post(
        f"/api/v1/recurring-templates/{template_id}/occurrences/2027-02-28/skip",
        headers=auth_headers,
    )
    assert skipped.status_code == 201
    assert skipped.json()["status"] == "skipped"
    after_skip = client.get("/api/v1/recurring-templates").json()[0]
    assert after_skip["next_due_on"] == "2027-03-31"


def test_duplicate_or_out_of_order_occurrence_is_rejected(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    account_id = _create_account(client, auth_headers, "Checking")
    category = _category(user.id, "income")
    created = client.post(
        "/api/v1/recurring-templates",
        headers=auth_headers,
        json={
            "kind": "income",
            "account_id": account_id,
            "category_id": category.id,
            "amount": "500.0000",
            "description": "Side income",
            "frequency": "weekly",
            "start_on": "2026-09-16",
        },
    )
    template_id = created.json()["id"]
    response = client.post(
        f"/api/v1/recurring-templates/{template_id}/occurrences",
        headers=auth_headers,
        json={"scheduled_for": "2026-09-23"},
    )
    assert response.status_code == 409
