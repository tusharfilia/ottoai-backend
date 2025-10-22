"""
Idempotency middleware for Otto AI backend.
Prevents duplicate processing of mutating requests using Idempotency-Key header.
"""
import hashlib
import json
import time
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Response
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.idempotency import IdempotencyRecord
from app.obs.logging import get_logger

logger = get_logger(__name__)


class IdempotencyMiddleware:
    """Middleware for handling idempotency keys on mutating requests."""
    
    def __init__(self, ttl_seconds: int = 3600):  # 1 hour default TTL
        self.ttl_seconds = ttl_seconds
    
    async def __call__(self, request: Request, call_next):
        """Process request for idempotency."""
        # Only apply to mutating methods
        if request.method not in ["POST", "PUT", "PATCH", "DELETE"]:
            return await call_next(request)
        
        # Check for Idempotency-Key header
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            # For critical endpoints, require idempotency key
            critical_paths = [
                "/api/v1/calls",
                "/api/v1/leads", 
                "/api/v1/followups",
                "/api/v1/rag/documents",
                "/api/v1/clones/train"
            ]
            
            if any(request.url.path.startswith(path) for path in critical_paths):
                raise HTTPException(
                    status_code=400,
                    detail="Idempotency-Key header required for this endpoint"
                )
            
            # For other endpoints, proceed without idempotency
            return await call_next(request)
        
        # Validate idempotency key format
        if len(idempotency_key) < 10 or len(idempotency_key) > 255:
            raise HTTPException(
                status_code=400,
                detail="Idempotency-Key must be 10-255 characters"
            )
        
        # Get tenant context
        tenant_id = getattr(request.state, 'tenant_id', None)
        if not tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Tenant context required for idempotency"
            )
        
        # Create composite key (tenant + idempotency key)
        composite_key = f"{tenant_id}:{idempotency_key}"
        
        # Check for existing record
        db = SessionLocal()
        try:
            existing_record = db.query(IdempotencyRecord).filter_by(
                composite_key=composite_key
            ).first()
            
            if existing_record:
                # Check if record is still valid
                if time.time() - existing_record.created_at.timestamp() < self.ttl_seconds:
                    # Return cached response
                    logger.info(f"Returning cached response for idempotency key: {idempotency_key}")
                    
                    response_data = json.loads(existing_record.response_body)
                    status_code = existing_record.status_code
                    
                    return Response(
                        content=json.dumps(response_data),
                        status_code=status_code,
                        headers={"Content-Type": "application/json"}
                    )
                else:
                    # Record expired, delete it
                    db.delete(existing_record)
                    db.commit()
            
            # Process request
            response = await call_next(request)
            
            # Store response for future requests
            response_body = response.body.decode() if response.body else "{}"
            
            new_record = IdempotencyRecord(
                composite_key=composite_key,
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                response_body=response_body,
                created_at=time.time()
            )
            
            db.add(new_record)
            db.commit()
            
            logger.info(f"Stored idempotency record for key: {idempotency_key}")
            
            return response
            
        except Exception as e:
            logger.error(f"Idempotency processing failed: {str(e)}")
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Idempotency processing failed"
            )
        finally:
            db.close()


def require_idempotency_key(request: Request) -> str:
    """
    Dependency that requires Idempotency-Key header for mutating endpoints.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        str: The idempotency key
        
    Raises:
        HTTPException: 400 if key is missing or invalid
    """
    idempotency_key = request.headers.get("Idempotency-Key")
    
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key header is required for this endpoint"
        )
    
    if len(idempotency_key) < 10 or len(idempotency_key) > 255:
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key must be 10-255 characters"
        )
    
    return idempotency_key


def generate_idempotency_key(tenant_id: str, user_id: str, action: str, data: Dict[str, Any]) -> str:
    """
    Generate a deterministic idempotency key for a request.
    
    Args:
        tenant_id: Tenant identifier
        user_id: User identifier  
        action: Action being performed
        data: Request data
        
    Returns:
        str: Generated idempotency key
    """
    # Create deterministic hash from request components
    key_data = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "action": action,
        "data": data,
        "timestamp": int(time.time() / 60)  # Round to minute for some flexibility
    }
    
    key_string = json.dumps(key_data, sort_keys=True)
    key_hash = hashlib.sha256(key_string.encode()).hexdigest()
    
    return f"{tenant_id[:8]}-{key_hash[:16]}"


# Cleanup function for expired records
def cleanup_expired_idempotency_records(ttl_seconds: int = 3600):
    """Remove expired idempotency records."""
    db = SessionLocal()
    try:
        cutoff_time = time.time() - ttl_seconds
        expired_count = db.query(IdempotencyRecord).filter(
            IdempotencyRecord.created_at < cutoff_time
        ).delete()
        
        db.commit()
        logger.info(f"Cleaned up {expired_count} expired idempotency records")
        
    except Exception as e:
        logger.error(f"Failed to cleanup idempotency records: {str(e)}")
        db.rollback()
    finally:
        db.close()

