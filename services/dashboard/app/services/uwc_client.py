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
    
    @staticmethod
    def _map_otto_role_to_shunya_target_role(otto_role: str) -> str:
        """
        Map Otto's internal role to Shunya's target_role value.
        
        Args:
            otto_role: Otto role string ("csr", "sales_rep", "manager", "exec")
        
        Returns:
            Shunya target_role string ("customer_rep", "sales_rep", "sales_manager", "admin")
        
        Valid Shunya target roles per Integration-Status.md:
        - "sales_rep" - Sales representative
        - "customer_rep" - Customer service representative
        - "sales_manager" - Sales manager
        - "admin" - Administrator
        """
        role_mapping = {
            "csr": "customer_rep",
            "sales_rep": "sales_rep",
            "rep": "sales_rep",  # Alias
            "manager": "sales_manager",
            "exec": "admin",
            "executive": "admin",  # Alias
        }
        return role_mapping.get(otto_role.lower(), "sales_rep")  # Default to sales_rep
    
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
        payload: Optional[dict] = None,
        target_role: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate request headers for UWC API calls.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID for request tracing
            payload: Optional request payload for signature generation
            target_role: Optional target role for Shunya (e.g., "sales_rep", "customer_rep", "sales_manager", "admin")
                         If provided, adds X-Target-Role header
        
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
        
        # Add X-Target-Role header if provided (per Shunya contract)
        if target_role:
            headers["X-Target-Role"] = target_role
        
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
        retry_count: int = 0,
        target_role: Optional[str] = None,
        target_role_query: Optional[str] = None
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
            target_role: Optional target role for X-Target-Role header (e.g., "sales_rep", "customer_rep")
            target_role_query: Optional target role for ?target_role= query parameter (for SOP/compliance endpoints)
        
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
        
        # Append target_role query parameter if provided
        url = f"{self.base_url}{endpoint}"
        if target_role_query:
            separator = "&" if "?" in endpoint else "?"
            url = f"{url}{separator}target_role={target_role_query}"
        
        headers = self._get_headers(company_id, request_id, payload, target_role=target_role)
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
                # P0 FIX: Record Shunya API error metric
                from app.obs.metrics import metrics
                error_type = "client_error" if response.status_code < 500 else "server_error"
                metrics.record_shunya_api_error(endpoint=endpoint, error_type=error_type)
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
        options: Optional[Dict[str, Any]] = None,
        target_role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query RAG system for contextual information.
        
        ⚠️ **LEGACY METHOD** - This method uses the legacy `/api/v1/search/` endpoint.
        For new code, use `query_ask_otto()` which calls the canonical `/api/v1/ask-otto/query` endpoint.
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            query: Natural language query
            context: Context dict with tenant_id, rep_id, meeting_id, user_role
            options: Optional RAG options (max_results, similarity_threshold, etc.)
            target_role: Optional target role for Shunya (e.g., "sales_rep", "customer_rep")
                        If not provided, will attempt to extract from context["user_role"]
        
        Returns:
            RAG query response with results and metadata
        """
        # Extract target_role from context if not explicitly provided
        if not target_role and context and "user_role" in context:
            target_role = self._map_otto_role_to_shunya_target_role(context["user_role"])
        
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
            payload,
            target_role=target_role
        )
    
    async def query_ask_otto(
        self,
        *,
        company_id: str,
        request_id: str,
        question: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        scope: Optional[Dict[str, Any]] = None,
        target_role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query Ask Otto using Shunya's canonical endpoint.
        
        This method calls the canonical `/api/v1/ask-otto/query` endpoint with the proper payload format
        as specified in Shunya's contract (webhook-and-other-payload-ask-otto.md).
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            question: Natural language question (required)
            conversation_id: Optional conversation ID for multi-turn conversations
            context: Optional context dict (e.g., tenant_id, user_role, filters)
            scope: Optional scope dict for data filtering
            target_role: Optional target role for Shunya (e.g., "sales_rep", "customer_rep")
                        If not provided, will attempt to extract from context["user_role"]
        
        Returns:
            Shunya's Ask Otto response with answer, sources, confidence, metadata, etc.
            Response format per webhook-and-other-payload-ask-otto.md:
            {
                "success": true,
                "query_id": "...",
                "conversation_id": "...",
                "question": "...",
                "answer": "...",
                "confidence": 0.7,
                "sources": [...],
                "suggested_follow_ups": [...],
                "metadata": {...}
            }
        """
        # Extract target_role from context if not explicitly provided
        if not target_role and context and "user_role" in context:
            target_role = self._map_otto_role_to_shunya_target_role(context["user_role"])
        
        # Build canonical Ask Otto payload per Shunya contract
        payload: Dict[str, Any] = {
            "question": question
        }
        
        if conversation_id:
            payload["conversation_id"] = conversation_id
        
        if context:
            payload["context"] = context
        
        if scope:
            payload["scope"] = scope
        
        return await self._make_request(
            "POST",
            "/api/v1/ask-otto/query",
            company_id,
            request_id,
            payload,
            target_role=target_role
        )
    
    async def get_followup_recommendations(
        self,
        *,
        call_id: int,
        company_id: str,
        request_id: str,
        target_role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get follow-up recommendations for a call from Shunya.
        
        This method calls Shunya's canonical endpoint for follow-up recommendations
        as specified in Integration-Status.md:
        POST /api/v1/analysis/followup-recommendations/{call_id}
        
        Args:
            call_id: Call ID to get recommendations for
            company_id: Tenant/company ID
            request_id: Correlation ID
            target_role: Optional target role for Shunya (e.g., "sales_rep", "customer_rep")
                        If not provided, will default based on context
        
        Returns:
            Normalized follow-up recommendations dict:
            {
                "recommendations": [...],  # List of recommendation objects
                "next_steps": [...],       # List of next step actions
                "priority_actions": [...], # List of high-priority actions
                "confidence_score": float|null  # Overall confidence in recommendations
            }
        """
        endpoint = f"/api/v1/analysis/followup-recommendations/{call_id}"
        
        # Shunya endpoint expects POST with empty body (call_id is in path)
        payload = {}
        
        try:
            response = await self._make_request(
                "POST",
                endpoint,
                company_id,
                request_id,
                payload,
                target_role=target_role
            )
            
            # Normalize Shunya response to Otto format
            # Defensive parsing: handle various response shapes
            normalized = {
                "recommendations": [],
                "next_steps": [],
                "priority_actions": [],
                "confidence_score": None
            }
            
            # Extract recommendations (handle various field names)
            if isinstance(response, dict):
                # Try common field names
                recommendations = (
                    response.get("recommendations") or
                    response.get("followup_recommendations") or
                    response.get("recommendation_list") or
                    []
                )
                
                # Normalize recommendation objects
                if isinstance(recommendations, list):
                    normalized["recommendations"] = [
                        self._normalize_recommendation_item(rec)
                        for rec in recommendations
                        if rec is not None
                    ]
                
                # Extract next_steps
                next_steps = (
                    response.get("next_steps") or
                    response.get("next_actions") or
                    response.get("suggested_actions") or
                    []
                )
                if isinstance(next_steps, list):
                    normalized["next_steps"] = [
                        self._normalize_recommendation_item(step)
                        for step in next_steps
                        if step is not None
                    ]
                
                # Extract priority_actions
                priority_actions = (
                    response.get("priority_actions") or
                    response.get("high_priority_actions") or
                    response.get("urgent_actions") or
                    []
                )
                if isinstance(priority_actions, list):
                    normalized["priority_actions"] = [
                        self._normalize_recommendation_item(action)
                        for action in priority_actions
                        if action is not None
                    ]
                
                # Extract confidence_score
                confidence = (
                    response.get("confidence_score") or
                    response.get("confidence") or
                    response.get("overall_confidence")
                )
                if confidence is not None:
                    try:
                        normalized["confidence_score"] = float(confidence)
                    except (ValueError, TypeError):
                        normalized["confidence_score"] = None
            
            return normalized
            
        except Exception as e:
            logger.warning(
                f"Failed to get follow-up recommendations for call {call_id}: {str(e)}",
                extra={"call_id": call_id, "company_id": company_id}
            )
            # Return empty structure on error (non-blocking)
            return {
                "recommendations": [],
                "next_steps": [],
                "priority_actions": [],
                "confidence_score": None
            }
    
    @staticmethod
    def _normalize_recommendation_item(item: Any) -> Dict[str, Any]:
        """
        Normalize a single recommendation/action item to consistent format.
        
        Args:
            item: Raw recommendation item (dict, string, or other)
        
        Returns:
            Normalized dict with: action, description, priority, timing, reasoning
        """
        if isinstance(item, dict):
            # Already a dict, ensure required fields exist
            return {
                "action": item.get("action") or item.get("title") or item.get("type") or "",
                "description": item.get("description") or item.get("text") or item.get("summary") or "",
                "priority": item.get("priority") or item.get("urgency") or "medium",
                "timing": item.get("timing") or item.get("when") or item.get("suggested_time") or None,
                "reasoning": item.get("reasoning") or item.get("reason") or item.get("rationale") or None
            }
        elif isinstance(item, str):
            # String item, convert to dict
            return {
                "action": item,
                "description": "",
                "priority": "medium",
                "timing": None,
                "reasoning": None
            }
        else:
            # Unknown type, return minimal structure
            return {
                "action": str(item) if item is not None else "",
                "description": "",
                "priority": "medium",
                "timing": None,
                "reasoning": None
            }
    
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
        metadata: Optional[Dict[str, Any]] = None,
        target_role: Optional[str] = None
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
            target_role: Optional target role for ?target_role= query parameter
                        (Shunya requires this for SOP/document ingestion per contract)
                        If not provided, Shunya may reject the request
        
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
            payload,
            target_role_query=target_role  # Use query param per Shunya contract for ingestion endpoints
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
        Check SOP compliance for a call (GET - retrieves existing results).
        
        ⚠️ **LEGACY METHOD** - This method uses the GET endpoint to retrieve existing compliance results.
        For running new compliance checks, use `run_compliance_check()` which calls the POST endpoint.
        
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
    
    async def run_compliance_check(
        self,
        *,
        call_id: int,
        company_id: str,
        request_id: str,
        target_role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run a new SOP compliance check for a call from Shunya.
        
        This method calls Shunya's canonical POST endpoint for compliance checks
        as specified in Integration-Status.md:
        POST /api/v1/sop/compliance/check?target_role={role}
        
        Args:
            call_id: Call ID to run compliance check for
            company_id: Tenant/company ID
            request_id: Correlation ID
            target_role: Target role for Shunya (e.g., "sales_rep", "customer_rep")
                        REQUIRED per Shunya contract - must be provided as query parameter
        
        Returns:
            Normalized compliance check response:
            {
                "compliance_score": float|null,
                "stages_followed": list[str],
                "stages_missed": list[str],
                "violations": list[dict],
                "positive_behaviors": list[dict],
                "recommendations": list[dict]
            }
        """
        endpoint = f"/api/v1/sop/compliance/check"
        
        # Shunya contract requires ?target_role= query parameter (not just header)
        # Send empty JSON body {} unless contract requires otherwise
        payload = {}
        
        try:
            response = await self._make_request(
                "POST",
                endpoint,
                company_id,
                request_id,
                payload,
                target_role=target_role,  # Also set X-Target-Role header if provided
                target_role_query=target_role  # REQUIRED: Set ?target_role= query param
            )
            
            # Normalize Shunya response to Otto format
            # Defensive parsing: handle various response shapes
            normalized = {
                "compliance_score": None,
                "stages_followed": [],
                "stages_missed": [],
                "violations": [],
                "positive_behaviors": [],
                "recommendations": []
            }
            
            if isinstance(response, dict):
                # Extract compliance_score (handle various field names)
                compliance_score = (
                    response.get("compliance_score") or
                    response.get("score") or
                    response.get("overall_score") or
                    response.get("compliance_rating")
                )
                if compliance_score is not None:
                    try:
                        normalized["compliance_score"] = float(compliance_score)
                    except (ValueError, TypeError):
                        normalized["compliance_score"] = None
                
                # Extract stages_followed (handle various field names)
                stages_followed = (
                    response.get("stages_followed") or
                    response.get("stages_completed") or
                    response.get("completed_stages") or
                    response.get("followed_stages") or
                    []
                )
                if isinstance(stages_followed, list):
                    normalized["stages_followed"] = [
                        str(stage) for stage in stages_followed
                        if stage is not None
                    ]
                
                # Extract stages_missed (handle various field names)
                stages_missed = (
                    response.get("stages_missed") or
                    response.get("missed_stages") or
                    response.get("incomplete_stages") or
                    []
                )
                if isinstance(stages_missed, list):
                    normalized["stages_missed"] = [
                        str(stage) for stage in stages_missed
                        if stage is not None
                    ]
                
                # Extract violations (handle various field names)
                violations = (
                    response.get("violations") or
                    response.get("compliance_violations") or
                    response.get("violation_list") or
                    []
                )
                if isinstance(violations, list):
                    normalized["violations"] = [
                        self._normalize_compliance_item(violation)
                        for violation in violations
                        if violation is not None
                    ]
                
                # Extract positive_behaviors (handle various field names)
                positive_behaviors = (
                    response.get("positive_behaviors") or
                    response.get("behaviors") or
                    response.get("positive_actions") or
                    response.get("strengths") or
                    []
                )
                if isinstance(positive_behaviors, list):
                    normalized["positive_behaviors"] = [
                        self._normalize_compliance_item(behavior)
                        for behavior in positive_behaviors
                        if behavior is not None
                    ]
                
                # Extract recommendations (handle various field names)
                recommendations = (
                    response.get("recommendations") or
                    response.get("compliance_recommendations") or
                    response.get("improvement_recommendations") or
                    response.get("suggestions") or
                    []
                )
                if isinstance(recommendations, list):
                    normalized["recommendations"] = [
                        self._normalize_compliance_item(rec)
                        for rec in recommendations
                        if rec is not None
                    ]
            
            return normalized
            
        except Exception as e:
            logger.warning(
                f"Failed to run compliance check for call {call_id}: {str(e)}",
                extra={"call_id": call_id, "company_id": company_id}
            )
            # Return empty structure on error (non-blocking)
            return {
                "compliance_score": None,
                "stages_followed": [],
                "stages_missed": [],
                "violations": [],
                "positive_behaviors": [],
                "recommendations": []
            }
    
    @staticmethod
    def _normalize_compliance_item(item: Any) -> Dict[str, Any]:
        """
        Normalize a single compliance item (violation, behavior, recommendation) to consistent format.
        
        Args:
            item: Raw compliance item (dict, string, or other)
        
        Returns:
            Normalized dict with: stage, type/behavior/recommendation, description, severity/priority, timestamp
        """
        if isinstance(item, dict):
            # Already a dict, ensure required fields exist
            return {
                "stage": item.get("stage") or item.get("sop_stage") or item.get("phase") or None,
                "type": item.get("type") or item.get("violation_type") or item.get("behavior") or item.get("recommendation_type") or "",
                "description": item.get("description") or item.get("text") or item.get("message") or item.get("summary") or "",
                "severity": item.get("severity") or item.get("priority") or item.get("urgency") or "medium",
                "timestamp": item.get("timestamp") or item.get("time") or item.get("when") or None,
                "reasoning": item.get("reasoning") or item.get("reason") or item.get("rationale") or None
            }
        elif isinstance(item, str):
            # String item, convert to dict
            return {
                "stage": None,
                "type": item,
                "description": "",
                "severity": "medium",
                "timestamp": None,
                "reasoning": None
            }
        else:
            # Unknown type, return minimal structure
            return {
                "stage": None,
                "type": str(item) if item is not None else "",
                "description": "",
                "severity": "medium",
                "timestamp": None,
                "reasoning": None
            }
    
    # Personal Otto (AI Clones) - per Integration-Status.md
    async def ingest_personal_otto_documents(
        self,
        *,
        company_id: str,
        request_id: str,
        rep_id: str,
        documents: List[Dict[str, Any]],
        target_role: str = "sales_rep"  # REQUIRED per Shunya contract, default to sales_rep
    ) -> Dict[str, Any]:
        """
        Ingest training documents for Personal Otto (AI clone) training.
        
        This method calls Shunya's canonical endpoint for Personal Otto document ingestion
        as specified in Integration-Status.md:
        POST /api/v1/personal-otto/ingest/training-documents
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            rep_id: Sales rep ID (user identifier)
            documents: List of training documents with content and metadata
            target_role: Target role for Shunya (REQUIRED per contract, defaults to "sales_rep")
                        Must be "sales_rep" or "customer_rep" per Shunya contract
        
        Returns:
            Ingestion response with job_id, status, document_ids
        """
        endpoint = "/api/v1/personal-otto/ingest/training-documents"
        
        payload = {
            "rep_id": rep_id,
            "documents": documents
        }
        
        try:
            # X-Target-Role header is REQUIRED per Shunya contract
            response = await self._make_request(
                "POST",
                endpoint,
                company_id,
                request_id,
                payload,
                target_role=target_role  # REQUIRED: Set X-Target-Role header
            )
            
            # Normalize response
            normalized = {
                "job_id": None,
                "status": "pending",
                "document_ids": [],
                "message": None
            }
            
            if isinstance(response, dict):
                normalized["job_id"] = response.get("job_id") or response.get("task_id")
                normalized["status"] = response.get("status", "pending")
                normalized["document_ids"] = response.get("document_ids") or response.get("documents", [])
                normalized["message"] = response.get("message") or response.get("status_message")
            
            return normalized
            
        except Exception as e:
            logger.warning(
                f"Failed to ingest Personal Otto documents for rep {rep_id}: {str(e)}",
                extra={"rep_id": rep_id, "company_id": company_id}
            )
            # Return error structure (non-blocking)
            return {
                "job_id": None,
                "status": "failed",
                "document_ids": [],
                "message": str(e)
            }
    
    async def run_personal_otto_training(
        self,
        *,
        company_id: str,
        request_id: str,
        rep_id: str,
        target_role: str = "sales_rep",  # REQUIRED per Shunya contract, default to sales_rep
        force_retrain: bool = False
    ) -> Dict[str, Any]:
        """
        Trigger Personal Otto (AI clone) training for a sales rep.
        
        This method calls Shunya's canonical endpoint for Personal Otto training
        as specified in Integration-Status.md:
        POST /api/v1/personal-otto/train
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            rep_id: Sales rep ID (user identifier)
            target_role: Target role for Shunya (REQUIRED per contract, defaults to "sales_rep")
                        Must be "sales_rep" or "customer_rep" per Shunya contract
            force_retrain: If True, force retraining even if already trained
        
        Returns:
            Training response with job_id, status, estimated_completion_time
        """
        endpoint = "/api/v1/personal-otto/train"
        
        payload = {
            "rep_id": rep_id,
            "force_retrain": force_retrain
        }
        
        try:
            # X-Target-Role header is REQUIRED per Shunya contract
            response = await self._make_request(
                "POST",
                endpoint,
                company_id,
                request_id,
                payload,
                target_role=target_role  # REQUIRED: Set X-Target-Role header
            )
            
            # Normalize response
            normalized = {
                "job_id": None,
                "status": "pending",
                "estimated_completion_time": None,
                "message": None
            }
            
            if isinstance(response, dict):
                normalized["job_id"] = response.get("job_id") or response.get("task_id")
                normalized["status"] = response.get("status", "pending")
                normalized["estimated_completion_time"] = response.get("estimated_completion_time") or response.get("eta")
                normalized["message"] = response.get("message") or response.get("status_message")
            
            return normalized
            
        except Exception as e:
            logger.warning(
                f"Failed to trigger Personal Otto training for rep {rep_id}: {str(e)}",
                extra={"rep_id": rep_id, "company_id": company_id}
            )
            # Return error structure (non-blocking)
            return {
                "job_id": None,
                "status": "failed",
                "estimated_completion_time": None,
                "message": str(e)
            }
    
    async def get_personal_otto_status(
        self,
        *,
        company_id: str,
        request_id: str,
        rep_id: str,
        target_role: str = "sales_rep"  # REQUIRED per Shunya contract, default to sales_rep
    ) -> Dict[str, Any]:
        """
        Get Personal Otto (AI clone) training status for a sales rep.
        
        This method calls Shunya's canonical endpoint for Personal Otto status
        as specified in Integration-Status.md:
        GET /api/v1/personal-otto/profile/status
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            rep_id: Sales rep ID (user identifier)
            target_role: Target role for Shunya (REQUIRED per contract, defaults to "sales_rep")
                        Must be "sales_rep" or "customer_rep" per Shunya contract
        
        Returns:
            Status response with is_trained, training_status, last_trained_at, model_version
        """
        endpoint = f"/api/v1/personal-otto/profile/status?rep_id={rep_id}"
        
        try:
            # X-Target-Role header is REQUIRED per Shunya contract
            response = await self._make_request(
                "GET",
                endpoint,
                company_id,
                request_id,
                None,  # GET request, no payload
                target_role=target_role  # REQUIRED: Set X-Target-Role header
            )
            
            # Normalize response
            normalized = {
                "rep_id": rep_id,
                "is_trained": False,
                "training_status": "not_started",
                "last_trained_at": None,
                "model_version": None,
                "progress_percentage": None
            }
            
            if isinstance(response, dict):
                normalized["rep_id"] = response.get("rep_id", rep_id)
                normalized["is_trained"] = response.get("is_trained", False)
                normalized["training_status"] = (
                    response.get("training_status") or
                    response.get("status") or
                    "not_started"
                )
                normalized["last_trained_at"] = response.get("last_trained_at") or response.get("last_trained")
                normalized["model_version"] = response.get("model_version") or response.get("version")
                normalized["progress_percentage"] = response.get("progress_percentage") or response.get("progress")
            
            return normalized
            
        except Exception as e:
            logger.warning(
                f"Failed to get Personal Otto status for rep {rep_id}: {str(e)}",
                extra={"rep_id": rep_id, "company_id": company_id}
            )
            # Return default structure on error (non-blocking)
            return {
                "rep_id": rep_id,
                "is_trained": False,
                "training_status": "error",
                "last_trained_at": None,
                "model_version": None,
                "progress_percentage": None
            }
    
    async def get_personal_otto_profile(
        self,
        *,
        company_id: str,
        request_id: str,
        rep_id: str,
        target_role: str = "sales_rep"  # REQUIRED per Shunya contract, default to sales_rep
    ) -> Dict[str, Any]:
        """
        Get Personal Otto (AI clone) profile for a sales rep.
        
        This method calls Shunya's canonical endpoint for Personal Otto profile
        as specified in Integration-Status.md:
        GET /api/v1/personal-otto/profile
        
        Args:
            company_id: Tenant/company ID
            request_id: Correlation ID
            rep_id: Sales rep ID (user identifier)
            target_role: Target role for Shunya (REQUIRED per contract, defaults to "sales_rep")
                        Must be "sales_rep" or "customer_rep" per Shunya contract
        
        Returns:
            Profile response with personality_traits, writing_style, communication_preferences, etc.
        """
        endpoint = f"/api/v1/personal-otto/profile?rep_id={rep_id}"
        
        try:
            # X-Target-Role header is REQUIRED per Shunya contract
            response = await self._make_request(
                "GET",
                endpoint,
                company_id,
                request_id,
                None,  # GET request, no payload
                target_role=target_role  # REQUIRED: Set X-Target-Role header
            )
            
            # Normalize response
            normalized = {
                "rep_id": rep_id,
                "personality_traits": [],
                "writing_style": {},
                "communication_preferences": {},
                "sample_outputs": [],
                "model_version": None
            }
            
            if isinstance(response, dict):
                normalized["rep_id"] = response.get("rep_id", rep_id)
                normalized["personality_traits"] = response.get("personality_traits") or response.get("traits") or []
                normalized["writing_style"] = response.get("writing_style") or response.get("style") or {}
                normalized["communication_preferences"] = (
                    response.get("communication_preferences") or
                    response.get("preferences") or
                    {}
                )
                normalized["sample_outputs"] = response.get("sample_outputs") or response.get("examples") or []
                normalized["model_version"] = response.get("model_version") or response.get("version")
            
            return normalized
            
        except Exception as e:
            logger.warning(
                f"Failed to get Personal Otto profile for rep {rep_id}: {str(e)}",
                extra={"rep_id": rep_id, "company_id": company_id}
            )
            # Return default structure on error (non-blocking)
            return {
                "rep_id": rep_id,
                "personality_traits": [],
                "writing_style": {},
                "communication_preferences": {},
                "sample_outputs": [],
                "model_version": None
            }
    
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
