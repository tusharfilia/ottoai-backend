"""
P0: Helper for Shunya job processing with distributed locking.

Provides a consistent pattern for processing Shunya jobs with distributed locking
to prevent webhook vs polling race conditions.
"""
import asyncio
from typing import Optional, Dict, Any, Callable
from sqlalchemy.orm import Session
from app.services.redis_lock_service import redis_lock_service
from app.services.shunya_job_service import shunya_job_service
from app.obs.logging import get_logger

logger = get_logger(__name__)


async def process_shunya_job_with_lock(
    db: Session,
    job,
    normalized_result: Dict[str, Any],
    process_fn: Callable,
    job_id: str
) -> Dict[str, Any]:
    """
    Process a Shunya job with distributed locking to prevent race conditions.
    
    This helper ensures that only one process (webhook or polling) can process
    a Shunya job at a time, preventing duplicate processing.
    
    Args:
        db: Database session
        job: ShunyaJob instance
        normalized_result: Normalized Shunya result
        process_fn: Function to call for processing (takes db, job, normalized_result)
        job_id: Job ID for logging
        
    Returns:
        Result dict with success status
    """
    lock_key = f"shunya_job:{job_id}"
    lock_token = None
    
    try:
        # Acquire distributed lock
        lock_token = await redis_lock_service.acquire_lock(
            lock_key=lock_key,
            tenant_id=job.company_id,
            timeout=300  # 5 minutes
        )
        
        if not lock_token:
            logger.warning(
                f"Could not acquire lock for Shunya job {job_id}, another process may be handling it",
                extra={"job_id": job_id, "shunya_job_id": job.shunya_job_id}
            )
            return {"success": False, "status": "processing_by_another"}
        
        # Check idempotency before processing (inside lock to prevent race)
        if not shunya_job_service.should_process(db, job, normalized_result):
            logger.info(
                f"Shunya job {job_id} already processed, skipping",
                extra={"job_id": job_id}
            )
            return {"success": True, "status": "already_processed"}
        
        # Process the job
        result = await process_fn(db, job, normalized_result)
        
        return result
        
    finally:
        # Always release lock
        if lock_token:
            await redis_lock_service.release_lock(
                lock_key=lock_key,
                tenant_id=job.company_id,
                lock_token=lock_token
            )


def process_shunya_job_with_lock_sync(
    db: Session,
    job,
    normalized_result: Dict[str, Any],
    process_fn: Callable,
    job_id: str
) -> Dict[str, Any]:
    """
    Synchronous wrapper for process_shunya_job_with_lock (for Celery tasks).
    
    Args:
        db: Database session
        job: ShunyaJob instance
        normalized_result: Normalized Shunya result
        process_fn: Function to call for processing (takes db, job, normalized_result)
        job_id: Job ID for logging
        
    Returns:
        Result dict with success status
    """
    return asyncio.run(
        process_shunya_job_with_lock(
            db=db,
            job=job,
            normalized_result=normalized_result,
            process_fn=process_fn,
            job_id=job_id
        )
    )



