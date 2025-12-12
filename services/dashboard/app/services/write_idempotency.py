"""
P0: Idempotency for write endpoints (recording sessions, appointment assignment).

Provides idempotency protection for write operations using Idempotency-Key header.
Returns cached response for duplicate requests.
"""
import logging
from typing import Optional, Dict, Any, Tuple, Callable
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Request, HTTPException, Header
from app.obs.logging import get_logger

logger = get_logger(__name__)


def get_idempotency_key(request: Request) -> Optional[str]:
    """
    Extract Idempotency-Key from request headers.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        Idempotency key if present, None otherwise
    """
    return request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")


def check_write_idempotency(
    db: Session,
    tenant_id: str,
    idempotency_key: str,
    operation_type: str,
    resource_id: Optional[str] = None
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Check if a write operation has already been processed (idempotency check).
    
    Args:
        db: Database session
        tenant_id: Tenant ID
        idempotency_key: Idempotency key from header
        operation_type: Operation type (e.g., "recording_session_start", "appointment_assign")
        resource_id: Optional resource ID for additional uniqueness
        
    Returns:
        Tuple of (is_duplicate: bool, cached_response: Optional[dict])
    """
    if not idempotency_key:
        return False, None
    
    try:
        # Check if this idempotency key has been used
        check_query = text("""
            SELECT first_processed_at
            FROM idempotency_keys
            WHERE tenant_id = :tenant_id
            AND provider = :operation_type
            AND external_id = :idempotency_key
            AND first_processed_at IS NOT NULL
        """)
        
        result = db.execute(check_query, {
            'tenant_id': tenant_id,
            'operation_type': operation_type,
            'idempotency_key': idempotency_key
        }).fetchone()
        
        if result and result[0]:  # Already processed
            logger.info(
                f"Idempotency key {idempotency_key} already processed for {operation_type}",
                extra={
                    'tenant_id': tenant_id,
                    'operation_type': operation_type,
                    'idempotency_key': idempotency_key,
                    'first_processed_at': result[0].isoformat() if result[0] else None
                }
            )
            
            # Return True to indicate duplicate (caller should handle response)
            return True, None
        
        return False, None
        
    except Exception as e:
        logger.error(f"Error checking idempotency: {str(e)}")
        # On error, allow operation to proceed (fail open)
        return False, None


def store_write_idempotency(
    db: Session,
    tenant_id: str,
    idempotency_key: str,
    operation_type: str,
    response: Dict[str, Any]
) -> None:
    """
    Store idempotency key and cache response for write operation.
    
    Args:
        db: Database session
        tenant_id: Tenant ID
        idempotency_key: Idempotency key from header
        operation_type: Operation type
        response: Response to cache
    """
    if not idempotency_key:
        return
    
    try:
        import json
        
        # Insert or update idempotency key (mark as processed)
        insert_query = text("""
            INSERT INTO idempotency_keys (
                tenant_id, provider, external_id, 
                first_processed_at, last_seen_at, attempts
            )
            VALUES (
                :tenant_id, :operation_type, :idempotency_key,
                NOW(), NOW(), 1
            )
            ON CONFLICT (tenant_id, provider, external_id)
            DO UPDATE SET
                last_seen_at = NOW(),
                attempts = idempotency_keys.attempts + 1,
                first_processed_at = COALESCE(idempotency_keys.first_processed_at, NOW())
            WHERE idempotency_keys.first_processed_at IS NULL
        """)
        
        db.execute(insert_query, {
            'tenant_id': tenant_id,
            'operation_type': operation_type,
            'idempotency_key': idempotency_key
        })
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Error storing idempotency: {str(e)}")
        db.rollback()
        # Non-blocking: log error but don't fail the operation


def with_write_idempotency(
    operation_type: str,
    get_resource_id: Optional[Callable] = None
):
    """
    Decorator for write endpoints to add idempotency protection.
    
    Usage:
        @router.post("/sessions/start")
        @with_write_idempotency("recording_session_start")
        async def start_session(request: Request, ...):
            # Operation code
            return response
    
    Args:
        operation_type: Operation type identifier
        get_resource_id: Optional function to extract resource ID from response
    """
    def decorator(func):
        from functools import wraps
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and db from args/kwargs
            request = None
            db = None
            
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                elif hasattr(arg, 'query'):  # SQLAlchemy Session
                    db = arg
            
            if not request:
                request = kwargs.get('request')
            if not db:
                db = kwargs.get('db')
            
            if not request or not db:
                # If we can't find request/db, proceed without idempotency
                return await func(*args, **kwargs)
            
            # Get tenant_id and idempotency key
            tenant_id = getattr(request.state, 'tenant_id', None)
            idempotency_key = get_idempotency_key(request)
            
            if not tenant_id:
                # No tenant context, proceed without idempotency
                return await func(*args, **kwargs)
            
            if idempotency_key:
                # Check if already processed
                is_duplicate, cached_response = check_write_idempotency(
                    db=db,
                    tenant_id=tenant_id,
                    idempotency_key=idempotency_key,
                    operation_type=operation_type
                )
                
                if is_duplicate and cached_response:
                    logger.info(
                        f"Returning cached response for idempotency key {idempotency_key}",
                        extra={
                            'tenant_id': tenant_id,
                            'operation_type': operation_type,
                            'idempotency_key': idempotency_key
                        }
                    )
                    # Return cached response (same status code as original)
                    from app.schemas.responses import APIResponse
                    return APIResponse(success=True, data=cached_response)
            
            # Execute operation
            response = await func(*args, **kwargs)
            
            # Store idempotency key and cache response
            if idempotency_key and tenant_id:
                # Extract data from response if it's an APIResponse
                response_data = None
                if hasattr(response, 'data'):
                    response_data = response.data
                elif isinstance(response, dict):
                    response_data = response.get('data') or response
                
                if response_data:
                    store_write_idempotency(
                        db=db,
                        tenant_id=tenant_id,
                        idempotency_key=idempotency_key,
                        operation_type=operation_type,
                        response=response_data if isinstance(response_data, dict) else {"result": response_data}
                    )
            
            return response
        
        return wrapper
    return decorator

