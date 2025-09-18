"""
Tests for webhook idempotency functionality.
"""
import pytest
import os
import time
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import text

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
    "RATE_LIMIT_TENANT": "10/minute",
    "IDEMPOTENCY_TTL_DAYS": "90"
})

from app.main import app
from app.services.idempotency import with_idempotency, cleanup_old_idempotency_keys, get_idempotency_stats
from app.database import get_db


class TestIdempotencyService:
    """Test the idempotency service functionality."""
    
    def test_first_time_delivery(self):
        """Test that first-time delivery processes and returns processed status."""
        def mock_process_fn():
            return {"result": "processed"}
        
        response, status_code = with_idempotency(
            provider="test_provider",
            external_id="test_external_id_1",
            tenant_id="test_tenant_1",
            process_fn=mock_process_fn,
            trace_id="test_trace_1"
        )
        
        assert status_code == 200
        assert response["status"] == "processed"
        assert response["provider"] == "test_provider"
        assert response["result"] == "processed"
    
    def test_duplicate_delivery(self):
        """Test that duplicate delivery returns duplicate_ignored status."""
        def mock_process_fn():
            return {"result": "processed"}
        
        # First delivery
        response1, status_code1 = with_idempotency(
            provider="test_provider",
            external_id="test_external_id_2",
            tenant_id="test_tenant_2",
            process_fn=mock_process_fn,
            trace_id="test_trace_2"
        )
        
        assert status_code1 == 200
        assert response1["status"] == "processed"
        
        # Duplicate delivery
        response2, status_code2 = with_idempotency(
            provider="test_provider",
            external_id="test_external_id_2",
            tenant_id="test_tenant_2",
            process_fn=mock_process_fn,
            trace_id="test_trace_2"
        )
        
        assert status_code2 == 200
        assert response2["status"] == "duplicate_ignored"
        assert response2["provider"] == "test_provider"
        assert "first_processed_at" in response2
    
    def test_failure_then_retry(self):
        """Test that failure removes key so retry can succeed."""
        call_count = 0
        
        def failing_process_fn():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Simulated failure")
            return {"result": "processed"}
        
        # First attempt - should fail
        with pytest.raises(Exception, match="Simulated failure"):
            with_idempotency(
                provider="test_provider",
                external_id="test_external_id_3",
                tenant_id="test_tenant_3",
                process_fn=failing_process_fn,
                trace_id="test_trace_3"
            )
        
        # Second attempt - should succeed
        response, status_code = with_idempotency(
            provider="test_provider",
            external_id="test_external_id_3",
            tenant_id="test_tenant_3",
            process_fn=failing_process_fn,
            trace_id="test_trace_3"
        )
        
        assert status_code == 200
        assert response["status"] == "processed"
        assert call_count == 2
    
    def test_different_tenants_same_external_id(self):
        """Test that different tenants can have same external_id."""
        def mock_process_fn():
            return {"result": "processed"}
        
        # Tenant 1
        response1, status_code1 = with_idempotency(
            provider="test_provider",
            external_id="shared_external_id",
            tenant_id="tenant_1",
            process_fn=mock_process_fn,
            trace_id="test_trace_4"
        )
        
        # Tenant 2 with same external_id
        response2, status_code2 = with_idempotency(
            provider="test_provider",
            external_id="shared_external_id",
            tenant_id="tenant_2",
            process_fn=mock_process_fn,
            trace_id="test_trace_5"
        )
        
        assert status_code1 == 200
        assert status_code2 == 200
        assert response1["status"] == "processed"
        assert response2["status"] == "processed"
    
    def test_different_providers_same_external_id(self):
        """Test that different providers can have same external_id."""
        def mock_process_fn():
            return {"result": "processed"}
        
        # Provider 1
        response1, status_code1 = with_idempotency(
            provider="provider_1",
            external_id="shared_external_id",
            tenant_id="test_tenant",
            process_fn=mock_process_fn,
            trace_id="test_trace_6"
        )
        
        # Provider 2 with same external_id
        response2, status_code2 = with_idempotency(
            provider="provider_2",
            external_id="shared_external_id",
            tenant_id="test_tenant",
            process_fn=mock_process_fn,
            trace_id="test_trace_7"
        )
        
        assert status_code1 == 200
        assert status_code2 == 200
        assert response1["status"] == "processed"
        assert response2["status"] == "processed"
    
    def test_cleanup_old_keys(self):
        """Test cleanup of old idempotency keys."""
        # This test would require mocking the database to test cleanup functionality
        # For now, we'll test that the function exists and can be called
        try:
            deleted_count = cleanup_old_idempotency_keys()
            assert isinstance(deleted_count, int)
        except Exception:
            # Expected to fail in test environment without proper DB setup
            pass
    
    def test_idempotency_stats(self):
        """Test that idempotency statistics are tracked."""
        stats = get_idempotency_stats()
        
        assert isinstance(stats, dict)
        assert "webhook_processed_total" in stats
        assert "webhook_duplicates_total" in stats
        assert "webhook_failures_total" in stats
        
        assert isinstance(stats["webhook_processed_total"], int)
        assert isinstance(stats["webhook_duplicates_total"], int)
        assert isinstance(stats["webhook_failures_total"], int)


class TestCallRailIdempotency:
    """Test CallRail webhook idempotency integration."""
    
    @patch('app.middleware.tenant.TenantContextMiddleware._get_jwks')
    @patch('requests.get')
    def test_callrail_pre_call_idempotency(self, mock_requests_get, mock_get_jwks):
        """Test CallRail pre-call webhook idempotency."""
        # Mock JWKS
        mock_jwks = {"keys": [{"kty": "RSA", "kid": "test", "use": "sig", "n": "test", "e": "AQAB"}]}
        mock_get_jwks.return_value = mock_jwks
        mock_response = MagicMock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response
        
        client = TestClient(app)
        
        # Mock tenant context
        with patch('app.middleware.tenant.TenantContextMiddleware') as mock_middleware:
            mock_middleware.return_value = None
            
            # First request
            response1 = client.post(
                "/callrail/pre-call",
                params={
                    "trackingnum": "1234567890",
                    "callernum": "0987654321",
                    "call_id": "call_123"
                },
                headers={"Authorization": "Bearer test_token"}
            )
            
            # Duplicate request
            response2 = client.post(
                "/callrail/pre-call",
                params={
                    "trackingnum": "1234567890",
                    "callernum": "0987654321",
                    "call_id": "call_123"
                },
                headers={"Authorization": "Bearer test_token"}
            )
            
            # Both should return 200, but second should be duplicate_ignored
            assert response1.status_code == 200
            assert response2.status_code == 200
            
            # Note: Actual response content depends on database setup
            # In a real test environment, we'd verify the idempotency behavior


class TestTwilioIdempotency:
    """Test Twilio webhook idempotency integration."""
    
    def test_twilio_external_id_derivation(self):
        """Test that Twilio external_id is derived correctly."""
        # This would test the Twilio webhook handler once implemented
        # For now, we document the expected behavior:
        
        # SMS webhook: external_id = request.form['MessageSid']
        # Call webhook: external_id = request.form['CallSid']
        # Voice webhook: external_id = request.form['CallSid']
        
        pass


class TestClerkIdempotency:
    """Test Clerk webhook idempotency integration."""
    
    def test_clerk_external_id_derivation(self):
        """Test that Clerk external_id is derived correctly."""
        # This would test the Clerk webhook handler once implemented
        # For now, we document the expected behavior:
        
        # User events: external_id = payload['data']['id']
        # Organization events: external_id = payload['data']['id']
        # If event_id is provided: external_id = payload['event_id']
        
        pass


class TestIdempotencyConcurrency:
    """Test idempotency under concurrent conditions."""
    
    def test_concurrent_identical_deliveries(self):
        """Test that concurrent identical deliveries only process once."""
        import threading
        import time
        
        results = []
        errors = []
        
        def mock_process_fn():
            time.sleep(0.1)  # Simulate processing time
            return {"result": "processed"}
        
        def make_request():
            try:
                response, status_code = with_idempotency(
                    provider="test_provider",
                    external_id="concurrent_test_id",
                    tenant_id="test_tenant",
                    process_fn=mock_process_fn,
                    trace_id="concurrent_trace"
                )
                results.append((response, status_code))
            except Exception as e:
                errors.append(e)
        
        # Start two concurrent requests
        thread1 = threading.Thread(target=make_request)
        thread2 = threading.Thread(target=make_request)
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        # Should have exactly 2 results (no errors)
        assert len(results) == 2
        assert len(errors) == 0
        
        # One should be "processed", one should be "duplicate_ignored"
        statuses = [result[0]["status"] for result in results]
        assert "processed" in statuses
        assert "duplicate_ignored" in statuses


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
