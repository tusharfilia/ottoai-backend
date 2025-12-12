"""
Lightweight domain event helper for first-class entities.
"""
from typing import Any, Dict

from app.realtime.bus import emit as emit_event
from app.obs.logging import get_logger

logger = get_logger(__name__)


def emit_domain_event(
    *,
    event_name: str,
    tenant_id: str,
    payload: Dict[str, Any],
    lead_id: str | None = None,
) -> None:
    """
    Emit a structured domain event to the tenant event stream.
    """
    try:
        emit_event(
            event_name=event_name,
            payload=payload,
            tenant_id=tenant_id,
            lead_id=lead_id,
            severity="info",
            version="1",
        )
    except Exception as exc:
        logger.error(
            "Failed to emit domain event",
            extra={
                "event_name": event_name,
                "tenant_id": tenant_id,
                "payload": payload,
                "error": str(exc),
            },
        )













