from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Time
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime
#931980e753b188c6856ffaed726ef00a
class Call(Base):
    __tablename__ = "calls"

    call_id = Column(Integer, primary_key=True, index=True)
    missed_call = Column(Boolean, default=False)
    address = Column(String)
    name = Column(String)
    quote_date = Column(DateTime)
    booked = Column(Boolean, default=False)
    phone_number = Column(String)
    transcript = Column(String)
    homeowner_followup_transcript = Column(String)
    in_person_transcript = Column(Text, nullable=True)  # New field for in-person meeting transcripts
    mobile_transcript = Column(Text, nullable=True)  # New field for mobile call transcripts
    mobile_calls_count = Column(Integer, default=0)  # Track number of mobile calls
    mobile_texts_count = Column(Integer, default=0)  # Track number of text messages
    assigned_rep_id = Column(String, ForeignKey("sales_reps.user_id"))
    bought = Column(Boolean, default=False)
    price_if_bought = Column(Float)
    company_id = Column(String, ForeignKey("companies.id"), nullable=True)
    reason_for_lost_sale = Column(String)
    reason_not_bought_homeowner = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # Add update timestamp
    bland_call_id = Column(String)  # Store Bland.ai call ID
    homeowner_followup_call_id = Column(String)
    transcript_discrepancies = Column(String)  # Add new field for discrepancies analysis
    problem = Column(String) 
    still_deciding = Column(Boolean, default=False)  # New field for tracking if customer is still deciding
    reason_for_deciding = Column(String)  # New field for storing why customer is still deciding
    # New fields
    cancelled = Column(Boolean, default=False)
    reason_for_cancellation = Column(String)
    rescheduled = Column(Boolean, default=False)
    text_messages = Column(Text, nullable=True)  # New field to store text message history
    status = Column(String)  # Status of the call (blank, completed, failed, etc.)
    call_sid = Column(String, nullable=True)  # Store Twilio Call SID
    last_call_status = Column(String, nullable=True)  # Last status of the call
    last_call_timestamp = Column(String, nullable=True)  # Timestamp of the last call
    last_call_duration = Column(Integer, nullable=True)  # Duration of the last call in seconds
    
    # Relationships
    assigned_rep = relationship("SalesRep", back_populates="calls")
    company = relationship("Company", back_populates="calls")
    
    # Geofence tracking fields
    geofence = Column(JSON, nullable=True)  # Stores latitude, longitude, and radius (in meters) of the geofence
    geofence_entry_1_ts = Column(DateTime, nullable=True)  # Timestamp of first geofence entry
    geofence_exit_1_ts = Column(DateTime, nullable=True)  # Timestamp of first geofence exit
    geofence_time_1_m = Column(Integer, nullable=True)  # Time spent during first geofence visit (in minutes)
    geofence_entry_2_ts = Column(DateTime, nullable=True)  # Timestamp of second geofence entry
    geofence_exit_2_ts = Column(DateTime, nullable=True)  # Timestamp of second geofence exit
    geofence_time_2_m = Column(Integer, nullable=True)  # Time spent during second geofence visit (in minutes)
    geofence_multiple_entries = Column(Boolean, default=False)  # Indicates if rep entered geofence more than once
    geofence_entry_count = Column(Integer, default=0)  # Total number of times rep entered the geofence
    
    # Recording tracking fields
    recording_started_ts = Column(DateTime, nullable=True)  # Timestamp when recording started
    recording_stopped_ts = Column(DateTime, nullable=True)  # Timestamp when recording stopped
    recording_duration_s = Column(Integer, nullable=True)  # Recording duration in seconds
    time_to_start_recording_s = Column(Integer, nullable=True)  # Time from geofence entry to recording start (seconds)
    
    # Battery tracking fields
    battery_at_geofence_entry = Column(Integer, nullable=True)  # Battery percentage at geofence entry
    charging_at_geofence_entry = Column(Boolean, nullable=True)  # Whether rep was charging at geofence entry
    battery_at_recording_start = Column(Integer, nullable=True)  # Battery percentage at recording start
    charging_at_recording_start = Column(Boolean, nullable=True)  # Whether rep was charging at recording start 