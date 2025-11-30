"""
Review follow-up trigger endpoints.
"""
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.appointment import Appointment, AppointmentOutcome
from app.models.lead import Lead
from app.models.contact_card import ContactCard
from app.schemas.responses import APIResponse, ErrorCodes, create_error_response
from app.services.domain_events import emit_domain_event

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


class ReviewRequestBody(BaseModel):
    """Request body for triggering a review request."""
    appointment_id: str = Field(..., description="Appointment ID")
    channel: Optional[str] = Field("sms", description="Channel for review request (sms, email)")
    template_id: Optional[str] = Field(None, description="Optional template ID")


class ReviewRequestResponse(BaseModel):
    """Response for review request."""
    review_request_id: str = Field(..., description="Review request ID")
    appointment_id: str = Field(..., description="Appointment ID")
    contact_card_id: str = Field(..., description="Contact card ID")
    channel: str = Field(..., description="Channel used")
    status: str = Field(..., description="Request status (queued/requested/sent/completed)")
    created_at: datetime = Field(..., description="When request was created")


@router.post("/request", response_model=APIResponse[ReviewRequestResponse])
@require_role("manager", "csr", "sales_rep")
async def request_review(
    request: Request,
    payload: ReviewRequestBody,
    db: Session = Depends(get_db),
) -> APIResponse[ReviewRequestResponse]:
    """
    Trigger a review follow-up request for a closed-won appointment.
    
    This creates a review request record and emits an event for background processing.
    The actual SMS/email sending is handled by a background worker.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    
    # Get appointment
    appointment = db.query(Appointment).filter(
        Appointment.id == payload.appointment_id,
        Appointment.company_id == tenant_id
    ).first()
    
    if not appointment:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Appointment not found",
                details={"appointment_id": payload.appointment_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Verify appointment outcome is won
    if appointment.outcome != AppointmentOutcome.WON:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code=ErrorCodes.INVALID_REQUEST,
                message="Review requests can only be sent for won appointments",
                details={
                    "appointment_id": payload.appointment_id,
                    "current_outcome": appointment.outcome.value,
                },
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Get lead and contact
    lead = db.query(Lead).filter(Lead.id == appointment.lead_id).first()
    if not lead:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Lead not found for appointment",
                details={"appointment_id": payload.appointment_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    contact_card = db.query(ContactCard).filter(ContactCard.id == appointment.contact_card_id).first()
    if not contact_card:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Contact card not found for appointment",
                details={"appointment_id": payload.appointment_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Create review request record
    # For now, we'll store this in a simple way (could create ReviewRequest model later)
    review_request_id = str(uuid4())
    
    # TODO: If ReviewRequest model exists, create it here
    # For now, we'll just emit the event and return success
    
    # Emit event for background worker to process
    emit_domain_event(
        event_name="review.requested",
        tenant_id=tenant_id,
        lead_id=lead.id,
        payload={
            "review_request_id": review_request_id,
            "appointment_id": payload.appointment_id,
            "lead_id": lead.id,
            "contact_card_id": contact_card.id,
            "company_id": tenant_id,
            "channel": payload.channel,
            "template_id": payload.template_id,
            "contact_phone": contact_card.primary_phone,
            "contact_name": f"{contact_card.first_name or ''} {contact_card.last_name or ''}".strip(),
            "deal_size": appointment.deal_size,
            "requested_by": user_id,
        },
    )
    
    response = ReviewRequestResponse(
        review_request_id=review_request_id,
        appointment_id=payload.appointment_id,
        contact_card_id=contact_card.id,
        channel=payload.channel,
        status="queued",  # Status will be updated by background worker
        created_at=datetime.utcnow(),
    )
    
    return APIResponse(data=response)

