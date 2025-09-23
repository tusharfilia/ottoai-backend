"""
Health and readiness endpoints for production deployment.
"""
import time
import redis
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.config import settings
from app.obs.logging import get_logger
from app.obs.metrics import record_cache_hit, record_cache_miss

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "otto-api"
    }


@router.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """
    Comprehensive readiness check for production deployment.
    Checks database and Redis connectivity.
    """
    start_time = time.time()
    components = {}
    all_ready = True
    
    # Check database connectivity
    try:
        # Simple query to test database connection
        result = db.execute(text("SELECT 1")).fetchone()
        if result and result[0] == 1:
            components["database"] = True
            logger.info("Database readiness check: OK")
        else:
            components["database"] = False
            all_ready = False
            logger.error("Database readiness check: FAILED - unexpected result")
    except Exception as e:
        components["database"] = False
        all_ready = False
        logger.error(f"Database readiness check: FAILED - {str(e)}")
    
    # Check Redis connectivity (if Redis URL is configured)
    if settings.REDIS_URL:
        try:
            redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            # Test Redis with PING
            pong = redis_client.ping()
            if pong:
                components["redis"] = True
                logger.info("Redis readiness check: OK")
                record_cache_hit("redis_ping")
            else:
                components["redis"] = False
                all_ready = False
                logger.error("Redis readiness check: FAILED - no pong response")
                record_cache_miss("redis_ping")
        except Exception as e:
            components["redis"] = False
            all_ready = False
            logger.error(f"Redis readiness check: FAILED - {str(e)}")
            record_cache_miss("redis_ping")
    else:
        components["redis"] = False
        logger.warning("Redis readiness check: SKIPPED - no REDIS_URL configured")
    
    # Check Celery worker connectivity (if Celery is enabled)
    if settings.ENABLE_CELERY:
        try:
            from app.services.celery_tasks import celery_app
            
            # Quick Celery inspect with timeout
            inspect = celery_app.control.inspect(timeout=5.0)
            active_workers = inspect.active()
            
            if active_workers:
                components["celery_workers"] = True
                logger.info(f"Celery workers readiness check: OK - {len(active_workers)} workers active")
            else:
                components["celery_workers"] = False
                all_ready = False
                logger.warning("Celery workers readiness check: FAILED - no active workers")
                
        except Exception as e:
            components["celery_workers"] = False
            all_ready = False
            logger.error(f"Celery workers readiness check: FAILED - {str(e)}")
    else:
        components["celery_workers"] = None
        logger.info("Celery workers readiness check: SKIPPED - Celery not enabled")
    
    # Calculate total check duration
    duration_ms = (time.time() - start_time) * 1000
    
    # Prepare response
    response = {
        "ready": all_ready,
        "timestamp": time.time(),
        "duration_ms": round(duration_ms, 2),
        "components": components,
        "service": "otto-api"
    }
    
    # Log structured readiness status
    logger.info(
        "Readiness check completed",
        extra={
            "ready": all_ready,
            "duration_ms": duration_ms,
            "components": components,
            "service": "api"
        }
    )
    
    # Return appropriate HTTP status
    if all_ready:
        return response
    else:
        raise HTTPException(status_code=503, detail=response)


@router.get("/internal/worker/heartbeat")
async def worker_heartbeat():
    """
    Simple heartbeat endpoint for worker health checks.
    Can be called by load balancers or monitoring systems.
    """
    if not settings.ENABLE_CELERY:
        raise HTTPException(status_code=404, detail="Celery not enabled")
    
    try:
        from app.services.celery_tasks import celery_app
        
        # Create a simple task to test worker responsiveness
        from celery import current_app
        
        # Use a simple ping task
        result = celery_app.control.inspect(timeout=3.0)
        if result:
            return {
                "status": "healthy",
                "timestamp": time.time(),
                "service": "otto-worker"
            }
        else:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "unhealthy",
                    "timestamp": time.time(),
                    "service": "otto-worker",
                    "error": "No worker response"
                }
            )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "timestamp": time.time(),
                "service": "otto-worker",
                "error": str(e)
            }
        )
