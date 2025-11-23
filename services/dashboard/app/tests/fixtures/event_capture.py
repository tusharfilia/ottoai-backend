"""
Event capture fixture for testing event emissions.

Captures events emitted via the EventBus for assertions in tests.
"""
from typing import List, Dict, Any, Optional
from unittest.mock import patch, MagicMock
import pytest


class EventCapture:
    """Captures events for testing."""
    
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self._original_emit = None
    
    def capture_event(
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
        Capture an event instead of emitting it.
        
        This replaces the real emit function in tests.
        """
        self.events.append({
            "event_name": event_name,
            "payload": payload,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "lead_id": lead_id,
            "key": key,
            "severity": severity,
            "version": version,
        })
        return True
    
    def get_events(self, event_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get captured events, optionally filtered by event_name."""
        if event_name:
            return [e for e in self.events if e["event_name"] == event_name]
        return self.events
    
    def clear(self):
        """Clear captured events."""
        self.events = []
    
    def assert_event_emitted(
        self,
        event_name: str,
        **filters
    ) -> Dict[str, Any]:
        """
        Assert that an event was emitted with the given name and filters.
        
        Args:
            event_name: Expected event name
            **filters: Additional filters (tenant_id, lead_id, etc.)
        
        Returns:
            The first matching event
        
        Raises:
            AssertionError: If no matching event is found
        """
        matching_events = self.get_events(event_name)
        
        if not matching_events:
            raise AssertionError(f"Event '{event_name}' was not emitted")
        
        # Apply filters
        for event in matching_events:
            matches = True
            for key, value in filters.items():
                if event.get(key) != value:
                    matches = False
                    break
            if matches:
                return event
        
        raise AssertionError(
            f"Event '{event_name}' was emitted but no event matched filters: {filters}"
        )


@pytest.fixture
def event_capture(monkeypatch):
    """
    Fixture that captures events for testing.
    
    Usage:
        def test_something(event_capture):
            # ... do something that emits events ...
            event_capture.assert_event_emitted("lead.created", tenant_id="test_123")
    """
    capture = EventCapture()
    
    # Patch the emit function to capture instead of emitting
    from app.realtime.bus import emit as real_emit
    
    def mock_emit(*args, **kwargs):
        return capture.capture_event(*args, **kwargs)
    
    # Monkey patch the emit function
    monkeypatch.setattr("app.realtime.bus.emit", mock_emit)
    monkeypatch.setattr("app.services.shunya_integration_service.emit", mock_emit)
    
    yield capture
    
    # Cleanup
    capture.clear()


