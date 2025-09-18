"""
Tests for Prometheus metrics functionality.
"""
import pytest
import time
from fastapi.testclient import TestClient
from app.main import app
from app.obs.metrics import (
    metrics, record_http_request, record_worker_task, 
    record_webhook_processed, record_webhook_duplicate,
    record_webhook_failure, record_asr_minutes, record_llm_tokens,
    record_sms_sent, record_cache_hit, record_cache_miss
)


class TestHTTPMetrics:
    """Test HTTP request metrics."""
    
    def test_record_http_request(self):
        """Test recording HTTP request metrics."""
        # Record a successful request
        record_http_request("/test", "GET", 200, 150.5)
        
        # Get metrics response
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        metrics_text = response.text
        
        # Check that metrics contain our recorded request
        assert "http_requests_total" in metrics_text
        assert 'route="/test"' in metrics_text
        assert 'method="GET"' in metrics_text
        assert 'status="200"' in metrics_text
        
        # Check duration histogram
        assert "http_request_duration_ms" in metrics_text
    
    def test_record_multiple_requests(self):
        """Test recording multiple HTTP requests."""
        # Record multiple requests
        record_http_request("/test", "GET", 200, 100.0)
        record_http_request("/test", "GET", 200, 200.0)
        record_http_request("/test", "POST", 201, 300.0)
        record_http_request("/test", "GET", 404, 50.0)
        
        # Get metrics response
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        metrics_text = response.text
        
        # Check that all requests are recorded
        assert "http_requests_total" in metrics_text
        assert 'route="/test"' in metrics_text
        assert 'method="GET"' in metrics_text
        assert 'method="POST"' in metrics_text
        assert 'status="200"' in metrics_text
        assert 'status="201"' in metrics_text
        assert 'status="404"' in metrics_text
    
    def test_route_normalization(self):
        """Test that routes are normalized for metrics."""
        # Record requests with dynamic segments
        record_http_request("/users/123", "GET", 200, 100.0)
        record_http_request("/users/456", "GET", 200, 100.0)
        record_http_request("/calls/abc-def-ghi", "GET", 200, 100.0)
        
        # Get metrics response
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        metrics_text = response.text
        
        # Check that routes are normalized
        assert 'route="/users/{id}"' in metrics_text
        assert 'route="/calls/{uuid}"' in metrics_text


class TestWorkerMetrics:
    """Test Celery worker task metrics."""
    
    def test_record_worker_task_success(self):
        """Test recording successful worker task."""
        record_worker_task("test_task", "success", 1000.0)
        
        # Get metrics response
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        metrics_text = response.text
        
        # Check that task metrics are recorded
        assert "worker_task_total" in metrics_text
        assert 'name="test_task"' in metrics_text
        assert 'status="success"' in metrics_text
        
        # Check duration histogram
        assert "worker_task_duration_ms" in metrics_text
    
    def test_record_worker_task_failure(self):
        """Test recording failed worker task."""
        record_worker_task("test_task", "failure", 500.0)
        
        # Get metrics response
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        metrics_text = response.text
        
        # Check that task metrics are recorded
        assert "worker_task_total" in metrics_text
        assert 'name="test_task"' in metrics_text
        assert 'status="failure"' in metrics_text
    
    def test_record_worker_task_without_duration(self):
        """Test recording worker task without duration."""
        record_worker_task("test_task", "started")
        
        # Get metrics response
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        metrics_text = response.text
        
        # Check that task metrics are recorded
        assert "worker_task_total" in metrics_text
        assert 'name="test_task"' in metrics_text
        assert 'status="started"' in metrics_text


class TestWebhookMetrics:
    """Test webhook processing metrics."""
    
    def test_record_webhook_processed(self):
        """Test recording webhook processing."""
        record_webhook_processed("callrail", "processed")
        
        # Get metrics response
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        metrics_text = response.text
        
        # Check that webhook metrics are recorded
        assert "webhook_processed_total" in metrics_text
        assert 'provider="callrail"' in metrics_text
        assert 'status="processed"' in metrics_text
    
    def test_record_webhook_duplicate(self):
        """Test recording duplicate webhook."""
        record_webhook_duplicate("twilio")
        
        # Get metrics response
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        metrics_text = response.text
        
        # Check that duplicate metrics are recorded
        assert "webhook_duplicates_total" in metrics_text
        assert 'provider="twilio"' in metrics_text
    
    def test_record_webhook_failure(self):
        """Test recording webhook failure."""
        record_webhook_failure("clerk")
        
        # Get metrics response
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        metrics_text = response.text
        
        # Check that failure metrics are recorded
        assert "webhook_failures_total" in metrics_text
        assert 'provider="clerk"' in metrics_text


class TestBusinessMetrics:
    """Test business/cost metrics."""
    
    def test_record_asr_minutes(self):
        """Test recording ASR usage."""
        record_asr_minutes("tenant-123", 5.5)
        
        # Get metrics response
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        metrics_text = response.text
        
        # Check that ASR metrics are recorded
        assert "asr_minutes_total" in metrics_text
        assert 'tenant_id="tenant-123"' in metrics_text
    
    def test_record_llm_tokens(self):
        """Test recording LLM token usage."""
        record_llm_tokens("tenant-123", "gpt-4", 1000)
        
        # Get metrics response
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        metrics_text = response.text
        
        # Check that LLM metrics are recorded
        assert "llm_tokens_total" in metrics_text
        assert 'tenant_id="tenant-123"' in metrics_text
        assert 'model="gpt-4"' in metrics_text
    
    def test_record_sms_sent(self):
        """Test recording SMS usage."""
        record_sms_sent("tenant-123", 3)
        
        # Get metrics response
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        metrics_text = response.text
        
        # Check that SMS metrics are recorded
        assert "sms_sent_total" in metrics_text
        assert 'tenant_id="tenant-123"' in metrics_text


class TestCacheMetrics:
    """Test cache metrics."""
    
    def test_record_cache_hit(self):
        """Test recording cache hit."""
        record_cache_hit("redis")
        
        # Get metrics response
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        metrics_text = response.text
        
        # Check that cache hit metrics are recorded
        assert "cache_hits_total" in metrics_text
        assert 'cache_type="redis"' in metrics_text
    
    def test_record_cache_miss(self):
        """Test recording cache miss."""
        record_cache_miss("redis")
        
        # Get metrics response
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        metrics_text = response.text
        
        # Check that cache miss metrics are recorded
        assert "cache_misses_total" in metrics_text
        assert 'cache_type="redis"' in metrics_text


class TestMetricsEndpoint:
    """Test the /metrics endpoint."""
    
    def test_metrics_endpoint_returns_prometheus_format(self):
        """Test that /metrics endpoint returns Prometheus format."""
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; version=0.0.4; charset=utf-8"
        
        metrics_text = response.text
        
        # Check for common Prometheus metric types
        assert "# HELP" in metrics_text
        assert "# TYPE" in metrics_text
        
        # Check for our custom metrics
        assert "http_requests_total" in metrics_text
        assert "http_request_duration_ms" in metrics_text
        assert "worker_task_total" in metrics_text
        assert "worker_task_duration_ms" in metrics_text
    
    def test_metrics_endpoint_includes_trace_id(self):
        """Test that /metrics endpoint includes trace ID in response headers."""
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        assert "X-Request-Id" in response.headers
        assert response.headers["X-Request-Id"] is not None


class TestMetricsIntegration:
    """Test metrics integration with actual API calls."""
    
    def test_api_calls_record_metrics(self):
        """Test that actual API calls record metrics."""
        client = TestClient(app)
        
        # Make several API calls
        response1 = client.get("/health")
        response2 = client.get("/health")
        response3 = client.get("/metrics")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response3.status_code == 200
        
        # Get metrics
        metrics_response = client.get("/metrics")
        metrics_text = metrics_response.text
        
        # Check that our API calls are recorded
        assert "http_requests_total" in metrics_text
        assert 'route="/health"' in metrics_text
        assert 'route="/metrics"' in metrics_text
        assert 'method="GET"' in metrics_text
        assert 'status="200"' in metrics_text


if __name__ == "__main__":
    pytest.main([__file__])
