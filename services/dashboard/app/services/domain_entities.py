"""
Shared helpers for managing first-class Otto domain entities.
"""
from __future__ import annotations

from typing import Tuple

from sqlalchemy.orm import Session

from app.models.contact_card import ContactCard
from app.models.lead import Lead, LeadSource, LeadStatus


def ensure_contact_card_and_lead(
    db: Session,
    *,
    company_id: str,
    phone_number: str,
) -> Tuple[ContactCard, Lead]:
    """
    Idempotently ensure a ContactCard and an active Lead exist for the given phone number.
    Used when new calls/events arrive without pre-existing CRM context.
    """

    contact = (
        db.query(ContactCard)
        .filter(
            ContactCard.company_id == company_id,
            ContactCard.primary_phone == phone_number,
        )
        .first()
    )

    if not contact:
        contact = ContactCard(
            company_id=company_id,
            primary_phone=phone_number,
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)

    lead = (
        db.query(Lead)
        .filter(
            Lead.company_id == company_id,
            Lead.contact_card_id == contact.id,
        )
        .order_by(Lead.created_at.desc())
        .first()
    )

    if not lead or not lead.is_active():
        lead = Lead(
            company_id=company_id,
            contact_card_id=contact.id,
            status=LeadStatus.NEW,
            source=LeadSource.INBOUND_CALL,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

    return contact, lead











