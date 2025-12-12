"""
Tenant isolation enforcement for Otto AI backend.
Provides strict tenant_id enforcement at the API boundary.
"""
import logging
from typing import Optional
from fastapi import Request, HTTPException, Depends
from app.obs.logging import get_logger

logger = get_logger(__name__)


def get_tenant_id(request: Request) -> str:
    """
    Extract and validate tenant_id from request state.
    
    This dependency must be used on all protected endpoints to ensure
    tenant isolation. It extracts the tenant_id that was set by the
    TenantContextMiddleware during request processing.
    
    Args:
        request: FastAPI Request object with tenant context
        
    Returns:
        str: Validated tenant_id
        
    Raises:
        HTTPException: 403 if tenant_id is missing or invalid
    """
    tenant_id = getattr(request.state, 'tenant_id', None)
    
    if not tenant_id:
        logger.warning("Missing tenant_id in request state")
        raise HTTPException(
            status_code=403,
            detail="Missing tenant context. Authentication required."
        )
    
    # Validate tenant_id format (basic UUID validation)
    if not isinstance(tenant_id, str) or len(tenant_id) < 10:
        logger.warning(f"Invalid tenant_id format: {tenant_id}")
        raise HTTPException(
            status_code=403,
            detail="Invalid tenant context."
        )
    
    logger.debug(f"Tenant isolation enforced for tenant_id: {tenant_id}")
    return tenant_id


def get_user_id(request: Request) -> str:
    """
    Extract and validate user_id from request state.
    
    Args:
        request: FastAPI Request object with user context
        
    Returns:
        str: Validated user_id
        
    Raises:
        HTTPException: 403 if user_id is missing or invalid
    """
    user_id = getattr(request.state, 'user_id', None)
    
    if not user_id:
        logger.warning("Missing user_id in request state")
        raise HTTPException(
            status_code=403,
            detail="Missing user context. Authentication required."
        )
    
    return user_id


def get_user_role(request: Request) -> str:
    """
    Extract and validate user_role from request state.
    
    Args:
        request: FastAPI Request object with role context
        
    Returns:
        str: Validated user_role
        
    Raises:
        HTTPException: 403 if user_role is missing or invalid
    """
    user_role = getattr(request.state, 'user_role', None)
    
    if not user_role:
        logger.warning("Missing user_role in request state")
        raise HTTPException(
            status_code=403,
            detail="Missing role context. Authentication required."
        )
    
    return user_role


def get_tenant_context(request: Request) -> dict:
    """
    Extract complete tenant context from request state.
    
    Args:
        request: FastAPI Request object with tenant context
        
    Returns:
        dict: Complete tenant context with tenant_id, user_id, user_role
        
    Raises:
        HTTPException: 403 if any context is missing
    """
    tenant_id = get_tenant_id(request)
    user_id = get_user_id(request)
    user_role = get_user_role(request)
    
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "user_role": user_role
    }


# Convenience dependency for endpoints that need full context
def require_tenant_context(request: Request) -> dict:
    """
    Dependency that requires complete tenant context.
    
    Use this for endpoints that need tenant_id, user_id, and user_role.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        dict: Complete tenant context
        
    Raises:
        HTTPException: 403 if any context is missing
    """
    return get_tenant_context(request)


# P0 FIX: Tenant ownership verification helper
def verify_tenant_ownership(db, model_class, resource_id: str, tenant_id: str) -> bool:
    """
    Verify that a resource belongs to the specified tenant.
    
    This helper prevents cross-tenant data access by ID enumeration.
    Returns False (not raises exception) to allow callers to return 404 instead of 403.
    
    Args:
        db: Database session
        model_class: SQLAlchemy model class (must have company_id or tenant_id column)
        resource_id: Resource ID to verify
        tenant_id: Expected tenant ID
        
    Returns:
        bool: True if resource belongs to tenant, False otherwise
    """
    try:
        # Determine tenant column name
        tenant_column = getattr(model_class, 'company_id', None) or getattr(model_class, 'tenant_id', None)
        if not tenant_column:
            logger.error(f"Model {model_class.__name__} has no company_id or tenant_id column")
            return False
        
        # Query resource with tenant filter
        query = db.query(model_class).filter(
            model_class.id == resource_id,
            tenant_column == tenant_id
        )
        
        resource = query.first()
        return resource is not None
        
    except Exception as e:
        logger.error(f"Error verifying tenant ownership: {str(e)}")
        return False

