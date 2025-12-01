"""
SOP Compliance Result model for sales process checklist (Section 4.5).
"""
from datetime import datetime
import enum
from uuid import uuid4

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, Float, Boolean, JSON, Index, Integer
from sqlalchemy.orm import relationship

from app.database import Base


class SopChecklistItem(str, enum.Enum):
    """SOP checklist items."""
    GREETING = "greeting"
    BUILDING_RAPPORT = "building_rapport"
    UNDERSTANDING_NEEDS = "understanding_needs"
    INSPECTING_ROOF = "inspecting_roof"
    TAKING_PHOTOS = "taking_photos"
    PRESENTING_ESTIMATE = "presenting_estimate"
    EXPLAINING_WARRANTY = "explaining_warranty"
    REVIEWING_PRICE = "reviewing_price"
    DISCUSSING_FINANCING = "discussing_financing"
    CLOSING_ATTEMPT = "closing_attempt"
    NEXT_STEPS_GIVEN = "next_steps_given"


class SopItemStatus(str, enum.Enum):
    """Status of individual SOP item."""
    COMPLETED = "completed"  # ✔
    MISSED = "missed"  # ❌
    WARNING = "warning"  # ⚠


class SopComplianceResult(Base):
    """
    Sales Process Checklist (SOP Compliance) results.
    
    Stores individual checklist items with status (completed/missed/warning)
    for each appointment or call.
    """
    __tablename__ = "sop_compliance_results"
    __table_args__ = (
        Index("ix_sop_compliance_appointment", "appointment_id"),
        Index("ix_sop_compliance_call", "call_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    
    # Foreign keys
    appointment_id = Column(String, ForeignKey("appointments.id"), nullable=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.call_id"), nullable=True, index=True)
    recording_session_id = Column(String, ForeignKey("recording_sessions.id"), nullable=True, index=True)
    
    # SOP item
    checklist_item = Column(
        Enum(SopChecklistItem, native_enum=False, name="sop_checklist_item"),
        nullable=False,
    )
    status = Column(
        Enum(SopItemStatus, native_enum=False, name="sop_item_status"),
        nullable=False,
    )
    
    # Details
    notes = Column(Text, nullable=True, comment="Notes about this item")
    timestamp = Column(DateTime, nullable=True, comment="When this item occurred (for timeline)")
    
    # Source
    detected_by = Column(String, nullable=False, comment="shunya/otto/manual")
    confidence_score = Column(Float, nullable=True, comment="AI confidence if auto-detected")
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    appointment = relationship("Appointment", back_populates="sop_compliance_results")
    company = relationship("Company", foreign_keys=[company_id])

