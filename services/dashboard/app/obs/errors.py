"""
RFC-7807 compliant error handling for OttoAI backend.
Provides structured error responses with trace correlation.
"""
import traceback
from typing import Any, Dict, Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.obs.logging import get_logger, log_error
from app.obs.tracing import get_current_trace_id

logger = get_logger(__name__)


class ProblemDetail:
    """RFC-7807 Problem Details for HTTP APIs."""
    
    def __init__(
        self,
        type: str,
        title: str,
        detail: str,
        status: int,
        instance: Optional[str] = None,
        trace_id: Optional[str] = None,
        **kwargs
    ):
        self.type = type
        self.title = title
        self.detail = detail
        self.status = status
        self.instance = instance
        self.trace_id = trace_id
        self.extensions = kwargs
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        result = {
            "type": self.type,
            "title": self.title,
            "detail": self.detail,
            "status": self.status,
        }
        
        if self.instance:
            result["instance"] = self.instance
        
        if self.trace_id:
            result["trace_id"] = self.trace_id
        
        # Add any additional extensions
        result.update(self.extensions)
        
        return result


def create_problem_detail(
    error: Exception,
    request: Request,
    status_code: int = 500,
    error_type: str = "about:blank",
    title: str = "Internal Server Error",
    detail: Optional[str] = None
) -> ProblemDetail:
    """Create a ProblemDetail from an exception."""
    
    # Get trace ID from request state or current trace
    trace_id = getattr(request.state, 'trace_id', None) or get_current_trace_id()
    
    # Use exception message as detail if not provided
    if detail is None:
        detail = str(error)
    
    return ProblemDetail(
        type=error_type,
        title=title,
        detail=detail,
        status=status_code,
        instance=request.url.path,
        trace_id=trace_id,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with RFC-7807 format."""
    
    problem = create_problem_detail(
        error=exc,
        request=request,
        status_code=exc.status_code,
        error_type="https://tools.ietf.org/html/rfc7231#section-6.5",
        title="HTTP Error",
        detail=exc.detail
    )
    
    # Log the error
    log_error(
        logger=logger,
        error=exc,
        trace_id=problem.trace_id,
        tenant_id=getattr(request.state, 'tenant_id', None),
        user_id=getattr(request.state, 'user_id', None),
        route=request.url.path,
        method=request.method,
        status_code=exc.status_code,
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(problem.to_dict())
    )


async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle Starlette HTTP exceptions with RFC-7807 format."""
    
    problem = create_problem_detail(
        error=exc,
        request=request,
        status_code=exc.status_code,
        error_type="https://tools.ietf.org/html/rfc7231#section-6.5",
        title="HTTP Error",
        detail=exc.detail
    )
    
    # Log the error
    log_error(
        logger=logger,
        error=exc,
        trace_id=problem.trace_id,
        tenant_id=getattr(request.state, 'tenant_id', None),
        user_id=getattr(request.state, 'user_id', None),
        route=request.url.path,
        method=request.method,
        status_code=exc.status_code,
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(problem.to_dict())
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors with RFC-7807 format."""
    
    problem = create_problem_detail(
        error=exc,
        request=request,
        status_code=422,
        error_type="https://tools.ietf.org/html/rfc4918#section-11.2",
        title="Validation Error",
        detail="Request validation failed"
    )
    
    # Add validation details to extensions
    problem.extensions["validation_errors"] = exc.errors()
    
    # Log the error
    log_error(
        logger=logger,
        error=exc,
        trace_id=problem.trace_id,
        tenant_id=getattr(request.state, 'tenant_id', None),
        user_id=getattr(request.state, 'user_id', None),
        route=request.url.path,
        method=request.method,
        status_code=422,
        validation_errors=exc.errors(),
    )
    
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(problem.to_dict())
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle general exceptions with RFC-7807 format."""
    
    problem = create_problem_detail(
        error=exc,
        request=request,
        status_code=500,
        error_type="https://tools.ietf.org/html/rfc7231#section-6.6.1",
        title="Internal Server Error",
        detail="An unexpected error occurred"
    )
    
    # Log the error with full stack trace
    log_error(
        logger=logger,
        error=exc,
        trace_id=problem.trace_id,
        tenant_id=getattr(request.state, 'tenant_id', None),
        user_id=getattr(request.state, 'user_id', None),
        route=request.url.path,
        method=request.method,
        status_code=500,
        stack_trace=traceback.format_exc(),
    )
    
    return JSONResponse(
        status_code=500,
        content=jsonable_encoder(problem.to_dict())
    )


def register_error_handlers(app):
    """Register all error handlers with the FastAPI app."""
    
    # HTTP exceptions
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    
    # Validation errors
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    
    # General exceptions (catch-all)
    app.add_exception_handler(Exception, general_exception_handler)
    
    return app


# Custom exception classes for specific error types
class BusinessLogicError(Exception):
    """Raised when business logic validation fails."""
    pass


class ExternalServiceError(Exception):
    """Raised when external service calls fail."""
    pass


class DatabaseError(Exception):
    """Raised when database operations fail."""
    pass


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthorizationError(Exception):
    """Raised when authorization fails."""
    pass


# Error type mappings for consistent error responses
ERROR_TYPE_MAPPINGS = {
    BusinessLogicError: {
        "type": "https://tools.ietf.org/html/rfc4918#section-11.2",
        "title": "Business Logic Error",
        "status": 422,
    },
    ExternalServiceError: {
        "type": "https://tools.ietf.org/html/rfc7231#section-6.5.4",
        "title": "External Service Error",
        "status": 502,
    },
    DatabaseError: {
        "type": "https://tools.ietf.org/html/rfc7231#section-6.6.1",
        "title": "Database Error",
        "status": 500,
    },
    AuthenticationError: {
        "type": "https://tools.ietf.org/html/rfc7235#section-3.1",
        "title": "Authentication Error",
        "status": 401,
    },
    AuthorizationError: {
        "type": "https://tools.ietf.org/html/rfc7235#section-3.1",
        "title": "Authorization Error",
        "status": 403,
    },
}