"""
Event Service for OttoAI Platform
Handles event emission with proper tenant isolation, HMAC signatures, and Otto taxonomy
"""
import json
import hmac
import hashlib
import time
from datetime import datetime
from typing import Dict, Any, Optional
from app.realtime.bus import emit
from app.obs.logging import get_logger
from app.config import settings

logger = get_logger(__name__)

class EventService:
    """Service for emitting events with Otto security and taxonomy compliance"""
    
    def __init__(self):
        self.hmac_secret = settings.UWC_HMAC_SECRET or "default_secret"
        self.replay_window = 300  # 5 minutes
        self.processed_events = {}  # In production, use Redis
    
    def emit_missed_call_event(
        self,
        event_name: str,
        tenant_id: str,
        lead_id: int,
        payload: Dict[str, Any],
        event_id: Optional[str] = None
    ):
        """
        Emit missed call related events with Otto taxonomy
        
        Args:
            event_name: Event name from Otto taxonomy
            tenant_id: Tenant ID for isolation
            lead_id: Lead ID for correlation
            payload: Event payload
            event_id: Optional event ID (generated if not provided)
        """
        try:
            # Generate event ID if not provided
            if not event_id:
                event_id = f"{tenant_id}:{lead_id}:{int(time.time())}"
            
            # Create event with Otto taxonomy
            event_payload = {
                "event_id": event_id,
                "tenant_id": tenant_id,
                "company_id": tenant_id,  # Assuming tenant_id is company_id
                "lead_id": lead_id,
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": event_name,
                "data": payload
            }
            
            # Generate HMAC signature
            signature = self._generate_hmac_signature(event_payload)
            event_payload["signature"] = signature
            
            # Emit event
            emit(
                event_name=event_name,
                payload=event_payload,
                tenant_id=tenant_id,
                lead_id=lead_id
            )
            
            logger.info(f"Emitted event {event_name} for tenant {tenant_id}, lead {lead_id}")
            
        except Exception as e:
            logger.error(f"Error emitting event {event_name}: {str(e)}")
    
    def emit_sms_event(
        self,
        event_name: str,
        tenant_id: str,
        lead_id: int,
        phone_number: str,
        message_sid: str,
        direction: str,
        payload: Dict[str, Any] = None
    ):
        """
        Emit SMS related events
        
        Args:
            event_name: Event name
            tenant_id: Tenant ID
            lead_id: Lead ID
            phone_number: Phone number
            message_sid: Twilio message SID
            direction: "inbound" or "outbound"
            payload: Additional payload data
        """
        sms_payload = {
            "phone_number": phone_number,
            "message_sid": message_sid,
            "direction": direction,
            "timestamp": datetime.utcnow().isoformat(),
            **(payload or {})
        }
        
        self.emit_missed_call_event(
            event_name=event_name,
            tenant_id=tenant_id,
            lead_id=lead_id,
            payload=sms_payload
        )
    
    def emit_queue_event(
        self,
        event_name: str,
        tenant_id: str,
        lead_id: int,
        queue_id: int,
        status: str,
        payload: Dict[str, Any] = None
    ):
        """
        Emit queue processing events
        
        Args:
            event_name: Event name
            tenant_id: Tenant ID
            lead_id: Lead ID
            queue_id: Queue entry ID
            status: Queue status
            payload: Additional payload data
        """
        queue_payload = {
            "queue_id": queue_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            **(payload or {})
        }
        
        self.emit_missed_call_event(
            event_name=event_name,
            tenant_id=tenant_id,
            lead_id=lead_id,
            payload=queue_payload
        )
    
    def emit_compliance_event(
        self,
        event_name: str,
        tenant_id: str,
        lead_id: int,
        compliance_type: str,
        action: str,
        payload: Dict[str, Any] = None
    ):
        """
        Emit compliance related events
        
        Args:
            event_name: Event name
            tenant_id: Tenant ID
            lead_id: Lead ID
            compliance_type: Type of compliance event
            action: Action taken
            payload: Additional payload data
        """
        compliance_payload = {
            "compliance_type": compliance_type,
            "action": action,
            "timestamp": datetime.utcnow().isoformat(),
            **(payload or {})
        }
        
        self.emit_missed_call_event(
            event_name=event_name,
            tenant_id=tenant_id,
            lead_id=lead_id,
            payload=compliance_payload
        )
    
    def _generate_hmac_signature(self, payload: Dict[str, Any]) -> str:
        """Generate HMAC signature for event payload"""
        try:
            # Create canonical string from payload
            canonical_string = json.dumps(payload, sort_keys=True, separators=(',', ':'))
            
            # Generate HMAC signature
            signature = hmac.new(
                self.hmac_secret.encode('utf-8'),
                canonical_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return signature
            
        except Exception as e:
            logger.error(f"Error generating HMAC signature: {str(e)}")
            return ""
    
    def verify_event_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        """Verify HMAC signature for incoming events"""
        try:
            # Remove signature from payload for verification
            payload_copy = payload.copy()
            payload_copy.pop("signature", None)
            
            # Generate expected signature
            expected_signature = self._generate_hmac_signature(payload_copy)
            
            # Compare signatures
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Error verifying event signature: {str(e)}")
            return False
    
    def is_event_replay(self, event_id: str) -> bool:
        """Check if event is a replay attack"""
        try:
            current_time = time.time()
            
            # Check if event ID already processed
            if event_id in self.processed_events:
                return True
            
            # Add to processed events with timestamp
            self.processed_events[event_id] = current_time
            
            # Clean up old events (older than replay window)
            self._cleanup_old_events(current_time)
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking event replay: {str(e)}")
            return True  # Err on the side of caution
    
    def _cleanup_old_events(self, current_time: float):
        """Clean up old processed events"""
        try:
            cutoff_time = current_time - self.replay_window
            
            # Remove events older than replay window
            old_events = [
                event_id for event_id, timestamp in self.processed_events.items()
                if timestamp < cutoff_time
            ]
            
            for event_id in old_events:
                del self.processed_events[event_id]
                
        except Exception as e:
            logger.error(f"Error cleaning up old events: {str(e)}")

# Global event service instance
event_service = EventService()













