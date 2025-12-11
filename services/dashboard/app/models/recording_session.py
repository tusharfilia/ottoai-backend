"""
RecordingSession model for geofenced appointment recordings.
"""
from datetime import datetime
import enum
from uuid import uuid4

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import relationship

from app.database import Base


class RecordingMode(str, enum.Enum):
    """Recording mode for privacy compliance."""
    NORMAL = "normal"  # Default: full recording stored
    GHOST = "ghost"  # Privacy mode: no raw audio retention
    OFF = "off"  # Recording disabled for this rep


class AudioStorageMode(str, enum.Enum):
    """How audio is stored for this session."""
    PERSISTENT = "persistent"  # Stored long-term (normal mode)
    EPHEMERAL = "ephemeral"  # Short-lived with TTL (ghost mode option B)
    NOT_STORED = "not_stored"  # Never stored (ghost mode option A)


class TranscriptionStatus(str, enum.Enum):
    """Status of transcription processing."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisStatus(str, enum.Enum):
    """Status of analysis processing."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class RecordingSession(Base):
    """
    Tracks each geofenced recording session.
    
    Records when a rep enters/exits a geofence around an appointment
    and handles audio recording with privacy modes (normal vs ghost).
    """
    __tablename__ = "recording_sessions"
    __table_args__ = (
        Index("ix_recording_sessions_company_rep_appointment", "company_id", "rep_id", "appointment_id"),
        Index("ix_recording_sessions_shift", "shift_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    
    # Foreign keys
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    rep_id = Column(String, ForeignKey("sales_reps.user_id"), nullable=False, index=True)
    appointment_id = Column(String, ForeignKey("appointments.id"), nullable=False, index=True)
    shift_id = Column(String, ForeignKey("rep_shifts.id"), nullable=True, index=True)
    
    # Recording mode and storage
    mode = Column(
        Enum(RecordingMode, native_enum=False, name="recording_mode"),
        nullable=False,
        default=RecordingMode.NORMAL,
        index=True,
    )
    audio_storage_mode = Column(
        Enum(AudioStorageMode, native_enum=False, name="audio_storage_mode"),
        nullable=False,
        default=AudioStorageMode.PERSISTENT,
    )
    
    # Timing
    started_at = Column(DateTime, nullable=False, index=True)
    ended_at = Column(DateTime, nullable=True)
    
    # Session status (simple status for recording lifecycle)
    status = Column(
        String,
        nullable=False,
        default="pending",
        index=True,
        comment="Session status: pending, recording, completed, failed"
    )
    
    # Location tracking
    start_lat = Column(Float, nullable=True)
    start_lng = Column(Float, nullable=True)
    end_lat = Column(Float, nullable=True)
    end_lng = Column(Float, nullable=True)
    
    # Geofence configuration used
    geofence_radius_start = Column(Float, nullable=True)  # Radius in feet (default 200)
    geofence_radius_stop = Column(Float, nullable=True)  # Radius in feet (default 500)
    
    # Audio storage (nullable in ghost mode)
    audio_url = Column(String, nullable=True)  # S3 URL or similar
    audio_duration_seconds = Column(Float, nullable=True)
    audio_size_bytes = Column(Integer, nullable=True)
    
    # Processing status
    transcription_status = Column(
        Enum(TranscriptionStatus, native_enum=False, name="transcription_status"),
        nullable=False,
        default=TranscriptionStatus.NOT_STARTED,
        index=True,
    )
    analysis_status = Column(
        Enum(AnalysisStatus, native_enum=False, name="analysis_status"),
        nullable=False,
        default=AnalysisStatus.NOT_STARTED,
        index=True,
    )
    
    # Shunya job tracking
    shunya_asr_job_id = Column(String, nullable=True, index=True)
    shunya_analysis_job_id = Column(String, nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    
    # Ghost Mode TTL (if ephemeral)
    expires_at = Column(DateTime, nullable=True, index=True)  # For ephemeral storage
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    company = relationship("Company", back_populates="recording_sessions")
    rep = relationship("SalesRep", back_populates="recording_sessions")
    appointment = relationship("Appointment", back_populates="recording_sessions")
    shift = relationship("RepShift", back_populates="recording_sessions")
    transcript = relationship("RecordingTranscript", back_populates="recording_session", uselist=False)
    analysis = relationship("RecordingAnalysis", back_populates="recording_session", uselist=False)

