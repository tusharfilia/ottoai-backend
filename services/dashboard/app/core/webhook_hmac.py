"""
HMAC webhook validation for Otto AI backend.
Provides secure webhook signature verification with replay protection.
"""
import hmac
import hashlib
import time
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException
from app.config import settings
from app.obs.logging import get_logger

logger = get_logger(__name__)


class WebhookHMACValidator:
    """Validator for webhook HMAC signatures with replay protection."""
    
    def __init__(self, max_age_seconds: int = 300):  # 5 minutes default
        self.max_age_seconds = max_age_seconds
        self.processed_events = set()  # In production, use Redis
    
    def validate_uwc_webhook(self, request: Request, body: bytes) -> bool:
        """
        Validate UWC/Shunya webhook signature.
        
        Expected headers:
        - X-UWC-Signature: HMAC-SHA256 signature
        - X-UWC-Timestamp: Unix timestamp
        - X-Event-ID: Unique event identifier
        
        Args:
            request: FastAPI Request object
            body: Raw request body
            
        Returns:
            bool: True if valid, False otherwise
        """
        signature = request.headers.get("X-UWC-Signature")
        timestamp = request.headers.get("X-UWC-Timestamp")
        event_id = request.headers.get("X-Event-ID")
        
        if not all([signature, timestamp, event_id]):
            logger.warning("Missing required UWC webhook headers")
            return False
        
        # Check timestamp to prevent replay attacks
        try:
            timestamp_int = int(timestamp)
            current_time = int(time.time())
            
            if abs(current_time - timestamp_int) > self.max_age_seconds:
                logger.warning(f"Webhook timestamp too old: {timestamp_int}, current: {current_time}")
                return False
        except ValueError:
            logger.warning(f"Invalid timestamp format: {timestamp}")
            return False
        
        # Check for replay attacks
        if event_id in self.processed_events:
            logger.warning(f"Duplicate event ID detected: {event_id}")
            return False
        
        # Verify HMAC signature
        expected_signature = self._calculate_uwc_signature(timestamp, body)
        
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning("Invalid UWC webhook signature")
            return False
        
        # Mark event as processed
        self.processed_events.add(event_id)
        
        logger.info(f"Valid UWC webhook: event_id={event_id}, timestamp={timestamp}")
        return True
    
    def validate_callrail_webhook(self, request: Request, body: bytes) -> bool:
        """
        Validate CallRail webhook signature.
        
        Expected headers:
        - X-CallRail-Signature: HMAC-SHA256 signature
        - X-CallRail-Timestamp: Unix timestamp
        
        Args:
            request: FastAPI Request object
            body: Raw request body
            
        Returns:
            bool: True if valid, False otherwise
        """
        signature = request.headers.get("X-CallRail-Signature")
        timestamp = request.headers.get("X-CallRail-Timestamp")
        
        if not all([signature, timestamp]):
            logger.warning("Missing required CallRail webhook headers")
            return False
        
        # Check timestamp
        try:
            timestamp_int = int(timestamp)
            current_time = int(time.time())
            
            if abs(current_time - timestamp_int) > self.max_age_seconds:
                logger.warning(f"CallRail webhook timestamp too old: {timestamp_int}")
                return False
        except ValueError:
            logger.warning(f"Invalid CallRail timestamp format: {timestamp}")
            return False
        
        # Verify HMAC signature
        expected_signature = self._calculate_callrail_signature(timestamp, body)
        
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning("Invalid CallRail webhook signature")
            return False
        
        logger.info(f"Valid CallRail webhook: timestamp={timestamp}")
        return True
    
    def validate_twilio_webhook(self, request: Request, body: bytes) -> bool:
        """
        Validate Twilio webhook signature.
        
        Expected headers:
        - X-Twilio-Signature: HMAC-SHA1 signature
        - X-Twilio-Timestamp: Unix timestamp
        
        Args:
            request: FastAPI Request object
            body: Raw request body
            
        Returns:
            bool: True if valid, False otherwise
        """
        signature = request.headers.get("X-Twilio-Signature")
        timestamp = request.headers.get("X-Twilio-Timestamp")
        
        if not all([signature, timestamp]):
            logger.warning("Missing required Twilio webhook headers")
            return False
        
        # Check timestamp
        try:
            timestamp_int = int(timestamp)
            current_time = int(time.time())
            
            if abs(current_time - timestamp_int) > self.max_age_seconds:
                logger.warning(f"Twilio webhook timestamp too old: {timestamp_int}")
                return False
        except ValueError:
            logger.warning(f"Invalid Twilio timestamp format: {timestamp}")
            return False
        
        # Verify HMAC signature
        expected_signature = self._calculate_twilio_signature(timestamp, body)
        
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning("Invalid Twilio webhook signature")
            return False
        
        logger.info(f"Valid Twilio webhook: timestamp={timestamp}")
        return True
    
    def validate_clerk_webhook(self, request: Request, body: bytes) -> bool:
        """
        Validate Clerk webhook signature.
        
        Expected headers:
        - X-Clerk-Signature: HMAC-SHA256 signature
        - X-Clerk-Timestamp: Unix timestamp
        
        Args:
            request: FastAPI Request object
            body: Raw request body
            
        Returns:
            bool: True if valid, False otherwise
        """
        signature = request.headers.get("X-Clerk-Signature")
        timestamp = request.headers.get("X-Clerk-Timestamp")
        
        if not all([signature, timestamp]):
            logger.warning("Missing required Clerk webhook headers")
            return False
        
        # Check timestamp
        try:
            timestamp_int = int(timestamp)
            current_time = int(time.time())
            
            if abs(current_time - timestamp_int) > self.max_age_seconds:
                logger.warning(f"Clerk webhook timestamp too old: {timestamp_int}")
                return False
        except ValueError:
            logger.warning(f"Invalid Clerk timestamp format: {timestamp}")
            return False
        
        # Verify HMAC signature
        expected_signature = self._calculate_clerk_signature(timestamp, body)
        
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning("Invalid Clerk webhook signature")
            return False
        
        logger.info(f"Valid Clerk webhook: timestamp={timestamp}")
        return True
    
    def _calculate_uwc_signature(self, timestamp: str, body: bytes) -> str:
        """Calculate expected UWC webhook signature."""
        secret = settings.UWC_WEBHOOK_SECRET
        if not secret:
            raise ValueError("UWC_WEBHOOK_SECRET not configured")
        
        # UWC signature format: HMAC-SHA256(timestamp + "." + sha256(body))
        body_hash = hashlib.sha256(body).hexdigest()
        message = f"{timestamp}.{body_hash}"
        
        signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _calculate_callrail_signature(self, timestamp: str, body: bytes) -> str:
        """Calculate expected CallRail webhook signature."""
        secret = settings.CALLRAIL_WEBHOOK_SECRET
        if not secret:
            raise ValueError("CALLRAIL_WEBHOOK_SECRET not configured")
        
        # CallRail signature format: HMAC-SHA256(timestamp + body)
        message = f"{timestamp}{body.decode()}"
        
        signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _calculate_twilio_signature(self, timestamp: str, body: bytes) -> str:
        """Calculate expected Twilio webhook signature."""
        secret = settings.TWILIO_WEBHOOK_SECRET
        if not secret:
            raise ValueError("TWILIO_WEBHOOK_SECRET not configured")
        
        # Twilio signature format: HMAC-SHA1(timestamp + body)
        message = f"{timestamp}{body.decode()}"
        
        signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha1
        ).hexdigest()
        
        return signature
    
    def _calculate_clerk_signature(self, timestamp: str, body: bytes) -> str:
        """Calculate expected Clerk webhook signature."""
        secret = settings.CLERK_WEBHOOK_SECRET
        if not secret:
            raise ValueError("CLERK_WEBHOOK_SECRET not configured")
        
        # Clerk signature format: HMAC-SHA256(timestamp + body)
        message = f"{timestamp}{body.decode()}"
        
        signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature


# Global validator instance
webhook_validator = WebhookHMACValidator()


# Convenience functions for route decorators
def require_uwc_webhook_signature(request: Request, body: bytes) -> bool:
    """Validate UWC webhook signature or raise HTTPException."""
    if not webhook_validator.validate_uwc_webhook(request, body):
        raise HTTPException(
            status_code=401,
            detail="Invalid UWC webhook signature"
        )
    return True


def require_callrail_webhook_signature(request: Request, body: bytes) -> bool:
    """Validate CallRail webhook signature or raise HTTPException."""
    if not webhook_validator.validate_callrail_webhook(request, body):
        raise HTTPException(
            status_code=401,
            detail="Invalid CallRail webhook signature"
        )
    return True


def require_twilio_webhook_signature(request: Request, body: bytes) -> bool:
    """Validate Twilio webhook signature or raise HTTPException."""
    if not webhook_validator.validate_twilio_webhook(request, body):
        raise HTTPException(
            status_code=401,
            detail="Invalid Twilio webhook signature"
        )
    return True


def require_clerk_webhook_signature(request: Request, body: bytes) -> bool:
    """Validate Clerk webhook signature or raise HTTPException."""
    if not webhook_validator.validate_clerk_webhook(request, body):
        raise HTTPException(
            status_code=401,
            detail="Invalid Clerk webhook signature"
        )
    return True

