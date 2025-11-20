import enum
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.contact_card import ContactCard
from app.models.lead import Lead, LeadSource, LeadStatus
from app.schemas.domain import (
    AppointmentSummary,
    ContactCardBase,
    LeadDetail,
    LeadResponse,
)
from app.schemas.responses import APIResponse, ErrorCodes, create_error_response
from app.services.domain_entities import ensure_contact_card_and_lead
from app.services.domain_events import emit_domain_event
from pydantic import BaseModel, Field, validator

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


@router.get("/{lead_id}", response_model=APIResponse[LeadResponse])
@require_role("exec", "manager", "csr", "rep")
async def get_lead(
    request: Request,
    lead_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[LeadDetail]:
    """
    Retrieve a lead with its contact card reference and upcoming appointments.
    """

    tenant_id = getattr(request.state, "tenant_id", None)

    lead: Lead | None = (
        db.query(Lead)
        .options(
            selectinload(Lead.contact_card),
            selectinload(Lead.appointments),
        )
        .filter(Lead.id == lead_id, Lead.company_id == tenant_id)
        .first()
    )

    if not lead:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Lead not found",
                details={"lead_id": lead_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )

    lead_payload = LeadDetail.from_orm(lead)
    contact_payload = None
    if lead.contact_card:
        contact_payload = ContactCardBase.from_orm(lead.contact_card)

    upcoming_appointments = [
        AppointmentSummary.from_orm(appt) for appt in sorted(lead.appointments, key=lambda item: item.scheduled_start)
    ]

    response_payload = lead_payload.copy(
        update={
            "tags": lead.tags or {},
        }
    )

    response = LeadResponse(
        lead=response_payload,
        contact=contact_payload,
        appointments=upcoming_appointments,
    )

    return APIResponse(data=response)


class LeadCreateBody(BaseModel):
    contact_card_id: Optional[str] = Field(None, description="Existing contact card identifier")
    primary_phone: Optional[str] = Field(None, description="Phone number used to resolve/create contact card")
    status: LeadStatus = Field(LeadStatus.NEW, description="Lead status")
    source: LeadSource = Field(LeadSource.INBOUND_CALL, description="Lead source")
    campaign: Optional[str] = None
    pipeline_stage: Optional[str] = None
    priority: Optional[str] = None
    score: Optional[int] = None
    tags: Optional[dict] = None

    @validator("primary_phone")
    def normalize_phone(cls, value: Optional[str]) -> Optional[str]:
        if value:
            return value.strip()
        return value


class LeadUpdateBody(BaseModel):
    status: Optional[LeadStatus] = None
    source: Optional[LeadSource] = None
    campaign: Optional[str] = None
    pipeline_stage: Optional[str] = None
    priority: Optional[str] = None
    score: Optional[int] = None
    tags: Optional[dict] = None
    last_contacted_at: Optional[datetime] = None
    last_qualified_at: Optional[datetime] = None


@router.post("", response_model=APIResponse[LeadResponse])
@require_role("exec", "manager", "csr")
async def create_lead(
    request: Request,
    payload: LeadCreateBody,
    db: Session = Depends(get_db),
) -> APIResponse[LeadResponse]:
    tenant_id = getattr(request.state, "tenant_id", None)
    contact_card_id = payload.contact_card_id
    primary_phone = payload.primary_phone

    if not contact_card_id and not primary_phone:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code=ErrorCodes.MISSING_REQUIRED_FIELD,
                message="Either contact_card_id or primary_phone must be provided",
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )

    if contact_card_id:
        contact = (
            db.query(ContactCard)
            .filter(ContactCard.id == contact_card_id, ContactCard.company_id == tenant_id)
            .first()
        )
        if not contact:
            raise HTTPException(
                status_code=404,
                detail=create_error_response(
                    error_code=ErrorCodes.NOT_FOUND,
                    message="Contact card not found",
                    details={"contact_card_id": contact_card_id},
                    request_id=getattr(request.state, "trace_id", None),
                ).dict(),
            )
    else:
        contact, _ = ensure_contact_card_and_lead(
            db,
            company_id=tenant_id,
            phone_number=primary_phone,
        )

    lead = Lead(
        company_id=tenant_id,
        contact_card_id=contact.id,
        status=payload.status,
        source=payload.source,
        campaign=payload.campaign,
        pipeline_stage=payload.pipeline_stage,
        priority=payload.priority,
        score=payload.score,
        tags=payload.tags,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    response = LeadResponse(
        lead=LeadDetail.from_orm(lead),
        contact=ContactCardBase.from_orm(contact),
        appointments=[],
    )

    emit_domain_event(
        event_name="lead.created",
        tenant_id=tenant_id,
        lead_id=lead.id,
        payload={
            "lead_id": lead.id,
            "company_id": lead.company_id,
            "contact_card_id": lead.contact_card_id,
            "status": lead.status.value,
            "source": lead.source.value,
            "campaign": lead.campaign,
            "pipeline_stage": lead.pipeline_stage,
        },
    )

    return APIResponse(data=response)


@router.patch("/{lead_id}", response_model=APIResponse[LeadResponse])
@require_role("exec", "manager", "csr")
async def update_lead(
    request: Request,
    lead_id: str,
    payload: LeadUpdateBody,
    db: Session = Depends(get_db),
) -> APIResponse[LeadResponse]:
    tenant_id = getattr(request.state, "tenant_id", None)

    lead: Lead | None = (
        db.query(Lead)
        .options(
            selectinload(Lead.contact_card),
            selectinload(Lead.appointments),
        )
        .filter(Lead.id == lead_id, Lead.company_id == tenant_id)
        .first()
    )

    if not lead:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Lead not found",
                details={"lead_id": lead_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )

    update_fields = {}
    for field in ["status", "source", "campaign", "pipeline_stage", "priority", "score", "tags", "last_contacted_at", "last_qualified_at"]:
        value = getattr(payload, field)
        if value is not None:
            setattr(lead, field, value)
            if isinstance(value, enum.Enum):
                update_fields[field] = value.value
            elif isinstance(value, datetime):
                update_fields[field] = value.isoformat()
            else:
                update_fields[field] = value

    lead.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(lead)

    response = LeadResponse(
        lead=LeadDetail.from_orm(lead),
        contact=ContactCardBase.from_orm(lead.contact_card) if lead.contact_card else None,
        appointments=[AppointmentSummary.from_orm(appt) for appt in sorted(lead.appointments, key=lambda appt: appt.scheduled_start)],
    )

    emit_domain_event(
        event_name="lead.updated",
        tenant_id=tenant_id,
        lead_id=lead.id,
        payload={
            "lead_id": lead.id,
            "company_id": lead.company_id,
            "contact_card_id": lead.contact_card_id,
            "status": lead.status.value,
            "source": lead.source.value,
            "changes": update_fields,
        },
    )

    return APIResponse(data=response)

