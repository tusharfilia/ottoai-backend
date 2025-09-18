"""
Tenant context middleware for OttoAI backend.
Extracts and validates tenant_id from Clerk JWT claims.
"""
import logging
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import jwt
import requests
from app.config import settings

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
            tenant_id = await self._extract_tenant_id(request)
            if not tenant_id:
                response = JSONResponse(
                    status_code=403,
                    content={"detail": "Missing or invalid tenant_id in JWT claims"}
                )
                await response(scope, receive, send)
                return
            
            # Extract user_id from JWT claims
            user_id = decoded_token.get("sub") or decoded_token.get("user_id")
            
            # Attach tenant_id and user_id to request state
            request.state.tenant_id = tenant_id
            request.state.user_id = user_id
            logger.debug(f"Tenant context set: {tenant_id}, User: {user_id}")
            
        except Exception as e:
            logger.error(f"Error extracting tenant_id: {str(e)}")
            response = JSONResponse(
                status_code=403,
                content={"detail": "Invalid authentication token"}
            )
            await response(scope, receive, send)
            return
        
        await self.app(scope, receive, send)
    
    def _should_skip_tenant_validation(self, request: Request) -> bool:
        """Check if tenant validation should be skipped for this request."""
        skip_paths = [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico"
        ]
        
        return any(request.url.path.startswith(path) for path in skip_paths)
    
    async def _extract_tenant_id(self, request: Request) -> Optional[str]:
        """Extract tenant_id from Clerk JWT claims."""
        # Get Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("No Authorization header found")
            return None
        
        token = auth_header.split(" ")[1]
        
        try:
            # Get JWKS for token verification
            jwks = await self._get_jwks()
            if not jwks:
                logger.error("Failed to get JWKS")
                return None
            
            # Decode and verify the JWT
            decoded_token = jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                options={"verify_exp": True, "verify_aud": False}
            )
            
            # Extract tenant_id from claims
            # Clerk stores organization info in different places depending on the token type
            tenant_id = None
            
            # Check for organization_id in the token
            if "org_id" in decoded_token:
                tenant_id = decoded_token["org_id"]
            elif "organization_id" in decoded_token:
                tenant_id = decoded_token["organization_id"]
            elif "org" in decoded_token and isinstance(decoded_token["org"], dict):
                tenant_id = decoded_token["org"].get("id")
            
            # If no organization found, check if user has a default organization
            if not tenant_id and "user_id" in decoded_token:
                tenant_id = await self._get_user_default_organization(decoded_token["user_id"])
            
            return tenant_id
            
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error decoding JWT: {str(e)}")
            return None
    
    async def _get_jwks(self) -> Optional[dict]:
        """Get JWKS from Clerk for JWT verification."""
        import time
        
        # Check cache first
        current_time = time.time()
        if (self.jwks_cache and 
            current_time - self.jwks_cache_time < self.cache_duration):
            return self.jwks_cache
        
        try:
            response = requests.get(settings.clerk_jwks_url, timeout=10)
            response.raise_for_status()
            
            jwks_data = response.json()
            self.jwks_cache = jwks_data
            self.jwks_cache_time = current_time
            
            return jwks_data
            
        except Exception as e:
            logger.error(f"Failed to fetch JWKS: {str(e)}")
            return None
    
    async def _get_user_default_organization(self, user_id: str) -> Optional[str]:
        """Get the default organization for a user from Clerk API."""
        try:
            headers = {
                "Authorization": f"Bearer {settings.CLERK_SECRET_KEY}",
                "Content-Type": "application/json"
            }
            
            # Get user's organization memberships
            response = requests.get(
                f"{settings.CLERK_API_URL}/users/{user_id}/organization_memberships",
                headers=headers,
                timeout=10
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
