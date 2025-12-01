"""
Onboarding-related database models.
"""
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey, JSON, Text, Enum
from sqlalchemy.orm import relationship
from ..database import Base


class CallProvider(str, enum.Enum):
    """Call tracking provider enum."""
    CALLRAIL = "callrail"
    TWILIO = "twilio"


class IngestionStatus(str, enum.Enum):
    """Document ingestion status enum."""
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class DocumentCategory(str, enum.Enum):
    """Document category enum."""
    SOP = "sop"
    TRAINING = "training"
    REFERENCE = "reference"
    POLICY = "policy"


class Document(Base):
    """Document model for company document ingestion."""
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    category = Column(
        Enum(DocumentCategory, native_enum=False, name="document_category"),
        nullable=False
    )
    role_target = Column(String, nullable=True)  # "manager", "csr", "sales_rep", or None for all
    s3_url = Column(String, nullable=False)
    ingestion_job_id = Column(String, nullable=True)  # Shunya/UWC job ID
    ingestion_status = Column(
        Enum(IngestionStatus, native_enum=False, name="ingestion_status"),
        nullable=False,
        default=IngestionStatus.PENDING
    )
    metadata = Column(JSON, nullable=True)  # Additional document metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    company = relationship("Company", back_populates="documents")


class OnboardingEvent(Base):
    """Onboarding event log for tracking onboarding progress."""
    __tablename__ = "onboarding_events"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    step = Column(String, nullable=False)  # "company_basics", "call_tracking", etc.
    action = Column(String, nullable=False)  # "started", "completed", "failed", etc.
    metadata = Column(JSON, nullable=True)  # Additional event metadata
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    company = relationship("Company", back_populates="onboarding_events")
    user = relationship("User", back_populates="onboarding_events")

