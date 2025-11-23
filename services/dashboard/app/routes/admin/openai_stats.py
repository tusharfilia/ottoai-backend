"""
Admin endpoint to view OpenAI API key usage statistics.
"""
from fastapi import APIRouter, Depends, Request
from typing import Dict, Any

from app.middleware.rbac import require_role
from app.schemas.responses import APIResponse
from app.services.openai_client_manager import get_openai_client_manager

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/openai/stats", response_model=APIResponse[Dict[str, Any]])
@require_role("exec", "manager")
async def get_openai_stats(request: Request) -> APIResponse[Dict[str, Any]]:
    """
    Get OpenAI API key usage statistics and health status.
    
    Shows:
    - Total keys and healthy keys
    - Request counts per key
    - Circuit breaker status
    - Rate limit status
    """
    manager = get_openai_client_manager()
    stats = manager.get_stats()
    
    return APIResponse(data=stats)


