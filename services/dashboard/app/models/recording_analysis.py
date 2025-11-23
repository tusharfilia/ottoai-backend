"""
Recording Analysis model for storing AI coaching and analysis results from recording sessions.
Always retained in Ghost Mode (aggregated data).
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime


class RecordingAnalysis(Base):
    """
    Stores AI analysis results from recording sessions (objections, coaching, sentiment, SOP tracking).
    
    Features:
    - Always retained in Ghost Mode (aggregated data)
    - Links to RecordingSession, Appointment, and Lead
    - Objection detection and details
    - Coaching recommendations
    - Sentiment and engagement scores
    - SOP compliance tracking
    - Conversion probability
    - UWC job tracking
    """
    __tablename__ = "recording_analyses"
    
    # Primary key
    id = Column(String, primary_key=True)  # UUID
    
    # Foreign keys (with indexes)
    recording_session_id = Column(String, ForeignKey("recording_sessions.id"), nullable=False, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    appointment_id = Column(String, ForeignKey("appointments.id"), nullable=True, index=True)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True, index=True)
    
    # Objection Analysis
    objections = Column(JSON, nullable=True)
    # Format: ["price", "timeline", "competitor", "need_spouse_approval"]
    
    objection_details = Column(JSON, nullable=True)
    # Format: [
    #   {
    #     "type": "price",
    #     "timestamp": 45.2,
    #     "quote": "That's too expensive for me",
    #     "resolved": false
    #   }
    # ]
    
    # Sentiment Analysis
    sentiment_score = Column(Float, nullable=True)  # 0.0 (negative) to 1.0 (positive)
    engagement_score = Column(Float, nullable=True)  # How engaged was customer? 0-1
    
    # Coaching Recommendations
    coaching_tips = Column(JSON, nullable=True)
    # Format: [
    #   {
    #     "tip": "Set agenda earlier in conversation",
    #     "priority": "high",
    #     "category": "sales_process",
    #     "timestamp": 5.2
    #   }
    # ]
    
    # SOP Stage Tracking
    sop_stages_completed = Column(JSON, nullable=True)
    # Format: ["connect", "agenda", "assess", "report", "present"]
    
    sop_stages_missed = Column(JSON, nullable=True)
    # Format: ["ask", "close", "referral"]
    
    sop_compliance_score = Column(Float, nullable=True)  # 0-10
    
    # Performance Metrics
    talk_time_ratio = Column(Float, nullable=True)  # rep_talk_time / total_time (ideal: 0.3-0.4)
    
    # Outcome Classification
    outcome = Column(String, nullable=True)  # "won", "lost", "qualified", "no_show", "rescheduled"
    outcome_confidence = Column(Float, nullable=True)  # 0-1
    
    # Lead Classification
    lead_quality = Column(String, nullable=True)  # "qualified", "unqualified", "hot", "warm", "cold"
    conversion_probability = Column(Float, nullable=True)  # 0-1
    
    # Meeting Segmentation
    meeting_segments = Column(JSON, nullable=True)
    # Format: [
    #   {"type": "rapport", "start": 0.0, "end": 120.5},
    #   {"type": "agenda", "start": 120.5, "end": 180.0},
    #   {"type": "proposal", "start": 180.0, "end": 600.0}
    # ]
    
    # UWC Tracking
    uwc_job_id = Column(String, index=True, nullable=True)  # Correlation with UWC
    analyzed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    analysis_version = Column(String, default="v1", nullable=False)  # Track model version
    processing_time_ms = Column(Integer, nullable=True)
    
    # Ghost Mode
    is_ghost_mode = Column(Boolean, nullable=False, default=False)  # True if session was in Ghost Mode
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    recording_session = relationship("RecordingSession", back_populates="analysis")
    company = relationship("Company", foreign_keys=[company_id])
    appointment = relationship("Appointment", back_populates="analyses")
    lead = relationship("Lead", back_populates="recording_analyses")
    
    # Multi-tenant performance indexes
    __table_args__ = (
        Index('ix_recording_analyses_company_session', 'company_id', 'recording_session_id'),
        Index('ix_recording_analyses_company_analyzed', 'company_id', 'analyzed_at'),
        Index('ix_recording_analyses_appointment', 'appointment_id'),
        Index('ix_recording_analyses_lead', 'lead_id'),
        Index('ix_recording_analyses_outcome', 'outcome'),
        Index('ix_recording_analyses_uwc_job', 'uwc_job_id'),
    )


