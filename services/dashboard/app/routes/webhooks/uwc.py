"""
UWC webhook handlers for Otto backend.
Receives callbacks from UWC for ASR, RAG, training, and other async operations.

Otto's Responsibility:
- Receive webhooks from UWC
- Verify HMAC signatures
- Store results in Otto database
- Emit real-time events to WebSocket subscribers
"""
import logging
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Header
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models.call import Call
from app.services.idempotency import with_idempotency
from app.obs.logging import get_logger
from app.obs.metrics import metrics
from app.realtime.bus import emit
from app.config import settings

router = APIRouter(prefix="/webhooks/uwc", tags=["uwc-webhooks"])
logger = get_logger(__name__)


async def verify_uwc_signature(
    payload: bytes,
    signature: str,
    timestamp: str
) -> bool:
    """
    Verify HMAC signature from UWC webhooks.
    
    NOTE: This is a placeholder implementation based on assumptions.
    Will be updated when UWC provides actual HMAC specification.
    
    Current assumptions:
    - Algorithm: HMAC-SHA256
    - Message format: {timestamp}:{payload}
    - Header: X-UWC-Signature
    - Timestamp header: X-UWC-Timestamp
    - Validation window: 5 minutes
    
    Args:
        payload: Raw request body bytes
        signature: HMAC signature from X-UWC-Signature header
        timestamp: ISO 8601 timestamp from X-UWC-Timestamp header
    
    Returns:
        bool: True if signature is valid, False otherwise
    """
    if not settings.UWC_HMAC_SECRET:
        logger.warning(
            "UWC_HMAC_SECRET not configured, skipping signature verification. "
            "This is INSECURE and should only be used in development!"
        )
        return True  # Allow in development
    
    try:
        # Validate timestamp (5-minute window to prevent replay attacks)
        webhook_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        now = datetime.utcnow()
        time_diff = abs((now - webhook_time).total_seconds())
        
        if time_diff > 300:  # 5 minutes
            logger.warning(
                f"Webhook timestamp too old: {timestamp} "
                f"(diff: {time_diff:.0f}s, max: 300s)"
            )
            return False
    except Exception as e:
        logger.error(f"Invalid timestamp format: {timestamp}, error: {e}")
        return False
    
    # Verify HMAC signature
    # Message format: {timestamp}:{payload}
    message = f"{timestamp}:{payload.decode('utf-8')}"
    expected_signature = hmac.new(
        settings.UWC_HMAC_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    is_valid = hmac.compare_digest(signature, expected_signature)
    
    if not is_valid:
        logger.warning(
            f"Invalid UWC webhook signature. "
            f"Expected: {expected_signature[:16]}..., Got: {signature[:16]}..."
        )
    
    return is_valid


@router.post("/asr/complete")
@with_idempotency(provider="uwc", event_type="asr_complete")
async def asr_complete_webhook(
    request: Request,
    x_uwc_signature: Optional[str] = Header(None, alias="X-UWC-Signature"),
    x_uwc_timestamp: Optional[str] = Header(None, alias="X-UWC-Timestamp")
):
    """
    Webhook: UWC notifies Otto that ASR batch processing is complete.
    
    Expected payload (will be updated when UWC provides actual spec):
    {
        "job_id": "job_abc123",
        "company_id": "tenant_123",
        "call_id": "call_456",
        "status": "completed",
        "transcript": [
            {"speaker": "CSR", "text": "Hello, this is RoofCo!"},
            {"speaker": "Customer", "text": "Hi, I need a quote..."}
        ],
        "duration_sec": 540,
        "confidence": 0.94,
        "language": "en"
    }
    
    Otto's job:
    1. Verify HMAC signature
    2. Store transcript in calls table
    3. Emit real-time event to WebSocket subscribers
    4. Return 200 OK (idempotent)
    """
    # Get raw body for signature verification
    body = await request.body()
    
    # Verify signature if headers provided
    if x_uwc_signature and x_uwc_timestamp:
        if not await verify_uwc_signature(body, x_uwc_signature, x_uwc_timestamp):
            logger.warning("Invalid UWC webhook signature - rejecting request")
            metrics.record_webhook_failure("uwc")
            raise HTTPException(status_code=401, detail="Invalid signature")
    elif settings.is_production:
        logger.error("UWC webhook missing signature headers in production")
        raise HTTPException(status_code=401, detail="Signature required")
    
    # Parse payload
    payload = await request.json()
    
    job_id = payload.get("job_id")
    company_id = payload.get("company_id")
    call_id = payload.get("call_id")
    status = payload.get("status")
    transcript = payload.get("transcript")
    confidence = payload.get("confidence")
    duration_sec = payload.get("duration_sec")
    
    logger.info(
        f"Received ASR complete webhook: job_id={job_id}, "
        f"call_id={call_id}, status={status}, confidence={confidence}"
    )
    
    # Store transcript in database
    if call_id and transcript:
        db = SessionLocal()
        try:
            call_record = db.query(Call).filter(Call.call_id == call_id).first()
            
            if call_record:
                # Verify tenant ownership
                if call_record.company_id != company_id:
                    logger.error(
                        f"Tenant mismatch: call belongs to {call_record.company_id}, "
                        f"webhook claims {company_id}"
                    )
                    raise HTTPException(
                        status_code=403,
                        detail="Tenant mismatch"
                    )
                
                # Store transcript
                call_record.transcript = transcript
                call_record.transcript_confidence = confidence
                db.commit()
                
                logger.info(f"Stored transcript for call {call_id}")
                
                # Emit real-time event to WebSocket subscribers
                await emit(
                    "call.transcribed",
                    {
                        "call_id": call_id,
                        "duration_sec": duration_sec,
                        "confidence": confidence,
                        "status": status
                    },
                    tenant_id=company_id,
                    severity="info"
                )
                
                logger.info(f"Emitted call.transcribed event for call {call_id}")
            else:
                logger.warning(f"Call {call_id} not found in database")
        finally:
            db.close()
    else:
        logger.warning("Webhook missing call_id or transcript")
    
    # Record metrics
    metrics.record_webhook_processed("uwc", "asr_complete")
    
    return {"status": "received", "call_id": call_id}


@router.post("/rag/indexed")
@with_idempotency(provider="uwc", event_type="rag_indexed")
async def rag_indexed_webhook(
    request: Request,
    x_uwc_signature: Optional[str] = Header(None, alias="X-UWC-Signature"),
    x_uwc_timestamp: Optional[str] = Header(None, alias="X-UWC-Timestamp")
):
    """
    Webhook: UWC notifies Otto that document indexing is complete.
    
    Expected payload (will be updated when UWC provides actual spec):
    {
        "job_id": "doc_job_xyz789",
        "company_id": "tenant_123",
        "document_id": "doc_456",
        "status": "completed",
        "chunks_indexed": 42,
        "vectors_created": 42
    }
    
    Otto's job:
    1. Verify HMAC signature
    2. Update document status in database (when we have documents table)
    3. Emit real-time event
    4. Return 200 OK
    """
    body = await request.body()
    
    # Verify signature
    if x_uwc_signature and x_uwc_timestamp:
        if not await verify_uwc_signature(body, x_uwc_signature, x_uwc_timestamp):
            metrics.record_webhook_failure("uwc")
            raise HTTPException(status_code=401, detail="Invalid signature")
    elif settings.is_production:
        raise HTTPException(status_code=401, detail="Signature required")
    
    payload = await request.json()
    
    job_id = payload.get("job_id")
    company_id = payload.get("company_id")
    document_id = payload.get("document_id")
    status = payload.get("status")
    
    logger.info(
        f"Received RAG indexed webhook: job_id={job_id}, "
        f"document_id={document_id}, status={status}"
    )
    
    # TODO: Update document status in database when documents table exists
    # For now, just log and emit event
    
    # Emit real-time event
    await emit(
        "document.indexed",
        {
            "document_id": document_id,
            "status": status,
            "chunks_indexed": payload.get("chunks_indexed"),
            "vectors_created": payload.get("vectors_created")
        },
        tenant_id=company_id,
        severity="info"
    )
    
    metrics.record_webhook_processed("uwc", "rag_indexed")
    
    return {"status": "received", "document_id": document_id}


@router.post("/training/status")
@with_idempotency(provider="uwc", event_type="training_status")
async def training_status_webhook(
    request: Request,
    x_uwc_signature: Optional[str] = Header(None, alias="X-UWC-Signature"),
    x_uwc_timestamp: Optional[str] = Header(None, alias="X-UWC-Timestamp")
):
    """
    Webhook: UWC notifies Otto about personal clone training status updates.
    
    Expected payload (will be updated when UWC provides actual spec):
    {
        "job_id": "train_def456",
        "company_id": "tenant_123",
        "rep_id": "rep_789",
        "status": "completed",
        "progress": 100,
        "model_version": "v1.2.3",
        "training_duration_min": 45
    }
    
    Otto's job:
    1. Verify HMAC signature
    2. Update rep clone training status (when we have rep_profiles table)
    3. Emit real-time event to rep
    4. Return 200 OK
    """
    body = await request.body()
    
    # Verify signature
    if x_uwc_signature and x_uwc_timestamp:
        if not await verify_uwc_signature(body, x_uwc_signature, x_uwc_timestamp):
            metrics.record_webhook_failure("uwc")
            raise HTTPException(status_code=401, detail="Invalid signature")
    elif settings.is_production:
        raise HTTPException(status_code=401, detail="Signature required")
    
    payload = await request.json()
    
    job_id = payload.get("job_id")
    company_id = payload.get("company_id")
    rep_id = payload.get("rep_id")
    status = payload.get("status")
    progress = payload.get("progress", 0)
    
    logger.info(
        f"Received training status webhook: job_id={job_id}, "
        f"rep_id={rep_id}, status={status}, progress={progress}%"
    )
    
    # TODO: Update rep clone training status when rep_profiles table exists
    # For now, just log and emit event
    
    # Emit real-time event to rep's user channel
    await emit(
        "clone.training_status",
        {
            "rep_id": rep_id,
            "status": status,
            "progress": progress,
            "model_version": payload.get("model_version")
        },
        tenant_id=company_id,
        user_id=rep_id,  # Also send to rep's personal channel
        severity="info"
    )
    
    metrics.record_webhook_processed("uwc", "training_status")
    
    return {"status": "received", "rep_id": rep_id}


@router.post("/analysis/complete")
@with_idempotency(provider="uwc", event_type="analysis_complete")
async def analysis_complete_webhook(
    request: Request,
    x_uwc_signature: Optional[str] = Header(None, alias="X-UWC-Signature"),
    x_uwc_timestamp: Optional[str] = Header(None, alias="X-UWC-Timestamp")
):
    """
    Webhook: UWC notifies Otto that ML analysis is complete.
    
    Expected payload (will be updated when UWC provides actual spec):
    {
        "job_id": "analysis_ghi789",
        "company_id": "tenant_123",
        "call_id": "call_456",
        "status": "completed",
        "analysis": {
            "lead_classification": "qualified",
            "objections": ["price", "timeline"],
            "sop_stage": "present",
            "rehash_score": 7.5,
            "coaching_tips": [...]
        }
    }
    
    Otto's job:
    1. Verify HMAC signature
    2. Store analysis results in transcript_analyses table
    3. Emit real-time event with insights
    4. Return 200 OK
    """
    body = await request.body()
    
    # Verify signature
    if x_uwc_signature and x_uwc_timestamp:
        if not await verify_uwc_signature(body, x_uwc_signature, x_uwc_timestamp):
            metrics.record_webhook_failure("uwc")
            raise HTTPException(status_code=401, detail="Invalid signature")
    elif settings.is_production:
        raise HTTPException(status_code=401, detail="Signature required")
    
    payload = await request.json()
    
    job_id = payload.get("job_id")
    company_id = payload.get("company_id")
    call_id = payload.get("call_id")
    status = payload.get("status")
    analysis = payload.get("analysis", {})
    
    logger.info(
        f"Received analysis complete webhook: job_id={job_id}, "
        f"call_id={call_id}, status={status}"
    )
    
    # Store analysis results
    if call_id and analysis:
        db = SessionLocal()
        try:
            call_record = db.query(Call).filter(Call.call_id == call_id).first()
            
            if call_record:
                # Verify tenant ownership
                if call_record.company_id != company_id:
                    logger.error(
                        f"Tenant mismatch: call belongs to {call_record.company_id}, "
                        f"webhook claims {company_id}"
                    )
                    raise HTTPException(status_code=403, detail="Tenant mismatch")
                
                # TODO: Store analysis in transcript_analyses table
                # For now, just log
                logger.info(
                    f"Analysis for call {call_id}: "
                    f"lead_class={analysis.get('lead_classification')}, "
                    f"objections={analysis.get('objections')}, "
                    f"sop_stage={analysis.get('sop_stage')}"
                )
                
                # Emit real-time event with AI insights
                await emit(
                    "ai.analysis.complete",
                    {
                        "call_id": call_id,
                        "lead_classification": analysis.get("lead_classification"),
                        "objections": analysis.get("objections", []),
                        "sop_stage": analysis.get("sop_stage"),
                        "rehash_score": analysis.get("rehash_score"),
                        "coaching_tips": analysis.get("coaching_tips", [])
                    },
                    tenant_id=company_id,
                    user_id=call_record.assigned_rep_id,  # Notify assigned rep
                    severity="info"
                )
                
                logger.info(f"Emitted ai.analysis.complete event for call {call_id}")
            else:
                logger.warning(f"Call {call_id} not found in database")
        finally:
            db.close()
    
    metrics.record_webhook_processed("uwc", "analysis_complete")
    
    return {"status": "received", "call_id": call_id}


@router.post("/followup/draft")
@with_idempotency(provider="uwc", event_type="followup_draft")
async def followup_draft_webhook(
    request: Request,
    x_uwc_signature: Optional[str] = Header(None, alias="X-UWC-Signature"),
    x_uwc_timestamp: Optional[str] = Header(None, alias="X-UWC-Timestamp")
):
    """
    Webhook: UWC notifies Otto that follow-up draft is ready.
    
    Expected payload (will be updated when UWC provides actual spec):
    {
        "job_id": "draft_jkl012",
        "company_id": "tenant_123",
        "rep_id": "rep_789",
        "lead_id": "lead_345",
        "status": "completed",
        "draft": {
            "message": "Hi Mrs. Patel, I understand budget is a concern...",
            "tone": "empathetic",
            "confidence": 0.91,
            "channel": "sms"
        }
    }
    
    Otto's job:
    1. Verify HMAC signature
    2. Store draft in followup_drafts table (when it exists)
    3. Emit real-time event to rep
    4. Return 200 OK
    """
    body = await request.body()
    
    # Verify signature
    if x_uwc_signature and x_uwc_timestamp:
        if not await verify_uwc_signature(body, x_uwc_signature, x_uwc_timestamp):
            metrics.record_webhook_failure("uwc")
            raise HTTPException(status_code=401, detail="Invalid signature")
    elif settings.is_production:
        raise HTTPException(status_code=401, detail="Signature required")
    
    payload = await request.json()
    
    job_id = payload.get("job_id")
    company_id = payload.get("company_id")
    rep_id = payload.get("rep_id")
    lead_id = payload.get("lead_id")
    draft = payload.get("draft", {})
    
    logger.info(
        f"Received followup draft webhook: job_id={job_id}, "
        f"rep_id={rep_id}, lead_id={lead_id}"
    )
    
    # TODO: Store draft in followup_drafts table when it exists
    
    # Emit real-time event to rep
    await emit(
        "followup.draft_ready",
        {
            "lead_id": lead_id,
            "rep_id": rep_id,
            "draft_message": draft.get("message"),
            "tone": draft.get("tone"),
            "confidence": draft.get("confidence"),
            "channel": draft.get("channel")
        },
        tenant_id=company_id,
        user_id=rep_id,
        severity="info"
    )
    
    metrics.record_webhook_processed("uwc", "followup_draft")
    
    return {"status": "received", "rep_id": rep_id, "lead_id": lead_id}


