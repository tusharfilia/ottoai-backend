"""
Event Log model for booking timeline and visit activity timeline (Section 5.3, 4.6).
"""
from datetime import datetime
import enum
from uuid import uuid4

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, JSON, Index, Integer
from sqlalchemy.orm import relationship

from app.database import Base


class EventType(str, enum.Enum):
    """Type of event for timeline."""
    # Call events
    CALL_RECEIVED = "call_received"
    CALL_MISSED = "call_missed"
    CALL_COMPLETED = "call_completed"
    CALL_TRANSCRIPT = "call_transcript"
    
    # SMS events
    SMS_SENT = "sms_sent"
    SMS_RECEIVED = "sms_received"
    
    # Automation events
    AUTOMATION_NURTURE = "automation_nurture"
    AUTOMATION_FOLLOWUP = "automation_followup"
    AUTOMATION_SCHEDULED = "automation_scheduled"
    AUTOMATION_TASK_CREATED = "automation_task_created"
    AUTOMATION_ESCALATED = "automation_escalated"
    
    # Appointment events
    APPOINTMENT_CREATED = "appointment_created"
    APPOINTMENT_RESCHEDULED = "appointment_rescheduled"
    APPOINTMENT_CONFIRMED = "appointment_confirmed"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    
    # Rep assignment events
    REP_ASSIGNED = "rep_assigned"
    REP_UNASSIGNED = "rep_unassigned"
    REP_CLAIMED = "rep_claimed"
    
    # Visit/recording events (Section 4.6)
    REP_EN_ROUTE = "rep_en_route"
    REP_ARRIVED = "rep_arrived"  # Geofence entry
    RECORDING_STARTED = "recording_started"
    INSPECTION_MILESTONE = "inspection_milestone"
    OBJECTION_MOMENT = "objection_moment"
    DECISION_MOMENT = "decision_moment"
    RECORDING_ENDED = "recording_ended"
    REP_DEPARTED = "rep_departed"  # Geofence exit
    APPOINTMENT_OUTCOME = "appointment_outcome"
    
    # CSR/Manual actions
    CSR_ACTION = "csr_action"
    MANAGER_ACTION = "manager_action"
    
    # Property events
    PROPERTY_INTELLIGENCE_UPDATED = "property_intelligence_updated"
    
    # Deal events
    DEAL_WON = "deal_won"
    DEAL_LOST = "deal_lost"


class EventLog(Base):
    """
    Chronological log of all events for a ContactCard/Lead/Appointment.
    
    Powers both:
    - Booking Timeline (Section 5.3 Tab 3)
    - Visit Activity Timeline (Section 4.6)
    """
    __tablename__ = "event_logs"
    __table_args__ = (
        Index("ix_event_logs_contact_card", "contact_card_id", "created_at"),
        Index("ix_event_logs_lead", "lead_id", "created_at"),
        Index("ix_event_logs_appointment", "appointment_id", "created_at"),
        Index("ix_event_logs_type", "event_type", "created_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    
    # Foreign keys (nullable - event can be linked to multiple entities)
    contact_card_id = Column(String, ForeignKey("contact_cards.id"), nullable=False, index=True)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True, index=True)
    appointment_id = Column(String, ForeignKey("appointments.id"), nullable=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.call_id"), nullable=True, index=True)
    
    # Event details
    event_type = Column(
        Enum(EventType, native_enum=False, name="event_type"),
        nullable=False,
        index=True,
    )
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Event metadata
    event_metadata = Column(JSON, nullable=True, comment="Event-specific data as JSON")
    description = Column(Text, nullable=True, comment="Human-readable event description")
    
    # Actor (who/what triggered this event)
    actor_id = Column(String, nullable=True, comment="User ID, 'otto', 'shunya', or system component")
    actor_role = Column(String, nullable=True, comment="rep/csr/manager/ai/system")
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    contact_card = relationship("ContactCard", back_populates="event_logs")
    lead = relationship("Lead", back_populates="event_logs")
    appointment = relationship("Appointment", back_populates="event_logs")
    company = relationship("Company", foreign_keys=[company_id])



