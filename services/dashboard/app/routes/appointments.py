import enum
from datetime import datetime, date, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_, or_, func

from app.database import get_db
from app.middleware.rbac import require_role
from app.core.tenant import get_tenant_id
from app.models.appointment import Appointment, AppointmentOutcome, AppointmentStatus
from app.models.lead import Lead
from app.models.task import Task, TaskStatus
from app.schemas.domain import AppointmentDetail, AppointmentResponse, ContactCardBase, LeadSummary
from app.schemas.appointments import AppointmentListItem, AppointmentListResponse
from app.schemas.responses import APIResponse, ErrorCodes, create_error_response
from app.services.domain_events import emit_domain_event

router = APIRouter(prefix="/api/v1/appointments", tags=["appointments"])


@router.get("/{appointment_id}", response_model=APIResponse[AppointmentResponse])
@require_role("manager", "csr", "sales_rep")
async def get_appointment(
    request: Request,
    appointment_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[AppointmentResponse]:
    """
    Retrieve an appointment with associated lead/contact context.
    """

    tenant_id = getattr(request.state, "tenant_id", None)

    appointment: Appointment | None = (
        db.query(Appointment)
        .options(
            selectinload(Appointment.lead),
            selectinload(Appointment.contact_card),
        )
        .filter(Appointment.id == appointment_id, Appointment.company_id == tenant_id)
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Appointment not found",
                details={"appointment_id": appointment_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )

    appointment_payload = AppointmentDetail.from_orm(appointment)
    lead_payload = LeadSummary.from_orm(appointment.lead) if appointment.lead else None
    contact_payload = ContactCardBase.from_orm(appointment.contact_card) if appointment.contact_card else None

    response = AppointmentResponse(
        appointment=appointment_payload,
        lead=lead_payload,
        contact=contact_payload,
    )

    return APIResponse(data=response)


class AppointmentCreateBody(BaseModel):
    lead_id: str = Field(..., description="Lead identifier")
    contact_card_id: Optional[str] = Field(None, description="Optional override contact card")
    scheduled_start: datetime = Field(..., description="Scheduled start timestamp")
    scheduled_end: Optional[datetime] = None
    status: AppointmentStatus = Field(AppointmentStatus.SCHEDULED, description="Appointment status")
    outcome: AppointmentOutcome = Field(AppointmentOutcome.PENDING, description="Appointment outcome")
    assigned_rep_id: Optional[str] = None
    location: Optional[str] = None
    service_type: Optional[str] = None
    notes: Optional[str] = None
    external_id: Optional[str] = None


class AppointmentUpdateBody(BaseModel):
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    status: Optional[AppointmentStatus] = None
    outcome: Optional[AppointmentOutcome] = None
    assigned_rep_id: Optional[str] = None
    location: Optional[str] = None
    service_type: Optional[str] = None
    notes: Optional[str] = None
    external_id: Optional[str] = None
    deal_size: Optional[float] = Field(None, description="Deal size in dollars (required when outcome=won)")


@router.get("", response_model=APIResponse[AppointmentListResponse])
@require_role("manager", "csr", "sales_rep")
async def list_appointments(
    request: Request,
    rep_id: Optional[str] = Query(None, description="Sales rep ID (defaults to authenticated user if rep)"),
    date: Optional[str] = Query(None, description="Date filter (ISO format YYYY-MM-DD, defaults to today)"),
    status: Optional[str] = Query(None, description="Filter by status (scheduled, confirmed, completed, cancelled, no_show)"),
    outcome: Optional[str] = Query(None, description="Filter by outcome (pending, won, lost, no_show, rescheduled)"),
    db: Session = Depends(get_db),
) -> APIResponse[AppointmentListResponse]:
    """
    List appointments for a rep (or all appointments for managers).
    
    For reps: defaults to authenticated user's appointments for today.
    For managers: can view all appointments, optionally filtered by rep_id.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "user_role", None)
    
    # Determine rep_id: use provided, or infer from auth context if rep
    if not rep_id and user_role == "sales_rep":
        rep_id = user_id
    elif not rep_id and user_role in ["manager", "csr"]:
        # Managers/CSRs can view all appointments if no rep_id specified
        rep_id = None
    
    # Parse date filter (default to today in UTC)
    if date:
        try:
            # Parse YYYY-MM-DD format
            filter_date = datetime.strptime(date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code=ErrorCodes.INVALID_REQUEST,
                    message="Invalid date format. Use YYYY-MM-DD",
                    details={"date": date},
                    request_id=getattr(request.state, "trace_id", None),
                ).dict(),
            )
    else:
        filter_date = datetime.utcnow().date()
    
    # Build query
    query = db.query(Appointment).filter(Appointment.company_id == tenant_id)
    
    # Filter by rep_id if provided
    if rep_id:
        query = query.filter(Appointment.assigned_rep_id == rep_id)
    
    # Filter by date (scheduled_start between start and end of day in UTC)
    day_start = datetime.combine(filter_date, datetime.min.time())
    day_end = datetime.combine(filter_date, datetime.max.time())
    query = query.filter(
        and_(
            Appointment.scheduled_start >= day_start,
            Appointment.scheduled_start < day_end + timedelta(days=1)
        )
    )
    
    # Filter by status
    if status:
        try:
            status_enum = AppointmentStatus(status.lower())
            query = query.filter(Appointment.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code=ErrorCodes.INVALID_REQUEST,
                    message=f"Invalid status: {status}",
                    details={"valid_statuses": [s.value for s in AppointmentStatus]},
                    request_id=getattr(request.state, "trace_id", None),
                ).dict(),
            )
    
    # Filter by outcome
    if outcome:
        try:
            outcome_enum = AppointmentOutcome(outcome.lower())
            query = query.filter(Appointment.outcome == outcome_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code=ErrorCodes.INVALID_REQUEST,
                    message=f"Invalid outcome: {outcome}",
                    details={"valid_outcomes": [o.value for o in AppointmentOutcome]},
                    request_id=getattr(request.state, "trace_id", None),
                ).dict(),
            )
    
    # Order by scheduled_start
    query = query.order_by(Appointment.scheduled_start.asc())
    
    # Eager load relationships
    appointments = query.options(
        selectinload(Appointment.contact_card),
        selectinload(Appointment.lead),
    ).all()
    
    # Build response items
    appointment_items = []
    for appointment in appointments:
        # Get customer name from contact card
        customer_name = None
        if appointment.contact_card:
            name_parts = []
            if appointment.contact_card.first_name:
                name_parts.append(appointment.contact_card.first_name)
            if appointment.contact_card.last_name:
                name_parts.append(appointment.contact_card.last_name)
            customer_name = " ".join(name_parts) if name_parts else None
        
        # Count pending tasks (cheap query)
        pending_tasks_count = None
        if appointment.id:
            pending_count = db.query(func.count(Task.id)).filter(
                Task.appointment_id == appointment.id,
                Task.company_id == tenant_id,
                Task.status.in_([TaskStatus.OPEN, TaskStatus.OVERDUE])
            ).scalar()
            pending_tasks_count = pending_count or 0
        
        # Determine if assigned to requesting user
        is_assigned_to_me = appointment.assigned_rep_id == user_id if user_id else False
        
        item = AppointmentListItem(
            appointment_id=appointment.id,
            lead_id=appointment.lead_id,
            contact_card_id=appointment.contact_card_id,
            customer_name=customer_name,
            address=appointment.location,
            scheduled_start=appointment.scheduled_start,
            scheduled_end=appointment.scheduled_end,
            status=appointment.status.value,
            outcome=appointment.outcome.value,
            service_type=appointment.service_type,
            is_assigned_to_me=is_assigned_to_me,
            deal_size=appointment.deal_size,
            pending_tasks_count=pending_tasks_count,
        )
        appointment_items.append(item)
    
    response = AppointmentListResponse(
        appointments=appointment_items,
        total=len(appointment_items),
        date=filter_date.isoformat(),
    )
    
    return APIResponse(data=response)


@router.post("", response_model=APIResponse[AppointmentResponse])
@require_role("manager", "csr")
async def create_appointment(
    request: Request,
    payload: AppointmentCreateBody,
    db: Session = Depends(get_db),
) -> APIResponse[AppointmentResponse]:
    tenant_id = getattr(request.state, "tenant_id", None)
    lead: Lead | None = (
        db.query(Lead)
        .options(selectinload(Lead.contact_card))
        .filter(Lead.id == payload.lead_id, Lead.company_id == tenant_id)
        .first()
    )
    if not lead:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Lead not found",
                details={"lead_id": payload.lead_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )

    contact_card_id = payload.contact_card_id or lead.contact_card_id
    if not contact_card_id:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code=ErrorCodes.VALIDATION_ERROR,
                message="Lead must be associated with a contact card",
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )

    appointment = Appointment(
        lead_id=lead.id,
        contact_card_id=contact_card_id,
        company_id=lead.company_id,
        assigned_rep_id=payload.assigned_rep_id,
        scheduled_start=payload.scheduled_start,
        scheduled_end=payload.scheduled_end,
        status=payload.status,
        outcome=payload.outcome,
        location=payload.location,
        service_type=payload.service_type,
        notes=payload.notes,
        external_id=payload.external_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    db.refresh(lead)
    
    # Auto-geocode address if location is provided
    if appointment.location and not (appointment.geo_lat and appointment.geo_lng):
        from app.services.geocoding_service import geocoding_service
        coordinates = geocoding_service.geocode_address(
            appointment.location,
            company_id=lead.company_id
        )
        if coordinates:
            appointment.geo_lat, appointment.geo_lng = coordinates
            # Use company defaults for geofence radius if not set
            from app.models.company import Company
            company = db.query(Company).filter(Company.id == lead.company_id).first()
            if company:
                appointment.geofence_radius_start = company.default_geofence_radius_start
                appointment.geofence_radius_stop = company.default_geofence_radius_stop
            db.commit()
            db.refresh(appointment)

    response = AppointmentResponse(
        appointment=AppointmentDetail.from_orm(appointment),
        lead=LeadSummary.from_orm(lead),
        contact=ContactCardBase.from_orm(appointment.contact_card) if appointment.contact_card else None,
    )

    emit_domain_event(
        event_name="appointment.created",
        tenant_id=lead.company_id,
        lead_id=lead.id,
        payload={
            "appointment_id": appointment.id,
            "lead_id": appointment.lead_id,
            "company_id": appointment.company_id,
            "status": appointment.status.value,
            "outcome": appointment.outcome.value,
            "scheduled_start": appointment.scheduled_start.isoformat(),
        },
    )

    return APIResponse(data=response)


@router.patch("/{appointment_id}", response_model=APIResponse[AppointmentResponse])
@require_role("manager", "csr", "sales_rep")
async def update_appointment(
    request: Request,
    appointment_id: str,
    payload: AppointmentUpdateBody,
    db: Session = Depends(get_db),
) -> APIResponse[AppointmentResponse]:
    tenant_id = getattr(request.state, "tenant_id", None)

    appointment: Appointment | None = (
        db.query(Appointment)
        .options(
            selectinload(Appointment.lead),
            selectinload(Appointment.contact_card),
        )
        .filter(Appointment.id == appointment_id, Appointment.company_id == tenant_id)
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Appointment not found",
                details={"appointment_id": appointment_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )

    change_log = {}
    outcome_changed_to_won = False
    
    # Process all fields first
    for field in ["scheduled_start", "scheduled_end", "status", "outcome", "assigned_rep_id", "location", "service_type", "notes", "external_id", "deal_size"]:
        value = getattr(payload, field)
        if value is not None:
            old_value = getattr(appointment, field, None)
            setattr(appointment, field, value)
            if isinstance(value, enum.Enum):
                change_log[field] = value.value
                if field == "outcome" and value == AppointmentOutcome.WON:
                    outcome_changed_to_won = True
            elif isinstance(value, datetime):
                change_log[field] = value.isoformat()
            else:
                change_log[field] = value
    
    # Handle outcome = won logic (after all fields are set)
    if outcome_changed_to_won:
        # Update appointment status to completed when outcome is won
        if appointment.status != AppointmentStatus.COMPLETED:
            appointment.status = AppointmentStatus.COMPLETED
            change_log["status"] = AppointmentStatus.COMPLETED.value
        
        # Sync deal_size to Lead if provided
        deal_size_to_sync = payload.deal_size if payload.deal_size is not None else appointment.deal_size
        if deal_size_to_sync is not None and appointment.lead:
            appointment.lead.deal_size = deal_size_to_sync
            appointment.lead.deal_status = "won"
            appointment.lead.closed_at = datetime.utcnow()
            from app.models.lead import LeadStatus
            if appointment.lead.status != LeadStatus.CLOSED_WON:
                appointment.lead.status = LeadStatus.CLOSED_WON
            change_log["lead_deal_size"] = deal_size_to_sync
    
    # Auto-geocode address if location changed and coordinates are missing
    if payload.location and (not appointment.geo_lat or not appointment.geo_lng):
        from app.services.geocoding_service import geocoding_service
        coordinates = geocoding_service.geocode_address(
            appointment.location,
            company_id=appointment.company_id
        )
        if coordinates:
            appointment.geo_lat, appointment.geo_lng = coordinates
            change_log["geo_lat"] = coordinates[0]
            change_log["geo_lng"] = coordinates[1]

    appointment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(appointment)

    response = AppointmentResponse(
        appointment=AppointmentDetail.from_orm(appointment),
        lead=LeadSummary.from_orm(appointment.lead) if appointment.lead else None,
        contact=ContactCardBase.from_orm(appointment.contact_card) if appointment.contact_card else None,
    )

    emit_domain_event(
        event_name="appointment.updated",
        tenant_id=appointment.company_id,
        lead_id=appointment.lead_id,
        payload={
            "appointment_id": appointment.id,
            "lead_id": appointment.lead_id,
            "company_id": appointment.company_id,
            "status": appointment.status.value,
            "outcome": appointment.outcome.value,
            "changes": change_log,
        },
    )

    return APIResponse(data=response)




from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_, or_, func

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.appointment import Appointment, AppointmentOutcome, AppointmentStatus
from app.models.lead import Lead
from app.models.task import Task, TaskStatus
from app.schemas.domain import AppointmentDetail, AppointmentResponse, ContactCardBase, LeadSummary
from app.schemas.appointments import AppointmentListItem, AppointmentListResponse
from app.schemas.responses import APIResponse, ErrorCodes, create_error_response
from app.services.domain_events import emit_domain_event

router = APIRouter(prefix="/api/v1/appointments", tags=["appointments"])


@router.get("/{appointment_id}", response_model=APIResponse[AppointmentResponse])
@require_role("manager", "csr", "sales_rep")
async def get_appointment(
    request: Request,
    appointment_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[AppointmentResponse]:
    """
    Retrieve an appointment with associated lead/contact context.
    """

    tenant_id = getattr(request.state, "tenant_id", None)

    appointment: Appointment | None = (
        db.query(Appointment)
        .options(
            selectinload(Appointment.lead),
            selectinload(Appointment.contact_card),
        )
        .filter(Appointment.id == appointment_id, Appointment.company_id == tenant_id)
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Appointment not found",
                details={"appointment_id": appointment_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )

    appointment_payload = AppointmentDetail.from_orm(appointment)
    lead_payload = LeadSummary.from_orm(appointment.lead) if appointment.lead else None
    contact_payload = ContactCardBase.from_orm(appointment.contact_card) if appointment.contact_card else None

    response = AppointmentResponse(
        appointment=appointment_payload,
        lead=lead_payload,
        contact=contact_payload,
    )

    return APIResponse(data=response)


class AppointmentCreateBody(BaseModel):
    lead_id: str = Field(..., description="Lead identifier")
    contact_card_id: Optional[str] = Field(None, description="Optional override contact card")
    scheduled_start: datetime = Field(..., description="Scheduled start timestamp")
    scheduled_end: Optional[datetime] = None
    status: AppointmentStatus = Field(AppointmentStatus.SCHEDULED, description="Appointment status")
    outcome: AppointmentOutcome = Field(AppointmentOutcome.PENDING, description="Appointment outcome")
    assigned_rep_id: Optional[str] = None
    location: Optional[str] = None
    service_type: Optional[str] = None
    notes: Optional[str] = None
    external_id: Optional[str] = None


class AppointmentUpdateBody(BaseModel):
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    status: Optional[AppointmentStatus] = None
    outcome: Optional[AppointmentOutcome] = None
    assigned_rep_id: Optional[str] = None
    location: Optional[str] = None
    service_type: Optional[str] = None
    notes: Optional[str] = None
    external_id: Optional[str] = None
    deal_size: Optional[float] = Field(None, description="Deal size in dollars (required when outcome=won)")


@router.get("", response_model=APIResponse[AppointmentListResponse])
@require_role("manager", "csr", "sales_rep")
async def list_appointments(
    request: Request,
    rep_id: Optional[str] = Query(None, description="Sales rep ID (defaults to authenticated user if rep)"),
    date: Optional[str] = Query(None, description="Date filter (ISO format YYYY-MM-DD, defaults to today)"),
    status: Optional[str] = Query(None, description="Filter by status (scheduled, confirmed, completed, cancelled, no_show)"),
    outcome: Optional[str] = Query(None, description="Filter by outcome (pending, won, lost, no_show, rescheduled)"),
    db: Session = Depends(get_db),
) -> APIResponse[AppointmentListResponse]:
    """
    List appointments for a rep (or all appointments for managers).
    
    For reps: defaults to authenticated user's appointments for today.
    For managers: can view all appointments, optionally filtered by rep_id.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "user_role", None)
    
    # Determine rep_id: use provided, or infer from auth context if rep
    if not rep_id and user_role == "sales_rep":
        rep_id = user_id
    elif not rep_id and user_role in ["manager", "csr"]:
        # Managers/CSRs can view all appointments if no rep_id specified
        rep_id = None
    
    # Parse date filter (default to today in UTC)
    if date:
        try:
            # Parse YYYY-MM-DD format
            filter_date = datetime.strptime(date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code=ErrorCodes.INVALID_REQUEST,
                    message="Invalid date format. Use YYYY-MM-DD",
                    details={"date": date},
                    request_id=getattr(request.state, "trace_id", None),
                ).dict(),
            )
    else:
        filter_date = datetime.utcnow().date()
    
    # Build query
    query = db.query(Appointment).filter(Appointment.company_id == tenant_id)
    
    # Filter by rep_id if provided
    if rep_id:
        query = query.filter(Appointment.assigned_rep_id == rep_id)
    
    # Filter by date (scheduled_start between start and end of day in UTC)
    day_start = datetime.combine(filter_date, datetime.min.time())
    day_end = datetime.combine(filter_date, datetime.max.time())
    query = query.filter(
        and_(
            Appointment.scheduled_start >= day_start,
            Appointment.scheduled_start < day_end + timedelta(days=1)
        )
    )
    
    # Filter by status
    if status:
        try:
            status_enum = AppointmentStatus(status.lower())
            query = query.filter(Appointment.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code=ErrorCodes.INVALID_REQUEST,
                    message=f"Invalid status: {status}",
                    details={"valid_statuses": [s.value for s in AppointmentStatus]},
                    request_id=getattr(request.state, "trace_id", None),
                ).dict(),
            )
    
    # Filter by outcome
    if outcome:
        try:
            outcome_enum = AppointmentOutcome(outcome.lower())
            query = query.filter(Appointment.outcome == outcome_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code=ErrorCodes.INVALID_REQUEST,
                    message=f"Invalid outcome: {outcome}",
                    details={"valid_outcomes": [o.value for o in AppointmentOutcome]},
                    request_id=getattr(request.state, "trace_id", None),
                ).dict(),
            )
    
    # Order by scheduled_start
    query = query.order_by(Appointment.scheduled_start.asc())
    
    # Eager load relationships
    appointments = query.options(
        selectinload(Appointment.contact_card),
        selectinload(Appointment.lead),
    ).all()
    
    # Build response items
    appointment_items = []
    for appointment in appointments:
        # Get customer name from contact card
        customer_name = None
        if appointment.contact_card:
            name_parts = []
            if appointment.contact_card.first_name:
                name_parts.append(appointment.contact_card.first_name)
            if appointment.contact_card.last_name:
                name_parts.append(appointment.contact_card.last_name)
            customer_name = " ".join(name_parts) if name_parts else None
        
        # Count pending tasks (cheap query)
        pending_tasks_count = None
        if appointment.id:
            pending_count = db.query(func.count(Task.id)).filter(
                Task.appointment_id == appointment.id,
                Task.company_id == tenant_id,
                Task.status.in_([TaskStatus.OPEN, TaskStatus.OVERDUE])
            ).scalar()
            pending_tasks_count = pending_count or 0
        
        # Determine if assigned to requesting user
        is_assigned_to_me = appointment.assigned_rep_id == user_id if user_id else False
        
        item = AppointmentListItem(
            appointment_id=appointment.id,
            lead_id=appointment.lead_id,
            contact_card_id=appointment.contact_card_id,
            customer_name=customer_name,
            address=appointment.location,
            scheduled_start=appointment.scheduled_start,
            scheduled_end=appointment.scheduled_end,
            status=appointment.status.value,
            outcome=appointment.outcome.value,
            service_type=appointment.service_type,
            is_assigned_to_me=is_assigned_to_me,
            deal_size=appointment.deal_size,
            pending_tasks_count=pending_tasks_count,
        )
        appointment_items.append(item)
    
    response = AppointmentListResponse(
        appointments=appointment_items,
        total=len(appointment_items),
        date=filter_date.isoformat(),
    )
    
    return APIResponse(data=response)


@router.post("", response_model=APIResponse[AppointmentResponse])
@require_role("manager", "csr")
async def create_appointment(
    request: Request,
    payload: AppointmentCreateBody,
    db: Session = Depends(get_db),
) -> APIResponse[AppointmentResponse]:
    tenant_id = getattr(request.state, "tenant_id", None)
    lead: Lead | None = (
        db.query(Lead)
        .options(selectinload(Lead.contact_card))
        .filter(Lead.id == payload.lead_id, Lead.company_id == tenant_id)
        .first()
    )
    if not lead:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Lead not found",
                details={"lead_id": payload.lead_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )

    contact_card_id = payload.contact_card_id or lead.contact_card_id
    if not contact_card_id:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code=ErrorCodes.VALIDATION_ERROR,
                message="Lead must be associated with a contact card",
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )

    appointment = Appointment(
        lead_id=lead.id,
        contact_card_id=contact_card_id,
        company_id=lead.company_id,
        assigned_rep_id=payload.assigned_rep_id,
        scheduled_start=payload.scheduled_start,
        scheduled_end=payload.scheduled_end,
        status=payload.status,
        outcome=payload.outcome,
        location=payload.location,
        service_type=payload.service_type,
        notes=payload.notes,
        external_id=payload.external_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    db.refresh(lead)
    
    # Auto-geocode address if location is provided
    if appointment.location and not (appointment.geo_lat and appointment.geo_lng):
        from app.services.geocoding_service import geocoding_service
        coordinates = geocoding_service.geocode_address(
            appointment.location,
            company_id=lead.company_id
        )
        if coordinates:
            appointment.geo_lat, appointment.geo_lng = coordinates
            # Use company defaults for geofence radius if not set
            from app.models.company import Company
            company = db.query(Company).filter(Company.id == lead.company_id).first()
            if company:
                appointment.geofence_radius_start = company.default_geofence_radius_start
                appointment.geofence_radius_stop = company.default_geofence_radius_stop
            db.commit()
            db.refresh(appointment)

    response = AppointmentResponse(
        appointment=AppointmentDetail.from_orm(appointment),
        lead=LeadSummary.from_orm(lead),
        contact=ContactCardBase.from_orm(appointment.contact_card) if appointment.contact_card else None,
    )

    emit_domain_event(
        event_name="appointment.created",
        tenant_id=lead.company_id,
        lead_id=lead.id,
        payload={
            "appointment_id": appointment.id,
            "lead_id": appointment.lead_id,
            "company_id": appointment.company_id,
            "status": appointment.status.value,
            "outcome": appointment.outcome.value,
            "scheduled_start": appointment.scheduled_start.isoformat(),
        },
    )

    return APIResponse(data=response)


@router.patch("/{appointment_id}", response_model=APIResponse[AppointmentResponse])
@require_role("manager", "csr", "sales_rep")
async def update_appointment(
    request: Request,
    appointment_id: str,
    payload: AppointmentUpdateBody,
    db: Session = Depends(get_db),
) -> APIResponse[AppointmentResponse]:
    tenant_id = getattr(request.state, "tenant_id", None)

    appointment: Appointment | None = (
        db.query(Appointment)
        .options(
            selectinload(Appointment.lead),
            selectinload(Appointment.contact_card),
        )
        .filter(Appointment.id == appointment_id, Appointment.company_id == tenant_id)
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Appointment not found",
                details={"appointment_id": appointment_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )

    change_log = {}
    outcome_changed_to_won = False
    
    # Process all fields first
    for field in ["scheduled_start", "scheduled_end", "status", "outcome", "assigned_rep_id", "location", "service_type", "notes", "external_id", "deal_size"]:
        value = getattr(payload, field)
        if value is not None:
            old_value = getattr(appointment, field, None)
            setattr(appointment, field, value)
            if isinstance(value, enum.Enum):
                change_log[field] = value.value
                if field == "outcome" and value == AppointmentOutcome.WON:
                    outcome_changed_to_won = True
            elif isinstance(value, datetime):
                change_log[field] = value.isoformat()
            else:
                change_log[field] = value
    
    # Handle outcome = won logic (after all fields are set)
    if outcome_changed_to_won:
        # Update appointment status to completed when outcome is won
        if appointment.status != AppointmentStatus.COMPLETED:
            appointment.status = AppointmentStatus.COMPLETED
            change_log["status"] = AppointmentStatus.COMPLETED.value
        
        # Sync deal_size to Lead if provided
        deal_size_to_sync = payload.deal_size if payload.deal_size is not None else appointment.deal_size
        if deal_size_to_sync is not None and appointment.lead:
            appointment.lead.deal_size = deal_size_to_sync
            appointment.lead.deal_status = "won"
            appointment.lead.closed_at = datetime.utcnow()
            from app.models.lead import LeadStatus
            if appointment.lead.status != LeadStatus.CLOSED_WON:
                appointment.lead.status = LeadStatus.CLOSED_WON
            change_log["lead_deal_size"] = deal_size_to_sync
    
    # Auto-geocode address if location changed and coordinates are missing
    if payload.location and (not appointment.geo_lat or not appointment.geo_lng):
        from app.services.geocoding_service import geocoding_service
        coordinates = geocoding_service.geocode_address(
            appointment.location,
            company_id=appointment.company_id
        )
        if coordinates:
            appointment.geo_lat, appointment.geo_lng = coordinates
            change_log["geo_lat"] = coordinates[0]
            change_log["geo_lng"] = coordinates[1]

    appointment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(appointment)

    response = AppointmentResponse(
        appointment=AppointmentDetail.from_orm(appointment),
        lead=LeadSummary.from_orm(appointment.lead) if appointment.lead else None,
        contact=ContactCardBase.from_orm(appointment.contact_card) if appointment.contact_card else None,
    )

    emit_domain_event(
        event_name="appointment.updated",
        tenant_id=appointment.company_id,
        lead_id=appointment.lead_id,
        payload={
            "appointment_id": appointment.id,
            "lead_id": appointment.lead_id,
            "company_id": appointment.company_id,
            "status": appointment.status.value,
            "outcome": appointment.outcome.value,
            "changes": change_log,
        },
    )

    return APIResponse(data=response)





class AppointmentAssignBody(BaseModel):
    rep_id: str = Field(..., description="Sales rep user ID to assign to")
    allow_double_booking: bool = Field(False, description="If True, skip double-booking conflict check")


@router.post("/{appointment_id}/assign", response_model=APIResponse[AppointmentDetail])
@require_role("csr", "manager")
async def assign_appointment_to_rep(
    request: Request,
    appointment_id: str,
    body: AppointmentAssignBody,
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
) -> APIResponse[AppointmentDetail]:
    """
    Assign an appointment to a sales rep.
    
    **Roles**: csr, manager
    
    **Path Parameters**:
    - `appointment_id`: Appointment ID
    
    **Request Body**:
    - `rep_id`: Sales rep user ID to assign to
    - `allow_double_booking`: If True, skip double-booking conflict check (default: False)
    
    **Returns**: Updated AppointmentDetail with assignment metadata.
    
    **Errors**:
    - 400: Appointment not found, booking_status != "booked", or double-booking conflict
    """
    try:
        # Get actor ID (CSR/manager performing assignment)
        actor_id = getattr(request.state, 'user_id', None)
        if not actor_id:
            raise HTTPException(status_code=401, detail="User ID not found in request")
        
        # Call dispatch service
        dispatch_service = AppointmentDispatchService(db)
        appointment = await dispatch_service.assign_appointment_to_rep(
            tenant_id=tenant_id,
            appointment_id=appointment_id,
            rep_id=body.rep_id,
            actor_id=actor_id,
            allow_double_booking=body.allow_double_booking
        )
        
        # Load assigned rep relationship for name
        db.refresh(appointment)
        if appointment.assigned_rep:
            # Rep name available via relationship
            pass
        
        # Convert to response schema
        response = AppointmentDetail.from_orm(appointment)
        
        return APIResponse(success=True, data=response)
    
    except AppointmentDispatchError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        from app.obs.logging import get_logger
        logger = get_logger(__name__)
        logger.error(f"Error assigning appointment: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to assign appointment: {str(e)}")

