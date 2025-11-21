"""
Shunya Integration Celery Tasks

Background tasks for processing calls and appointments through Shunya pipeline.
"""
from celery import current_task
from app.celery_app import celery_app
from app.services.shunya_integration_service import shunya_integration_service
from app.core.pii_masking import PIISafeLogger
import asyncio

logger = PIISafeLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def process_call_with_shunya(
    self,
    call_id: int,
    audio_url: str,
    company_id: str,
    call_type: str = "csr_call"
):
    """
    Process a CSR call through Shunya pipeline.
    
    This task:
    1. Transcribes audio via Shunya
    2. Analyzes call (qualification, objections, SOP compliance)
    3. Persists results into Otto domain models
    4. Updates Lead status
    5. Creates Appointment if booked
    6. Creates Tasks from pending actions
    7. Triggers property intelligence if address extracted
    8. Emits domain events
    
    Args:
        call_id: Call ID
        audio_url: Publicly accessible audio URL
        company_id: Company/tenant ID
        call_type: "csr_call" or "sales_call"
    
    Returns:
        Dict with processing status
    """
    try:
        logger.info(f"Starting Shunya processing for call {call_id}")
        
        # Run async service method
        result = asyncio.run(
            shunya_integration_service.process_csr_call(
                call_id=call_id,
                audio_url=audio_url,
                company_id=company_id,
                call_type=call_type
            )
        )
        
        if not result.get("success"):
            logger.error(f"Shunya processing failed for call {call_id}: {result.get('error')}")
            # Retry on failure
            raise self.retry(
                countdown=60 * (2 ** self.request.retries),
                exc=Exception(result.get("error", "Unknown error"))
            )
        
        logger.info(f"Successfully processed call {call_id} via Shunya")
        return result
        
    except Exception as e:
        logger.error(f"Error processing call {call_id} with Shunya: {str(e)}", exc_info=True)
        raise self.retry(
            countdown=60 * (2 ** self.request.retries),
            exc=e
        )


@celery_app.task(bind=True, max_retries=3)
def process_visit_with_shunya(
    self,
    recording_session_id: str,
    audio_url: str,
    company_id: str
):
    """
    Process a sales visit recording through Shunya pipeline.
    
    This task:
    1. Transcribes audio (if not ghost mode)
    2. Analyzes visit (outcome, objections, SOP compliance)
    3. Updates Appointment and Lead status
    4. Creates Tasks from visit actions
    5. Emits domain events
    
    Args:
        recording_session_id: RecordingSession ID
        audio_url: Publicly accessible audio URL (may be None in ghost mode)
        company_id: Company/tenant ID
    
    Returns:
        Dict with processing status
    """
    try:
        logger.info(f"Starting Shunya processing for visit {recording_session_id}")
        
        # Run async service method
        result = asyncio.run(
            shunya_integration_service.process_sales_visit(
                recording_session_id=recording_session_id,
                audio_url=audio_url,
                company_id=company_id
            )
        )
        
        if not result.get("success"):
            logger.error(f"Shunya processing failed for visit {recording_session_id}: {result.get('error')}")
            # Retry on failure
            raise self.retry(
                countdown=60 * (2 ** self.request.retries),
                exc=Exception(result.get("error", "Unknown error"))
            )
        
        logger.info(f"Successfully processed visit {recording_session_id} via Shunya")
        return result
        
    except Exception as e:
        logger.error(f"Error processing visit {recording_session_id} with Shunya: {str(e)}", exc_info=True)
        raise self.retry(
            countdown=60 * (2 ** self.request.retries),
            exc=e
        )

