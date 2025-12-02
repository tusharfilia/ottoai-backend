"""
Shunya webhook signature verification.

Provides HMAC-SHA256 signature verification for Shunya webhooks
with constant-time comparison to prevent timing attacks.

Aligned with final Shunya integration contracts:
- Headers: X-Shunya-Signature, X-Shunya-Timestamp, X-Shunya-Task-Id
- Signature: HMAC_SHA256(secret, "{timestamp}.{raw_body_bytes}")
- Timestamp: epoch milliseconds (not ISO 8601)
"""
import hmac
import hashlib
from typing import Optional
import time

from app.config import settings
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)


class ShunyaWebhookSecurityError(Exception):
    """Base exception for webhook security errors."""
    pass


class InvalidSignatureError(ShunyaWebhookSecurityError):
    """Raised when webhook signature is invalid."""
    pass


class MissingHeadersError(ShunyaWebhookSecurityError):
    """Raised when required headers are missing."""
    pass


class TimestampExpiredError(ShunyaWebhookSecurityError):
    """Raised when webhook timestamp is too old (replay attack)."""
    pass


def verify_shunya_webhook_signature(
    raw_body: bytes,
    signature: Optional[str],
    timestamp: Optional[str],
    task_id: Optional[str] = None,
    max_age_seconds: int = 300,  # 5 minutes default
) -> bool:
    """
    Verify HMAC-SHA256 signature for Shunya webhook.
    
    Aligned with final Shunya contract:
    - Headers: X-Shunya-Signature, X-Shunya-Timestamp, X-Shunya-Task-Id
    - Signature: HMAC_SHA256(secret, "{timestamp}.{raw_body_bytes}")
    - Timestamp: epoch milliseconds (as string, e.g. "1701234567890")
    - Digest: lowercase hex string
    
    Args:
        raw_body: Raw request body bytes (unmodified, exact bytes as sent)
        signature: HMAC signature from X-Shunya-Signature header (hex string)
        timestamp: Epoch milliseconds from X-Shunya-Timestamp header (string)
        task_id: Task ID from X-Shunya-Task-Id header (optional, for idempotency logging)
        max_age_seconds: Maximum age of webhook in seconds (default 5 minutes)
    
    Returns:
        True if signature is valid
    
    Raises:
        MissingHeadersError: If signature or timestamp headers are missing
        TimestampExpiredError: If timestamp is too old (replay attack)
        InvalidSignatureError: If signature verification fails
    """
    # Check if HMAC secret is configured
    if not settings.UWC_HMAC_SECRET:
        logger.error(
            "UWC_HMAC_SECRET not configured - webhook signature verification disabled. "
            "This is INSECURE and should not be used in production!"
        )
        # In production, signature verification is mandatory
        if settings.ENVIRONMENT.lower() == "production":
            raise InvalidSignatureError(
                "Webhook signature verification required in production but UWC_HMAC_SECRET not configured"
            )
        # In development/test, allow but log warning
        logger.warning(
            "Allowing webhook without signature verification (development/test mode). "
            "This is INSECURE and should not be used in production!"
        )
        return True  # Allow in development/test only
    
    # Check required headers are present
    if not signature:
        logger.warning("Missing X-Shunya-Signature header in webhook")
        raise MissingHeadersError("Missing X-Shunya-Signature header")
    
    if not timestamp:
        logger.warning("Missing X-Shunya-Timestamp header in webhook")
        raise MissingHeadersError("Missing X-Shunya-Timestamp header")
    
    # Validate timestamp (epoch milliseconds) to prevent replay attacks
    try:
        # Timestamp is epoch milliseconds as string (e.g. "1701234567890")
        timestamp_ms = int(timestamp)
        current_time_ms = int(time.time() * 1000)  # Current time in milliseconds
        
        # Calculate time difference in seconds
        time_diff_seconds = abs((current_time_ms - timestamp_ms) / 1000.0)
        
        if time_diff_seconds > max_age_seconds:
            logger.warning(
                f"Webhook timestamp too old: {timestamp_ms}ms "
                f"(diff: {time_diff_seconds:.0f}s, max: {max_age_seconds}s)",
                extra={
                    "webhook_timestamp_ms": timestamp_ms,
                    "current_time_ms": current_time_ms,
                    "time_diff_seconds": time_diff_seconds,
                    "max_age_seconds": max_age_seconds,
                    "task_id": task_id,
                }
            )
            raise TimestampExpiredError(
                f"Webhook timestamp too old: {time_diff_seconds:.0f}s > {max_age_seconds}s"
            )
    except ValueError as e:
        logger.error(f"Invalid timestamp format (expected epoch milliseconds): {timestamp}, error: {str(e)}")
        raise MissingHeadersError(f"Invalid timestamp format (expected epoch milliseconds): {timestamp}")
    
    # Construct signed message: "{timestamp}.{raw_body_bytes}"
    # Format: HMAC_SHA256(secret, "{timestamp}.{raw_body_bytes}")
    # Note: timestamp is the raw string value, raw_body is exact bytes (no decoding)
    signed_message = f"{timestamp}.".encode('utf-8') + raw_body
    
    # Compute expected signature (lowercase hex)
    expected_signature = hmac.new(
        settings.UWC_HMAC_SECRET.encode('utf-8'),
        signed_message,
        hashlib.sha256
    ).hexdigest().lower()  # Ensure lowercase hex
    
    # Normalize received signature to lowercase for comparison
    received_signature = signature.lower()
    
    # Constant-time comparison to prevent timing attacks
    is_valid = hmac.compare_digest(received_signature, expected_signature)
    
    if not is_valid:
        logger.warning(
            "Invalid Shunya webhook signature",
            extra={
                "webhook_timestamp_ms": timestamp_ms if 'timestamp_ms' in locals() else timestamp,
                "signature_prefix": received_signature[:16] if len(received_signature) > 16 else received_signature,
                "expected_prefix": expected_signature[:16] if len(expected_signature) > 16 else expected_signature,
                "task_id": task_id,
            }
        )
        raise InvalidSignatureError("Invalid webhook signature")
    
    logger.debug(
        "Shunya webhook signature verified successfully",
        extra={
            "webhook_timestamp_ms": timestamp_ms if 'timestamp_ms' in locals() else timestamp,
            "task_id": task_id,
        }
    )
    
    return True


def validate_shunya_webhook(
    raw_body: bytes,
    signature: Optional[str],
    timestamp: Optional[str],
    task_id: Optional[str] = None,
    required_in_production: bool = True,
) -> tuple[bool, Optional[str]]:
    """
    Validate Shunya webhook signature and return (is_valid, error_message).
    
    This is a convenience wrapper that returns a tuple instead of raising exceptions.
    Useful for webhook handlers that want to handle errors gracefully.
    
    Args:
        raw_body: Raw request body bytes
        signature: HMAC signature from X-Shunya-Signature header
        timestamp: Epoch milliseconds from X-Shunya-Timestamp header
        task_id: Task ID from X-Shunya-Task-Id header (optional, for logging)
        required_in_production: If True, require signature verification in production
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
        - If valid: (True, None)
        - If invalid: (False, error_message)
    """
    try:
        # In production, signature is required
        if settings.ENVIRONMENT.lower() == "production" and required_in_production:
            if not settings.UWC_HMAC_SECRET:
                return (False, "Webhook signature verification required but UWC_HMAC_SECRET not configured")
        
        verify_shunya_webhook_signature(raw_body, signature, timestamp, task_id)
        return (True, None)
    
    except MissingHeadersError as e:
        if settings.ENVIRONMENT.lower() == "production" and required_in_production:
            return (False, str(e))
        # In development, log but allow
        logger.warning(f"Webhook signature validation warning (dev mode): {str(e)}")
        return (True, None)  # Allow in development
    
    except TimestampExpiredError as e:
        return (False, str(e))
    
    except InvalidSignatureError as e:
        return (False, str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error during webhook signature verification: {str(e)}", exc_info=True)
        return (False, f"Signature verification error: {str(e)}")

