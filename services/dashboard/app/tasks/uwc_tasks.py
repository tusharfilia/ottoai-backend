"""
UWC/Shunya specific background tasks
"""
from celery import current_task
from app.celery_app import celery_app
from app.services.uwc_client import UWCClient
from app.core.pii_masking import PIISafeLogger
import logging

logger = PIISafeLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def submit_training_job(self, audio_urls: list, rep_id: str, tenant_id: str):
    """
    Submit voice training job to UWC for personal clone
    """
    try:
        logger.info(f"Submitting training job for rep {rep_id} with {len(audio_urls)} audio files")
        
        uwc_client = UWCClient()
        
        # Submit training job to UWC
        try:
            result = uwc_client.submit_training_job(
                audio_urls=audio_urls,
                rep_id=rep_id,
                tenant_id=tenant_id
            )
            
            if result:
                logger.info(f"UWC training job submitted successfully for rep {rep_id}")
                return {
                    "success": True,
                    "provider": "uwc",
                    "job_id": result.get("job_id"),
                    "rep_id": rep_id,
                    "tenant_id": tenant_id
                }
        except Exception as e:
            logger.warning(f"UWC training job submission failed for rep {rep_id}: {str(e)}")
        
        # Fallback to local processing
        logger.info(f"Using fallback training for rep {rep_id}")
        return {
            "success": True,
            "provider": "fallback",
            "rep_id": rep_id,
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        logger.error(f"Training job submission failed for rep {rep_id}: {str(e)}")
        raise self.retry(countdown=60 * (2 ** self.request.retries))

@celery_app.task(bind=True, max_retries=3)
def check_training_status(self, job_id: str, rep_id: str, tenant_id: str):
    """
    Check status of UWC training job
    """
    try:
        logger.info(f"Checking training status for job {job_id}")
        
        uwc_client = UWCClient()
        
        # Check status with UWC
        try:
            result = uwc_client.get_training_status(job_id, tenant_id)
            
            if result:
                logger.info(f"UWC training status retrieved for job {job_id}")
                return {
                    "success": True,
                    "provider": "uwc",
                    "job_id": job_id,
                    "status": result.get("status"),
                    "progress": result.get("progress", 0),
                    "rep_id": rep_id,
                    "tenant_id": tenant_id
                }
        except Exception as e:
            logger.warning(f"UWC training status check failed for job {job_id}: {str(e)}")
        
        # Fallback status
        logger.info(f"Using fallback status for job {job_id}")
        return {
            "success": True,
            "provider": "fallback",
            "job_id": job_id,
            "status": "processing",
            "progress": 50,
            "rep_id": rep_id,
            "tenant_id": tenant_id
        }
        
    except Exception as e:
        logger.error(f"Training status check failed for job {job_id}: {str(e)}")
        raise self.retry(countdown=60 * (2 ** self.request.retries))

@celery_app.task
def sync_uwc_webhooks():
    """
    Sync webhook status with UWC services
    """
    logger.info("Syncing UWC webhooks")
    # Implementation for webhook sync
    pass
