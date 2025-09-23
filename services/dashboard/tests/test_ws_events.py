"""
WebSocket event emission and handling tests.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from app.realtime.bus import emit, EventBus


class TestEventEmission:
    """Test event emission functionality."""
    
    @patch('redis.from_url')
    def test_emit_telephony_call_received(self, mock_redis):
        """Test emitting telephony.call.received event."""
        # Mock Redis client
        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.publish.return_value = 1
        mock_redis.return_value = mock_redis_client
        
        # Test event emission
        success = emit(
            event_name="telephony.call.received",
            payload={
                "call_id": "call-123",
                "phone_number": "+1234567890",
                "company_id": "company-456",
                "answered": True
            },
            tenant_id="tenant-123",
            lead_id="call-123"
        )
        
        assert success is True
        
        # Verify Redis publish was called
        mock_redis_client.publish.assert_called()
        
        # Get published messages
        publish_calls = mock_redis_client.publish.call_args_list
        
        # Should publish to tenant and lead channels
        channels_published = [call[0][0] for call in publish_calls]
        assert "tenant:tenant-123:events" in channels_published
        assert "lead:call-123:timeline" in channels_published
        
        # Verify message envelope format
        message_data = json.loads(publish_calls[0][0][1])
        assert message_data["version"] == "1"
        assert message_data["event"] == "telephony.call.received"
        assert "ts" in message_data
        assert message_data["severity"] == "info"
        assert "trace_id" in message_data
        assert message_data["tenant_id"] == "tenant-123"
        assert message_data["lead_id"] == "call-123"
        assert "data" in message_data
        
        # Verify payload
        payload = message_data["data"]
        assert payload["call_id"] == "call-123"
        assert payload["phone_number"] == "+1234567890"
        assert payload["company_id"] == "company-456"
        assert payload["answered"] is True
    
    @patch('redis.from_url')
    def test_emit_telephony_call_completed(self, mock_redis):
        """Test emitting telephony.call.completed event."""
        # Mock Redis client
        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.publish.return_value = 1
        mock_redis.return_value = mock_redis_client
        
        # Test event emission
        success = emit(
            event_name="telephony.call.completed",
            payload={
                "call_id": "call-123",
                "phone_number": "+1234567890",
                "company_id": "company-456",
                "booked": True,
                "qualified": True,
                "objections": ["price", "timing"],
                "quote_date": "2025-09-21T10:00:00Z"
            },
            tenant_id="tenant-123",
            lead_id="call-123"
        )
        
        assert success is True
        
        # Verify message envelope
        publish_calls = mock_redis_client.publish.call_args_list
        message_data = json.loads(publish_calls[0][0][1])
        
        assert message_data["event"] == "telephony.call.completed"
        assert message_data["tenant_id"] == "tenant-123"
        assert message_data["lead_id"] == "call-123"
        
        # Verify payload
        payload = message_data["data"]
        assert payload["call_id"] == "call-123"
        assert payload["booked"] is True
        assert payload["qualified"] is True
        assert payload["objections"] == ["price", "timing"]
    
    @patch('redis.from_url')
    def test_emit_system_webhook_processed(self, mock_redis):
        """Test emitting system.webhook.processed event."""
        # Mock Redis client
        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.publish.return_value = 1
        mock_redis.return_value = mock_redis_client
        
        # Test event emission
        success = emit(
            event_name="system.webhook.processed",
            payload={
                "provider": "callrail",
                "external_id": "call-123",
                "webhook_type": "call-complete",
                "processing_time_ms": 150.5
            },
            tenant_id="tenant-123"
        )
        
        assert success is True
        
        # Verify message envelope
        publish_calls = mock_redis_client.publish.call_args_list
        message_data = json.loads(publish_calls[0][0][1])
        
        assert message_data["event"] == "system.webhook.processed"
        assert message_data["tenant_id"] == "tenant-123"
        
        # Verify payload
        payload = message_data["data"]
        assert payload["provider"] == "callrail"
        assert payload["external_id"] == "call-123"
        assert payload["webhook_type"] == "call-complete"
    
    @patch('redis.from_url')
    def test_emit_user_task_event(self, mock_redis):
        """Test emitting user task events."""
        # Mock Redis client
        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.publish.return_value = 1
        mock_redis.return_value = mock_redis_client
        
        # Test event emission
        success = emit(
            event_name="task.updated",
            payload={
                "task_id": "task-123",
                "type": "follow_up",
                "status": "assigned",
                "due_date": "2025-09-21T15:00:00Z",
                "lead_id": "lead-456"
            },
            tenant_id="tenant-123",
            user_id="user-789"
        )
        
        assert success is True
        
        # Should publish to both tenant and user channels
        publish_calls = mock_redis_client.publish.call_args_list
        channels_published = [call[0][0] for call in publish_calls]
        
        assert "tenant:tenant-123:events" in channels_published
        assert "user:user-789:tasks" in channels_published


class TestMessageEnvelope:
    """Test message envelope format and validation."""
    
    def test_message_envelope_structure(self):
        """Test that message envelope has required fields."""
        from app.realtime.bus import EventBus
        
        event_bus = EventBus(None)  # No Redis for this test
        
        envelope = event_bus._create_envelope(
            event_name="test.event",
            payload={"test": "data"},
            tenant_id="tenant-123",
            user_id="user-456",
            lead_id="lead-789",
            key="dedup-key",
            severity="warn",
            version="1"
        )
        
        # Verify required fields
        required_fields = ["version", "event", "ts", "severity", "trace_id", "tenant_id", "data"]
        for field in required_fields:
            assert field in envelope, f"Missing required field: {field}"
        
        # Verify optional fields
        assert envelope["user_id"] == "user-456"
        assert envelope["lead_id"] == "lead-789"
        assert envelope["key"] == "dedup-key"
        
        # Verify data types
        assert envelope["version"] == "1"
        assert envelope["event"] == "test.event"
        assert envelope["severity"] == "warn"
        assert envelope["tenant_id"] == "tenant-123"
        assert isinstance(envelope["data"], dict)
    
    def test_message_size_guard(self):
        """Test that large messages are truncated with pointers."""
        from app.realtime.bus import EventBus, MAX_MESSAGE_SIZE
        
        event_bus = EventBus(None)  # No Redis for this test
        
        # Create large payload
        large_data = "x" * (MAX_MESSAGE_SIZE + 1000)
        large_payload = {"large_field": large_data, "id": "test-123"}
        
        # Create envelope
        envelope = event_bus._create_envelope(
            event_name="test.large.event",
            payload=large_payload,
            tenant_id="tenant-123",
            user_id=None,
            lead_id=None,
            key=None,
            severity="info",
            version="1"
        )
        
        # Check if message would be too large
        message_json = json.dumps(envelope)
        if len(message_json.encode('utf-8')) > MAX_MESSAGE_SIZE:
            # Create pointer message
            pointer_envelope = event_bus._create_pointer_message(envelope, large_payload)
            
            # Verify pointer message structure
            assert pointer_envelope["data"]["_truncated"] is True
            assert "_original_size_bytes" in pointer_envelope["data"]
            assert pointer_envelope["data"]["id"] == "test-123"  # ID preserved
            
            # Verify pointer message is smaller
            pointer_json = json.dumps(pointer_envelope)
            assert len(pointer_json.encode('utf-8')) < MAX_MESSAGE_SIZE
    
    def test_channel_derivation(self):
        """Test that correct channels are derived from event context."""
        from app.realtime.bus import EventBus
        
        event_bus = EventBus(None)
        
        # Test tenant-only event
        channels = event_bus._get_channels("tenant-123", None, None)
        assert channels == ["tenant:tenant-123:events"]
        
        # Test tenant + user event
        channels = event_bus._get_channels("tenant-123", "user-456", None)
        assert "tenant:tenant-123:events" in channels
        assert "user:user-456:tasks" in channels
        
        # Test tenant + user + lead event
        channels = event_bus._get_channels("tenant-123", "user-456", "lead-789")
        assert "tenant:tenant-123:events" in channels
        assert "user:user-456:tasks" in channels
        assert "lead:lead-789:timeline" in channels


class TestEventCatalog:
    """Test that all defined events can be emitted properly."""
    
    @patch('redis.from_url')
    def test_telephony_events(self, mock_redis):
        """Test all telephony events."""
        # Mock Redis client
        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.publish.return_value = 1
        mock_redis.return_value = mock_redis_client
        
        telephony_events = [
            ("telephony.call.received", {"call_id": "123", "answered": True}),
            ("telephony.call.completed", {"call_id": "123", "booked": True}),
            ("telephony.sms.received", {"message_id": "456", "content": "Hello"}),
            ("telephony.sms.sent", {"message_id": "789", "to": "+1234567890"}),
            ("telephony.call.status", {"call_id": "123", "status": "completed"})
        ]
        
        for event_name, payload in telephony_events:
            success = emit(
                event_name=event_name,
                payload=payload,
                tenant_id="tenant-123"
            )
            assert success is True
    
    @patch('redis.from_url')
    def test_system_events(self, mock_redis):
        """Test all system events."""
        # Mock Redis client
        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.publish.return_value = 1
        mock_redis.return_value = mock_redis_client
        
        system_events = [
            ("system.webhook.processed", {"provider": "callrail", "external_id": "123"}),
            ("system.buffer_dropped", {"reason": "Queue overflow", "max_size": 100}),
            ("system.rate_limited", {"connection_id": "conn-123", "limit": "10/minute"})
        ]
        
        for event_name, payload in system_events:
            success = emit(
                event_name=event_name,
                payload=payload,
                tenant_id="tenant-123"
            )
            assert success is True
    
    @patch('redis.from_url')
    def test_identity_events(self, mock_redis):
        """Test identity/user events."""
        # Mock Redis client
        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True
        mock_redis_client.publish.return_value = 1
        mock_redis.return_value = mock_redis_client
        
        identity_events = [
            ("identity.user.created", {"user_id": "user-123", "email": "test@example.com"}),
            ("identity.user.updated", {"user_id": "user-123", "changes": ["email"]})
        ]
        
        for event_name, payload in identity_events:
            success = emit(
                event_name=event_name,
                payload=payload,
                tenant_id="tenant-123",
                user_id="user-123"
            )
            assert success is True


if __name__ == "__main__":
    pytest.main([__file__])
