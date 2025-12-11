import enum
from datetime import datetime
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_

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
from app.services.metrics_service import MetricsService
from app.schemas.metrics import MissedLeadsSelfResponse
from app.obs.logging import get_logger
from app.core.tenant import get_tenant_id
from pydantic import BaseModel, Field, validator

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])
logger = get_logger(__name__)


@router.get("/{lead_id}", response_model=APIResponse[LeadResponse])
@require_role("manager", "csr", "sales_rep")
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
@require_role("manager", "csr")
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
@require_role("manager", "csr")
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


@router.get("", response_model=APIResponse[dict])
@require_role("manager", "csr", "sales_rep")
async def list_leads(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status (comma-separated for multiple)"),
    rep_id: Optional[str] = Query(None, description="Filter by assigned rep ID"),
    source: Optional[str] = Query(None, description="Filter by source"),
    date_from: Optional[datetime] = Query(None, description="Filter leads created after this date"),
    date_to: Optional[datetime] = Query(None, description="Filter leads created before this date"),
    search: Optional[str] = Query(None, description="Search by name or phone number"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
) -> APIResponse[dict]:
    """
    List leads with optional filters.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    
    # Build query
    query = db.query(Lead).join(ContactCard).filter(Lead.company_id == tenant_id)
    
    # Filter by status (support comma-separated list)
    if status:
        status_list = [s.strip() for s in status.split(",")]
        try:
            status_enums = [LeadStatus(s.lower()) for s in status_list]
            query = query.filter(Lead.status.in_(status_enums))
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code=ErrorCodes.INVALID_REQUEST,
                    message=f"Invalid status value: {str(e)}",
                    details={"valid_statuses": [s.value for s in LeadStatus]},
                    request_id=getattr(request.state, "trace_id", None),
                ).dict(),
            )
    
    # Filter by rep_id
    if rep_id:
        query = query.filter(Lead.assigned_rep_id == rep_id)
    
    # Filter by source
    if source:
        try:
            source_enum = LeadSource(source.lower())
            query = query.filter(Lead.source == source_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code=ErrorCodes.INVALID_REQUEST,
                    message=f"Invalid source: {source}",
                    details={"valid_sources": [s.value for s in LeadSource]},
                    request_id=getattr(request.state, "trace_id", None),
                ).dict(),
            )
    
    # Filter by date range (on created_at)
    if date_from:
        query = query.filter(Lead.created_at >= date_from)
    if date_to:
        query = query.filter(Lead.created_at <= date_to)
    
    # Search by name or phone
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                ContactCard.first_name.ilike(search_term),
                ContactCard.last_name.ilike(search_term),
                ContactCard.primary_phone.ilike(search_term),
                ContactCard.secondary_phone.ilike(search_term),
            )
        )
    
    # Get total count before pagination
    total_count = query.count()
    
    # Apply pagination
    query = query.order_by(Lead.created_at.desc()).offset(offset).limit(limit)
    
    # Eager load contact cards
    leads = query.options(selectinload(Lead.contact_card)).all()
    
    # Build response items
    lead_items = []
    for lead in leads:
        contact = lead.contact_card
        contact_name = None
        if contact:
            name_parts = []
            if contact.first_name:
                name_parts.append(contact.first_name)
            if contact.last_name:
                name_parts.append(contact.last_name)
            contact_name = " ".join(name_parts) if name_parts else None
        
        lead_items.append({
            "lead_id": lead.id,
            "status": lead.status.value,
            "source": lead.source.value,
            "priority": lead.priority,
            "score": lead.score,
            "last_contacted_at": lead.last_contacted_at.isoformat() if lead.last_contacted_at else None,
            "contact": {
                "name": contact_name,
                "primary_phone": contact.primary_phone if contact else None,
                "city": contact.city if contact else None,
                "state": contact.state if contact else None,
            },
            "created_at": lead.created_at.isoformat(),
        })
    
    response = {
        "leads": lead_items,
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }
    
    return APIResponse(data=response)




from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_

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
@require_role("manager", "csr", "sales_rep")
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
@require_role("manager", "csr")
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
@require_role("manager", "csr")
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


@router.get("", response_model=APIResponse[dict])
@require_role("manager", "csr", "sales_rep")
async def list_leads(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status (comma-separated for multiple)"),
    rep_id: Optional[str] = Query(None, description="Filter by assigned rep ID"),
    source: Optional[str] = Query(None, description="Filter by source"),
    date_from: Optional[datetime] = Query(None, description="Filter leads created after this date"),
    date_to: Optional[datetime] = Query(None, description="Filter leads created before this date"),
    search: Optional[str] = Query(None, description="Search by name or phone number"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
) -> APIResponse[dict]:
    """
    List leads with optional filters.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    
    # Build query
    query = db.query(Lead).join(ContactCard).filter(Lead.company_id == tenant_id)
    
    # Filter by status (support comma-separated list)
    if status:
        status_list = [s.strip() for s in status.split(",")]
        try:
            status_enums = [LeadStatus(s.lower()) for s in status_list]
            query = query.filter(Lead.status.in_(status_enums))
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code=ErrorCodes.INVALID_REQUEST,
                    message=f"Invalid status value: {str(e)}",
                    details={"valid_statuses": [s.value for s in LeadStatus]},
                    request_id=getattr(request.state, "trace_id", None),
                ).dict(),
            )
    
    # Filter by rep_id
    if rep_id:
        query = query.filter(Lead.assigned_rep_id == rep_id)
    
    # Filter by source
    if source:
        try:
            source_enum = LeadSource(source.lower())
            query = query.filter(Lead.source == source_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code=ErrorCodes.INVALID_REQUEST,
                    message=f"Invalid source: {source}",
                    details={"valid_sources": [s.value for s in LeadSource]},
                    request_id=getattr(request.state, "trace_id", None),
                ).dict(),
            )
    
    # Filter by date range (on created_at)
    if date_from:
        query = query.filter(Lead.created_at >= date_from)
    if date_to:
        query = query.filter(Lead.created_at <= date_to)
    
    # Search by name or phone
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                ContactCard.first_name.ilike(search_term),
                ContactCard.last_name.ilike(search_term),
                ContactCard.primary_phone.ilike(search_term),
                ContactCard.secondary_phone.ilike(search_term),
            )
        )
    
    # Get total count before pagination
    total_count = query.count()
    
    # Apply pagination
    query = query.order_by(Lead.created_at.desc()).offset(offset).limit(limit)
    
    # Eager load contact cards
    leads = query.options(selectinload(Lead.contact_card)).all()
    
    # Build response items
    lead_items = []
    for lead in leads:
        contact = lead.contact_card
        contact_name = None
        if contact:
            name_parts = []
            if contact.first_name:
                name_parts.append(contact.first_name)
            if contact.last_name:
                name_parts.append(contact.last_name)
            contact_name = " ".join(name_parts) if name_parts else None
        
        lead_items.append({
            "lead_id": lead.id,
            "status": lead.status.value,
            "source": lead.source.value,
            "priority": lead.priority,
            "score": lead.score,
            "last_contacted_at": lead.last_contacted_at.isoformat() if lead.last_contacted_at else None,
            "contact": {
                "name": contact_name,
                "primary_phone": contact.primary_phone if contact else None,
                "city": contact.city if contact else None,
                "state": contact.state if contact else None,
            },
            "created_at": lead.created_at.isoformat(),
        })
    
    response = {
        "leads": lead_items,
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }
    
    return APIResponse(data=response)






def parse_date_param(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse ISO8601 date string to datetime.
    
    Handles both date-only (YYYY-MM-DD) and full ISO8601 formats.
    Returns None if date_str is None or empty.
    """
    if not date_str:
        return None
    try:
        # Try parsing as full ISO8601 datetime
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        try:
            # Try parsing as date-only (YYYY-MM-DD)
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            logger.warning(f"Invalid date format: {date_str}")
            return None


@router.get("/missed/self", response_model=APIResponse[MissedLeadsSelfResponse])
@require_role("csr", "manager")
async def get_leads_missed_self(
    request: Request,
    status: Optional[Literal["booked", "pending", "dead"]] = Query(None, description="Filter by status: booked, pending, or dead"),
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get paginated missed leads for CSR self.
    
    **Roles**: csr, manager
    
    **Query Parameters**:
    - `status`: Filter by status (booked, pending, dead) - optional
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: MissedLeadsSelfResponse with paginated missed leads.
    Uses Shunya booking/outcome for status, plus Otto's call/twilio interaction counts for attempt_count.
    """
    try:
        # Parse dates
        parsed_from = parse_date_param(date_from)
        parsed_to = parse_date_param(date_to)
        
        # Get CSR user ID from auth
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in request")
        
        # Instantiate metrics service
        metrics_service = MetricsService(db)
        
        # Call the service method
        response = await metrics_service.get_csr_missed_leads_self(
            csr_user_id=user_id,
            tenant_id=tenant_id,
            status=status,
            date_from=parsed_from,
            date_to=parsed_to
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get missed leads for CSR")
        raise HTTPException(status_code=500, detail="Failed to get missed leads")
