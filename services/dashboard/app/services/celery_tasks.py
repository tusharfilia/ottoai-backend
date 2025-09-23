"""
Celery tasks for background processing and maintenance.
"""
import os
import time
from celery import Celery
from celery.schedules import crontab
from app.services.idempotency import cleanup_old_idempotency_keys
from app.obs.logging import get_logger, log_celery_task
from app.obs.tracing import instrument_celery, get_tracer, trace_celery_task
from app.obs.metrics import record_worker_task

# Setup observability for Celery
instrument_celery()

logger = get_logger(__name__)
tracer = get_tracer(__name__)

# Initialize Celery
celery_app = Celery('ottoai_backend')

# Make celery_app available at module level for CLI
app = celery_app

# Configure Celery
celery_app.conf.update(
    broker_url=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    'cleanup-idempotency-keys': {
        'task': 'app.services.celery_tasks.cleanup_idempotency_keys_task',
        'schedule': crontab(hour=2, minute=0),  # Daily at 02:00 UTC
    },
}

celery_app.conf.timezone = 'UTC'


@celery_app.task(bind=True)
def cleanup_idempotency_keys_task(self):
    """
    Periodic task to clean up old idempotency keys.
    Runs daily at 02:00 UTC.
    """
    start_time = time.time()
    task_name = "cleanup_idempotency_keys"
    task_id = self.request.id
    
    # Create span for tracing
    with trace_celery_task(task_name, task_id) as span:
        try:
            logger.info("Starting idempotency keys cleanup task")
            
            # Run the cleanup function
            deleted_count = cleanup_old_idempotency_keys()
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log success
            log_celery_task(
                logger=logger,
                task_name=task_name,
                task_id=task_id,
                status="success",
                duration_ms=duration_ms
            )
            
            # Record metrics
            record_worker_task(task_name, "success", duration_ms)
            
            return {
                'status': 'success',
                'deleted_count': deleted_count,
                'task_id': task_id
            }
            
        except Exception as e:
            # Calculate duration for error case
            duration_ms = (time.time() - start_time) * 1000
            
            # Log failure
            log_celery_task(
                logger=logger,
                task_name=task_name,
                task_id=task_id,
                status="failure",
                duration_ms=duration_ms,
                error=str(e)
            )
            
            # Record metrics
            record_worker_task(task_name, "failure", duration_ms)
            
            raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(bind=True)
def test_task(self):
    """Simple test task to verify Celery is working."""
    start_time = time.time()
    task_name = "test_task"
    task_id = self.request.id
    
    # Create span for tracing
    with trace_celery_task(task_name, task_id) as span:
        try:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log success
            log_celery_task(
                logger=logger,
                task_name=task_name,
                task_id=task_id,
                status="success",
                duration_ms=duration_ms
            )
            
            # Record metrics
            record_worker_task(task_name, "success", duration_ms)
            
            return {'status': 'success', 'message': 'Celery is working', 'task_id': task_id}
            
        except Exception as e:
            # Calculate duration for error case
            duration_ms = (time.time() - start_time) * 1000
            
            # Log failure
            log_celery_task(
                logger=logger,
                task_name=task_name,
                task_id=task_id,
                status="failure",
                duration_ms=duration_ms,
                error=str(e)
            )
            
            # Record metrics
            record_worker_task(task_name, "failure", duration_ms)
            
            raise


# Optional: Add a manual trigger task for testing
@celery_app.task
def manual_cleanup_idempotency_keys():
    """
    Manual trigger for idempotency keys cleanup.
    Useful for testing and emergency cleanup.
    """
    try:
        logger.info("Manual idempotency keys cleanup triggered")
        deleted_count = cleanup_old_idempotency_keys()
        
        logger.info(
            f"Manual idempotency keys cleanup completed",
            extra={
                'deleted_count': deleted_count,
                'task': 'manual_cleanup_idempotency_keys'
            }
        )
        
        return {
            'status': 'success',
            'deleted_count': deleted_count,
            'trigger': 'manual'
        }
        
    except Exception as e:
        logger.error(
            f"Manual idempotency keys cleanup failed: {str(e)}",
            extra={
                'error': str(e),
                'task': 'manual_cleanup_idempotency_keys'
            },
            exc_info=True
        )
        raise
