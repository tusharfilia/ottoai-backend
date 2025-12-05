"""
Authentication dependency for internal AI endpoints.

These endpoints are used by Ask Otto backend and require a special internal API token.
"""
from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from pydantic import BaseModel

from app.config import settings


class AIInternalContext(BaseModel):
    """Context for internal AI API requests."""
    company_id: str
    token: str


async def get_ai_internal_context(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
) -> AIInternalContext:
    """
    Validate internal AI API token and extract company context.
    
    Expected header format:
        Authorization: Bearer <AI_INTERNAL_TOKEN>
        X-Company-Id: <company_id>
    
    The AI_INTERNAL_TOKEN should be configured in environment variables.
    """
    # Extract token from Authorization header
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header"
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected: Bearer <token>"
        )
    
    token = authorization.replace("Bearer ", "").strip()
    
    # Validate token against configured internal token
    expected_token = getattr(settings, "AI_INTERNAL_TOKEN", None)
    if not expected_token:
        # If no token is configured, allow any token (for development)
        # In production, this should be set
        pass
    elif token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API token"
        )
    
    # Extract company_id from header
    if not x_company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Company-Id header"
        )
    
    return AIInternalContext(
        company_id=x_company_id,
        token=token
    )
