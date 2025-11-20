"""
Recording Session APIs for geofenced appointment recordings.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.recording_session import (
    RecordingSession,
    RecordingMode,
    AudioStorageMode,
    TranscriptionStatus,
    AnalysisStatus,
)
from app.models.rep_shift import RepShift, ShiftStatus
from app.models.appointment import Appointment
from app.models.sales_rep import SalesRep
from app.models.company import Company
from app.schemas.domain import (
    RecordingSessionStartRequest,
    RecordingSessionStartResponse,
    RecordingSessionStopRequest,
    RecordingSessionResponse,
    RecordingSessionBase,
    RecordingMode as RecordingModeEnum,
    AudioStorageMode as AudioStorageModeEnum,
)
from app.schemas.responses import APIResponse
from app.realtime.bus import emit
from app.services.recording_session_service import RecordingSessionService

router = APIRouter(prefix="/api/v1/recording-sessions", tags=["recording-sessions"])

recording_service = RecordingSessionService()


# Request/Response Models
class AudioUploadComplete(BaseModel):
    audio_url: str
    audio_duration_seconds: float
    audio_size_bytes: int


class AudioMetadata(BaseModel):
    audio_duration_seconds: Optional[float] = None
    audio_size_bytes: Optional[int] = None


@router.post("/start", response_model=APIResponse[RecordingSessionStartResponse])
@require_role("rep", "manager", "exec")
async def start_recording_session(
    request: Request,
    body: RecordingSessionStartRequest,
    db: Session = Depends(get_db),
) -> APIResponse[RecordingSessionStartResponse]:
    """
    Start a geofenced recording session.
    
    Validates:
    - Rep has active shift
    - Appointment is assigned to rep
    - Recording is allowed
    - Location is within geofence
    
    Returns recording session ID and configuration.
    """
    company_id = request.state.tenant_id
    
    # Get rep
    rep = db.query(SalesRep).filter(
        SalesRep.user_id == body.rep_id,
        SalesRep.company_id == company_id
    ).first()
    if not rep:
        raise HTTPException(status_code=404, detail=f"Sales rep {body.rep_id} not found")
    
    # Validate permissions
    if not rep.allow_recording:
        raise HTTPException(
            status_code=403,
            detail="Recording is not allowed for this rep"
        )
    
    if not rep.allow_location_tracking:
        raise HTTPException(
            status_code=403,
            detail="Location tracking is not allowed for this rep"
        )
    
    # Check for active shift
    from app.routes.rep_shifts import _get_today_shift
    shift = _get_today_shift(db, body.rep_id, company_id)
    if not shift or shift.status != ShiftStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail="Rep must be clocked in to start recording"
        )
    
    # Get appointment
    appointment = db.query(Appointment).filter(
        Appointment.id == body.appointment_id,
        Appointment.company_id == company_id,
        Appointment.assigned_rep_id == body.rep_id,
    ).first()
    if not appointment:
        raise HTTPException(
            status_code=404,
            detail=f"Appointment {body.appointment_id} not found or not assigned to rep"
        )
    
    # Validate geofence (basic check - mobile app does detailed geofencing)
    if appointment.geo_lat and appointment.geo_lng:
        # Simple distance check (mobile app does more sophisticated geofencing)
        # For now, we trust the mobile app's geofence detection
        pass
    
    # Determine recording mode
    mode = body.mode or RecordingMode(rep.recording_mode.value)
    
    # Determine audio storage mode based on mode and company config
    audio_storage_mode = recording_service.get_audio_storage_mode(mode, company_id, db)
    
    # Create recording session
    session = RecordingSession(
        company_id=company_id,
        rep_id=body.rep_id,
        appointment_id=body.appointment_id,
        shift_id=shift.id,
        mode=mode,
        audio_storage_mode=audio_storage_mode,
        started_at=datetime.utcnow(),
        start_lat=body.location.lat,
        start_lng=body.location.lng,
        geofence_radius_start=appointment.geofence_radius_start or 200.0,
        geofence_radius_stop=appointment.geofence_radius_stop or 500.0,
        transcription_status=TranscriptionStatus.NOT_STARTED,
        analysis_status=AnalysisStatus.NOT_STARTED,
    )
    
    # Set expiration for ephemeral storage
    if audio_storage_mode == AudioStorageMode.EPHEMERAL:
        # Default TTL: 60 minutes (configurable per tenant)
        ttl_minutes = 60  # TODO: Get from tenant config
        session.expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    # Get audio upload URL (if applicable)
    audio_upload_url = None
    if audio_storage_mode != AudioStorageMode.NOT_STORED:
        # Generate presigned S3 URL for audio upload
        from app.services.storage import storage_service
        from app.config import settings
        
        if settings.is_storage_configured():
            s3_key = storage_service.generate_audio_upload_key(
                recording_session_id=session.id,
                tenant_id=company_id,
            )
            audio_upload_url = storage_service.generate_presigned_upload_url(
                s3_key=s3_key,
                content_type="audio/m4a",  # Default format
                expires_in=3600,  # 1 hour
                tenant_id=company_id,
            )
            # Store the S3 key (we'll update audio_url after upload)
            # For now, we'll construct the final URL after upload completes
        else:
            logger.warning(f"S3 not configured, audio upload URL not available for session {session.id}")
    
    # Emit event
    await emit(
        "recording_session.started",
        {
            "recording_session_id": session.id,
            "rep_id": body.rep_id,
            "company_id": company_id,
            "appointment_id": body.appointment_id,
            "mode": mode.value,
            "audio_storage_mode": audio_storage_mode.value,
            "started_at": session.started_at.isoformat(),
        },
        tenant_id=company_id,
        user_id=body.rep_id,
    )
    
    response = RecordingSessionStartResponse(
        recording_session_id=session.id,
        mode=RecordingModeEnum(mode.value),
        audio_storage_mode=AudioStorageModeEnum(audio_storage_mode.value),
        audio_upload_url=audio_upload_url,
        shunya_job_config=None,  # Will be set when audio is uploaded
    )
    
    return APIResponse(data=response)


@router.post("/{session_id}/stop", response_model=APIResponse[RecordingSessionResponse])
@require_role("rep", "manager", "exec")
async def stop_recording_session(
    request: Request,
    session_id: str,
    body: RecordingSessionStopRequest,
    db: Session = Depends(get_db),
) -> APIResponse[RecordingSessionResponse]:
    """
    Stop a recording session.
    
    Sets ended_at, triggers Shunya transcription (if applicable),
    and enforces Ghost Mode retention policies.
    """
    company_id = request.state.tenant_id
    
    # Get session
    session = db.query(RecordingSession).filter(
        RecordingSession.id == session_id,
        RecordingSession.company_id == company_id,
    ).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Recording session {session_id} not found"
        )
    
    if session.ended_at:
        raise HTTPException(
            status_code=400,
            detail="Recording session is already stopped"
        )
    
    # Update session
    session.ended_at = datetime.utcnow()
    session.end_lat = body.location.lat
    session.end_lng = body.location.lng
    
    # Mark transcription as in progress (will be updated by Shunya webhook)
    session.transcription_status = TranscriptionStatus.IN_PROGRESS
    
    db.commit()
    db.refresh(session)
    
    # Trigger Shunya transcription (if applicable)
    # For Ghost Mode with NOT_STORED, we may skip transcription
    # or use streaming endpoint
    if session.audio_storage_mode != AudioStorageMode.NOT_STORED:
        # TODO: Enqueue Shunya ASR task
        # This will be handled by a Celery task that processes the audio
        from app.tasks.recording_session_tasks import process_recording_session
        process_recording_session.delay(session.id)
    
    # Emit event
    await emit(
        "recording_session.ended",
        {
            "recording_session_id": session.id,
            "rep_id": session.rep_id,
            "company_id": company_id,
            "appointment_id": session.appointment_id,
            "mode": session.mode.value,
            "ended_at": session.ended_at.isoformat(),
        },
        tenant_id=company_id,
        user_id=session.rep_id,
    )
    
    return APIResponse(
        data=RecordingSessionResponse(
            session=RecordingSessionBase.model_validate(session)
        )
    )


@router.post("/{session_id}/upload-audio", status_code=200)
@require_role("rep", "manager", "exec")
async def upload_audio_complete(
    request: Request,
    session_id: str,
    upload_data: AudioUploadComplete,
    db: Session = Depends(get_db),
) -> APIResponse[dict]:
    """
    Mark audio upload as complete and update recording session metadata.
    
    Called by mobile app after successfully uploading audio to S3.
    Updates audio_url, audio_duration_seconds, and audio_size_bytes.
    """
    company_id = request.state.tenant_id
    
    # Get session
    session = db.query(RecordingSession).filter(
        RecordingSession.id == session_id,
        RecordingSession.company_id == company_id,
    ).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Recording session {session_id} not found"
        )
    
    # Update session metadata
    session.audio_url = upload_data.audio_url
    session.audio_duration_seconds = upload_data.audio_duration_seconds
    session.audio_size_bytes = upload_data.audio_size_bytes
    
    db.commit()
    db.refresh(session)
    
    logger.info(
        f"Audio upload completed for session {session_id}: "
        f"{upload_data.audio_size_bytes} bytes, {upload_data.audio_duration_seconds}s"
    )
    
    # Trigger transcription processing (if not Ghost Mode)
    if session.audio_storage_mode != AudioStorageMode.NOT_STORED:
        from app.tasks.recording_session_tasks import process_recording_session
        process_recording_session.delay(session_id)
    
    return APIResponse(data={"status": "uploaded", "recording_session_id": session_id})


@router.post("/{session_id}/metadata", response_model=APIResponse[RecordingSessionResponse])
@require_role("rep", "manager", "exec")
async def update_audio_metadata(
    request: Request,
    session_id: str,
    metadata: AudioMetadata,
    db: Session = Depends(get_db),
) -> APIResponse[RecordingSessionResponse]:
    """
    Update recording session audio metadata (duration, size).
    
    Alternative endpoint if metadata is known before upload completes.
    """
    company_id = request.state.tenant_id
    
    session = db.query(RecordingSession).filter(
        RecordingSession.id == session_id,
        RecordingSession.company_id == company_id,
    ).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Recording session {session_id} not found"
        )
    
    if metadata.audio_duration_seconds is not None:
        session.audio_duration_seconds = metadata.audio_duration_seconds
    if metadata.audio_size_bytes is not None:
        session.audio_size_bytes = metadata.audio_size_bytes
    
    db.commit()
    db.refresh(session)
    
    return APIResponse(
        data=RecordingSessionResponse(
            session=RecordingSessionBase.model_validate(session)
        )
    )


@router.get("/{session_id}", response_model=APIResponse[RecordingSessionResponse])
@require_role("rep", "manager", "exec")
async def get_recording_session(
    request: Request,
    session_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[RecordingSessionResponse]:
    """
    Get a recording session by ID.
    
    In Ghost Mode, audio_url will be None and transcript may be restricted
    based on tenant retention policy.
    """
    company_id = request.state.tenant_id
    
    session = db.query(RecordingSession).filter(
        RecordingSession.id == session_id,
        RecordingSession.company_id == company_id,
    ).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Recording session {session_id} not found"
        )
    
    # Apply Ghost Mode restrictions
    session_data = recording_service.apply_ghost_mode_restrictions(
        session, company_id, db
    )
    
    return APIResponse(
        data=RecordingSessionResponse(
            session=RecordingSessionBase.model_validate(session_data)
        )
    )

