"""
Tests for rate limiting functionality.
"""
import pytest
import time
import os
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import redis
import json

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
    "ALLOWED_ORIGINS": "http://localhost:3000,https://test.example.com",
    "REDIS_URL": "redis://localhost:6379/1",  # Use different DB for tests
    "RATE_LIMIT_USER": "5/minute",  # Lower limits for testing
    "RATE_LIMIT_TENANT": "10/minute"
})

from app.main import app
from app.config import settings
from app.middleware.rate_limiter import RateLimiter, create_rate_limit_response


class TestRateLimiter:
    """Test the RateLimiter class."""
    
    def test_parse_limit(self):
        """Test limit string parsing."""
        limiter = RateLimiter()
        
        # Test valid limits
        assert limiter._parse_limit("60/minute") == (60, 60)
        assert limiter._parse_limit("100/hour") == (100, 3600)
        assert limiter._parse_limit("10/second") == (10, 1)
        
        # Test invalid limits
        assert limiter._parse_limit("invalid") == (60, 60)  # Default fallback
    
    def test_redis_key_generation(self):
        """Test Redis key generation."""
        limiter = RateLimiter()
        
        user_key = limiter._get_redis_key("user", "tenant:123:user:456")
        assert user_key == "rate_limit:user:tenant:123:user:456"
        
        tenant_key = limiter._get_redis_key("tenant", "tenant:123")
        assert tenant_key == "rate_limit:tenant:tenant:123"
    
    @patch('redis.from_url')
    def test_redis_connection_failure(self, mock_redis):
        """Test fallback when Redis connection fails."""
        mock_redis.side_effect = Exception("Connection failed")
        
        limiter = RateLimiter()
        assert limiter.redis_client is None
        
        # Should not raise exception
        allowed, retry_after = limiter.check_user_limit("tenant123", "user456")
        assert allowed is True
        assert retry_after == 0


class TestRateLimitResponse:
    """Test rate limit response creation."""
    
    def test_create_rate_limit_response(self):
        """Test rate limit response format."""
        response = create_rate_limit_response(30, "test-trace-123")
        
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "30"
        assert response.headers["X-Trace-Id"] == "test-trace-123"
        
        content = response.body.decode()
        data = json.loads(content)
        
        assert data["type"] == "https://tools.ietf.org/html/rfc6585#section-4"
        assert data["title"] == "Too Many Requests"
        assert data["detail"] == "Rate limit exceeded. Please try again later."
        assert data["retry_after"] == 30
        assert data["trace_id"] == "test-trace-123"


class TestRateLimitMiddleware:
    """Test rate limiting middleware integration."""
    
    def create_test_jwt(self, org_id: str = "org_test123", user_id: str = "user_test123") -> str:
        """Create a test JWT token."""
        import jwt
        payload = {
            "sub": user_id,
            "org_id": org_id,
            "exp": 9999999999,
            "iat": 1000000000
        }
        return jwt.encode(payload, "test_secret", algorithm="HS256")
    
    @patch('app.middleware.tenant.TenantContextMiddleware._get_jwks')
    @patch('requests.get')
    @patch('redis.from_url')
    def test_per_user_rate_limit(self, mock_redis, mock_requests_get, mock_get_jwks):
        """Test per-user rate limiting."""
        # Mock Redis
        mock_redis_client = MagicMock()
        mock_redis.return_value = mock_redis_client
        mock_redis_client.ping.return_value = True
        
        # Mock JWKS
        mock_jwks = {"keys": [{"kty": "RSA", "kid": "test", "use": "sig", "n": "test", "e": "AQAB"}]}
        mock_get_jwks.return_value = mock_jwks
        mock_response = MagicMock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response
        
        # Mock Redis operations for rate limiting
        mock_redis_client.pipeline.return_value.__enter__.return_value.execute.return_value = [0, 5, 0, 0]  # 5 requests already made
        
        client = TestClient(app)
        token = self.create_test_jwt("org_test123", "user_test123")
        
        # Make requests up to the limit
        for i in range(5):
            response = client.get(
                "/user/company",
                headers={"Authorization": f"Bearer {token}"}
            )
            # Should succeed for first 5 requests
            assert response.status_code != 429
        
        # 6th request should be rate limited
        response = client.get(
            "/user/company",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers
    
    @patch('app.middleware.tenant.TenantContextMiddleware._get_jwks')
    @patch('requests.get')
    @patch('redis.from_url')
    def test_per_tenant_rate_limit(self, mock_redis, mock_requests_get, mock_get_jwks):
        """Test per-tenant rate limiting with multiple users."""
        # Mock Redis
        mock_redis_client = MagicMock()
        mock_redis.return_value = mock_redis_client
        mock_redis_client.ping.return_value = True
        
        # Mock JWKS
        mock_jwks = {"keys": [{"kty": "RSA", "kid": "test", "use": "sig", "n": "test", "e": "AQAB"}]}
        mock_get_jwks.return_value = mock_jwks
        mock_response = MagicMock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response
        
        # Mock Redis operations - tenant limit exceeded
        mock_redis_client.pipeline.return_value.__enter__.return_value.execute.return_value = [0, 10, 0, 0]  # 10 requests already made
        
        client = TestClient(app)
        
        # Create tokens for different users in same tenant
        token1 = self.create_test_jwt("org_test123", "user_test123")
        token2 = self.create_test_jwt("org_test123", "user_test456")
        
        # First user makes requests
        for i in range(5):
            response = client.get(
                "/user/company",
                headers={"Authorization": f"Bearer {token1}"}
            )
            assert response.status_code != 429
        
        # Second user makes requests - should hit tenant limit
        response = client.get(
            "/user/company",
            headers={"Authorization": f"Bearer {token2}"}
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers
    
    def test_exempt_routes(self):
        """Test that exempt routes bypass rate limiting."""
        client = TestClient(app)
        
        # Health endpoint should not be rate limited
        response = client.get("/health")
        assert response.status_code == 200
        
        # Docs endpoint should not be rate limited
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_missing_tenant_context(self):
        """Test that requests without tenant context are not rate limited."""
        client = TestClient(app)
        
        # Request without auth should not be rate limited (but will fail auth)
        response = client.get("/user/company")
        # Should fail with 403 (auth), not 429 (rate limit)
        assert response.status_code == 403
        assert "tenant_id" in response.json()["detail"]


class TestRateLimitDecorator:
    """Test the @limits decorator."""
    
    def create_test_jwt(self, org_id: str = "org_test123", user_id: str = "user_test123") -> str:
        """Create a test JWT token."""
        import jwt
        payload = {
            "sub": user_id,
            "org_id": org_id,
            "exp": 9999999999,
            "iat": 1000000000
        }
        return jwt.encode(payload, "test_secret", algorithm="HS256")
    
    @patch('app.middleware.tenant.TenantContextMiddleware._get_jwks')
    @patch('requests.get')
    @patch('redis.from_url')
    def test_custom_rate_limits(self, mock_redis, mock_requests_get, mock_get_jwks):
        """Test custom rate limits via decorator."""
        # Mock Redis
        mock_redis_client = MagicMock()
        mock_redis.return_value = mock_redis_client
        mock_redis_client.ping.return_value = True
        
        # Mock JWKS
        mock_jwks = {"keys": [{"kty": "RSA", "kid": "test", "use": "sig", "n": "test", "e": "AQAB"}]}
        mock_get_jwks.return_value = mock_jwks
        mock_response = MagicMock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response
        
        # Mock Redis operations - custom limit exceeded
        mock_redis_client.pipeline.return_value.__enter__.return_value.execute.return_value = [0, 30, 0, 0]  # 30 requests already made
        
        client = TestClient(app)
        token = self.create_test_jwt("org_test123", "user_test123")
        
        # Test CallRail endpoint with custom limit (30/minute)
        response = client.post(
                "/callrail/pre-call",
                headers={"Authorization": f"Bearer {token}"},
                params={"trackingnum": "1234567890", "callernum": "0987654321"}
            )
        assert response.status_code == 429
        assert "Retry-After" in response.headers


class TestRateLimitIntegration:
    """Integration tests for rate limiting."""
    
    @patch('redis.from_url')
    def test_redis_integration(self, mock_redis):
        """Test integration with Redis."""
        # Create a real Redis mock that behaves like Redis
        mock_redis_client = MagicMock()
        mock_redis.return_value = mock_redis_client
        mock_redis_client.ping.return_value = True
        
        # Mock Redis sorted set operations
        mock_redis_client.pipeline.return_value.__enter__.return_value.execute.return_value = [0, 0, 0, 0]  # No existing requests
        
        limiter = RateLimiter()
        
        # Test user limit
        allowed, retry_after = limiter.check_user_limit("tenant123", "user456", "2/minute")
        assert allowed is True
        assert retry_after == 0
        
        # Test tenant limit
        allowed, retry_after = limiter.check_tenant_limit("tenant123", "5/minute")
        assert allowed is True
        assert retry_after == 0
    
    def test_environment_configuration(self):
        """Test that rate limits are loaded from environment."""
        assert settings.RATE_LIMIT_USER == "5/minute"
        assert settings.RATE_LIMIT_TENANT == "10/minute"
        assert settings.REDIS_URL == "redis://localhost:6379/1"
    
    @patch('app.middleware.tenant.TenantContextMiddleware._get_jwks')
    @patch('requests.get')
    @patch('redis.from_url')
    def test_rate_limit_retry_after_header(self, mock_redis, mock_requests_get, mock_get_jwks):
        """Test that rate limit responses include proper Retry-After header."""
        # Mock Redis
        mock_redis_client = MagicMock()
        mock_redis.return_value = mock_redis_client
        mock_redis_client.ping.return_value = True
        
        # Mock JWKS
        mock_jwks = {"keys": [{"kty": "RSA", "kid": "test", "use": "sig", "n": "test", "e": "AQAB"}]}
        mock_get_jwks.return_value = mock_jwks
        mock_response = MagicMock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response
        
        # Mock Redis operations - rate limit exceeded with specific retry time
        mock_redis_client.pipeline.return_value.__enter__.return_value.execute.return_value = [0, 5, 30, 0]  # 30 seconds retry
        
        client = TestClient(app)
        token = self.create_test_jwt("org_test123", "user_test123")
        
        response = client.get(
            "/user/company",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 429
        assert "Retry-After" in response.headers
        assert response.headers["Retry-After"] == "30"
        
        # Check response body format
        data = response.json()
        assert data["type"] == "https://tools.ietf.org/html/rfc6585#section-4"
        assert data["title"] == "Too Many Requests"
        assert data["retry_after"] == 30
    
    @patch('app.middleware.tenant.TenantContextMiddleware._get_jwks')
    @patch('requests.get')
    @patch('redis.from_url')
    def test_multiple_users_tenant_limit_saturation(self, mock_redis, mock_requests_get, mock_get_jwks):
        """Test that multiple users in same tenant can saturate tenant bucket."""
        # Mock Redis
        mock_redis_client = MagicMock()
        mock_redis.return_value = mock_redis_client
        mock_redis_client.ping.return_value = True
        
        # Mock JWKS
        mock_jwks = {"keys": [{"kty": "RSA", "kid": "test", "use": "sig", "n": "test", "e": "AQAB"}]}
        mock_get_jwks.return_value = mock_jwks
        mock_response = MagicMock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response
        
        client = TestClient(app)
        
        # Create tokens for two users in same tenant
        token_a = self.create_test_jwt("org_test123", "user_a")
        token_b = self.create_test_jwt("org_test123", "user_b")
        
        # Mock Redis to simulate tenant bucket saturation
        # User A makes 6 requests, User B makes 6 requests = 12 total (exceeds 10/minute tenant limit)
        mock_redis_client.pipeline.return_value.__enter__.return_value.execute.return_value = [0, 10, 0, 0]  # Tenant limit exceeded
        
        # User A should be rate limited due to tenant saturation
        response_a = client.get(
            "/user/company",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert response_a.status_code == 429
        
        # User B should also be rate limited due to tenant saturation
        response_b = client.get(
            "/user/company",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        assert response_b.status_code == 429
    
    def test_exempt_routes_comprehensive(self):
        """Test that all exempt routes bypass rate limiting."""
        client = TestClient(app)
        
        exempt_routes = [
            "/health",
            "/ready", 
            "/metrics",
            "/docs",
            "/openapi.json",
            "/redoc"
        ]
        
        for route in exempt_routes:
            response = client.get(route)
            # Should not be rate limited (may return other status codes, but not 429)
            assert response.status_code != 429, f"Route {route} was rate limited"
    
    @patch('redis.from_url')
    def test_redis_degradation_graceful(self, mock_redis):
        """Test that rate limiting degrades gracefully when Redis is unavailable."""
        # Mock Redis connection failure
        mock_redis.side_effect = Exception("Redis connection failed")
        
        limiter = RateLimiter()
        
        # Should not raise exception and should allow requests
        allowed, retry_after = limiter.check_user_limit("tenant123", "user456")
        assert allowed is True
        assert retry_after == 0
        
        allowed, retry_after = limiter.check_tenant_limit("tenant123")
        assert allowed is True
        assert retry_after == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
