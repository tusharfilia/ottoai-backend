"""
Tests for readiness and health endpoints.
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Test basic health endpoint."""
    
    def test_health_endpoint_returns_200(self):
        """Test that health endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["service"] == "otto-api"
    
    def test_health_endpoint_includes_trace_id(self):
        """Test that health endpoint includes trace ID header."""
        response = client.get("/health")
        assert "X-Request-Id" in response.headers
        assert response.headers["X-Request-Id"] is not None


class TestReadinessEndpoint:
    """Test comprehensive readiness endpoint."""
    
    @patch('redis.from_url')
    def test_readiness_all_components_healthy(self, mock_redis):
        """Test readiness endpoint when all components are healthy."""
        # Mock Redis ping
        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True
        mock_redis.return_value = mock_redis_client
        
        # Mock Celery (disabled by default in tests)
        with patch('app.config.settings.ENABLE_CELERY', False):
            response = client.get("/ready")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["ready"] is True
        assert data["components"]["database"] is True
        assert data["components"]["redis"] is True
        assert data["components"]["celery_workers"] is None  # Disabled
        assert "duration_ms" in data
        assert data["service"] == "otto-api"
    
    @patch('redis.from_url')
    def test_readiness_redis_failure(self, mock_redis):
        """Test readiness endpoint when Redis is unavailable."""
        # Mock Redis connection failure
        mock_redis.side_effect = Exception("Connection refused")
        
        with patch('app.config.settings.ENABLE_CELERY', False):
            response = client.get("/ready")
        
        assert response.status_code == 503
        
        data = response.json()["detail"]
        assert data["ready"] is False
        assert data["components"]["database"] is True
        assert data["components"]["redis"] is False
    
    @patch('redis.from_url')
    def test_readiness_database_failure(self, mock_redis):
        """Test readiness endpoint when database is unavailable."""
        # Mock Redis as healthy
        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True
        mock_redis.return_value = mock_redis_client
        
        # Mock database failure by patching the database session
        with patch('app.routes.health.get_db') as mock_get_db:
            mock_session = MagicMock()
            mock_session.execute.side_effect = Exception("Database connection failed")
            mock_get_db.return_value = mock_session
            
            with patch('app.config.settings.ENABLE_CELERY', False):
                response = client.get("/ready")
        
        assert response.status_code == 503
        
        data = response.json()["detail"]
        assert data["ready"] is False
        assert data["components"]["database"] is False
        assert data["components"]["redis"] is True
    
    @patch('redis.from_url')
    def test_readiness_with_celery_enabled(self, mock_redis):
        """Test readiness endpoint when Celery is enabled."""
        # Mock Redis as healthy
        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True
        mock_redis.return_value = mock_redis_client
        
        # Mock Celery as enabled and healthy
        with patch('app.config.settings.ENABLE_CELERY', True):
            with patch('app.services.celery_tasks.celery_app') as mock_celery:
                mock_inspect = MagicMock()
                mock_inspect.active.return_value = {"worker1": []}
                mock_celery.control.inspect.return_value = mock_inspect
                
                response = client.get("/ready")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["ready"] is True
        assert data["components"]["database"] is True
        assert data["components"]["redis"] is True
        assert data["components"]["celery_workers"] is True
    
    @patch('redis.from_url')
    def test_readiness_with_celery_no_workers(self, mock_redis):
        """Test readiness endpoint when Celery is enabled but no workers are active."""
        # Mock Redis as healthy
        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True
        mock_redis.return_value = mock_redis_client
        
        # Mock Celery as enabled but no active workers
        with patch('app.config.settings.ENABLE_CELERY', True):
            with patch('app.services.celery_tasks.celery_app') as mock_celery:
                mock_inspect = MagicMock()
                mock_inspect.active.return_value = {}  # No active workers
                mock_celery.control.inspect.return_value = mock_inspect
                
                response = client.get("/ready")
        
        assert response.status_code == 503
        
        data = response.json()["detail"]
        assert data["ready"] is False
        assert data["components"]["database"] is True
        assert data["components"]["redis"] is True
        assert data["components"]["celery_workers"] is False
    
    def test_readiness_no_redis_url(self):
        """Test readiness endpoint when no Redis URL is configured."""
        with patch('app.config.settings.REDIS_URL', None):
            with patch('app.config.settings.ENABLE_CELERY', False):
                response = client.get("/ready")
        
        # Should still return 200 but Redis will be False
        data = response.json() if response.status_code == 200 else response.json()["detail"]
        assert data["components"]["database"] is True
        assert data["components"]["redis"] is False


class TestWorkerHeartbeat:
    """Test worker heartbeat endpoint."""
    
    def test_worker_heartbeat_celery_disabled(self):
        """Test worker heartbeat when Celery is disabled."""
        with patch('app.config.settings.ENABLE_CELERY', False):
            response = client.get("/internal/worker/heartbeat")
        
        assert response.status_code == 404
        assert "Celery not enabled" in response.json()["detail"]
    
    def test_worker_heartbeat_celery_enabled_healthy(self):
        """Test worker heartbeat when Celery is enabled and healthy."""
        with patch('app.config.settings.ENABLE_CELERY', True):
            with patch('app.services.celery_tasks.celery_app') as mock_celery:
                mock_inspect = MagicMock()
                mock_celery.control.inspect.return_value = mock_inspect
                
                response = client.get("/internal/worker/heartbeat")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "otto-worker"
        assert "timestamp" in data
    
    def test_worker_heartbeat_celery_enabled_unhealthy(self):
        """Test worker heartbeat when Celery is enabled but unhealthy."""
        with patch('app.config.settings.ENABLE_CELERY', True):
            with patch('app.services.celery_tasks.celery_app') as mock_celery:
                mock_celery.control.inspect.side_effect = Exception("Worker not responding")
                
                response = client.get("/internal/worker/heartbeat")
        
        assert response.status_code == 503
        
        data = response.json()["detail"]
        assert data["status"] == "unhealthy"
        assert data["service"] == "otto-worker"
        assert "Worker not responding" in data["error"]


class TestReadinessIntegration:
    """Integration tests for readiness endpoint."""
    
    def test_readiness_response_structure(self):
        """Test that readiness endpoint returns proper structure."""
        response = client.get("/ready")
        
        # Should return either 200 or 503
        assert response.status_code in [200, 503]
        
        # Extract data from response
        if response.status_code == 200:
            data = response.json()
        else:
            data = response.json()["detail"]
        
        # Verify required fields
        required_fields = ["ready", "timestamp", "duration_ms", "components", "service"]
        for field in required_fields:
            assert field in data
        
        # Verify components structure
        components = data["components"]
        assert "database" in components
        assert "redis" in components
        assert "celery_workers" in components
        
        # Verify data types
        assert isinstance(data["ready"], bool)
        assert isinstance(data["timestamp"], (int, float))
        assert isinstance(data["duration_ms"], (int, float))
        assert isinstance(components["database"], bool)
        assert isinstance(components["redis"], bool)
        assert components["celery_workers"] in [True, False, None]


if __name__ == "__main__":
    pytest.main([__file__])
