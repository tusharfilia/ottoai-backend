"""
Celery tasks for onboarding processes.
"""
import asyncio
from celery import Task
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.onboarding import Document, IngestionStatus
from app.services.uwc_client import get_uwc_client
from app.services.celery_tasks import celery_app
from app.obs.logging import get_logger
from app.obs.tracing import trace_celery_task

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def ingest_document_with_shunya(
    self: Task,
    document_id: str,
    tenant_id: str,
    trace_id: str
) -> dict:
    """
    Ingest document with Shunya/UWC.
    
    This task:
    1. Loads document from database
    2. Calls Shunya ingestion API
    3. Updates document status
    4. Polls for completion (or relies on webhook)
    
    Args:
        document_id: Document ID
        tenant_id: Tenant/company ID
        trace_id: Request trace ID
        
    Returns:
        Task result dict
    """
    task_name = "ingest_document_with_shunya"
    task_id = self.request.id
    
    with trace_celery_task(task_name, task_id) as span:
        db: Session = SessionLocal()
        try:
            # Load document
            document = db.query(Document).filter_by(
                id=document_id,
                company_id=tenant_id
            ).first()
            
            if not document:
                logger.error(
                    f"Document not found: {document_id}",
                    extra={"tenant_id": tenant_id, "document_id": document_id}
                )
                return {"status": "error", "error": "Document not found"}
            
            # Check if already processed (idempotency)
            if document.ingestion_status == IngestionStatus.DONE:
                logger.info(
                    f"Document already processed: {document_id}",
                    extra={"tenant_id": tenant_id, "document_id": document_id}
                )
                return {"status": "already_processed", "document_id": document_id}
            
            # Update status to processing
            document.ingestion_status = IngestionStatus.PROCESSING
            db.commit()
            
            # Call Shunya ingestion API
            uwc_client = get_uwc_client()
            if not uwc_client.is_available():
                logger.error(
                    "UWC client not available",
                    extra={"tenant_id": tenant_id, "document_id": document_id}
                )
                document.ingestion_status = IngestionStatus.FAILED
                db.commit()
                return {"status": "error", "error": "UWC not available"}
            
            try:
                # Run async UWC client call
                result = asyncio.run(
                    uwc_client.ingest_document(
                        company_id=tenant_id,
                        request_id=trace_id,
                        file_url=document.s3_url,
                        document_type=document.category.value,
                        filename=document.filename,
                        metadata={
                            "document_id": document_id,
                            "role_target": document.role_target,
                            **document.metadata_json or {}
                        }
                    )
                )
                
                # Extract job ID from response
                job_id = (
                    result.get("job_id") or
                    result.get("processing_job_id") or
                    result.get("upload_id") or
                    result.get("document_id")
                )
                
                if job_id:
                    document.ingestion_job_id = str(job_id)
                    db.commit()
                    
                    logger.info(
                        f"Document ingestion started: {document_id}",
                        extra={
                            "tenant_id": tenant_id,
                            "document_id": document_id,
                            "job_id": job_id
                        }
                    )
                    
                    # Note: Status will be updated via webhook or polling task
                    return {
                        "status": "processing",
                        "document_id": document_id,
                        "job_id": job_id
                    }
                else:
                    # If no job_id, assume synchronous completion
                    document.ingestion_status = IngestionStatus.DONE
                    db.commit()
                    return {
                        "status": "completed",
                        "document_id": document_id
                    }
                    
            except Exception as e:
                logger.error(
                    f"Shunya ingestion failed: {str(e)}",
                    extra={"tenant_id": tenant_id, "document_id": document_id},
                    exc_info=True
                )
                document.ingestion_status = IngestionStatus.FAILED
                db.commit()
                
                # Retry if retryable
                if self.request.retries < self.max_retries:
                    raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
                
                return {"status": "error", "error": str(e)}
                
        except Exception as e:
            logger.error(
                f"Unexpected error in document ingestion task: {str(e)}",
                extra={"tenant_id": tenant_id, "document_id": document_id},
                exc_info=True
            )
            if self.request.retries < self.max_retries:
                raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
            return {"status": "error", "error": str(e)}
        finally:
            db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def test_callrail_connection(
    self: Task,
    company_id: str,
    api_key: str,
    account_id: str
) -> dict:
    """
    Test CallRail API connection.
    
    Args:
        company_id: Company ID
        api_key: CallRail API key
        account_id: CallRail account ID
        
    Returns:
        Test result dict
    """
    task_name = "test_callrail_connection"
    task_id = self.request.id
    
    with trace_celery_task(task_name, task_id) as span:
        import httpx
        
        try:
            async def _test():
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # Test by fetching account info
                    response = await client.get(
                        f"https://api.callrail.com/v3/accounts/{account_id}.json",
                        headers={"Authorization": f"Token {api_key}"}
                    )
                    response.raise_for_status()
                    return response.json()
            
            account_data = asyncio.run(_test())
            
            logger.info(
                f"CallRail connection test successful for company {company_id}",
                extra={"company_id": company_id}
            )
            
            return {
                "status": "success",
                "connected": True,
                "account_name": account_data.get("name")
            }
        except Exception as e:
            logger.error(
                f"CallRail connection test failed: {str(e)}",
                extra={"company_id": company_id},
                exc_info=True
            )
            if self.request.retries < self.max_retries:
                raise self.retry(exc=e, countdown=30)
            return {
                "status": "error",
                "connected": False,
                "error": str(e)
            }


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def test_twilio_connection(
    self: Task,
    company_id: str,
    account_sid: str,
    auth_token: str
) -> dict:
    """
    Test Twilio API connection.
    
    Args:
        company_id: Company ID
        account_sid: Twilio Account SID
        auth_token: Twilio Auth Token
        
    Returns:
        Test result dict
    """
    task_name = "test_twilio_connection"
    task_id = self.request.id
    
    with trace_celery_task(task_name, task_id) as span:
        import httpx
        
        try:
            async def _test():
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # Test by fetching account info
                    response = await client.get(
                        f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}.json",
                        auth=(account_sid, auth_token)
                    )
                    response.raise_for_status()
                    return response.json()
            
            account_data = asyncio.run(_test())
            
            logger.info(
                f"Twilio connection test successful for company {company_id}",
                extra={"company_id": company_id}
            )
            
            return {
                "status": "success",
                "connected": True,
                "account_name": account_data.get("friendly_name")
            }
        except Exception as e:
            logger.error(
                f"Twilio connection test failed: {str(e)}",
                extra={"company_id": company_id},
                exc_info=True
            )
            if self.request.retries < self.max_retries:
                raise self.retry(exc=e, countdown=30)
            return {
                "status": "error",
                "connected": False,
                "error": str(e)
            }

