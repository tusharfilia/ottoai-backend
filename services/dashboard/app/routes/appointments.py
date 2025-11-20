import enum
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.appointment import Appointment, AppointmentOutcome, AppointmentStatus
from app.models.lead import Lead
from app.schemas.domain import AppointmentDetail, AppointmentResponse, ContactCardBase, LeadSummary
from app.schemas.responses import APIResponse, ErrorCodes, create_error_response
from app.services.domain_events import emit_domain_event

router = APIRouter(prefix="/api/v1/appointments", tags=["appointments"])


@router.get("/{appointment_id}", response_model=APIResponse[AppointmentResponse])
@require_role("exec", "manager", "csr", "rep")
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


@router.post("", response_model=APIResponse[AppointmentResponse])
@require_role("exec", "manager", "csr")
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
@require_role("exec", "manager", "csr", "rep")
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
    for field in ["scheduled_start", "scheduled_end", "status", "outcome", "assigned_rep_id", "location", "service_type", "notes", "external_id"]:
        value = getattr(payload, field)
        if value is not None:
            setattr(appointment, field, value)
            if isinstance(value, enum.Enum):
                change_log[field] = value.value
            elif isinstance(value, datetime):
                change_log[field] = value.isoformat()
            else:
                change_log[field] = value
    
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

