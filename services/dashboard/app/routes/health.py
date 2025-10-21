"""
Health check and monitoring endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
import redis
import httpx
import asyncio
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }

@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Detailed health check with all dependencies"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "checks": {}
    }
    
    # Check database
    try:
        db.execute("SELECT 1")
        health_status["checks"]["database"] = {"status": "healthy", "response_time_ms": 0}
    except Exception as e:
        health_status["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "unhealthy"
    
    # Check Redis
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        start_time = datetime.utcnow()
        redis_client.ping()
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        health_status["checks"]["redis"] = {"status": "healthy", "response_time_ms": response_time}
    except Exception as e:
        health_status["checks"]["redis"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "unhealthy"
    
    # Check S3
    try:
        import boto3
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_DEFAULT_REGION
        )
        start_time = datetime.utcnow()
        s3_client.head_bucket(Bucket=settings.S3_BUCKET)
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        health_status["checks"]["s3"] = {"status": "healthy", "response_time_ms": response_time}
    except Exception as e:
        health_status["checks"]["s3"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "unhealthy"
    
    # Check UWC/Shunya API
    try:
        async with httpx.AsyncClient() as client:
            start_time = datetime.utcnow()
            response = await client.get(f"{settings.UWC_BASE_URL}/health", timeout=5.0)
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            if response.status_code == 200:
                health_status["checks"]["uwc"] = {"status": "healthy", "response_time_ms": response_time}
            else:
                health_status["checks"]["uwc"] = {"status": "degraded", "response_time_ms": response_time, "status_code": response.status_code}
    except Exception as e:
        health_status["checks"]["uwc"] = {"status": "unhealthy", "error": str(e)}
        # Don't mark overall status as unhealthy for UWC issues
    
    return health_status

@router.get("/health/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Kubernetes readiness probe"""
    try:
        # Check if database is accessible
        db.execute("SELECT 1")
        
        # Check if Redis is accessible
        redis_client = redis.from_url(settings.REDIS_URL)
        redis_client.ping()
        
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")

@router.get("/health/live")
async def liveness_check():
    """Kubernetes liveness probe"""
    return {"status": "alive"}

@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    # This would integrate with Prometheus metrics
    # For now, return basic metrics
    return {
        "otto_requests_total": 0,
        "otto_requests_duration_seconds": 0,
        "otto_errors_total": 0,
        "otto_active_connections": 0
    }