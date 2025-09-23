"""
Redis pub/sub event bus for real-time transport.
Provides standardized event emission and message envelope format.
"""
import json
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, List
import redis
from app.config import settings
from app.obs.logging import get_logger
from app.obs.tracing import get_current_trace_id
from app.obs.metrics import record_cache_hit, record_cache_miss

logger = get_logger(__name__)

# Message size limit (32KB)
MAX_MESSAGE_SIZE = 32 * 1024

class EventBus:
    """Redis-based event bus for real-time messaging."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self._redis_client = None
        self._connect()
    
    def _connect(self):
        """Connect to Redis with error handling."""
        try:
            if self.redis_url:
                self._redis_client = redis.from_url(self.redis_url, decode_responses=True)
                # Test connection
                self._redis_client.ping()
                logger.info("Connected to Redis for event bus")
            else:
                logger.warning("No Redis URL configured - event bus disabled")
                self._redis_client = None
        except Exception as e:
            logger.error(f"Failed to connect to Redis event bus: {e}")
            self._redis_client = None
    
    @property
    def redis_client(self):
        """Get Redis client, reconnecting if needed."""
        if self._redis_client is None:
            self._connect()
        return self._redis_client
    
    def emit(
        self,
        event_name: str,
        payload: Dict[str, Any],
        *,
        tenant_id: str,
        user_id: Optional[str] = None,
        lead_id: Optional[str] = None,
        key: Optional[str] = None,
        severity: str = "info",
        version: str = "1"
    ) -> bool:
        """
        Emit an event to appropriate channels.
        
        Args:
            event_name: Kebab-case event name (e.g., 'telephony.call.received')
            payload: Event data payload
            tenant_id: Required tenant ID
            user_id: Optional user ID for user-specific events
            lead_id: Optional lead ID for lead-specific events
            key: Optional deduplication key
            severity: Event severity (info|warn|error)
            version: Message format version
        
        Returns:
            True if event was emitted successfully, False otherwise
        """
        if not self.redis_client:
            logger.warning("Event bus not available - skipping event emission")
            return False
        
        try:
            # Create message envelope
            envelope = self._create_envelope(
                event_name=event_name,
                payload=payload,
                tenant_id=tenant_id,
                user_id=user_id,
                lead_id=lead_id,
                key=key,
                severity=severity,
                version=version
            )
            
            # Check message size
            message_json = json.dumps(envelope)
            if len(message_json.encode('utf-8')) > MAX_MESSAGE_SIZE:
                # Create pointer message for large payloads
                envelope = self._create_pointer_message(envelope, payload)
                message_json = json.dumps(envelope)
                logger.warning(
                    f"Large payload truncated for event {event_name}",
                    extra={
                        "event": event_name,
                        "tenant_id": tenant_id,
                        "original_size": len(json.dumps(payload).encode('utf-8')),
                        "truncated_size": len(message_json.encode('utf-8'))
                    }
                )
            
            # Determine channels to publish to
            channels = self._get_channels(tenant_id, user_id, lead_id)
            
            # Publish to all relevant channels
            published_count = 0
            for channel in channels:
                try:
                    self.redis_client.publish(channel, message_json)
                    published_count += 1
                    record_cache_hit("event_publish")
                    logger.debug(
                        f"Published event to channel {channel}",
                        extra={
                            "event": event_name,
                            "channel": channel,
                            "tenant_id": tenant_id,
                            "trace_id": envelope.get("trace_id")
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to publish to channel {channel}: {e}")
                    record_cache_miss("event_publish")
            
            if published_count > 0:
                logger.info(
                    f"Event {event_name} published to {published_count} channels",
                    extra={
                        "event": event_name,
                        "channels": channels,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "lead_id": lead_id,
                        "trace_id": envelope.get("trace_id")
                    }
                )
                return True
            else:
                logger.error(f"Failed to publish event {event_name} to any channels")
                return False
                
        except Exception as e:
            logger.error(
                f"Failed to emit event {event_name}: {e}",
                extra={
                    "event": event_name,
                    "tenant_id": tenant_id,
                    "error": str(e)
                }
            )
            return False
    
    def _create_envelope(
        self,
        event_name: str,
        payload: Dict[str, Any],
        tenant_id: str,
        user_id: Optional[str],
        lead_id: Optional[str],
        key: Optional[str],
        severity: str,
        version: str
    ) -> Dict[str, Any]:
        """Create standardized message envelope."""
        envelope = {
            "version": version,
            "event": event_name,
            "ts": datetime.utcnow().isoformat() + "Z",
            "severity": severity,
            "trace_id": get_current_trace_id() or str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "data": payload
        }
        
        # Add optional fields
        if user_id:
            envelope["user_id"] = user_id
        if lead_id:
            envelope["lead_id"] = lead_id
        if key:
            envelope["key"] = key
        
        return envelope
    
    def _create_pointer_message(
        self,
        original_envelope: Dict[str, Any],
        original_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a pointer message for large payloads."""
        # Extract key identifiers from payload
        pointer_data = {}
        
        # Common identifiers to preserve
        id_fields = ["id", "call_id", "lead_id", "user_id", "appointment_id", "task_id"]
        for field in id_fields:
            if field in original_payload:
                pointer_data[field] = original_payload[field]
        
        # Add truncation info
        pointer_data["_truncated"] = True
        pointer_data["_original_size_bytes"] = len(json.dumps(original_payload).encode('utf-8'))
        pointer_data["_message"] = "Payload too large - fetch details via REST API"
        
        # Create new envelope with pointer data
        envelope = original_envelope.copy()
        envelope["data"] = pointer_data
        
        return envelope
    
    def _get_channels(
        self,
        tenant_id: str,
        user_id: Optional[str],
        lead_id: Optional[str]
    ) -> List[str]:
        """Get list of channels to publish to based on event context."""
        channels = []
        
        # Always publish to tenant channel
        channels.append(f"tenant:{tenant_id}:events")
        
        # Add user-specific channel if user_id provided
        if user_id:
            channels.append(f"user:{user_id}:tasks")
        
        # Add lead-specific channel if lead_id provided
        if lead_id:
            channels.append(f"lead:{lead_id}:timeline")
        
        return channels
    
    def validate_channel_access(
        self,
        channel: str,
        tenant_id: str,
        user_id: str
    ) -> bool:
        """
        Validate that a user can access a specific channel.
        
        Args:
            channel: Channel name to validate
            tenant_id: User's tenant ID
            user_id: User's ID
        
        Returns:
            True if access is allowed, False otherwise
        """
        try:
            # Parse channel format
            if channel.startswith(f"tenant:{tenant_id}:events"):
                # User can access their own tenant's events
                return True
            elif channel.startswith(f"user:{user_id}:tasks"):
                # User can access their own tasks
                return True
            elif channel.startswith(f"lead:") and channel.endswith(":timeline"):
                # For lead channels, we need to validate the lead belongs to the tenant
                # Extract lead_id from channel: lead:{lead_id}:timeline
                parts = channel.split(":")
                if len(parts) == 3 and parts[0] == "lead" and parts[2] == "timeline":
                    lead_id = parts[1]
                    # TODO: Validate lead belongs to tenant via database query
                    # For now, we'll allow it if the format is correct
                    logger.info(
                        f"Lead channel access granted (validation needed): {channel}",
                        extra={
                            "channel": channel,
                            "tenant_id": tenant_id,
                            "user_id": user_id,
                            "lead_id": lead_id
                        }
                    )
                    return True
            
            # Deny access to any other channels
            logger.warning(
                f"Channel access denied: {channel}",
                extra={
                    "channel": channel,
                    "tenant_id": tenant_id,
                    "user_id": user_id
                }
            )
            return False
            
        except Exception as e:
            logger.error(f"Error validating channel access: {e}")
            return False
    
    def is_valid_channel_format(self, channel: str) -> bool:
        """Validate channel name format using regex whitelist."""
        import re
        
        # Allowed channel patterns
        patterns = [
            r'^tenant:[a-zA-Z0-9_-]+:events$',
            r'^user:[a-zA-Z0-9_-]+:tasks$',
            r'^lead:[a-zA-Z0-9_-]+:timeline$'
        ]
        
        for pattern in patterns:
            if re.match(pattern, channel):
                return True
        
        return False


# Global event bus instance
event_bus = EventBus()


def emit(
    event_name: str,
    payload: Dict[str, Any],
    *,
    tenant_id: str,
    user_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    key: Optional[str] = None,
    severity: str = "info",
    version: str = "1"
) -> bool:
    """
    Convenience function to emit an event using the global event bus.
    
    See EventBus.emit() for parameter documentation.
    """
    return event_bus.emit(
        event_name=event_name,
        payload=payload,
        tenant_id=tenant_id,
        user_id=user_id,
        lead_id=lead_id,
        key=key,
        severity=severity,
        version=version
    )
