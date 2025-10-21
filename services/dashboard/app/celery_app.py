"""
Celery configuration for Otto AI background tasks
"""
import os
from celery import Celery
from app.config import settings

# Create Celery instance
celery_app = Celery(
    "ottoai",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.asr_tasks",
        "app.tasks.analysis_tasks", 
        "app.tasks.followup_tasks",
        "app.tasks.indexing_tasks",
        "app.tasks.uwc_tasks"
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task routing
    task_routes={
        "app.tasks.asr_tasks.*": {"queue": "asr"},
        "app.tasks.analysis_tasks.*": {"queue": "analysis"},
        "app.tasks.followup_tasks.*": {"queue": "followups"},
        "app.tasks.indexing_tasks.*": {"queue": "indexing"},
        "app.tasks.uwc_tasks.*": {"queue": "uwc"},
    },
    
    # Queue configuration
    task_default_queue="default",
    task_queues={
        "default": {"exchange": "default", "routing_key": "default"},
        "asr": {"exchange": "asr", "routing_key": "asr"},
        "analysis": {"exchange": "analysis", "routing_key": "analysis"},
        "followups": {"exchange": "followups", "routing_key": "followups"},
        "indexing": {"exchange": "indexing", "routing_key": "indexing"},
        "uwc": {"exchange": "uwc", "routing_key": "uwc"},
    },
    
    # Task execution
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    
    # Retry configuration
    task_default_retry_delay=60,
    task_max_retries=3,
    task_retry_jitter=True,
    
    # Result backend
    result_expires=3600,  # 1 hour
    result_persistent=True,
    
    # Beat schedule for periodic tasks
    beat_schedule={
        "process-pending-transcriptions": {
            "task": "app.tasks.asr_tasks.process_pending_transcriptions",
            "schedule": 60.0,  # Every minute
        },
        "generate-daily-reports": {
            "task": "app.tasks.analysis_tasks.generate_daily_reports",
            "schedule": 86400.0,  # Daily
        },
        "cleanup-old-tasks": {
            "task": "app.tasks.cleanup_tasks.cleanup_old_tasks",
            "schedule": 3600.0,  # Hourly
        },
    },
)

# Optional: Configure task monitoring
if settings.ENVIRONMENT == "production":
    celery_app.conf.update(
        worker_send_task_events=True,
        task_send_sent_event=True,
    )
