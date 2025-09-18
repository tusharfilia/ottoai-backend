"""
Observability middleware for FastAPI.
Provides request tracing, logging, and metrics collection.
"""
import time
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.obs.logging import get_logger, log_request, extract_trace_id
from app.obs.tracing import get_tracer, add_span_attributes, add_span_error
from app.obs.metrics import record_http_request
from app.config import settings

logger = get_logger(__name__)
tracer = get_tracer(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware for request observability (logging, tracing, metrics)."""
    
    def __init__(self, app, exclude_paths: list = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or ['/health', '/metrics', '/docs', '/openapi.json']
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with observability."""
        start_time = time.time()
        
        # Skip observability for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Extract or generate trace ID
        trace_id = extract_trace_id(request)
        request.state.trace_id = trace_id
        
        # Create span for the request
        with tracer.start_as_current_span(
            f"{request.method} {request.url.path}",
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.route": request.url.path,
                "trace_id": trace_id,
            }
        ) as span:
            try:
                # Add request attributes to span
                add_span_attributes({
                    "http.user_agent": request.headers.get("user-agent", ""),
                    "http.host": request.headers.get("host", ""),
                })
                
                # Add client IP if available
                if request.client:
                    add_span_attributes({
                        "http.client_ip": request.client.host,
                    })
                
                # Process request
                response = await call_next(request)
                
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000
                
                # Add response attributes to span
                add_span_attributes({
                    "http.status_code": response.status_code,
                    "http.response_size": response.headers.get("content-length", 0),
                })
                
                # Add trace ID to response headers
                response.headers["X-Request-Id"] = trace_id
                
                # Record metrics
                record_http_request(
                    route=request.url.path,
                    method=request.method,
                    status_code=response.status_code,
                    duration_ms=duration_ms
                )
                
                # Log request
                log_request(
                    logger=logger,
                    request=request,
                    status_code=response.status_code,
                    latency_ms=duration_ms,
                    trace_id=trace_id,
                    tenant_id=getattr(request.state, 'tenant_id', None),
                    user_id=getattr(request.state, 'user_id', None),
                )
                
                return response
                
            except Exception as e:
                # Calculate duration for error case
                duration_ms = (time.time() - start_time) * 1000
                
                # Add error to span
                add_span_error(e, {
                    "error.route": request.url.path,
                    "error.method": request.method,
                })
                
                # Record metrics for error
                record_http_request(
                    route=request.url.path,
                    method=request.method,
                    status_code=500,
                    duration_ms=duration_ms
                )
                
                # Log error
                from app.obs.logging import log_error
                log_error(
                    logger=logger,
                    error=e,
                    trace_id=trace_id,
                    tenant_id=getattr(request.state, 'tenant_id', None),
                    user_id=getattr(request.state, 'user_id', None),
                    route=request.url.path,
                    method=request.method,
                )
                
                # Re-raise the exception
                raise


class TenantContextMiddleware:
    """Middleware to extract and set tenant context from JWT tokens."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope, receive)
        
        # Extract tenant and user context from JWT token
        # This is a simplified version - in production, you'd validate the JWT
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            # TODO: Validate JWT and extract tenant_id and user_id
            # For now, we'll set placeholder values
            request.state.tenant_id = "placeholder_tenant"
            request.state.user_id = "placeholder_user"
        
        await self.app(scope, receive, send)
