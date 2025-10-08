"""
Role-Based Access Control (RBAC) decorators for OttoAI backend.
Enforces role-based permissions on protected endpoints.
"""
import logging
from functools import wraps
from typing import List, Union
from fastapi import Request, HTTPException
from app.obs.logging import get_logger

logger = get_logger(__name__)


class RBACError(HTTPException):
    """Custom exception for RBAC violations."""
    
    def __init__(self, required_roles: List[str], user_role: str):
        detail = f"Access denied. Required roles: {', '.join(required_roles)}. User role: {user_role}"
        super().__init__(status_code=403, detail=detail)
        logger.warning(f"RBAC violation: {detail}")


def require_role(*allowed_roles: str):
    """
    Decorator to enforce role-based access control on endpoints.
    
    Usage:
        @router.get("/admin/dashboard")
        @require_role("exec", "manager")
        async def admin_dashboard(request: Request):
            ...
    
    Args:
        *allowed_roles: Variable number of role strings ("exec", "manager", "csr", "rep")
    
    Raises:
        HTTPException: 403 if user's role is not in allowed_roles
        HTTPException: 401 if user_role is not found in request state
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args or kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                request = kwargs.get('request')
            
            if not request:
                logger.error("RBAC decorator: Request object not found in function arguments")
                raise HTTPException(
                    status_code=500,
                    detail="Internal error: Request object not available for RBAC check"
                )
            
            # Get user_role from request state (set by TenantContextMiddleware)
            user_role = getattr(request.state, 'user_role', None)
            user_id = getattr(request.state, 'user_id', None)
            tenant_id = getattr(request.state, 'tenant_id', None)
            
            if not user_role:
                logger.warning(f"RBAC check failed: user_role not found in request state for user {user_id}")
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required: user role not found"
                )
            
            # Check if user's role is in allowed roles
            if user_role not in allowed_roles:
                logger.warning(
                    f"RBAC violation: user {user_id} (role: {user_role}) "
                    f"attempted to access endpoint requiring roles: {allowed_roles}. "
                    f"Tenant: {tenant_id}"
                )
                raise RBACError(list(allowed_roles), user_role)
            
            # Log successful authorization
            logger.debug(
                f"RBAC check passed: user {user_id} (role: {user_role}) "
                f"accessing endpoint. Tenant: {tenant_id}"
            )
            
            # Call the original function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_tenant_ownership(resource_tenant_id_param: str = "company_id"):
    """
    Decorator to ensure the user can only access resources from their own tenant.
    
    Usage:
        @router.get("/companies/{company_id}")
        @require_tenant_ownership("company_id")
        async def get_company(request: Request, company_id: str):
            ...
    
    Args:
        resource_tenant_id_param: Name of the parameter containing the resource's tenant_id
    
    Raises:
        HTTPException: 403 if resource tenant_id doesn't match user's tenant_id
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args or kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                request = kwargs.get('request')
            
            if not request:
                logger.error("Tenant ownership decorator: Request object not found")
                raise HTTPException(
                    status_code=500,
                    detail="Internal error: Request object not available for tenant check"
                )
            
            # Get user's tenant_id from request state
            user_tenant_id = getattr(request.state, 'tenant_id', None)
            user_id = getattr(request.state, 'user_id', None)
            
            if not user_tenant_id:
                logger.warning(f"Tenant ownership check failed: tenant_id not found for user {user_id}")
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required: tenant context not found"
                )
            
            # Get resource tenant_id from path parameters or kwargs
            resource_tenant_id = kwargs.get(resource_tenant_id_param)
            
            if not resource_tenant_id:
                logger.error(
                    f"Tenant ownership check failed: {resource_tenant_id_param} "
                    f"not found in function parameters"
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Internal error: {resource_tenant_id_param} parameter not found"
                )
            
            # Check if user's tenant matches resource tenant
            if user_tenant_id != resource_tenant_id:
                logger.warning(
                    f"Cross-tenant access attempt: user {user_id} (tenant: {user_tenant_id}) "
                    f"attempted to access resource from tenant: {resource_tenant_id}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: resource belongs to a different organization"
                )
            
            # Log successful check
            logger.debug(
                f"Tenant ownership check passed: user {user_id} accessing resource "
                f"from tenant {user_tenant_id}"
            )
            
            # Call the original function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def get_user_context(request: Request) -> dict:
    """
    Helper function to extract user context from request state.
    
    Returns:
        dict: {
            "user_id": str,
            "tenant_id": str,
            "user_role": str,
            "rep_id": Optional[str],
            "meeting_id": Optional[str]
        }
    """
    return {
        "user_id": getattr(request.state, 'user_id', None),
        "tenant_id": getattr(request.state, 'tenant_id', None),
        "user_role": getattr(request.state, 'user_role', None),
        "rep_id": getattr(request.state, 'rep_id', None),
        "meeting_id": getattr(request.state, 'meeting_id', None),
    }
