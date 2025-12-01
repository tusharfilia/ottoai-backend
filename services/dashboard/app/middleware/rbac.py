"""
Role-Based Access Control (RBAC) decorators for OttoAI backend.
Enforces role-based permissions on protected endpoints.

Otto uses 3 roles:
- manager: Business owners, executives, and sales managers (full management access)
- csr: Customer service representatives (call handling, booking)
- sales_rep: Sales representatives (appointments, follow-ups)
"""
import logging
from functools import wraps
from typing import List, Union
from fastapi import Request, HTTPException
from app.obs.logging import get_logger

logger = get_logger(__name__)

# Role definitions (standardized 3-role model)
ROLE_MANAGER = "manager"    # Business owners, executives, sales managers
ROLE_CSR = "csr"            # Customer service representatives
ROLE_SALES_REP = "sales_rep"  # Sales representatives

# Valid roles
VALID_ROLES = {ROLE_MANAGER, ROLE_CSR, ROLE_SALES_REP}

# Role hierarchy for permission inheritance
ROLE_HIERARCHY = {
    ROLE_MANAGER: [ROLE_MANAGER, ROLE_CSR, ROLE_SALES_REP],  # Manager can access all
    ROLE_CSR: [ROLE_CSR],                                    # CSR can access CSR endpoints
    ROLE_SALES_REP: [ROLE_SALES_REP]                         # Sales rep can access rep endpoints
}


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
        @require_role("admin")
        async def admin_dashboard(request: Request):
            ...
        
        @router.get("/calls")
        @require_role("admin", "csr")
        async def get_calls(request: Request):
            ...
    
    Args:
        *allowed_roles: Variable number of role strings ("admin", "csr", "rep")
    
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
            
            # Check if user's role is in allowed roles (with hierarchy support)
            user_allowed_roles = ROLE_HIERARCHY.get(user_role, [user_role])
            # Normalize role names for backwards compatibility
            # Map old role names to new standardized names
            role_aliases = {
                "admin": "manager",
                "leadership": "manager",
                "exec": "manager",
                "rep": "sales_rep"
            }
            normalized_allowed_roles = set()
            for role in allowed_roles:
                normalized_role = role_aliases.get(role, role)
                normalized_allowed_roles.add(normalized_role)
            # Also normalize user_role
            normalized_user_role = role_aliases.get(user_role, user_role)
            normalized_user_allowed_roles = [role_aliases.get(r, r) for r in user_allowed_roles]
            has_permission = any(role in normalized_allowed_roles for role in normalized_user_allowed_roles)
            
            if not has_permission:
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

