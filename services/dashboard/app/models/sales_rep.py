from datetime import time
import enum
from sqlalchemy import Column, String, ForeignKey, JSON, Enum, Time, Boolean
from sqlalchemy.orm import relationship
from ..database import Base
#931980e753b188c6856ffaed726ef00a


class RecordingMode(str, enum.Enum):
    """Recording mode for privacy compliance."""
    NORMAL = "normal"  # Default: full recording stored
    GHOST = "ghost"  # Privacy mode: no raw audio retention
    OFF = "off"  # Recording disabled for this rep


class ShiftConfigSource(str, enum.Enum):
    """Source of shift configuration."""
    TENANT_DEFAULT = "tenant_default"  # Uses company default shift times
    CUSTOM = "custom"  # Rep has custom shift times


class SalesRep(Base):
    __tablename__ = "sales_reps"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)  # This is now the Clerk user ID
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)  # Now references Clerk org ID
    manager_id = Column(String, ForeignKey("sales_managers.user_id"), nullable=True)  # Now references Clerk user ID
    active_geofences = Column(JSON, nullable=True)  # List of active geofences as (latitude, longitude, radius) tuples
    expo_push_token = Column(String, nullable=True)  # Expo Push Token for mobile notifications
    
    # Recording and shift settings
    recording_mode = Column(
        Enum(RecordingMode, native_enum=False, name="recording_mode"),
        nullable=False,
        default=RecordingMode.NORMAL,
    )
    allow_location_tracking = Column(Boolean, nullable=False, default=True)
    allow_recording = Column(Boolean, nullable=False, default=True)
    
    # Shift configuration
    default_shift_start = Column(Time, nullable=True)  # Local time (e.g., 07:00)
    default_shift_end = Column(Time, nullable=True)  # Local time (e.g., 20:00)
    shift_config_source = Column(
        Enum(ShiftConfigSource, native_enum=False, name="shift_config_source"),
        nullable=False,
        default=ShiftConfigSource.TENANT_DEFAULT,
    )
    
    # Relationships
    calls = relationship("Call", back_populates="assigned_rep")
    manager = relationship("SalesManager", back_populates="sales_reps")
    company = relationship("Company", back_populates="sales_reps")
    user = relationship("User", back_populates="rep_profile")
    appointments = relationship("Appointment", back_populates="assigned_rep")
    shifts = relationship("RepShift", back_populates="rep")
    recording_sessions = relationship("RecordingSession", back_populates="rep")