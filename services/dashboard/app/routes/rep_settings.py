"""
Rep settings endpoints (ghost mode, etc.).
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.sales_rep import SalesRep, RecordingMode
from app.schemas.responses import APIResponse, ErrorCodes, create_error_response
from app.services.domain_events import emit_domain_event

router = APIRouter(prefix="/api/v1/reps", tags=["rep-settings"])


class GhostModeStatus(BaseModel):
    """Ghost mode status response."""
    rep_id: str = Field(..., description="Sales rep ID")
    ghost_mode_enabled: bool = Field(..., description="Whether ghost mode is enabled")
    recording_mode: str = Field(..., description="Current recording mode (normal/ghost/off)")
    updated_at: Optional[datetime] = Field(None, description="When ghost mode was last updated")


class GhostModeToggleRequest(BaseModel):
    """Request body for toggling ghost mode."""
    enabled: Optional[bool] = Field(None, description="Set ghost mode enabled (if None, toggles)")


@router.get("/{rep_id}/ghost-mode", response_model=APIResponse[GhostModeStatus])
@require_role("manager", "csr", "sales_rep")
async def get_ghost_mode_status(
    request: Request,
    rep_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[GhostModeStatus]:
    """
    Get ghost mode status for a rep.
    
    Reps can only view their own status unless caller is manager/admin.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "user_role", None)
    
    # Check permissions: rep can only view their own, managers can view any
    if user_role == "sales_rep" and rep_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code=ErrorCodes.FORBIDDEN,
                message="You can only view your own ghost mode status",
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Get rep
    rep = db.query(SalesRep).filter(
        SalesRep.user_id == rep_id,
        SalesRep.company_id == tenant_id
    ).first()
    
    if not rep:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Sales rep not found",
                details={"rep_id": rep_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Determine ghost mode status
    ghost_mode_enabled = rep.recording_mode == RecordingMode.GHOST
    
    response = GhostModeStatus(
        rep_id=rep_id,
        ghost_mode_enabled=ghost_mode_enabled,
        recording_mode=rep.recording_mode.value,
        updated_at=datetime.utcnow(),  # TODO: Add updated_at field to SalesRep if needed
    )
    
    return APIResponse(data=response)


@router.post("/{rep_id}/ghost-mode/toggle", response_model=APIResponse[GhostModeStatus])
@require_role("manager", "csr", "sales_rep")
async def toggle_ghost_mode(
    request: Request,
    rep_id: str,
    payload: GhostModeToggleRequest,
    db: Session = Depends(get_db),
) -> APIResponse[GhostModeStatus]:
    """
    Toggle ghost mode for a rep.
    
    Reps can only toggle their own mode unless caller is manager/admin.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "user_role", None)
    
    # Check permissions: rep can only toggle their own, managers can toggle any
    if user_role == "sales_rep" and rep_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code=ErrorCodes.FORBIDDEN,
                message="You can only toggle your own ghost mode",
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Get rep
    rep = db.query(SalesRep).filter(
        SalesRep.user_id == rep_id,
        SalesRep.company_id == tenant_id
    ).first()
    
    if not rep:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Sales rep not found",
                details={"rep_id": rep_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Determine new mode
    if payload.enabled is not None:
        # Explicit set
        new_mode = RecordingMode.GHOST if payload.enabled else RecordingMode.NORMAL
    else:
        # Toggle
        if rep.recording_mode == RecordingMode.GHOST:
            new_mode = RecordingMode.NORMAL
        else:
            new_mode = RecordingMode.GHOST
    
    # Update rep
    old_mode = rep.recording_mode
    rep.recording_mode = new_mode
    db.commit()
    db.refresh(rep)
    
    # Emit event
    emit_domain_event(
        event_name="rep.ghost_mode_changed",
        tenant_id=tenant_id,
        lead_id=None,
        payload={
            "rep_id": rep_id,
            "company_id": tenant_id,
            "old_mode": old_mode.value,
            "new_mode": new_mode.value,
            "changed_by": user_id,
        },
    )
    
    response = GhostModeStatus(
        rep_id=rep_id,
        ghost_mode_enabled=(new_mode == RecordingMode.GHOST),
        recording_mode=new_mode.value,
        updated_at=datetime.utcnow(),
    )
    
    return APIResponse(data=response)


Rep settings endpoints (ghost mode, etc.).
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.sales_rep import SalesRep, RecordingMode
from app.schemas.responses import APIResponse, ErrorCodes, create_error_response
from app.services.domain_events import emit_domain_event

router = APIRouter(prefix="/api/v1/reps", tags=["rep-settings"])


class GhostModeStatus(BaseModel):
    """Ghost mode status response."""
    rep_id: str = Field(..., description="Sales rep ID")
    ghost_mode_enabled: bool = Field(..., description="Whether ghost mode is enabled")
    recording_mode: str = Field(..., description="Current recording mode (normal/ghost/off)")
    updated_at: Optional[datetime] = Field(None, description="When ghost mode was last updated")


class GhostModeToggleRequest(BaseModel):
    """Request body for toggling ghost mode."""
    enabled: Optional[bool] = Field(None, description="Set ghost mode enabled (if None, toggles)")


@router.get("/{rep_id}/ghost-mode", response_model=APIResponse[GhostModeStatus])
@require_role("manager", "csr", "sales_rep")
async def get_ghost_mode_status(
    request: Request,
    rep_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[GhostModeStatus]:
    """
    Get ghost mode status for a rep.
    
    Reps can only view their own status unless caller is manager/admin.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "user_role", None)
    
    # Check permissions: rep can only view their own, managers can view any
    if user_role == "sales_rep" and rep_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code=ErrorCodes.FORBIDDEN,
                message="You can only view your own ghost mode status",
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Get rep
    rep = db.query(SalesRep).filter(
        SalesRep.user_id == rep_id,
        SalesRep.company_id == tenant_id
    ).first()
    
    if not rep:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Sales rep not found",
                details={"rep_id": rep_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Determine ghost mode status
    ghost_mode_enabled = rep.recording_mode == RecordingMode.GHOST
    
    response = GhostModeStatus(
        rep_id=rep_id,
        ghost_mode_enabled=ghost_mode_enabled,
        recording_mode=rep.recording_mode.value,
        updated_at=datetime.utcnow(),  # TODO: Add updated_at field to SalesRep if needed
    )
    
    return APIResponse(data=response)


@router.post("/{rep_id}/ghost-mode/toggle", response_model=APIResponse[GhostModeStatus])
@require_role("manager", "csr", "sales_rep")
async def toggle_ghost_mode(
    request: Request,
    rep_id: str,
    payload: GhostModeToggleRequest,
    db: Session = Depends(get_db),
) -> APIResponse[GhostModeStatus]:
    """
    Toggle ghost mode for a rep.
    
    Reps can only toggle their own mode unless caller is manager/admin.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "user_role", None)
    
    # Check permissions: rep can only toggle their own, managers can toggle any
    if user_role == "sales_rep" and rep_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code=ErrorCodes.FORBIDDEN,
                message="You can only toggle your own ghost mode",
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Get rep
    rep = db.query(SalesRep).filter(
        SalesRep.user_id == rep_id,
        SalesRep.company_id == tenant_id
    ).first()
    
    if not rep:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Sales rep not found",
                details={"rep_id": rep_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Determine new mode
    if payload.enabled is not None:
        # Explicit set
        new_mode = RecordingMode.GHOST if payload.enabled else RecordingMode.NORMAL
    else:
        # Toggle
        if rep.recording_mode == RecordingMode.GHOST:
            new_mode = RecordingMode.NORMAL
        else:
            new_mode = RecordingMode.GHOST
    
    # Update rep
    old_mode = rep.recording_mode
    rep.recording_mode = new_mode
    db.commit()
    db.refresh(rep)
    
    # Emit event
    emit_domain_event(
        event_name="rep.ghost_mode_changed",
        tenant_id=tenant_id,
        lead_id=None,
        payload={
            "rep_id": rep_id,
            "company_id": tenant_id,
            "old_mode": old_mode.value,
            "new_mode": new_mode.value,
            "changed_by": user_id,
        },
    )
    
    response = GhostModeStatus(
        rep_id=rep_id,
        ghost_mode_enabled=(new_mode == RecordingMode.GHOST),
        recording_mode=new_mode.value,
        updated_at=datetime.utcnow(),
    )
    
    return APIResponse(data=response)


Rep settings endpoints (ghost mode, etc.).
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.sales_rep import SalesRep, RecordingMode
from app.schemas.responses import APIResponse, ErrorCodes, create_error_response
from app.services.domain_events import emit_domain_event

router = APIRouter(prefix="/api/v1/reps", tags=["rep-settings"])


class GhostModeStatus(BaseModel):
    """Ghost mode status response."""
    rep_id: str = Field(..., description="Sales rep ID")
    ghost_mode_enabled: bool = Field(..., description="Whether ghost mode is enabled")
    recording_mode: str = Field(..., description="Current recording mode (normal/ghost/off)")
    updated_at: Optional[datetime] = Field(None, description="When ghost mode was last updated")


class GhostModeToggleRequest(BaseModel):
    """Request body for toggling ghost mode."""
    enabled: Optional[bool] = Field(None, description="Set ghost mode enabled (if None, toggles)")


@router.get("/{rep_id}/ghost-mode", response_model=APIResponse[GhostModeStatus])
@require_role("manager", "csr", "sales_rep")
async def get_ghost_mode_status(
    request: Request,
    rep_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[GhostModeStatus]:
    """
    Get ghost mode status for a rep.
    
    Reps can only view their own status unless caller is manager/admin.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "user_role", None)
    
    # Check permissions: rep can only view their own, managers can view any
    if user_role == "sales_rep" and rep_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code=ErrorCodes.FORBIDDEN,
                message="You can only view your own ghost mode status",
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Get rep
    rep = db.query(SalesRep).filter(
        SalesRep.user_id == rep_id,
        SalesRep.company_id == tenant_id
    ).first()
    
    if not rep:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Sales rep not found",
                details={"rep_id": rep_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Determine ghost mode status
    ghost_mode_enabled = rep.recording_mode == RecordingMode.GHOST
    
    response = GhostModeStatus(
        rep_id=rep_id,
        ghost_mode_enabled=ghost_mode_enabled,
        recording_mode=rep.recording_mode.value,
        updated_at=datetime.utcnow(),  # TODO: Add updated_at field to SalesRep if needed
    )
    
    return APIResponse(data=response)


@router.post("/{rep_id}/ghost-mode/toggle", response_model=APIResponse[GhostModeStatus])
@require_role("manager", "csr", "sales_rep")
async def toggle_ghost_mode(
    request: Request,
    rep_id: str,
    payload: GhostModeToggleRequest,
    db: Session = Depends(get_db),
) -> APIResponse[GhostModeStatus]:
    """
    Toggle ghost mode for a rep.
    
    Reps can only toggle their own mode unless caller is manager/admin.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "user_role", None)
    
    # Check permissions: rep can only toggle their own, managers can toggle any
    if user_role == "sales_rep" and rep_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code=ErrorCodes.FORBIDDEN,
                message="You can only toggle your own ghost mode",
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Get rep
    rep = db.query(SalesRep).filter(
        SalesRep.user_id == rep_id,
        SalesRep.company_id == tenant_id
    ).first()
    
    if not rep:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Sales rep not found",
                details={"rep_id": rep_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Determine new mode
    if payload.enabled is not None:
        # Explicit set
        new_mode = RecordingMode.GHOST if payload.enabled else RecordingMode.NORMAL
    else:
        # Toggle
        if rep.recording_mode == RecordingMode.GHOST:
            new_mode = RecordingMode.NORMAL
        else:
            new_mode = RecordingMode.GHOST
    
    # Update rep
    old_mode = rep.recording_mode
    rep.recording_mode = new_mode
    db.commit()
    db.refresh(rep)
    
    # Emit event
    emit_domain_event(
        event_name="rep.ghost_mode_changed",
        tenant_id=tenant_id,
        lead_id=None,
        payload={
            "rep_id": rep_id,
            "company_id": tenant_id,
            "old_mode": old_mode.value,
            "new_mode": new_mode.value,
            "changed_by": user_id,
        },
    )
    
    response = GhostModeStatus(
        rep_id=rep_id,
        ghost_mode_enabled=(new_mode == RecordingMode.GHOST),
        recording_mode=new_mode.value,
        updated_at=datetime.utcnow(),
    )
    
    return APIResponse(data=response)


