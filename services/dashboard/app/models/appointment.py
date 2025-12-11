from datetime import datetime
import enum
from uuid import uuid4

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, String, Text, Boolean, Integer, Index
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.enums import AppointmentType


class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class AppointmentOutcome(str, enum.Enum):
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"


class Appointment(Base):
    """
    Represents a scheduled interaction between a rep and a contact.
    Appointments are tenant scoped and linked back to the originating lead/contact card.
    """

    __tablename__ = "appointments"
    __table_args__ = (
        Index(
            "ix_appointments_company_lead_window",
            "company_id",
            "lead_id",
            "scheduled_start",
            "assigned_rep_id",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    lead_id = Column(String, ForeignKey("leads.id"), nullable=False, index=True)
    contact_card_id = Column(String, ForeignKey("contact_cards.id"), nullable=True, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)

    assigned_rep_id = Column(String, ForeignKey("sales_reps.user_id"), nullable=True, index=True)

    scheduled_start = Column(DateTime, nullable=False)
    scheduled_end = Column(DateTime, nullable=True)

    status = Column(Enum(AppointmentStatus, native_enum=False, name="appointment_status"), nullable=False, default=AppointmentStatus.SCHEDULED)
    outcome = Column(
        Enum(AppointmentOutcome, native_enum=False, name="appointment_outcome"),
        nullable=False,
        default=AppointmentOutcome.PENDING,
    )
    # Canonical AppointmentType enum (aligned with Shunya enums-inventory-by-service.md)
    appointment_type = Column(
        Enum(AppointmentType, native_enum=False, name="appointment_type"),
        nullable=True,
        comment="Canonical appointment type: in-person, virtual, phone"
    )

    location = Column(String, nullable=True)  # Address string (legacy field)
    location_address = Column(String, nullable=True, comment="Address from Shunya entities (triggers property enrichment)")
    geo_lat = Column(Float, nullable=True)  # Latitude (geocoded from address)
    geo_lng = Column(Float, nullable=True)  # Longitude (geocoded from address)
    location_lat = Column(Float, nullable=True, comment="Latitude for geofencing (synced from geo_lat or property enrichment)")
    location_lng = Column(Float, nullable=True, comment="Longitude for geofencing (synced from geo_lng or property enrichment)")
    
    # Geofence configuration (in feet)
    geofence_radius_start = Column(Float, nullable=True, default=200.0)  # Default 200 feet
    geofence_radius_stop = Column(Float, nullable=True, default=500.0)  # Default 500 feet
    
    service_type = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    external_id = Column(String, nullable=True, index=True)
    
    # Deal information (Section 4.4)
    deal_size = Column(Float, nullable=True, comment="Estimated deal size in dollars")
    material_type = Column(String, nullable=True, comment="Roofing material type discussed")
    financing_type = Column(String, nullable=True, comment="Financing option discussed")
    
    # Rep assignment details (Section 3.3, 4.3)
    assigned_by = Column(String, nullable=True, comment="User ID who assigned this appointment")
    assigned_at = Column(DateTime, nullable=True, comment="When rep was assigned")
    rep_claimed = Column(Boolean, default=False, comment="Whether rep claimed this lead/appointment")
    route_position = Column(Integer, nullable=True, comment="Position in rep's route for the day")
    route_group = Column(String, nullable=True, comment="Route group identifier")
    distance_from_previous_stop = Column(Float, nullable=True, comment="Distance in miles/feet from previous stop")
    
    # Geofence events (Section 4.7)
    arrival_at = Column(DateTime, nullable=True, comment="When rep entered 200ft geofence")
    departure_at = Column(DateTime, nullable=True, comment="When rep exited 500ft geofence")
    on_site_duration = Column(Integer, nullable=True, comment="Duration on site in minutes")
    gps_confidence = Column(Float, nullable=True, comment="GPS location confidence score")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    lead = relationship("Lead", back_populates="appointments")
    contact_card = relationship("ContactCard", back_populates="appointments")
    company = relationship("Company", back_populates="appointments")
    assigned_rep = relationship("SalesRep", back_populates="appointments")
    recording_sessions = relationship("RecordingSession", back_populates="appointment")
    transcripts = relationship("RecordingTranscript", back_populates="appointment")
    analyses = relationship("RecordingAnalysis", back_populates="appointment")
    tasks = relationship("Task", back_populates="appointment")
    key_signals = relationship("KeySignal", back_populates="appointment")
    sop_compliance_results = relationship("SopComplianceResult", back_populates="appointment")
    assignment_history = relationship("RepAssignmentHistory", back_populates="appointment", order_by="RepAssignmentHistory.created_at.desc()")
    event_logs = relationship("EventLog", back_populates="appointment", order_by="EventLog.created_at.desc()")


