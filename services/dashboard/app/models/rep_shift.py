"""
RepShift model for tracking sales rep clock-in/out and shift management.
"""
from datetime import datetime, time
import enum
from uuid import uuid4

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, String, Text, Time, Index
from sqlalchemy.orm import relationship

from app.database import Base


class ShiftStatus(str, enum.Enum):
    """Status of a rep shift."""
    OFF = "off"  # Rep is off (holiday, PTO, sick, manager-marked)
    PLANNED = "planned"  # Shift is scheduled but not started
    ACTIVE = "active"  # Rep has clocked in
    COMPLETED = "completed"  # Rep has clocked out
    SKIPPED = "skipped"  # Shift was skipped (no clock-in)


class RepShift(Base):
    """
    Tracks clock-in/out state for a sales rep.
    
    Each shift represents one day's work period for a rep.
    Supports configurable shift windows and exemptions.
    """
    __tablename__ = "rep_shifts"
    __table_args__ = (
        Index("ix_rep_shifts_company_rep_date", "company_id", "rep_id", "shift_date"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    rep_id = Column(String, ForeignKey("sales_reps.user_id"), nullable=False, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)

    shift_date = Column(Date, nullable=False, index=True)  # Date of the shift
    
    # Clock times
    clock_in_at = Column(DateTime, nullable=True)
    clock_out_at = Column(DateTime, nullable=True)
    
    # Scheduled shift window (for that day)
    scheduled_start = Column(Time, nullable=True)  # Local time
    scheduled_end = Column(Time, nullable=True)  # Local time
    
    status = Column(
        Enum(ShiftStatus, native_enum=False, name="shift_status"),
        nullable=False,
        default=ShiftStatus.PLANNED,
        index=True,
    )
    
    notes = Column(Text, nullable=True)  # e.g., PTO reason, holiday, etc.
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    rep = relationship("SalesRep", back_populates="shifts")
    company = relationship("Company", back_populates="rep_shifts")
    recording_sessions = relationship("RecordingSession", back_populates="shift")

