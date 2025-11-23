"""
Rep Shift Management APIs for clock-in/out and shift tracking.
"""
from datetime import datetime, date, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.rep_shift import RepShift, ShiftStatus
from app.models.sales_rep import SalesRep, RecordingMode, ShiftConfigSource
from app.schemas.domain import (
    RepShiftBase,
    RepShiftCreate,
    RepShiftResponse,
)
from app.schemas.responses import APIResponse
from app.realtime.bus import emit

router = APIRouter(prefix="/api/v1/reps", tags=["rep-shifts"])


def _get_rep_or_404(db: Session, rep_id: str, company_id: str) -> SalesRep:
    """Get rep or raise 404."""
    rep = db.query(SalesRep).filter(
        SalesRep.user_id == rep_id,
        SalesRep.company_id == company_id
    ).first()
    if not rep:
        raise HTTPException(status_code=404, detail=f"Sales rep {rep_id} not found")
    return rep


def _get_today_shift(db: Session, rep_id: str, company_id: str) -> Optional[RepShift]:
    """Get today's shift for a rep."""
    today = date.today()
    return db.query(RepShift).filter(
        RepShift.rep_id == rep_id,
        RepShift.company_id == company_id,
        RepShift.shift_date == today
    ).first()


def _get_rep_shift_config(rep: SalesRep, company_id: str) -> tuple[Optional[time], Optional[time]]:
    """
    Get shift start/end times for a rep.
    
    Returns:
        (start_time, end_time) based on rep's shift_config_source
    """
    if rep.shift_config_source == ShiftConfigSource.CUSTOM:
        return (rep.default_shift_start, rep.default_shift_end)
    else:
        # TODO: Get from company default settings when that model exists
        # For now, use rep's defaults or sensible defaults
        return (
            rep.default_shift_start or time(7, 0),  # 7am default
            rep.default_shift_end or time(20, 0),  # 8pm default
        )


@router.post("/{rep_id}/shifts/clock-in", response_model=APIResponse[RepShiftResponse])
@require_role("rep", "manager", "exec")
async def clock_in(
    request: Request,
    rep_id: str,
    body: RepShiftCreate,
    db: Session = Depends(get_db),
) -> APIResponse[RepShiftResponse]:
    """
    Clock in for a shift.
    
    Creates or updates today's shift with status='active'.
    Validates rep configuration and permissions.
    """
    company_id = request.state.tenant_id
    
    # Get rep
    rep = _get_rep_or_404(db, rep_id, company_id)
    
    # Validate recording permissions
    if not rep.allow_recording:
        raise HTTPException(
            status_code=403,
            detail="Recording is not allowed for this rep"
        )
    
    # Get or create today's shift
    shift = _get_today_shift(db, rep_id, company_id)
    
    if shift:
        # Update existing shift
        if shift.status == ShiftStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail="Rep is already clocked in"
            )
        shift.status = ShiftStatus.ACTIVE
        shift.clock_in_at = body.desired_start_time or datetime.utcnow()
        if body.notes:
            shift.notes = body.notes
    else:
        # Create new shift
        start_time, end_time = _get_rep_shift_config(rep, company_id)
        shift = RepShift(
            rep_id=rep_id,
            company_id=company_id,
            shift_date=date.today(),
            clock_in_at=body.desired_start_time or datetime.utcnow(),
            scheduled_start=start_time,
            scheduled_end=end_time,
            status=ShiftStatus.ACTIVE,
            notes=body.notes,
        )
        db.add(shift)
    
    db.commit()
    db.refresh(shift)
    
    # Emit event
    await emit(
        "rep.shift.started",
        {
            "rep_id": rep_id,
            "company_id": company_id,
            "shift_id": shift.id,
            "clock_in_at": shift.clock_in_at.isoformat() if shift.clock_in_at else None,
        },
        tenant_id=company_id,
        user_id=rep_id,
    )
    
    # Build response
    response = RepShiftResponse(
        shift=RepShiftBase.model_validate(shift),
        effective_start_time=shift.clock_in_at,
        effective_end_time=shift.scheduled_end,  # TODO: Calculate from scheduled_end + shift_date
        recording_mode=rep.recording_mode.value,
        allow_location_tracking=rep.allow_location_tracking,
        allow_recording=rep.allow_recording,
    )
    
    return APIResponse(data=response)


@router.post("/{rep_id}/shifts/clock-out", response_model=APIResponse[RepShiftBase])
@require_role("rep", "manager", "exec")
async def clock_out(
    request: Request,
    rep_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[RepShiftBase]:
    """
    Clock out from current shift.
    
    Marks shift as completed and sets clock_out_at.
    """
    company_id = request.state.tenant_id
    
    # Get today's shift
    shift = _get_today_shift(db, rep_id, company_id)
    if not shift:
        raise HTTPException(
            status_code=404,
            detail="No active shift found for today"
        )
    
    if shift.status != ShiftStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot clock out from shift with status: {shift.status.value}"
        )
    
    shift.clock_out_at = datetime.utcnow()
    shift.status = ShiftStatus.COMPLETED
    
    db.commit()
    db.refresh(shift)
    
    # Emit event
    await emit(
        "rep.shift.ended",
        {
            "rep_id": rep_id,
            "company_id": company_id,
            "shift_id": shift.id,
            "clock_out_at": shift.clock_out_at.isoformat(),
        },
        tenant_id=company_id,
        user_id=rep_id,
    )
    
    return APIResponse(data=RepShiftBase.model_validate(shift))


@router.get("/{rep_id}/shifts/today", response_model=APIResponse[RepShiftResponse])
@require_role("rep", "manager", "exec")
async def get_today_shift(
    request: Request,
    rep_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[RepShiftResponse]:
    """
    Get today's shift status for a rep.
    
    Returns current shift status, mode, and time window.
    """
    company_id = request.state.tenant_id
    
    # Get rep
    rep = _get_rep_or_404(db, rep_id, company_id)
    
    # Get today's shift
    shift = _get_today_shift(db, rep_id, company_id)
    
    if not shift:
        # Return default response for no shift
        start_time, end_time = _get_rep_shift_config(rep, company_id)
        response = RepShiftResponse(
            shift=None,  # No shift yet
            effective_start_time=None,
            effective_end_time=None,
            recording_mode=rep.recording_mode.value,
            allow_location_tracking=rep.allow_location_tracking,
            allow_recording=rep.allow_recording,
        )
        return APIResponse(data=response)
    
    # Build response
    response = RepShiftResponse(
        shift=RepShiftBase.model_validate(shift),
        effective_start_time=shift.clock_in_at,
        effective_end_time=shift.scheduled_end,  # TODO: Calculate properly
        recording_mode=rep.recording_mode.value,
        allow_location_tracking=rep.allow_location_tracking,
        allow_recording=rep.allow_recording,
    )
    
    return APIResponse(data=response)


