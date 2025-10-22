"""
Standard API response schemas for consistent client experience.
All API endpoints should use these standardized response formats.
"""
from pydantic import BaseModel, Field
from typing import Optional, Any, List, Generic, TypeVar, Dict
from datetime import datetime

T = TypeVar('T')


class APIMetadata(BaseModel):
    """
    Metadata included in API responses.
    Useful for pagination, performance tracking, and debugging.
    """
    request_id: Optional[str] = Field(None, description="Request trace ID for debugging")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    version: str = Field(default="v1", description="API version")
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "req_abc123xyz",
                "timestamp": "2025-10-09T12:00:00Z",
                "version": "v1"
            }
        }


class APIResponse(BaseModel, Generic[T]):
    """
    Standard success response wrapper.
    
    Usage:
        @router.get("/calls")
        async def get_calls() -> APIResponse[List[CallSchema]]:
            calls = db.query(Call).all()
            return APIResponse(
                success=True,
                data=calls,
                meta=APIMetadata(request_id=request.state.trace_id)
            )
    """
    success: bool = Field(True, description="Indicates successful operation")
    data: T = Field(..., description="Response payload")
    meta: Optional[APIMetadata] = Field(None, description="Response metadata")
    message: Optional[str] = Field(None, description="Optional human-readable message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"id": "123", "name": "Example"},
                "meta": {
                    "request_id": "req_abc123",
                    "timestamp": "2025-10-09T12:00:00Z",
                    "version": "v1"
                }
            }
        }


class ErrorResponse(BaseModel):
    """
    Standard error response.
    
    Usage:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="not_found",
                error_code="CALL_NOT_FOUND",
                message="Call with ID 123 not found",
                request_id=request.state.trace_id
            ).dict()
        )
    """
    success: bool = Field(False, description="Always false for errors")
    error: str = Field(..., description="Error type (snake_case)")
    error_code: str = Field(..., description="Machine-readable error code (UPPER_SNAKE_CASE)")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    request_id: Optional[str] = Field(None, description="Request ID for debugging")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "not_found",
                "error_code": "CALL_NOT_FOUND",
                "message": "Call with ID 123 not found in your company",
                "details": {"call_id": 123, "tenant_id": "company_456"},
                "request_id": "req_abc123",
                "timestamp": "2025-10-09T12:00:00Z"
            }
        }


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standard paginated list response.
    
    Usage:
        @router.get("/calls")
        async def get_calls(page: int = 1, page_size: int = 50):
            total = db.query(func.count(Call.call_id)).scalar()
            calls = db.query(Call)\
                .offset((page - 1) * page_size)\
                .limit(page_size)\
                .all()
            
            return PaginatedResponse(
                items=calls,
                meta=PaginationMeta(
                    total=total,
                    page=page,
                    page_size=page_size,
                    total_pages=(total + page_size - 1) // page_size,
                    has_next=page * page_size < total,
                    has_prev=page > 1
                )
            )
    """
    success: bool = Field(True, description="Always true for successful pagination")
    items: List[T] = Field(..., description="List of items for current page")
    meta: PaginationMeta = Field(..., description="Pagination metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "items": [
                    {"id": "1", "name": "Item 1"},
                    {"id": "2", "name": "Item 2"}
                ],
                "meta": {
                    "total": 100,
                    "page": 1,
                    "page_size": 50,
                    "total_pages": 2,
                    "has_next": True,
                    "has_prev": False
                }
            }
        }


class JobStatusResponse(BaseModel):
    """
    Standard response for async job status.
    Used for long-running operations like ASR, training, indexing.
    """
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status: queued, processing, completed, failed")
    progress: Optional[int] = Field(None, description="Progress percentage (0-100)")
    message: Optional[str] = Field(None, description="Status message")
    created_at: datetime = Field(..., description="Job creation time")
    started_at: Optional[datetime] = Field(None, description="Job start time")
    completed_at: Optional[datetime] = Field(None, description="Job completion time")
    error: Optional[str] = Field(None, description="Error message if failed")
    result: Optional[Dict[str, Any]] = Field(None, description="Job result if completed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "job_abc123",
                "status": "processing",
                "progress": 45,
                "message": "Analyzing call transcript",
                "created_at": "2025-10-09T12:00:00Z",
                "started_at": "2025-10-09T12:00:05Z"
            }
        }


class HealthCheckResponse(BaseModel):
    """Standard health check response."""
    status: str = Field(..., description="Service status: healthy, degraded, unhealthy")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(default="v1")
    checks: Dict[str, bool] = Field(..., description="Individual component health checks")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-10-09T12:00:00Z",
                "version": "v1",
                "checks": {
                    "database": True,
                    "redis": True,
                    "uwc": True
                }
            }
        }


# Standard error codes (use these consistently)
class ErrorCodes:
    """Centralized error code definitions."""
    
    # Authentication & Authorization (400s)
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    
    # Resource Not Found (404s)
    NOT_FOUND = "NOT_FOUND"
    CALL_NOT_FOUND = "CALL_NOT_FOUND"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    COMPANY_NOT_FOUND = "COMPANY_NOT_FOUND"
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    
    # Validation Errors (400s)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    
    # Business Logic Errors (400s)
    DUPLICATE_RESOURCE = "DUPLICATE_RESOURCE"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    OPERATION_NOT_ALLOWED = "OPERATION_NOT_ALLOWED"
    
    # Rate Limiting (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    TENANT_RATE_LIMIT_EXCEEDED = "TENANT_RATE_LIMIT_EXCEEDED"
    
    # External Service Errors (503)
    UWC_UNAVAILABLE = "UWC_UNAVAILABLE"
    UWC_TIMEOUT = "UWC_TIMEOUT"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    
    # Internal Errors (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    STORAGE_ERROR = "STORAGE_ERROR"


def create_error_response(
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> ErrorResponse:
    """
    Helper function to create standardized error responses.
    
    Args:
        error_code: Error code from ErrorCodes class
        message: Human-readable error message
        details: Additional error details
        request_id: Request trace ID
    
    Returns:
        ErrorResponse object
    """
    # Convert error code to snake_case for error field
    error_type = error_code.lower()
    
    return ErrorResponse(
        error=error_type,
        error_code=error_code,
        message=message,
        details=details,
        request_id=request_id
    )




