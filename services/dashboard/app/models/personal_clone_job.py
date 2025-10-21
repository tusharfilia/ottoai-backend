"""
Personal Clone Job model for tracking voice/style clone training jobs.
Enables reps to have AI that mimics their personal communication style.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON, Index, Enum, Float
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime
import enum


class TrainingStatus(str, enum.Enum):
    """Status of personal clone training job."""
    PENDING = "pending"  # Queued, not started
    PROCESSING = "processing"  # Training in progress
    COMPLETED = "completed"  # Successfully trained
    FAILED = "failed"  # Training failed


class TrainingDataType(str, enum.Enum):
    """Type of training data used."""
    CALLS = "calls"  # Phone call recordings
    VIDEOS = "videos"  # Reels, shorts, presentations
    TRANSCRIPTS = "transcripts"  # Text-only data
    MIXED = "mixed"  # Combination


class PersonalCloneJob(Base):
    """
    Tracks personal voice/style clone training jobs.
    
    Features:
    - Training data tracking (what was used)
    - Progress monitoring
    - Quality scoring
    - Model versioning
    - Retry support for failed jobs
    """
    __tablename__ = "personal_clone_jobs"
    
    # Primary key
    id = Column(String, primary_key=True)  # UUID
    
    # Foreign keys (with indexes)
    tenant_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    rep_id = Column(String, ForeignKey("sales_reps.user_id"), nullable=False, index=True)
    
    # Training Data
    training_data_type = Column(Enum(TrainingDataType), nullable=False)
    training_call_ids = Column(JSON, nullable=True)  # [call_id_1, call_id_2, ...]
    training_media_urls = Column(JSON, nullable=True)  # [url_1, url_2, ...] for videos
    total_audio_duration_seconds = Column(Integer, nullable=True)
    total_media_count = Column(Integer, default=0)
    
    # UWC Job Tracking
    uwc_job_id = Column(String, index=True, unique=True, nullable=False)
    status = Column(Enum(TrainingStatus), default=TrainingStatus.PENDING, nullable=False, index=True)
    progress_percent = Column(Integer, default=0)  # 0-100
    
    # Training Progress Details
    current_epoch = Column(Integer, nullable=True)
    total_epochs = Column(Integer, nullable=True)
    loss = Column(Float, nullable=True)  # Training loss metric
    accuracy = Column(Float, nullable=True)  # Training accuracy
    
    # Results
    model_id = Column(String, nullable=True)  # UWC's model identifier
    model_version = Column(String, nullable=True)  # Version/iteration
    quality_score = Column(Integer, nullable=True)  # 0-100 (UWC's quality assessment)
    
    # Error Handling
    error_message = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)
    last_retry_at = Column(DateTime, nullable=True)
    
    # Metadata
    initiated_by = Column(String, ForeignKey("users.id"), nullable=True)  # Who started training
    notes = Column(Text, nullable=True)  # Optional notes about training data
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", foreign_keys=[tenant_id])
    rep = relationship("SalesRep", foreign_keys=[rep_id])
    initiator = relationship("User", foreign_keys=[initiated_by])
    
    # Multi-tenant performance indexes
    __table_args__ = (
        Index('ix_clone_jobs_tenant_rep', 'tenant_id', 'rep_id'),  # Rep's training history
        Index('ix_clone_jobs_uwc_job', 'uwc_job_id', unique=True),  # UWC correlation
        Index('ix_clone_jobs_status', 'status'),  # Filter by status
        Index('ix_clone_jobs_tenant_status', 'tenant_id', 'status'),  # Tenant's active jobs
        Index('ix_clone_jobs_rep_created', 'rep_id', 'created_at'),  # Rep's job timeline
    )
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "rep_id": self.rep_id,
            "training_data_type": self.training_data_type.value if self.training_data_type else None,
            "training_call_ids": self.training_call_ids,
            "training_media_urls": self.training_media_urls,
            "total_audio_duration_seconds": self.total_audio_duration_seconds,
            "total_media_count": self.total_media_count,
            "uwc_job_id": self.uwc_job_id,
            "status": self.status.value if self.status else None,
            "progress_percent": self.progress_percent,
            "current_epoch": self.current_epoch,
            "total_epochs": self.total_epochs,
            "loss": self.loss,
            "accuracy": self.accuracy,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "quality_score": self.quality_score,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
    
    @property
    def is_active(self) -> bool:
        """Check if job is still active (pending or processing)."""
        return self.status in [TrainingStatus.PENDING, TrainingStatus.PROCESSING]
    
    @property
    def duration_seconds(self) -> int:
        """Calculate job duration in seconds."""
        if not self.started_at:
            return 0
        
        end_time = self.completed_at or datetime.utcnow()
        return int((end_time - self.started_at).total_seconds())



