from datetime import time
import enum
from sqlalchemy import Column, String, DateTime, Boolean, Enum, Time, Float, Integer
from sqlalchemy.orm import relationship
from ..database import Base
from .service import Service
from datetime import datetime


class GhostModeRetention(str, enum.Enum):
    """Retention policy for Ghost Mode recordings."""
    AGGREGATES_ONLY = "aggregates_only"  # Only aggregated metrics
    MINIMAL = "minimal"  # Aggregates + summary transcript
    NONE = "none"  # No data retention (only real-time analysis)


class GhostModeStorage(str, enum.Enum):
    """Storage mode for Ghost Mode audio."""
    NOT_STORED = "not_stored"  # Never stored (most private)
    EPHEMERAL = "ephemeral"  # Temporarily stored with TTL


class CallProvider(str, enum.Enum):
    """Call tracking provider enum."""
    CALLRAIL = "callrail"
    TWILIO = "twilio"


class Company(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True) 
    name = Column(String, unique=True, index=True)
    address = Column(String)
    phone_number = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # CallRail integration fields
    callrail_api_key = Column(String, nullable=True)
    callrail_account_id = Column(String, nullable=True)
    
    # Onboarding fields
    industry = Column(String, nullable=True)
    timezone = Column(String, nullable=True, default="America/New_York")
    domain = Column(String, nullable=True)
    domain_verified = Column(Boolean, nullable=False, default=False)
    
    # Call tracking provider
    call_provider = Column(
        Enum(CallProvider, native_enum=False, name="call_provider"),
        nullable=True
    )
    twilio_account_sid = Column(String, nullable=True)
    twilio_auth_token = Column(String, nullable=True)
    primary_tracking_number = Column(String, nullable=True)
    
    # Onboarding progress
    onboarding_step = Column(String, nullable=False, default="company_basics")
    onboarding_completed = Column(Boolean, nullable=False, default=False)
    onboarding_completed_at = Column(DateTime, nullable=True)
    
    # Subscription fields
    subscription_status = Column(String, nullable=False, default="trialing")  # trialing, active, past_due, canceled
    trial_ends_at = Column(DateTime, nullable=True)
    max_seats = Column(Integer, nullable=False, default=5)
    
    # Recording & Privacy Configuration
    require_recording_consent = Column(Boolean, nullable=False, default=True)
    allow_ghost_mode = Column(Boolean, nullable=False, default=True)
    ghost_mode_retention = Column(
        Enum(GhostModeRetention, native_enum=False, name="ghost_mode_retention"),
        nullable=False,
        default=GhostModeRetention.AGGREGATES_ONLY,
    )
    ghost_mode_storage = Column(
        Enum(GhostModeStorage, native_enum=False, name="ghost_mode_storage"),
        nullable=False,
        default=GhostModeStorage.NOT_STORED,
    )
    ghost_mode_ephemeral_ttl_minutes = Column(Integer, nullable=False, default=60)
    
    # Shift Configuration
    default_shift_start = Column(Time, nullable=True, default=time(7, 0))  # 7am
    default_shift_end = Column(Time, nullable=True, default=time(20, 0))  # 8pm
    require_clock_in = Column(Boolean, nullable=False, default=True)
    
    # Geofence Defaults
    default_geofence_radius_start = Column(Float, nullable=False, default=200.0)  # feet
    default_geofence_radius_stop = Column(Float, nullable=False, default=500.0)  # feet
    
    # Relationships
    calls = relationship("Call", back_populates="company")
    sales_reps = relationship("SalesRep", back_populates="company")
    sales_managers = relationship("SalesManager", back_populates="company")
    services = relationship("Service", back_populates="company")
    contact_cards = relationship("ContactCard", back_populates="company")
    leads = relationship("Lead", back_populates="company")
    appointments = relationship("Appointment", back_populates="company")
    users = relationship("User", back_populates="company")
    rep_shifts = relationship("RepShift", back_populates="company")
    recording_sessions = relationship("RecordingSession", back_populates="company")
    tasks = relationship("Task", back_populates="company", foreign_keys="Task.company_id")
    key_signals = relationship("KeySignal", back_populates="company", foreign_keys="KeySignal.company_id")
    event_logs = relationship("EventLog", back_populates="company", foreign_keys="EventLog.company_id")
    sop_compliance_results = relationship("SopComplianceResult", back_populates="company", foreign_keys="SopComplianceResult.company_id")
    documents = relationship("Document", back_populates="company")
    onboarding_events = relationship("OnboardingEvent", back_populates="company") 