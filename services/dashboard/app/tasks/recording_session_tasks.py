"""
Recording Session background tasks for processing geofenced appointment recordings.
"""
from celery import current_task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.pii_masking import PIISafeLogger
from app.database import SessionLocal
from app.models.recording_session import (
    RecordingSession,
    RecordingMode,
    AudioStorageMode,
    TranscriptionStatus,
    AnalysisStatus,
)
from app.services.uwc_client import UWCClient
from app.services.recording_session_service import RecordingSessionService
from app.realtime.bus import emit

logger = PIISafeLogger(__name__)
recording_service = RecordingSessionService()


@celery_app.task(bind=True, max_retries=3)
def process_recording_session(self, recording_session_id: str):
    """
    Process a recording session: transcribe audio and run analysis.
    
    Handles Ghost Mode restrictions:
    - If audio_storage_mode is NOT_STORED, audio_url will be None
    - In Ghost Mode, we may skip transcription or use streaming endpoint
    
    Args:
        recording_session_id: UUID of the RecordingSession
    """
    db = SessionLocal()
    try:
        session = db.query(RecordingSession).filter(
            RecordingSession.id == recording_session_id
        ).first()
        
        if not session:
            logger.error(f"Recording session {recording_session_id} not found")
            return {"success": False, "error": "Session not found"}
        
        # Check if audio is available
        if session.audio_storage_mode == AudioStorageMode.NOT_STORED:
            # Ghost Mode: No raw audio stored
            # We can't transcribe, but we can still run analysis on metadata
            logger.info(
                f"Recording session {recording_session_id} is in Ghost Mode (NOT_STORED). "
                "Skipping transcription, storing only aggregates."
            )
            
            # Mark transcription as not applicable
            session.transcription_status = TranscriptionStatus.NOT_STARTED
            session.analysis_status = AnalysisStatus.COMPLETED  # No analysis possible without audio
            
            db.commit()
            
            # Emit event (emit is synchronous, safe to call from Celery task)
            emit(
                "recording_session.transcription.completed",
                {
                    "recording_session_id": recording_session_id,
                    "rep_id": session.rep_id,
                    "company_id": session.company_id,
                    "appointment_id": session.appointment_id,
                    "mode": session.mode.value,
                    "skipped": True,
                    "reason": "ghost_mode_not_stored",
                },
                tenant_id=session.company_id,
                user_id=session.rep_id,
            )
                {
                    "recording_session_id": recording_session_id,
                    "rep_id": session.rep_id,
                    "company_id": session.company_id,
                    "appointment_id": session.appointment_id,
                    "mode": session.mode.value,
                    "skipped": True,
                    "reason": "ghost_mode_not_stored",
                },
                tenant_id=session.company_id,
                user_id=session.rep_id,
            )
            
            return {
                "success": True,
                "mode": session.mode.value,
                "transcription_skipped": True,
                "reason": "ghost_mode_not_stored",
            }
        
        # Normal or Ephemeral mode: Audio is available
        if not session.audio_url:
            logger.warning(
                f"Recording session {recording_session_id} has no audio_url. "
                "Waiting for audio upload..."
            )
            # Retry later if audio hasn't been uploaded yet
            raise self.retry(countdown=30)
        
        # Update status
        session.transcription_status = TranscriptionStatus.IN_PROGRESS
        db.commit()
        
        # Transcribe with Shunya/UWC
        try:
            uwc_client = UWCClient()
            result = uwc_client.transcribe_audio(session.audio_url)
            
            if result and result.get("transcript"):
                # Store transcription result
                # TODO: Store transcript in a separate table or attach to session
                # For now, we'll store it in the session's notes or a related model
                
                session.transcription_status = TranscriptionStatus.COMPLETED
                session.shunya_asr_job_id = result.get("job_id")
                
                # Run analysis
                session.analysis_status = AnalysisStatus.IN_PROGRESS
                db.commit()
                
                # Analyze transcript
                analysis_result = uwc_client.query_rag(
                    query=f"Analyze this appointment recording transcript for coaching insights, "
                          f"objections, and SOP compliance: {result['transcript']}",
                    tenant_id=session.company_id
                )
                
                if analysis_result:
                    session.analysis_status = AnalysisStatus.COMPLETED
                    session.shunya_analysis_job_id = analysis_result.get("job_id")
                    
                    # TODO: Store analysis results in Appointment or Lead
                    # For now, we'll just mark as completed
                    
                    db.commit()
                    
                    # Emit events
                    emit(
                        "recording_session.transcription.completed",
                        {
                            "recording_session_id": recording_session_id,
                            "rep_id": session.rep_id,
                            "company_id": session.company_id,
                            "appointment_id": session.appointment_id,
                            "mode": session.mode.value,
                            "transcript_length": len(result.get("transcript", "")),
                        },
                        tenant_id=session.company_id,
                        user_id=session.rep_id,
                    )
                    
                    emit(
                        "recording_session.analysis.completed",
                        {
                            "recording_session_id": recording_session_id,
                            "rep_id": session.rep_id,
                            "company_id": session.company_id,
                            "appointment_id": session.appointment_id,
                            "mode": session.mode.value,
                        },
                        tenant_id=session.company_id,
                        user_id=session.rep_id,
                    )
                    
                    logger.info(
                        f"Successfully processed recording session {recording_session_id}"
                    )
                    
                    return {
                        "success": True,
                        "transcription_status": "completed",
                        "analysis_status": "completed",
                    }
                else:
                    session.analysis_status = AnalysisStatus.FAILED
                    session.error_message = "Analysis returned no results"
                    db.commit()
                    return {
                        "success": False,
                        "error": "Analysis returned no results",
                    }
            else:
                session.transcription_status = TranscriptionStatus.FAILED
                session.error_message = "Transcription returned no transcript"
                db.commit()
                return {
                    "success": False,
                    "error": "Transcription returned no transcript",
                }
                
        except Exception as e:
            logger.error(
                f"Shunya processing failed for recording session {recording_session_id}: {str(e)}"
            )
            session.transcription_status = TranscriptionStatus.FAILED
            session.error_message = str(e)
            db.commit()
            
            # Emit failure event
            emit(
                "recording_session.transcription.failed",
                {
                    "recording_session_id": recording_session_id,
                    "rep_id": session.rep_id,
                    "company_id": session.company_id,
                    "appointment_id": session.appointment_id,
                    "error": str(e),
                },
                tenant_id=session.company_id,
                user_id=session.rep_id,
            )
            
            # Retry with exponential backoff
            raise self.retry(countdown=60 * (2 ** self.request.retries), exc=e)
            
    except Exception as e:
        logger.error(f"Error processing recording session {recording_session_id}: {str(e)}")
        raise self.retry(countdown=60 * (2 ** self.request.retries), exc=e)
    finally:
        db.close()


@celery_app.task
def cleanup_ephemeral_sessions():
    """
    Periodic task to clean up expired ephemeral recording sessions.
    
    Runs every hour to delete sessions with expires_at < now.
    """
    from app.services.recording_session_service import RecordingSessionService
    
    db = SessionLocal()
    try:
        service = RecordingSessionService()
        count = service.cleanup_ephemeral_sessions(db)
        logger.info(f"Cleaned up {count} expired ephemeral recording sessions")
        return {"success": True, "cleaned_up": count}
    except Exception as e:
        logger.error(f"Error cleaning up ephemeral sessions: {str(e)}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()

