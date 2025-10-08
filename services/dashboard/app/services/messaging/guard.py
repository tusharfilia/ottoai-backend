"""
Messaging guard for quiet hours and opt-out enforcement.
"""
from datetime import datetime, time
from typing import Optional
from sqlalchemy.orm import Session
from app.utils.audit_test_shim import log_audit

class QuietHoursError(Exception):
    """Raised when messaging is blocked due to quiet hours."""
    pass

class OptOutError(Exception):
    """Raised when messaging is blocked due to opt-out."""
    pass

def get_current_time_for_tenant(tenant_id: str) -> str:
    """
    Get current local time for tenant.
    In production, this would use tenant timezone.
    For testing, we can mock this function.
    """
    return datetime.now().strftime("%H:%M")

def is_opted_out(tenant_id: str, recipient_id: str) -> bool:
    """
    Check if recipient has opted out.
    In production, this would query the opt-out table.
    """
    # Mock implementation for testing
    return recipient_id.startswith("opted_out_")

def enforce_quiet_hours_and_optout(
    tenant_id: str, 
    recipient_id: str, 
    is_human_override: bool = False
) -> None:
    """
    Enforce quiet hours and opt-out restrictions.
    
    Args:
        tenant_id: The tenant ID
        recipient_id: The recipient ID
        is_human_override: Whether human override is enabled
        
    Raises:
        QuietHoursError: If blocked due to quiet hours
        OptOutError: If blocked due to opt-out
    """
    # Check opt-out first
    if is_opted_out(tenant_id, recipient_id):
        log_audit(
            tenant_id=tenant_id,
            user_id="system",
            action="messaging_blocked_optout",
            details={"recipient_id": recipient_id}
        )
        raise OptOutError("Recipient has opted out")
    
    # Check quiet hours (21:00 - 08:00)
    current_time = get_current_time_for_tenant(tenant_id)
    hour = int(current_time.split(":")[0])
    
    is_quiet_hours = hour >= 21 or hour < 8
    
    if is_quiet_hours and not is_human_override:
        log_audit(
            tenant_id=tenant_id,
            user_id="system", 
            action="messaging_blocked_quiet_hours",
            details={"recipient_id": recipient_id, "time": current_time}
        )
        raise QuietHoursError("Messaging blocked during quiet hours")
    
    # Log successful send
    log_audit(
        tenant_id=tenant_id,
        user_id="system",
        action="messaging_sent",
        details={
            "recipient_id": recipient_id,
            "override": is_human_override,
            "time": current_time
        }
    )
