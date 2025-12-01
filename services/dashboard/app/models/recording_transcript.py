"""
Recording Transcript model for storing ASR results from recording sessions.
Supports Ghost Mode restrictions on transcript visibility.
"""
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, JSON, Index, Boolean
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime


class RecordingTranscript(Base):
    """
    Stores ASR transcription results from recording sessions.
    
    Features:
    - Tenant isolation (company_id)
    - Links to RecordingSession
    - Speaker diarization (separate rep vs customer speech)
    - Confidence scoring
    - Ghost Mode support (transcript may be restricted)
    - UWC job tracking for correlation
    - Performance indexes for fast retrieval
    """
    __tablename__ = "recording_transcripts"
    
    # Primary key
    id = Column(String, primary_key=True)  # UUID
    
    # Foreign keys (with indexes)
    recording_session_id = Column(String, ForeignKey("recording_sessions.id"), nullable=False, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    appointment_id = Column(String, ForeignKey("appointments.id"), nullable=True, index=True)
    
    # UWC ASR Results
    uwc_job_id = Column(String, index=True, unique=True, nullable=True)  # Nullable for Ghost Mode
    transcript_text = Column(Text, nullable=True)  # Nullable in Ghost Mode (aggregates_only or none)
    
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
    
    # Ghost Mode Restrictions
    is_ghost_mode = Column(Boolean, nullable=False, default=False)  # True if session was in Ghost Mode
    transcript_restricted = Column(Boolean, nullable=False, default=False)  # True if transcript is not available due to Ghost Mode
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    recording_session = relationship("RecordingSession", back_populates="transcript")
    company = relationship("Company", foreign_keys=[company_id])
    appointment = relationship("Appointment", back_populates="transcripts")
    
    # Multi-tenant performance indexes
    __table_args__ = (
        Index('ix_recording_transcripts_company_session', 'company_id', 'recording_session_id'),
        Index('ix_recording_transcripts_company_created', 'company_id', 'created_at'),
        Index('ix_recording_transcripts_uwc_job', 'uwc_job_id'),
        Index('ix_recording_transcripts_appointment', 'appointment_id'),
    )




