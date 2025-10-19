"""
Call Analysis endpoints for AI coaching, objection detection, and SOP tracking.
Triggers UWC ASR processing and retrieves analysis results.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta

from app.database import get_db
from app.middleware.rbac import require_role
from app.config import settings
from app.services.uwc_client import uwc_client
from app.services.audit_logger import AuditLogger
from app.models.call import Call
from app.models.call_transcript import CallTranscript
from app.models.call_analysis import CallAnalysis
from app.schemas.responses import APIResponse, ErrorResponse, ErrorCodes, create_error_response, JobStatusResponse
from app.obs.logging import get_logger
from app.obs.metrics import metrics

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/calls", tags=["analysis", "coaching"])


# Request/Response Schemas
class AnalyzeCallRequest(BaseModel):
    """Request to trigger call analysis."""
    include_transcript: bool = Field(True, description="Include transcript in analysis")
    include_coaching: bool = Field(True, description="Include coaching recommendations")
    include_objections: bool = Field(True, description="Include objection detection")
    include_sop: bool = Field(True, description="Include SOP stage tracking")


class CallAnalysisResponse(BaseModel):
    """Complete call analysis results."""
    call_id: int
    analysis_id: str
    status: str
    transcript: Optional[str] = None
    objections: Optional[List[str]] = None
    objection_details: Optional[List[Dict[str, Any]]] = None
    coaching_tips: Optional[List[Dict[str, Any]]] = None
    sentiment_score: Optional[float] = None
    sop_stages_completed: Optional[List[str]] = None
    sop_stages_missed: Optional[List[str]] = None
    sop_compliance_score: Optional[float] = None
    rehash_score: Optional[float] = None
    lead_quality: Optional[str] = None
    analyzed_at: Optional[str] = None


class ObjectionSummary(BaseModel):
    """Objection summary for analytics."""
    objection_type: str
    count: int
    percentage: float
    example_quotes: List[str]


class ObjectionAnalyticsResponse(BaseModel):
    """Objection analytics for dashboard."""
    date_range: str
    total_calls_analyzed: int
    top_objections: List[ObjectionSummary]
    objections_by_rep: Optional[Dict[str, List[ObjectionSummary]]] = None


# Endpoints

@router.post("/{call_id}/analyze", response_model=APIResponse[JobStatusResponse])
@require_role("exec", "manager", "rep")
async def analyze_call(
    request: Request,
    call_id: int,
    analyze_request: Optional[AnalyzeCallRequest] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """
    Trigger AI analysis on a call recording.
    
    Process:
    1. Verify call exists and user has access
    2. Send audio to UWC for ASR processing
    3. Return job_id for status tracking
    4. UWC will send webhook when complete
    
    Returns job_id immediately (async processing).
    """
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id
    user_role = request.state.user_role
    
    # Get call and verify access
    call = db.query(Call).filter_by(
        call_id=call_id,
        company_id=tenant_id
    ).first()
    
    if not call:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.CALL_NOT_FOUND,
                message=f"Call {call_id} not found",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Verify rep can only analyze their own calls
    if user_role == "rep" and call.assigned_rep_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code=ErrorCodes.FORBIDDEN,
                message="You can only analyze your own calls",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Check if already analyzed (prevent duplicate processing)
    existing_analysis = db.query(CallAnalysis).filter_by(
        call_id=call_id,
        tenant_id=tenant_id
    ).first()
    
    if existing_analysis:
        logger.info(f"Call already analyzed, returning existing analysis",
                   extra={"call_id": call_id, "analysis_id": existing_analysis.id})
        
        return APIResponse(
            data=JobStatusResponse(
                job_id=existing_analysis.uwc_job_id,
                status="completed",
                progress=100,
                message="Analysis already complete",
                created_at=existing_analysis.created_at,
                completed_at=existing_analysis.analyzed_at
            )
        )
    
    # Prepare audio URL for UWC
    audio_url = None
    if hasattr(call, 'audio_url') and call.audio_url:
        audio_url = call.audio_url
    elif hasattr(call, 'in_person_transcript') and call.in_person_transcript:
        # If we only have transcript, still send for analysis
        pass
    else:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code=ErrorCodes.VALIDATION_ERROR,
                message="Call has no audio or transcript to analyze",
                request_id=request.state.trace_id
            ).dict()
        )
    
    try:
        # Send to UWC for analysis
        if settings.ENABLE_UWC_ASR and settings.UWC_BASE_URL:
            uwc_result = await uwc_client.submit_asr_batch(
                company_id=tenant_id,
                audio_urls=[{
                    "url": audio_url,
                    "call_id": call_id,
                    "metadata": {
                        "tenant_id": tenant_id,
                        "rep_id": call.assigned_rep_id,
                        "call_date": call.created_at.isoformat() if call.created_at else None
                    }
                }],
                request_id=request.state.trace_id
            )
            
            job_id = uwc_result.get("job_id", f"uwc_{uuid.uuid4().hex}")
            status = "processing"
            
        else:
            # Mock response for development
            job_id = f"mock_{uuid.uuid4().hex}"
            status = "queued"
            
            # Simulate async processing with background task
            background_tasks.add_task(
                process_mock_analysis,
                db=db,
                call_id=call_id,
                tenant_id=tenant_id,
                job_id=job_id
            )
        
        logger.info(f"Call analysis triggered",
                   extra={
                       "call_id": call_id,
                       "tenant_id": tenant_id,
                       "job_id": job_id
                   })
        
        # Record metrics
        metrics.call_analyses_triggered_total.labels(
            tenant_id=tenant_id
        ).inc()
        
        # Return job status
        return APIResponse(
            data=JobStatusResponse(
                job_id=job_id,
                status=status,
                progress=0,
                message="Analysis queued, will complete shortly",
                created_at=datetime.utcnow()
            )
        )
        
    except Exception as e:
        logger.error(f"Failed to trigger call analysis: {str(e)}",
                    extra={"call_id": call_id, "tenant_id": tenant_id})
        
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_code=ErrorCodes.INTERNAL_ERROR,
                message="Failed to start analysis. Please try again.",
                request_id=request.state.trace_id
            ).dict()
        )


@router.get("/{call_id}/analysis", response_model=APIResponse[CallAnalysisResponse])
@require_role("exec", "manager", "rep")
async def get_call_analysis(
    request: Request,
    call_id: int,
    db: Session = Depends(get_db)
):
    """
    Get AI analysis results for a call.
    
    Returns:
    - Transcript with speaker labels
    - Objections detected
    - Coaching recommendations
    - SOP stages completed/missed
    - Sentiment and rehash scores
    """
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id
    user_role = request.state.user_role
    
    # Verify call exists and access
    call = db.query(Call).filter_by(
        call_id=call_id,
        company_id=tenant_id
    ).first()
    
    if not call:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.CALL_NOT_FOUND,
                message=f"Call {call_id} not found",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Reps can only view their own call analysis
    if user_role == "rep" and call.assigned_rep_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code=ErrorCodes.FORBIDDEN,
                message="You can only view analysis of your own calls",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Get analysis from database
    analysis = db.query(CallAnalysis).filter_by(
        call_id=call_id,
        tenant_id=tenant_id
    ).first()
    
    # Get transcript
    transcript_record = db.query(CallTranscript).filter_by(
        call_id=call_id,
        tenant_id=tenant_id
    ).first()
    
    if not analysis:
        # Analysis not yet complete
        return APIResponse(
            data=CallAnalysisResponse(
                call_id=call_id,
                analysis_id="pending",
                status="not_analyzed",
                transcript=transcript_record.transcript_text if transcript_record else None
            )
        )
    
    # Build response
    response = CallAnalysisResponse(
        call_id=call_id,
        analysis_id=analysis.id,
        status="complete",
        transcript=transcript_record.transcript_text if transcript_record else None,
        objections=analysis.objections,
        objection_details=analysis.objection_details,
        coaching_tips=analysis.coaching_tips,
        sentiment_score=analysis.sentiment_score,
        sop_stages_completed=analysis.sop_stages_completed,
        sop_stages_missed=analysis.sop_stages_missed,
        sop_compliance_score=analysis.sop_compliance_score,
        rehash_score=analysis.rehash_score,
        lead_quality=analysis.lead_quality,
        analyzed_at=analysis.analyzed_at.isoformat() if analysis.analyzed_at else None
    )
    
    return APIResponse(data=response)


@router.post("/analyze-batch", response_model=APIResponse[List[JobStatusResponse]])
@require_role("exec", "manager")
async def analyze_batch(
    request: Request,
    call_ids: List[int],
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """
    Trigger analysis on multiple calls at once.
    Useful for batch processing during onboarding.
    
    Limits: 50 calls per request.
    """
    tenant_id = request.state.tenant_id
    
    # Validate batch size
    if len(call_ids) > 50:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code=ErrorCodes.VALIDATION_ERROR,
                message="Batch size limited to 50 calls",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Verify all calls exist and belong to tenant
    calls = db.query(Call).filter(
        Call.call_id.in_(call_ids),
        Call.company_id == tenant_id
    ).all()
    
    if len(calls) != len(call_ids):
        missing = set(call_ids) - {c.call_id for c in calls}
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.CALL_NOT_FOUND,
                message=f"Calls not found: {missing}",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Prepare audio URLs for UWC
    audio_data = []
    for call in calls:
        if hasattr(call, 'audio_url') and call.audio_url:
            audio_data.append({
                "url": call.audio_url,
                "call_id": call.call_id,
                "metadata": {"tenant_id": tenant_id}
            })
    
    # Send batch to UWC
    if settings.ENABLE_UWC_ASR and settings.UWC_BASE_URL and audio_data:
        uwc_result = await uwc_client.submit_asr_batch(
            company_id=tenant_id,
            audio_urls=audio_data,
            request_id=request.state.trace_id
        )
        
        job_id = uwc_result.get("job_id")
        
    else:
        # Mock batch job
        job_id = f"mock_batch_{uuid.uuid4().hex}"
    
    # Return batch job status
    job_statuses = [
        JobStatusResponse(
            job_id=job_id,
            status="processing",
            progress=0,
            message=f"Analyzing {len(call_ids)} calls",
            created_at=datetime.utcnow()
        )
    ]
    
    logger.info(f"Batch analysis triggered",
               extra={
                   "call_count": len(call_ids),
                   "tenant_id": tenant_id,
                   "job_id": job_id
               })
    
    return APIResponse(data=job_statuses)


@router.get("/analytics/objections", response_model=APIResponse[ObjectionAnalyticsResponse])
@require_role("exec", "manager")
async def get_objection_analytics(
    request: Request,
    date_range: str = "last_30_days",
    rep_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get objection analytics for dashboard.
    
    Returns:
    - Top objections across all calls
    - Percentage breakdown
    - Example quotes
    - Optional: by-rep breakdown
    """
    tenant_id = request.state.tenant_id
    
    # Parse date range
    date_filters = parse_date_range(date_range)
    
    # Base query
    query = db.query(CallAnalysis).filter(
        CallAnalysis.tenant_id == tenant_id,
        CallAnalysis.created_at >= date_filters['start_date']
    )
    
    # Optional rep filter
    if rep_id:
        call_ids = db.query(Call.call_id).filter_by(
            company_id=tenant_id,
            assigned_rep_id=rep_id
        ).all()
        call_ids = [c[0] for c in call_ids]
        query = query.filter(CallAnalysis.call_id.in_(call_ids))
    
    # Get all analyses
    analyses = query.all()
    total_calls = len(analyses)
    
    if total_calls == 0:
        return APIResponse(
            data=ObjectionAnalyticsResponse(
                date_range=date_range,
                total_calls_analyzed=0,
                top_objections=[]
            )
        )
    
    # Aggregate objections
    objection_counts = {}
    objection_quotes = {}
    
    for analysis in analyses:
        if analysis.objections:
            for objection in analysis.objections:
                objection_counts[objection] = objection_counts.get(objection, 0) + 1
                
                # Collect example quotes
                if objection not in objection_quotes:
                    objection_quotes[objection] = []
                
                # Extract quote from objection_details if available
                if analysis.objection_details:
                    for detail in analysis.objection_details:
                        if detail.get('type') == objection and 'quote' in detail:
                            objection_quotes[objection].append(detail['quote'])
    
    # Build top objections list
    top_objections = []
    for objection, count in sorted(objection_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_calls) * 100
        example_quotes = objection_quotes.get(objection, [])[:3]  # Top 3 examples
        
        top_objections.append(
            ObjectionSummary(
                objection_type=objection,
                count=count,
                percentage=round(percentage, 1),
                example_quotes=example_quotes
            )
        )
    
    # Build response
    response = ObjectionAnalyticsResponse(
        date_range=date_range,
        total_calls_analyzed=total_calls,
        top_objections=top_objections[:10]  # Top 10 objections
    )
    
    logger.info(f"Objection analytics retrieved",
               extra={
                   "tenant_id": tenant_id,
                   "date_range": date_range,
                   "total_calls": total_calls,
                   "unique_objections": len(objection_counts)
               })
    
    return APIResponse(data=response)


def parse_date_range(date_range: str) -> Dict[str, datetime]:
    """Parse date range string into start/end dates."""
    now = datetime.utcnow()
    
    if date_range == "last_7_days":
        start_date = now - timedelta(days=7)
    elif date_range == "last_30_days":
        start_date = now - timedelta(days=30)
    elif date_range == "last_90_days":
        start_date = now - timedelta(days=90)
    elif date_range == "this_year":
        start_date = datetime(now.year, 1, 1)
    else:
        # Default to last 30 days
        start_date = now - timedelta(days=30)
    
    return {
        "start_date": start_date,
        "end_date": now
    }


# Background task for mock analysis processing
async def process_mock_analysis(db: Session, call_id: int, tenant_id: str, job_id: str):
    """
    Simulate analysis processing for development (when UWC not available).
    Creates mock transcript and analysis after a short delay.
    """
    import asyncio
    await asyncio.sleep(3)  # Simulate processing time
    
    try:
        # Create mock transcript
        transcript_id = str(uuid.uuid4())
        transcript = CallTranscript(
            id=transcript_id,
            call_id=call_id,
            tenant_id=tenant_id,
            uwc_job_id=job_id,
            transcript_text="[Mock transcript] This is a simulated transcript. Enable UWC_ASR for real transcription.",
            confidence_score=0.95,
            processing_time_ms=3000
        )
        db.add(transcript)
        
        # Create mock analysis
        analysis_id = str(uuid.uuid4())
        analysis = CallAnalysis(
            id=analysis_id,
            call_id=call_id,
            tenant_id=tenant_id,
            uwc_job_id=job_id,
            objections=["price", "need_to_think"],
            objection_details=[
                {
                    "type": "price",
                    "timestamp": 120.5,
                    "quote": "[Mock] That's more than I expected",
                    "resolved": False
                }
            ],
            coaching_tips=[
                {
                    "tip": "Set agenda earlier in conversation",
                    "priority": "high",
                    "category": "sales_process"
                }
            ],
            sentiment_score=0.65,
            sop_stages_completed=["connect", "agenda", "assess"],
            sop_stages_missed=["close", "referral"],
            sop_compliance_score=6.0,
            rehash_score=7.5,
            talk_time_ratio=0.35,
            lead_quality="qualified",
            conversion_probability=0.70
        )
        db.add(analysis)
        db.commit()
        
        logger.info(f"Mock analysis completed",
                   extra={"call_id": call_id, "analysis_id": analysis_id})
        
    except Exception as e:
        logger.error(f"Mock analysis failed: {str(e)}",
                    extra={"call_id": call_id})

