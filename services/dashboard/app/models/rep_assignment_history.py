"""
Rep Assignment History model for tracking rep assignment changes (Section 4.3).
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Boolean, Integer, Float, Index
from sqlalchemy.orm import relationship

from app.database import Base


class RepAssignmentHistory(Base):
    """
    Tracks rep assignment history for leads and appointments.
    
    Records:
    - When rep was assigned/unassigned
    - Who assigned them
    - Whether rep claimed the lead
    - Routing information
    """
    __tablename__ = "rep_assignment_history"
    __table_args__ = (
        Index("ix_rep_assignment_history_lead", "lead_id", "created_at"),
        Index("ix_rep_assignment_history_rep", "rep_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    
    # Foreign keys
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True, index=True)
    appointment_id = Column(String, ForeignKey("appointments.id"), nullable=True, index=True)
    rep_id = Column(String, ForeignKey("sales_reps.user_id"), nullable=False, index=True)
    
    # Assignment details
    assigned_by = Column(String, nullable=True, comment="User ID who made the assignment")
    assignment_type = Column(String, nullable=False, comment="requested/assigned/declined/revoked/unassigned/claimed/unclaimed")
    requested_at = Column(DateTime, nullable=True, comment="When rep requested this lead")
    assigned_at = Column(DateTime, nullable=True, comment="When lead was assigned to rep")
    status = Column(String, nullable=False, default="requested", comment="requested/assigned/declined/revoked")
    
    # Routing information
    route_position = Column(Integer, nullable=True, comment="Position in rep's route")
    route_group = Column(String, nullable=True, comment="Route group identifier")
    distance_from_previous_stop = Column(Float, nullable=True, comment="Distance in miles/feet")
    
    # Claim tracking
    rep_claimed = Column(Boolean, default=False, comment="Whether rep claimed this lead")
    
    # Context
    notes = Column(Text, nullable=True, comment="Assignment notes or reason")
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    lead = relationship("Lead", back_populates="assignment_history")
    appointment = relationship("Appointment", back_populates="assignment_history")
    rep = relationship("SalesRep", foreign_keys=[rep_id])
    company = relationship("Company", foreign_keys=[company_id])

