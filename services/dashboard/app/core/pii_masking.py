"""
PII (Personally Identifiable Information) masking utilities.
Ensures sensitive data is never logged in plain text.
"""
import re
import logging
from typing import Any, Dict, Optional
from app.obs.logging import get_logger

logger = get_logger(__name__)


class PIIMasker:
    """Utility class for masking PII in logs and data."""
    
    # Regex patterns for common PII
    PHONE_PATTERN = re.compile(r'(\+?1?[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})')
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    SSN_PATTERN = re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b')
    CREDIT_CARD_PATTERN = re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b')
    
    # Common name patterns (basic)
    NAME_PATTERNS = [
        re.compile(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'),  # First Last
        re.compile(r'\b[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+\b'),  # First M. Last
    ]
    
    @classmethod
    def mask_phone(cls, phone: str) -> str:
        """Mask phone number, keeping only last 4 digits."""
        if not phone:
            return phone
        
        # Extract digits only
        digits = re.sub(r'\D', '', phone)
        if len(digits) >= 4:
            return f"***-***-{digits[-4:]}"
        else:
            return "***-***-****"
    
    @classmethod
    def mask_email(cls, email: str) -> str:
        """Mask email address, keeping only first letter and domain."""
        if not email or '@' not in email:
            return email
        
        local, domain = email.split('@', 1)
        if len(local) > 1:
            masked_local = f"{local[0]}***"
        else:
            masked_local = "***"
        
        return f"{masked_local}@{domain}"
    
    @classmethod
    def mask_name(cls, name: str) -> str:
        """Mask full name, keeping only first letter of each part."""
        if not name:
            return name
        
        parts = name.strip().split()
        if len(parts) >= 2:
            return f"{parts[0][0]}*** {parts[-1][0]}***"
        elif len(parts) == 1:
            return f"{parts[0][0]}***"
        else:
            return "***"
    
    @classmethod
    def mask_address(cls, address: str) -> str:
        """Mask address, keeping only city/state."""
        if not address:
            return address
        
        # Simple masking - replace numbers and most text
        # Keep city/state if present
        words = address.split()
        masked_words = []
        
        for word in words:
            if word.isdigit():
                masked_words.append("***")
            elif len(word) > 3:
                masked_words.append(f"{word[0]}***")
            else:
                masked_words.append("***")
        
        return " ".join(masked_words)
    
    @classmethod
    def mask_transcript(cls, transcript: str, max_length: int = 100) -> str:
        """Mask transcript content, keeping only structure."""
        if not transcript:
            return transcript
        
        if len(transcript) <= max_length:
            return "***[TRANSCRIPT_MASKED]***"
        
        # Show first and last few characters
        start = transcript[:20]
        end = transcript[-20:]
        return f"{start}***[TRANSCRIPT_MASKED]***{end}"
    
    @classmethod
    def mask_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively mask PII in a dictionary."""
        if not isinstance(data, dict):
            return data
        
        masked = {}
        for key, value in data.items():
            key_lower = key.lower()
            
            # Mask based on field names
            if any(pii_field in key_lower for pii_field in ['phone', 'mobile', 'tel']):
                masked[key] = cls.mask_phone(str(value)) if value else value
            elif any(pii_field in key_lower for pii_field in ['email', 'mail']):
                masked[key] = cls.mask_email(str(value)) if value else value
            elif any(pii_field in key_lower for pii_field in ['name', 'first_name', 'last_name']):
                masked[key] = cls.mask_name(str(value)) if value else value
            elif any(pii_field in key_lower for pii_field in ['address', 'street', 'location']):
                masked[key] = cls.mask_address(str(value)) if value else value
            elif any(pii_field in key_lower for pii_field in ['transcript', 'conversation', 'call_text']):
                masked[key] = cls.mask_transcript(str(value)) if value else value
            elif isinstance(value, dict):
                masked[key] = cls.mask_dict(value)
            elif isinstance(value, list):
                masked[key] = [cls.mask_dict(item) if isinstance(item, dict) else item for item in value]
            else:
                masked[key] = value
        
        return masked
    
    @classmethod
    def mask_string(cls, text: str) -> str:
        """Mask PII in a string using regex patterns."""
        if not text:
            return text
        
        # Mask phone numbers
        text = cls.PHONE_PATTERN.sub(lambda m: cls.mask_phone(m.group(0)), text)
        
        # Mask email addresses
        text = cls.EMAIL_PATTERN.sub(lambda m: cls.mask_email(m.group(0)), text)
        
        # Mask SSNs
        text = cls.SSN_PATTERN.sub("***-**-****", text)
        
        # Mask credit cards
        text = cls.CREDIT_CARD_PATTERN.sub("****-****-****-****", text)
        
        return text


class PIISafeLogger:
    """Logger wrapper that automatically masks PII."""
    
    def __init__(self, name: str):
        self.logger = get_logger(name)
    
    def _mask_log_data(self, *args, **kwargs) -> tuple:
        """Mask PII in log arguments."""
        masked_args = []
        for arg in args:
            if isinstance(arg, dict):
                masked_args.append(PIIMasker.mask_dict(arg))
            elif isinstance(arg, str):
                masked_args.append(PIIMasker.mask_string(arg))
            else:
                masked_args.append(arg)
        
        masked_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, dict):
                masked_kwargs[key] = PIIMasker.mask_dict(value)
            elif isinstance(value, str):
                masked_kwargs[key] = PIIMasker.mask_string(value)
            else:
                masked_kwargs[key] = value
        
        return tuple(masked_args), masked_kwargs
    
    def debug(self, message: str, *args, **kwargs):
        """Log debug message with PII masking."""
        masked_args, masked_kwargs = self._mask_log_data(*args, **kwargs)
        self.logger.debug(message, *masked_args, **masked_kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Log info message with PII masking."""
        masked_args, masked_kwargs = self._mask_log_data(*args, **kwargs)
        self.logger.info(message, *masked_args, **masked_kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log warning message with PII masking."""
        masked_args, masked_kwargs = self._mask_log_data(*args, **kwargs)
        self.logger.warning(message, *masked_args, **masked_kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log error message with PII masking."""
        masked_args, masked_kwargs = self._mask_log_data(*args, **kwargs)
        self.logger.error(message, *masked_args, **masked_kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """Log critical message with PII masking."""
        masked_args, masked_kwargs = self._mask_log_data(*args, **kwargs)
        self.logger.critical(message, *masked_args, **masked_kwargs)


# Convenience function for getting PII-safe logger
def get_pii_safe_logger(name: str) -> PIISafeLogger:
    """Get a logger that automatically masks PII."""
    return PIISafeLogger(name)

