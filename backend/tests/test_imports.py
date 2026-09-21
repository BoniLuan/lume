from decimal import Decimal
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy import select

from lume.categories.models import Category
from lume.core.database import SessionFactory
from lume.imports.parser import parse_statement
from lume.users.models import User


def _account(client: TestClient, headers: dict[str, str], name: str) -> str:
    response = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "name": name,
            "account_type": "checking",
            "account_class": "asset",
            "opening_balance": "0.00",
            "opened_on": "2026-09-01",
        },
    )
    assert response.status_code == 201, response.text
    return cast(str, response.json()["id"])


def _category(user_id: str, kind: str) -> str:
    with SessionFactory() as db:
        category = db.scalar(
            select(Category).where(Category.user_id == user_id, Category.kind == kind)
        )
        assert category is not None
        return category.id


def test_csv_review_commit_suggest_and_retry(
    client: TestClient, user: User, auth_headers: dict[str, str]
) -> None:
    account_id = _account(client, auth_headers, "Checking")
    category_id = _category(user.id, "expense")
    statement = {
        "account_id": account_id,
        "filename": "bank.csv",
        "content": "date,description,amount\n2026-09-10,Coffee,-12.50\n2026-09-11,Salary,100.00\n",
    }
    preview = client.post("/api/v1/imports/preview", json=statement, headers=auth_headers)
    assert preview.status_code == 200, preview.text
    rows = preview.json()["rows"]
    assert [row["kind"] for row in rows] == ["expense", "income"]
    decisions = [
        {
            "row_key": rows[0]["row_key"],
            "action": "create",
            "category_id": category_id,
            "remember_category": True,
        },
        {"row_key": rows[1]["row_key"], "action": "skip"},
    ]
    committed = client.post(
        "/api/v1/imports/commit", json={**statement, "decisions": decisions}, headers=auth_headers
    )
    assert committed.status_code == 201, committed.text
    assert committed.json() == {"created": 1, "skipped": 1, "matched": 0}
    again = client.post("/api/v1/imports/preview", json=statement, headers=auth_headers)
    assert again.json()["rows"][0]["matched_transaction_id"]
    assert again.json()["rows"][0]["suggested_category_id"] == category_id
    retry = client.post(
        "/api/v1/imports/commit", json={**statement, "decisions": decisions}, headers=auth_headers
    )
    assert retry.status_code == 201
    assert retry.json() == {"created": 0, "skipped": 1, "matched": 1}
    assert client.get(f"/api/v1/accounts/{account_id}").json()["current_balance"] == "-12.5000"


def test_ofx_incoming_transfer_and_invalid_review(
    client: TestClient, user: User, auth_headers: dict[str, str]
) -> None:
    bank = _account(client, auth_headers, "Bank")
    other = _account(client, auth_headers, "Other")
    statement = {
        "account_id": bank,
        "filename": "statement.ofx",
        "content": (
            "<STMTTRN><DTPOSTED>20260910120000<TRNAMT>25.00<FITID>abc<NAME>Transfer in</STMTTRN>"
        ),
    }
    preview = client.post("/api/v1/imports/preview", json=statement, headers=auth_headers)
    assert preview.status_code == 200, preview.text
    row = preview.json()["rows"][0]
    assert row["effective_date"] == "2026-09-10"
    incomplete = client.post(
        "/api/v1/imports/commit",
        json={**statement, "decisions": [{"row_key": row["row_key"], "action": "create"}]},
        headers=auth_headers,
    )
    assert incomplete.status_code == 422
    committed = client.post(
        "/api/v1/imports/commit",
        json={
            **statement,
            "decisions": [
                {
                    "row_key": row["row_key"],
                    "action": "create",
                    "kind": "transfer",
                    "counterparty_account_id": other,
                }
            ],
        },
        headers=auth_headers,
    )
    assert committed.status_code == 201, committed.text
    assert committed.json()["created"] == 1
    assert client.get(f"/api/v1/accounts/{bank}").json()["current_balance"] == "25.0000"
    assert client.get(f"/api/v1/accounts/{other}").json()["current_balance"] == "-25.0000"


def test_possible_match_requires_explicit_override(
    client: TestClient, user: User, auth_headers: dict[str, str]
) -> None:
    account_id = _account(client, auth_headers, "Checking")
    category_id = _category(user.id, "expense")
    first = {
        "account_id": account_id,
        "filename": "first.csv",
        "content": "date,description,amount\n2026-09-10,Coffee,-12.50\n",
    }
    second = {
        "account_id": account_id,
        "filename": "second.csv",
        "content": "date,description,amount\n2026-09-11,Coffee,-12.50\n",
    }
    first_row = client.post("/api/v1/imports/preview", json=first, headers=auth_headers).json()[
        "rows"
    ][0]
    decision = {"row_key": first_row["row_key"], "action": "create", "category_id": category_id}
    assert (
        client.post(
            "/api/v1/imports/commit", json={**first, "decisions": [decision]}, headers=auth_headers
        ).json()["created"]
        == 1
    )
    second_row = client.post("/api/v1/imports/preview", json=second, headers=auth_headers).json()[
        "rows"
    ][0]
    assert second_row["matched_transaction_id"]
    decision["row_key"] = second_row["row_key"]
    assert (
        client.post(
            "/api/v1/imports/commit", json={**second, "decisions": [decision]}, headers=auth_headers
        ).json()["matched"]
        == 1
    )
    decision["allow_possible_match"] = True
    assert (
        client.post(
            "/api/v1/imports/commit", json={**second, "decisions": [decision]}, headers=auth_headers
        ).json()["created"]
        == 1
    )


def test_csv_and_ofx_parsing() -> None:
    csv_rows = parse_statement(
        "account", "statement.csv", "Data;Descrição;Débito;Crédito\n21/09/2026;Shop;47,90;\n"
    )[1]
    assert csv_rows[0].amount == Decimal("47.90")
    assert csv_rows[0].kind == "expense"
    ofx_rows = parse_statement(
        "account",
        "statement.ofx",
        "<STMTTRN><DTPOSTED>20260921120000<TRNAMT>-5.25<NAME>Shop</STMTTRN>",
    )[1]
    assert ofx_rows[0].effective_date.isoformat() == "2026-09-21"
