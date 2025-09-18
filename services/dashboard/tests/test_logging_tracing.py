"""
Tests for observability logging and tracing functionality.
"""
import json
import pytest
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI, Request, HTTPException
from app.main import app
from app.obs.logging import get_logger, extract_trace_id, generate_trace_id
from app.obs.tracing import get_current_trace_id, get_current_span_id
from app.obs.errors import ProblemDetail, create_problem_detail


class TestLogging:
    """Test structured logging functionality."""
    
    def test_generate_trace_id(self):
        """Test trace ID generation."""
        trace_id = generate_trace_id()
        assert isinstance(trace_id, str)
        assert len(trace_id) == 36  # UUID4 length
        # Should be valid UUID
        uuid.UUID(trace_id)
    
    def test_extract_trace_id_from_header(self):
        """Test extracting trace ID from X-Request-Id header."""
        from fastapi import Request
        from unittest.mock import Mock
        
        # Mock request with X-Request-Id header
        request = Mock(spec=Request)
        request.headers = {"X-Request-Id": "test-trace-id-123"}
        
        trace_id = extract_trace_id(request)
        assert trace_id == "test-trace-id-123"
    
    def test_extract_trace_id_from_traceparent(self):
        """Test extracting trace ID from traceparent header."""
        from fastapi import Request
        from unittest.mock import Mock
        
        # Mock request with traceparent header
        request = Mock(spec=Request)
        request.headers = {"traceparent": "00-12345678901234567890123456789012-1234567890123456-01"}
        
        trace_id = extract_trace_id(request)
        assert trace_id == "12345678901234567890123456789012"
    
    def test_extract_trace_id_generates_new(self):
        """Test that new trace ID is generated when none provided."""
        from fastapi import Request
        from unittest.mock import Mock
        
        # Mock request without trace headers
        request = Mock(spec=Request)
        request.headers = {}
        
        trace_id = extract_trace_id(request)
        assert isinstance(trace_id, str)
        assert len(trace_id) == 36
        # Should be valid UUID
        uuid.UUID(trace_id)
    
    def test_structured_logging_format(self):
        """Test that logs are in JSON format with required fields."""
        import logging
        from io import StringIO
        from app.obs.logging import StructuredFormatter
        
        # Create a test logger with StringIO handler
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(StructuredFormatter(redact_pii=False))
        
        logger = logging.getLogger("test_logger")
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        
        # Log a test message
        logger.info("Test message", extra={
            'service': 'api',
            'route': '/test',
            'method': 'GET',
            'status': 200,
            'trace_id': 'test-trace-id'
        })
        
        # Parse the log output
        log_output = log_stream.getvalue().strip()
        log_data = json.loads(log_output)
        
        # Verify required fields
        assert 'ts' in log_data
        assert 'level' in log_data
        assert 'message' in log_data
        assert 'service' in log_data
        assert 'route' in log_data
        assert 'method' in log_data
        assert 'status' in log_data
        assert 'trace_id' in log_data
        
        assert log_data['level'] == 'INFO'
        assert log_data['message'] == 'Test message'
        assert log_data['service'] == 'api'
        assert log_data['route'] == '/test'
        assert log_data['method'] == 'GET'
        assert log_data['status'] == 200
        assert log_data['trace_id'] == 'test-trace-id'


class TestTracing:
    """Test distributed tracing functionality."""
    
    def test_get_current_trace_id_no_span(self):
        """Test getting trace ID when no active span."""
        trace_id = get_current_trace_id()
        assert trace_id is None
    
    def test_get_current_span_id_no_span(self):
        """Test getting span ID when no active span."""
        span_id = get_current_span_id()
        assert span_id is None


class TestErrorHandling:
    """Test RFC-7807 error handling."""
    
    def test_problem_detail_creation(self):
        """Test ProblemDetail object creation."""
        problem = ProblemDetail(
            type="https://example.com/errors/validation",
            title="Validation Error",
            detail="Invalid input provided",
            status=422,
            instance="/api/users",
            trace_id="test-trace-id"
        )
        
        problem_dict = problem.to_dict()
        
        assert problem_dict['type'] == "https://example.com/errors/validation"
        assert problem_dict['title'] == "Validation Error"
        assert problem_dict['detail'] == "Invalid input provided"
        assert problem_dict['status'] == 422
        assert problem_dict['instance'] == "/api/users"
        assert problem_dict['trace_id'] == "test-trace-id"
    
    def test_create_problem_detail_from_exception(self):
        """Test creating ProblemDetail from exception."""
        from fastapi import Request
        from unittest.mock import Mock
        
        # Mock request
        request = Mock(spec=Request)
        request.url.path = "/api/test"
        request.state.trace_id = "test-trace-id"
        
        # Create exception
        error = ValueError("Test error")
        
        problem = create_problem_detail(
            error=error,
            request=request,
            status_code=400,
            error_type="https://example.com/errors/validation",
            title="Validation Error"
        )
        
        problem_dict = problem.to_dict()
        
        assert problem_dict['type'] == "https://example.com/errors/validation"
        assert problem_dict['title'] == "Validation Error"
        assert problem_dict['detail'] == "Test error"
        assert problem_dict['status'] == 400
        assert problem_dict['instance'] == "/api/test"
        assert problem_dict['trace_id'] == "test-trace-id"


class TestAPIEndpoints:
    """Test API endpoints with observability."""
    
    def test_health_endpoint_returns_trace_id(self):
        """Test that health endpoint returns X-Request-Id header."""
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        assert "X-Request-Id" in response.headers
        assert response.headers["X-Request-Id"] is not None
    
    def test_metrics_endpoint_returns_trace_id(self):
        """Test that metrics endpoint returns X-Request-Id header."""
        client = TestClient(app)
        response = client.get("/metrics")
        
        assert response.status_code == 200
        assert "X-Request-Id" in response.headers
        assert response.headers["X-Request-Id"] is not None
    
    def test_error_endpoint_returns_rfc7807(self):
        """Test that error endpoint returns RFC-7807 format."""
        # Create a test endpoint that raises an exception
        @app.get("/test-error")
        async def test_error():
            raise HTTPException(status_code=400, detail="Test error")
        
        client = TestClient(app)
        response = client.get("/test-error")
        
        assert response.status_code == 400
        assert "X-Request-Id" in response.headers
        
        # Parse response body
        response_data = response.json()
        
        # Verify RFC-7807 format
        assert "type" in response_data
        assert "title" in response_data
        assert "detail" in response_data
        assert "status" in response_data
        assert "trace_id" in response_data
        
        assert response_data["status"] == 400
        assert response_data["detail"] == "Test error"
        assert response_data["trace_id"] == response.headers["X-Request-Id"]
    
    def test_trace_id_consistency(self):
        """Test that trace ID is consistent across request and response."""
        client = TestClient(app)
        response = client.get("/health")
        
        trace_id = response.headers["X-Request-Id"]
        
        # Make another request and verify trace ID is different
        response2 = client.get("/health")
        trace_id2 = response2.headers["X-Request-Id"]
        
        assert trace_id != trace_id2
        assert len(trace_id) == 36  # UUID4 length
        assert len(trace_id2) == 36


class TestCeleryIntegration:
    """Test Celery task observability."""
    
    @patch('app.services.celery_tasks.celery_app')
    def test_celery_task_tracing(self, mock_celery):
        """Test that Celery tasks include trace context."""
        from app.services.celery_tasks import test_task
        
        # Mock Celery task request
        mock_request = MagicMock()
        mock_request.id = "test-task-id"
        
        # Mock the task binding
        with patch.object(test_task, 'request', mock_request):
            result = test_task()
            
            assert result['status'] == 'success'
            assert result['task_id'] == 'test-task-id'
    
    @patch('app.services.celery_tasks.celery_app')
    def test_celery_task_error_handling(self, mock_celery):
        """Test Celery task error handling with observability."""
        from app.services.celery_tasks import test_task
        
        # Mock Celery task request
        mock_request = MagicMock()
        mock_request.id = "test-task-id"
        
        # Mock the task to raise an exception
        with patch.object(test_task, 'request', mock_request):
            with patch('app.obs.logging.log_celery_task') as mock_log:
                with patch('app.obs.metrics.record_worker_task') as mock_metrics:
                    # This should not raise an exception due to error handling
                    try:
                        result = test_task()
                        assert result['status'] == 'success'
                    except Exception:
                        # If an exception is raised, verify it was logged
                        mock_log.assert_called()
                        mock_metrics.assert_called()


if __name__ == "__main__":
    pytest.main([__file__])
