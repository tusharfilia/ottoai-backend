from datetime import datetime, date, time
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class LeadStatus(str, Enum):
    NEW = "new"
    QUALIFIED_BOOKED = "qualified_booked"
    QUALIFIED_UNBOOKED = "qualified_unbooked"
    QUALIFIED_SERVICE_NOT_OFFERED = "qualified_service_not_offered"
    NURTURING = "nurturing"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class LeadSource(str, Enum):
    UNKNOWN = "unknown"
    INBOUND_CALL = "inbound_call"
    INBOUND_WEB = "inbound_web"
    REFERRAL = "referral"
    PARTNER = "partner"
    OTHER = "other"


class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class AppointmentOutcome(str, Enum):
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"


class ContactCardBase(BaseModel):
    id: str = Field(..., description="Unique identifier for the contact card")
    company_id: str = Field(..., description="Tenant/company identifier")
    primary_phone: Optional[str] = Field(None, description="Primary phone number")
    secondary_phone: Optional[str] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    metadata: Optional[dict] = Field(None, alias="custom_metadata", serialization_alias="metadata", description="Arbitrary metadata captured for the contact")
    property_snapshot: Optional[dict] = Field(
        None,
        description="Property intelligence snapshot (roof_type, square_feet, stories, etc.)",
    )
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class LeadSummary(BaseModel):
    id: str
    company_id: str
    contact_card_id: str
    status: LeadStatus
    source: LeadSource
    priority: Optional[str] = None
    score: Optional[int] = None
    last_contacted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppointmentSummary(BaseModel):
    id: str
    lead_id: str
    contact_card_id: Optional[str] = None
    company_id: str
    assigned_rep_id: Optional[str] = None
    scheduled_start: datetime
    scheduled_end: Optional[datetime] = None
    status: AppointmentStatus
    outcome: AppointmentOutcome
    location: Optional[str] = None
    service_type: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PropertyIntelligence(BaseModel):
    """Normalized property intelligence data extracted from public sources."""
    roof_type: Optional[str] = None
    square_feet: Optional[int] = None
    stories: Optional[int] = None
    year_built: Optional[int] = None
    access_notes: Optional[str] = None
    solar: Optional[str] = None
    hoa: Optional[str] = None
    subdivision: Optional[str] = None
    last_sale_date: Optional[str] = None
    last_sale_price: Optional[str] = None
    est_value_range: Optional[str] = None
    potential_equity: Optional[str] = None
    is_for_sale: Optional[str] = None
    sources: List[str] = Field(default_factory=list, description="Sources used for property data")
    google_earth_url: Optional[str] = Field(None, description="Google Earth URL for this property")
    updated_at: Optional[datetime] = Field(None, description="When property snapshot was last updated")
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Task Schemas (Section 3.5)
# ============================================================================

class TaskSource(str, Enum):
    OTTO = "otto"
    SHUNYA = "shunya"
    MANUAL = "manual"


class TaskAssignee(str, Enum):
    CSR = "csr"
    REP = "rep"
    MANAGER = "manager"
    AI = "ai"


class TaskStatus(str, Enum):
    OPEN = "open"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class TaskSummary(BaseModel):
    id: str
    description: str
    assigned_to: TaskAssignee
    source: TaskSource
    due_at: Optional[datetime] = None
    status: TaskStatus
    completed_at: Optional[datetime] = None
    priority: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Key Signal Schemas (Section 3.6)
# ============================================================================

class SignalType(str, Enum):
    RISK = "risk"
    OPPORTUNITY = "opportunity"
    COACHING = "coaching"
    OPERATIONAL = "operational"


class SignalSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class KeySignalSummary(BaseModel):
    id: str
    signal_type: SignalType
    severity: SignalSeverity
    title: str
    description: Optional[str] = None
    acknowledged: bool = False
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Event Log Schemas (Section 4.6, 5.3)
# ============================================================================

class EventType(str, Enum):
    CALL_RECEIVED = "call_received"
    CALL_MISSED = "call_missed"
    CALL_COMPLETED = "call_completed"
    SMS_SENT = "sms_sent"
    SMS_RECEIVED = "sms_received"
    AUTOMATION_NURTURE = "automation_nurture"
    AUTOMATION_FOLLOWUP = "automation_followup"
    APPOINTMENT_CREATED = "appointment_created"
    APPOINTMENT_RESCHEDULED = "appointment_rescheduled"
    REP_ASSIGNED = "rep_assigned"
    REP_ARRIVED = "rep_arrived"
    RECORDING_STARTED = "recording_started"
    RECORDING_ENDED = "recording_ended"
    REP_DEPARTED = "rep_departed"
    APPOINTMENT_OUTCOME = "appointment_outcome"
    DEAL_WON = "deal_won"
    DEAL_LOST = "deal_lost"
    PROPERTY_INTELLIGENCE_UPDATED = "property_intelligence_updated"


class EventLogSummary(BaseModel):
    id: str
    event_type: EventType
    timestamp: datetime
    description: Optional[str] = None
    actor_role: Optional[str] = None
    metadata: Optional[dict] = None
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Call Schemas (with transcript/intelligence)
# ============================================================================

class CallTranscriptSummary(BaseModel):
    id: str
    transcript_text: Optional[str] = None  # May be None in Ghost Mode
    confidence_score: Optional[float] = None
    word_count: Optional[int] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class CallAnalysisSummary(BaseModel):
    id: str
    objections: Optional[List[str]] = None
    objection_details: Optional[List[dict]] = None
    sentiment_score: Optional[float] = None
    engagement_score: Optional[float] = None
    coaching_tips: Optional[List[dict]] = None
    sop_stages_completed: Optional[List[str]] = None
    sop_stages_missed: Optional[List[str]] = None
    sop_compliance_score: Optional[float] = None
    rehash_score: Optional[float] = None
    lead_quality: Optional[str] = None
    conversion_probability: Optional[float] = None
    analyzed_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class CallSummary(BaseModel):
    call_id: int
    phone_number: str
    direction: Optional[str] = None  # inbound/outbound
    missed_call: bool
    booked: bool
    bought: bool
    created_at: datetime
    duration_seconds: Optional[int] = None
    transcript: Optional[CallTranscriptSummary] = None
    analysis: Optional[CallAnalysisSummary] = None
    recording_url: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# SMS/Message Schemas (Section 5.3 Tab 2)
# ============================================================================

class MessageSummary(BaseModel):
    timestamp: datetime
    sender: str  # phone number or user ID
    role: str  # customer/csr/otto/rep
    body: str
    direction: str  # inbound/outbound
    type: str  # manual/automated
    message_sid: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Recording Session Schemas (Section 4.8)
# ============================================================================

class RecordingSessionSummary(BaseModel):
    id: str
    appointment_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    mode: RecordingMode
    audio_url: Optional[str] = None  # Nullable in Ghost Mode
    transcription_status: TranscriptionStatus
    analysis_status: AnalysisStatus
    outcome_classification: Optional[str] = None
    sentiment_score: Optional[float] = None
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# SOP Compliance Schemas (Section 4.5)
# ============================================================================

class SopChecklistItem(str, Enum):
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


class SopItemStatus(str, Enum):
    COMPLETED = "completed"
    MISSED = "missed"
    WARNING = "warning"


class SopComplianceItem(BaseModel):
    checklist_item: SopChecklistItem
    status: SopItemStatus
    notes: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Appointment Detail Schema (Extended)
# ============================================================================

class AppointmentDetailExtended(AppointmentSummary):
    notes: Optional[str] = None
    external_id: Optional[str] = None
    deal_size: Optional[float] = None
    material_type: Optional[str] = None
    financing_type: Optional[str] = None
    assigned_rep_name: Optional[str] = None
    assigned_at: Optional[datetime] = None
    rep_claimed: bool = False
    route_position: Optional[int] = None
    route_group: Optional[str] = None
    arrival_at: Optional[datetime] = None
    departure_at: Optional[datetime] = None
    on_site_duration: Optional[int] = None
    recording_sessions: List[RecordingSessionSummary] = Field(default_factory=list)
    sop_compliance: List[SopComplianceItem] = Field(default_factory=list)
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Lead Detail Schema (Extended)
# ============================================================================

class LeadDetailExtended(LeadSummary):
    campaign: Optional[str] = None
    pipeline_stage: Optional[str] = None
    tags: Optional[dict] = None
    deal_status: Optional[str] = None
    deal_size: Optional[float] = None
    deal_summary: Optional[str] = None
    closed_at: Optional[datetime] = None
    assigned_rep_id: Optional[str] = None
    assigned_rep_name: Optional[str] = None
    assigned_at: Optional[datetime] = None
    rep_claimed: bool = False
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Contact Card Detail Schema (Full Structure - Section 2)
# ============================================================================

class ContactCardTopSection(BaseModel):
    """Top Section - Current Status & Priority (Section 3)."""
    # Customer Snapshot (3.1)
    lead_source: Optional[str] = None
    lead_age_days: Optional[int] = None  # Computed from lead.created_at
    last_activity_at: Optional[datetime] = None
    
    # Deal Status (3.2)
    deal_status: Optional[str] = None
    deal_size: Optional[float] = None
    deal_summary: Optional[str] = None
    closed_at: Optional[datetime] = None
    
    # Rep Assignment (3.3)
    assigned_rep_id: Optional[str] = None
    assigned_rep_name: Optional[str] = None
    assigned_at: Optional[datetime] = None
    rep_claimed: bool = False
    route_position: Optional[int] = None
    route_group: Optional[str] = None
    distance_from_previous_stop: Optional[float] = None
    
    # Tasks (3.5)
    tasks: List[TaskSummary] = Field(default_factory=list)
    
    # Key Signals (3.6)
    key_signals: List[KeySignalSummary] = Field(default_factory=list)
    
    model_config = ConfigDict(from_attributes=True)


class ContactCardMiddleSection(BaseModel):
    """Middle Section - Sales Appointment & Performance (Section 4)."""
    # Only appears after booking
    # Appointment Header (4.1)
    active_appointment: Optional[AppointmentDetailExtended] = None
    
    # Property Intelligence (4.2)
    property_intelligence: Optional[PropertyIntelligence] = None
    
    # Rep Assignment Details (4.3) - already in Top Section
    
    # Appointment Overview (4.4) - already in active_appointment
    
    # SOP Compliance (4.5)
    sop_compliance: List[SopComplianceItem] = Field(default_factory=list)
    
    # Visit Activity Timeline (4.6)
    visit_timeline: List[EventLogSummary] = Field(default_factory=list)
    
    # Geofence Events (4.7) - already in active_appointment
    
    # Recording Sessions (4.8)
    recording_sessions: List[RecordingSessionSummary] = Field(default_factory=list)
    
    # Tasks (4.9)
    appointment_tasks: List[TaskSummary] = Field(default_factory=list)
    
    # Escalation Warnings (4.10)
    escalation_warnings: List[str] = Field(default_factory=list)
    
    # Transcript Intelligence (4.11)
    transcript_intelligence: Optional[CallAnalysisSummary] = None
    
    model_config = ConfigDict(from_attributes=True)


class ContactCardBottomSection(BaseModel):
    """Bottom Section - How Customer Was Booked (Section 5)."""
    # Narrative Summary (5.1)
    narrative_summary: Optional[str] = None  # Generated summary
    
    # Booking Risk/Context Chips (5.2)
    booking_chips: List[dict] = Field(default_factory=list)  # List of {label, severity, metadata}
    
    # Call Recordings (5.3 Tab 1)
    call_recordings: List[CallSummary] = Field(default_factory=list)
    
    # Text Messages (5.3 Tab 2)
    text_messages: List[MessageSummary] = Field(default_factory=list)
    
    # Booking Timeline (5.3 Tab 3)
    booking_timeline: List[EventLogSummary] = Field(default_factory=list)
    
    model_config = ConfigDict(from_attributes=True)


class ContactCardGlobalBlocks(BaseModel):
    """Global Data Blocks (Section 6)."""
    # Calls (6.1)
    all_calls: List[CallSummary] = Field(default_factory=list)
    
    # Messages (6.2)
    all_messages: List[MessageSummary] = Field(default_factory=list)
    
    # Automation Events (6.3)
    automation_events: List[EventLogSummary] = Field(default_factory=list)
    
    # Property Intelligence (6.4) - already in Middle Section
    
    # Pending Action Items (6.5)
    pending_actions: List[TaskSummary] = Field(default_factory=list)
    
    # AI Insights (6.6)
    ai_insights: Optional[dict] = Field(None, description="Aggregated insights: missed_opps, sop_compliance, objections, buying_signals, deal_risk")
    
    # Recording Sessions (6.7) - already in Middle Section
    
    # Task System (6.8) - already distributed in Top/Middle
    
    model_config = ConfigDict(from_attributes=True)


class ContactCardDetail(ContactCardBase):
    """
    Full Contact Card Detail with Top/Middle/Bottom sections + Global blocks.
    
    This is the canonical response for GET /api/v1/contact-cards/{id}.
    """
    full_name: Optional[str] = Field(None, description="Convenience field combining first and last name")
    
    # Sectioned structure (Section 2)
    top_section: ContactCardTopSection = Field(..., description="Current Status & Priority")
    middle_section: Optional[ContactCardMiddleSection] = Field(None, description="Sales Appointment & Performance (only after booking)")
    bottom_section: ContactCardBottomSection = Field(..., description="How Customer Was Booked")
    global_blocks: ContactCardGlobalBlocks = Field(..., description="Global Data Blocks")
    
    # Backward compatibility: keep flat fields for existing frontend
    property_intelligence: Optional[PropertyIntelligence] = Field(
        None, description="Property intelligence (also in middle_section)"
    )
    leads: List[LeadSummary] = Field(default_factory=list)
    appointments: List[AppointmentSummary] = Field(default_factory=list)
    recent_call_ids: List[int] = Field(default_factory=list)
    
    model_config = ConfigDict(from_attributes=True)


class LeadDetail(LeadSummary):
    campaign: Optional[str] = None
    pipeline_stage: Optional[str] = None
    tags: Optional[dict] = None


class AppointmentDetail(AppointmentSummary):
    notes: Optional[str] = None
    external_id: Optional[str] = None
class LeadResponse(BaseModel):
    lead: LeadDetail
    contact: Optional[ContactCardBase] = None
    appointments: List[AppointmentSummary] = Field(default_factory=list)


class AppointmentResponse(BaseModel):
    appointment: AppointmentDetail
    lead: Optional[LeadSummary] = None
    contact: Optional[ContactCardBase] = None


# ============================================================================
# Rep Shift Schemas
# ============================================================================

class ShiftStatus(str, Enum):
    OFF = "off"
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class RepShiftBase(BaseModel):
    id: str
    rep_id: str
    company_id: str
    shift_date: date
    clock_in_at: Optional[datetime] = None
    clock_out_at: Optional[datetime] = None
    scheduled_start: Optional[time] = None
    scheduled_end: Optional[time] = None
    status: ShiftStatus
    notes: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class RepShiftCreate(BaseModel):
    """Request body for creating/updating a shift."""
    desired_start_time: Optional[datetime] = Field(None, description="Desired clock-in time (optional)")
    notes: Optional[str] = None


class RepShiftResponse(BaseModel):
    """Response for shift operations."""
    shift: RepShiftBase
    effective_start_time: Optional[datetime] = Field(None, description="Effective shift start time")
    effective_end_time: Optional[datetime] = Field(None, description="Effective shift end time")
    recording_mode: str = Field(..., description="Recording mode for this rep")
    allow_location_tracking: bool = Field(..., description="Whether location tracking is allowed")
    allow_recording: bool = Field(..., description="Whether recording is allowed")


# ============================================================================
# Recording Session Schemas
# ============================================================================

class RecordingMode(str, Enum):
    NORMAL = "normal"
    GHOST = "ghost"
    OFF = "off"


class AudioStorageMode(str, Enum):
    PERSISTENT = "persistent"
    EPHEMERAL = "ephemeral"
    NOT_STORED = "not_stored"


class TranscriptionStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class LocationInput(BaseModel):
    """Location coordinates for geofence operations."""
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")


class RecordingSessionStartRequest(BaseModel):
    """Request to start a recording session."""
    rep_id: str = Field(..., description="Sales rep ID")
    appointment_id: str = Field(..., description="Appointment ID")
    mode: Optional[RecordingMode] = Field(None, description="Recording mode (if omitted, uses rep default)")
    location: LocationInput = Field(..., description="Current location")


class RecordingSessionStartResponse(BaseModel):
    """Response when starting a recording session."""
    recording_session_id: str = Field(..., description="ID of the created recording session")
    mode: RecordingMode = Field(..., description="Recording mode being used")
    audio_storage_mode: AudioStorageMode = Field(..., description="How audio will be stored")
    audio_upload_url: Optional[str] = Field(None, description="URL to upload audio (if applicable)")
    shunya_job_config: Optional[dict] = Field(None, description="Shunya job configuration (if applicable)")


class RecordingSessionStopRequest(BaseModel):
    """Request to stop a recording session."""
    location: LocationInput = Field(..., description="Current location when stopping")


class RecordingSessionBase(BaseModel):
    """Base recording session schema."""
    id: str
    company_id: str
    rep_id: str
    appointment_id: str
    shift_id: Optional[str] = None
    mode: RecordingMode
    audio_storage_mode: AudioStorageMode
    started_at: datetime
    ended_at: Optional[datetime] = None
    start_lat: Optional[float] = None
    start_lng: Optional[float] = None
    end_lat: Optional[float] = None
    end_lng: Optional[float] = None
    geofence_radius_start: Optional[float] = None
    geofence_radius_stop: Optional[float] = None
    audio_url: Optional[str] = None  # Will be None in Ghost Mode
    audio_duration_seconds: Optional[float] = None
    audio_size_bytes: Optional[int] = None
    transcription_status: TranscriptionStatus
    analysis_status: AnalysisStatus
    shunya_asr_job_id: Optional[str] = None
    shunya_analysis_job_id: Optional[str] = None
    error_message: Optional[str] = None
    expires_at: Optional[datetime] = None  # For ephemeral storage
    
    model_config = ConfigDict(from_attributes=True)


class RecordingSessionResponse(BaseModel):
    """Response for recording session operations."""
    session: RecordingSessionBase


