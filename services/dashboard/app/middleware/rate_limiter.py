"""
Rate limiting middleware for OttoAI backend.
Implements per-user and per-tenant rate limiting using Redis.
"""
import time
import logging
import redis
import json
import uuid
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Response
from fastapi.responses import JSONResponse
from functools import wraps
from app.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter using Redis for distributed rate limiting."""
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis_client = None
        self._connect_redis()
    
    def _connect_redis(self):
        """Connect to Redis with error handling."""
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            logger.info("Connected to Redis for rate limiting")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            # Fallback to in-memory rate limiting for development
            self.redis_client = None
    
    def _parse_limit(self, limit_str: str) -> tuple:
        """Parse limit string like '60/minute' into (count, seconds)."""
        try:
            count, period = limit_str.split('/')
            count = int(count)
            
            period_map = {
                'second': 1,
                'minute': 60,
                'hour': 3600,
                'day': 86400
            }
            
            seconds = period_map.get(period, 60)
            return count, seconds
        except (ValueError, KeyError):
            logger.warning(f"Invalid limit format: {limit_str}, using default 60/minute")
            return 60, 60
    
    def _get_redis_key(self, key_type: str, identifier: str) -> str:
        """Generate Redis key for rate limiting."""
        return f"rate_limit:{key_type}:{identifier}"
    
    def _check_rate_limit(self, key: str, limit: str) -> tuple:
        """Check if request is within rate limit. Returns (allowed, retry_after)."""
        if not self.redis_client:
            # Fallback: always allow if Redis is not available
            return True, 0
        
        count, window_seconds = self._parse_limit(limit)
        current_time = int(time.time())
        window_start = current_time - window_seconds
        
        try:
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            
            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiration
            pipe.expire(key, window_seconds)
            
            results = pipe.execute()
            current_count = results[1]
            
            if current_count >= count:
                # Rate limit exceeded
                # Get the oldest request to calculate retry_after
                oldest_requests = self.redis_client.zrange(key, 0, 0, withscores=True)
                if oldest_requests:
                    oldest_time = int(oldest_requests[0][1])
                    retry_after = window_seconds - (current_time - oldest_time)
                    return False, max(1, retry_after)
                return False, window_seconds
            
            return True, 0
            
        except Exception as e:
            logger.error(f"Redis error in rate limiting: {e}")
            # Fallback: allow request if Redis fails
            return True, 0
    
    def check_user_limit(self, tenant_id: str, user_id: str, limit: str = None) -> tuple:
        """Check per-user rate limit."""
        limit = limit or settings.RATE_LIMIT_USER
        key = self._get_redis_key("user", f"tenant:{tenant_id}:user:{user_id}")
        return self._check_rate_limit(key, limit)
    
    def check_tenant_limit(self, tenant_id: str, limit: str = None) -> tuple:
        """Check per-tenant rate limit."""
        limit = limit or settings.RATE_LIMIT_TENANT
        key = self._get_redis_key("tenant", f"tenant:{tenant_id}")
        return self._check_rate_limit(key, limit)


# Global rate limiter instance
rate_limiter = RateLimiter()


def create_rate_limit_response(retry_after: int, trace_id: str = None) -> JSONResponse:
    """Create standardized 429 rate limit response."""
    if not trace_id:
        trace_id = str(uuid.uuid4())
    
    response_data = {
        "type": "https://tools.ietf.org/html/rfc6585#section-4",
        "title": "Too Many Requests",
        "detail": "Rate limit exceeded. Please try again later.",
        "retry_after": retry_after,
        "trace_id": trace_id
    }
    
    response = JSONResponse(
        status_code=429,
        content=response_data
    )
    response.headers["Retry-After"] = str(retry_after)
    response.headers["X-Trace-Id"] = trace_id
    
    return response


def limits(user: str = None, tenant: str = None):
    """
    Decorator for applying rate limits to routes.
    
    Args:
        user: Per-user rate limit (e.g., "60/minute")
        tenant: Per-tenant rate limit (e.g., "600/minute")
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args (FastAPI dependency injection)
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                # If no request found, call function normally
                return await func(*args, **kwargs)
            
            # Skip rate limiting for exempt routes
            if _is_exempt_route(request):
                return await func(*args, **kwargs)
            
            # Get tenant_id and user_id from request state
            tenant_id = getattr(request.state, 'tenant_id', None)
            user_id = getattr(request.state, 'user_id', None)
            
            if not tenant_id:
                # If no tenant context, skip rate limiting
                return await func(*args, **kwargs)
            
            trace_id = str(uuid.uuid4())
            
            # Check per-user limit
            if user and user_id:
                allowed, retry_after = rate_limiter.check_user_limit(tenant_id, user_id, user)
                if not allowed:
                    _log_rate_limit_hit("user", request, tenant_id, user_id)
                    return create_rate_limit_response(retry_after, trace_id)
            
            # Check per-tenant limit
            if tenant:
                allowed, retry_after = rate_limiter.check_tenant_limit(tenant_id, tenant)
                if not allowed:
                    _log_rate_limit_hit("tenant", request, tenant_id, user_id)
                    return create_rate_limit_response(retry_after, trace_id)
            
            # If no specific limits provided, use defaults
            if not user and not tenant:
                # Check default user limit
                if user_id:
                    allowed, retry_after = rate_limiter.check_user_limit(tenant_id, user_id)
                    if not allowed:
                        _log_rate_limit_hit("user_default", request, tenant_id, user_id)
                        return create_rate_limit_response(retry_after, trace_id)
                
                # Check default tenant limit
                allowed, retry_after = rate_limiter.check_tenant_limit(tenant_id)
                if not allowed:
                    _log_rate_limit_hit("tenant_default", request, tenant_id, user_id)
                    return create_rate_limit_response(retry_after, trace_id)
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def _is_exempt_route(request: Request) -> bool:
    """Check if route is exempt from rate limiting."""
    exempt_paths = [
        "/health",
        "/ready", 
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico"
    ]
    
    # Check for WebSocket upgrade
    if request.headers.get("upgrade", "").lower() == "websocket":
        return True
    
    # Check exempt paths
    return any(request.url.path.startswith(path) for path in exempt_paths)


def _log_rate_limit_hit(limit_type: str, request: Request, tenant_id: str, user_id: str = None):
    """Log rate limit hit for telemetry."""
    logger.warning(
        f"Rate limit hit: {limit_type}",
        extra={
            "event_type": "rate_limit_hit",
            "limit_type": limit_type,
            "route": request.url.path,
            "method": request.method,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "timestamp": time.time()
        }
    )
    
    # TODO: Increment Prometheus metrics here
    # rate_limit_hits_total.labels(
    #     route=request.url.path,
    #     tenant_id=tenant_id,
    #     limit_type=limit_type
    # ).inc()


class RateLimitMiddleware:
    """Middleware for global rate limiting."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope, receive)
        
        # Skip rate limiting for exempt routes
        if _is_exempt_route(request):
            await self.app(scope, receive, send)
            return
        
        # Get tenant_id and user_id from request state (set by auth middleware)
        tenant_id = getattr(request.state, 'tenant_id', None)
        user_id = getattr(request.state, 'user_id', None)
        
        if not tenant_id:
            # If no tenant context, skip rate limiting
            await self.app(scope, receive, send)
            return
        
        trace_id = str(uuid.uuid4())
        
        # Apply default rate limits
        if user_id:
            allowed, retry_after = rate_limiter.check_user_limit(tenant_id, user_id)
            if not allowed:
                _log_rate_limit_hit("user_global", request, tenant_id, user_id)
                response = create_rate_limit_response(retry_after, trace_id)
                await response(scope, receive, send)
                return
        
        allowed, retry_after = rate_limiter.check_tenant_limit(tenant_id)
        if not allowed:
            _log_rate_limit_hit("tenant_global", request, tenant_id, user_id)
            response = create_rate_limit_response(retry_after, trace_id)
            await response(scope, receive, send)
            return
        
        await self.app(scope, receive, send)
