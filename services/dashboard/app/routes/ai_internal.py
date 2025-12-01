"""
Internal AI API endpoints for Shunya/UWC integration.

These endpoints provide read-only metadata for Ask Otto AI.
All endpoints require internal authentication and company isolation.
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.ai_internal_auth import get_ai_internal_context, AIInternalContext
from app.schemas.ai_internal import (
    AICallResponse,
    AIRepResponse,
    AICompanyResponse,
    AILeadResponse,
    AIContactSummary,
    AIAppointmentResponse,
    AIAppointmentSummary,
    AIServiceCatalogResponse,
)
from app.models.call import Call
from app.models.sales_rep import SalesRep
from app.models.company import Company
from app.models.lead import Lead
from app.models.contact_card import ContactCard
from app.models.appointment import Appointment
from app.models.service import Service
from app.models.user import User
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)

router = APIRouter(prefix="/internal/ai", tags=["AI Internal"])


def _check_company_access(entity_company_id: Optional[str], context: AIInternalContext) -> None:
    """Raise 404 if entity does not belong to the authenticated company."""
    if not entity_company_id or entity_company_id != context.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found"
        )


@router.get("/calls/{call_id}", response_model=AICallResponse)
def get_call_metadata(
    call_id: int,
    ctx: AIInternalContext = Depends(get_ai_internal_context),
    db: Session = Depends(get_db),
) -> AICallResponse:
    """
    Get call metadata for internal AI API.
    
    Returns call information including lead, contact, rep, and booking outcome.
    """
    call = db.query(Call).filter(Call.call_id == call_id).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call {call_id} not found"
        )
    
    _check_company_access(call.company_id, ctx)
    
    # Determine booking outcome
    booking_outcome = None
    if call.booked:
        booking_outcome = "booked"
    elif call.missed_call:
        booking_outcome = "pending"
    elif call.cancelled or call.rescheduled:
        booking_outcome = "pending"
    else:
        # Infer from other fields
        if hasattr(call, 'bought') and call.bought:
            booking_outcome = "booked"
        else:
            booking_outcome = "unbooked"
    
    # Get appointment_id if linked
    appointment_id = None
    if call.lead_id:
        appointment = db.query(Appointment).filter(
            Appointment.lead_id == call.lead_id,
            Appointment.company_id == ctx.company_id
        ).order_by(Appointment.scheduled_start.desc()).first()
        if appointment:
            appointment_id = appointment.id
    
    # Calculate duration
    duration_seconds = None
    if call.last_call_duration:
        duration_seconds = call.last_call_duration
    elif call.last_call_timestamp:
        # Could parse from timestamp, but for now use stored duration
        duration_seconds = call.last_call_duration
    
    return AICallResponse(
        call_id=call.call_id,
        company_id=call.company_id or ctx.company_id,
        lead_id=call.lead_id,
        contact_card_id=call.contact_card_id,
        rep_id=call.assigned_rep_id,
        phone_number=call.phone_number,
        is_missed=call.missed_call or False,
        direction=None,  # CallRail source field might contain this
        source=call.status,  # Use status as source indicator
        started_at=None,  # Not stored directly in Call model
        ended_at=None,  # Not stored directly in Call model
        duration_seconds=duration_seconds,
        booking_outcome=booking_outcome,
        appointment_id=appointment_id,
    )


@router.get("/reps/{rep_id}", response_model=AIRepResponse)
def get_rep_metadata(
    rep_id: str,
    ctx: AIInternalContext = Depends(get_ai_internal_context),
    db: Session = Depends(get_db),
) -> AIRepResponse:
    """
    Get sales rep metadata for internal AI API.
    
    Returns rep information including name, contact, role, and region.
    """
    rep = db.query(SalesRep).filter(SalesRep.user_id == rep_id).first()
    
    if not rep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rep {rep_id} not found"
        )
    
    _check_company_access(rep.company_id, ctx)
    
    # Get user details
    user = db.query(User).filter(User.id == rep_id).first()
    name = None
    email = None
    phone = None
    
    if user:
        name = f"{user.name}" if user.name else None
        email = user.email
        phone = user.phone_number
    
    return AIRepResponse(
        rep_id=rep.user_id,
        company_id=rep.company_id,
        name=name,
        email=email,
        phone=phone,
        role="sales_rep",  # Default role
        region=None,  # Not stored in SalesRep model
        active=rep.allow_location_tracking and rep.allow_recording,  # Use permissions as proxy for active
    )


@router.get("/companies/{company_id}", response_model=AICompanyResponse)
def get_company_metadata(
    company_id: str,
    ctx: AIInternalContext = Depends(get_ai_internal_context),
    db: Session = Depends(get_db),
) -> AICompanyResponse:
    """
    Get company metadata for internal AI API.
    
    Validates that path company_id matches authenticated company_id.
    """
    if company_id != ctx.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company ID mismatch"
        )
    
    company = db.query(Company).filter(Company.id == company_id).first()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )
    
    # Get services offered
    services = db.query(Service).filter(Service.company_id == company_id).all()
    services_offered = [s.name for s in services] if services else []
    
    return AICompanyResponse(
        company_id=company.id,
        name=company.name,
        timezone=None,  # Not stored in Company model
        service_areas=None,  # Not stored in Company model
        services_offered=services_offered,
        created_at=company.created_at,
    )


@router.get("/leads/{lead_id}", response_model=AILeadResponse)
def get_lead_metadata(
    lead_id: str,
    ctx: AIInternalContext = Depends(get_ai_internal_context),
    db: Session = Depends(get_db),
) -> AILeadResponse:
    """
    Get lead metadata for internal AI API (compound response).
    
    Returns lead, contact, and related appointments.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {lead_id} not found"
        )
    
    _check_company_access(lead.company_id, ctx)
    
    # Get contact card
    contact_card = None
    if lead.contact_card_id:
        contact_card = db.query(ContactCard).filter(ContactCard.id == lead.contact_card_id).first()
    
    # Build contact summary
    contact_summary = AIContactSummary(
        name=f"{contact_card.first_name or ''} {contact_card.last_name or ''}".strip() if contact_card else None,
        phones=[contact_card.primary_phone] if contact_card and contact_card.primary_phone else [],
        email=contact_card.email if contact_card else None,
        address=contact_card.address if contact_card else None,
        city=contact_card.city if contact_card else None,
        state=contact_card.state if contact_card else None,
        postal_code=contact_card.postal_code if contact_card else None,
    )
    if contact_card and contact_card.secondary_phone:
        contact_summary.phones.append(contact_card.secondary_phone)
    
    # Get related appointments
    appointments = db.query(Appointment).filter(
        Appointment.lead_id == lead_id,
        Appointment.company_id == ctx.company_id
    ).order_by(Appointment.scheduled_start.desc()).all()
    
    appointment_summaries = [
        AIAppointmentSummary(
            id=apt.id,
            scheduled_start=apt.scheduled_start,
            scheduled_end=apt.scheduled_end,
            status=apt.status.value if apt.status else "unknown",
            outcome=apt.outcome.value if apt.outcome else None,
        )
        for apt in appointments
    ]
    
    # Build lead dict
    lead_dict = {
        "id": lead.id,
        "company_id": lead.company_id,
        "contact_card_id": lead.contact_card_id,
        "status": lead.status.value if lead.status else None,
        "source": lead.source.value if lead.source else None,
        "priority": lead.priority,
        "score": lead.score,
        "last_contacted_at": lead.last_contacted_at.isoformat() if lead.last_contacted_at else None,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
    }
    
    return AILeadResponse(
        lead=lead_dict,
        contact=contact_summary,
        appointments=appointment_summaries,
    )


@router.get("/appointments/{appointment_id}", response_model=AIAppointmentResponse)
def get_appointment_metadata(
    appointment_id: str,
    ctx: AIInternalContext = Depends(get_ai_internal_context),
    db: Session = Depends(get_db),
) -> AIAppointmentResponse:
    """
    Get appointment metadata for internal AI API (compound response).
    
    Returns appointment, lead, and contact information.
    """
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment {appointment_id} not found"
        )
    
    _check_company_access(appointment.company_id, ctx)
    
    # Get lead
    lead = db.query(Lead).filter(Lead.id == appointment.lead_id).first()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {appointment.lead_id} not found"
        )
    
    # Get contact card
    contact_card = None
    if appointment.contact_card_id:
        contact_card = db.query(ContactCard).filter(ContactCard.id == appointment.contact_card_id).first()
    elif lead.contact_card_id:
        contact_card = db.query(ContactCard).filter(ContactCard.id == lead.contact_card_id).first()
    
    # Build contact summary
    contact_summary = AIContactSummary(
        name=f"{contact_card.first_name or ''} {contact_card.last_name or ''}".strip() if contact_card else None,
        phones=[contact_card.primary_phone] if contact_card and contact_card.primary_phone else [],
        email=contact_card.email if contact_card else None,
        address=appointment.location or (contact_card.address if contact_card else None),
        city=contact_card.city if contact_card else None,
        state=contact_card.state if contact_card else None,
        postal_code=contact_card.postal_code if contact_card else None,
    )
    if contact_card and contact_card.secondary_phone:
        contact_summary.phones.append(contact_card.secondary_phone)
    
    # Build appointment dict
    appointment_dict = {
        "id": appointment.id,
        "company_id": appointment.company_id,
        "lead_id": appointment.lead_id,
        "contact_card_id": appointment.contact_card_id,
        "assigned_rep_id": appointment.assigned_rep_id,
        "scheduled_start": appointment.scheduled_start.isoformat() if appointment.scheduled_start else None,
        "scheduled_end": appointment.scheduled_end.isoformat() if appointment.scheduled_end else None,
        "status": appointment.status.value if appointment.status else None,
        "outcome": appointment.outcome.value if appointment.outcome else None,
        "service_type": appointment.service_type,
        "location": appointment.location,
    }
    
    # Build lead dict
    lead_dict = {
        "id": lead.id,
        "company_id": lead.company_id,
        "contact_card_id": lead.contact_card_id,
        "status": lead.status.value if lead.status else None,
        "source": lead.source.value if lead.source else None,
        "priority": lead.priority,
        "score": lead.score,
    }
    
    return AIAppointmentResponse(
        appointment=appointment_dict,
        lead=lead_dict,
        contact=contact_summary,
    )


@router.get("/services/{company_id}", response_model=AIServiceCatalogResponse)
def get_service_catalog(
    company_id: str,
    ctx: AIInternalContext = Depends(get_ai_internal_context),
    db: Session = Depends(get_db),
) -> AIServiceCatalogResponse:
    """
    Get service catalog for internal AI API.
    
    Validates that path company_id matches authenticated company_id.
    Returns empty list if services table doesn't exist or has no services.
    """
    if company_id != ctx.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company ID mismatch"
        )
    
    # Check if company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )
    
    # Try to get services
    try:
        services = db.query(Service).filter(Service.company_id == company_id).all()
        services_list = [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "base_price": s.base_price,
            }
            for s in services
        ]
    except Exception as e:
        # Services table might not exist
        logger.debug(f"Could not fetch services for company {company_id}: {str(e)}")
        services_list = []
    
    return AIServiceCatalogResponse(
        company_id=company_id,
        services=services_list,
    )



