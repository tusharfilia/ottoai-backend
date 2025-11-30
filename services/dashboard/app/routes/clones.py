"""
Personal Clone endpoints for voice/style training.
Enables reps to train AI that mimics their communication style.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime

from app.database import get_db
from app.middleware.rbac import require_role
from app.config import settings
from app.services.uwc_client import get_uwc_client
from app.services.audit_logger import AuditLogger
from app.models.sales_rep import SalesRep
from app.models.personal_clone_job import PersonalCloneJob, TrainingStatus, TrainingDataType
from app.schemas.responses import APIResponse, PaginatedResponse, PaginationMeta, ErrorResponse, ErrorCodes, create_error_response, JobStatusResponse
from app.obs.logging import get_logger
from app.obs.metrics import metrics

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/clone", tags=["personal-clone", "training"])


# Request/Response Schemas
class TrainCloneRequest(BaseModel):
    """Request to train personal clone."""
    rep_id: str = Field(..., description="Sales rep ID to train clone for")
    training_data_type: str = Field(..., description="Type of training data: calls, media, mixed")
    training_call_ids: Optional[List[int]] = Field(None, description="Call IDs to use for training")
    training_media_urls: Optional[List[str]] = Field(None, description="Video URLs (reels, shorts, presentations)")
    notes: Optional[str] = Field(None, description="Notes about training data")
    
    class Config:
        json_schema_extra = {
            "example": {
                "rep_id": "rep_123",
                "training_data_type": "mixed",
                "training_call_ids": [101, 102, 103],
                "training_media_urls": [
                    "https://youtube.com/shorts/abc123",
                    "https://tiktok.com/@user/video/xyz789"
                ],
                "notes": "Using top 3 performing calls + Instagram reels"
            }
        }


class CloneStatusResponse(BaseModel):
    """Personal clone training status."""
    job_id: str
    rep_id: str
    status: str
    progress_percent: int
    current_epoch: Optional[int] = None
    total_epochs: Optional[int] = None
    quality_score: Optional[int] = None
    model_id: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


# Endpoints

@router.post("/train", response_model=APIResponse[JobStatusResponse])
@require_role("manager", "sales_rep")
async def train_personal_clone(
    request: Request,
    train_request: TrainCloneRequest,
    db: Session = Depends(get_db)
):
    """
    Submit personal clone training job.
    
    Takes reels/shorts/call recordings to learn rep's communication style.
    Training takes 2-4 hours typically.
    
    Process:
    1. Validate rep exists and user has access
    2. Validate training data
    3. Submit to UWC for training
    4. Track job status
    5. UWC sends webhook when complete
    """
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id
    user_role = request.state.user_role
    
    # Validate training data type
    try:
        data_type_enum = TrainingDataType(train_request.training_data_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code=ErrorCodes.VALIDATION_ERROR,
                message=f"Invalid training_data_type. Must be one of: {[t.value for t in TrainingDataType]}",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Verify rep exists and belongs to company
    rep = db.query(SalesRep).filter_by(
        user_id=train_request.rep_id,
        company_id=tenant_id
    ).first()
    
    if not rep:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message=f"Sales rep {train_request.rep_id} not found",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Reps can only train their own clone
    if user_role == "sales_rep" and train_request.rep_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code=ErrorCodes.FORBIDDEN,
                message="You can only train your own personal clone",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Validate training data provided
    if not train_request.training_call_ids and not train_request.training_media_urls:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code=ErrorCodes.VALIDATION_ERROR,
                message="Must provide either training_call_ids or training_media_urls",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Check for existing active training job
    existing_job = db.query(PersonalCloneJob).filter_by(
        tenant_id=tenant_id,
        rep_id=train_request.rep_id
    ).filter(
        PersonalCloneJob.status.in_([TrainingStatus.PENDING, TrainingStatus.PROCESSING])
    ).first()
    
    if existing_job:
        logger.warning(f"Training already in progress for rep {train_request.rep_id}")
        return APIResponse(
            data=JobStatusResponse(
                job_id=existing_job.uwc_job_id,
                status=existing_job.status.value,
                progress=existing_job.progress_percent,
                message="Training already in progress",
                created_at=existing_job.created_at
            )
        )
    
    try:
        # Prepare training data for UWC
        training_data = {
            "call_ids": train_request.training_call_ids or [],
            "media_urls": train_request.training_media_urls or []
        }
        
        # Submit to UWC for training
        if settings.ENABLE_UWC_TRAINING and settings.UWC_BASE_URL:
            uwc_client = get_uwc_client()
            uwc_result = await uwc_client.submit_training_job(
                company_id=tenant_id,
                rep_id=train_request.rep_id,
                training_data=training_data,
                request_id=request.state.trace_id
            )
            
            job_id = uwc_result.get("job_id")
            estimated_completion = uwc_result.get("estimated_completion")
            
        else:
            # Mock training job
            job_id = f"mock_training_{uuid.uuid4().hex}"
            estimated_completion = None
        
        # Create job tracking record
        clone_job = PersonalCloneJob(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            rep_id=train_request.rep_id,
            training_data_type=data_type_enum,
            training_call_ids=train_request.training_call_ids,
            training_media_urls=train_request.training_media_urls,
            total_media_count=len(train_request.training_call_ids or []) + len(train_request.training_media_urls or []),
            uwc_job_id=job_id,
            status=TrainingStatus.PENDING,
            initiated_by=user_id,
            notes=train_request.notes
        )
        db.add(clone_job)
        db.commit()
        
        logger.info(f"Personal clone training submitted",
                   extra={
                       "job_id": job_id,
                       "rep_id": train_request.rep_id,
                       "tenant_id": tenant_id,
                       "data_count": clone_job.total_media_count
                   })
        
        # Record metrics
        metrics.clone_training_jobs_total.labels(
            tenant_id=tenant_id
        ).inc()
        
        # Return job status
        return APIResponse(
            data=JobStatusResponse(
                job_id=job_id,
                status="pending",
                progress=0,
                message="Training job submitted successfully",
                created_at=clone_job.created_at
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit training job: {str(e)}",
                    extra={"rep_id": train_request.rep_id, "tenant_id": tenant_id})
        
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_code=ErrorCodes.INTERNAL_ERROR,
                message="Failed to submit training job. Please try again.",
                request_id=request.state.trace_id
            ).dict()
        )


@router.get("/{rep_id}/status", response_model=APIResponse[CloneStatusResponse])
@require_role("manager", "sales_rep")
async def get_clone_status(
    request: Request,
    rep_id: str,
    db: Session = Depends(get_db)
):
    """
    Get training status for rep's personal clone.
    Returns latest training job status.
    """
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id
    user_role = request.state.user_role
    
    # Verify rep exists
    rep = db.query(SalesRep).filter_by(
        user_id=rep_id,
        company_id=tenant_id
    ).first()
    
    if not rep:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message=f"Sales rep {rep_id} not found",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Reps can only check their own clone status
    if user_role == "sales_rep" and rep_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code=ErrorCodes.FORBIDDEN,
                message="You can only check your own clone status",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Get latest training job
    latest_job = db.query(PersonalCloneJob).filter_by(
        tenant_id=tenant_id,
        rep_id=rep_id
    ).order_by(PersonalCloneJob.created_at.desc()).first()
    
    if not latest_job:
        return APIResponse(
            data=CloneStatusResponse(
                job_id="none",
                rep_id=rep_id,
                status="not_trained",
                progress_percent=0,
                created_at=datetime.utcnow().isoformat()
            )
        )
    
    # Build response
    response = CloneStatusResponse(
        job_id=latest_job.uwc_job_id,
        rep_id=rep_id,
        status=latest_job.status.value,
        progress_percent=latest_job.progress_percent or 0,
        current_epoch=latest_job.current_epoch,
        total_epochs=latest_job.total_epochs,
        quality_score=latest_job.quality_score,
        model_id=latest_job.model_id,
        created_at=latest_job.created_at.isoformat(),
        started_at=latest_job.started_at.isoformat() if latest_job.started_at else None,
        completed_at=latest_job.completed_at.isoformat() if latest_job.completed_at else None,
        error_message=latest_job.error_message
    )
    
    return APIResponse(data=response)


@router.get("/{rep_id}/history", response_model=PaginatedResponse[Dict])
@require_role("manager")
async def get_clone_training_history(
    request: Request,
    rep_id: str,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    """
    Get training history for a rep (all past jobs).
    Only accessible by exec/manager.
    """
    tenant_id = request.state.tenant_id
    
    # Base query
    query = db.query(PersonalCloneJob).filter_by(
        tenant_id=tenant_id,
        rep_id=rep_id
    )
    
    # Get total
    total = query.count()
    
    # Paginate
    jobs = query.order_by(PersonalCloneJob.created_at.desc())\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()
    
    # Convert to dicts
    items = [job.to_dict() for job in jobs]
    
    # Build pagination
    total_pages = (total + page_size - 1) // page_size
    
    return PaginatedResponse(
        items=items,
        meta=PaginationMeta(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
    )


@router.post("/{rep_id}/retry")
@require_role("manager")
async def retry_failed_training(
    request: Request,
    rep_id: str,
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Retry a failed training job.
    Resubmits same training data to UWC.
    """
    tenant_id = request.state.tenant_id
    
    # Find failed job
    job = db.query(PersonalCloneJob).filter_by(
        uwc_job_id=job_id,
        tenant_id=tenant_id,
        rep_id=rep_id,
        status=TrainingStatus.FAILED
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message=f"Failed training job {job_id} not found",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Prepare same training data
    training_data = {
        "call_ids": job.training_call_ids or [],
        "media_urls": job.training_media_urls or []
    }
    
    # Resubmit to UWC
    if settings.ENABLE_UWC_TRAINING and settings.UWC_BASE_URL:
        uwc_client = get_uwc_client()
        uwc_result = await uwc_client.submit_training_job(
            company_id=tenant_id,
            rep_id=rep_id,
            training_data=training_data,
            request_id=request.state.trace_id
        )
        
        new_job_id = uwc_result.get("job_id")
    else:
        new_job_id = f"mock_retry_{uuid.uuid4().hex}"
    
    # Update job record
    job.retry_count += 1
    job.last_retry_at = datetime.utcnow()
    job.status = TrainingStatus.PENDING
    job.error_message = None
    job.uwc_job_id = new_job_id  # New UWC job ID
    db.commit()
    
    logger.info(f"Training job retry submitted",
               extra={
                   "original_job_id": job_id,
                   "new_job_id": new_job_id,
                   "rep_id": rep_id,
                   "retry_count": job.retry_count
               })
    
    return APIResponse(
        data=JobStatusResponse(
            job_id=new_job_id,
            status="pending",
            progress=0,
            message=f"Training job retry submitted (attempt #{job.retry_count})",
            created_at=datetime.utcnow()
        )
    )



