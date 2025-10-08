"""
Unified Workflow Composer (UWC) client for OttoAI backend.
Handles all API calls to UWC with proper headers, retry logic, and error handling.
"""
import logging
import time
import hmac
import hashlib
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
import httpx
from app.config import settings
from app.obs.logging import get_logger
from app.obs.metrics import metrics

logger = get_logger(__name__)


class UWCClientError(Exception):
    """Base exception for UWC client errors."""
    pass


class UWCAuthenticationError(UWCClientError):
    """Authentication error with UWC API."""
    pass


class UWCRateLimitError(UWCClientError):
    """Rate limit exceeded error."""
    pass


class UWCServerError(UWCClientError):
    """Server error from UWC API."""
    pass


class UWCClient:
    """
    Client for interacting with the Unified Workflow Composer (UWC) API.
    
    Features:
    - Automatic retry with exponential backoff
    - Request/response logging
    - HMAC signature generation
    - Latency and error metrics
    - x-request-id propagation
    """
    
    def __init__(self):
        self.base_url = settings.UWC_BASE_URL
        self.api_key = settings.UWC_API_KEY
        self.hmac_secret = settings.UWC_HMAC_SECRET
        self.version = settings.UWC_VERSION
        self.use_staging = settings.USE_UWC_STAGING
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds
        self.retry_multiplier = 2.0
        self.timeout = 30.0  # seconds
        
        # Validate configuration
        if not self.base_url:
            raise ValueError("UWC_BASE_URL must be configured")
        if not self.api_key:
            raise ValueError("UWC_API_KEY must be configured")
        
        logger.info(
            f"UWC Client initialized: base_url={self.base_url}, "
            f"version={self.version}, staging={self.use_staging}"
        )
    
    def _generate_signature(self, payload: dict, timestamp: str) -> str:
        """
        Generate HMAC-SHA256 signature for request authentication.
        
        Args:
            payload: Request payload dictionary
            timestamp: ISO 8601 timestamp string
        
        Returns:
            Hex-encoded HMAC signature
        """
        if not self.hmac_secret:
            logger.warning("UWC_HMAC_SECRET not configured, skipping signature generation")
            return ""
        
        message = f"{timestamp}:{json.dumps(payload, sort_keys=True)}"
        signature = hmac.new(
            self.hmac_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _get_headers(
        self,
        company_id: str,
        request_id: str,
        payload: Optional[dict] = None
    ) -> Dict[str, str]:
        """
        Generate request headers for UWC API calls.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID for request tracing
            payload: Optional request payload for signature generation
        
        Returns:
            Dictionary of HTTP headers
        """
        timestamp = datetime.utcnow().isoformat() + "Z"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Company-ID": company_id,
            "X-Request-ID": request_id,
            "X-UWC-Version": self.version,
            "Content-Type": "application/json",
            "X-UWC-Timestamp": timestamp,
        }
        
        # Add HMAC signature if payload provided
        if payload and self.hmac_secret:
            signature = self._generate_signature(payload, timestamp)
            headers["X-Signature"] = signature
        
        return headers
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        company_id: str,
        request_id: str,
        payload: Optional[dict] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Make HTTP request to UWC API with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            company_id: Tenant/company ID
            request_id: Correlation ID
            payload: Optional request payload
            retry_count: Current retry attempt number
        
        Returns:
            Response JSON as dictionary
        
        Raises:
            UWCAuthenticationError: For 401/403 errors
            UWCRateLimitError: For 429 errors
            UWCServerError: For 5xx errors
            UWCClientError: For other errors
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(company_id, request_id, payload)
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(
                    f"UWC API request: {method} {endpoint} "
                    f"(company_id={company_id}, request_id={request_id}, retry={retry_count})"
                )
                
                if method == "GET":
                    response = await client.get(url, headers=headers)
                elif method == "POST":
                    response = await client.post(url, headers=headers, json=payload)
                elif method == "PUT":
                    response = await client.put(url, headers=headers, json=payload)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                latency_ms = (time.time() - start_time) * 1000
                
                # Record metrics
                metrics.record_uwc_request(
                    endpoint=endpoint,
                    method=method,
                    status_code=response.status_code,
                    latency_ms=latency_ms
                )
                
                # Handle response
                if response.status_code == 200:
                    logger.info(
                        f"UWC API success: {method} {endpoint} "
                        f"(status={response.status_code}, latency={latency_ms:.2f}ms)"
                    )
                    return response.json()
                
                elif response.status_code in [401, 403]:
                    logger.error(
                        f"UWC API authentication error: {method} {endpoint} "
                        f"(status={response.status_code}, response={response.text})"
                    )
                    raise UWCAuthenticationError(
                        f"Authentication failed: {response.status_code} - {response.text}"
                    )
                
                elif response.status_code == 429:
                    logger.warning(
                        f"UWC API rate limit exceeded: {method} {endpoint} "
                        f"(retry={retry_count}/{self.max_retries})"
                    )
                    if retry_count < self.max_retries:
                        return await self._retry_request(
                            method, endpoint, company_id, request_id, payload, retry_count
                        )
                    raise UWCRateLimitError("Rate limit exceeded after max retries")
                
                elif response.status_code >= 500:
                    logger.error(
                        f"UWC API server error: {method} {endpoint} "
                        f"(status={response.status_code}, response={response.text}, "
                        f"retry={retry_count}/{self.max_retries})"
                    )
                    if retry_count < self.max_retries:
                        return await self._retry_request(
                            method, endpoint, company_id, request_id, payload, retry_count
                        )
                    raise UWCServerError(
                        f"Server error: {response.status_code} - {response.text}"
                    )
                
                else:
                    logger.error(
                        f"UWC API error: {method} {endpoint} "
                        f"(status={response.status_code}, response={response.text})"
                    )
                    raise UWCClientError(
                        f"Request failed: {response.status_code} - {response.text}"
                    )
        
        except httpx.TimeoutException as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                f"UWC API timeout: {method} {endpoint} "
                f"(timeout={self.timeout}s, latency={latency_ms:.2f}ms, "
                f"retry={retry_count}/{self.max_retries})"
            )
            metrics.record_uwc_request(
                endpoint=endpoint,
                method=method,
                status_code=0,
                latency_ms=latency_ms
            )
            if retry_count < self.max_retries:
                return await self._retry_request(
                    method, endpoint, company_id, request_id, payload, retry_count
                )
            raise UWCClientError(f"Request timeout after {self.timeout}s")
        
        except (UWCClientError, UWCAuthenticationError, UWCRateLimitError, UWCServerError):
            # Re-raise our own exceptions without wrapping
            raise
        
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.exception(
                f"UWC API unexpected error: {method} {endpoint} "
                f"(error={str(e)}, latency={latency_ms:.2f}ms)"
            )
            metrics.record_uwc_request(
                endpoint=endpoint,
                method=method,
                status_code=0,
                latency_ms=latency_ms
            )
            raise UWCClientError(f"Unexpected error: {str(e)}")
    
    async def _retry_request(
        self,
        method: str,
        endpoint: str,
        company_id: str,
        request_id: str,
        payload: Optional[dict],
        retry_count: int
    ) -> Dict[str, Any]:
        """Retry request with exponential backoff."""
        retry_count += 1
        delay = self.retry_delay * (self.retry_multiplier ** (retry_count - 1))
        
        logger.info(
            f"Retrying UWC API request in {delay:.2f}s "
            f"(retry={retry_count}/{self.max_retries})"
        )
        
        time.sleep(delay)
        
        return await self._make_request(
            method, endpoint, company_id, request_id, payload, retry_count
        )
    
    # ASR Batch Processing
    async def submit_asr_batch(
        self,
        company_id: str,
        request_id: str,
        audio_urls: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Submit batch ASR processing request.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            audio_urls: List of audio URLs with metadata
            options: Optional ASR options (language, punctuation, etc.)
        
        Returns:
            ASR batch response with job_id and status
        """
        payload = {
            "request_id": request_id,
            "company_id": company_id,
            "audio_urls": audio_urls,
            "options": options or {
                "language": "en-US",
                "punctuation": True,
                "speaker_diarization": True
            }
        }
        
        return await self._make_request(
            "POST",
            "/uwc/v1/asr/batch",
            company_id,
            request_id,
            payload
        )
    
    # RAG Query
    async def query_rag(
        self,
        company_id: str,
        request_id: str,
        query: str,
        context: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query RAG system for contextual information.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            query: Natural language query
            context: Context dict with tenant_id, rep_id, meeting_id
            options: Optional RAG options (max_results, similarity_threshold, etc.)
        
        Returns:
            RAG query response with results and metadata
        """
        payload = {
            "request_id": request_id,
            "company_id": company_id,
            "query": query,
            "context": context,
            "options": options or {
                "max_results": 10,
                "similarity_threshold": 0.7,
                "include_metadata": True
            }
        }
        
        return await self._make_request(
            "POST",
            "/uwc/v1/rag/query",
            company_id,
            request_id,
            payload
        )
    
    # Document Indexing
    async def index_documents(
        self,
        company_id: str,
        request_id: str,
        documents: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Index documents for RAG system.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            documents: List of documents with content and metadata
            options: Optional indexing options (chunk_size, overlap, etc.)
        
        Returns:
            Document indexing response with job_id and status
        """
        payload = {
            "request_id": request_id,
            "company_id": company_id,
            "documents": documents,
            "options": options or {
                "chunk_size": 1000,
                "overlap": 200,
                "embedding_model": "text-embedding-ada-002"
            }
        }
        
        return await self._make_request(
            "POST",
            "/uwc/v1/documents/index",
            company_id,
            request_id,
            payload
        )
    
    # Training Job Submission
    async def submit_training_job(
        self,
        company_id: str,
        request_id: str,
        training_data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Submit training job for personal clone model.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            training_data: Training data with media_urls and transcripts
            options: Optional training options (model_type, epochs, etc.)
        
        Returns:
            Training job response with job_id and status
        """
        payload = {
            "request_id": request_id,
            "company_id": company_id,
            "training_data": training_data,
            "options": options or {
                "model_type": "personal_clone",
                "training_epochs": 10,
                "learning_rate": 0.001
            }
        }
        
        return await self._make_request(
            "POST",
            "/uwc/v1/training/submit",
            company_id,
            request_id,
            payload
        )


# Singleton instance
_uwc_client: Optional[UWCClient] = None


def get_uwc_client() -> UWCClient:
    """Get or create UWC client singleton instance."""
    global _uwc_client
    if _uwc_client is None:
        _uwc_client = UWCClient()
    return _uwc_client

