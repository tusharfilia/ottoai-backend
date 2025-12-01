"""
KeySignals list + acknowledge endpoints.
"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.key_signal import KeySignal, SignalType, SignalSeverity
from app.schemas.domain import KeySignalSummary
from app.schemas.responses import APIResponse, ErrorCodes, create_error_response
from app.services.domain_events import emit_domain_event

router = APIRouter(prefix="/api/v1/key-signals", tags=["key-signals"])


class KeySignalListResponse(BaseModel):
    """Response for key signal listing."""
    signals: List[KeySignalSummary] = Field(default_factory=list)
    total: int = Field(..., description="Total count matching filters")
    unacknowledged_count: int = Field(0, description="Count of unacknowledged signals")


@router.get("", response_model=APIResponse[KeySignalListResponse])
@require_role("manager", "csr", "sales_rep")
async def list_key_signals(
    request: Request,
    lead_id: Optional[str] = Query(None, description="Filter by lead ID"),
    appointment_id: Optional[str] = Query(None, description="Filter by appointment ID"),
    contact_card_id: Optional[str] = Query(None, description="Filter by contact card ID"),
    signal_type: Optional[str] = Query(None, description="Filter by signal type (risk, opportunity, coaching, operational)"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledged status"),
    created_after: Optional[datetime] = Query(None, description="Filter signals created after this date"),
    created_before: Optional[datetime] = Query(None, description="Filter signals created before this date"),
    db: Session = Depends(get_db),
) -> APIResponse[KeySignalListResponse]:
    """
    List key signals with optional filters.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    
    # Build query
    query = db.query(KeySignal).filter(KeySignal.company_id == tenant_id)
    
    # Filter by lead_id
    if lead_id:
        query = query.filter(KeySignal.lead_id == lead_id)
    
    # Filter by appointment_id
    if appointment_id:
        query = query.filter(KeySignal.appointment_id == appointment_id)
    
    # Filter by contact_card_id
    if contact_card_id:
        query = query.filter(KeySignal.contact_card_id == contact_card_id)
    
    # Filter by signal_type
    if signal_type:
        try:
            type_enum = SignalType(signal_type.lower())
            query = query.filter(KeySignal.signal_type == type_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code=ErrorCodes.INVALID_REQUEST,
                    message=f"Invalid signal_type: {signal_type}",
                    details={"valid_types": [t.value for t in SignalType]},
                    request_id=getattr(request.state, "trace_id", None),
                ).dict(),
            )
    
    # Filter by acknowledged
    if acknowledged is not None:
        query = query.filter(KeySignal.acknowledged == acknowledged)
    
    # Filter by created date range
    if created_after:
        query = query.filter(KeySignal.created_at >= created_after)
    if created_before:
        query = query.filter(KeySignal.created_at <= created_before)
    
    # Order by severity (critical first), then created_at (newest first)
    query = query.order_by(
        KeySignal.severity.desc(),
        KeySignal.created_at.desc()
    )
    
    signals = query.all()
    
    # Calculate unacknowledged count
    unacknowledged_count = sum(1 for signal in signals if not signal.acknowledged)
    
    # Build response
    signal_summaries = [KeySignalSummary.from_orm(signal) for signal in signals]
    
    response = KeySignalListResponse(
        signals=signal_summaries,
        total=len(signal_summaries),
        unacknowledged_count=unacknowledged_count,
    )
    
    return APIResponse(data=response)


@router.post("/{signal_id}/acknowledge", response_model=APIResponse[KeySignalSummary])
@require_role("manager", "csr", "sales_rep")
async def acknowledge_signal(
    request: Request,
    signal_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[KeySignalSummary]:
    """
    Acknowledge a key signal.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    
    signal = db.query(KeySignal).filter(
        KeySignal.id == signal_id,
        KeySignal.company_id == tenant_id
    ).first()
    
    if not signal:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Key signal not found",
                details={"signal_id": signal_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Check if already acknowledged
    if signal.acknowledged:
        # Return existing signal (idempotent)
        return APIResponse(data=KeySignalSummary.from_orm(signal))
    
    # Acknowledge signal
    signal.acknowledged = True
    signal.acknowledged_at = datetime.utcnow()
    signal.acknowledged_by = user_id
    signal.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(signal)
    
    # Emit event
    emit_domain_event(
        event_name="key_signal.acknowledged",
        tenant_id=tenant_id,
        lead_id=signal.lead_id,
        payload={
            "signal_id": signal.id,
            "company_id": signal.company_id,
            "contact_card_id": signal.contact_card_id,
            "signal_type": signal.signal_type.value,
            "title": signal.title,
            "acknowledged_by": user_id,
            "acknowledged_at": signal.acknowledged_at.isoformat(),
        },
    )
    
    return APIResponse(data=KeySignalSummary.from_orm(signal))


