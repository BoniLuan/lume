from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from lume.core.database import SessionFactory
from lume.imports.models import ImportReview, ImportRowResolution
from lume.transactions.models import Transaction
from lume.users.models import User
from test_imports import _account, _category


def start(
    client: TestClient,
    headers: dict[str, str],
    account: str,
    content: str,
    filename: str = "bank.csv",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/imports/reviews",
        headers=headers,
        json={
            "account_id": account,
            "filename": filename,
            "content": content,
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def update(
    client: TestClient,
    headers: dict[str, str],
    review: dict[str, Any],
    decisions: list[dict[str, Any]],
    apply: bool = False,
) -> Any:
    method = client.post if apply else client.put
    return method(
        f"/api/v1/imports/reviews/{review['id']}" + ("/apply" if apply else ""),
        headers=headers,
        json={"version": review["version"], "decisions": decisions},
    )


def existing(
    client: TestClient,
    headers: dict[str, str],
    user: User,
    account: str,
    description: str,
    amount: str = "12.50",
    **extra: str,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "kind": "expense",
            "account_id": account,
            "category_id": _category(user.id, "expense"),
            "amount": amount,
            "description": description,
            "effective_date": "2026-10-05",
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def test_review_links_different_descriptions_and_saves_pending_rows(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    bank = _account(client, auth_headers, "Nubank")
    tx = existing(client, auth_headers, user, bank, "My subscription")
    review = start(
        client,
        auth_headers,
        bank,
        "date,description,amount\n2026-10-05,Pix to someone,-12.50\n2026-10-06,Shop,-20.00\n",
    )
    assert [d["action"] for d in review["decisions"]] == ["pending", "pending"]
    match = review["rows"][0]["candidates"][0]
    assert match["transaction_id"] == tx["id"]
    assert match["description"] == "My subscription"
    assert "Same account" in match["reasons"]
    decisions = review["decisions"]
    decisions[0].update(action="link", transaction_id=tx["id"], account_id=bank)
    saved = update(client, auth_headers, review, decisions)
    assert saved.status_code == 200, saved.text
    with SessionFactory() as db:
        assert db.scalar(select(func.count()).select_from(Transaction)) == 1
        assert db.scalar(select(func.count()).select_from(ImportRowResolution)) == 0
    resumed = client.get(f"/api/v1/imports/reviews/{review['id']}").json()
    assert resumed["decisions"][0]["action"] == "link"
    assert update(client, auth_headers, review, decisions).status_code == 409
    applied = update(client, auth_headers, resumed, decisions, apply=True)
    assert applied.status_code == 200, applied.text
    assert {k: applied.json()[k] for k in ["created", "linked", "ignored", "pending"]} == {
        "created": 0,
        "linked": 1,
        "ignored": 0,
        "pending": 1,
    }
    assert client.get(f"/api/v1/transactions/{tx['id']}").json()["description"] == "My subscription"
    again = start(
        client,
        auth_headers,
        bank,
        "date,description,amount\n2026-10-05,Pix to someone,-12.50\n2026-10-06,Shop,-20.00\n",
    )
    assert again["id"] == review["id"]
    assert again["rows"][0]["resolved_action"] == "link"
    retried = update(client, auth_headers, applied.json()["review"], decisions, apply=True)
    assert retried.status_code == 200
    assert retried.json()["linked"] == 0


def test_review_creates_transfers_ignores_rows_and_projects_balances(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    bank = _account(client, auth_headers, "Bank")
    card = _account(client, auth_headers, "Card")
    ofx = """<OFX><STMTRS><CURDEF>BRL<BANKACCTFROM><ACCTTYPE>CHECKING<ACCTID>12345678</BANKACCTFROM>
<BANKTRANLIST><DTSTART>20261001<DTEND>20261031
<STMTTRN><DTPOSTED>20261005<TRNAMT>-25.00<FITID>payment<MEMO>Pagamento de fatura</STMTTRN>
<STMTTRN><DTPOSTED>20261006<TRNAMT>25.00<FITID>return<MEMO>Incoming transfer</STMTTRN>
<STMTTRN><DTPOSTED>20261007<TRNAMT>-1.00<FITID>ignored<MEMO>Ignore me</STMTTRN>
</BANKTRANLIST><LEDGERBAL><BALAMT>-1.00<DTASOF>20261031</LEDGERBAL></STMTRS></OFX>"""
    review = start(client, auth_headers, bank, ofx, "bank.ofx")
    assert review["metadata"]["closing_balance"] == "-1.0000"
    assert review["metadata"]["inferred_opening_balance"] == "0.0000"
    assert review["metadata"]["account_last_four"] == "5678"
    decisions = review["decisions"]
    decisions[0].update(
        action="create", kind="transfer", counterparty_account_id=card, description="Card payment"
    )
    decisions[1].update(action="create", kind="transfer", counterparty_account_id=card)
    decisions[2]["action"] = "skip"
    saved = update(client, auth_headers, review, decisions)
    assert saved.status_code == 200, saved.text
    balances = {b["account_id"]: b for b in saved.json()["balances"]}
    assert balances[bank]["projected_balance"] == "0.0000"
    assert balances[card]["projected_balance"] == "0.0000"
    applied = update(client, auth_headers, saved.json(), decisions, apply=True)
    assert applied.status_code == 200, applied.text
    assert applied.json()["created"] == 2
    assert applied.json()["ignored"] == 1
    with SessionFactory() as db:
        txs = list(db.scalars(select(Transaction).order_by(Transaction.effective_date)))
        assert (txs[0].account_id, txs[0].destination_account_id) == (bank, card)
        assert (txs[1].account_id, txs[1].destination_account_id) == (card, bank)
        assert all(tx.category_id is None for tx in txs)
    assert (
        update(client, auth_headers, applied.json()["review"], decisions, apply=True).json()[
            "created"
        ]
        == 0
    )


def test_same_transaction_leg_cannot_resolve_two_rows_and_batch_is_atomic(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    bank = _account(client, auth_headers, "Bank")
    tx = existing(client, auth_headers, user, bank, "Coffee")
    review = start(
        client,
        auth_headers,
        bank,
        "date,description,amount\n2026-10-05,Pix one,-12.50\n2026-10-05,Pix two,-12.50\n",
    )
    decisions = review["decisions"]
    for decision in decisions:
        decision.update(action="link", transaction_id=tx["id"], account_id=bank)
    response = update(client, auth_headers, review, decisions, apply=True)
    assert response.status_code == 409, response.text
    with SessionFactory() as db:
        assert db.scalar(select(func.count()).select_from(ImportRowResolution)) == 0
        assert db.get(ImportReview, review["id"]).version == review["version"]  # type: ignore[union-attr]


def test_create_despite_candidate_requires_explicit_confirmation(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    bank = _account(client, auth_headers, "Bank")
    existing(client, auth_headers, user, bank, "Coffee")
    review = start(client, auth_headers, bank, "date,description,amount\n2026-10-05,Pix,-12.50\n")
    decisions = review["decisions"]
    decisions[0].update(
        action="create", category_id=_category(user.id, "expense"), description="Another coffee"
    )
    assert update(client, auth_headers, review, decisions, apply=True).status_code == 422
    decisions[0]["allow_possible_match"] = True
    response = update(client, auth_headers, review, decisions, apply=True)
    assert response.status_code == 200, response.text
    assert response.json()["created"] == 1


def test_account_override_and_search_across_dates(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    bank = _account(client, auth_headers, "Bank")
    other = _account(client, auth_headers, "Other")
    tx = existing(client, auth_headers, user, other, "Older entry", effective_date="2026-09-01")
    review = start(client, auth_headers, bank, "date,description,amount\n2026-10-05,Pix,-12.50\n")
    assert not review["rows"][0]["candidates"]
    response = client.get(
        f"/api/v1/imports/reviews/{review['id']}/candidates",
        params={"row_key": review["rows"][0]["row_key"], "search": "Older"},
    )
    assert response.status_code == 200
    assert response.json()[0]["transaction_id"] == tx["id"]
    assert response.json()[0]["ledger_account_id"] == other
    decisions = review["decisions"]
    decisions[0].update(action="link", account_id=other, transaction_id=tx["id"])
    saved = update(client, auth_headers, review, decisions)
    assert saved.status_code == 200, saved.text
    assert saved.json()["rows"][0]["candidates"][0]["transaction_id"] == tx["id"]
    applied = update(client, auth_headers, saved.json(), decisions, apply=True)
    assert applied.status_code == 200, applied.text
    assert applied.json()["review"]["rows"][0]["resolution_warning"]


def test_saved_review_delete_keeps_links_and_reupload_resolves_again(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    bank = _account(client, auth_headers, "Bank")
    content = "date,description,amount\n2026-10-05,Skip this,-12.50\n"
    review = start(client, auth_headers, bank, content)
    review["decisions"][0]["action"] = "skip"
    assert update(client, auth_headers, review, review["decisions"], apply=True).status_code == 200
    response = client.delete(f"/api/v1/imports/reviews/{review['id']}", headers=auth_headers)
    assert response.status_code == 204
    assert client.get(f"/api/v1/imports/reviews/{review['id']}").status_code == 404
    reuploaded = start(client, auth_headers, bank, content)
    assert reuploaded["id"] != review["id"]
    assert reuploaded["rows"][0]["resolved_action"] == "skip"


def test_review_owner_checks_and_link_validation(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    bank = _account(client, auth_headers, "Bank")
    tx = existing(client, auth_headers, user, bank, "Wrong amount", amount="5.00")
    review = start(client, auth_headers, bank, "date,description,amount\n2026-10-05,Pix,-12.50\n")
    review["decisions"][0].update(action="link", transaction_id=tx["id"])
    assert update(client, auth_headers, review, review["decisions"], apply=True).status_code == 422
    # Ownership on the saved file is independent of knowing its identifier.
    with SessionFactory.begin() as db:
        other = User(
            email="other@example.com",
            normalized_email="other@example.com",
            password_hash=user.password_hash,
            display_name="Other",
            base_currency="BRL",
            locale="en",
            timezone="America/Sao_Paulo",
        )
        db.add(other)
        db.flush()
        other_id = other.id
        record = db.get(ImportReview, review["id"])
        assert record is not None
        # Use direct endpoint calls under another authenticated owner's dependency below.
    from lume.auth.dependencies import get_auth_context
    from lume.main import app

    original = app.dependency_overrides.get(get_auth_context)
    from lume.auth.dependencies import AuthContext
    from lume.auth.models import AuthSession

    with SessionFactory() as db:
        session = db.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
        other_user = db.get(User, other_id)
        assert session is not None and other_user is not None
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            session, other_user, "unused"
        )
        try:
            assert client.get(f"/api/v1/imports/reviews/{review['id']}").status_code == 404
            assert client.get("/api/v1/imports/reviews").json() == []
            assert (
                client.get(
                    f"/api/v1/imports/reviews/{review['id']}/candidates",
                    params={"row_key": review["rows"][0]["row_key"]},
                ).status_code
                == 404
            )
        finally:
            if original is None:
                app.dependency_overrides.pop(get_auth_context)
            else:
                app.dependency_overrides[get_auth_context] = original


@pytest.mark.parametrize("change", ["currency", "multiple"])
def test_statement_metadata_rejects_incompatible_files(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
    change: str,
) -> None:
    bank = _account(client, auth_headers, "Bank")
    content = (
        "<STMTRS><CURDEF>USD<STMTTRN><DTPOSTED>20261005<TRNAMT>-1<NAME>Shop</STMTTRN></STMTRS>"
    )
    if change == "multiple":
        content = content.replace("USD", "BRL") * 2
    response = client.post(
        "/api/v1/imports/reviews",
        headers=auth_headers,
        json={"account_id": bank, "filename": "bank.ofx", "content": content},
    )
    assert response.status_code == 422, response.text


def test_transfer_can_be_linked_once_from_each_account_statement(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    bank = _account(client, auth_headers, "Bank")
    savings = _account(client, auth_headers, "Savings")
    response = client.post(
        "/api/v1/transactions",
        headers=auth_headers,
        json={
            "kind": "transfer",
            "account_id": bank,
            "destination_account_id": savings,
            "amount": "50.00",
            "description": "Saving money",
            "effective_date": "2026-10-05",
        },
    )
    assert response.status_code == 201
    tx_id = response.json()["id"]
    for account, amount in [(bank, "-50.00"), (savings, "50.00")]:
        review = start(
            client,
            auth_headers,
            account,
            f"date,description,amount\n2026-10-05,Transfer,{amount}\n",
        )
        assert review["rows"][0]["candidates"][0]["already_linked"] is False
        review["decisions"][0].update(action="link", account_id=account, transaction_id=tx_id)
        response = update(client, auth_headers, review, review["decisions"], apply=True)
        assert response.status_code == 200, response.text
        assert response.json()["linked"] == 1
    with SessionFactory() as db:
        assert db.scalar(select(func.count()).select_from(Transaction)) == 1
        assert db.scalar(select(func.count()).select_from(ImportRowResolution)) == 2


def test_resolution_warns_after_void_and_does_not_create_replacement(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    bank = _account(client, auth_headers, "Bank")
    tx = existing(client, auth_headers, user, bank, "Recorded purchase")
    review = start(client, auth_headers, bank, "date,description,amount\n2026-10-05,Pix,-12.50\n")
    review["decisions"][0].update(action="link", transaction_id=tx["id"])
    assert update(client, auth_headers, review, review["decisions"], apply=True).status_code == 200
    assert (
        client.post(f"/api/v1/transactions/{tx['id']}/void", headers=auth_headers).status_code
        == 200
    )
    refreshed = client.get(f"/api/v1/imports/reviews/{review['id']}").json()
    assert refreshed["rows"][0]["resolved_action"] == "link"
    assert refreshed["rows"][0]["resolution_warning"]
    refreshed["decisions"][0].update(action="create", category_id=_category(user.id, "expense"))
    response = update(client, auth_headers, refreshed, refreshed["decisions"], apply=True)
    assert response.status_code == 200
    assert response.json()["created"] == 0


def test_review_retains_full_bank_text_and_accepts_incomplete_saved_description(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    bank = _account(client, auth_headers, "Bank")
    description = "Bank description " + "details " * 30
    review = start(
        client, auth_headers, bank, f"date,description,amount\n2026-10-05,{description},-12.50\n"
    )
    assert review["rows"][0]["description"] == description.strip()
    review["decisions"][0].update(action="create", description="")
    saved = update(client, auth_headers, review, review["decisions"])
    assert saved.status_code == 200, saved.text
    assert (
        update(
            client, auth_headers, saved.json(), saved.json()["decisions"], apply=True
        ).status_code
        == 422
    )


def test_already_linked_candidate_still_requires_duplicate_confirmation(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    bank = _account(client, auth_headers, "Bank")
    tx = existing(client, auth_headers, user, bank, "Coffee")
    first = start(
        client,
        auth_headers,
        bank,
        "date,description,amount,id\n2026-10-05,Pix,-12.50,first-bank-id\n",
    )
    first["decisions"][0].update(action="link", account_id=bank, transaction_id=tx["id"])
    assert update(client, auth_headers, first, first["decisions"], apply=True).status_code == 200
    second = start(
        client,
        auth_headers,
        bank,
        "date,description,amount,id\n2026-10-05,Pix,-12.50,another-bank-id\n",
    )
    assert second["rows"][0]["candidates"][0]["already_linked"] is True
    second["decisions"][0].update(
        action="create", category_id=_category(user.id, "expense"), allow_possible_match=False
    )
    response = update(client, auth_headers, second, second["decisions"], apply=True)
    assert response.status_code == 422, response.text
    with SessionFactory() as db:
        assert db.scalar(select(func.count()).select_from(Transaction)) == 1
    second["decisions"][0]["allow_possible_match"] = True
    confirmed = update(client, auth_headers, second, second["decisions"], apply=True)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["created"] == 1


def test_review_write_endpoints_and_links_reject_another_owner(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    from lume.categories.defaults import seed_default_categories
    from lume.main import app

    bank = _account(client, auth_headers, "Owner bank")
    owned = start(client, auth_headers, bank, "date,description,amount\n2026-10-05,Pix,-12.50\n")
    with SessionFactory.begin() as db:
        other = User(
            email="private@example.com",
            normalized_email="private@example.com",
            password_hash=user.password_hash,
            display_name="Another owner",
            base_currency="BRL",
            locale="en",
            timezone="America/Sao_Paulo",
        )
        db.add(other)
        db.flush()
        seed_default_categories(db, other.id)
        other_id = other.id
    with TestClient(app, base_url="http://127.0.0.1:15173") as other_client:
        login = other_client.post(
            "/api/v1/auth/sessions",
            json={
                "email": "private@example.com",
                "password": "correct horse battery staple",
            },
        )
        assert login.status_code == 201
        other_headers = {
            "Origin": "http://127.0.0.1:15173",
            "X-CSRF-Token": login.json()["csrf_token"],
        }
        other_bank = _account(other_client, other_headers, "Private bank")
        private_review = start(
            other_client,
            other_headers,
            other_bank,
            "date,description,amount\n2026-10-05,Private purchase,-12.50\n",
        )
        private_tx = other_client.post(
            "/api/v1/transactions",
            headers=other_headers,
            json={
                "kind": "expense",
                "account_id": other_bank,
                "category_id": _category(other_id, "expense"),
                "amount": "12.50",
                "description": "Private purchase",
                "effective_date": "2026-10-05",
            },
        )
        assert private_tx.status_code == 201
        assert client.get(f"/api/v1/imports/reviews/{private_review['id']}").status_code == 404
        assert (
            update(client, auth_headers, private_review, private_review["decisions"]).status_code
            == 404
        )
        assert (
            update(
                client, auth_headers, private_review, private_review["decisions"], apply=True
            ).status_code
            == 404
        )
        assert (
            client.delete(
                f"/api/v1/imports/reviews/{private_review['id']}", headers=auth_headers
            ).status_code
            == 404
        )
        owned["decisions"][0].update(action="link", transaction_id=private_tx.json()["id"])
        response = update(client, auth_headers, owned, owned["decisions"], apply=True)
        assert response.status_code == 422, response.text
        assert not client.get(f"/api/v1/imports/reviews/{owned['id']}").json()["rows"][0][
            "candidates"
        ]
        assert (
            other_client.get(f"/api/v1/imports/reviews/{private_review['id']}").status_code == 200
        )


def test_apply_rejects_a_transaction_voided_after_saving_the_link(
    client: TestClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    bank = _account(client, auth_headers, "Bank")
    tx = existing(client, auth_headers, user, bank, "Coffee")
    review = start(client, auth_headers, bank, "date,description,amount\n2026-10-05,Pix,-12.50\n")
    review["decisions"][0].update(action="link", transaction_id=tx["id"])
    saved = update(client, auth_headers, review, review["decisions"])
    assert saved.status_code == 200
    assert (
        client.post(f"/api/v1/transactions/{tx['id']}/void", headers=auth_headers).status_code
        == 200
    )
    applied = update(client, auth_headers, saved.json(), saved.json()["decisions"], apply=True)
    assert applied.status_code == 422, applied.text
    refreshed = client.get(f"/api/v1/imports/reviews/{review['id']}").json()
    assert refreshed["version"] == saved.json()["version"]
    assert refreshed["rows"][0]["invalid_transaction_id"] == tx["id"]
    with SessionFactory() as db:
        assert db.scalar(select(func.count()).select_from(ImportRowResolution)) == 0
