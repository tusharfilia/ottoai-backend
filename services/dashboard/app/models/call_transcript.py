"""
Call Transcript model for storing ASR (Automatic Speech Recognition) results from UWC.
Includes speaker diarization, confidence scores, and processing metadata.
"""
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime


class CallTranscript(Base):
    """
    Stores ASR transcription results from UWC.
    
    Features:
    - Tenant isolation (company_id)
    - Speaker diarization (separate customer vs rep speech)
    - Confidence scoring
    - UWC job tracking for correlation
    - Performance indexes for fast retrieval
    """
    __tablename__ = "call_transcripts"
    
    # Primary key
    id = Column(String, primary_key=True)  # UUID
    
    # Foreign keys (with indexes)
    call_id = Column(Integer, ForeignKey("calls.call_id"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    
    # UWC ASR Results
    uwc_job_id = Column(String, index=True, unique=True, nullable=False)  # Unique prevents duplicates
    transcript_text = Column(Text, nullable=False)  # Full transcript
    
    # Speaker Diarization
    speaker_labels = Column(JSON, nullable=True)
    # Format: [
    #   {"speaker": "rep", "text": "Hello, this is John", "start_time": 0.0, "end_time": 3.2},
    #   {"speaker": "customer", "text": "Hi, I need a quote", "start_time": 3.5, "end_time": 5.8}
    # ]
    
    # Quality Metrics
    confidence_score = Column(Float, nullable=True)  # 0.0 to 1.0
    language = Column(String, default="en-US", nullable=False)
    word_count = Column(Integer, nullable=True)
    
    # Processing Metadata
    processing_time_ms = Column(Integer, nullable=True)  # How long ASR took
    model_version = Column(String, nullable=True)  # UWC model version used
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    call = relationship("Call", foreign_keys=[call_id])
    company = relationship("Company", foreign_keys=[tenant_id])
    
    # Multi-tenant performance indexes
    __table_args__ = (
        Index('ix_transcripts_tenant_call', 'tenant_id', 'call_id'),  # Fast lookup by tenant + call
        Index('ix_transcripts_tenant_created', 'tenant_id', 'created_at'),  # Fast list by tenant + time
        Index('ix_transcripts_uwc_job', 'uwc_job_id', unique=True),  # Prevent duplicate processing
    )
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "call_id": self.call_id,
            "tenant_id": self.tenant_id,
            "uwc_job_id": self.uwc_job_id,
            "transcript_text": self.transcript_text,
            "speaker_labels": self.speaker_labels,
            "confidence_score": self.confidence_score,
            "language": self.language,
            "word_count": self.word_count,
            "processing_time_ms": self.processing_time_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }



