"""
Tenant context middleware for OttoAI backend.
Extracts and validates tenant_id from Clerk JWT claims.
"""
import logging
from typing import Optional

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

from app.config import settings
from app.routes.dependencies import verify_clerk_jwt

logger = logging.getLogger(__name__)


class TenantContextMiddleware:
    """Middleware to extract and validate tenant_id from Clerk JWT claims."""
    
    def __init__(self, app):
        self.app = app
        self.jwks_cache = {}
        self.jwks_cache_time = 0
        self.cache_duration = 3600  # 1 hour
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope, receive)
        
        # Skip tenant validation for health checks and public endpoints
        if self._should_skip_tenant_validation(request):
            await self.app(scope, receive, send)
            return
        
        try:
            # Extract tenant context (tenant_id, user_id, user_role)
            context = await self._extract_tenant_context(request)
            if not context or not context.get("tenant_id"):
                # In dev mode, use test company/user if no auth token provided
                if settings.DEV_MODE:
                    logger.info("DEV_MODE enabled: Using test company/user for unauthenticated request")
                    context = {
                        "tenant_id": settings.DEV_TEST_COMPANY_ID,
                        "user_id": settings.DEV_TEST_USER_ID,
                        "user_role": "manager"  # Default to manager in dev mode for full access
                    }
                else:
                    response = JSONResponse(
                        status_code=403,
                        content={"detail": "Missing or invalid tenant_id in JWT claims"}
                    )
                    await response(scope, receive, send)
                    return
            
            # Attach context to request state
            request.state.tenant_id = context["tenant_id"]
            request.state.user_id = context["user_id"]
            request.state.user_role = context["user_role"]
            logger.debug(
                f"Tenant context set: {context['tenant_id']}, "
                f"User: {context['user_id']}, Role: {context['user_role']}"
            )
            
        except Exception as e:
            logger.error(f"Error extracting tenant_id: {str(e)}")
            # In dev mode, fall back to test company/user on error
            if settings.DEV_MODE:
                logger.info("DEV_MODE enabled: Using test company/user after error")
                request.state.tenant_id = settings.DEV_TEST_COMPANY_ID
                request.state.user_id = settings.DEV_TEST_USER_ID
                request.state.user_role = "manager"  # Default to manager in dev mode for full access
            else:
                response = JSONResponse(
                    status_code=403,
                    content={"detail": "Invalid authentication token"}
                )
                await response(scope, receive, send)
                return
        
        await self.app(scope, receive, send)
    
    def _should_skip_tenant_validation(self, request: Request) -> bool:
        """Check if tenant validation should be skipped for this request."""
        # Skip OPTIONS requests (CORS preflight) - they don't include auth headers
        if request.method == "OPTIONS":
            return True
        
        skip_paths = [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
            "/call-complete",  # CallRail webhook
            "/callrail/",  # CallRail webhooks
            "/pre-call",  # CallRail pre-call webhook
            "/call-modified",  # CallRail call-modified webhook
            "/sms/callrail-webhook",  # CallRail SMS webhook
            "/sms/twilio-webhook",  # Twilio SMS webhook
            "/twilio-webhook",  # Twilio webhook
            "/mobile/twilio-",  # Twilio mobile webhooks
            "/clerk-webhook",  # Clerk webhook
        ]
        
        return any(request.url.path.startswith(path) for path in skip_paths)
    
    async def _extract_tenant_context(self, request: Request) -> Optional[dict]:
        """
        Extract tenant context from Clerk JWT claims.
        
        Returns:
            dict with tenant_id, user_id, user_role, or None if extraction fails
        """
        # In dev mode, if no auth header, return None to trigger dev mode fallback
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            if settings.DEV_MODE:
                logger.debug("DEV_MODE: No Authorization header, will use test company/user")
                return None
            logger.warning("No Authorization header found")
            return None
        
        token = auth_header.split(" ")[1]
        
        try:
            # Use shared Clerk JWT verification helper to decode the token
            decoded_token = await verify_clerk_jwt(token)
            
            # Extract tenant_id from claims
            # Clerk stores organization / tenant info in different places
            tenant_id = (
                decoded_token.get("org_id")
                or decoded_token.get("organization_id")
                or decoded_token.get("tenant_id")
                or decoded_token.get("company_id")
            )
            # Some tokens may nest org info under an "org" object
            if not tenant_id and "org" in decoded_token and isinstance(decoded_token["org"], dict):
                tenant_id = decoded_token["org"].get("id")
            
            # If no organization found, check if user has a default organization
            if not tenant_id and "user_id" in decoded_token:
                tenant_id = await self._get_user_default_organization(decoded_token["user_id"])
            
            # Extract user_id and role
            user_id = decoded_token.get("sub") or decoded_token.get("user_id")
            clerk_role = decoded_token.get("org_role") or decoded_token.get("role") or "sales_rep"
            
            # Map Clerk roles to Otto's standardized 3-role system
            # Clerk may use: admin, org:admin, exec, manager, csr, rep, sales_rep
            # Otto uses: manager, csr, sales_rep
            role_mapping = {
                "admin": "manager",
                "org:admin": "manager",
                "exec": "manager",
                "manager": "manager",
                "csr": "csr",
                "rep": "sales_rep",
                "sales_rep": "sales_rep"
            }
            user_role = role_mapping.get(clerk_role.lower(), "sales_rep")  # Default to sales_rep if unknown
            
            return {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "user_role": user_role,
            }
            
        except Exception as e:
            # verify_clerk_jwt already logs; here we just treat as auth failure
            logger.warning(f"Failed to verify Clerk JWT in tenant middleware: {e}")
            return None
    
    async def _get_user_default_organization(self, user_id: str) -> Optional[str]:
        """Get the default organization for a user from Clerk API."""
        try:
            headers = {
                "Authorization": f"Bearer {settings.CLERK_SECRET_KEY}",
                "Content-Type": "application/json"
            }
            
            # Get user's organization memberships - use async httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.CLERK_API_URL}/users/{user_id}/organization_memberships",
                    headers=headers
                )
                response.raise_for_status()
                
                memberships = response.json()
                if memberships and len(memberships) > 0:
                    # Return the first organization ID
                    return memberships[0].get("organization", {}).get("id")
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user organization: {str(e)}")
            return None


def get_tenant_id(request: Request) -> str:
    """Get tenant_id from request state. Raises HTTPException if not found."""
    if not hasattr(request.state, 'tenant_id') or not request.state.tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Tenant context not found. Ensure you're authenticated with a valid organization."
        )
    return request.state.tenant_id

    if not hasattr(request.state, 'tenant_id') or not request.state.tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Tenant context not found. Ensure you're authenticated with a valid organization."
        )
    return request.state.tenant_id

    if not hasattr(request.state, 'tenant_id') or not request.state.tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Tenant context not found. Ensure you're authenticated with a valid organization."
        )
    return request.state.tenant_id
