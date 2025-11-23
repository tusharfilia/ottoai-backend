"""
Lead Pool API endpoints.

Manages the shared lead pool where qualified, bookable leads flow.
Reps can request leads, managers can assign leads, and assignment history is tracked.
"""
from datetime import datetime
from typing import Optional, List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_, or_

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.lead import Lead, PoolStatus, LeadStatus
from app.models.rep_assignment_history import RepAssignmentHistory
from app.models.contact_card import ContactCard
from app.models.key_signal import KeySignal
from app.schemas.responses import APIResponse, ErrorCodes, create_error_response
from app.realtime.bus import emit
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/lead-pool", tags=["lead-pool"])


class PoolLeadSummary(BaseModel):
    """Summary of a lead in the pool."""
    lead_id: str
    contact_card_id: str
    contact_name: Optional[str] = None
    primary_phone: Optional[str] = None
    address: Optional[str] = None
    lead_status: str
    deal_status: Optional[str] = None
    signals: List[str] = Field(default_factory=list, description="Key signal titles")
    last_activity: Optional[datetime] = None
    assigned_rep_id: Optional[str] = None
    requested_by_rep_ids: List[str] = Field(default_factory=list)
    created_at: datetime


class LeadPoolListResponse(BaseModel):
    """Response for listing pool leads."""
    leads: List[PoolLeadSummary]
    total_count: int
    in_pool_count: int
    assigned_count: int


class RequestLeadResponse(BaseModel):
    """Response for rep requesting a lead."""
    lead_id: str
    rep_id: str
    status: str
    requested_at: datetime
    message: str


class AssignLeadRequest(BaseModel):
    """Request body for assigning a lead."""
    rep_id: str = Field(..., description="ID of rep to assign lead to")
    notes: Optional[str] = Field(None, description="Optional assignment notes")


class AssignLeadResponse(BaseModel):
    """Response for assigning a lead."""
    lead_id: str
    rep_id: str
    assigned_by: str
    assigned_at: datetime
    pool_status: str
    message: str


@router.get("", response_model=APIResponse[LeadPoolListResponse])
@require_role("exec", "manager", "rep", "csr")
async def list_pool_leads(
    request: Request,
    status: Optional[str] = None,  # in_pool, assigned, closed
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> APIResponse[LeadPoolListResponse]:
    """
    List all leads in the lead pool.
    
    Returns leads with pool_status = "in_pool" by default.
    Managers can see all leads (in_pool, assigned, closed).
    Reps can see in_pool leads and their own assigned leads.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    user_role = getattr(request.state, "user_role", None)
    user_id = getattr(request.state, "user_id", None)
    
    # Build query
    query = db.query(Lead).join(ContactCard).filter(
        Lead.company_id == tenant_id
    )
    
    # Filter by pool status
    if status:
        try:
            pool_status_enum = PoolStatus(status)
            query = query.filter(Lead.pool_status == pool_status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code=ErrorCodes.INVALID_REQUEST,
                    message=f"Invalid pool status: {status}. Valid values: in_pool, assigned, closed, archived",
                    request_id=getattr(request.state, "trace_id", None),
                ).dict(),
            )
    else:
        # Default: show in_pool leads, but managers see all
        if user_role not in ["exec", "manager"]:
            # Reps only see in_pool leads or their own assigned leads
            query = query.filter(
                or_(
                    Lead.pool_status == PoolStatus.IN_POOL,
                    and_(
                        Lead.pool_status == PoolStatus.ASSIGNED,
                        Lead.assigned_rep_id == user_id
                    )
                )
            )
        # Managers/execs see all pool statuses by default
    
    # Get totals
    total_count = query.count()
    in_pool_count = db.query(Lead).filter(
        Lead.company_id == tenant_id,
        Lead.pool_status == PoolStatus.IN_POOL
    ).count()
    assigned_count = db.query(Lead).filter(
        Lead.company_id == tenant_id,
        Lead.pool_status == PoolStatus.ASSIGNED
    ).count()
    
    # Get leads with related data
    leads = (
        query
        .options(
            selectinload(Lead.contact_card),
            selectinload(Lead.key_signals),
            selectinload(Lead.appointments)
        )
        .order_by(Lead.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    # Build summaries
    lead_summaries = []
    for lead in leads:
        contact = lead.contact_card
        if not contact:
            continue
        
        # Get key signals
        signal_titles = [sig.title for sig in lead.key_signals if not sig.acknowledged][:3]
        
        # Get last activity (last appointment or last contacted)
        last_activity = lead.last_contacted_at
        if lead.appointments:
            last_appt = max(lead.appointments, key=lambda a: a.scheduled_start or datetime.min)
            if last_appt.scheduled_start:
                if not last_activity or last_appt.scheduled_start > last_activity:
                    last_activity = last_appt.scheduled_start
        
        # Get requested by rep IDs
        requested_by_rep_ids = lead.requested_by_rep_ids or []
        
        # Get contact name
        contact_name = None
        if contact.first_name or contact.last_name:
            name_parts = [p for p in [contact.first_name, contact.last_name] if p]
            contact_name = " ".join(name_parts)
        
        lead_summary = PoolLeadSummary(
            lead_id=lead.id,
            contact_card_id=lead.contact_card_id,
            contact_name=contact_name,
            primary_phone=contact.primary_phone,
            address=contact.address,
            lead_status=lead.status.value,
            deal_status=lead.deal_status,
            signals=signal_titles,
            last_activity=last_activity,
            assigned_rep_id=lead.assigned_rep_id,
            requested_by_rep_ids=requested_by_rep_ids,
            created_at=lead.created_at
        )
        lead_summaries.append(lead_summary)
    
    response = LeadPoolListResponse(
        leads=lead_summaries,
        total_count=total_count,
        in_pool_count=in_pool_count,
        assigned_count=assigned_count
    )
    
    return APIResponse(data=response)


@router.post("/{lead_id}/request", response_model=APIResponse[RequestLeadResponse])
@require_role("rep")
async def request_lead(
    request: Request,
    lead_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[RequestLeadResponse]:
    """
    Request a lead from the pool.
    
    Reps can express interest in a lead by requesting it.
    Creates a RepAssignmentHistory entry with status="requested".
    Updates the denormalized requested_by_rep_ids list on Lead.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail=create_error_response(
                error_code=ErrorCodes.UNAUTHORIZED,
                message="User ID not found in request",
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Get lead
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.company_id == tenant_id
    ).first()
    
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
    
    # Check if lead is in pool
    if lead.pool_status != PoolStatus.IN_POOL:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code=ErrorCodes.INVALID_REQUEST,
                message=f"Lead is not in pool. Current status: {lead.pool_status.value}",
                details={"lead_id": lead_id, "pool_status": lead.pool_status.value},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Check if already requested
    existing_request = db.query(RepAssignmentHistory).filter(
        RepAssignmentHistory.lead_id == lead_id,
        RepAssignmentHistory.rep_id == user_id,
        RepAssignmentHistory.status == "requested"
    ).first()
    
    if existing_request:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code=ErrorCodes.INVALID_REQUEST,
                message="You have already requested this lead",
                details={"lead_id": lead_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Create request history entry
    request_entry = RepAssignmentHistory(
        id=str(uuid4()),
        company_id=tenant_id,
        lead_id=lead_id,
        rep_id=user_id,
        assignment_type="requested",
        status="requested",
        requested_at=datetime.utcnow()
    )
    db.add(request_entry)
    
    # Update denormalized requested_by_rep_ids list
    requested_ids = lead.requested_by_rep_ids or []
    if user_id not in requested_ids:
        requested_ids.append(user_id)
        lead.requested_by_rep_ids = requested_ids
    
    db.commit()
    
    # Emit event
    emit(
        event_name="lead.requested_by_rep",
        payload={
            "lead_id": lead_id,
            "rep_id": user_id,
            "contact_card_id": lead.contact_card_id
        },
        tenant_id=tenant_id,
        lead_id=lead_id,
        user_id=user_id
    )
    
    response = RequestLeadResponse(
        lead_id=lead_id,
        rep_id=user_id,
        status="requested",
        requested_at=request_entry.requested_at,
        message="Lead request recorded successfully"
    )
    
    return APIResponse(data=response)


@router.post("/{lead_id}/assign", response_model=APIResponse[AssignLeadResponse])
@require_role("exec", "manager")
async def assign_lead(
    request: Request,
    lead_id: str,
    assign_request: AssignLeadRequest,
    db: Session = Depends(get_db),
) -> APIResponse[AssignLeadResponse]:
    """
    Assign a lead from the pool to a rep.
    
    Only managers/execs can assign leads.
    Updates Lead.pool_status to "assigned".
    Updates Appointment.assigned_rep_id if appointment exists.
    Creates/updates RepAssignmentHistory with status="assigned".
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    assigned_by_user_id = getattr(request.state, "user_id", None)
    rep_id = assign_request.rep_id
    
    if not assigned_by_user_id:
        raise HTTPException(
            status_code=401,
            detail=create_error_response(
                error_code=ErrorCodes.UNAUTHORIZED,
                message="User ID not found in request",
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Get lead
    lead = (
        db.query(Lead)
        .options(selectinload(Lead.appointments))
        .filter(
            Lead.id == lead_id,
            Lead.company_id == tenant_id
        )
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
    
    # Check if lead is assignable
    if lead.pool_status not in [PoolStatus.IN_POOL, PoolStatus.ASSIGNED]:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code=ErrorCodes.INVALID_REQUEST,
                message=f"Cannot assign lead with status: {lead.pool_status.value}",
                details={"lead_id": lead_id, "pool_status": lead.pool_status.value},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Update lead
    old_assigned_rep_id = lead.assigned_rep_id
    lead.assigned_rep_id = rep_id
    lead.assigned_at = datetime.utcnow()
    lead.assigned_by = assigned_by_user_id
    lead.pool_status = PoolStatus.ASSIGNED
    lead.rep_claimed = False  # Reset claim status
    
    # Update appointments
    for appointment in lead.appointments:
        if appointment.status.value in ["scheduled", "confirmed"]:  # Only update active appointments
            appointment.assigned_rep_id = rep_id
    
    # Create/update assignment history
    assignment_entry = RepAssignmentHistory(
        id=str(uuid4()),
        company_id=tenant_id,
        lead_id=lead_id,
        rep_id=rep_id,
        assigned_by=assigned_by_user_id,
        assignment_type="assigned",
        status="assigned",
        assigned_at=datetime.utcnow(),
        notes=assign_request.notes
    )
    db.add(assignment_entry)
    
    # Update any existing "requested" entries for this rep to "assigned"
    existing_requests = db.query(RepAssignmentHistory).filter(
        RepAssignmentHistory.lead_id == lead_id,
        RepAssignmentHistory.rep_id == rep_id,
        RepAssignmentHistory.status == "requested"
    ).all()
    
    for req in existing_requests:
        req.status = "assigned"
        req.assigned_at = datetime.utcnow()
    
    db.commit()
    
    # Emit event
    emit(
        event_name="lead.assigned_to_rep",
        payload={
            "lead_id": lead_id,
            "rep_id": rep_id,
            "assigned_by": assigned_by_user_id,
            "previous_rep_id": old_assigned_rep_id,
            "contact_card_id": lead.contact_card_id,
            "pool_status": PoolStatus.ASSIGNED.value
        },
        tenant_id=tenant_id,
        lead_id=lead_id,
        user_id=rep_id
    )
    
    response = AssignLeadResponse(
        lead_id=lead_id,
        rep_id=rep_id,
        assigned_by=assigned_by_user_id,
        assigned_at=assignment_entry.assigned_at,
        pool_status=PoolStatus.ASSIGNED.value,
        message=f"Lead assigned to rep {rep_id} successfully"
    )
    
    return APIResponse(data=response)


