"""
Internal AI authentication dependency for Shunya/UWC integration.

Validates Bearer token and X-Company-Id header for internal API access.
"""
from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from app.config import settings
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)


class AIInternalContext(BaseModel):
    """Internal AI API context with validated company ID and caller info."""
    company_id: str
    caller: str = "ask_otto"


def get_ai_internal_context(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
) -> AIInternalContext:
    """
    Validate internal AI API authentication.
    
    Requirements:
    - Authorization: Bearer <AI_INTERNAL_TOKEN>
    - X-Company-Id: <company_id>
    
    Returns:
        AIInternalContext with validated company_id and caller info
        
    Raises:
        HTTPException 401: Missing or invalid token
        HTTPException 400: Missing X-Company-Id header
    """
    # Validate Authorization header
    if not authorization:
        logger.warning("Missing Authorization header for internal AI API")
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )
    
    if not authorization.startswith("Bearer "):
        logger.warning("Invalid Authorization format for internal AI API")
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format. Must be 'Bearer <token>'"
        )
    
    token = authorization.replace("Bearer ", "").strip()
    
    # Validate token matches AI_INTERNAL_TOKEN
    if not settings.AI_INTERNAL_TOKEN:
        logger.error("AI_INTERNAL_TOKEN not configured in settings")
        raise HTTPException(
            status_code=500,
            detail="Internal API authentication not configured"
        )
    
    if token != settings.AI_INTERNAL_TOKEN:
        logger.warning("Invalid AI internal token provided")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token"
        )
    
    # Validate X-Company-Id header
    if not x_company_id:
        logger.warning("Missing X-Company-Id header for internal AI API")
        raise HTTPException(
            status_code=400,
            detail="Missing X-Company-Id header"
        )
    
    company_id = x_company_id.strip()
    
    if not company_id:
        logger.warning("Empty X-Company-Id header for internal AI API")
        raise HTTPException(
            status_code=400,
            detail="X-Company-Id header cannot be empty"
        )
    
    logger.debug(
        f"Internal AI API access authenticated for company {company_id}",
        extra={"company_id": company_id}
    )
    
    return AIInternalContext(company_id=company_id, caller="ask_otto")



Internal AI authentication dependency for Shunya/UWC integration.

Validates Bearer token and X-Company-Id header for internal API access.
"""
from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from app.config import settings
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)


class AIInternalContext(BaseModel):
    """Internal AI API context with validated company ID and caller info."""
    company_id: str
    caller: str = "ask_otto"


def get_ai_internal_context(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
) -> AIInternalContext:
    """
    Validate internal AI API authentication.
    
    Requirements:
    - Authorization: Bearer <AI_INTERNAL_TOKEN>
    - X-Company-Id: <company_id>
    
    Returns:
        AIInternalContext with validated company_id and caller info
        
    Raises:
        HTTPException 401: Missing or invalid token
        HTTPException 400: Missing X-Company-Id header
    """
    # Validate Authorization header
    if not authorization:
        logger.warning("Missing Authorization header for internal AI API")
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )
    
    if not authorization.startswith("Bearer "):
        logger.warning("Invalid Authorization format for internal AI API")
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format. Must be 'Bearer <token>'"
        )
    
    token = authorization.replace("Bearer ", "").strip()
    
    # Validate token matches AI_INTERNAL_TOKEN
    if not settings.AI_INTERNAL_TOKEN:
        logger.error("AI_INTERNAL_TOKEN not configured in settings")
        raise HTTPException(
            status_code=500,
            detail="Internal API authentication not configured"
        )
    
    if token != settings.AI_INTERNAL_TOKEN:
        logger.warning("Invalid AI internal token provided")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token"
        )
    
    # Validate X-Company-Id header
    if not x_company_id:
        logger.warning("Missing X-Company-Id header for internal AI API")
        raise HTTPException(
            status_code=400,
            detail="Missing X-Company-Id header"
        )
    
    company_id = x_company_id.strip()
    
    if not company_id:
        logger.warning("Empty X-Company-Id header for internal AI API")
        raise HTTPException(
            status_code=400,
            detail="X-Company-Id header cannot be empty"
        )
    
    logger.debug(
        f"Internal AI API access authenticated for company {company_id}",
        extra={"company_id": company_id}
    )
    
    return AIInternalContext(company_id=company_id, caller="ask_otto")



Internal AI authentication dependency for Shunya/UWC integration.

Validates Bearer token and X-Company-Id header for internal API access.
"""
from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from app.config import settings
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)


class AIInternalContext(BaseModel):
    """Internal AI API context with validated company ID and caller info."""
    company_id: str
    caller: str = "ask_otto"


def get_ai_internal_context(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
) -> AIInternalContext:
    """
    Validate internal AI API authentication.
    
    Requirements:
    - Authorization: Bearer <AI_INTERNAL_TOKEN>
    - X-Company-Id: <company_id>
    
    Returns:
        AIInternalContext with validated company_id and caller info
        
    Raises:
        HTTPException 401: Missing or invalid token
        HTTPException 400: Missing X-Company-Id header
    """
    # Validate Authorization header
    if not authorization:
        logger.warning("Missing Authorization header for internal AI API")
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )
    
    if not authorization.startswith("Bearer "):
        logger.warning("Invalid Authorization format for internal AI API")
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format. Must be 'Bearer <token>'"
        )
    
    token = authorization.replace("Bearer ", "").strip()
    
    # Validate token matches AI_INTERNAL_TOKEN
    if not settings.AI_INTERNAL_TOKEN:
        logger.error("AI_INTERNAL_TOKEN not configured in settings")
        raise HTTPException(
            status_code=500,
            detail="Internal API authentication not configured"
        )
    
    if token != settings.AI_INTERNAL_TOKEN:
        logger.warning("Invalid AI internal token provided")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token"
        )
    
    # Validate X-Company-Id header
    if not x_company_id:
        logger.warning("Missing X-Company-Id header for internal AI API")
        raise HTTPException(
            status_code=400,
            detail="Missing X-Company-Id header"
        )
    
    company_id = x_company_id.strip()
    
    if not company_id:
        logger.warning("Empty X-Company-Id header for internal AI API")
        raise HTTPException(
            status_code=400,
            detail="X-Company-Id header cannot be empty"
        )
    
    logger.debug(
        f"Internal AI API access authenticated for company {company_id}",
        extra={"company_id": company_id}
    )
    
    return AIInternalContext(company_id=company_id, caller="ask_otto")



