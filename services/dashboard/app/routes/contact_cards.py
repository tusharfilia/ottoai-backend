from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.contact_card import ContactCard
from app.models.call import Call
from app.models.lead import Lead
from app.models.appointment import Appointment
from app.schemas.domain import ContactCardDetail, PropertyIntelligence
from app.schemas.responses import APIResponse, ErrorCodes, create_error_response
from app.tasks.property_intelligence_tasks import scrape_property_intelligence
from app.services.contact_card_assembler import contact_card_assembler

router = APIRouter(prefix="/api/v1/contact-cards", tags=["contact-cards"])


@router.get("/{contact_id}", response_model=APIResponse[ContactCardDetail])
@require_role("manager", "csr", "sales_rep")
async def get_contact_card(
    request: Request,
    contact_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[ContactCardDetail]:
    """
    Retrieve a contact card and associated lead/appointment context for the tenant.
    """

    tenant_id = getattr(request.state, "tenant_id", None)

    contact: ContactCard | None = (
        db.query(ContactCard)
        .options(
            selectinload(ContactCard.leads),
            selectinload(ContactCard.appointments),
            selectinload(ContactCard.calls),
        )
        .filter(ContactCard.id == contact_id, ContactCard.company_id == tenant_id)
        .first()
    )

    if not contact:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Contact card not found",
                details={"contact_id": contact_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )

    # Use assembler to build complete Contact Card Detail
    payload = contact_card_assembler.assemble_contact_card(
        db=db,
        contact=contact,
        company_id=tenant_id,
    )

    return APIResponse(data=payload)


@router.get("/by-phone", response_model=APIResponse[ContactCardDetail])
@require_role("manager", "csr", "sales_rep")
async def get_contact_card_by_phone(
    request: Request,
    company_id: str,
    phone_number: str,
    db: Session = Depends(get_db),
) -> APIResponse[ContactCardDetail]:
    """
    Retrieve a contact card by phone number for the tenant.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    
    # Verify tenant matches company_id
    if tenant_id != company_id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code=ErrorCodes.FORBIDDEN,
                message="Company ID does not match tenant",
                details={"company_id": company_id, "tenant_id": tenant_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )

    contact: ContactCard | None = (
        db.query(ContactCard)
        .options(
            selectinload(ContactCard.leads),
            selectinload(ContactCard.appointments),
            selectinload(ContactCard.calls),
        )
        .filter(
            ContactCard.company_id == company_id,
            ContactCard.primary_phone == phone_number,
        )
        .first()
    )

    if not contact:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Contact card not found",
                details={"company_id": company_id, "phone_number": phone_number},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )

    # Use assembler to build complete Contact Card Detail
    payload = contact_card_assembler.assemble_contact_card(
        db=db,
        contact=contact,
        company_id=company_id,
    )

    return APIResponse(data=payload)


@router.post("/{contact_id}/refresh-property")
@require_role("manager", "csr", "sales_rep")
async def refresh_property_intelligence(
    request: Request,
    contact_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[dict]:
    """
    Manually trigger property intelligence scrape for a contact card.
    
    Returns 202 Accepted with job status.
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    contact: ContactCard | None = (
        db.query(ContactCard)
        .filter(ContactCard.id == contact_id, ContactCard.company_id == tenant_id)
        .first()
    )

    if not contact:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Contact card not found",
                details={"contact_id": contact_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )

    if not contact.address:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code=ErrorCodes.BAD_REQUEST,
                message="Contact card has no address",
                details={"contact_id": contact_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )

    # Enqueue scrape job
    scrape_property_intelligence.delay(contact_id)

    return APIResponse(
        data={"status": "queued", "contact_id": contact_id},
        status_code=202,
    )


