from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lume.accounts.models import Account
from lume.auth.dependencies import CsrfAuth, CurrentAuth
from lume.categories.models import Category
from lume.core.database import get_db
from lume.imports.models import ImportCategoryRule, ImportReview, ImportRowResolution
from lume.imports.parser import merchant_key
from lume.imports.review_schemas import (
    MatchCandidate,
    ReviewApplyResponse,
    ReviewDecision,
    ReviewResponse,
    ReviewSummary,
    ReviewUpdate,
)
from lume.imports.review_service import (
    active_account,
    build_review,
    candidate,
    creation_values,
    effect,
    new_review,
    parsed_rows,
    validate_decisions,
)
from lume.imports.schemas import StatementPreviewRequest
from lume.transactions.models import Transaction
from lume.users.models import User

router = APIRouter(prefix="/api/v1/imports/reviews", tags=["imports"])


def owned_review(db: Session, user_id: str, review_id: str, lock: bool = False) -> ImportReview:
    if lock:
        # Serialize imports for this owner, including two overlapping statement files.
        db.scalar(select(User).where(User.id == user_id).with_for_update())
    query = select(ImportReview).where(
        ImportReview.user_id == user_id, ImportReview.id == review_id
    )
    review = db.scalar(query.with_for_update() if lock else query)
    if review is None:
        raise HTTPException(404, "Statement review not found")
    return review


def save_decisions(review: ImportReview, payload: ReviewUpdate) -> None:
    if review.version != payload.version:
        raise HTTPException(409, "This review changed in another tab. Reopen it before saving.")
    validate_decisions(parsed_rows(review), payload.decisions)
    review.decisions = [d.model_dump(mode="json") for d in payload.decisions]
    review.version += 1


@router.get("", response_model=list[ReviewSummary])
def list_reviews(auth: CurrentAuth, db: Annotated[Session, Depends(get_db)]) -> list[ImportReview]:
    return list(
        db.scalars(
            select(ImportReview)
            .where(ImportReview.user_id == auth.user.id)
            .order_by(ImportReview.updated_at.desc())
            .limit(50)
        )
    )


@router.post("", response_model=ReviewResponse, status_code=201)
def create_review(
    payload: StatementPreviewRequest, auth: CsrfAuth, db: Annotated[Session, Depends(get_db)]
) -> ReviewResponse:
    db.scalar(select(User).where(User.id == auth.user.id).with_for_update())
    review = new_review(db, auth.user.id, payload)
    db.commit()
    return build_review(db, review)


@router.get("/{review_id}", response_model=ReviewResponse)
def get_review(
    review_id: str, auth: CurrentAuth, db: Annotated[Session, Depends(get_db)]
) -> ReviewResponse:
    return build_review(db, owned_review(db, auth.user.id, review_id))


@router.put("/{review_id}", response_model=ReviewResponse)
def update_review(
    review_id: str, payload: ReviewUpdate, auth: CsrfAuth, db: Annotated[Session, Depends(get_db)]
) -> ReviewResponse:
    review = owned_review(db, auth.user.id, review_id, lock=True)
    save_decisions(review, payload)
    db.commit()
    return build_review(db, review)


@router.delete("/{review_id}", status_code=204)
def delete_review(
    review_id: str, auth: CsrfAuth, db: Annotated[Session, Depends(get_db)]
) -> Response:
    review = owned_review(db, auth.user.id, review_id, lock=True)
    db.delete(review)
    db.commit()
    return Response(status_code=204)


@router.get("/{review_id}/candidates", response_model=list[MatchCandidate])
def search_candidates(
    review_id: str,
    auth: CurrentAuth,
    db: Annotated[Session, Depends(get_db)],
    row_key: str,
    search: Annotated[str, Query(max_length=100)] = "",
) -> list[MatchCandidate]:
    review = owned_review(db, auth.user.id, review_id)
    row = next((r for r in parsed_rows(review) if r.row_key == row_key), None)
    if row is None:
        raise HTTPException(404, "Statement row not found")
    accounts = {a.id: a for a in db.scalars(select(Account).where(Account.user_id == auth.user.id))}
    categories = {
        c.id: c for c in db.scalars(select(Category).where(Category.user_id == auth.user.id))
    }
    linked = {
        (r.transaction_id, r.ledger_account_id): r.row_key
        for r in db.scalars(
            select(ImportRowResolution).where(ImportRowResolution.user_id == auth.user.id)
        )
    }
    query = select(Transaction).where(
        Transaction.user_id == auth.user.id,
        Transaction.voided_at.is_(None),
        Transaction.amount == row.amount,
    )
    if search:
        query = query.where(Transaction.description.contains(search, autoescape=True))
    matches = []
    for tx in db.scalars(query.order_by(Transaction.effective_date.desc(), Transaction.id.desc())):
        anchor: str | None = review.account_id
        if anchor not in (tx.account_id, tx.destination_account_id):
            anchor = (
                tx.destination_account_id
                if tx.kind == "transfer" and row.kind == "income"
                else tx.account_id
            )
        if not anchor or (effect(tx, anchor) > 0) != (row.kind == "income"):
            continue
        if accounts[anchor].currency != accounts[review.account_id].currency:
            continue
        owner = linked.get((tx.id, anchor))
        matches.append(
            candidate(
                tx,
                anchor,
                accounts,
                categories,
                ["Same amount", "Search result — check date and accounts"],
                owner is not None and owner != row.row_key,
            )
        )
        if len(matches) == 50:
            break
    return matches


def remember_category(
    db: Session, user_id: str, row_kind: str, description: str, decision: ReviewDecision
) -> None:
    if not decision.remember_category or decision.kind == "transfer" or not decision.category_id:
        return
    key = merchant_key(description)
    rule = db.scalar(
        select(ImportCategoryRule).where(
            ImportCategoryRule.user_id == user_id,
            ImportCategoryRule.kind == row_kind,
            ImportCategoryRule.merchant_key == key,
        )
    )
    if rule is None:
        db.add(
            ImportCategoryRule(
                user_id=user_id, kind=row_kind, merchant_key=key, category_id=decision.category_id
            )
        )
    else:
        rule.category_id = decision.category_id


@router.post("/{review_id}/apply", response_model=ReviewApplyResponse)
def apply_review(
    review_id: str, payload: ReviewUpdate, auth: CsrfAuth, db: Annotated[Session, Depends(get_db)]
) -> ReviewApplyResponse:
    review = owned_review(db, auth.user.id, review_id, lock=True)
    active_account(db, auth.user.id, review.account_id)
    save_decisions(review, payload)
    preview = build_review(db, review)
    rows = {r.row_key: r for r in preview.rows}
    created = linked = ignored = pending = 0
    try:
        for decision in payload.decisions:
            row = rows[decision.row_key]
            if row.resolved_action is not None:
                continue
            if decision.action == "pending":
                pending += 1
                continue
            anchor = decision.account_id or review.account_id
            account = active_account(db, auth.user.id, anchor)
            if account.currency != active_account(db, auth.user.id, review.account_id).currency:
                raise HTTPException(422, "Row accounts must use the statement currency")
            tx = None
            if decision.action == "create":
                nearby = [m for m in row.candidates if m.ledger_account_id == anchor]
                if nearby and not decision.allow_possible_match:
                    raise HTTPException(
                        422, "Review the possible match or confirm a separate transaction"
                    )
                values = creation_values(db, review, row, decision)
                tx = Transaction(
                    user_id=auth.user.id, client_request_id=row.row_key, **values.model_dump()
                )
                db.add(tx)
                db.flush()
                remember_category(db, auth.user.id, row.kind, row.description, decision)
                created += 1
            elif decision.action == "link":
                tx = db.scalar(
                    select(Transaction)
                    .where(
                        Transaction.id == decision.transaction_id,
                        Transaction.user_id == auth.user.id,
                    )
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if tx is None or tx.voided_at is not None:
                    raise HTTPException(422, "Choose an available transaction to link")
                signed = effect(tx, anchor)
                if abs(signed) != row.amount or (signed > 0) != (row.kind == "income"):
                    raise HTTPException(
                        422, "Linked transaction must match the amount, account, and direction"
                    )
                linked += 1
            else:
                ignored += 1
            if tx is not None and db.scalar(
                select(ImportRowResolution.id).where(
                    ImportRowResolution.user_id == auth.user.id,
                    ImportRowResolution.transaction_id == tx.id,
                    ImportRowResolution.ledger_account_id == anchor,
                )
            ):
                raise HTTPException(
                    409,
                    "This transaction is already linked to another statement row for this account",
                )
            db.add(
                ImportRowResolution(
                    user_id=auth.user.id,
                    row_key=row.row_key,
                    statement_account_id=review.account_id,
                    ledger_account_id=anchor,
                    transaction_id=tx.id if tx else None,
                    action=decision.action,
                    original_description=row.description,
                )
            )
            db.flush()
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            409, "A statement row or transaction was already reconciled. Reopen the review."
        ) from error
    return ReviewApplyResponse(
        created=created,
        linked=linked,
        ignored=ignored,
        pending=pending,
        review=build_review(db, review),
    )
