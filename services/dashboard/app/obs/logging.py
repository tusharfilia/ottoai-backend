"""
Structured logging configuration for OttoAI backend.
Provides JSON-formatted logs with correlation IDs and PII redaction.
"""
import json
import logging
import logging.config
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Union
from fastapi import Request
from app.config import settings


class PIIRedactor:
    """Redacts PII from log messages when enabled."""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        if enabled:
            # Phone number patterns (various formats)
            self.phone_patterns = [
                r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # 123-456-7890
                r'\(\d{3}\)\s*\d{3}[-.]?\d{4}',    # (123) 456-7890
                r'\+\d{1,3}[-.\s]?\d{3,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}',  # International
            ]
            
            # Email pattern
            self.email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            
            # Compile patterns
            self.compiled_patterns = [
                re.compile(pattern) for pattern in self.phone_patterns
            ]
            self.email_pattern_compiled = re.compile(self.email_pattern)
    
    def redact(self, message: str) -> str:
        """Redact PII from a log message."""
        if not self.enabled:
            return message
        
        # Redact phone numbers
        for pattern in self.compiled_patterns:
            message = pattern.sub('[REDACTED_PHONE]', message)
        
        # Redact emails
        message = self.email_pattern_compiled.sub('[REDACTED_EMAIL]', message)
        
        return message


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging with PII redaction."""
    
    def __init__(self, redact_pii: bool = True):
        super().__init__()
        self.redactor = PIIRedactor(redact_pii)
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with structured fields."""
        # Base log structure
        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": getattr(record, 'service', 'api'),
            "message": self.redactor.redact(record.getMessage()),
            "logger": record.name,
        }
        
        # Add optional fields if present
        optional_fields = [
            'route', 'method', 'status', 'latency_ms', 'trace_id', 
            'tenant_id', 'user_id', 'ip', 'provider', 'external_id',
            'task_name', 'task_id', 'error_type', 'stack_trace'
        ]
        
        for field in optional_fields:
            if hasattr(record, field):
                value = getattr(record, field)
                if value is not None:
                    log_entry[field] = value
        
        # Add exception info if present
        if record.exc_info:
            log_entry["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            log_entry["stack_trace"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging():
    """Configure structured logging for the application."""
    log_level = getattr(settings, 'LOG_LEVEL', 'INFO').upper()
    redact_pii = getattr(settings, 'OBS_REDACT_PII', True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler with structured formatter
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(StructuredFormatter(redact_pii))
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


def log_request(
    logger: logging.Logger,
    request: Request,
    status_code: int,
    latency_ms: float,
    trace_id: str,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    **kwargs
):
    """Log a request with structured fields."""
    extra = {
        'service': 'api',
        'route': request.url.path,
        'method': request.method,
        'status': status_code,
        'latency_ms': round(latency_ms, 2),
        'trace_id': trace_id,
        'ip': request.client.host if request.client else None,
    }
    
    if tenant_id:
        extra['tenant_id'] = tenant_id
    if user_id:
        extra['user_id'] = user_id
    
    # Add any additional fields
    extra.update(kwargs)
    
    # Choose log level based on status code
    if status_code >= 500:
        logger.error(f"Request completed with server error", extra=extra)
    elif status_code >= 400:
        logger.warning(f"Request completed with client error", extra=extra)
    else:
        logger.info(f"Request completed successfully", extra=extra)


def log_webhook(
    logger: logging.Logger,
    provider: str,
    external_id: str,
    trace_id: str,
    status: str = "processed",
    tenant_id: Optional[str] = None,
    **kwargs
):
    """Log webhook processing with structured fields."""
    extra = {
        'service': 'api',
        'provider': provider,
        'external_id': external_id,
        'trace_id': trace_id,
        'status': status,
    }
    
    if tenant_id:
        extra['tenant_id'] = tenant_id
    
    # Add any additional fields
    extra.update(kwargs)
    
    logger.info(f"Webhook {status}: {provider}", extra=extra)


def log_celery_task(
    logger: logging.Logger,
    task_name: str,
    task_id: str,
    status: str,
    trace_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    **kwargs
):
    """Log Celery task execution with structured fields."""
    extra = {
        'service': 'worker',
        'task_name': task_name,
        'task_id': task_id,
        'status': status,
    }
    
    if trace_id:
        extra['trace_id'] = trace_id
    if tenant_id:
        extra['tenant_id'] = tenant_id
    if duration_ms is not None:
        extra['latency_ms'] = round(duration_ms, 2)
    
    # Add any additional fields
    extra.update(kwargs)
    
    if status == "success":
        logger.info(f"Task completed: {task_name}", extra=extra)
    elif status == "failure":
        logger.error(f"Task failed: {task_name}", extra=extra)
    else:
        logger.info(f"Task {status}: {task_name}", extra=extra)


def log_error(
    logger: logging.Logger,
    error: Exception,
    trace_id: str,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    **kwargs
):
    """Log an error with structured fields and stack trace."""
    extra = {
        'service': 'api',
        'trace_id': trace_id,
        'error_type': type(error).__name__,
    }
    
    if tenant_id:
        extra['tenant_id'] = tenant_id
    if user_id:
        extra['user_id'] = user_id
    
    # Add any additional fields
    extra.update(kwargs)
    
    logger.error(f"Error occurred: {str(error)}", exc_info=True, extra=extra)


def generate_trace_id() -> str:
    """Generate a new trace ID."""
    return str(uuid.uuid4())


def extract_trace_id(request: Request) -> str:
    """Extract trace ID from request headers or generate new one."""
    # Check for X-Request-Id header first
    request_id = request.headers.get("X-Request-Id")
    if request_id:
        return request_id
    
    # Check for traceparent header (OpenTelemetry)
    traceparent = request.headers.get("traceparent")
    if traceparent:
        # Extract trace ID from traceparent format: 00-<trace_id>-<span_id>-<flags>
        parts = traceparent.split("-")
        if len(parts) >= 2:
            return parts[1]
    
    # Generate new trace ID
    return generate_trace_id()
