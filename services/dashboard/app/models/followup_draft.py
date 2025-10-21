"""
Follow-Up Draft model for AI-generated follow-up messages.
Stores SMS, email, and call script drafts with approval workflow tracking.
"""
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON, Index, Boolean, Enum
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime
import enum


class DraftType(str, enum.Enum):
    """Type of follow-up draft."""
    SMS = "sms"
    EMAIL = "email"
    CALL_SCRIPT = "call_script"


class DraftStatus(str, enum.Enum):
    """Draft approval/usage status."""
    PENDING = "pending"  # Generated, awaiting review
    APPROVED = "approved"  # Human approved
    SENT = "sent"  # Actually sent to customer
    REJECTED = "rejected"  # Human rejected
    EXPIRED = "expired"  # Not used within time window


class FollowUpDraft(Base):
    """
    Stores AI-generated follow-up message drafts.
    
    Features:
    - Multiple draft types (SMS, email, call script)
    - Human-in-the-loop approval workflow
    - Modification tracking (did human edit before sending?)
    - Quiet hours compliance
    - Personal clone vs generic draft tracking
    - Usage analytics
    """
    __tablename__ = "followup_drafts"
    
    # Primary key
    id = Column(String, primary_key=True)  # UUID
    
    # Foreign keys (with indexes)
    tenant_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    call_id = Column(Integer, ForeignKey("calls.call_id"), nullable=False, index=True)
    generated_for = Column(String, ForeignKey("users.id"), nullable=False)  # Rep who will use it
    generated_by = Column(String, nullable=True)  # "personal_clone" or "generic_ai"
    
    # Draft Content
    draft_text = Column(Text, nullable=False)
    draft_type = Column(Enum(DraftType), nullable=False)
    tone = Column(String, nullable=True)  # "professional", "friendly", "urgent", "casual"
    
    # AI Generation Metadata
    uwc_request_id = Column(String, nullable=True)
    prompt_context = Column(JSON, nullable=True)  # Context used to generate
    # Format: {"call_summary": "...", "objections": ["price"], "customer_name": "John"}
    
    generation_time_ms = Column(Integer, nullable=True)
    model_version = Column(String, nullable=True)
    
    # Approval Workflow
    status = Column(Enum(DraftStatus), default=DraftStatus.PENDING, nullable=False, index=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Usage Tracking
    used = Column(Boolean, default=False, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    modified_before_send = Column(Boolean, default=False)  # Did human edit it?
    final_text = Column(Text, nullable=True)  # If modified, store final version
    
    # Quiet Hours Tracking
    blocked_by_quiet_hours = Column(Boolean, default=False)
    scheduled_send_time = Column(DateTime, nullable=True)  # If delayed due to quiet hours
    
    # Customer Response (for effectiveness tracking)
    customer_responded = Column(Boolean, nullable=True)
    customer_response_time_hours = Column(Integer, nullable=True)
    led_to_booking = Column(Boolean, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # Auto-generated drafts expire after 7 days
    
    # Relationships
    company = relationship("Company", foreign_keys=[tenant_id])
    call = relationship("Call", foreign_keys=[call_id])
    recipient = relationship("User", foreign_keys=[generated_for])
    approver = relationship("User", foreign_keys=[approved_by])
    
    # Multi-tenant performance indexes
    __table_args__ = (
        Index('ix_drafts_tenant_call', 'tenant_id', 'call_id'),  # Find drafts for call
        Index('ix_drafts_tenant_user', 'tenant_id', 'generated_for'),  # Rep's drafts
        Index('ix_drafts_tenant_status', 'tenant_id', 'status'),  # Filter by status
        Index('ix_drafts_tenant_created', 'tenant_id', 'created_at'),  # Recent drafts
        Index('ix_drafts_user_pending', 'generated_for', 'status'),  # Rep's pending approvals
        Index('ix_drafts_type_created', 'draft_type', 'created_at'),  # Analytics by type
    )
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "call_id": self.call_id,
            "generated_for": self.generated_for,
            "generated_by": self.generated_by,
            "draft_text": self.draft_text,
            "draft_type": self.draft_type.value if self.draft_type else None,
            "tone": self.tone,
            "status": self.status.value if self.status else None,
            "used": self.used,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "modified_before_send": self.modified_before_send,
            "final_text": self.final_text,
            "blocked_by_quiet_hours": self.blocked_by_quiet_hours,
            "scheduled_send_time": self.scheduled_send_time.isoformat() if self.scheduled_send_time else None,
            "customer_responded": self.customer_responded,
            "led_to_booking": self.led_to_booking,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }



