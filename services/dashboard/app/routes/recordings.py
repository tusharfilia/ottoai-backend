"""
Recording Session APIs for Sales Rep app.

Simplified endpoints for starting and stopping recording sessions.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.rbac import require_role
from app.middleware.tenant import get_tenant_id
from app.models.recording_session import RecordingSession
from app.services.recording_session_service import RecordingSessionService, RecordingSessionError
from app.schemas.responses import APIResponse
from app.obs.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/recordings", tags=["recordings"])


class StartRecordingSessionRequest(BaseModel):
    """Request body for starting a recording session."""
    appointment_id: str = Field(..., description="Appointment ID to record")


class StopRecordingSessionRequest(BaseModel):
    """Request body for stopping a recording session."""
    audio_url: str = Field(..., description="URL to the recorded audio file")


class RecordingSessionResponse(BaseModel):
    """Response schema for recording session."""
    id: str
    appointment_id: str
    started_at: str
    ended_at: str | None
    status: str
    audio_url: str | None
    shunya_job_id: str | None
    
    class Config:
        from_attributes = True


@router.post("/sessions/start", response_model=APIResponse[RecordingSessionResponse])
@require_role("sales_rep")
async def start_recording_session(
    request: Request,
    body: StartRecordingSessionRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
) -> APIResponse[RecordingSessionResponse]:
    """
    Start a recording session for an appointment.
    
    **Roles**: sales_rep
    
    **Request Body**:
    - `appointment_id`: Appointment ID to record
    
    **Returns**: RecordingSessionResponse with session details.
    
    **Validations**:
    - Appointment exists and belongs to tenant
    - Rep owns the appointment (assigned_rep_id == rep_id)
    - Appointment is scheduled (allows 30-minute early start window)
    - No existing active session for this appointment
    
    **Errors**:
    - 400: Appointment not found, not assigned to rep, too early, or session already exists
    - 401: User ID not found
    """
    try:
        # P0 FIX: Check idempotency if key provided
        from app.services.write_idempotency import check_write_idempotency, store_write_idempotency
        if idempotency_key:
            is_duplicate, _ = check_write_idempotency(
                db=db,
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                operation_type="recording_session_start"
            )
            if is_duplicate:
                logger.info(f"Idempotency key {idempotency_key} already processed, returning success")
                # Return success response for duplicate (operation already completed)
                return APIResponse(
                    success=True, 
                    data={"status": "already_processed", "idempotency_key": idempotency_key}
                )
        
        # Get rep user ID from request state
        rep_id = getattr(request.state, 'user_id', None)
        if not rep_id:
            raise HTTPException(status_code=401, detail="User ID not found in request")
        
        # P0 FIX: Verify tenant ownership of appointment
        from app.core.tenant import verify_tenant_ownership
        from app.models.appointment import Appointment
        if not verify_tenant_ownership(db, Appointment, body.appointment_id, tenant_id):
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        # Call service
        service = RecordingSessionService(db)
        session = await service.start_session(
            tenant_id=tenant_id,
            rep_id=rep_id,
            appointment_id=body.appointment_id
        )
        
        # Convert to response schema
        response = RecordingSessionResponse(
            id=session.id,
            appointment_id=session.appointment_id,
            started_at=session.started_at.isoformat(),
            ended_at=session.ended_at.isoformat() if session.ended_at else None,
            status=session.status,
            audio_url=session.audio_url,
            shunya_job_id=session.shunya_analysis_job_id
        )
        
        return APIResponse(success=True, data=response)
    
    except RecordingSessionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting recording session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start recording session: {str(e)}")


@router.post("/sessions/{session_id}/stop", response_model=APIResponse[RecordingSessionResponse])
@require_role("sales_rep")
async def stop_recording_session(
    request: Request,
    session_id: str,
    body: StopRecordingSessionRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
) -> APIResponse[RecordingSessionResponse]:
    """
    Stop a recording session and trigger Shunya analysis.
    
    **Roles**: sales_rep
    
    **Path Parameters**:
    - `session_id`: Recording session ID
    
    **Request Body**:
    - `audio_url`: URL to the recorded audio file
    
    **Returns**: Updated RecordingSessionResponse.
    
    **Validations**:
    - Session exists and belongs to tenant
    - Rep owns the session
    - Session status is "recording"
    
    **Errors**:
    - 400: Session not found, not owned by rep, or not in recording status
    - 401: User ID not found
    - 500: Failed to trigger Shunya analysis (session marked as failed)
    """
    try:
        # P0 FIX: Check idempotency if key provided
        from app.services.write_idempotency import check_write_idempotency, store_write_idempotency
        if idempotency_key:
            is_duplicate, _ = check_write_idempotency(
                db=db,
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                operation_type="recording_session_stop"
            )
            if is_duplicate:
                logger.info(f"Idempotency key {idempotency_key} already processed, returning success")
                # Return success response for duplicate (operation already completed)
                return APIResponse(
                    success=True, 
                    data={"status": "already_processed", "idempotency_key": idempotency_key}
                )
        
        # P0 FIX: Verify tenant ownership of session
        from app.core.tenant import verify_tenant_ownership
        from app.models.recording_session import RecordingSession as RecordingSessionModel
        if not verify_tenant_ownership(db, RecordingSessionModel, session_id, tenant_id):
            raise HTTPException(status_code=404, detail="Recording session not found")
        
        # Get rep user ID from request state
        rep_id = getattr(request.state, 'user_id', None)
        if not rep_id:
            raise HTTPException(status_code=401, detail="User ID not found in request")
        
        # Call service
        service = RecordingSessionService(db)
        session = await service.stop_session(
            tenant_id=tenant_id,
            session_id=session_id,
            rep_id=rep_id,
            audio_url=body.audio_url
        )
        
        # Convert to response schema
        response = RecordingSessionResponse(
            id=session.id,
            appointment_id=session.appointment_id,
            started_at=session.started_at.isoformat(),
            ended_at=session.ended_at.isoformat() if session.ended_at else None,
            status=session.status,
            audio_url=session.audio_url,
            shunya_job_id=session.shunya_analysis_job_id
        )
        
        # P0 FIX: Store idempotency key if provided
        if idempotency_key:
            response_data = response.dict() if hasattr(response, 'dict') else response
            store_write_idempotency(
                db=db,
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                operation_type="recording_session_stop",
                response=response_data
            )
        
        return APIResponse(success=True, data=response)
    
    except RecordingSessionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping recording session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to stop recording session: {str(e)}")

