"""
Wins feed endpoint for closed-won appointments.
"""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.appointment import Appointment, AppointmentOutcome, AppointmentStatus
from app.models.lead import Lead
from app.models.contact_card import ContactCard
from app.models.sales_rep import SalesRep
from app.models.user import User
from app.schemas.responses import APIResponse, ErrorCodes, create_error_response

router = APIRouter(prefix="/api/v1/wins-feed", tags=["wins-feed"])


class WinItem(BaseModel):
    """Single win item in the feed."""
    appointment_id: str = Field(..., description="Appointment ID")
    lead_id: str = Field(..., description="Lead ID")
    contact_name: Optional[str] = Field(None, description="Customer name")
    address: Optional[str] = Field(None, description="Customer address")
    rep_name: Optional[str] = Field(None, description="Sales rep name")
    rep_id: Optional[str] = Field(None, description="Sales rep ID")
    deal_size: float = Field(..., description="Deal size in dollars")
    closed_at: datetime = Field(..., description="When deal was closed")
    service_type: Optional[str] = Field(None, description="Service type")
    scheduled_start: Optional[datetime] = Field(None, description="Original appointment scheduled start")
    
    class Config:
        from_attributes = True


class WinsFeedResponse(BaseModel):
    """Response for wins feed."""
    wins: List[WinItem] = Field(default_factory=list)
    total: int = Field(..., description="Total count matching filters")
    date_from: Optional[str] = Field(None, description="Date filter start (ISO format)")
    date_to: Optional[str] = Field(None, description="Date filter end (ISO format)")


@router.get("", response_model=APIResponse[WinsFeedResponse])
@require_role("manager", "csr", "sales_rep")
async def get_wins_feed(
    request: Request,
    date_from: Optional[datetime] = Query(None, description="Filter wins from this date (defaults to 30 days ago)"),
    date_to: Optional[datetime] = Query(None, description="Filter wins until this date (defaults to now)"),
    rep_id: Optional[str] = Query(None, description="Filter by sales rep ID"),
    limit: int = Query(100, ge=1, le=200, description="Maximum number of results"),
    db: Session = Depends(get_db),
) -> APIResponse[WinsFeedResponse]:
    """
    Get wins feed (closed-won appointments with deal sizes).
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    
    # Set default date range (last 30 days)
    if not date_from:
        date_from = datetime.utcnow() - timedelta(days=30)
    if not date_to:
        date_to = datetime.utcnow()
    
    # Build query
    query = db.query(Appointment).filter(
        Appointment.company_id == tenant_id,
        Appointment.outcome == AppointmentOutcome.WON,
        Appointment.deal_size.isnot(None),
        Appointment.deal_size > 0,
    )
    
    # Filter by date range (on updated_at when outcome changed to won, or scheduled_start)
    # We'll use updated_at as proxy for closed_at
    query = query.filter(
        Appointment.updated_at >= date_from,
        Appointment.updated_at <= date_to
    )
    
    # Filter by rep_id
    if rep_id:
        query = query.filter(Appointment.assigned_rep_id == rep_id)
    
    # Order by closed_at (updated_at) descending (newest first)
    query = query.order_by(Appointment.updated_at.desc())
    
    # Apply limit
    query = query.limit(limit)
    
    # Eager load relationships
    appointments = query.options(
        selectinload(Appointment.lead),
        selectinload(Appointment.contact_card),
        selectinload(Appointment.assigned_rep),
    ).all()
    
    # Build win items
    win_items = []
    for appointment in appointments:
        # Get contact name
        contact_name = None
        if appointment.contact_card:
            name_parts = []
            if appointment.contact_card.first_name:
                name_parts.append(appointment.contact_card.first_name)
            if appointment.contact_card.last_name:
                name_parts.append(appointment.contact_card.last_name)
            contact_name = " ".join(name_parts) if name_parts else None
        
        # Get rep name
        rep_name = None
        if appointment.assigned_rep_id:
            rep = appointment.assigned_rep
            if rep:
                user = db.query(User).filter(User.id == rep.user_id).first()
                if user:
                    rep_name = user.name
        
        # Use updated_at as proxy for closed_at (when outcome was set to won)
        closed_at = appointment.updated_at
        
        win_items.append(WinItem(
            appointment_id=appointment.id,
            lead_id=appointment.lead_id,
            contact_name=contact_name,
            address=appointment.location,
            rep_name=rep_name,
            rep_id=appointment.assigned_rep_id,
            deal_size=appointment.deal_size or 0.0,
            closed_at=closed_at,
            service_type=appointment.service_type,
            scheduled_start=appointment.scheduled_start,
        ))
    
    response = WinsFeedResponse(
        wins=win_items,
        total=len(win_items),
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
    )
    
    return APIResponse(data=response)


