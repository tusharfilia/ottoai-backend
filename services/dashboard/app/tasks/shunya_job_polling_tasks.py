"""
Celery tasks for polling Shunya job status.

Handles async polling of Shunya jobs with exponential backoff.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from celery import current_task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.pii_masking import PIISafeLogger
from app.database import SessionLocal
from app.models.shunya_job import ShunyaJob, ShunyaJobStatus, ShunyaJobType
from app.services.uwc_client import get_uwc_client
from app.services.shunya_job_service import shunya_job_service
from app.services.shunya_response_normalizer import ShunyaResponseNormalizer

shunya_normalizer = ShunyaResponseNormalizer()
from app.services.shunya_integration_service import ShunyaIntegrationService
from app.realtime.bus import emit
from app.utils.shunya_job_utils import extract_shunya_job_id, extract_call_id_from_payload

logger = PIISafeLogger(__name__)


@celery_app.task(bind=True, max_retries=10)
def poll_shunya_job_status(self, job_id: str):
    """
    Poll Shunya job status until complete or failed.
    
    Uses exponential backoff (5s, 10s, 30s, 60s, capped at 300s).
    
    Args:
        job_id: Otto ShunyaJob ID (UUID string)
    """
    db = SessionLocal()
    try:
        job = db.query(ShunyaJob).filter(ShunyaJob.id == job_id).first()
        
        if not job:
            logger.error(f"Shunya job {job_id} not found")
            return {"success": False, "error": "Job not found"}
        
        # Check if already completed/failed
        if job.job_status in [ShunyaJobStatus.SUCCEEDED, ShunyaJobStatus.FAILED, ShunyaJobStatus.TIMEOUT]:
            logger.info(
                f"Shunya job {job_id} already in final state: {job.job_status.value}",
                extra={"job_id": job_id, "status": job.job_status.value}
            )
            return {"success": True, "status": job.job_status.value, "already_complete": True}
        
        # Check timeout
        if job.created_at:
            age = datetime.utcnow() - job.created_at
            if age > timedelta(hours=24):
                logger.warning(f"Shunya job {job_id} timed out")
                shunya_job_service.mark_timeout(db, job)
                emit(
                    "shunya.job.timeout",
                    {"job_id": job_id, "job_type": job.job_type.value},
                    tenant_id=job.company_id,
                )
                return {"success": False, "status": "timeout"}
        
        # Mark as running if not already
        if job.job_status == ShunyaJobStatus.PENDING:
            shunya_job_service.mark_running(db, job, job.shunya_job_id)
        
        # Get call_id from input payload
        call_id = extract_call_id_from_payload(job.input_payload) or job.call_id
        
        if not call_id and job.job_type in [ShunyaJobType.CSR_CALL, ShunyaJobType.SALES_VISIT]:
            logger.error(f"Shunya job {job_id} missing call_id")
            shunya_job_service.mark_failed(
                db,
                job,
                "Missing call_id in job payload",
                should_retry=False,
            )
            return {"success": False, "error": "Missing call_id"}
        
        # Determine job type string for API
        job_type_str = "transcription" if job.job_type == ShunyaJobType.CSR_CALL else "analysis"
        
        # Poll Shunya for job status
        uwc_client = get_uwc_client()
        request_id = f"poll-{job_id}"
        
        try:
            # Poll status
            status_response = asyncio.run(
                uwc_client.get_job_status(
                    company_id=job.company_id,
                    request_id=request_id,
                    job_id=str(call_id or job.shunya_job_id or ""),
                    job_type=job_type_str,
                )
            )
            
            # Extract status from response
            status = status_response.get("status") or status_response.get("processing_status")
            
            if status in ["completed", "succeeded", "success"]:
                # Job completed - fetch result
                logger.info(f"Shunya job {job_id} completed, fetching result")
                
                # Fetch final result
                result_response = asyncio.run(
                    uwc_client.get_job_result(
                        company_id=job.company_id,
                        request_id=request_id,
                        call_id=call_id or 0,
                        job_type=job_type_str,
                    )
                )
                
                # Normalize result
                normalized_result = shunya_normalizer.normalize_complete_analysis(result_response)
                
                # P0 FIX: Acquire distributed lock to prevent webhook vs polling race condition
                from app.services.redis_lock_service import redis_lock_service
                lock_key = f"shunya_job:{job_id}"
                lock_token = None
                
                try:
                    lock_token = asyncio.run(
                        redis_lock_service.acquire_lock(
                            lock_key=lock_key,
                            tenant_id=job.company_id,
                            timeout=300  # 5 minutes
                        )
                    )
                    
                    if not lock_token:
                        logger.warning(
                            f"Could not acquire lock for Shunya job {job_id}, another process may be handling it",
                            extra={"job_id": job_id}
                        )
                        return {"success": False, "status": "processing_by_another"}
                    
                    # Check idempotency before processing (inside lock to prevent race)
                    if not shunya_job_service.should_process(db, job, normalized_result):
                        logger.info(
                            f"Shunya job {job_id} already processed, skipping",
                            extra={"job_id": job_id}
                        )
                        return {"success": True, "status": "already_processed"}
                    
                    # Mark job as succeeded (idempotent)
                    shunya_job_service.mark_succeeded(db, job, normalized_result)
                    db.refresh(job)  # Refresh to get updated processed_output_hash
                    
                    # Process result and persist to domain models (idempotent)
                    integration_service = ShunyaIntegrationService()
                    
                    if job.job_type == ShunyaJobType.CSR_CALL and call_id:
                        # Process CSR call analysis (pass shunya_job for idempotency)
                        from app.models.call import Call
                        call = db.query(Call).filter(Call.call_id == call_id).first()
                        if call:
                            asyncio.run(
                                integration_service._process_shunya_analysis_for_call(
                                    db=db,
                                    call=call,
                                    company_id=job.company_id,
                                    complete_analysis=normalized_result,
                                    transcript_text=normalized_result.get("transcript", {}).get("transcript_text", ""),
                                    shunya_job=job,  # Pass job for idempotency checking
                                )
                            )
                    elif job.job_type == ShunyaJobType.SALES_VISIT and job.recording_session_id:
                        # Process sales visit analysis (pass shunya_job for idempotency)
                        from app.models.recording_session import RecordingSession
                        session = db.query(RecordingSession).filter(
                            RecordingSession.id == job.recording_session_id
                        ).first()
                        if session:
                            asyncio.run(
                                integration_service._process_shunya_analysis_for_visit(
                                    db=db,
                                    recording_session=session,
                                    company_id=job.company_id,
                                    complete_analysis=normalized_result,
                                    transcript_text="",  # May be ghost mode
                                    shunya_job=job,  # Pass job for idempotency checking
                                )
                            )
                    
                    db.commit()
                    
                    # Emit success event (idempotent check)
                    if job.job_status == ShunyaJobStatus.SUCCEEDED:
                        emit(
                            "shunya.job.succeeded",
                            {
                                "job_id": job_id,
                                "job_type": job.job_type.value,
                                "call_id": call_id,
                            },
                            tenant_id=job.company_id,
                            lead_id=job.lead_id,
                        )
                    
                    logger.info(f"Successfully processed Shunya job {job_id}")
                    return {"success": True, "status": "succeeded"}
                finally:
                    # P0 FIX: Always release lock
                    if lock_token:
                        asyncio.run(
                            redis_lock_service.release_lock(
                                lock_key=lock_key,
                                tenant_id=job.company_id,
                                lock_token=lock_token
                            )
                        )
                
            elif status in ["failed", "error"]:
                # Job failed
                error_msg = status_response.get("error") or status_response.get("error_message") or "Job failed"
                shunya_job_service.mark_failed(
                    db,
                    job,
                    error_msg,
                    error_details=status_response,
                    should_retry=shunya_job_service.should_retry(job),
                )
                
                if not shunya_job_service.should_retry(job):
                    emit(
                        "shunya.job.failed",
                        {
                            "job_id": job_id,
                            "job_type": job.job_type.value,
                            "error": error_msg,
                        },
                        tenant_id=job.company_id,
                    )
                
                return {"success": False, "status": "failed", "error": error_msg}
                
            else:
                # Still processing - schedule retry
                retry_delay = shunya_job_service.next_retry_delay(job)
                
                # Record attempt
                shunya_job_service.record_attempt(db, job)
                
                # Schedule next poll
                poll_shunya_job_status.apply_async(
                    args=[job_id],
                    countdown=retry_delay,
                )
                
                logger.info(
                    f"Shunya job {job_id} still processing, will retry in {retry_delay}s",
                    extra={
                        "job_id": job_id,
                        "status": status,
                        "retry_delay": retry_delay,
                    }
                )
                
                return {"success": True, "status": "processing", "retry_in": retry_delay}
                
        except Exception as e:
            logger.error(f"Error polling Shunya job {job_id}: {str(e)}", exc_info=True)
            
            # Check if we should retry
            if shunya_job_service.should_retry(job):
                retry_delay = shunya_job_service.next_retry_delay(job)
                shunya_job_service.mark_failed(
                    db,
                    job,
                    str(e),
                    error_details={"exception": type(e).__name__},
                    should_retry=True,
                )
                
                # Schedule retry
                poll_shunya_job_status.apply_async(
                    args=[job_id],
                    countdown=retry_delay,
                )
                
                return {"success": False, "status": "retrying", "retry_in": retry_delay}
            else:
                # Permanent failure
                shunya_job_service.mark_failed(
                    db,
                    job,
                    str(e),
                    error_details={"exception": type(e).__name__},
                    should_retry=False,
                )
                
                emit(
                    "shunya.job.failed",
                    {
                        "job_id": job_id,
                        "job_type": job.job_type.value,
                        "error": str(e),
                    },
                    tenant_id=job.company_id,
                )
                
                return {"success": False, "status": "failed", "error": str(e)}
                
    except Exception as e:
        logger.error(f"Error in poll_shunya_job_status for job {job_id}: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=10)
def poll_shunya_segmentation_status(self, job_id: str):
    """
    Poll Shunya meeting segmentation status.
    
    Similar to poll_shunya_job_status but specifically for segmentation jobs.
    
    Args:
        job_id: Otto ShunyaJob ID (UUID string)
    """
    db = SessionLocal()
    try:
        job = db.query(ShunyaJob).filter(
            ShunyaJob.id == job_id,
            ShunyaJob.job_type == ShunyaJobType.SEGMENTATION,
        ).first()
        
        if not job:
            logger.error(f"Shunya segmentation job {job_id} not found")
            return {"success": False, "error": "Job not found"}
        
        # Check if already completed
        if job.job_status == ShunyaJobStatus.SUCCEEDED:
            return {"success": True, "status": "already_complete"}
        
        # Get call_id
        call_id = extract_call_id_from_payload(job.input_payload) or job.call_id
        
        if not call_id:
            logger.error(f"Shunya segmentation job {job_id} missing call_id")
            shunya_job_service.mark_failed(
                db,
                job,
                "Missing call_id for segmentation",
                should_retry=False,
            )
            return {"success": False, "error": "Missing call_id"}
        
        # Poll segmentation status
        uwc_client = get_uwc_client()
        request_id = f"poll-seg-{job_id}"
        
        try:
            status_response = asyncio.run(
                uwc_client.get_segmentation_status(
                    company_id=job.company_id,
                    request_id=request_id,
                    call_id=call_id,
                )
            )
            
            # Check status
            has_segmentation = status_response.get("has_segmentation_analysis", False)
            status = status_response.get("status", "pending")
            
            if has_segmentation and status in ["completed", "succeeded"]:
                # Fetch segmentation result
                seg_result = asyncio.run(
                    uwc_client.get_segmentation_result(
                        company_id=job.company_id,
                        request_id=request_id,
                        call_id=call_id,
                    )
                )
                
                # Normalize segmentation result
                normalized_seg = shunya_normalizer.normalize_meeting_segmentation(seg_result)
                
                # Mark job as succeeded
                shunya_job_service.mark_succeeded(db, job, normalized_seg)
                
                # Merge with visit analysis if exists
                if job.recording_session_id:
                    from app.models.recording_session import RecordingSession
                    session = db.query(RecordingSession).filter(
                        RecordingSession.id == job.recording_session_id
                    ).first()
                    if session and session.appointment_id:
                        # Merge segmentation into visit analysis
                        # This will be handled by the visit analysis processing
                        pass
                
                db.commit()
                
                emit(
                    "shunya.job.succeeded",
                    {
                        "job_id": job_id,
                        "job_type": "segmentation",
                        "call_id": call_id,
                    },
                    tenant_id=job.company_id,
                )
                
                return {"success": True, "status": "succeeded"}
                
            elif status in ["failed", "error"]:
                error_msg = status_response.get("error") or "Segmentation failed"
                shunya_job_service.mark_failed(
                    db,
                    job,
                    error_msg,
                    should_retry=shunya_job_service.should_retry(job),
                )
                return {"success": False, "status": "failed"}
                
            else:
                # Still processing - schedule retry
                retry_delay = shunya_job_service.next_retry_delay(job)
                shunya_job_service.record_attempt(db, job)
                
                poll_shunya_segmentation_status.apply_async(
                    args=[job_id],
                    countdown=retry_delay,
                )
                
                return {"success": True, "status": "processing", "retry_in": retry_delay}
                
        except Exception as e:
            logger.error(f"Error polling segmentation job {job_id}: {str(e)}", exc_info=True)
            
            if shunya_job_service.should_retry(job):
                retry_delay = shunya_job_service.next_retry_delay(job)
                shunya_job_service.mark_failed(db, job, str(e), should_retry=True)
                poll_shunya_segmentation_status.apply_async(
                    args=[job_id],
                    countdown=retry_delay,
                )
                return {"success": False, "status": "retrying", "retry_in": retry_delay}
            else:
                shunya_job_service.mark_failed(db, job, str(e), should_retry=False)
                return {"success": False, "status": "failed", "error": str(e)}
                
    except Exception as e:
        logger.error(f"Error in poll_shunya_segmentation_status: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        db.close()





Handles async polling of Shunya jobs with exponential backoff.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from celery import current_task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.pii_masking import PIISafeLogger
from app.database import SessionLocal
from app.models.shunya_job import ShunyaJob, ShunyaJobStatus, ShunyaJobType
from app.services.uwc_client import get_uwc_client
from app.services.shunya_job_service import shunya_job_service
from app.services.shunya_response_normalizer import ShunyaResponseNormalizer

shunya_normalizer = ShunyaResponseNormalizer()
from app.services.shunya_integration_service import ShunyaIntegrationService
from app.realtime.bus import emit
from app.utils.shunya_job_utils import extract_shunya_job_id, extract_call_id_from_payload

logger = PIISafeLogger(__name__)


@celery_app.task(bind=True, max_retries=10)
def poll_shunya_job_status(self, job_id: str):
    """
    Poll Shunya job status until complete or failed.
    
    Uses exponential backoff (5s, 10s, 30s, 60s, capped at 300s).
    
    Args:
        job_id: Otto ShunyaJob ID (UUID string)
    """
    db = SessionLocal()
    try:
        job = db.query(ShunyaJob).filter(ShunyaJob.id == job_id).first()
        
        if not job:
            logger.error(f"Shunya job {job_id} not found")
            return {"success": False, "error": "Job not found"}
        
        # Check if already completed/failed
        if job.job_status in [ShunyaJobStatus.SUCCEEDED, ShunyaJobStatus.FAILED, ShunyaJobStatus.TIMEOUT]:
            logger.info(
                f"Shunya job {job_id} already in final state: {job.job_status.value}",
                extra={"job_id": job_id, "status": job.job_status.value}
            )
            return {"success": True, "status": job.job_status.value, "already_complete": True}
        
        # Check timeout
        if job.created_at:
            age = datetime.utcnow() - job.created_at
            if age > timedelta(hours=24):
                logger.warning(f"Shunya job {job_id} timed out")
                shunya_job_service.mark_timeout(db, job)
                emit(
                    "shunya.job.timeout",
                    {"job_id": job_id, "job_type": job.job_type.value},
                    tenant_id=job.company_id,
                )
                return {"success": False, "status": "timeout"}
        
        # Mark as running if not already
        if job.job_status == ShunyaJobStatus.PENDING:
            shunya_job_service.mark_running(db, job, job.shunya_job_id)
        
        # Get call_id from input payload
        call_id = extract_call_id_from_payload(job.input_payload) or job.call_id
        
        if not call_id and job.job_type in [ShunyaJobType.CSR_CALL, ShunyaJobType.SALES_VISIT]:
            logger.error(f"Shunya job {job_id} missing call_id")
            shunya_job_service.mark_failed(
                db,
                job,
                "Missing call_id in job payload",
                should_retry=False,
            )
            return {"success": False, "error": "Missing call_id"}
        
        # Determine job type string for API
        job_type_str = "transcription" if job.job_type == ShunyaJobType.CSR_CALL else "analysis"
        
        # Poll Shunya for job status
        uwc_client = get_uwc_client()
        request_id = f"poll-{job_id}"
        
        try:
            # Poll status
            status_response = asyncio.run(
                uwc_client.get_job_status(
                    company_id=job.company_id,
                    request_id=request_id,
                    job_id=str(call_id or job.shunya_job_id or ""),
                    job_type=job_type_str,
                )
            )
            
            # Extract status from response
            status = status_response.get("status") or status_response.get("processing_status")
            
            if status in ["completed", "succeeded", "success"]:
                # Job completed - fetch result
                logger.info(f"Shunya job {job_id} completed, fetching result")
                
                # Fetch final result
                result_response = asyncio.run(
                    uwc_client.get_job_result(
                        company_id=job.company_id,
                        request_id=request_id,
                        call_id=call_id or 0,
                        job_type=job_type_str,
                    )
                )
                
                # Normalize result
                normalized_result = shunya_normalizer.normalize_complete_analysis(result_response)
                
                # P0 FIX: Acquire distributed lock to prevent webhook vs polling race condition
                from app.services.redis_lock_service import redis_lock_service
                lock_key = f"shunya_job:{job_id}"
                lock_token = None
                
                try:
                    lock_token = asyncio.run(
                        redis_lock_service.acquire_lock(
                            lock_key=lock_key,
                            tenant_id=job.company_id,
                            timeout=300  # 5 minutes
                        )
                    )
                    
                    if not lock_token:
                        logger.warning(
                            f"Could not acquire lock for Shunya job {job_id}, another process may be handling it",
                            extra={"job_id": job_id}
                        )
                        return {"success": False, "status": "processing_by_another"}
                    
                    # Check idempotency before processing (inside lock to prevent race)
                    if not shunya_job_service.should_process(db, job, normalized_result):
                        logger.info(
                            f"Shunya job {job_id} already processed, skipping",
                            extra={"job_id": job_id}
                        )
                        return {"success": True, "status": "already_processed"}
                    
                    # Mark job as succeeded (idempotent)
                    shunya_job_service.mark_succeeded(db, job, normalized_result)
                    db.refresh(job)  # Refresh to get updated processed_output_hash
                    
                    # Process result and persist to domain models (idempotent)
                    integration_service = ShunyaIntegrationService()
                    
                    if job.job_type == ShunyaJobType.CSR_CALL and call_id:
                        # Process CSR call analysis (pass shunya_job for idempotency)
                        from app.models.call import Call
                        call = db.query(Call).filter(Call.call_id == call_id).first()
                        if call:
                            asyncio.run(
                                integration_service._process_shunya_analysis_for_call(
                                    db=db,
                                    call=call,
                                    company_id=job.company_id,
                                    complete_analysis=normalized_result,
                                    transcript_text=normalized_result.get("transcript", {}).get("transcript_text", ""),
                                    shunya_job=job,  # Pass job for idempotency checking
                                )
                            )
                    elif job.job_type == ShunyaJobType.SALES_VISIT and job.recording_session_id:
                        # Process sales visit analysis (pass shunya_job for idempotency)
                        from app.models.recording_session import RecordingSession
                        session = db.query(RecordingSession).filter(
                            RecordingSession.id == job.recording_session_id
                        ).first()
                        if session:
                            asyncio.run(
                                integration_service._process_shunya_analysis_for_visit(
                                    db=db,
                                    recording_session=session,
                                    company_id=job.company_id,
                                    complete_analysis=normalized_result,
                                    transcript_text="",  # May be ghost mode
                                    shunya_job=job,  # Pass job for idempotency checking
                                )
                            )
                    
                    db.commit()
                    
                    # Emit success event (idempotent check)
                    if job.job_status == ShunyaJobStatus.SUCCEEDED:
                        emit(
                            "shunya.job.succeeded",
                            {
                                "job_id": job_id,
                                "job_type": job.job_type.value,
                                "call_id": call_id,
                            },
                            tenant_id=job.company_id,
                            lead_id=job.lead_id,
                        )
                    
                    logger.info(f"Successfully processed Shunya job {job_id}")
                    return {"success": True, "status": "succeeded"}
                finally:
                    # P0 FIX: Always release lock
                    if lock_token:
                        asyncio.run(
                            redis_lock_service.release_lock(
                                lock_key=lock_key,
                                tenant_id=job.company_id,
                                lock_token=lock_token
                            )
                        )
                
            elif status in ["failed", "error"]:
                # Job failed
                error_msg = status_response.get("error") or status_response.get("error_message") or "Job failed"
                shunya_job_service.mark_failed(
                    db,
                    job,
                    error_msg,
                    error_details=status_response,
                    should_retry=shunya_job_service.should_retry(job),
                )
                
                if not shunya_job_service.should_retry(job):
                    emit(
                        "shunya.job.failed",
                        {
                            "job_id": job_id,
                            "job_type": job.job_type.value,
                            "error": error_msg,
                        },
                        tenant_id=job.company_id,
                    )
                
                return {"success": False, "status": "failed", "error": error_msg}
                
            else:
                # Still processing - schedule retry
                retry_delay = shunya_job_service.next_retry_delay(job)
                
                # Record attempt
                shunya_job_service.record_attempt(db, job)
                
                # Schedule next poll
                poll_shunya_job_status.apply_async(
                    args=[job_id],
                    countdown=retry_delay,
                )
                
                logger.info(
                    f"Shunya job {job_id} still processing, will retry in {retry_delay}s",
                    extra={
                        "job_id": job_id,
                        "status": status,
                        "retry_delay": retry_delay,
                    }
                )
                
                return {"success": True, "status": "processing", "retry_in": retry_delay}
                
        except Exception as e:
            logger.error(f"Error polling Shunya job {job_id}: {str(e)}", exc_info=True)
            
            # Check if we should retry
            if shunya_job_service.should_retry(job):
                retry_delay = shunya_job_service.next_retry_delay(job)
                shunya_job_service.mark_failed(
                    db,
                    job,
                    str(e),
                    error_details={"exception": type(e).__name__},
                    should_retry=True,
                )
                
                # Schedule retry
                poll_shunya_job_status.apply_async(
                    args=[job_id],
                    countdown=retry_delay,
                )
                
                return {"success": False, "status": "retrying", "retry_in": retry_delay}
            else:
                # Permanent failure
                shunya_job_service.mark_failed(
                    db,
                    job,
                    str(e),
                    error_details={"exception": type(e).__name__},
                    should_retry=False,
                )
                
                emit(
                    "shunya.job.failed",
                    {
                        "job_id": job_id,
                        "job_type": job.job_type.value,
                        "error": str(e),
                    },
                    tenant_id=job.company_id,
                )
                
                return {"success": False, "status": "failed", "error": str(e)}
                
    except Exception as e:
        logger.error(f"Error in poll_shunya_job_status for job {job_id}: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=10)
def poll_shunya_segmentation_status(self, job_id: str):
    """
    Poll Shunya meeting segmentation status.
    
    Similar to poll_shunya_job_status but specifically for segmentation jobs.
    
    Args:
        job_id: Otto ShunyaJob ID (UUID string)
    """
    db = SessionLocal()
    try:
        job = db.query(ShunyaJob).filter(
            ShunyaJob.id == job_id,
            ShunyaJob.job_type == ShunyaJobType.SEGMENTATION,
        ).first()
        
        if not job:
            logger.error(f"Shunya segmentation job {job_id} not found")
            return {"success": False, "error": "Job not found"}
        
        # Check if already completed
        if job.job_status == ShunyaJobStatus.SUCCEEDED:
            return {"success": True, "status": "already_complete"}
        
        # Get call_id
        call_id = extract_call_id_from_payload(job.input_payload) or job.call_id
        
        if not call_id:
            logger.error(f"Shunya segmentation job {job_id} missing call_id")
            shunya_job_service.mark_failed(
                db,
                job,
                "Missing call_id for segmentation",
                should_retry=False,
            )
            return {"success": False, "error": "Missing call_id"}
        
        # Poll segmentation status
        uwc_client = get_uwc_client()
        request_id = f"poll-seg-{job_id}"
        
        try:
            status_response = asyncio.run(
                uwc_client.get_segmentation_status(
                    company_id=job.company_id,
                    request_id=request_id,
                    call_id=call_id,
                )
            )
            
            # Check status
            has_segmentation = status_response.get("has_segmentation_analysis", False)
            status = status_response.get("status", "pending")
            
            if has_segmentation and status in ["completed", "succeeded"]:
                # Fetch segmentation result
                seg_result = asyncio.run(
                    uwc_client.get_segmentation_result(
                        company_id=job.company_id,
                        request_id=request_id,
                        call_id=call_id,
                    )
                )
                
                # Normalize segmentation result
                normalized_seg = shunya_normalizer.normalize_meeting_segmentation(seg_result)
                
                # Mark job as succeeded
                shunya_job_service.mark_succeeded(db, job, normalized_seg)
                
                # Merge with visit analysis if exists
                if job.recording_session_id:
                    from app.models.recording_session import RecordingSession
                    session = db.query(RecordingSession).filter(
                        RecordingSession.id == job.recording_session_id
                    ).first()
                    if session and session.appointment_id:
                        # Merge segmentation into visit analysis
                        # This will be handled by the visit analysis processing
                        pass
                
                db.commit()
                
                emit(
                    "shunya.job.succeeded",
                    {
                        "job_id": job_id,
                        "job_type": "segmentation",
                        "call_id": call_id,
                    },
                    tenant_id=job.company_id,
                )
                
                return {"success": True, "status": "succeeded"}
                
            elif status in ["failed", "error"]:
                error_msg = status_response.get("error") or "Segmentation failed"
                shunya_job_service.mark_failed(
                    db,
                    job,
                    error_msg,
                    should_retry=shunya_job_service.should_retry(job),
                )
                return {"success": False, "status": "failed"}
                
            else:
                # Still processing - schedule retry
                retry_delay = shunya_job_service.next_retry_delay(job)
                shunya_job_service.record_attempt(db, job)
                
                poll_shunya_segmentation_status.apply_async(
                    args=[job_id],
                    countdown=retry_delay,
                )
                
                return {"success": True, "status": "processing", "retry_in": retry_delay}
                
        except Exception as e:
            logger.error(f"Error polling segmentation job {job_id}: {str(e)}", exc_info=True)
            
            if shunya_job_service.should_retry(job):
                retry_delay = shunya_job_service.next_retry_delay(job)
                shunya_job_service.mark_failed(db, job, str(e), should_retry=True)
                poll_shunya_segmentation_status.apply_async(
                    args=[job_id],
                    countdown=retry_delay,
                )
                return {"success": False, "status": "retrying", "retry_in": retry_delay}
            else:
                shunya_job_service.mark_failed(db, job, str(e), should_retry=False)
                return {"success": False, "status": "failed", "error": str(e)}
                
    except Exception as e:
        logger.error(f"Error in poll_shunya_segmentation_status: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        db.close()






