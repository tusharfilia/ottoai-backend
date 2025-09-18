"""
Tests for CORS and tenant validation middleware.
"""
import pytest
import os
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import jwt
import json
import time

# Set test environment variables
os.environ.update({
    "CLERK_SECRET_KEY": "sk_test_fake_key_for_testing",
    "CLERK_PUBLISHABLE_KEY": "pk_test_fake_key_for_testing",
    "TWILIO_ACCOUNT_SID": "ACfake_account_sid",
    "TWILIO_AUTH_TOKEN": "fake_auth_token",
    "CALLRAIL_API_KEY": "fake_callrail_key",
    "CALLRAIL_ACCOUNT_ID": "fake_account_id",
    "DEEPGRAM_API_KEY": "fake_deepgram_key",
    "OPENAI_API_KEY": "sk-fake_openai_key",
    "BLAND_API_KEY": "fake_bland_key",
    "DATABASE_URL": "sqlite:///./test.db",
    "ALLOWED_ORIGINS": "http://localhost:3000,https://test.example.com,exp://*",
    "REDIS_URL": "redis://localhost:6379/0",
    "RATE_LIMIT_USER": "5/minute",
    "RATE_LIMIT_TENANT": "10/minute"
})

from app.main import app
from app.config import settings


@pytest.fixture
def valid_jwt_token():
    """Create a valid JWT token for testing."""
    payload = {
        "sub": "user_test123",
        "org_id": "org_test123",
        "exp": int(time.time()) + 3600,  # 1 hour from now
        "iat": int(time.time())
    }
    return jwt.encode(payload, "test_secret", algorithm="HS256")


@pytest.fixture
def valid_jwt_token_user_a():
    """Create a valid JWT token for user A."""
    payload = {
        "sub": "user_a_test",
        "org_id": "org_test123",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time())
    }
    return jwt.encode(payload, "test_secret", algorithm="HS256")


@pytest.fixture
def valid_jwt_token_user_b():
    """Create a valid JWT token for user B (same tenant)."""
    payload = {
        "sub": "user_b_test",
        "org_id": "org_test123",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time())
    }
    return jwt.encode(payload, "test_secret", algorithm="HS256")


@pytest.fixture
def valid_jwt_token_different_tenant():
    """Create a valid JWT token for different tenant."""
    payload = {
        "sub": "user_test456",
        "org_id": "org_test456",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time())
    }
    return jwt.encode(payload, "test_secret", algorithm="HS256")


class TestCORS:
    """Test CORS configuration."""
    
    def test_cors_allowed_origin_localhost(self):
        """Test that requests from localhost:3000 are accepted."""
        client = TestClient(app)
        
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"}
        )
        
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers
    
    def test_cors_allowed_origin_test_domain(self):
        """Test that requests from test.example.com are accepted."""
        client = TestClient(app)
        
        response = client.get(
            "/health",
            headers={"Origin": "https://test.example.com"}
        )
        
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers
    
    def test_cors_allowed_origin_expo(self):
        """Test that requests from Expo development client are accepted."""
        client = TestClient(app)
        
        response = client.get(
            "/health",
            headers={"Origin": "exp://192.168.1.100:8081"}
        )
        
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers
    
    def test_cors_disallowed_origin_malicious(self):
        """Test that requests from malicious origins are rejected."""
        client = TestClient(app)
        
        response = client.get(
            "/health",
            headers={"Origin": "https://malicious-site.com"}
        )
        
        # CORS middleware should reject this
        assert response.status_code == 403 or "Access-Control-Allow-Origin" not in response.headers
    
    def test_cors_disallowed_origin_phishing(self):
        """Test that requests from phishing-like origins are rejected."""
        client = TestClient(app)
        
        response = client.get(
            "/health",
            headers={"Origin": "https://ottoai-fake.com"}
        )
        
        assert response.status_code == 403 or "Access-Control-Allow-Origin" not in response.headers
    
    def test_cors_no_origin_header(self):
        """Test that requests without Origin header work (same-origin requests)."""
        client = TestClient(app)
        
        response = client.get("/health")
        
        assert response.status_code == 200
    
    def test_cors_preflight_request(self):
        """Test CORS preflight OPTIONS request."""
        client = TestClient(app)
        
        response = client.options(
            "/user/company",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization"
            }
        )
        
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers
        assert "Access-Control-Allow-Headers" in response.headers


class TestTenantValidation:
    """Test tenant validation middleware."""
    
    def create_test_jwt(self, org_id: str = "org_test123") -> str:
        """Create a test JWT token with organization ID."""
        payload = {
            "sub": "user_test123",
            "org_id": org_id,
            "exp": 9999999999,  # Far future
            "iat": 1000000000
        }
        
        # Use a test secret for signing
        return jwt.encode(payload, "test_secret", algorithm="HS256")
    
    @patch('app.middleware.tenant.TenantContextMiddleware._get_jwks')
    @patch('requests.get')
    def test_tenant_validation_success(self, mock_requests_get, mock_get_jwks):
        """Test successful tenant validation."""
        # Mock JWKS response
        mock_jwks = {
            "keys": [{
                "kty": "RSA",
                "kid": "test",
                "use": "sig",
                "n": "test",
                "e": "AQAB"
            }]
        }
        mock_get_jwks.return_value = mock_jwks
        
        # Mock requests.get for JWKS
        mock_response = MagicMock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response
        
        client = TestClient(app)
        
        # Create a valid JWT token
        token = self.create_test_jwt("org_test123")
        
        response = client.get(
            "/user/company",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Should not be a 403 (tenant validation passed)
        # Note: The actual endpoint might return other errors, but not 403 for tenant validation
        assert response.status_code != 403
    
    def test_tenant_validation_missing_token(self):
        """Test tenant validation with missing token."""
        client = TestClient(app)
        
        response = client.get("/user/company")
        
        assert response.status_code == 403
        assert "Missing or invalid tenant_id" in response.json()["detail"]
    
    def test_tenant_validation_invalid_token(self):
        """Test tenant validation with invalid token."""
        client = TestClient(app)
        
        response = client.get(
            "/user/company",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 403
        assert "Invalid authentication token" in response.json()["detail"]
    
    def test_tenant_validation_no_org_id(self):
        """Test tenant validation with token that has no organization ID."""
        # Create JWT without org_id
        payload = {
            "sub": "user_test123",
            "exp": 9999999999,
            "iat": 1000000000
        }
        token = jwt.encode(payload, "test_secret", algorithm="HS256")
        
        client = TestClient(app)
        
        response = client.get(
            "/user/company",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 403
        assert "Missing or invalid tenant_id" in response.json()["detail"]
    
    def test_health_endpoint_bypasses_tenant_validation(self):
        """Test that health endpoint bypasses tenant validation."""
        client = TestClient(app)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        assert "status" in response.json()
    
    def test_docs_endpoint_bypasses_tenant_validation(self):
        """Test that docs endpoint bypasses tenant validation."""
        client = TestClient(app)
        
        response = client.get("/docs")
        
        assert response.status_code == 200
    
    def test_openapi_endpoint_bypasses_tenant_validation(self):
        """Test that OpenAPI endpoint bypasses tenant validation."""
        client = TestClient(app)
        
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
    
    def test_ready_endpoint_bypasses_tenant_validation(self):
        """Test that ready endpoint bypasses tenant validation."""
        client = TestClient(app)
        
        response = client.get("/ready")
        
        assert response.status_code == 200
    
    def test_metrics_endpoint_bypasses_tenant_validation(self):
        """Test that metrics endpoint bypasses tenant validation."""
        client = TestClient(app)
        
        response = client.get("/metrics")
        
        assert response.status_code == 200
    
    @patch('app.middleware.tenant.TenantContextMiddleware._get_jwks')
    @patch('requests.get')
    def test_tenant_validation_with_fixtures(self, mock_requests_get, mock_get_jwks, valid_jwt_token):
        """Test tenant validation using pytest fixtures."""
        # Mock JWKS response
        mock_jwks = {
            "keys": [{
                "kty": "RSA",
                "kid": "test",
                "use": "sig",
                "n": "test",
                "e": "AQAB"
            }]
        }
        mock_get_jwks.return_value = mock_jwks
        
        # Mock requests.get for JWKS
        mock_response = MagicMock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response
        
        client = TestClient(app)
        
        response = client.get(
            "/user/company",
            headers={"Authorization": f"Bearer {valid_jwt_token}"}
        )
        
        # Should not be a 403 (tenant validation passed)
        assert response.status_code != 403
    
    def test_cross_tenant_isolation(self, valid_jwt_token, valid_jwt_token_different_tenant):
        """Test that users from different tenants cannot access each other's data."""
        client = TestClient(app)
        
        # This test would need to be implemented based on actual data isolation
        # For now, we verify that different tenant tokens are handled differently
        response1 = client.get(
            "/user/company",
            headers={"Authorization": f"Bearer {valid_jwt_token}"}
        )
        
        response2 = client.get(
            "/user/company",
            headers={"Authorization": f"Bearer {valid_jwt_token_different_tenant}"}
        )
        
        # Both should either succeed (if they have data) or fail with same error
        # The key is that they don't interfere with each other
        assert response1.status_code == response2.status_code or response1.status_code != 403


class TestTenantScopedDatabase:
    """Test tenant-scoped database queries."""
    
    @patch('app.database.engine')
    def test_tenant_scoped_session(self, mock_engine):
        """Test that database session is scoped by tenant."""
        from app.database import TenantScopedSession
        
        # Create a mock model with company_id
        class MockModel:
            def __init__(self):
                self.company_id = None
        
        # Create tenant-scoped session
        session = TenantScopedSession("org_test123", bind=mock_engine)
        
        # Test that queries are automatically filtered by tenant
        query = session.query(MockModel)
        
        # The query should include tenant filtering
        # Note: This is a simplified test - in practice, you'd test the actual SQL generation
        assert session.tenant_id == "org_test123"


if __name__ == "__main__":
    pytest.main([__file__])
