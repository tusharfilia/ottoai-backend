"""
Tests for I001: UWC typed client + retry/backoff + headers.
Tests x-request-id propagation and basic metrics (latency, errors).
"""
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.uwc_client import (
    UWCClient,
    UWCClientError,
    UWCAuthenticationError,
    UWCRateLimitError,
    UWCServerError,
    get_uwc_client
)
from app.config import settings
import time


@pytest.fixture
def uwc_client():
    """Create UWC client instance for testing."""
    with patch.object(settings, 'UWC_BASE_URL', 'https://uwc-test.example.com'):
        with patch.object(settings, 'UWC_API_KEY', 'test_api_key'):
            with patch.object(settings, 'UWC_HMAC_SECRET', 'test_hmac_secret'):
                with patch.object(settings, 'UWC_VERSION', 'v1'):
                    with patch.object(settings, 'USE_UWC_STAGING', True):
                        client = UWCClient()
                        yield client


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient for testing."""
    with patch('httpx.AsyncClient') as mock:
        yield mock


class TestUWCClientInitialization:
    """Test UWC client initialization and configuration."""
    
    def test_client_initializes_with_config(self, uwc_client):
        """Test that client initializes with proper configuration."""
        assert uwc_client.base_url == 'https://uwc-test.example.com'
        assert uwc_client.api_key == 'test_api_key'
        assert uwc_client.hmac_secret == 'test_hmac_secret'
        assert uwc_client.version == 'v1'
        assert uwc_client.use_staging is True
    
    def test_client_requires_base_url(self):
        """Test that client requires UWC_BASE_URL to be configured."""
        with patch.object(settings, 'UWC_BASE_URL', ''):
            with pytest.raises(ValueError, match="UWC_BASE_URL must be configured"):
                UWCClient()
    
    def test_client_requires_api_key(self):
        """Test that client requires UWC_API_KEY to be configured."""
        with patch.object(settings, 'UWC_BASE_URL', 'https://uwc-test.example.com'):
            with patch.object(settings, 'UWC_API_KEY', ''):
                with pytest.raises(ValueError, match="UWC_API_KEY must be configured"):
                    UWCClient()
    
    def test_singleton_instance(self):
        """Test that get_uwc_client returns singleton instance."""
        with patch.object(settings, 'UWC_BASE_URL', 'https://uwc-test.example.com'):
            with patch.object(settings, 'UWC_API_KEY', 'test_api_key'):
                client1 = get_uwc_client()
                client2 = get_uwc_client()
                assert client1 is client2


class TestUWCClientHeaders:
    """Test UWC client header generation."""
    
    def test_headers_include_required_fields(self, uwc_client):
        """Test that headers include all required fields."""
        headers = uwc_client._get_headers(
            company_id="test_company",
            request_id="test_request_123"
        )
        
        assert headers["Authorization"] == "Bearer test_api_key"
        assert headers["X-Company-ID"] == "test_company"
        assert headers["X-Request-ID"] == "test_request_123"
        assert headers["X-UWC-Version"] == "v1"
        assert headers["Content-Type"] == "application/json"
        assert "X-UWC-Timestamp" in headers
    
    def test_headers_include_hmac_signature(self, uwc_client):
        """Test that headers include HMAC signature when payload provided."""
        payload = {"test": "data"}
        headers = uwc_client._get_headers(
            company_id="test_company",
            request_id="test_request_123",
            payload=payload
        )
        
        assert "X-Signature" in headers
        assert len(headers["X-Signature"]) == 64  # SHA256 hex digest length
    
    def test_signature_generation(self, uwc_client):
        """Test HMAC signature generation."""
        payload = {"test": "data"}
        timestamp = "2025-01-01T00:00:00Z"
        
        signature = uwc_client._generate_signature(payload, timestamp)
        
        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 hex digest length
        
        # Same payload and timestamp should generate same signature
        signature2 = uwc_client._generate_signature(payload, timestamp)
        assert signature == signature2


class TestUWCClientRetryLogic:
    """Test UWC client retry and backoff logic."""
    
    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self, uwc_client, mock_httpx_client):
        """Test that client retries on 429 rate limit errors."""
        # Mock response sequence: 429, 429, 200
        mock_responses = [
            MagicMock(status_code=429, text="Rate limit exceeded"),
            MagicMock(status_code=429, text="Rate limit exceeded"),
            MagicMock(status_code=200, json=lambda: {"status": "success"})
        ]
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.side_effect = mock_responses
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = await uwc_client._make_request(
                "POST",
                "/test",
                "company_123",
                "request_123",
                {"data": "test"}
            )
        
        assert result == {"status": "success"}
        assert mock_client_instance.post.call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_on_server_error(self, uwc_client, mock_httpx_client):
        """Test that client retries on 5xx server errors."""
        mock_responses = [
            MagicMock(status_code=500, text="Internal server error"),
            MagicMock(status_code=200, json=lambda: {"status": "success"})
        ]
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.side_effect = mock_responses
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        
        with patch('time.sleep'):
            result = await uwc_client._make_request(
                "POST",
                "/test",
                "company_123",
                "request_123",
                {"data": "test"}
            )
        
        assert result == {"status": "success"}
        assert mock_client_instance.post.call_count == 2
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, uwc_client, mock_httpx_client):
        """Test that client raises error after max retries."""
        mock_response = MagicMock(status_code=500, text="Internal server error")
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        
        with patch('time.sleep'):
            with pytest.raises(UWCServerError):
                await uwc_client._make_request(
                    "POST",
                    "/test",
                    "company_123",
                    "request_123",
                    {"data": "test"}
                )
        
        # Should have tried max_retries + 1 times (initial + retries)
        assert mock_client_instance.post.call_count == uwc_client.max_retries + 1
    
    @pytest.mark.asyncio
    async def test_no_retry_on_auth_error(self, uwc_client, mock_httpx_client):
        """Test that client doesn't retry on authentication errors."""
        mock_response = MagicMock(status_code=401, text="Unauthorized")
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        
        with pytest.raises(UWCAuthenticationError):
            await uwc_client._make_request(
                "POST",
                "/test",
                "company_123",
                "request_123",
                {"data": "test"}
            )
        
        # Should only try once
        assert mock_client_instance.post.call_count == 1


class TestUWCClientMetrics:
    """Test UWC client metrics recording."""
    
    @pytest.mark.asyncio
    async def test_metrics_recorded_on_success(self, uwc_client, mock_httpx_client):
        """Test that metrics are recorded on successful requests."""
        mock_response = MagicMock(status_code=200, json=lambda: {"status": "success"})
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        
        with patch('app.obs.metrics.metrics.record_uwc_request') as mock_metrics:
            await uwc_client._make_request(
                "POST",
                "/test",
                "company_123",
                "request_123",
                {"data": "test"}
            )
            
            mock_metrics.assert_called_once()
            call_args = mock_metrics.call_args[1]
            assert call_args["endpoint"] == "/test"
            assert call_args["method"] == "POST"
            assert call_args["status_code"] == 200
            assert "latency_ms" in call_args
    
    @pytest.mark.asyncio
    async def test_metrics_recorded_on_error(self, uwc_client, mock_httpx_client):
        """Test that metrics are recorded on error responses."""
        mock_response = MagicMock(status_code=500, text="Internal server error")
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        
        with patch('app.obs.metrics.metrics.record_uwc_request') as mock_metrics:
            with patch('time.sleep'):
                with pytest.raises(UWCServerError):
                    await uwc_client._make_request(
                        "POST",
                        "/test",
                        "company_123",
                        "request_123",
                        {"data": "test"}
                    )
            
            # Should record metrics for each attempt
            assert mock_metrics.call_count == uwc_client.max_retries + 1


class TestUWCClientAPIMethods:
    """Test UWC client API method implementations."""
    
    @pytest.mark.asyncio
    async def test_submit_asr_batch(self, uwc_client):
        """Test ASR batch submission."""
        with patch.object(uwc_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"job_id": "job_123", "status": "processing"}
            
            result = await uwc_client.submit_asr_batch(
                company_id="company_123",
                request_id="request_123",
                audio_urls=[{"url": "https://example.com/audio.mp3", "call_id": "call_123"}]
            )
            
            assert result["job_id"] == "job_123"
            mock_request.assert_called_once()
            call_args = mock_request.call_args[0]
            assert call_args[0] == "POST"
            assert call_args[1] == "/uwc/v1/asr/batch"
    
    @pytest.mark.asyncio
    async def test_query_rag(self, uwc_client):
        """Test RAG query."""
        with patch.object(uwc_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"results": [{"content": "test result"}]}
            
            result = await uwc_client.query_rag(
                company_id="company_123",
                request_id="request_123",
                query="What is the status?",
                context={"tenant_id": "tenant_123"}
            )
            
            assert "results" in result
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_index_documents(self, uwc_client):
        """Test document indexing."""
        with patch.object(uwc_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"job_id": "job_456", "status": "processing"}
            
            result = await uwc_client.index_documents(
                company_id="company_123",
                request_id="request_123",
                documents=[{"document_id": "doc_123", "content": "test content"}]
            )
            
            assert result["job_id"] == "job_456"
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_submit_training_job(self, uwc_client):
        """Test training job submission."""
        with patch.object(uwc_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"job_id": "job_789", "status": "queued"}
            
            result = await uwc_client.submit_training_job(
                company_id="company_123",
                request_id="request_123",
                training_data={"media_urls": []}
            )
            
            assert result["job_id"] == "job_789"
            mock_request.assert_called_once()


class TestUWCClientErrorHandling:
    """Test UWC client error handling."""
    
    @pytest.mark.asyncio
    async def test_timeout_error(self, uwc_client, mock_httpx_client):
        """Test handling of timeout errors."""
        mock_client_instance = AsyncMock()
        mock_client_instance.post.side_effect = httpx.TimeoutException("Request timeout")
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        
        with patch('time.sleep'):
            with pytest.raises(UWCClientError, match="Request timeout"):
                await uwc_client._make_request(
                    "POST",
                    "/test",
                    "company_123",
                    "request_123",
                    {"data": "test"}
                )
    
    @pytest.mark.asyncio
    async def test_network_error(self, uwc_client, mock_httpx_client):
        """Test handling of network errors."""
        mock_client_instance = AsyncMock()
        mock_client_instance.post.side_effect = httpx.NetworkError("Network unreachable")
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        
        with pytest.raises(UWCClientError, match="Unexpected error"):
            await uwc_client._make_request(
                "POST",
                "/test",
                "company_123",
                "request_123",
                {"data": "test"}
            )
    
    @pytest.mark.asyncio
    async def test_invalid_json_response(self, uwc_client, mock_httpx_client):
        """Test handling of invalid JSON responses."""
        mock_response = MagicMock(status_code=200)
        mock_response.json.side_effect = ValueError("Invalid JSON")
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        
        with pytest.raises(UWCClientError):
            await uwc_client._make_request(
                "POST",
                "/test",
                "company_123",
                "request_123",
                {"data": "test"}
            )


class TestAskOttoCanonical:
    """Test canonical Ask Otto endpoint and payload format."""
    
    @pytest.mark.asyncio
    async def test_query_ask_otto_canonical_payload(self, uwc_client):
        """Test query_ask_otto builds canonical payload correctly and sets X-Target-Role."""
        with patch.object(uwc_client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "success": True,
                "query_id": "query_123",
                "question": "test question",
                "answer": "test answer",
                "confidence": 0.85,
                "sources": [
                    {"reference": "ref_1", "title": "Source 1", "confidence": 0.9}
                ]
            }
            
            result = await uwc_client.query_ask_otto(
                company_id="company_123",
                request_id="request_123",
                question="test question",
                context={"tenant_id": "company_123", "user_role": "csr"},
                target_role="customer_rep"
            )
            
            assert result["answer"] == "test answer"
            assert result["query_id"] == "query_123"
            mock_request.assert_called_once()
            
            # Verify canonical endpoint is used
            call_args = mock_request.call_args
            assert call_args[0][1] == "/api/v1/ask-otto/query"  # endpoint
            
            # Verify canonical payload format
            payload = call_args[0][4]  # payload is 5th positional arg
            assert payload["question"] == "test question"
            assert "context" in payload
            assert payload["context"]["user_role"] == "csr"
            
            # Verify target_role is passed
            assert call_args[1]["target_role"] == "customer_rep"
    
    def test_map_otto_role_to_shunya_target_role(self, uwc_client):
        """Test role mapping from Otto roles to Shunya target roles."""
        assert uwc_client._map_otto_role_to_shunya_target_role("csr") == "customer_rep"
        assert uwc_client._map_otto_role_to_shunya_target_role("sales_rep") == "sales_rep"
        assert uwc_client._map_otto_role_to_shunya_target_role("rep") == "sales_rep"  # Alias
        assert uwc_client._map_otto_role_to_shunya_target_role("manager") == "sales_manager"
        assert uwc_client._map_otto_role_to_shunya_target_role("exec") == "admin"
        assert uwc_client._map_otto_role_to_shunya_target_role("executive") == "admin"  # Alias
        assert uwc_client._map_otto_role_to_shunya_target_role("unknown") == "sales_rep"  # Default
    
    def test_get_headers_with_target_role(self, uwc_client):
        """Test that _get_headers includes X-Target-Role when provided."""
        headers = uwc_client._get_headers(
            company_id="test_company",
            request_id="test_request_123",
            target_role="customer_rep"
        )
        
        assert "X-Target-Role" in headers
        assert headers["X-Target-Role"] == "customer_rep"
    
    def test_get_headers_without_target_role(self, uwc_client):
        """Test that _get_headers doesn't include X-Target-Role when not provided."""
        headers = uwc_client._get_headers(
            company_id="test_company",
            request_id="test_request_123"
        )
        
        assert "X-Target-Role" not in headers

