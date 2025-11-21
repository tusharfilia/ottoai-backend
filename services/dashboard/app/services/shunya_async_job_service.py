"""
Shunya Async Job Service for CSR calls and sales visits.

Handles async job creation and processing using ShunyaJob model.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import uuid4
import asyncio

from sqlalchemy.orm import Session

from app.models.shunya_job import ShunyaJob, ShunyaJobType, ShunyaJobStatus
from app.models.call import Call
from app.models.recording_session import RecordingSession
from app.services.shunya_job_service import shunya_job_service
from app.services.uwc_client import get_uwc_client
from app.utils.shunya_job_utils import extract_shunya_job_id
from app.core.pii_masking import PIISafeLogger
from app.realtime.bus import emit

logger = PIISafeLogger(__name__)


class ShunyaAsyncJobService:
    """
    Service for creating and managing async Shunya jobs.
    
    This service creates ShunyaJob records and triggers async processing,
    replacing fixed-delay synchronous calls.
    """
    
    def __init__(self):
        self.uwc_client = get_uwc_client()
    
    async def submit_csr_call_job(
        self,
        db: Session,
        call_id: int,
        audio_url: str,
        company_id: str,
        request_id: Optional[str] = None,
    ) -> ShunyaJob:
        """
        Submit a CSR call for async processing via Shunya.
        
        Creates a ShunyaJob and triggers async polling.
        
        Args:
            db: Database session
            call_id: Call ID
            audio_url: Publicly accessible audio URL
            company_id: Company/tenant ID
            request_id: Optional correlation ID
        
        Returns:
            Created ShunyaJob instance
        """
        request_id = request_id or str(uuid4())
        
        # Get call record
        call = db.query(Call).filter(Call.call_id == call_id).first()
        if not call:
            raise ValueError(f"Call {call_id} not found")
        
        # Create input payload
        input_payload = {
            "call_id": call_id,
            "audio_url": audio_url,
            "call_type": "csr_call",
        }
        
        # Create ShunyaJob
        job = shunya_job_service.create_job(
            db=db,
            company_id=company_id,
            job_type=ShunyaJobType.CSR_CALL,
            input_payload=input_payload,
            contact_card_id=call.contact_card_id,
            lead_id=str(call.lead_id) if call.lead_id else None,
            call_id=call_id,
        )
        db.flush()
        
        # Submit transcription job to Shunya
        try:
            transcript_response = await self.uwc_client.transcribe_audio(
                company_id=company_id,
                request_id=request_id,
                audio_url=audio_url,
                language="en-US",
            )
            
            # Extract job ID from response
            shunya_job_id = extract_shunya_job_id(transcript_response, job_type="transcription")
            
            if not shunya_job_id:
                logger.warning(
                    f"No job ID in Shunya transcription response for call {call_id}",
                    extra={"call_id": call_id, "response": transcript_response}
                )
                # Still create job, but without Shunya job ID
                # Polling will use call_id
            else:
                # Update job with Shunya job ID
                job.shunya_job_id = shunya_job_id
                db.commit()
                db.refresh(job)
            
            # Start analysis pipeline (also async)
            analysis_response = await self.uwc_client.start_analysis(
                company_id=company_id,
                request_id=request_id,
                call_id=call_id,
            )
            
            # Extract analysis job ID (may be different from transcription)
            analysis_job_id = extract_shunya_job_id(analysis_response, job_type="analysis")
            
            # For now, we'll poll using call_id
            # If analysis_job_id exists, we could create a separate job for it
            # For simplicity, we'll use the transcription job and poll for complete analysis
            
            # Mark job as running
            shunya_job_service.mark_running(db, job, shunya_job_id)
            
            db.commit()
            db.refresh(job)
            
            # Emit job created event
            emit(
                "shunya.job.created",
                {
                    "job_id": job.id,
                    "job_type": job.job_type.value,
                    "call_id": call_id,
                    "shunya_job_id": shunya_job_id,
                },
                tenant_id=company_id,
                lead_id=str(call.lead_id) if call.lead_id else None,
            )
            
            # Schedule polling task
            from app.tasks.shunya_job_polling_tasks import poll_shunya_job_status
            poll_shunya_job_status.delay(job.id)
            
            logger.info(
                f"Submitted CSR call {call_id} for async Shunya processing",
                extra={
                    "job_id": job.id,
                    "call_id": call_id,
                    "shunya_job_id": shunya_job_id,
                }
            )
            
            return job
            
        except Exception as e:
            logger.error(
                f"Error submitting CSR call {call_id} to Shunya: {str(e)}",
                exc_info=True
            )
            shunya_job_service.mark_failed(
                db,
                job,
                str(e),
                error_details={"exception": type(e).__name__},
                should_retry=True,
            )
            db.commit()
            raise
    
    async def submit_sales_visit_job(
        self,
        db: Session,
        recording_session_id: str,
        audio_url: Optional[str],
        company_id: str,
        request_id: Optional[str] = None,
    ) -> ShunyaJob:
        """
        Submit a sales visit for async processing via Shunya.
        
        Creates a ShunyaJob and triggers async polling.
        
        Args:
            db: Database session
            recording_session_id: RecordingSession ID
            audio_url: Publicly accessible audio URL (None in ghost mode)
            company_id: Company/tenant ID
            request_id: Optional correlation ID
        
        Returns:
            Created ShunyaJob instance
        """
        request_id = request_id or str(uuid4())
        
        # Get recording session
        session = db.query(RecordingSession).filter(
            RecordingSession.id == recording_session_id
        ).first()
        if not session:
            raise ValueError(f"Recording session {recording_session_id} not found")
        
        # Check if already has a job
        existing_job = db.query(ShunyaJob).filter(
            ShunyaJob.recording_session_id == recording_session_id,
            ShunyaJob.job_type == ShunyaJobType.SALES_VISIT,
            ShunyaJob.job_status.in_([ShunyaJobStatus.PENDING, ShunyaJobStatus.RUNNING]),
        ).first()
        
        if existing_job:
            logger.info(
                f"Recording session {recording_session_id} already has pending job {existing_job.id}",
                extra={
                    "recording_session_id": recording_session_id,
                    "existing_job_id": existing_job.id,
                }
            )
            return existing_job
        
        # Determine call_id from appointment (for Shunya API)
        call_id = None
        if session.appointment_id:
            appointment = db.query("Appointment").filter_by(id=session.appointment_id).first()
            # Appointment may have a call_id field or we may need to create a synthetic one
            # For now, use appointment ID as a reference
        
        # Create input payload
        input_payload = {
            "recording_session_id": recording_session_id,
            "appointment_id": session.appointment_id,
            "audio_url": audio_url,  # May be None in ghost mode
            "is_ghost_mode": session.mode.value == "ghost" if session.mode else False,
        }
        
        if call_id:
            input_payload["call_id"] = call_id
        
        # Create ShunyaJob
        job = shunya_job_service.create_job(
            db=db,
            company_id=company_id,
            job_type=ShunyaJobType.SALES_VISIT,
            input_payload=input_payload,
            contact_card_id=session.contact_card_id if hasattr(session, "contact_card_id") else None,
            lead_id=session.lead_id if hasattr(session, "lead_id") else None,
            appointment_id=session.appointment_id,
            recording_session_id=recording_session_id,
        )
        db.flush()
        
        # Submit visit analysis to Shunya
        try:
            # For sales visits, we use meeting segmentation + complete analysis
            # Start meeting segmentation if call_id available
            if call_id:
                seg_response = await self.uwc_client.analyze_meeting_segmentation(
                    company_id=company_id,
                    request_id=request_id,
                    call_id=call_id,
                    analysis_type="full",
                )
                
                seg_job_id = extract_shunya_job_id(seg_response, job_type="segmentation")
                
                if seg_job_id:
                    job.shunya_job_id = seg_job_id
                    db.commit()
                    db.refresh(job)
                    
                    # Create separate segmentation job
                    seg_job = shunya_job_service.create_job(
                        db=db,
                        company_id=company_id,
                        job_type=ShunyaJobType.SEGMENTATION,
                        input_payload={"call_id": call_id, "analysis_type": "full"},
                        appointment_id=session.appointment_id,
                        recording_session_id=recording_session_id,
                        call_id=call_id,
                    )
                    seg_job.shunya_job_id = seg_job_id
                    db.commit()
                    
                    # Schedule segmentation polling
                    from app.tasks.shunya_job_polling_tasks import poll_shunya_segmentation_status
                    poll_shunya_segmentation_status.delay(seg_job.id)
            
            # Start complete analysis
            if call_id:
                analysis_response = await self.uwc_client.start_analysis(
                    company_id=company_id,
                    request_id=request_id,
                    call_id=call_id,
                )
                
                analysis_job_id = extract_shunya_job_id(analysis_response, job_type="analysis")
                if analysis_job_id and not job.shunya_job_id:
                    job.shunya_job_id = analysis_job_id
            
            # Mark job as running
            shunya_job_service.mark_running(db, job, job.shunya_job_id)
            
            db.commit()
            db.refresh(job)
            
            # Emit job created event
            emit(
                "shunya.job.created",
                {
                    "job_id": job.id,
                    "job_type": job.job_type.value,
                    "recording_session_id": recording_session_id,
                    "appointment_id": session.appointment_id,
                    "shunya_job_id": job.shunya_job_id,
                },
                tenant_id=company_id,
                lead_id=session.lead_id if hasattr(session, "lead_id") else None,
            )
            
            # Schedule polling task
            from app.tasks.shunya_job_polling_tasks import poll_shunya_job_status
            poll_shunya_job_status.delay(job.id)
            
            logger.info(
                f"Submitted sales visit {recording_session_id} for async Shunya processing",
                extra={
                    "job_id": job.id,
                    "recording_session_id": recording_session_id,
                    "shunya_job_id": job.shunya_job_id,
                }
            )
            
            return job
            
        except Exception as e:
            logger.error(
                f"Error submitting sales visit {recording_session_id} to Shunya: {str(e)}",
                exc_info=True
            )
            shunya_job_service.mark_failed(
                db,
                job,
                str(e),
                error_details={"exception": type(e).__name__},
                should_retry=True,
            )
            db.commit()
            raise


# Global service instance
shunya_async_job_service = ShunyaAsyncJobService()

