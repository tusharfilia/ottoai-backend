"""
Shunya webhook handler for job completion notifications.

Handles webhook notifications from Shunya when jobs complete.
Includes HMAC signature verification for security.
"""
from datetime import datetime
from typing import Optional, Dict, Any
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
import asyncio

from app.database import get_db
from app.models.shunya_job import ShunyaJob, ShunyaJobStatus
from app.services.shunya_job_service import shunya_job_service
from app.services.shunya_response_normalizer import ShunyaResponseNormalizer
from app.utils.shunya_webhook_security import (
    verify_shunya_webhook_signature,
    InvalidSignatureError,
    MissingHeadersError,
    TimestampExpiredError,
)

shunya_normalizer = ShunyaResponseNormalizer()
from app.services.shunya_integration_service import ShunyaIntegrationService
from app.services.uwc_client import get_uwc_client
from app.realtime.bus import emit
from app.core.pii_masking import PIISafeLogger
from app.schemas.responses import APIResponse

logger = PIISafeLogger(__name__)

router = APIRouter(prefix="/api/v1/shunya", tags=["shunya"])


@router.post("/webhook", status_code=200)
async def shunya_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_shunya_signature: Optional[str] = Header(None, alias="X-Shunya-Signature"),
    x_shunya_timestamp: Optional[str] = Header(None, alias="X-Shunya-Timestamp"),
    x_shunya_task_id: Optional[str] = Header(None, alias="X-Shunya-Task-Id"),
) -> APIResponse[dict]:
    """
    Webhook endpoint for Shunya job completion notifications.
    
    Security:
    - Verifies HMAC-SHA256 signature before processing (X-Shunya-Signature)
    - Validates timestamp to prevent replay attacks (X-Shunya-Timestamp, epoch milliseconds)
    - Uses X-Shunya-Task-Id for idempotency tracking
    - Enforces tenant isolation
    
    Headers:
    - X-Shunya-Signature: HMAC-SHA256 hex digest
    - X-Shunya-Timestamp: Epoch milliseconds (string)
    - X-Shunya-Task-Id: Task ID for idempotency (optional)
    
    Payload structure:
    {
        "shunya_job_id": "job_12345",
        "status": "completed" | "failed",
        "result": {...},  # Optional, if status is "completed"
        "error": {...},   # Optional, if status is "failed" (canonical error envelope)
        "company_id": "...",  # Required for tenant verification
    }
    
    Behavior:
    1. Read raw request body
    2. Verify HMAC signature (if invalid -> 401)
    3. Parse JSON payload
    4. Extract company_id and verify tenant isolation
    5. Look up ShunyaJob by shunya_job_id (or use task_id for idempotency)
    6. Verify company_id matches job.company_id (if mismatch -> 403)
    7. Update job_status
    8. If completed: fetch final result, normalize, persist (idempotent)
    9. Emit events (idempotent)
    
    Webhook delivery guarantees:
    - At-least-once delivery (duplicates possible)
    - Idempotency handled via ShunyaJob + output hash
    """
    # Step 1: Read raw body BEFORE parsing JSON (required for signature verification)
    raw_body = await request.body()
    
    # Step 2: Verify signature BEFORE any processing
    try:
        verify_shunya_webhook_signature(
            raw_body=raw_body,
            signature=x_shunya_signature,
            timestamp=x_shunya_timestamp,
            task_id=x_shunya_task_id,  # Pass for logging/idempotency
        )
    except MissingHeadersError as e:
        logger.warning(f"Shunya webhook missing required headers: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail={"success": False, "error": "invalid_signature", "message": "Missing required headers"}
        )
    except TimestampExpiredError as e:
        logger.warning(f"Shunya webhook timestamp expired: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail={"success": False, "error": "invalid_signature", "message": "Webhook timestamp expired"}
        )
    except InvalidSignatureError as e:
        logger.warning(f"Shunya webhook invalid signature: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail={"success": False, "error": "invalid_signature", "message": "Signature verification failed"}
        )
    except Exception as e:
        logger.error(f"Unexpected error during signature verification: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=401,
            detail={"success": False, "error": "invalid_signature", "message": "Signature verification error"}
        )
    
    # Step 3: Parse JSON payload (now that signature is verified)
    try:
        payload = json.loads(raw_body.decode('utf-8'))
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in webhook payload: {str(e)}")
        return APIResponse(
            data={"success": False, "error": "invalid_payload", "message": "Invalid JSON format"}
        )
    
    shunya_job_id = payload.get("shunya_job_id")
    status = payload.get("status", "").lower()
    company_id = payload.get("company_id")
    
    # Step 4: Validate required fields
    if not shunya_job_id:
        logger.warning("Shunya webhook received without shunya_job_id")
        raise HTTPException(
            status_code=400,
            detail={"success": False, "error": "invalid_payload", "message": "Missing shunya_job_id"}
        )
    
    if not company_id:
        logger.warning(
            "Shunya webhook received without company_id - required for tenant isolation",
            extra={"shunya_job_id": shunya_job_id}
        )
        raise HTTPException(
            status_code=400,
            detail={"success": False, "error": "invalid_payload", "message": "Missing company_id"}
        )
    
    # Step 5: Find job by Shunya job ID (tenant-scoped lookup)
    job = shunya_job_service.get_job_by_shunya_id(db, company_id, shunya_job_id)
    
    if not job:
        logger.warning(
            f"Shunya webhook for unknown job: {shunya_job_id}",
            extra={"shunya_job_id": shunya_job_id, "company_id": company_id}
        )
        # Return 200 to prevent webhook retries (but log for security monitoring)
        return APIResponse(data={"status": "ignored", "reason": "Job not found"})
    
    # Step 6: Verify tenant isolation - company_id MUST match job.company_id
    if job.company_id != company_id:
        logger.error(
            f"Company ID mismatch in webhook (potential cross-tenant attack): "
            f"expected {job.company_id}, got {company_id}",
            extra={
                "job_id": job.id,
                "shunya_job_id": shunya_job_id,
                "expected_company": job.company_id,
                "received_company": company_id,
            }
        )
        # Return 403 to indicate security violation (cross-tenant attack attempt)
        raise HTTPException(
            status_code=403,
            detail={"success": False, "error": "forbidden", "message": "Company ID mismatch"}
        )
    
    # Check idempotency: don't process if already succeeded
    if job.job_status == ShunyaJobStatus.SUCCEEDED:
        logger.info(
            f"Shunya webhook received for already-succeeded job {job.id}",
            extra={"job_id": job.id, "shunya_job_id": shunya_job_id}
        )
        return APIResponse(data={"status": "already_processed", "job_id": job.id})
    
    # Process webhook based on status
    if status in ["completed", "succeeded", "success"]:
        # Job completed - fetch result and process
        logger.info(
            f"Shunya webhook: job {job.id} completed",
            extra={"job_id": job.id, "shunya_job_id": shunya_job_id}
        )
        
        try:
            # Get result from payload or fetch from Shunya
            result = payload.get("result")
            
            if not result:
                # Fetch result from Shunya API
                call_id = job.call_id
                if not call_id:
                    call_id = job.input_payload.get("call_id") if isinstance(job.input_payload, dict) else None
                
                if call_id:
                    job_type_str = "transcription" if job.job_type.value == "csr_call" else "analysis"
                    uwc_client = get_uwc_client()
                    request_id = f"webhook-{job.id}"
                    
                    result = await uwc_client.get_job_result(
                        company_id=job.company_id,
                        request_id=request_id,
                        call_id=int(call_id),
                        job_type=job_type_str,
                    )
            
            if not result:
                logger.error(f"No result available for Shunya job {job.id}")
                shunya_job_service.mark_failed(
                    db,
                    job,
                    "No result available from webhook",
                    should_retry=True,
                )
                return APIResponse(data={"status": "error", "error": "No result available"})
            
            # Normalize result
            if job.job_type.value == "segmentation":
                normalized_result = shunya_normalizer.normalize_meeting_segmentation(result)
            else:
                normalized_result = shunya_normalizer.normalize_complete_analysis(result)
            
            # Check idempotency before processing
            if not shunya_job_service.should_process(db, job, normalized_result):
                logger.info(
                    f"Shunya job {job.id} already processed via webhook, skipping",
                    extra={"job_id": job.id, "shunya_job_id": shunya_job_id}
                )
                return APIResponse(data={"status": "already_processed", "job_id": job.id})
            
            # Mark job as succeeded (idempotent)
            shunya_job_service.mark_succeeded(db, job, normalized_result)
            db.refresh(job)  # Refresh to get updated processed_output_hash
            
            # Process result and persist to domain models (idempotent)
            integration_service = ShunyaIntegrationService()
            
            if job.job_type.value == "csr_call" and job.call_id:
                from app.models.call import Call
                call = db.query(Call).filter(Call.call_id == job.call_id).first()
                if call:
                    await integration_service._process_shunya_analysis_for_call(
                        db=db,
                        call=call,
                        company_id=job.company_id,
                        complete_analysis=normalized_result,
                        transcript_text=normalized_result.get("transcript", {}).get("transcript_text", ""),
                        shunya_job=job,  # Pass job for idempotency checking
                    )
            elif job.job_type.value == "sales_visit" and job.recording_session_id:
                from app.models.recording_session import RecordingSession
                session = db.query(RecordingSession).filter(
                    RecordingSession.id == job.recording_session_id
                ).first()
                if session:
                    await integration_service._process_shunya_analysis_for_visit(
                        db=db,
                        recording_session=session,
                        company_id=job.company_id,
                        complete_analysis=normalized_result,
                        transcript_text="",  # May be ghost mode
                        shunya_job=job,  # Pass job for idempotency checking
                    )
            
            db.commit()
            
            # Emit success event (idempotent check)
            emit(
                "shunya.job.succeeded",
                {
                    "job_id": job.id,
                    "job_type": job.job_type.value,
                    "shunya_job_id": shunya_job_id,
                },
                tenant_id=job.company_id,
                lead_id=job.lead_id,
            )
            
            logger.info(f"Successfully processed Shunya webhook for job {job.id}")
            return APIResponse(data={"status": "processed", "job_id": job.id})
            
        except Exception as e:
            logger.error(
                f"Error processing Shunya webhook for job {job.id}: {str(e)}",
                exc_info=True
            )
            shunya_job_service.mark_failed(
                db,
                job,
                f"Webhook processing error: {str(e)}",
                error_details={"exception": type(e).__name__},
                should_retry=True,
            )
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Error processing webhook: {str(e)}")
    
    elif status in ["failed", "error"]:
        # Job failed
        error_msg = payload.get("error") or "Job failed"
        
        logger.warning(
            f"Shunya webhook: job {job.id} failed",
            extra={"job_id": job.id, "shunya_job_id": shunya_job_id, "error": error_msg}
        )
        
        shunya_job_service.mark_failed(
            db,
            job,
            error_msg,
            error_details=payload,
            should_retry=shunya_job_service.should_retry(job),
        )
        
        if not shunya_job_service.should_retry(job):
            emit(
                "shunya.job.failed",
                {
                    "job_id": job.id,
                    "job_type": job.job_type.value,
                    "error": error_msg,
                },
                tenant_id=job.company_id,
            )
        
        return APIResponse(data={"status": "processed", "job_id": job.id, "status_update": "failed"})
    
    else:
        # Unknown status
        logger.warning(
            f"Shunya webhook received with unknown status: {status}",
            extra={"job_id": job.id, "shunya_job_id": shunya_job_id, "status": status}
        )
        return APIResponse(data={"status": "ignored", "reason": f"Unknown status: {status}"})



