"""
OpenTelemetry distributed tracing for OttoAI backend.
Provides tracing for FastAPI requests and Celery tasks.
"""
import os
from typing import Optional, Dict, Any
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositeHTTPPropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.trace.propagation.b3 import B3MultiFormat
from app.config import settings


def setup_tracing():
    """Configure OpenTelemetry tracing for the application."""
    
    # Get service names from config
    api_service_name = getattr(settings, 'OTEL_SERVICE_NAME_API', 'otto-api')
    worker_service_name = getattr(settings, 'OTEL_SERVICE_NAME_WORKER', 'otto-worker')
    
    # Determine current service (API or Worker)
    current_service = api_service_name
    if os.getenv('CELERY_WORKER', '').lower() in ('true', '1', 'yes'):
        current_service = worker_service_name
    
    # Create resource with service information
    resource = Resource.create({
        "service.name": current_service,
        "service.version": "1.0.0",
        "deployment.environment": getattr(settings, 'ENVIRONMENT', 'development'),
    })
    
    # Create tracer provider
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)
    
    # Configure exporter
    otlp_endpoint = getattr(settings, 'OTEL_EXPORTER_OTLP_ENDPOINT', None)
    
    if otlp_endpoint:
        # Use OTLP exporter for production
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    else:
        # Use console exporter for development
        exporter = ConsoleSpanExporter()
    
    # Add span processor
    span_processor = BatchSpanProcessor(exporter)
    tracer_provider.add_span_processor(span_processor)
    
    # Set up propagation
    propagator = CompositeHTTPPropagator([
        TraceContextTextMapPropagator(),
        B3MultiFormat(),
    ])
    set_global_textmap(propagator)
    
    return tracer_provider


def instrument_fastapi(app):
    """Instrument FastAPI application with OpenTelemetry."""
    FastAPIInstrumentor.instrument_app(app)
    return app


def instrument_celery():
    """Instrument Celery with OpenTelemetry."""
    CeleryInstrumentor().instrument()
    return True


def instrument_requests():
    """Instrument requests library with OpenTelemetry."""
    RequestsInstrumentor().instrument()
    return True


def instrument_sqlalchemy():
    """Instrument SQLAlchemy with OpenTelemetry."""
    SQLAlchemyInstrumentor().instrument()
    return True


def get_tracer(name: str):
    """Get a tracer instance."""
    return trace.get_tracer(name)


def get_current_trace_id() -> Optional[str]:
    """Get the current trace ID from the active span."""
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        span_context = current_span.get_span_context()
        if span_context.is_valid:
            return format(span_context.trace_id, '032x')
    return None


def get_current_span_id() -> Optional[str]:
    """Get the current span ID from the active span."""
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        span_context = current_span.get_span_context()
        if span_context.is_valid:
            return format(span_context.span_id, '016x')
    return None


def create_span(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Create a new span with the given name and attributes."""
    tracer = get_tracer(__name__)
    span = tracer.start_span(name)
    
    if attributes:
        for key, value in attributes.items():
            span.set_attribute(key, value)
    
    return span


def add_span_attributes(attributes: Dict[str, Any]):
    """Add attributes to the current active span."""
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        for key, value in attributes.items():
            current_span.set_attribute(key, value)


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Add an event to the current active span."""
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.add_event(name, attributes or {})


def add_span_error(error: Exception, attributes: Optional[Dict[str, Any]] = None):
    """Add error information to the current active span."""
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.set_status(trace.Status(trace.StatusCode.ERROR, str(error)))
        current_span.set_attribute("error", True)
        current_span.set_attribute("error.type", type(error).__name__)
        current_span.set_attribute("error.message", str(error))
        
        if attributes:
            for key, value in attributes.items():
                current_span.set_attribute(key, value)


def trace_webhook(provider: str, external_id: str, tenant_id: Optional[str] = None):
    """Create a span for webhook processing."""
    attributes = {
        "webhook.provider": provider,
        "webhook.external_id": external_id,
    }
    
    if tenant_id:
        attributes["tenant.id"] = tenant_id
    
    return create_span(f"webhook.{provider}", attributes)


def trace_celery_task(task_name: str, task_id: str, tenant_id: Optional[str] = None):
    """Create a span for Celery task execution."""
    attributes = {
        "celery.task_name": task_name,
        "celery.task_id": task_id,
    }
    
    if tenant_id:
        attributes["tenant.id"] = tenant_id
    
    return create_span(f"celery.{task_name}", attributes)


def extract_trace_context_from_celery_headers(headers: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Extract trace context from Celery task headers."""
    trace_context = {}
    
    # Check for traceparent header
    if 'traceparent' in headers:
        trace_context['traceparent'] = headers['traceparent']
    
    # Check for b3 headers
    if 'b3' in headers:
        trace_context['b3'] = headers['b3']
    elif 'x-b3-traceid' in headers and 'x-b3-spanid' in headers:
        trace_context['x-b3-traceid'] = headers['x-b3-traceid']
        trace_context['x-b3-spanid'] = headers['x-b3-spanid']
        if 'x-b3-sampled' in headers:
            trace_context['x-b3-sampled'] = headers['x-b3-sampled']
    
    return trace_context if trace_context else None


def inject_trace_context_into_celery_headers(headers: Dict[str, Any]) -> Dict[str, Any]:
    """Inject current trace context into Celery task headers."""
    from opentelemetry.propagate import inject
    
    # Create a carrier dict for injection
    carrier = {}
    inject(carrier)
    
    # Add trace context to headers
    headers.update(carrier)
    
    return headers
