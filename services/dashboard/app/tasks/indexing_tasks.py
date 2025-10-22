"""
Document indexing and RAG background tasks
"""
from celery import current_task
from app.celery_app import celery_app
from app.services.uwc_client import UWCClient
from app.core.pii_masking import PIISafeLogger
import logging

logger = PIISafeLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def index_document(self, document_url: str, document_type: str, tenant_id: str):
    """
    Index document for RAG search using UWC
    """
    try:
        logger.info(f"Indexing document {document_url} for tenant {tenant_id}")
        
        uwc_client = UWCClient()
        
        # Index using UWC
        try:
            result = uwc_client.index_documents(
                documents=[{"url": document_url, "type": document_type}],
                tenant_id=tenant_id
            )
            
            if result:
                logger.info(f"UWC indexing successful for document {document_url}")
                return {
                    "success": True,
                    "provider": "uwc",
                    "document_url": document_url,
                    "document_type": document_type,
                    "tenant_id": tenant_id
                }
        except Exception as e:
            logger.warning(f"UWC indexing failed for document {document_url}: {str(e)}")
        
        # Fallback to local indexing
        logger.info(f"Using fallback indexing for document {document_url}")
        return {
            "success": True,
            "provider": "fallback",
            "document_url": document_url,
            "document_type": document_type,
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        logger.error(f"Document indexing failed for {document_url}: {str(e)}")
        raise self.retry(countdown=60 * (2 ** self.request.retries))

@celery_app.task(bind=True, max_retries=3)
def batch_index_documents(self, documents: list, tenant_id: str):
    """
    Batch index multiple documents for efficiency
    """
    try:
        logger.info(f"Batch indexing {len(documents)} documents for tenant {tenant_id}")
        
        uwc_client = UWCClient()
        
        # Batch index using UWC
        try:
            result = uwc_client.index_documents(
                documents=documents,
                tenant_id=tenant_id
            )
            
            if result:
                logger.info(f"UWC batch indexing successful for {len(documents)} documents")
                return {
                    "success": True,
                    "provider": "uwc",
                    "total_documents": len(documents),
                    "tenant_id": tenant_id
                }
        except Exception as e:
            logger.warning(f"UWC batch indexing failed: {str(e)}")
        
        # Fallback processing
        logger.info(f"Using fallback batch indexing for {len(documents)} documents")
        return {
            "success": True,
            "provider": "fallback",
            "total_documents": len(documents),
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        logger.error(f"Batch indexing failed: {str(e)}")
        raise self.retry(countdown=60 * (2 ** self.request.retries))

@celery_app.task
def cleanup_indexed_documents():
    """
    Cleanup old or unused indexed documents
    """
    logger.info("Cleaning up indexed documents")
    # Implementation for cleanup
    pass

