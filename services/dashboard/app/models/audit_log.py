"""
Audit Log model for security and compliance tracking.
Logs all sensitive operations for forensics and compliance audits.
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime


class AuditLog(Base):
    """
    Logs security-relevant events for compliance and forensics.
    
    What gets logged:
    - User creation/deletion
    - RBAC changes (role assignments)
    - Document uploads/deletions
    - Ask Otto queries (for audit trail)
    - Company setting changes
    - Data exports
    - GDPR deletion requests
    
    Features:
    - Immutable (never delete audit logs)
    - Tenant isolation
    - IP address tracking
    - Request context capture
    - Never expires (keep forever for compliance)
    """
    __tablename__ = "audit_logs"
    
    # Primary key
    id = Column(String, primary_key=True)  # UUID
    
    # Foreign keys (with indexes)
    tenant_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)  # Null for system actions
    
    # Action Details
    action = Column(String, nullable=False, index=True)
    # Examples: "user_created", "document_uploaded", "rag_query", "role_changed", "user_deleted"
    
    resource_type = Column(String, nullable=False, index=True)
    # Examples: "user", "document", "call", "company", "settings"
    
    resource_id = Column(String, nullable=False, index=True)
    # The ID of the resource that was acted upon
    
    # Change Details
    changes = Column(JSON, nullable=True)
    # Format: {"old_value": "manager", "new_value": "exec"} for role changes
    # Or: {"query": "What are top objections?"} for RAG queries
    
    metadata = Column(JSON, nullable=True)
    # Additional context: {"call_id": 123, "analysis_type": "coaching"}
    
    # Request Context
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(String, nullable=True, index=True)  # Correlation with logs/traces
    
    # Result
    success = Column(String, nullable=False)  # "success", "failure", "partial"
    error_message = Column(Text, nullable=True)  # If action failed
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    company = relationship("Company", foreign_keys=[tenant_id])
    user = relationship("User", foreign_keys=[user_id])
    
    # Multi-tenant performance indexes
    __table_args__ = (
        Index('ix_audit_tenant_action', 'tenant_id', 'action'),  # Filter by action type
        Index('ix_audit_tenant_created', 'tenant_id', 'created_at'),  # Chronological listing
        Index('ix_audit_user_action', 'user_id', 'action'),  # User's action history
        Index('ix_audit_resource', 'resource_type', 'resource_id'),  # Resource audit trail
        Index('ix_audit_request', 'request_id'),  # Correlation with logs
    )
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "changes": self.changes,
            "metadata": self.metadata,
            "ip_address": self.ip_address,
            "request_id": self.request_id,
            "success": self.success,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


