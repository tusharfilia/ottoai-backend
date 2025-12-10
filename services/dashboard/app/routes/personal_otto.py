"""
Personal Otto (AI Clone) routes for sales rep AI profile training.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import uuid4

from app.database import get_db
from app.middleware.rbac import require_role
from app.core.tenant import get_tenant_id
from app.services.personal_otto_service import personal_otto_service
from app.schemas.responses import APIResponse
from app.config import settings
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)
router = APIRouter(prefix="/api/v1/personal-otto", tags=["personal-otto"])


# Request/Response Schemas
class IngestDocumentsRequest(BaseModel):
    """Request to ingest training documents."""
    documents: List[Dict[str, Any]] = Field(..., description="List of training documents with content and metadata")
    rep_id: Optional[str] = Field(None, description="Sales rep ID (defaults to authenticated user)")


class TrainRequest(BaseModel):
    """Request to trigger Personal Otto training."""
    rep_id: Optional[str] = Field(None, description="Sales rep ID (defaults to authenticated user)")
    force_retrain: bool = Field(False, description="Force retraining even if already trained")


@router.post("/ingest-documents", response_model=APIResponse[dict])
@require_role("sales_rep")
async def ingest_documents(
    request: Request,
    ingest_request: IngestDocumentsRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Ingest training documents for Personal Otto (AI clone) training.
    
    RBAC: sales_rep only
    
    Args:
        ingest_request: Request with documents list
        tenant_id: Tenant ID from JWT
        db: Database session
    
    Returns:
        Ingestion response with job_id, status
    """
    if not settings.ENABLE_PERSONAL_OTTO:
        raise HTTPException(
            status_code=503,
            detail="Personal Otto feature is not enabled"
        )
    
    # Get rep_id from request or authenticated user
    rep_id = ingest_request.rep_id or request.state.user_id
    
    if not rep_id:
        raise HTTPException(
            status_code=400,
            detail="rep_id is required"
        )
    
    # Verify rep belongs to tenant (if rep_id is different from user_id)
    if rep_id != request.state.user_id:
        # TODO: Add verification that rep_id belongs to tenant
        # For now, only allow users to ingest for themselves
        raise HTTPException(
            status_code=403,
            detail="Cannot ingest documents for other users"
        )
    
    try:
        request_id = str(uuid4())
        result = await personal_otto_service.ingest_documents_for_rep(
            db=db,
            company_id=tenant_id,
            rep_id=rep_id,
            documents=ingest_request.documents,
            request_id=request_id
        )
        
        logger.info(
            f"Ingested Personal Otto documents for rep {rep_id}",
            extra={"rep_id": rep_id, "company_id": tenant_id, "document_count": len(ingest_request.documents)}
        )
        
        return APIResponse(
            success=True,
            data=result
        )
        
    except Exception as e:
        logger.error(
            f"Failed to ingest Personal Otto documents for rep {rep_id}: {str(e)}",
            extra={"rep_id": rep_id, "company_id": tenant_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to ingest documents: {str(e)}"
        )


@router.post("/train", response_model=APIResponse[dict])
@require_role("sales_rep")
async def train_personal_otto(
    request: Request,
    train_request: TrainRequest,
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Trigger Personal Otto (AI clone) training for a sales rep.
    
    RBAC: sales_rep only
    Idempotent: Can be called multiple times safely
    
    Args:
        train_request: Request with optional rep_id and force_retrain flag
        tenant_id: Tenant ID from JWT
        db: Database session
    
    Returns:
        Training response with job_id, status, estimated_completion_time
    """
    if not settings.ENABLE_PERSONAL_OTTO:
        raise HTTPException(
            status_code=503,
            detail="Personal Otto feature is not enabled"
        )
    
    # Get rep_id from request or authenticated user
    rep_id = train_request.rep_id or request.state.user_id
    
    if not rep_id:
        raise HTTPException(
            status_code=400,
            detail="rep_id is required"
        )
    
    # Verify rep belongs to tenant (if rep_id is different from user_id)
    if rep_id != request.state.user_id:
        # TODO: Add verification that rep_id belongs to tenant
        # For now, only allow users to train for themselves
        raise HTTPException(
            status_code=403,
            detail="Cannot trigger training for other users"
        )
    
    try:
        request_id = str(uuid4())
        result = await personal_otto_service.trigger_training_for_rep(
            db=db,
            company_id=tenant_id,
            rep_id=rep_id,
            request_id=request_id,
            force_retrain=train_request.force_retrain
        )
        
        logger.info(
            f"Triggered Personal Otto training for rep {rep_id}",
            extra={"rep_id": rep_id, "company_id": tenant_id, "force_retrain": train_request.force_retrain}
        )
        
        return APIResponse(
            success=True,
            data=result
        )
        
    except Exception as e:
        logger.error(
            f"Failed to trigger Personal Otto training for rep {rep_id}: {str(e)}",
            extra={"rep_id": rep_id, "company_id": tenant_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger training: {str(e)}"
        )


@router.get("/status", response_model=APIResponse[dict])
@require_role("sales_rep")
async def get_personal_otto_status(
    request: Request,
    rep_id: Optional[str] = None,
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get Personal Otto (AI clone) training status for a sales rep.
    
    RBAC: sales_rep only
    
    Args:
        rep_id: Optional sales rep ID (defaults to authenticated user)
        tenant_id: Tenant ID from JWT
        db: Database session
    
    Returns:
        Status response with is_trained, training_status, last_trained_at, etc.
    """
    if not settings.ENABLE_PERSONAL_OTTO:
        raise HTTPException(
            status_code=503,
            detail="Personal Otto feature is not enabled"
        )
    
    # Get rep_id from query param or authenticated user
    rep_id = rep_id or request.state.user_id
    
    if not rep_id:
        raise HTTPException(
            status_code=400,
            detail="rep_id is required"
        )
    
    # Verify rep belongs to tenant (if rep_id is different from user_id)
    if rep_id != request.state.user_id:
        # TODO: Add verification that rep_id belongs to tenant
        # For now, only allow users to check status for themselves
        raise HTTPException(
            status_code=403,
            detail="Cannot check status for other users"
        )
    
    try:
        request_id = str(uuid4())
        result = await personal_otto_service.get_status_for_rep(
            db=db,
            company_id=tenant_id,
            rep_id=rep_id,
            request_id=request_id
        )
        
        return APIResponse(
            success=True,
            data=result
        )
        
    except Exception as e:
        logger.error(
            f"Failed to get Personal Otto status for rep {rep_id}: {str(e)}",
            extra={"rep_id": rep_id, "company_id": tenant_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get status: {str(e)}"
        )


@router.get("/profile", response_model=APIResponse[dict])
@require_role("sales_rep")
async def get_personal_otto_profile(
    request: Request,
    rep_id: Optional[str] = None,
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get Personal Otto (AI clone) profile for a sales rep.
    
    RBAC: sales_rep only
    
    Args:
        rep_id: Optional sales rep ID (defaults to authenticated user)
        tenant_id: Tenant ID from JWT
        db: Database session
    
    Returns:
        Profile response with personality_traits, writing_style, communication_preferences, etc.
    """
    if not settings.ENABLE_PERSONAL_OTTO:
        raise HTTPException(
            status_code=503,
            detail="Personal Otto feature is not enabled"
        )
    
    # Get rep_id from query param or authenticated user
    rep_id = rep_id or request.state.user_id
    
    if not rep_id:
        raise HTTPException(
            status_code=400,
            detail="rep_id is required"
        )
    
    # Verify rep belongs to tenant (if rep_id is different from user_id)
    if rep_id != request.state.user_id:
        # TODO: Add verification that rep_id belongs to tenant
        # For now, only allow users to get profile for themselves
        raise HTTPException(
            status_code=403,
            detail="Cannot get profile for other users"
        )
    
    try:
        request_id = str(uuid4())
        result = await personal_otto_service.get_profile_for_rep(
            db=db,
            company_id=tenant_id,
            rep_id=rep_id,
            request_id=request_id
        )
        
        return APIResponse(
            success=True,
            data=result
        )
        
    except Exception as e:
        logger.error(
            f"Failed to get Personal Otto profile for rep {rep_id}: {str(e)}",
            extra={"rep_id": rep_id, "company_id": tenant_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get profile: {str(e)}"
        )

