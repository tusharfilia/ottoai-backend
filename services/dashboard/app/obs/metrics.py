"""
Prometheus metrics for OttoAI backend.
Provides metrics for HTTP requests, Celery tasks, and business operations.
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from typing import Optional, Dict, Any
from fastapi import Response
import time


# HTTP Request Metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['route', 'method', 'status']
)

http_request_duration_ms = Histogram(
    'http_request_duration_ms',
    'HTTP request duration in milliseconds',
    ['route', 'method'],
    buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)
)

# Ask Otto / RAG Metrics
rag_queries_total = Counter(
    'rag_queries_total',
    'Total number of Ask Otto RAG queries',
    ['tenant_id', 'user_role', 'result_count']
)

rag_query_latency_ms = Histogram(
    'rag_query_latency_ms',
    'Ask Otto RAG query latency in milliseconds',
    ['tenant_id', 'user_role'],
    buckets=(10, 50, 100, 250, 500, 1000, 2500, 5000, 10000)
)

# Celery Task Metrics
worker_task_total = Counter(
    'worker_task_total',
    'Total number of Celery tasks',
    ['name', 'status']
)

worker_task_duration_ms = Histogram(
    'worker_task_duration_ms',
    'Celery task duration in milliseconds',
    ['name'],
    buckets=(10, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000)
)

# Webhook Idempotency Metrics (existing, moved here for centralization)
webhook_processed_total = Counter(
    'webhook_processed_total',
    'Total number of webhooks processed',
    ['provider', 'status']
)

webhook_duplicates_total = Counter(
    'webhook_duplicates_total',
    'Total number of duplicate webhooks ignored',
    ['provider']
)

webhook_failures_total = Counter(
    'webhook_failures_total',
    'Total number of webhook processing failures',
    ['provider']
)

webhook_idempotency_purged_total = Counter(
    'webhook_idempotency_purged_total',
    'Total number of idempotency keys purged',
    ['provider']
)

# Business/Cost Metrics (stubs for future implementation)
asr_minutes_total = Counter(
    'asr_minutes_total',
    'Total ASR (Automatic Speech Recognition) minutes used',
    ['tenant_id']
)

llm_tokens_total = Counter(
    'llm_tokens_total',
    'Total LLM tokens used',
    ['tenant_id', 'model']
)

sms_sent_total = Counter(
    'sms_sent_total',
    'Total SMS messages sent',
    ['tenant_id']
)

# System Health Metrics
active_connections = Gauge(
    'active_connections',
    'Number of active database connections'
)

# WebSocket Metrics
ws_connections = Gauge(
    'ws_connections',
    'Number of active WebSocket connections',
    ['tenant_id']
)

ws_messages_sent_total = Counter(
    'ws_messages_sent_total',
    'Total WebSocket messages sent',
    ['channel']
)

ws_messages_dropped_total = Counter(
    'ws_messages_dropped_total',
    'Total WebSocket messages dropped',
    ['reason']
)

ws_subscriptions_total = Counter(
    'ws_subscriptions_total',
    'Total WebSocket channel subscriptions',
    ['channel']
)

cache_hits_total = Counter(
    'cache_hits_total',
    'Total number of cache hits',
    ['cache_type']
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Total number of cache misses',
    ['cache_type']
)

# UWC Integration Metrics
uwc_requests_total = Counter(
    'uwc_requests_total',
    'Total number of UWC API requests',
    ['endpoint', 'method', 'status']
)

uwc_request_duration_ms = Histogram(
    'uwc_request_duration_ms',
    'UWC API request duration in milliseconds',
    ['endpoint', 'method'],
    buckets=(10, 50, 100, 250, 500, 1000, 2000, 5000, 10000, 30000)
)

uwc_request_errors_total = Counter(
    'uwc_request_errors_total',
    'Total number of UWC API request errors',
    ['endpoint', 'error_type']
)

uwc_retries_total = Counter(
    'uwc_retries_total',
    'Total number of UWC API request retries',
    ['endpoint']
)


class MetricsCollector:
    """Centralized metrics collection and management."""
    
    def __init__(self):
        self.start_time = time.time()
        # Expose RAG metrics so callers can use metrics.rag_queries_total / rag_query_latency_ms
        self.rag_queries_total = rag_queries_total
        self.rag_query_latency_ms = rag_query_latency_ms
    
    def record_http_request(self, route: str, method: str, status_code: int, duration_ms: float):
        """Record HTTP request metrics."""
        # Normalize route for metrics (remove dynamic segments)
        normalized_route = self._normalize_route(route)
        
        http_requests_total.labels(
            route=normalized_route,
            method=method,
            status=str(status_code)
        ).inc()
        
        http_request_duration_ms.labels(
            route=normalized_route,
            method=method
        ).observe(duration_ms)
    
    def record_worker_task(self, task_name: str, status: str, duration_ms: Optional[float] = None):
        """Record Celery task metrics."""
        worker_task_total.labels(
            name=task_name,
            status=status
        ).inc()
        
        if duration_ms is not None:
            worker_task_duration_ms.labels(name=task_name).observe(duration_ms)
    
    def record_webhook_processed(self, provider: str, status: str = "processed"):
        """Record webhook processing metrics."""
        webhook_processed_total.labels(
            provider=provider,
            status=status
        ).inc()
    
    def record_webhook_duplicate(self, provider: str):
        """Record duplicate webhook metrics."""
        webhook_duplicates_total.labels(provider=provider).inc()
    
    def record_webhook_failure(self, provider: str):
        """Record webhook failure metrics."""
        webhook_failures_total.labels(provider=provider).inc()
    
    def record_idempotency_purged(self, provider: str, count: int = 1):
        """Record idempotency key purge metrics."""
        webhook_idempotency_purged_total.labels(provider=provider).inc(count)
    
    def record_asr_minutes(self, tenant_id: str, minutes: float):
        """Record ASR usage metrics."""
        asr_minutes_total.labels(tenant_id=tenant_id).inc(minutes)
    
    def record_llm_tokens(self, tenant_id: str, model: str, tokens: int):
        """Record LLM token usage metrics."""
        llm_tokens_total.labels(
            tenant_id=tenant_id,
            model=model
        ).inc(tokens)
    
    def record_sms_sent(self, tenant_id: str, count: int = 1):
        """Record SMS usage metrics."""
        sms_sent_total.labels(tenant_id=tenant_id).inc(count)
    
    def record_cache_hit(self, cache_type: str):
        """Record cache hit metrics."""
        cache_hits_total.labels(cache_type=cache_type).inc()
    
    def record_cache_miss(self, cache_type: str):
        """Record cache miss metrics."""
        cache_misses_total.labels(cache_type=cache_type).inc()
    
    def set_active_connections(self, count: int):
        """Set the number of active database connections."""
        active_connections.set(count)
    
    def record_uwc_request(self, endpoint: str, method: str, status_code: int, latency_ms: float):
        """Record UWC API request metrics."""
        uwc_requests_total.labels(
            endpoint=endpoint,
            method=method,
            status=str(status_code)
        ).inc()
        
        uwc_request_duration_ms.labels(
            endpoint=endpoint,
            method=method
        ).observe(latency_ms)
        
        # Record errors
        if status_code >= 400:
            error_type = "client_error" if status_code < 500 else "server_error"
            uwc_request_errors_total.labels(
                endpoint=endpoint,
                error_type=error_type
            ).inc()
    
    def record_uwc_retry(self, endpoint: str):
        """Record UWC API request retry."""
        uwc_retries_total.labels(endpoint=endpoint).inc()
    
    def _normalize_route(self, route: str) -> str:
        """Normalize route for metrics by replacing dynamic segments."""
        import re
        
        # Replace UUIDs with placeholder
        route = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{uuid}', route)
        
        # Replace numeric IDs with placeholder
        route = re.sub(r'/\d+', '/{id}', route)
        
        # Replace other common dynamic segments
        route = re.sub(r'/[a-zA-Z0-9_-]{20,}', '/{hash}', route)
        
        return route
    
    def get_metrics_response(self) -> Response:
        """Get Prometheus metrics in text format."""
        metrics_data = generate_latest()
        return Response(
            content=metrics_data,
            media_type=CONTENT_TYPE_LATEST
        )


# Global metrics collector instance
metrics = MetricsCollector()


# Helper functions for easy metric recording
def record_http_request(route: str, method: str, status_code: int, duration_ms: float):
    """Record HTTP request metrics."""
    metrics.record_http_request(route, method, status_code, duration_ms)


def record_worker_task(task_name: str, status: str, duration_ms: Optional[float] = None):
    """Record Celery task metrics."""
    metrics.record_worker_task(task_name, status, duration_ms)


def record_webhook_processed(provider: str, status: str = "processed"):
    """Record webhook processing metrics."""
    metrics.record_webhook_processed(provider, status)


def record_webhook_duplicate(provider: str):
    """Record duplicate webhook metrics."""
    metrics.record_webhook_duplicate(provider)


def record_webhook_failure(provider: str):
    """Record webhook failure metrics."""
    metrics.record_webhook_failure(provider)


def record_idempotency_purged(provider: str, count: int = 1):
    """Record idempotency key purge metrics."""
    metrics.record_idempotency_purged(provider, count)


def record_asr_minutes(tenant_id: str, minutes: float):
    """Record ASR usage metrics."""
    metrics.record_asr_minutes(tenant_id, minutes)


def record_llm_tokens(tenant_id: str, model: str, tokens: int):
    """Record LLM token usage metrics."""
    metrics.record_llm_tokens(tenant_id, model, tokens)


def record_sms_sent(tenant_id: str, count: int = 1):
    """Record SMS usage metrics."""
    metrics.record_sms_sent(tenant_id, count)


def record_cache_hit(cache_type: str):
    """Record cache hit metrics."""
    metrics.record_cache_hit(cache_type)


def record_cache_miss(cache_type: str):
    """Record cache miss metrics."""
    metrics.record_cache_miss(cache_type)


def set_active_connections(count: int):
    """Set the number of active database connections."""
    metrics.set_active_connections(count)


def record_ws_connection(tenant_id: str, count: int):
    """Record WebSocket connection count for a tenant."""
    ws_connections.labels(tenant_id=tenant_id).set(count)


def record_ws_message_sent(channel: str):
    """Record WebSocket message sent."""
    ws_messages_sent_total.labels(channel=channel).inc()


def record_ws_message_dropped(reason: str):
    """Record WebSocket message dropped."""
    ws_messages_dropped_total.labels(reason=reason).inc()


def record_ws_subscription(channel: str):
    """Record WebSocket channel subscription."""
    ws_subscriptions_total.labels(channel=channel).inc()
