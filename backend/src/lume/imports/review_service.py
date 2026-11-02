"""Reviewed bank rows remain separate from the financial ledger until explicitly applied."""

import hashlib
import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal, cast

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from lume.accounts.models import Account
from lume.categories.models import Category
from lume.imports.models import ImportCategoryRule, ImportReview, ImportRowResolution
from lume.imports.parser import _date, _tag, merchant_key, parse_statement
from lume.imports.review_schemas import (
    MatchCandidate,
    ReviewBalance,
    ReviewDecision,
    ReviewResponse,
    ReviewRow,
    StatementMetadata,
)
from lume.imports.schemas import StatementPreviewRequest, StatementRow
from lume.transactions.models import Transaction
from lume.transactions.schemas import TransactionValues
from lume.transactions.service import validate_transaction_references


def active_account(db: Session, user_id: str, account_id: str) -> Account:
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user_id))
    if account is None or account.archived_at is not None:
        raise HTTPException(422, "Choose an active account")
    return account


def parsed_rows(review: ImportReview) -> list[StatementRow]:
    try:
        return parse_statement(review.account_id, review.filename, review.content)[1]
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


def metadata(review: ImportReview, rows: list[StatementRow]) -> StatementMetadata:
    start = min(row.effective_date for row in rows)
    end = max(row.effective_date for row in rows)
    if not review.filename.lower().endswith(".ofx"):
        return StatementMetadata(start_date=start, end_date=end)
    content = review.content
    # Never flatten several real bank accounts into one selected Lume account.
    if len(re.findall(r"<(?:STMTRS|CCSTMTRS)>", content, re.I)) > 1:
        raise HTTPException(
            422, "This OFX contains multiple statement accounts. Export each account separately."
        )
    try:
        start = _date(_tag(content, "DTSTART")) if _tag(content, "DTSTART") else start
        end = _date(_tag(content, "DTEND")) if _tag(content, "DTEND") else end
        ledger = re.search(r"<LEDGERBAL>(.*?)(?:</LEDGERBAL>|$)", content, re.I | re.S)
        balance = Decimal(_tag(ledger.group(1), "BALAMT")) if ledger else None
        balance_date = _date(_tag(ledger.group(1), "DTASOF")) if ledger else None
        if balance is not None and (not balance.is_finite() or abs(balance) >= 10**15):
            raise ValueError("Invalid OFX balance")
    except (ValueError, ArithmeticError) as error:
        raise HTTPException(422, "Invalid OFX statement dates or balance") from error
    if start > end or any(not start <= row.effective_date <= end for row in rows):
        raise HTTPException(422, "Statement dates do not cover its transactions")
    movement = sum(
        (row.amount if row.kind == "income" else -row.amount for row in rows), Decimal(0)
    )
    return StatementMetadata(
        institution=_tag(content, "ORG") or None,
        account_type=_tag(content, "ACCTTYPE")
        or ("CREDIT_CARD" if "<CCSTMTRS>" in content.upper() else None),
        currency=_tag(content, "CURDEF") or None,
        account_last_four=(_tag(content, "ACCTID")[-4:] or None),
        start_date=start,
        end_date=end,
        closing_balance=balance,
        balance_date=balance_date,
        inferred_opening_balance=balance - movement
        if balance is not None and balance_date == end
        else None,
    )


def new_review(db: Session, user_id: str, payload: StatementPreviewRequest) -> ImportReview:
    account = active_account(db, user_id, payload.account_id)
    fingerprint = hashlib.sha256(payload.content.encode()).hexdigest()
    existing = db.scalar(
        select(ImportReview).where(
            ImportReview.user_id == user_id,
            ImportReview.account_id == account.id,
            ImportReview.fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return existing
    review = ImportReview(
        user_id=user_id,
        account_id=account.id,
        filename=payload.filename,
        content=payload.content,
        fingerprint=fingerprint,
        decisions=[],
        version=1,
    )
    rows = parsed_rows(review)
    meta = metadata(review, rows)
    if meta.currency and meta.currency != account.currency:
        raise HTTPException(422, "Statement currency must match the Lume account")
    db.add(review)
    db.flush()
    return review


def review_decisions(review: ImportReview, rows: list[StatementRow]) -> list[ReviewDecision]:
    saved = {item["row_key"]: ReviewDecision.model_validate(item) for item in review.decisions}
    return [saved.get(row.row_key, ReviewDecision(row_key=row.row_key)) for row in rows]


def validate_decisions(rows: list[StatementRow], decisions: list[ReviewDecision]) -> None:
    if len(decisions) != len(rows) or {d.row_key for d in decisions} != {r.row_key for r in rows}:
        raise HTTPException(422, "Review every statement row exactly once")


def effect(transaction: Transaction, account_id: str) -> Decimal:
    if transaction.destination_account_id == account_id:
        return transaction.amount
    if transaction.account_id == account_id:
        return transaction.amount if transaction.kind == "income" else -transaction.amount
    return Decimal(0)


def balance_at(db: Session, accounts: list[Account], cutoff: date) -> dict[str, Decimal]:
    if not accounts:
        return {}
    user_id = accounts[0].user_id
    conditions = (
        Transaction.user_id == user_id,
        Transaction.voided_at.is_(None),
        Transaction.effective_date <= cutoff,
    )
    outgoing = {
        account_id: Decimal(total)
        for account_id, total in db.execute(
            select(
                Transaction.account_id,
                func.sum(
                    case(
                        (Transaction.kind == "income", Transaction.amount),
                        else_=-Transaction.amount,
                    )
                ),
            )
            .where(*conditions)
            .group_by(Transaction.account_id)
        ).all()
    }
    incoming = {
        account_id: Decimal(total)
        for account_id, total in db.execute(
            select(Transaction.destination_account_id, func.sum(Transaction.amount))
            .where(*conditions, Transaction.kind == "transfer")
            .group_by(Transaction.destination_account_id)
        ).all()
    }
    return {
        a.id: a.opening_balance + outgoing.get(a.id, Decimal(0)) + incoming.get(a.id, Decimal(0))
        for a in accounts
    }


def suggested_transfer(
    row: StatementRow, accounts: list[Account], statement_account: str
) -> tuple[bool, str | None]:
    text = (
        unicodedata.normalize("NFKD", row.description.casefold()).encode("ascii", "ignore").decode()
    )
    possible = [a for a in accounts if a.id != statement_account and a.archived_at is None]
    if "pagamento de fatura" in text or "invoice payment" in text:
        possible = [a for a in possible if a.account_type == "credit_card"]
    elif "criptomoeda" in text or "crypto" in text:
        possible = [a for a in possible if re.search("cripto|crypto", a.name, re.I)]
    elif "etf" in text:
        possible = [a for a in possible if "invest" in a.name.casefold()]
    elif "aplicacao rdb" in text:
        possible = [a for a in possible if re.search("box|caix|rdb", a.name, re.I)]
    else:
        return False, None
    return True, possible[0].id if len(possible) == 1 else None


def candidate(
    transaction: Transaction,
    anchor: str,
    accounts: dict[str, Account],
    categories: dict[str, Category],
    reasons: list[str],
    linked: bool,
) -> MatchCandidate:
    destination = accounts.get(transaction.destination_account_id or "")
    category = categories.get(transaction.category_id or "")
    return MatchCandidate(
        transaction_id=transaction.id,
        description=transaction.description,
        effective_date=transaction.effective_date,
        amount=transaction.amount,
        kind=cast(Literal["income", "expense", "transfer"], transaction.kind),
        account_id=transaction.account_id,
        account_name=accounts[transaction.account_id].name,
        destination_account_id=transaction.destination_account_id,
        destination_account_name=destination.name if destination else None,
        category_name=category.name if category else None,
        ledger_account_id=anchor,
        reasons=reasons,
        already_linked=linked,
    )


def creation_values(
    db: Session, review: ImportReview, row: StatementRow, decision: ReviewDecision
) -> TransactionValues:
    anchor = decision.account_id or review.account_id
    active_account(db, review.user_id, anchor)
    kind = decision.kind or row.kind
    if kind != "transfer" and kind != row.kind:
        raise HTTPException(422, "The transaction must preserve the statement direction")
    source = (
        decision.counterparty_account_id if kind == "transfer" and row.kind == "income" else anchor
    )
    destination = (
        (anchor if row.kind == "income" else decision.counterparty_account_id)
        if kind == "transfer"
        else None
    )
    try:
        values = TransactionValues(
            kind=kind,
            account_id=source or "",
            destination_account_id=destination,
            category_id=decision.category_id if kind != "transfer" else None,
            amount=row.amount,
            effective_date=row.effective_date,
            description=decision.description
            if decision.description is not None
            else row.description[:160],
        )
        validate_transaction_references(db, review.user_id, values)
    except ValueError as error:
        raise HTTPException(
            422, "Choose a valid category and accounts for each transaction"
        ) from error
    if values.description.isspace():
        raise HTTPException(422, "Enter a transaction description")
    statement_account = active_account(db, review.user_id, review.account_id)
    if active_account(db, review.user_id, anchor).currency != statement_account.currency:
        raise HTTPException(422, "Row accounts must use the statement currency")
    return values


def build_review(db: Session, review: ImportReview) -> ReviewResponse:
    rows = parsed_rows(review)
    decisions = review_decisions(review, rows)
    meta = metadata(review, rows)
    accounts = {
        a.id: a for a in db.scalars(select(Account).where(Account.user_id == review.user_id))
    }
    categories = {
        c.id: c for c in db.scalars(select(Category).where(Category.user_id == review.user_id))
    }
    resolutions = list(
        db.scalars(select(ImportRowResolution).where(ImportRowResolution.user_id == review.user_id))
    )
    resolved = {r.row_key: r for r in resolutions}
    linked_legs = {
        (r.transaction_id, r.ledger_account_id): r.row_key for r in resolutions if r.transaction_id
    }
    transactions = list(
        db.scalars(
            select(Transaction).where(
                Transaction.user_id == review.user_id,
                or_(
                    and_(
                        Transaction.effective_date >= meta.start_date - timedelta(days=2),
                        Transaction.effective_date <= meta.end_date + timedelta(days=2),
                    ),
                    Transaction.client_request_id.in_([row.row_key for row in rows]),
                    Transaction.id.in_([d.transaction_id for d in decisions if d.transaction_id]),
                ),
            )
        )
    )
    tx_by_id = {t.id: t for t in transactions}
    # Include linked transactions even if their dates were edited outside the period.
    resolved_ids = {
        r.transaction_id
        for r in resolutions
        if r.row_key in {row.row_key for row in rows} and r.transaction_id
    }
    if resolved_ids:
        tx_by_id.update(
            {
                t.id: t
                for t in db.scalars(
                    select(Transaction).where(
                        Transaction.user_id == review.user_id,
                        Transaction.id.in_(resolved_ids),
                    )
                )
            }
        )
    rules = {
        (r.kind, r.merchant_key): r.category_id
        for r in db.scalars(
            select(ImportCategoryRule).where(ImportCategoryRule.user_id == review.user_id)
        )
    }
    result = []
    linked_ids = set()
    projections: dict[str, Decimal] = {}
    cutoff = meta.balance_date or meta.end_date
    for row, decision in zip(rows, decisions, strict=True):
        resolution = resolved.get(row.row_key)
        legacy = next((t for t in transactions if t.client_request_id == row.row_key), None)
        resolved_tx = tx_by_id.get(resolution.transaction_id or "") if resolution else legacy
        resolved_action = resolution.action if resolution else ("create" if legacy else None)
        warning = None
        if resolution and resolution.transaction_id and resolved_tx is None:
            warning = "The linked transaction is unavailable."
        elif resolved_tx is not None:
            linked_ids.add(resolved_tx.id)
            anchor = resolution.ledger_account_id if resolution else review.account_id
            if (
                resolved_tx.voided_at is not None
                or abs(effect(resolved_tx, anchor)) != row.amount
                or (effect(resolved_tx, anchor) > 0) != (row.kind == "income")
                or resolved_tx.effective_date != row.effective_date
            ):
                warning = (
                    "The linked transaction differs in date, amount, direction, or status. "
                    "Review it in Transactions."
                )
        anchor = decision.account_id or review.account_id
        matches = []
        for tx in transactions:
            if (
                tx.voided_at is not None
                or tx.amount != row.amount
                or (
                    abs((tx.effective_date - row.effective_date).days) > 2
                    and tx.id != decision.transaction_id
                )
            ):
                continue
            candidate_anchor: str | None = anchor
            same_account = anchor in (tx.account_id, tx.destination_account_id)
            if not same_account:
                candidate_anchor = (
                    tx.destination_account_id
                    if tx.kind == "transfer" and row.kind == "income"
                    else tx.account_id
                )
            if not candidate_anchor or (effect(tx, candidate_anchor) > 0) != (row.kind == "income"):
                continue
            if accounts[candidate_anchor].currency != accounts[review.account_id].currency:
                continue
            reasons = [
                "Same amount",
                "Same date"
                if tx.effective_date == row.effective_date
                else (
                    "Date within 2 days"
                    if abs((tx.effective_date - row.effective_date).days) <= 2
                    else "Different date — verify this movement"
                ),
                "Same account"
                if same_account
                else "Different account — confirm account assignment",
            ]
            if merchant_key(tx.description) == merchant_key(row.description):
                reasons.append("Same description")
            owner = linked_legs.get((tx.id, candidate_anchor))
            matches.append(
                candidate(
                    tx,
                    candidate_anchor,
                    accounts,
                    categories,
                    reasons,
                    owner is not None and owner != row.row_key,
                )
            )
        matches.sort(
            key=lambda m: (
                m.ledger_account_id != anchor,
                m.already_linked,
                m.effective_date != row.effective_date,
                m.transaction_id,
            )
        )
        suggested_category = rules.get((row.kind, merchant_key(row.description)))
        if (
            suggested_category not in categories
            or categories[suggested_category].archived_at is not None
        ):
            suggested_category = None
        transfer, other = suggested_transfer(row, list(accounts.values()), review.account_id)
        selected_tx = tx_by_id.get(decision.transaction_id or "")
        invalid_selection = (
            decision.action == "link"
            and decision.transaction_id
            and (
                selected_tx is None
                or selected_tx.voided_at is not None
                or selected_tx.amount != row.amount
                or abs(effect(selected_tx, anchor)) != row.amount
                or (effect(selected_tx, anchor) > 0) != (row.kind == "income")
            )
        )
        result.append(
            ReviewRow(
                **row.model_dump(exclude={"suggested_category_id"}),
                suggested_category_id=suggested_category,
                candidates=matches,
                suggested_kind="transfer" if transfer else row.kind,
                suggested_counterparty_account_id=other,
                resolved_action=cast(Literal["create", "link", "skip"] | None, resolved_action),
                resolved_transaction_id=resolved_tx.id if resolved_tx else None,
                resolution_warning=warning,
                invalid_transaction_id=decision.transaction_id if invalid_selection else None,
            )
        )
        if resolved_action is None and decision.action == "create" and row.effective_date <= cutoff:
            # Only valid, complete registrations contribute to the projected balances.
            try:
                values = creation_values(db, review, row, decision)
            except HTTPException:
                continue
            projections[values.account_id] = projections.get(values.account_id, Decimal(0)) + (
                row.amount if values.kind == "income" else -row.amount
            )
            if values.destination_account_id:
                projections[values.destination_account_id] = (
                    projections.get(values.destination_account_id, Decimal(0)) + row.amount
                )
        elif decision.action == "link" and decision.transaction_id:
            linked_ids.add(decision.transaction_id)
    opening = balance_at(db, list(accounts.values()), meta.start_date - timedelta(days=1))[
        review.account_id
    ]
    balances = balance_at(db, list(accounts.values()), cutoff)
    balance_rows = []
    for a in accounts.values():
        projected = balances[a.id] + projections.get(a.id, Decimal(0))
        actual = meta.closing_balance if a.id == review.account_id else None
        balance_rows.append(
            ReviewBalance(
                account_id=a.id,
                account_name=a.name,
                balance_date=cutoff,
                current_balance=balances[a.id],
                projected_balance=projected,
                statement_closing_balance=actual,
                difference=actual - projected if actual is not None else None,
            )
        )
    unmatched = [
        candidate(tx, review.account_id, accounts, categories, [], False)
        for tx in transactions
        if tx.voided_at is None
        and tx.id not in linked_ids
        and review.account_id in (tx.account_id, tx.destination_account_id)
        and meta.start_date <= tx.effective_date <= meta.end_date
    ]
    return ReviewResponse(
        id=review.id,
        filename=review.filename,
        account_id=review.account_id,
        updated_at=review.updated_at,
        version=review.version,
        rows=result,
        decisions=decisions,
        metadata=meta,
        balances=balance_rows,
        opening_lume_balance=opening,
        opening_difference=meta.inferred_opening_balance - opening
        if meta.inferred_opening_balance is not None
        else None,
        unmatched_transactions=unmatched,
    )
