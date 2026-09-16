from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from lume.auth.dependencies import CsrfAuth, CurrentAuth
from lume.core.database import get_db
from lume.core.time import utc_now
from lume.recurring.models import RecurringOccurrence, RecurringTemplate
from lume.recurring.schemas import (
    OccurrenceAction,
    OccurrenceResponse,
    RecurringCreate,
    RecurringResponse,
    RecurringUpdate,
)
from lume.recurring.service import advance_template
from lume.transactions.models import Transaction
from lume.transactions.schemas import TransactionValues
from lume.transactions.service import validate_transaction_references

router = APIRouter(prefix="/api/v1/recurring-templates", tags=["recurring"])


def _owned_template(db: Session, user_id: str, template_id: str) -> RecurringTemplate:
    template = db.scalar(
        select(RecurringTemplate).where(
            RecurringTemplate.id == template_id,
            RecurringTemplate.user_id == user_id,
        )
    )
    if template is None:
        raise HTTPException(status_code=404, detail="Recurring template not found")
    return template


def _validate_references(db: Session, user_id: str, payload: RecurringCreate) -> None:
    values = TransactionValues(
        kind=payload.kind,
        account_id=payload.account_id,
        category_id=payload.category_id,
        amount=payload.amount,
        description=payload.description,
        notes=payload.notes,
        effective_date=payload.start_on,
    )
    try:
        validate_transaction_references(db, user_id, values)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("", response_model=list[RecurringResponse])
def list_templates(
    auth: CurrentAuth,
    db: Annotated[Session, Depends(get_db)],
) -> list[RecurringTemplate]:
    return list(
        db.scalars(
            select(RecurringTemplate)
            .where(
                RecurringTemplate.user_id == auth.user.id,
                RecurringTemplate.archived_at.is_(None),
            )
            .order_by(RecurringTemplate.next_due_on, RecurringTemplate.id)
        ).all()
    )


@router.post("", response_model=RecurringResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: RecurringCreate,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> RecurringTemplate:
    _validate_references(db, auth.user.id, payload)
    template = RecurringTemplate(
        user_id=auth.user.id,
        next_due_on=payload.start_on,
        anchor_month=payload.start_on.month,
        anchor_day=payload.start_on.day,
        active=True,
        **payload.model_dump(),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.patch("/{template_id}", response_model=RecurringResponse)
def update_template(
    template_id: str,
    payload: RecurringUpdate,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> RecurringTemplate:
    template = _owned_template(db, auth.user.id, template_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    if template.end_on is not None and template.end_on < template.start_on:
        raise HTTPException(status_code=422, detail="End date cannot precede start date")
    db.commit()
    db.refresh(template)
    return template


@router.post("/{template_id}/archive", response_model=RecurringResponse)
def archive_template(
    template_id: str,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> RecurringTemplate:
    template = _owned_template(db, auth.user.id, template_id)
    template.archived_at = utc_now()
    template.active = False
    db.commit()
    return template


def _prepare_occurrence(
    db: Session, auth: CsrfAuth, template_id: str, scheduled_for: date
) -> RecurringTemplate:
    template = _owned_template(db, auth.user.id, template_id)
    if template.archived_at is not None or not template.active:
        raise HTTPException(status_code=422, detail="Recurring template is inactive")
    if scheduled_for != template.next_due_on:
        raise HTTPException(status_code=409, detail="Occurrence is not the next expected date")
    existing = db.scalar(
        select(RecurringOccurrence).where(
            RecurringOccurrence.template_id == template.id,
            RecurringOccurrence.scheduled_for == scheduled_for,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Occurrence already handled")
    return template


@router.post(
    "/{template_id}/occurrences",
    response_model=OccurrenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_occurrence(
    template_id: str,
    payload: OccurrenceAction,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> RecurringOccurrence:
    template = _prepare_occurrence(db, auth, template_id, payload.scheduled_for)
    values = TransactionValues(
        kind=template.kind,
        account_id=template.account_id,
        category_id=template.category_id,
        amount=template.amount,
        description=template.description,
        notes=template.notes,
        effective_date=payload.scheduled_for,
    )
    try:
        validate_transaction_references(db, auth.user.id, values)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    transaction = Transaction(
        user_id=auth.user.id,
        **values.model_dump(),
    )
    db.add(transaction)
    db.flush()
    occurrence = RecurringOccurrence(
        template_id=template.id,
        user_id=auth.user.id,
        scheduled_for=payload.scheduled_for,
        status="recorded",
        transaction_id=transaction.id,
    )
    db.add(occurrence)
    advance_template(template)
    db.commit()
    db.refresh(occurrence)
    return occurrence


@router.post(
    "/{template_id}/occurrences/{scheduled_for}/skip",
    response_model=OccurrenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def skip_occurrence(
    template_id: str,
    scheduled_for: date,
    auth: CsrfAuth,
    db: Annotated[Session, Depends(get_db)],
) -> RecurringOccurrence:
    template = _prepare_occurrence(db, auth, template_id, scheduled_for)
    occurrence = RecurringOccurrence(
        template_id=template.id,
        user_id=auth.user.id,
        scheduled_for=scheduled_for,
        status="skipped",
    )
    db.add(occurrence)
    advance_template(template)
    db.commit()
    db.refresh(occurrence)
    return occurrence
