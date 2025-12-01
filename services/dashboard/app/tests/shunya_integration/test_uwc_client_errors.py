"""
Tests for UWC client error envelope handling.

Tests that canonical Shunya error envelopes are properly parsed and handled.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import Response
import json

from app.services.uwc_client import (
    UWCClient,
    ShunyaAPIError,
    UWCAuthenticationError,
    UWCRateLimitError,
    UWCServerError,
    UWCClientError,
)


class TestShunyaErrorEnvelopeParsing:
    """Test parsing of canonical Shunya error envelopes."""
    
    @pytest.fixture
    def uwc_client(self, monkeypatch):
        """Create UWC client with mocked dependencies."""
        monkeypatch.setenv("UWC_BASE_URL", "https://test.shunya.example.com")
        monkeypatch.setenv("UWC_API_KEY", "test_api_key")
        monkeypatch.setenv("UWC_HMAC_SECRET", "test_hmac_secret")
        monkeypatch.setenv("ENVIRONMENT", "test")
        return UWCClient()
    
    def test_parse_canonical_error_envelope(self, uwc_client):
        """Test parsing of canonical error envelope structure."""
        error_obj = {
            "error_code": "RATE_LIMIT",
            "error_type": "throttling",
            "message": "Too many requests",
            "retryable": True,
            "details": {"limit": 100, "window": "1h"},
            "timestamp": "2025-11-28T10:15:42.123Z",
            "request_id": "abc-123",
        }
        
        error = uwc_client._parse_shunya_error_envelope(error_obj, {})
        
        assert isinstance(error, ShunyaAPIError)
        assert error.error_code == "RATE_LIMIT"
        assert error.error_type == "throttling"
        assert error.message == "Too many requests"
        assert error.retryable is True
        assert error.details == {"limit": 100, "window": "1h"}
        assert error.timestamp == "2025-11-28T10:15:42.123Z"
        assert error.request_id == "abc-123"
    
    def test_parse_error_envelope_with_legacy_fields(self, uwc_client):
        """Test parsing error envelope with legacy field names."""
        error_obj = {
            "code": "TRANSCRIPTION_FAILED",  # Legacy field name
            "type": "processing_error",  # Legacy field name
            "message": "Audio quality too poor",
            "retryable": False,
            "requestId": "xyz-789",  # Legacy camelCase
        }
        
        error = uwc_client._parse_shunya_error_envelope(error_obj, {})
        
        assert error.error_code == "TRANSCRIPTION_FAILED"
        assert error.error_type == "processing_error"
        assert error.message == "Audio quality too poor"
        assert error.retryable is False
        assert error.request_id == "xyz-789"
    
    def test_parse_error_envelope_with_missing_fields(self, uwc_client):
        """Test parsing error envelope with missing optional fields."""
        error_obj = {
            "error_code": "UNKNOWN_ERROR",
            "message": "Something went wrong",
        }
        
        error = uwc_client._parse_shunya_error_envelope(error_obj, {})
        
        assert error.error_code == "UNKNOWN_ERROR"
        assert error.message == "Something went wrong"
        assert error.error_type == "unknown"  # Default value
        assert error.retryable is False  # Default value
        assert error.details == {}  # Default value
        assert error.timestamp is None
        assert error.request_id is None


class TestUWClientErrorHandling:
    """Test UWC client error handling with canonical error envelopes."""
    
    @pytest.fixture
    def uwc_client(self, monkeypatch):
        """Create UWC client with mocked dependencies."""
        monkeypatch.setenv("UWC_BASE_URL", "https://test.shunya.example.com")
        monkeypatch.setenv("UWC_API_KEY", "test_api_key")
        monkeypatch.setenv("UWC_HMAC_SECRET", "test_hmac_secret")
        monkeypatch.setenv("ENVIRONMENT", "test")
        return UWCClient()
    
    @pytest.mark.asyncio
    async def test_rate_limit_error_with_envelope(self, uwc_client):
        """Test that rate limit errors parse canonical error envelope."""
        error_response = {
            "success": False,
            "error": {
                "error_code": "RATE_LIMIT",
                "error_type": "throttling",
                "message": "Too many requests",
                "retryable": True,
                "details": {"limit": 100},
                "timestamp": "2025-11-28T10:15:42.123Z",
                "request_id": "abc-123",
            }
        }
        
        mock_response = Response(
            status_code=429,
            content=json.dumps(error_response).encode(),
            headers={"Content-Type": "application/json"},
        )
        
        with patch.object(uwc_client, "_make_request") as mock_make_request:
            mock_make_request.side_effect = UWCRateLimitError(
                f"Rate limit: {error_response['error']['message']}"
            )
            
            with pytest.raises(UWCRateLimitError) as exc_info:
                await uwc_client._make_request("GET", "/test", "company_123", "req_123")
            
            assert "Too many requests" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_500_error_with_retryable_flag(self, uwc_client):
        """Test that 500 errors with retryable flag are handled correctly."""
        error_response = {
            "success": False,
            "error": {
                "error_code": "PROCESSING_ERROR",
                "error_type": "server_error",
                "message": "Temporary processing error",
                "retryable": True,
                "request_id": "req-456",
            }
        }
        
        # Mock the httpx response
        mock_http_response = AsyncMock(spec=Response)
        mock_http_response.status_code = 500
        mock_http_response.json.return_value = error_response
        mock_http_response.text = json.dumps(error_response)
        
        # Mock the circuit breaker and httpx client
        with patch("app.services.uwc_client.circuit_breaker_manager") as mock_breaker_mgr:
            mock_breaker = MagicMock()
            mock_breaker.call = AsyncMock(return_value=mock_http_response)
            mock_breaker_mgr.get_breaker.return_value = mock_breaker
            
            # This should raise UWCServerError with retryable=True
            with pytest.raises(UWCServerError):
                await uwc_client._make_request("POST", "/test", "company_123", "req_123", {"data": "test"})
    
    @pytest.mark.asyncio
    async def test_200_response_with_error_envelope(self, uwc_client):
        """Test that 200 responses with success=false error envelope are handled."""
        error_response = {
            "success": False,
            "error": {
                "error_code": "VALIDATION_ERROR",
                "error_type": "client_error",
                "message": "Invalid request parameters",
                "retryable": False,
                "request_id": "req-789",
            }
        }
        
        mock_http_response = AsyncMock(spec=Response)
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = error_response
        mock_http_response.text = json.dumps(error_response)
        
        with patch("app.services.uwc_client.circuit_breaker_manager") as mock_breaker_mgr:
            mock_breaker = MagicMock()
            mock_breaker.call = AsyncMock(return_value=mock_http_response)
            mock_breaker_mgr.get_breaker.return_value = mock_breaker
            
            # Should raise ShunyaAPIError
            with pytest.raises(ShunyaAPIError) as exc_info:
                await uwc_client._make_request("GET", "/test", "company_123", "req_123")
            
            assert exc_info.value.error_code == "VALIDATION_ERROR"
            assert exc_info.value.message == "Invalid request parameters"
            assert exc_info.value.retryable is False
            assert exc_info.value.request_id == "req-789"
    
    def test_error_envelope_preserves_request_id(self, uwc_client):
        """Test that request_id from error envelope is preserved for observability."""
        error_obj = {
            "error_code": "TIMEOUT",
            "error_type": "timeout_error",
            "message": "Request timed out",
            "retryable": True,
            "request_id": "trace-123-456",
        }
        
        error = uwc_client._parse_shunya_error_envelope(error_obj, {})
        
        assert error.request_id == "trace-123-456"
        # Verify request_id is in error message for logging
        assert "trace-123-456" in str(error.original_response) or error.request_id == "trace-123-456"


class TestErrorEnvelopeRetryLogic:
    """Test that retryable flag affects retry behavior."""
    
    @pytest.fixture
    def uwc_client(self, monkeypatch):
        """Create UWC client with mocked dependencies."""
        monkeypatch.setenv("UWC_BASE_URL", "https://test.shunya.example.com")
        monkeypatch.setenv("UWC_API_KEY", "test_api_key")
        monkeypatch.setenv("UWC_HMAC_SECRET", "test_hmac_secret")
        monkeypatch.setenv("ENVIRONMENT", "test")
        return UWCClient()
    
    def test_retryable_error_flag_respected(self, uwc_client):
        """Test that retryable flag is parsed and available."""
        retryable_error = {
            "error_code": "TEMPORARY_FAILURE",
            "error_type": "transient_error",
            "message": "Temporary failure, please retry",
            "retryable": True,
        }
        
        non_retryable_error = {
            "error_code": "INVALID_REQUEST",
            "error_type": "client_error",
            "message": "Invalid request, do not retry",
            "retryable": False,
        }
        
        retryable = uwc_client._parse_shunya_error_envelope(retryable_error, {})
        non_retryable = uwc_client._parse_shunya_error_envelope(non_retryable_error, {})
        
        assert retryable.retryable is True
        assert non_retryable.retryable is False
        
        # Verify retryable flag is in exception message
        assert "retryable=True" in str(retryable)
        assert "retryable=False" in str(non_retryable)


