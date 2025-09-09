import os
from typing import List, Dict, Optional, Union
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

class TwilioService:
    """Service for handling SMS functionality via Twilio."""
    
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
        
        # Initialize Twilio client
        self.client = Client(self.account_sid, self.auth_token)
        
    def send_sms(self, to: str, body: str, from_number: Optional[str] = None) -> Dict:
        """
        Send an SMS message.
        
        Args:
            to: Recipient phone number
            body: Message content
            from_number: Optional override for the from number
            
        Returns:
            dict: Response from Twilio API with message details
        """
        try:
            # Normalize the phone number
            to_number = self._normalize_phone_number(to)
            
            # Send the message
            message = self.client.messages.create(
                to=to_number,
                from_=from_number or self.from_number,
                body=body
            )
            
            logger.info(f"SMS sent successfully to {to_number}, SID: {message.sid}")
            return {
                "status": "success",
                "message_sid": message.sid,
                "to": to_number
            }
            
        except TwilioRestException as e:
            logger.error(f"Twilio error sending SMS to {to}: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "code": e.code,
                "to": to
            }
        except Exception as e:
            logger.error(f"Unexpected error sending SMS to {to}: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "to": to
            }
            
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