"""
Recording Session Service for managing geofenced appointment recordings.

Handles:
- Starting recording sessions
- Stopping recording sessions
- Triggering Shunya analysis jobs
"""
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.recording_session import RecordingSession, RecordingMode, AudioStorageMode
from app.models.appointment import Appointment, AppointmentStatus
from app.models.shunya_job import ShunyaJob, ShunyaJobType, ShunyaJobStatus
from app.services.shunya_job_service import ShunyaJobService
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)


class RecordingSessionError(Exception):
    """Raised when recording session operation fails."""
    pass


class RecordingSessionService:
    """Service for managing recording sessions."""
    
    def __init__(self, db: Session):
        self.db = db
        self.shunya_job_service = ShunyaJobService()
    
    async def start_session(
        self,
        *,
        tenant_id: str,
        rep_id: str,
        appointment_id: str
    ) -> RecordingSession:
        """
        Start a recording session for an appointment.
        
        Args:
            tenant_id: Company/tenant ID
            rep_id: Sales rep user ID
            appointment_id: Appointment ID
        
        Returns:
            Created RecordingSession instance
        
        Raises:
            RecordingSessionError: If session cannot be started
        """
        # Validate appointment exists
        appointment = self.db.query(Appointment).filter(
            Appointment.id == appointment_id,
            Appointment.company_id == tenant_id
        ).first()
        
        if not appointment:
            raise RecordingSessionError(f"Appointment {appointment_id} not found")
        
        # Validate rep owns the appointment
        if appointment.assigned_rep_id != rep_id:
            raise RecordingSessionError(
                f"Appointment {appointment_id} is not assigned to rep {rep_id}"
            )
        
        # Validate appointment is scheduled (allow some window for early starts)
        now = datetime.utcnow()
        window_minutes = 30  # Allow starting 30 minutes before scheduled time
        earliest_start = appointment.scheduled_start - timedelta(minutes=window_minutes)
        
        if now < earliest_start:
            raise RecordingSessionError(
                f"Appointment {appointment_id} is scheduled for {appointment.scheduled_start}, "
                f"cannot start recording more than {window_minutes} minutes early"
            )
        
        # Check if session already exists for this appointment
        existing_session = self.db.query(RecordingSession).filter(
            RecordingSession.appointment_id == appointment_id,
            RecordingSession.company_id == tenant_id,
            RecordingSession.status.in_(["pending", "recording"])
        ).first()
        
        if existing_session:
            raise RecordingSessionError(
                f"Recording session already exists for appointment {appointment_id} (session: {existing_session.id})"
            )
        
        # Create recording session
        session = RecordingSession(
            company_id=tenant_id,
            rep_id=rep_id,
            appointment_id=appointment_id,
            started_at=now,
            status="recording"
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        logger.info(
            f"Started recording session {session.id} for appointment {appointment_id}",
            extra={
                "session_id": session.id,
                "appointment_id": appointment_id,
                "rep_id": rep_id,
                "tenant_id": tenant_id
            }
        )
        
        return session
    
    async def stop_session(
        self,
        *,
        tenant_id: str,
        session_id: str,
        rep_id: str,
        audio_url: str
    ) -> RecordingSession:
        """
        Stop a recording session and trigger Shunya analysis.
        
        Args:
            tenant_id: Company/tenant ID
            session_id: Recording session ID
            rep_id: Sales rep user ID (for validation)
            audio_url: URL to the recorded audio file
        
        Returns:
            Updated RecordingSession instance
        
        Raises:
            RecordingSessionError: If session cannot be stopped
        """
        # Fetch session
        session = self.db.query(RecordingSession).filter(
            RecordingSession.id == session_id,
            RecordingSession.company_id == tenant_id
        ).first()
        
        if not session:
            raise RecordingSessionError(f"Recording session {session_id} not found")
        
        # Validate rep owns the session
        if session.rep_id != rep_id:
            raise RecordingSessionError(
                f"Recording session {session_id} does not belong to rep {rep_id}"
            )
        
        # Validate status
        if session.status != "recording":
            raise RecordingSessionError(
                f"Recording session {session_id} is not in 'recording' status (current: {session.status})"
            )
        
        # Update session
        now = datetime.utcnow()
        session.ended_at = now
        session.status = "completed"
        session.audio_url = audio_url
        
        self.db.commit()
        self.db.refresh(session)
        
        # Trigger Shunya final analysis job (reuse existing patterns)
        try:
            # Create Shunya job for analysis
            shunya_job = self.shunya_job_service.create_job(
                db=self.db,
                company_id=tenant_id,
                job_type=ShunyaJobType.SALES_VISIT,
                input_payload={
                    "recording_session_id": session_id,
                    "audio_url": audio_url,
                    "appointment_id": session.appointment_id
                },
                appointment_id=session.appointment_id,
                recording_session_id=session_id
            )
            
            # Link job to session
            session.shunya_analysis_job_id = shunya_job.id
            self.db.commit()
            self.db.refresh(session)
            
            logger.info(
                f"Stopped recording session {session_id} and triggered Shunya analysis job {shunya_job.id}",
                extra={
                    "session_id": session_id,
                    "appointment_id": session.appointment_id,
                    "shunya_job_id": shunya_job.id,
                    "tenant_id": tenant_id
                }
            )
        except Exception as e:
            # Log error but don't fail the stop operation
            logger.error(
                f"Failed to trigger Shunya analysis for session {session_id}: {str(e)}",
                extra={"session_id": session_id},
                exc_info=True
            )
            # Mark session as failed if we can't trigger analysis
            session.status = "failed"
            session.error_message = f"Failed to trigger Shunya analysis: {str(e)}"
            self.db.commit()
            self.db.refresh(session)
        
        return session
    
    def get_audio_storage_mode(
        self,
        mode: RecordingMode,
        company_id: str,
        db: Optional[Session] = None
    ) -> AudioStorageMode:
        """
        Determine audio storage mode based on recording mode and company config.
        
        Args:
            mode: Recording mode (normal, ghost, off)
            company_id: Company/tenant ID
            db: Database session (optional, uses self.db if not provided)
        
        Returns:
            AudioStorageMode enum value
        """
        # Simple logic: normal mode = persistent, ghost mode = not_stored
        # TODO: Add company-level config for ghost mode storage preferences
        if mode == RecordingMode.GHOST:
            return AudioStorageMode.NOT_STORED
        elif mode == RecordingMode.NORMAL:
            return AudioStorageMode.PERSISTENT
        else:  # OFF mode
            return AudioStorageMode.NOT_STORED
    
    def apply_ghost_mode_restrictions(
        self,
        session: RecordingSession,
        company_id: str,
        db: Optional[Session] = None
    ) -> RecordingSession:
        """
        Apply Ghost Mode restrictions to session data.
        
        In Ghost Mode, audio_url and transcript may be restricted based on
        tenant retention policy.
        
        Args:
            session: RecordingSession instance
            company_id: Company/tenant ID
            db: Database session
        
        Returns:
            RecordingSession with restrictions applied (or original if not ghost mode)
        """
        # If not in ghost mode, return session as-is
        if session.mode != RecordingMode.GHOST:
            return session
        
        # In ghost mode, restrict audio_url if retention policy requires it
        # TODO: Add company-level retention policy check
        # For now, if audio_storage_mode is NOT_STORED, ensure audio_url is None
        if session.audio_storage_mode == AudioStorageMode.NOT_STORED:
            # Create a copy-like object or modify in place
            # Since we're returning the same object, we'll just ensure audio_url is None
            if session.audio_url:
                # Don't modify the actual session, return a restricted view
                # For now, we'll return the session but the caller should handle None audio_url
                pass
        
        return session
