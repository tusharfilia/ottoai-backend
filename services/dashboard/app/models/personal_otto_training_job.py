"""
Personal Otto Training Job model for tracking AI clone training status.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Enum, Index
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime
import enum


class PersonalOttoTrainingStatus(str, enum.Enum):
    """Training job status enum."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PersonalOttoTrainingJob(Base):
    """
    Tracks Personal Otto (AI clone) training jobs for sales reps.
    
    Stores training status, job metadata, and links to Shunya job IDs
    for idempotency and status tracking.
    """
    __tablename__ = "personal_otto_training_jobs"
    
    # Primary key
    id = Column(String, primary_key=True)  # UUID
    
    # Foreign keys
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    rep_id = Column(String, nullable=False, index=True)  # Sales rep user ID
    
    # Status tracking
    status = Column(
        Enum(PersonalOttoTrainingStatus, native_enum=False, name="personal_otto_status"),
        nullable=False,
        default=PersonalOttoTrainingStatus.PENDING
    )
    
    # Shunya integration
    shunya_job_id = Column(String, nullable=True, index=True)  # Shunya job ID for tracking
    
    # Training metadata
    last_trained_at = Column(DateTime, nullable=True)  # When training last completed successfully
    last_error = Column(String, nullable=True)  # Last error message if failed
    job_metadata = Column(JSON, nullable=True)  # Additional metadata (model_version, progress, etc.)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    
    # Multi-tenant performance indexes
    __table_args__ = (
        Index('ix_personal_otto_company_rep', 'company_id', 'rep_id'),  # Fast lookup by company + rep
        Index('ix_personal_otto_status', 'company_id', 'status'),  # Filter by status
        Index('ix_personal_otto_shunya_job', 'shunya_job_id'),  # Lookup by Shunya job ID
    )
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "company_id": self.company_id,
            "rep_id": self.rep_id,
            "status": self.status.value if self.status else None,
            "shunya_job_id": self.shunya_job_id,
            "last_trained_at": self.last_trained_at.isoformat() if self.last_trained_at else None,
            "last_error": self.last_error,
            "job_metadata": self.job_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

