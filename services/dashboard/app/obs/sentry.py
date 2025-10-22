"""
Sentry error tracking and performance monitoring integration.
Captures exceptions, performance issues, and provides real-time error alerts.
"""
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from app.config import settings
from app.obs.logging import get_logger

logger = get_logger(__name__)


def setup_sentry():
    """
    Initialize Sentry SDK for error tracking and performance monitoring.
    
    Features:
    - Automatic exception capture
    - Performance transaction tracking
    - Request context (user, tenant, trace_id)
    - Integration with FastAPI, SQLAlchemy, Redis, Celery
    """
    if not settings.SENTRY_DSN:
        logger.warning("SENTRY_DSN not configured, skipping Sentry initialization")
        return
    
    try:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            
            # Integrations
            integrations=[
                FastApiIntegration(
                    transaction_style="endpoint",  # Group by endpoint path
                    failed_request_status_codes=[500, 501, 502, 503, 504]
                ),
                SqlalchemyIntegration(),
                RedisIntegration(),
                CeleryIntegration()
            ],
            
            # Performance monitoring
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            
            # Event filtering
            before_send=before_send_event,
            
            # Release tracking (for deployment correlation)
            release=f"otto-backend@{settings.ENVIRONMENT}",
            
            # Additional configuration
            send_default_pii=False,  # Don't send PII automatically
            attach_stacktrace=True,
            max_breadcrumbs=50
        )
        
        logger.info(f"Sentry initialized for environment: {settings.ENVIRONMENT}")
        
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {str(e)}")


def before_send_event(event, hint):
    """
    Filter/modify events before sending to Sentry.
    
    - Redact PII from error messages
    - Add custom context (tenant_id, user_id)
    - Skip non-error events in development
    """
    # Skip non-errors in development
    if settings.ENVIRONMENT == "development" and event.get("level") != "error":
        return None
    
    # Redact PII from exception messages
    if "exception" in event:
        for exception in event["exception"].get("values", []):
            if exception.get("value"):
                exception["value"] = redact_pii(exception["value"])
    
    return event


def redact_pii(text: str) -> str:
    """
    Redact PII from error messages.
    Replace phone numbers, emails, and other sensitive data.
    """
    import re
    
    # Redact phone numbers
    text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE_REDACTED]', text)
    
    # Redact emails
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]', text)
    
    # Redact API keys
    text = re.sub(r'(sk-|pk-|api_key=)[A-Za-z0-9_-]+', r'\1[REDACTED]', text)
    
    return text


def set_user_context(user_id: str, tenant_id: str, role: str):
    """
    Set user context for Sentry error tracking.
    Call this in middleware after authentication.
    """
    sentry_sdk.set_user({
        "id": user_id,
        "tenant_id": tenant_id,
        "role": role
    })


def set_request_context(request_id: str, endpoint: str, method: str):
    """
    Set request context for Sentry.
    Call this for each request in middleware.
    """
    sentry_sdk.set_context("request", {
        "request_id": request_id,
        "endpoint": endpoint,
        "method": method
    })


def capture_exception(exception: Exception, extra_context: dict = None):
    """
    Manually capture an exception with additional context.
    
    Args:
        exception: The exception to capture
        extra_context: Additional context dict (e.g., {"job_id": "123"})
    """
    with sentry_sdk.push_scope() as scope:
        if extra_context:
            for key, value in extra_context.items():
                scope.set_extra(key, value)
        
        sentry_sdk.capture_exception(exception)


def capture_message(message: str, level: str = "info", extra_context: dict = None):
    """
    Capture a message (not an exception) in Sentry.
    
    Args:
        message: The message to log
        level: Severity level (info, warning, error)
        extra_context: Additional context dict
    """
    with sentry_sdk.push_scope() as scope:
        if extra_context:
            for key, value in extra_context.items():
                scope.set_extra(key, value)
        
        sentry_sdk.capture_message(message, level)




