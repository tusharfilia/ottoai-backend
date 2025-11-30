"""
GDPR compliance endpoints for data deletion and privacy rights.
Implements Right to Erasure, Right to Access, and data portability.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
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
from app.services.storage import storage_service
from app.models.user import User
from app.models.call import Call
from app.models.call_transcript import CallTranscript
from app.models.call_analysis import CallAnalysis
from app.models.rag_document import RAGDocument
from app.models.rag_query import RAGQuery
from app.models.followup_draft import FollowUpDraft
from app.models.personal_clone_job import PersonalCloneJob
from app.schemas.responses import APIResponse, ErrorResponse, ErrorCodes, create_error_response
from app.obs.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/gdpr", tags=["gdpr", "privacy", "compliance"])


# Request/Response Schemas
class DataDeletionRequest(BaseModel):
    """Request to delete user data (GDPR Right to Erasure)."""
    user_id: str = Field(..., description="User ID to delete data for")
    reason: str = Field("gdpr_request", description="Reason for deletion")
    confirm: bool = Field(..., description="Must be true to confirm deletion")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "reason": "gdpr_request",
                "confirm": True
            }
        }


class DataDeletionResponse(BaseModel):
    """Response after data deletion."""
    user_id: str
    status: str
    deleted_records: Dict[str, int]
    s3_files_deleted: int
    uwc_deletion_requested: bool
    completed_at: str


class UserDataExportResponse(BaseModel):
    """Response for data export (GDPR Right to Access)."""
    user_id: str
    export_url: str
    expires_at: str
    file_size_bytes: int


# Endpoints

@router.post("/delete-user", response_model=APIResponse[DataDeletionResponse])
@require_role("manager")
async def delete_user_data(
    request: Request,
    deletion_request: DataDeletionRequest,
    db: Session = Depends(get_db)
):
    """
    Delete all user data (GDPR Right to Erasure).
    
    WARNING: This is irreversible and deletes:
    - User account
    - All calls assigned to user
    - All transcripts and analyses
    - All RAG queries
    - All follow-up drafts
    - All personal clone jobs
    - All uploaded documents
    - All S3 files
    - Requests UWC deletion via their API
    
    Only execs can perform this operation.
    Requires explicit confirmation.
    """
    tenant_id = request.state.tenant_id
    executor_user_id = request.state.user_id
    target_user_id = deletion_request.user_id
    
    # Require explicit confirmation
    if not deletion_request.confirm:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code=ErrorCodes.VALIDATION_ERROR,
                message="Must set confirm=true to delete user data",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Verify user exists and belongs to company
    user = db.query(User).filter_by(
        id=target_user_id,
        company_id=tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.USER_NOT_FOUND,
                message=f"User {target_user_id} not found in your company",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Prevent self-deletion
    if target_user_id == executor_user_id:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code=ErrorCodes.OPERATION_NOT_ALLOWED,
                message="Cannot delete your own account",
                request_id=request.state.trace_id
            ).dict()
        )
    
    deletion_stats = {
        "calls": 0,
        "transcripts": 0,
        "analyses": 0,
        "rag_queries": 0,
        "documents": 0,
        "followup_drafts": 0,
        "clone_jobs": 0
    }
    s3_files_deleted = 0
    uwc_deletion_requested = False
    
    try:
        # 1. Delete uploaded documents and S3 files
        documents = db.query(RAGDocument).filter_by(
            tenant_id=tenant_id,
            uploaded_by=target_user_id
        ).all()
        
        for doc in documents:
            # Delete from S3
            if settings.is_storage_configured() and doc.file_url:
                try:
                    await storage_service.delete_file(doc.file_url, tenant_id)
                    s3_files_deleted += 1
                except Exception as e:
                    logger.warning(f"Failed to delete S3 file: {str(e)}")
            
            # Delete from UWC
            if settings.ENABLE_UWC_RAG and doc.uwc_job_id:
                try:
                    uwc_client = get_uwc_client()
                    await uwc_client.delete_document(
                        company_id=tenant_id,
                        document_id=doc.id,
                        uwc_job_id=doc.uwc_job_id
                    )
                    uwc_deletion_requested = True
                except Exception as e:
                    logger.warning(f"Failed to delete from UWC: {str(e)}")
            
            # Delete database record
            db.delete(doc)
            deletion_stats["documents"] += 1
        
        # 2. Delete RAG queries
        rag_queries = db.query(RAGQuery).filter_by(
            tenant_id=tenant_id,
            user_id=target_user_id
        ).all()
        
        for query in rag_queries:
            db.delete(query)
            deletion_stats["rag_queries"] += 1
        
        # 3. Delete follow-up drafts
        drafts = db.query(FollowUpDraft).filter_by(
            tenant_id=tenant_id,
            generated_for=target_user_id
        ).all()
        
        for draft in drafts:
            db.delete(draft)
            deletion_stats["followup_drafts"] += 1
        
        # 4. Delete personal clone jobs
        clone_jobs = db.query(PersonalCloneJob).filter_by(
            tenant_id=tenant_id,
            rep_id=target_user_id
        ).all()
        
        for job in clone_jobs:
            # Request UWC to delete clone model
            if settings.ENABLE_UWC_TRAINING and job.model_id:
                try:
                    uwc_client = get_uwc_client()
                    await uwc_client.delete_clone_model(
                        company_id=tenant_id,
                        rep_id=target_user_id,
                        model_id=job.model_id
                    )
                    uwc_deletion_requested = True
                except Exception as e:
                    logger.warning(f"Failed to delete clone model: {str(e)}")
            
            db.delete(job)
            deletion_stats["clone_jobs"] += 1
        
        # 5. Delete call analyses for user's calls
        user_call_ids = [c.call_id for c in db.query(Call).filter_by(
            company_id=tenant_id,
            assigned_rep_id=target_user_id
        ).all()]
        
        if user_call_ids:
            analyses = db.query(CallAnalysis).filter(
                CallAnalysis.tenant_id == tenant_id,
                CallAnalysis.call_id.in_(user_call_ids)
            ).all()
            
            for analysis in analyses:
                db.delete(analysis)
                deletion_stats["analyses"] += 1
            
            # Delete transcripts
            transcripts = db.query(CallTranscript).filter(
                CallTranscript.tenant_id == tenant_id,
                CallTranscript.call_id.in_(user_call_ids)
            ).all()
            
            for transcript in transcripts:
                db.delete(transcript)
                deletion_stats["transcripts"] += 1
            
            # Delete calls
            calls = db.query(Call).filter_by(
                company_id=tenant_id,
                assigned_rep_id=target_user_id
            ).all()
            
            for call in calls:
                db.delete(call)
                deletion_stats["calls"] += 1
        
        # 6. Delete user record last
        db.delete(user)
        
        # Commit all deletions
        db.commit()
        
        # Audit log
        audit = AuditLogger(db, request)
        audit.log_user_deletion(
            deleted_user_id=target_user_id,
            deleted_email=user.email,
            reason=deletion_request.reason
        )
        
        logger.warning(f"User data deletion completed",
                      extra={
                          "target_user_id": target_user_id,
                          "deleted_email": user.email,
                          "deletion_stats": deletion_stats,
                          "s3_files_deleted": s3_files_deleted,
                          "executor_user_id": executor_user_id,
                          "tenant_id": tenant_id
                      })
        
        # Return summary
        return APIResponse(
            data=DataDeletionResponse(
                user_id=target_user_id,
                status="deleted",
                deleted_records=deletion_stats,
                s3_files_deleted=s3_files_deleted,
                uwc_deletion_requested=uwc_deletion_requested,
                completed_at=datetime.utcnow().isoformat()
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"User data deletion failed: {str(e)}",
                    extra={"target_user_id": target_user_id, "tenant_id": tenant_id})
        
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_code=ErrorCodes.INTERNAL_ERROR,
                message="Failed to delete user data. Please contact support.",
                request_id=request.state.trace_id
            ).dict()
        )


@router.post("/export-user-data")
@require_role("manager", "sales_rep")
async def export_user_data(
    request: Request,
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Export all user data (GDPR Right to Access).
    
    Generates JSON export of all user data and uploads to S3.
    Returns presigned URL for download (expires in 24 hours).
    
    Reps can export their own data.
    Execs can export any user's data.
    """
    tenant_id = request.state.tenant_id
    requester_id = request.state.user_id
    user_role = request.state.user_role
    
    # Reps can only export their own data
    if user_role == "sales_rep" and user_id != requester_id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code=ErrorCodes.FORBIDDEN,
                message="You can only export your own data",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Verify user exists
    user = db.query(User).filter_by(
        id=user_id,
        company_id=tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.USER_NOT_FOUND,
                message=f"User {user_id} not found",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Collect all user data
    export_data = {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "phone_number": user.phone_number
        },
        "calls": [],
        "rag_queries": [],
        "documents_uploaded": [],
        "followup_drafts": [],
        "clone_training_jobs": [],
        "export_generated_at": datetime.utcnow().isoformat()
    }
    
    # Get all calls
    calls = db.query(Call).filter_by(
        company_id=tenant_id,
        assigned_rep_id=user_id
    ).all()
    
    for call in calls:
        export_data["calls"].append({
            "call_id": call.call_id,
            "customer_name": call.name,
            "phone_number": call.phone_number,
            "created_at": call.created_at.isoformat() if call.created_at else None,
            "transcript": call.transcript
        })
    
    # Get RAG queries
    queries = db.query(RAGQuery).filter_by(
        tenant_id=tenant_id,
        user_id=user_id
    ).all()
    
    for query in queries:
        export_data["rag_queries"].append(query.to_dict())
    
    # Get uploaded documents
    docs = db.query(RAGDocument).filter_by(
        tenant_id=tenant_id,
        uploaded_by=user_id
    ).all()
    
    for doc in docs:
        export_data["documents_uploaded"].append(doc.to_dict())
    
    # TODO: Generate JSON file, upload to S3, return presigned URL
    # For now, return inline data
    
    logger.info(f"User data export generated",
               extra={
                   "user_id": user_id,
                   "tenant_id": tenant_id,
                   "data_size": len(str(export_data))
               })
    
    return APIResponse(
        data={
            "status": "export_generated",
            "user_id": user_id,
            "data": export_data
        }
    )


@router.delete("/tenant-data")
@require_role("manager")
async def delete_tenant_data(
    request: Request,
    confirm_company_name: str,
    db: Session = Depends(get_db)
):
    """
    Delete ALL company data (company offboarding).
    
    WARNING: This is EXTREMELY destructive!
    Requires company name confirmation.
    
    Deletes:
    - All users
    - All calls
    - All analyses
    - All documents
    - All S3 files
    - Requests full UWC deletion
    
    Only execs can perform this.
    """
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id
    
    # Get company
    from app.models.company import Company
    company = db.query(Company).filter_by(id=tenant_id).first()
    
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Require exact company name match for confirmation
    if confirm_company_name != company.name:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code=ErrorCodes.VALIDATION_ERROR,
                message=f"Company name confirmation does not match. Expected: '{company.name}'",
                request_id=request.state.trace_id
            ).dict()
        )
    
    try:
        # Delete all S3 files for tenant
        if settings.is_storage_configured():
            s3_deleted = await storage_service.delete_tenant_files(tenant_id)
            logger.warning(f"Deleted {s3_deleted} S3 files for tenant {tenant_id}")
        
        # Request UWC to delete all tenant data
        if settings.is_uwc_enabled():
            try:
                uwc_client = get_uwc_client()
                await uwc_client.delete_tenant_data(
                    company_id=tenant_id,
                    request_id=request.state.trace_id
                )
                logger.info("UWC tenant deletion requested")
            except Exception as e:
                logger.error(f"Failed to request UWC deletion: {str(e)}")
        
        # Delete all database records (CASCADE should handle most)
        db.query(RAGQuery).filter_by(tenant_id=tenant_id).delete()
        db.query(FollowUpDraft).filter_by(tenant_id=tenant_id).delete()
        db.query(PersonalCloneJob).filter_by(tenant_id=tenant_id).delete()
        db.query(CallAnalysis).filter_by(tenant_id=tenant_id).delete()
        db.query(CallTranscript).filter_by(tenant_id=tenant_id).delete()
        db.query(RAGDocument).filter_by(tenant_id=tenant_id).delete()
        db.query(Call).filter_by(company_id=tenant_id).delete()
        db.query(User).filter_by(company_id=tenant_id).delete()
        # Note: Company record remains for audit purposes
        
        db.commit()
        
        # Audit log
        audit = AuditLogger(db, request)
        audit.log_action(
            action="tenant_data_deleted",
            resource_type="company",
            resource_id=tenant_id,
            metadata={"company_name": company.name},
            success="success"
        )
        
        logger.critical(f"TENANT DATA DELETION COMPLETED",
                       extra={
                           "tenant_id": tenant_id,
                           "company_name": company.name,
                           "executor_user_id": user_id
                       })
        
        return APIResponse(
            data={
                "status": "deleted",
                "tenant_id": tenant_id,
                "company_name": company.name,
                "completed_at": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Tenant data deletion failed: {str(e)}",
                    extra={"tenant_id": tenant_id})
        
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_code=ErrorCodes.INTERNAL_ERROR,
                message="Failed to delete tenant data. Please contact support.",
                request_id=request.state.trace_id
            ).dict()
        )



