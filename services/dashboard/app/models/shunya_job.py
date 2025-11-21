"""
ShunyaJob model for tracking async Shunya API jobs.

Tracks job lifecycle, handles idempotency, and manages retries.
"""
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
import uuid

from sqlalchemy import Column, String, Integer, JSON, DateTime, Index, UniqueConstraint, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class ShunyaJobType(str, PyEnum):
    """Type of Shunya job."""
    CSR_CALL = "csr_call"
    SALES_VISIT = "sales_visit"
    SEGMENTATION = "segmentation"


class ShunyaJobStatus(str, PyEnum):
    """Status of Shunya job."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ShunyaJob(Base):
    """
    Tracks async Shunya API jobs.
    
    Ensures idempotency and manages retries for CSR calls, sales visits, and segmentation.
    """
    __tablename__ = "shunya_jobs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    
    # Entity relationships (nullable for flexibility)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True, index=True)
    appointment_id = Column(String, ForeignKey("appointments.id"), nullable=True, index=True)
    contact_card_id = Column(String, ForeignKey("contact_cards.id"), nullable=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.call_id"), nullable=True)
    recording_session_id = Column(String, ForeignKey("recording_sessions.id"), nullable=True)
    
    # Job metadata
    job_type = Column(Enum(ShunyaJobType, native_enum=False), nullable=False, index=True)
    job_status = Column(Enum(ShunyaJobStatus, native_enum=False), nullable=False, index=True, default=ShunyaJobStatus.PENDING)
    
    # Shunya job ID (returned by Shunya API)
    shunya_job_id = Column(String, nullable=True, index=True)
    
    # Job payloads
    input_payload = Column(JSON, nullable=True, comment="Input sent to Shunya (audio_url, call_id, etc.)")
    output_payload = Column(JSON, nullable=True, comment="Normalized Shunya response")
    
    # Idempotency: hash of processed output to prevent duplicate processing
    processed_output_hash = Column(String, nullable=True, index=True, comment="SHA256 hash of output_payload for idempotency")
    
    # Retry management
    num_attempts = Column(Integer, default=0, nullable=False)
    last_attempt_at = Column(DateTime, nullable=True)
    max_attempts = Column(Integer, default=5, nullable=False)
    next_retry_at = Column(DateTime, nullable=True, index=True)
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Error tracking
    error_message = Column(String, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    lead = relationship("Lead", foreign_keys=[lead_id])
    appointment = relationship("Appointment", foreign_keys=[appointment_id])
    contact_card = relationship("ContactCard", foreign_keys=[contact_card_id])
    
    __table_args__ = (
        # Unique constraint: one job per Shunya job ID per company
        UniqueConstraint('company_id', 'shunya_job_id', name='uq_shunya_job_company_shunya_id'),
        
        # Indexes for common queries
        Index('ix_shunya_jobs_status', 'job_status'),
        Index('ix_shunya_jobs_retry', 'next_retry_at', 'job_status'),
        Index('ix_shunya_jobs_created', 'created_at'),
        Index('ix_shunya_jobs_lead_appt', 'lead_id', 'appointment_id'),
    )
    
    def __repr__(self):
        return f"<ShunyaJob(id={self.id}, job_type={self.job_type}, status={self.job_status}, shunya_job_id={self.shunya_job_id})>"

