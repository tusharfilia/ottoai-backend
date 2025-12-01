"""
Lead Status History model for tracking adaptive lead status transitions (Section 3.4).
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Index
from sqlalchemy.orm import relationship

from app.database import Base


class LeadStatusHistory(Base):
    """
    Tracks transitions in lead status for the adaptive lead status engine.
    
    Records when status changes: new -> warm -> hot -> booked -> won
    or: new -> dormant -> abandoned
    """
    __tablename__ = "lead_status_history"
    __table_args__ = (
        Index("ix_lead_status_history_lead", "lead_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    
    # Status transition
    from_status = Column(String, nullable=True, comment="Previous status")
    to_status = Column(String, nullable=False, comment="New status")
    
    # Transition reason
    reason = Column(Text, nullable=True, comment="Why status changed (auto or manual)")
    triggered_by = Column(String, nullable=True, comment="User ID if manual, 'otto' if automatic")
    
    # Context
    context = Column(Text, nullable=True, comment="Additional context as JSON")
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    lead = relationship("Lead", back_populates="status_history")
    company = relationship("Company", foreign_keys=[company_id])



