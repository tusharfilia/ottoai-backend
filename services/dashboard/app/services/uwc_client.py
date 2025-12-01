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
import jwt
from app.config import settings
from app.obs.logging import get_logger
from app.obs.metrics import metrics
from app.services.circuit_breaker import circuit_breaker_manager

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


class ShunyaAPIError(UWCClientError):
    """
    Structured exception for Shunya API canonical error envelope.
    
    Aligned with final Shunya contract:
    {
        "success": false,
        "error": {
            "error_code": "string",
            "error_type": "string",
            "message": "string",
            "retryable": true,
            "details": {},
            "timestamp": "2025-11-28T10:15:42.123Z",
            "request_id": "uuid"
        }
    }
    """
    def __init__(
        self,
        error_code: str,
        error_type: str,
        message: str,
        retryable: bool = False,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
        request_id: Optional[str] = None,
        original_response: Optional[Dict[str, Any]] = None,
    ):
        self.error_code = error_code
        self.error_type = error_type
        self.message = message
        self.retryable = retryable
        self.details = details or {}
        self.timestamp = timestamp
        self.request_id = request_id
        self.original_response = original_response
        
        # Use message as the exception message
        super().__init__(f"[{error_code}] {message} (retryable={retryable})")


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
        self.api_key = settings.UWC_API_KEY  # legacy; prefer JWT
        self.jwt_secret = settings.UWC_JWT_SECRET
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
            logger.warning("UWC_BASE_URL not configured - UWC features will be disabled")
            self.base_url = None
        if not self.api_key:
            logger.warning("UWC_API_KEY not configured - UWC features will be disabled")
            self.api_key = None
        
        # HTTPS validation for production
        if self.base_url and not self.base_url.startswith("https://"):
            env = settings.ENVIRONMENT.lower() if hasattr(settings, "ENVIRONMENT") else "unknown"
            if env == "production":
                logger.error(
                    f"UWC_BASE_URL must use HTTPS in production, got: {self.base_url}. "
                    "This is a security risk!"
                )
            else:
                logger.warning(
                    f"UWC_BASE_URL should use HTTPS, got: {self.base_url}. "
                    "This is insecure and should not be used in production."
                )
        
        logger.info(
            f"UWC Client initialized: base_url={self.base_url}, "
            f"version={self.version}, staging={self.use_staging}"
        )
    
    def is_available(self) -> bool:
        """Check if UWC is properly configured and available."""
        return self.base_url is not None and self.api_key is not None
    
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
    
    def _generate_jwt(self, company_id: str) -> str:
        """Generate short-lived HS256 JWT for UWC per OpenAPI (HTTP Bearer)."""
        if not self.jwt_secret:
            logger.warning("UWC_JWT_SECRET not configured; falling back to API key if present")
            return ""
        iat = int(time.time())
        exp = iat + 60 * 5  # 5 minutes TTL
        claims = {
            "company_id": company_id,
            "iat": iat,
            "exp": exp,
            "iss": "otto-backend",
            "aud": "uwc"
        }
        token = jwt.encode(claims, self.jwt_secret, algorithm="HS256")
        # PyJWT returns str in v2+
        return token

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
        bearer = self._generate_jwt(company_id)
        auth_header = f"Bearer {bearer}" if bearer else (f"Bearer {self.api_key}" if self.api_key else "")
        headers = {
            "Authorization": auth_header,
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
        # Check if UWC is available
        if not self.is_available():
            logger.warning(f"UWC not available - skipping {method} {endpoint}")
            raise UWCClientError("UWC is not configured or available")
        
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(company_id, request_id, payload)
        # Idempotency for mutating requests
        if method in ("POST", "PUT", "DELETE"):
            headers.setdefault("Idempotency-Key", request_id)
        
        start_time = time.time()
        
        async def _do_http():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(
                    f"UWC API request: {method} {endpoint} "
                    f"(company_id={company_id}, request_id={request_id}, retry={retry_count})"
                )
                if method == "GET":
                    return await client.get(url, headers=headers)
                elif method == "POST":
                    return await client.post(url, headers=headers, json=payload)
                elif method == "PUT":
                    return await client.put(url, headers=headers, json=payload)
                elif method == "DELETE":
                    return await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

        breaker = circuit_breaker_manager.get_breaker(
            name=f"uwc:{endpoint}", tenant_id=company_id, failure_threshold=5, recovery_timeout=30, expected_exception=Exception
        )

        try:
            response = await breaker.call(_do_http)
            
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
                response_data = response.json()
                
                # Check if response indicates failure (canonical error envelope)
                if isinstance(response_data, dict) and response_data.get("success") is False:
                    error_obj = response_data.get("error") or {}
                    raise self._parse_shunya_error_envelope(error_obj, response_data)
                
                return response_data
            
            # Try to parse canonical error envelope for all error status codes
            try:
                response_data = response.json()
                if isinstance(response_data, dict) and response_data.get("success") is False:
                    error_obj = response_data.get("error") or {}
                    shunya_error = self._parse_shunya_error_envelope(error_obj, response_data)
                    
                    # Map error to appropriate exception type based on status code
                    if response.status_code in [401, 403]:
                        logger.error(
                            f"UWC API authentication error: {method} {endpoint} "
                            f"(status={response.status_code}, error_code={shunya_error.error_code}, "
                            f"retryable={shunya_error.retryable}, request_id={shunya_error.request_id})"
                        )
                        raise UWCAuthenticationError(str(shunya_error)) from shunya_error
                    elif response.status_code == 429:
                        logger.warning(
                            f"UWC API rate limit exceeded: {method} {endpoint} "
                            f"(retry={retry_count}/{self.max_retries}, request_id={shunya_error.request_id})"
                        )
                        if retry_count < self.max_retries and shunya_error.retryable:
                            return await self._retry_request(
                                method, endpoint, company_id, request_id, payload, retry_count
                            )
                        raise UWCRateLimitError(str(shunya_error)) from shunya_error
                    elif response.status_code >= 500:
                        logger.error(
                            f"UWC API server error: {method} {endpoint} "
                            f"(status={response.status_code}, error_code={shunya_error.error_code}, "
                            f"retryable={shunya_error.retryable}, retry={retry_count}/{self.max_retries}, "
                            f"request_id={shunya_error.request_id})"
                        )
                        if retry_count < self.max_retries and shunya_error.retryable:
                            return await self._retry_request(
                                method, endpoint, company_id, request_id, payload, retry_count
                            )
                        raise UWCServerError(str(shunya_error)) from shunya_error
                    else:
                        # Other 4xx errors - check if retryable
                        logger.error(
                            f"UWC API error: {method} {endpoint} "
                            f"(status={response.status_code}, error_code={shunya_error.error_code}, "
                            f"retryable={shunya_error.retryable}, request_id={shunya_error.request_id})"
                        )
                        if retry_count < self.max_retries and shunya_error.retryable:
                            return await self._retry_request(
                                method, endpoint, company_id, request_id, payload, retry_count
                            )
                        raise shunya_error
            except (json.JSONDecodeError, KeyError, ValueError):
                # Fallback to original error handling if error envelope parsing fails
                pass
            
            # Fallback error handling (if error envelope parsing failed)
            if response.status_code in [401, 403]:
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
        
        except (UWCClientError, UWCAuthenticationError, UWCRateLimitError, UWCServerError, ShunyaAPIError):
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
    
    def _parse_shunya_error_envelope(
        self,
        error_obj: Dict[str, Any],
        full_response: Optional[Dict[str, Any]] = None
    ) -> ShunyaAPIError:
        """
        Parse Shunya canonical error envelope into ShunyaAPIError exception.
        
        Expected format:
        {
            "success": false,
            "error": {
                "error_code": "string",
                "error_type": "string",
                "message": "string",
                "retryable": true,
                "details": {},
                "timestamp": "2025-11-28T10:15:42.123Z",
                "request_id": "uuid"
            }
        }
        
        Args:
            error_obj: Error object from response["error"]
            full_response: Full response dictionary (for debugging)
        
        Returns:
            ShunyaAPIError exception with parsed fields
        """
        error_code = error_obj.get("error_code") or error_obj.get("code") or "UNKNOWN_ERROR"
        error_type = error_obj.get("error_type") or error_obj.get("type") or "unknown"
        message = error_obj.get("message") or "Unknown error"
        retryable = error_obj.get("retryable", False)
        details = error_obj.get("details") or {}
        timestamp = error_obj.get("timestamp")
        request_id = error_obj.get("request_id") or error_obj.get("requestId")
        
        return ShunyaAPIError(
            error_code=str(error_code),
            error_type=str(error_type),
            message=str(message),
            retryable=bool(retryable),
            details=details if isinstance(details, dict) else {},
            timestamp=timestamp,
            request_id=request_id,
            original_response=full_response,
        )
    
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
    
    # ASR Single Transcription (per OpenAPI)
    async def transcribe_audio(
        self,
        company_id: str,
        request_id: str,
        audio_url: str,
        language: str = "en-US",
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe a single audio file using UWC ASR (compatible with Shunya mock API).
        
        Returns a job/task ID that can be used for status polling.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            audio_url: Publicly accessible audio URL
            language: Language code (default: en-US)
            model: Optional ASR model identifier
        
        Returns:
            Transcription response with task_id/job_id/transcript_id for async tracking
            Response format: {"success": True, "task_id": "...", "transcript_id": ..., "message": "..."}
        """
        payload = {
            "call_id": 0,  # Will be set by caller if known
            "audio_url": audio_url,
            "call_type": "csr_call",  # Default, caller can override
        }
        if language:
            payload["language"] = language
        if model:
            payload["model"] = model
        
        # OpenAPI path: /api/v1/transcription/transcribe
        response = await self._make_request(
            "POST",
            "/api/v1/transcription/transcribe",
            company_id,
            request_id,
            payload
        )
        
        # Extract job ID from response (may be task_id, transcript_id, or job_id)
        # Return response as-is - job ID extraction handled by caller
        return response

    async def get_transcription_status(
        self,
        company_id: str,
        request_id: str,
        call_id: int,
    ) -> Dict[str, Any]:
        return await self._make_request(
            "GET",
            f"/api/v1/transcription/status/{call_id}",
            company_id,
            request_id,
        )

    async def get_transcript(
        self,
        company_id: str,
        request_id: str,
        call_id: int,
    ) -> Dict[str, Any]:
        return await self._make_request(
            "GET",
            f"/api/v1/transcription/transcript/{call_id}",
            company_id,
            request_id,
        )
    
    # RAG Query (per OpenAPI /api/v1/search/)
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
            "query": query,
            "document_types": options.get("document_types") if options else None,
            "limit": (options or {}).get("limit", 10),
            "score_threshold": (options or {}).get("score_threshold", 0),
            "filters": (options or {}).get("filters"),
        }
        return await self._make_request(
            "POST",
            "/api/v1/search/",
            company_id,
            request_id,
            payload
        )
    
    # Document Indexing (legacy - kept for backward compatibility)
    async def index_documents(
        self,
        company_id: str,
        request_id: str,
        documents: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Index documents for RAG system (legacy method).
        Use ingest_document() for new implementations.
        
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
    
    # Document Ingestion to UWC (per OpenAPI /api/v1/ingestion/documents/upload)
    async def ingest_document(
        self,
        company_id: str,
        request_id: str,
        file_url: str,
        document_type: str,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingest a document to UWC for processing.
        Call this after uploading file to S3.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            file_url: S3 URL or public URL of the document
            document_type: Type of document (sop, training, reference)
            filename: Original filename
            metadata: Optional document metadata
        
        Returns:
            Ingestion response with document_id, status, job_id
        """
        payload = {
            "company_id": company_id,
            "document_name": filename,
            "document_type": document_type,
            "url": file_url,
            "metadata": metadata or {}
        }
        
        return await self._make_request(
            "POST",
            "/api/v1/ingestion/documents/upload",
            company_id,
            request_id,
            payload
        )
    
    async def get_document_status(
        self,
        company_id: str,
        request_id: str,
        document_id: str
    ) -> Dict[str, Any]:
        """
        Get document processing status from UWC.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            document_id: Document ID returned from ingestion
        
        Returns:
            Document status response
        """
        return await self._make_request(
            "GET",
            f"/api/v1/ingestion/{document_id}/status",
            company_id,
            request_id
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
    
    # Follow-up Draft Generation (keep for future when available)
    async def generate_followup_draft(
        self,
        company_id: str,
        request_id: str,
        rep_id: str,
        call_context: Dict[str, Any],
        draft_type: str = "sms",
        tone: str = "professional",
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate personalized follow-up draft for a rep.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            rep_id: Sales rep ID to generate draft for
            call_context: Context about the call (customer info, objections, etc.)
            draft_type: Type of draft (sms, email, call_script)
            tone: Tone of the message (professional, friendly, urgent)
            options: Optional generation options (length, style, etc.)
        
        Returns:
            Follow-up draft response with content and metadata
        """
        payload = {
            "request_id": request_id,
            "company_id": company_id,
            "rep_id": rep_id,
            "call_context": call_context,
            "draft_type": draft_type,
            "tone": tone,
            "options": options or {
                "max_length": 160 if draft_type == "sms" else 500,
                "include_personalization": True,
                "include_callback_request": True
            }
        }
        
        return await self._make_request(
            "POST",
            "/uwc/v1/followups/generate",
            company_id,
            request_id,
            payload
        )
    
    # Call Summarization (per OpenAPI /api/v1/summarization/summarize)
    async def summarize_call(
        self,
        company_id: str,
        request_id: str,
        call_id: int,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Summarize a call transcript using UWC.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            call_id: Call ID to summarize
            options: Optional summarization options (length, focus, etc.)
        
        Returns:
            Summarization response with summary, key_points, action_items
        """
        payload = {
            "call_id": call_id
        }
        if options:
            payload.update(options)
        
        return await self._make_request(
            "POST",
            "/api/v1/summarization/summarize",
            company_id,
            request_id,
            payload
        )
    
    async def get_summarization_status(
        self,
        company_id: str,
        request_id: str,
        call_id: int
    ) -> Dict[str, Any]:
        """
        Get summarization status for a call.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            call_id: Call ID
        
        Returns:
            Summarization status response
        """
        return await self._make_request(
            "GET",
            f"/api/v1/summarization/status/{call_id}",
            company_id,
            request_id
        )
    
    # Call Analysis - Objections (per OpenAPI /api/v1/analysis/objections/{call_id})
    async def detect_objections(
        self,
        company_id: str,
        request_id: str,
        call_id: int
    ) -> Dict[str, Any]:
        """
        Detect objections in a call transcript.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            call_id: Call ID
        
        Returns:
            Objections response with detected objections list
        """
        return await self._make_request(
            "GET",
            f"/api/v1/analysis/objections/{call_id}",
            company_id,
            request_id
        )
    
    # Call Analysis - Lead Qualification (per OpenAPI /api/v1/analysis/qualification/{call_id})
    async def qualify_lead(
        self,
        company_id: str,
        request_id: str,
        call_id: int
    ) -> Dict[str, Any]:
        """
        Qualify a lead from a call transcript.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            call_id: Call ID
        
        Returns:
            Lead qualification response with BANT scores and qualification level
        """
        return await self._make_request(
            "GET",
            f"/api/v1/analysis/qualification/{call_id}",
            company_id,
            request_id
        )
    
    # Call Analysis - SOP Compliance (per OpenAPI /api/v1/analysis/compliance/{call_id})
    async def check_compliance(
        self,
        company_id: str,
        request_id: str,
        call_id: int
    ) -> Dict[str, Any]:
        """
        Check SOP compliance for a call.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            call_id: Call ID
        
        Returns:
            Compliance check response with compliance score, violations, recommendations
        """
        return await self._make_request(
            "GET",
            f"/api/v1/analysis/compliance/{call_id}",
            company_id,
            request_id
        )
    
    # Call Analysis - Complete Analysis (per OpenAPI /api/v1/analysis/complete/{call_id})
    async def get_complete_analysis(
        self,
        company_id: str,
        request_id: str,
        call_id: int
    ) -> Dict[str, Any]:
        """
        Get complete analysis results for a call (summary, objections, qualification, compliance).
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            call_id: Call ID
        
        Returns:
            Complete analysis response with all analysis types
        """
        return await self._make_request(
            "GET",
            f"/api/v1/analysis/complete/{call_id}",
            company_id,
            request_id
        )
    
    # Call Analysis - Start Analysis (per OpenAPI /api/v1/analysis/start/{call_id})
    async def start_analysis(
        self,
        company_id: str,
        request_id: str,
        call_id: int
    ) -> Dict[str, Any]:
        """
        Start analysis pipeline for a call.
        
        Returns a job ID for async tracking.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            call_id: Call ID
        
        Returns:
            Analysis start response with job_id/task_id for async tracking
        """
        response = await self._make_request(
            "POST",
            f"/api/v1/analysis/start/{call_id}",
            company_id,
            request_id
        )
        
        # Return response as-is - job ID extraction handled by caller
        return response
    
    async def get_job_status(
        self,
        company_id: str,
        request_id: str,
        job_id: str,
        job_type: str = "analysis",
    ) -> Dict[str, Any]:
        """
        Get status of a Shunya job.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            job_id: Shunya job/task ID
            job_type: Type of job ("analysis", "transcription", "segmentation")
        
        Returns:
            Job status response with status, progress, etc.
        """
        # Map job type to endpoint
        if job_type == "transcription":
            # For transcription, we use call_id or job_id
            # Try to use analysis status endpoint if call_id available
            # Otherwise, use a generic status endpoint
            return await self._make_request(
                "GET",
                f"/api/v1/transcription/status/{job_id}",  # Using job_id as call_id temporarily
                company_id,
                request_id,
            )
        elif job_type == "segmentation":
            return await self._make_request(
                "GET",
                f"/api/v1/meeting-segmentation/status/{job_id}",
                company_id,
                request_id,
            )
        else:
            # Analysis status
            return await self._make_request(
                "GET",
                f"/api/v1/analysis/status/{job_id}",
                company_id,
                request_id,
            )
    
    async def get_job_result(
        self,
        company_id: str,
        request_id: str,
        call_id: int,
        job_type: str = "analysis",
    ) -> Dict[str, Any]:
        """
        Get result of a completed Shunya job.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            call_id: Call ID (used for result retrieval)
            job_type: Type of job ("analysis", "transcription", "segmentation")
        
        Returns:
            Job result (normalized if possible)
        """
        if job_type == "transcription":
            return await self.get_transcript(company_id, request_id, call_id)
        elif job_type == "segmentation":
            return await self.get_meeting_segmentation_analysis(company_id, request_id, call_id)
        else:
            # Complete analysis
            return await self.get_complete_analysis(company_id, request_id, call_id)
    
    async def get_segmentation_status(
        self,
        company_id: str,
        request_id: str,
        call_id: int,
    ) -> Dict[str, Any]:
        """Get meeting segmentation status."""
        return await self.get_meeting_segmentation_status(company_id, request_id, call_id)
    
    async def get_segmentation_result(
        self,
        company_id: str,
        request_id: str,
        call_id: int,
    ) -> Dict[str, Any]:
        """Get meeting segmentation result."""
        return await self.get_meeting_segmentation_analysis(company_id, request_id, call_id)
    
    async def get_analysis_status(
        self,
        company_id: str,
        request_id: str,
        call_id: int
    ) -> Dict[str, Any]:
        """
        Get analysis status for a call.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            call_id: Call ID
        
        Returns:
            Analysis status response with status per analysis type
        """
        return await self._make_request(
            "GET",
            f"/api/v1/analysis/status/{call_id}",
            company_id,
            request_id
        )
    
    async def get_call_summary(
        self,
        company_id: str,
        request_id: str,
        call_id: int
    ) -> Dict[str, Any]:
        """
        Get call summary (alternative endpoint).
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            call_id: Call ID
        
        Returns:
            Call summary response
        """
        return await self._make_request(
            "GET",
            f"/api/v1/analysis/summary/{call_id}",
            company_id,
            request_id
        )
    
    # Meeting Segmentation (per OpenAPI /api/v1/meeting-segmentation/analyze)
    async def analyze_meeting_segmentation(
        self,
        company_id: str,
        request_id: str,
        call_id: int,
        analysis_type: str = "full"
    ) -> Dict[str, Any]:
        """
        Analyze meeting segmentation for a sales appointment.
        
        Segments appointment into:
        - Part 1: Rapport/Agenda (relationship building, agenda setting)
        - Part 2: Proposal/Close (presentation, proposal, closing)
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            call_id: Call ID (for sales appointment)
            analysis_type: "full" or "quick"
        
        Returns:
            Meeting segmentation response with part1, part2, transition point, etc.
        """
        payload = {
            "call_id": call_id,
            "analysis_type": analysis_type
        }
        return await self._make_request(
            "POST",
            "/api/v1/meeting-segmentation/analyze",
            company_id,
            request_id,
            payload
        )
    
    async def get_meeting_segmentation_status(
        self,
        company_id: str,
        request_id: str,
        call_id: int
    ) -> Dict[str, Any]:
        """Get meeting segmentation status."""
        return await self._make_request(
            "GET",
            f"/api/v1/meeting-segmentation/status/{call_id}",
            company_id,
            request_id
        )
    
    async def get_meeting_segmentation_analysis(
        self,
        company_id: str,
        request_id: str,
        call_id: int
    ) -> Dict[str, Any]:
        """Get full meeting segmentation analysis."""
        return await self._make_request(
            "GET",
            f"/api/v1/meeting-segmentation/analysis/{call_id}",
            company_id,
            request_id
        )


# Singleton instance
_uwc_client: Optional[UWCClient] = None


def get_uwc_client() -> UWCClient:
    """Get or create UWC client singleton instance."""
    global _uwc_client
    if _uwc_client is None:
        _uwc_client = UWCClient()
    return _uwc_client


