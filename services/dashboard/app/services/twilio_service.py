"""
Enhanced Twilio Service for SMS functionality
Handles SMS sending with circuit breaker, retry logic, and phone number normalization
"""
import os
import asyncio
import time
import hashlib
from typing import List, Dict, Optional, Union, Any
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException, TwilioException
from app.services.circuit_breaker import circuit_breaker_manager
from app.obs.logging import get_logger
import logging

logger = get_logger(__name__)

class TwilioService:
    """Enhanced service for handling SMS functionality via Twilio with circuit breaker and retry logic."""
    
    def __init__(self, account_sid: Optional[str] = None, auth_token: Optional[str] = None):
        """
        Initialize the Twilio service.
        
        Args:
            account_sid: Twilio account SID (defaults to environment variable)
            auth_token: Twilio auth token (defaults to environment variable)
        """
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.getenv("TWILIO_FROM_NUMBER", "")
        self.callback_number = os.getenv("TWILIO_CALLBACK_NUMBER", "")
        
        # Initialize Twilio client lazily (only when needed)
        self.client = None
        
        # Circuit breaker for Twilio API
        self.circuit_breaker = circuit_breaker_manager.get_breaker(
            name="twilio_sms",
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=TwilioException
        )
    
    def _get_client(self):
        """Get Twilio client, creating it if needed."""
        if self.client is None:
            if not self.account_sid or not self.auth_token:
                raise ValueError("Twilio credentials not configured. Please set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables.")
            self.client = Client(self.account_sid, self.auth_token)
        return self.client
        
    async def send_sms(
        self, 
        to: str, 
        body: str, 
        from_number: Optional[str] = None,
        tenant_id: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Dict:
        """
        Send an SMS message with circuit breaker and retry logic.
        
        Args:
            to: Recipient phone number
            body: Message content
            from_number: Optional override for the from number
            tenant_id: Tenant ID for isolation
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries (exponential backoff)
            
        Returns:
            dict: Response from Twilio API with message details
        """
        # Generate idempotency key
        idempotency_key = self._generate_idempotency_key(to, body, tenant_id)
        
        for attempt in range(max_retries + 1):
            try:
                # Use circuit breaker to protect against cascade failures
                result = await self.circuit_breaker.call(
                    self._send_sms_internal,
                    to=to,
                    body=body,
                    from_number=from_number,
                    idempotency_key=idempotency_key
                )
                
                logger.info(f"SMS sent successfully to {to}, attempt {attempt + 1}")
                return result
                
            except TwilioRestException as e:
                logger.warning(f"Twilio error sending SMS to {to}, attempt {attempt + 1}: {str(e)}")
                
                # Check if we should retry
                if attempt < max_retries and self._should_retry(e):
                    delay = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"Retrying SMS to {to} in {delay} seconds")
                    await asyncio.sleep(delay)
                    continue
                else:
                    return {
                        "status": "error",
                        "error": str(e),
                        "code": e.code,
                        "to": to,
                        "attempts": attempt + 1
                    }
                    
            except Exception as e:
                logger.error(f"Unexpected error sending SMS to {to}, attempt {attempt + 1}: {str(e)}")
                
                if attempt < max_retries:
                    delay = retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                else:
                    return {
                        "status": "error",
                        "error": str(e),
                        "to": to,
                        "attempts": attempt + 1
                    }
        
        # This should never be reached, but just in case
        return {
            "status": "error",
            "error": "Max retries exceeded",
            "to": to,
            "attempts": max_retries + 1
        }
    
    def _send_sms_internal(
        self, 
        to: str, 
        body: str, 
        from_number: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict:
        """Internal SMS sending method (called by circuit breaker)"""
        # Normalize the phone number
        to_number = self._normalize_phone_number(to)
        
        # Send the message
        message = self._get_client().messages.create(
            to=to_number,
            from_=from_number or self.from_number,
            body=body
        )
        
        return {
            "status": "success",
            "message_sid": message.sid,
            "to": to_number,
            "idempotency_key": idempotency_key
        }
    
    def _should_retry(self, exception: TwilioRestException) -> bool:
        """Determine if we should retry based on the exception"""
        # Retry on temporary errors
        retryable_codes = [429, 500, 502, 503, 504]  # Rate limit, server errors
        return exception.code in retryable_codes
    
    def _generate_idempotency_key(
        self, 
        to: str, 
        body: str, 
        tenant_id: Optional[str] = None
    ) -> str:
        """Generate idempotency key for SMS"""
        content = f"{tenant_id or 'default'}:{to}:{body}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
            
    def send_sales_rep_callback_message(self, phone_number: str, customer_name: str) -> Dict:
        """
        Send a callback message to a sales rep.
        
        Args:
            phone_number: Sales rep's phone number
            customer_name: Customer's name for the message
            
        Returns:
            dict: Status of the SMS delivery
        """
        body = f"Hi Sales Rep, please call us back at {self.callback_number} about your recent appointment with {customer_name}"
        return self.send_sms(to=phone_number, body=body)
        
    def send_customer_callback_message(self, phone_number: str) -> Dict:
        """
        Send a callback message to a customer.
        
        Args:
            phone_number: Customer's phone number
            
        Returns:
            dict: Status of the SMS delivery
        """
        body = f"Hi, please call us back at {self.callback_number} about your recent appointment"
        return self.send_sms(to=phone_number, body=body)
        
    def notify_sales_manager(self, manager_phone: str, unassigned_calls_count: int) -> Dict:
        """
        Notify a sales manager about unassigned calls.
        
        Args:
            manager_phone: Sales manager's phone number
            unassigned_calls_count: Number of unassigned calls
            
        Returns:
            dict: Status of the SMS delivery
        """
        body = f"You have {unassigned_calls_count} unassigned call{'s' if unassigned_calls_count != 1 else ''} that need attention. Please log in to the dashboard to review."
        return self.send_sms(to=manager_phone, body=body)
    
    def batch_send(self, recipients: List[str], body: str) -> List[Dict]:
        """
        Send the same message to multiple recipients.
        
        Args:
            recipients: List of phone numbers
            body: Message content
            
        Returns:
            list: List of response dicts for each message
        """
        results = []
        for recipient in recipients:
            result = self.send_sms(to=recipient, body=body)
            results.append(result)
        return results
    
    def _normalize_phone_number(self, phone_number: str) -> str:
        """
        Ensure phone number is in E.164 format.
        
        Args:
            phone_number: Input phone number
            
        Returns:
            str: Normalized phone number
        """
        # Strip all non-digit characters
        digits_only = ''.join(c for c in phone_number if c.isdigit())
        
        # Add country code if needed
        if len(digits_only) == 10:
            return f"+1{digits_only}"
        elif phone_number.startswith('+'):
            return phone_number  # Already in E.164 format
        else:
            return f"+{digits_only}"  # Add + prefix

# Create a singleton instance
twilio_service = TwilioService() 