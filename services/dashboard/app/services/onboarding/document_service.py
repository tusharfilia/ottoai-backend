"""
Service for handling document upload and ingestion onboarding step.
"""
import uuid
from typing import Optional
from fastapi import UploadFile
from sqlalchemy.orm import Session
from app.models.onboarding import Document, IngestionStatus, DocumentCategory
from app.services.storage import StorageService
from app.services.uwc_client import get_uwc_client
from app.obs.logging import get_logger
from app.schemas.onboarding import DocumentUploadRequest

logger = get_logger(__name__)


class DocumentService:
    """Service for document upload and ingestion."""
    
    def __init__(self):
        self.storage_service = StorageService()
        self.uwc_client = get_uwc_client()
    
    async def upload_document(
        self,
        db: Session,
        tenant_id: str,
        user_id: str,
        file: UploadFile,
        request: DocumentUploadRequest,
        trace_id: str
    ) -> dict:
        """
        Upload document to S3 and initiate Shunya ingestion.
        
        Args:
            db: Database session
            tenant_id: Tenant/company ID
            user_id: User ID
            file: Uploaded file
            request: Document upload request metadata
            trace_id: Request trace ID
            
        Returns:
            Document upload response
        """
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Upload to S3
        try:
            file.file.seek(0)  # Reset file pointer
            s3_url = await self.storage_service.upload_file(
                file=file.file,
                filename=file.filename,
                tenant_id=tenant_id,
                file_type="documents",
                content_type=file.content_type
            )
        except Exception as e:
            logger.error(
                f"Failed to upload document to S3: {str(e)}",
                extra={"tenant_id": tenant_id, "filename": file.filename}
            )
            raise ValueError(f"Failed to upload document: {str(e)}")
        
        # Create document record
        document = Document(
            id=document_id,
            company_id=tenant_id,
            filename=file.filename,
            category=DocumentCategory(request.category.value),
            role_target=request.role_target,
            s3_url=s3_url,
            ingestion_status=IngestionStatus.PENDING,
            metadata=request.metadata or {}
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        
        # Trigger Celery task for Shunya ingestion (async)
        try:
            from app.tasks.onboarding_tasks import ingest_document_with_shunya
            ingest_document_with_shunya.delay(
                document_id=document_id,
                tenant_id=tenant_id,
                trace_id=trace_id
            )
            logger.info(
                f"Document ingestion task queued for document {document_id}",
                extra={"tenant_id": tenant_id, "document_id": document_id}
            )
        except Exception as e:
            logger.error(
                f"Failed to queue ingestion task: {str(e)}",
                extra={"tenant_id": tenant_id, "document_id": document_id}
            )
            # Don't fail the upload - task can be retried later
            document.ingestion_status = IngestionStatus.PENDING
        
        db.commit()
        
        return {
            "success": True,
            "document_id": document_id,
            "filename": file.filename,
            "s3_url": s3_url,
            "ingestion_job_id": None,  # Will be set by Celery task
            "ingestion_status": document.ingestion_status.value,
            "estimated_processing_time": "2-5 minutes"
        }
    
    def get_document_status(
        self,
        db: Session,
        tenant_id: str,
        document_id: str
    ) -> dict:
        """
        Get document ingestion status.
        
        Args:
            db: Database session
            tenant_id: Tenant/company ID
            document_id: Document ID
            
        Returns:
            Document status response
        """
        document = db.query(Document).filter_by(
            id=document_id,
            company_id=tenant_id
        ).first()
        
        if not document:
            raise ValueError(f"Document not found: {document_id}")
        
        return {
            "document_id": document_id,
            "ingestion_status": document.ingestion_status.value,
            "ingestion_job_id": document.ingestion_job_id,
            "progress": None,  # Could be enhanced with Shunya status polling
            "error_message": None  # Could be stored in metadata
        }
    
    def check_all_documents_processed(
        self,
        db: Session,
        tenant_id: str
    ) -> bool:
        """
        Check if all documents for a company are processed.
        
        Args:
            db: Database session
            tenant_id: Tenant/company ID
            
        Returns:
            True if all documents are done or failed, False otherwise
        """
        pending_docs = db.query(Document).filter_by(
            company_id=tenant_id
        ).filter(
            Document.ingestion_status.in_([
                IngestionStatus.PENDING,
                IngestionStatus.PROCESSING
            ])
        ).count()
        
        return pending_docs == 0

