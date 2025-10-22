"""
Call Analysis model for storing AI coaching, objections, and sentiment analysis from UWC.
Powers the coaching, objection tracking, and rehash scoring features.
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime


class CallAnalysis(Base):
    """
    Stores AI analysis results (objections, coaching, sentiment, SOP tracking).
    
    Features:
    - Objection detection (what objections were raised)
    - Coaching recommendations (what rep should improve)
    - Sentiment analysis (customer engagement)
    - Rehash scoring (should we follow up?)
    - SOP stage tracking (which steps were completed)
    - Talk time ratios (rep vs customer speaking time)
    """
    __tablename__ = "call_analysis"
    
    # Primary key
    id = Column(String, primary_key=True)  # UUID
    
    # Foreign keys (with indexes)
    call_id = Column(Integer, ForeignKey("calls.call_id"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    
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
    rehash_score = Column(Float, nullable=True)  # 0.0 to 10.0 (likelihood of recovery)
    talk_time_ratio = Column(Float, nullable=True)  # rep_talk_time / total_time (ideal: 0.3-0.4)
    
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
    uwc_job_id = Column(String, index=True, unique=True, nullable=False)  # Correlation with UWC
    analyzed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    analysis_version = Column(String, default="v1", nullable=False)  # Track model version
    processing_time_ms = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    call = relationship("Call", foreign_keys=[call_id])
    company = relationship("Company", foreign_keys=[tenant_id])
    
    # Multi-tenant performance indexes
    __table_args__ = (
        Index('ix_analysis_tenant_call', 'tenant_id', 'call_id'),  # Fast lookup
        Index('ix_analysis_uwc_job', 'uwc_job_id', unique=True),  # Prevent duplicates
        Index('ix_analysis_tenant_analyzed', 'tenant_id', 'analyzed_at'),  # Fast list by time
        Index('ix_analysis_tenant_quality', 'tenant_id', 'lead_quality'),  # Filter by lead quality
        Index('ix_analysis_tenant_rehash', 'tenant_id', 'rehash_score'),  # Sort by rehash score
    )
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "call_id": self.call_id,
            "tenant_id": self.tenant_id,
            "objections": self.objections,
            "objection_details": self.objection_details,
            "sentiment_score": self.sentiment_score,
            "engagement_score": self.engagement_score,
            "coaching_tips": self.coaching_tips,
            "sop_stages_completed": self.sop_stages_completed,
            "sop_stages_missed": self.sop_stages_missed,
            "sop_compliance_score": self.sop_compliance_score,
            "rehash_score": self.rehash_score,
            "talk_time_ratio": self.talk_time_ratio,
            "lead_quality": self.lead_quality,
            "conversion_probability": self.conversion_probability,
            "meeting_segments": self.meeting_segments,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
            "analysis_version": self.analysis_version
        }




