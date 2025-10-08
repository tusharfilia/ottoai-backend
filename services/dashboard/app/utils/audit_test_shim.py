"""
Audit logging shim for testing purposes.
This provides a simple audit logging interface that tests can hook into.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Create a test logger
test_logger = logging.getLogger("audit_test")

def log_audit(tenant_id: str, user_id: str, action: str, details: Optional[Dict[str, Any]] = None):
    """
    Log an audit entry for testing.
    
    Args:
        tenant_id: The tenant ID
        user_id: The user ID  
        action: The action performed
        details: Optional additional details
    """
    audit_entry = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "action": action,
        "details": details or {},
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    test_logger.info(f"AUDIT: {audit_entry}")
    return audit_entry

def get_audit_entries():
    """Get all audit entries logged during tests."""
    # This would be implemented with a proper audit store in production
    # For testing, we'll use the log capture mechanism
    return []
