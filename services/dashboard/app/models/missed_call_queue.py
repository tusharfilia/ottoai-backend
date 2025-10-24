"""
Database models for Missed Call Queue System
Implements systematic processing of missed calls with SLA management
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Enum, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
from datetime import datetime
import enum

class MissedCallStatus(str, enum.Enum):
    """Status of missed call recovery"""
    QUEUED = "queued"                    # Just missed, in queue
    PROCESSING = "processing"            # AI recovery in progress
    AI_RESCUED_PENDING = "ai_rescued_pending"  # Customer responded, pending
    RECOVERED = "recovered"              # Successfully converted
    ESCALATED = "escalated"              # Sent to human CSR
    FAILED = "failed"                    # Could not recover
    EXPIRED = "expired"                  # SLA deadline passed

class MissedCallPriority(str, enum.Enum):
    """Priority levels for missed calls"""
    HIGH = "high"        # New customers, high-value leads
    MEDIUM = "medium"    # Existing customers
    LOW = "low"          # Low-value or repeat missed calls

class MissedCallQueue(Base):
    """Main missed call queue table"""
    __tablename__ = "missed_call_queue"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.call_id"), nullable=False)
    customer_phone = Column(String, nullable=False, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    
    # Queue management
    status = Column(Enum(MissedCallStatus), default=MissedCallStatus.QUEUED, nullable=False)
    priority = Column(Enum(MissedCallPriority), default=MissedCallPriority.MEDIUM, nullable=False)
    
    # SLA management
    sla_deadline = Column(DateTime, nullable=False)  # 2-hour response deadline
    escalation_deadline = Column(DateTime, nullable=False)  # 48-hour escalation deadline
    
    # Processing tracking
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    last_attempt_at = Column(DateTime, nullable=True)
    next_attempt_at = Column(DateTime, nullable=True)
    
    # Recovery tracking
    ai_rescue_attempted = Column(Boolean, default=False, nullable=False)
    customer_responded = Column(Boolean, default=False, nullable=False)
    recovery_method = Column(String, nullable=True)  # "sms", "call", "email"
    
    # Context and metadata
    customer_type = Column(String, nullable=True)  # "new", "existing", "unknown"
    lead_value = Column(Float, nullable=True)  # Estimated lead value
    conversation_context = Column(Text, nullable=True)  # JSON context
    
    # Compliance tracking
    consent_status = Column(String(50), default="pending", nullable=False)  # "pending", "granted", "denied", "withdrawn"
    opt_out_reason = Column(Text, nullable=True)  # Reason for opt-out
    consent_granted_at = Column(DateTime, nullable=True)  # When consent was granted
    consent_withdrawn_at = Column(DateTime, nullable=True)  # When consent was withdrawn
    
    # Data privacy
    phone_number_encrypted = Column(Text, nullable=True)  # Encrypted phone number
    data_retention_expires_at = Column(DateTime, nullable=True)  # When data should be deleted
    
    # Business hours and timezone
    business_hours_override = Column(Boolean, default=False, nullable=False)  # Override business hours
    customer_timezone = Column(String(50), nullable=True)  # Customer's timezone
    preferred_contact_time = Column(String(20), nullable=True)  # "morning", "afternoon", "evening"
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    processed_at = Column(DateTime, nullable=True)
    escalated_at = Column(DateTime, nullable=True)
    
    # Relationships
    call = relationship("Call", backref="missed_call_queue_entries")
    company = relationship("Company", backref="missed_call_queue_entries")
    
    def __repr__(self):
        return f"<MissedCallQueue(id={self.id}, phone={self.customer_phone}, status={self.status})>"

class MissedCallAttempt(Base):
    """Track individual recovery attempts"""
    __tablename__ = "missed_call_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    queue_id = Column(Integer, ForeignKey("missed_call_queue.id"), nullable=False)
    
    # Attempt details
    attempt_number = Column(Integer, nullable=False)
    method = Column(String, nullable=False)  # "sms", "call", "email"
    message_sent = Column(Text, nullable=True)  # SMS content sent
    response_received = Column(Text, nullable=True)  # Customer response
    
    # AI processing
    ai_intent_analysis = Column(Text, nullable=True)  # JSON intent analysis
    ai_response_generated = Column(Text, nullable=True)  # AI-generated response
    confidence_score = Column(Float, nullable=True)  # AI confidence
    
    # Results
    success = Column(Boolean, default=False, nullable=False)
    customer_engaged = Column(Boolean, default=False, nullable=False)
    escalation_triggered = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    attempted_at = Column(DateTime, default=func.now(), nullable=False)
    responded_at = Column(DateTime, nullable=True)
    
    # Relationships
    queue_entry = relationship("MissedCallQueue", backref="attempts")
    
    def __repr__(self):
        return f"<MissedCallAttempt(id={self.id}, queue_id={self.queue_id}, method={self.method})>"

class MissedCallSLA(Base):
    """SLA configuration and tracking"""
    __tablename__ = "missed_call_sla"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    
    # SLA settings
    response_time_hours = Column(Integer, default=2, nullable=False)  # Hours to respond
    escalation_time_hours = Column(Integer, default=48, nullable=False)  # Hours to escalate
    max_retries = Column(Integer, default=3, nullable=False)
    
    # Business hours (optional)
    business_hours_start = Column(String, default="09:00", nullable=False)
    business_hours_end = Column(String, default="17:00", nullable=False)
    business_days = Column(String, default="1,2,3,4,5", nullable=False)  # Mon-Fri
    
    # AI settings
    ai_enabled = Column(Boolean, default=True, nullable=False)
    ai_confidence_threshold = Column(Float, default=0.7, nullable=False)
    escalation_ai_failure = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    company = relationship("Company", backref="missed_call_sla")
    
    def __repr__(self):
        return f"<MissedCallSLA(id={self.id}, company_id={self.company_id}, response_hours={self.response_time_hours})>"
