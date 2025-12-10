"""
Canonical enums aligned with Shunya's enums-inventory-by-service.md.

All enums are string enums (str, Enum) for JSON serialization compatibility.
These enums serve as the source of truth for enum values across Otto backend.
"""
import enum


class BookingStatus(str, enum.Enum):
    """
    Booking status enum per Shunya canonical values.
    
    Values:
    - booked: Appointment scheduled with confirmed date/time
    - not_booked: No appointment scheduled yet, requires follow-up
    - service_not_offered: Customer needs service we don't provide
    """
    BOOKED = "booked"
    NOT_BOOKED = "not_booked"
    SERVICE_NOT_OFFERED = "service_not_offered"


class ActionType(str, enum.Enum):
    """
    Action type enum per Shunya canonical values (30 total).
    
    Used for pending actions and task creation.
    """
    # Callback / Follow-Up (CSR)
    CALL_BACK = "call_back"
    FOLLOW_UP_CALL = "follow_up_call"
    CHECK_IN = "check_in"
    
    # Send Information (CSR)
    SEND_QUOTE = "send_quote"
    SEND_ESTIMATE = "send_estimate"
    SEND_CONTRACT = "send_contract"
    SEND_INFO = "send_info"
    SEND_PHOTOS = "send_photos"
    SEND_DETAILS = "send_details"
    
    # Scheduling (CSR)
    SCHEDULE_APPOINTMENT = "schedule_appointment"
    SCHEDULE_VISIT = "schedule_visit"
    RESCHEDULE = "reschedule"
    CONFIRM_APPOINTMENT = "confirm_appointment"
    
    # Field Work (REP)
    SITE_VISIT = "site_visit"
    INSPECTION = "inspection"
    MEASUREMENT = "measurement"
    
    # Verification (CSR)
    VERIFY_INSURANCE = "verify_insurance"
    VERIFY_DETAILS = "verify_details"
    CHECK_AVAILABILITY = "check_availability"
    CONFIRM_ADDRESS = "confirm_address"
    
    # Documentation (CSR)
    PREPARE_CONTRACT = "prepare_contract"
    COLLECT_DOCUMENTS = "collect_documents"
    SEND_INVOICE = "send_invoice"
    
    # Escalation (MANAGER)
    ESCALATE = "escalate"
    MANAGER_REVIEW = "manager_review"
    GET_APPROVAL = "get_approval"
    
    # Financial (CSR)
    SETUP_FINANCING = "setup_financing"
    PROCESS_PAYMENT = "process_payment"
    SEND_PAYMENT_LINK = "send_payment_link"
    
    # Custom (Fallback)
    CUSTOM = "custom"


class AppointmentType(str, enum.Enum):
    """
    Appointment type enum per Shunya canonical values.
    
    Values:
    - in-person: Physical meeting at customer location or office
    - virtual: Video call meeting (Zoom, Teams, Google Meet, etc.)
    - phone: Phone conversation appointment
    """
    IN_PERSON = "in-person"
    VIRTUAL = "virtual"
    PHONE = "phone"


class CallOutcomeCategory(str, enum.Enum):
    """
    Call outcome category enum per Shunya canonical values.
    
    Computed from qualification_status + booking_status.
    
    Values:
    - qualified_and_booked: Lead is qualified and appointment successfully scheduled
    - qualified_service_not_offered: Lead is qualified but we don't offer the service they need
    - qualified_but_unbooked: Lead is qualified but no appointment scheduled yet
    """
    QUALIFIED_AND_BOOKED = "qualified_and_booked"
    QUALIFIED_SERVICE_NOT_OFFERED = "qualified_service_not_offered"
    QUALIFIED_BUT_UNBOOKED = "qualified_but_unbooked"


class MeetingPhase(str, enum.Enum):
    """
    Meeting phase enum per Shunya canonical values.
    
    Used in meeting segmentation analysis.
    
    Values:
    - rapport_agenda: Part 1: Relationship building, agenda setting, discovery, and needs assessment phase
    - proposal_close: Part 2: Presentation of solutions, pricing discussion, objection handling, and closing phase
    """
    RAPPORT_AGENDA = "rapport_agenda"
    PROPOSAL_CLOSE = "proposal_close"


class MissedOpportunityType(str, enum.Enum):
    """
    Missed opportunity type enum per Shunya canonical values.
    
    Used in opportunity analysis.
    
    Values:
    - discovery: Missed questions during needs discovery phase
    - cross_sell: Missed opportunity to offer additional/complementary services
    - upsell: Missed opportunity to suggest premium/upgraded options
    - qualification: Missed BANT (Budget, Authority, Need, Timeline) questions
    """
    DISCOVERY = "discovery"
    CROSS_SELL = "cross_sell"
    UPSELL = "upsell"
    QUALIFICATION = "qualification"


class CallType(str, enum.Enum):
    """
    Call type enum per Shunya canonical values.
    
    Values:
    - sales_call: Sales appointment call
    - csr_call: Customer service representative call
    """
    SALES_CALL = "sales_call"
    CSR_CALL = "csr_call"


# Helper functions for enum validation and mapping

def normalize_booking_status(value: str | None) -> str | None:
    """
    Normalize booking status string to canonical enum value.
    
    Args:
        value: Raw booking status string (may be None or invalid)
    
    Returns:
        Canonical enum value string or None if invalid/unknown
    """
    if not value:
        return None
    
    value_lower = value.lower().strip()
    
    # Map common variations to canonical values
    mapping = {
        "booked": BookingStatus.BOOKED.value,
        "not_booked": BookingStatus.NOT_BOOKED.value,
        "not-booked": BookingStatus.NOT_BOOKED.value,
        "service_not_offered": BookingStatus.SERVICE_NOT_OFFERED.value,
        "service-not-offered": BookingStatus.SERVICE_NOT_OFFERED.value,
    }
    
    # Check if it's already a canonical value
    try:
        BookingStatus(value_lower)
        return value_lower
    except ValueError:
        pass
    
    # Try mapping
    if value_lower in mapping:
        return mapping[value_lower]
    
    # Unknown value, return None (non-throwing)
    return None


def normalize_action_type(value: str | None) -> str | None:
    """
    Normalize action type string to canonical enum value.
    
    Args:
        value: Raw action type string (may be None or invalid)
    
    Returns:
        Canonical enum value string or None if invalid/unknown
    """
    if not value:
        return None
    
    value_lower = value.lower().strip()
    
    # Check if it's already a canonical value
    try:
        ActionType(value_lower)
        return value_lower
    except ValueError:
        pass
    
    # Unknown value, return None (non-throwing)
    return None


def normalize_appointment_type(value: str | None) -> str | None:
    """
    Normalize appointment type string to canonical enum value.
    
    Args:
        value: Raw appointment type string (may be None or invalid)
    
    Returns:
        Canonical enum value string or None if invalid/unknown
    """
    if not value:
        return None
    
    value_lower = value.lower().strip()
    
    # Map common variations
    mapping = {
        "in_person": AppointmentType.IN_PERSON.value,
        "in-person": AppointmentType.IN_PERSON.value,
        "virtual": AppointmentType.VIRTUAL.value,
        "phone": AppointmentType.PHONE.value,
    }
    
    # Check if it's already a canonical value
    try:
        AppointmentType(value_lower)
        return value_lower
    except ValueError:
        pass
    
    # Try mapping
    if value_lower in mapping:
        return mapping[value_lower]
    
    # Unknown value, return None (non-throwing)
    return None


def normalize_call_type(value: str | None) -> str | None:
    """
    Normalize call type string to canonical enum value.
    
    Args:
        value: Raw call type string (may be None or invalid)
    
    Returns:
        Canonical enum value string or None if invalid/unknown
    """
    if not value:
        return None
    
    value_lower = value.lower().strip()
    
    # Map common variations
    mapping = {
        "sales": CallType.SALES_CALL.value,
        "csr": CallType.CSR_CALL.value,
        "customer_service": CallType.CSR_CALL.value,
    }
    
    # Check if it's already a canonical value
    try:
        CallType(value_lower)
        return value_lower
    except ValueError:
        pass
    
    # Try mapping
    if value_lower in mapping:
        return mapping[value_lower]
    
    # Unknown value, return None (non-throwing)
    return None


def normalize_meeting_phase(value: str | None) -> str | None:
    """
    Normalize meeting phase string to canonical enum value.
    
    Args:
        value: Raw meeting phase string (may be None or invalid)
    
    Returns:
        Canonical enum value string or None if invalid/unknown
    """
    if not value:
        return None
    
    value_lower = value.lower().strip()
    
    # Check if it's already a canonical value
    try:
        MeetingPhase(value_lower)
        return value_lower
    except ValueError:
        pass
    
    # Unknown value, return None (non-throwing)
    return None


def normalize_missed_opportunity_type(value: str | None) -> str | None:
    """
    Normalize missed opportunity type string to canonical enum value.
    
    Args:
        value: Raw missed opportunity type string (may be None or invalid)
    
    Returns:
        Canonical enum value string or None if invalid/unknown
    """
    if not value:
        return None
    
    value_lower = value.lower().strip()
    
    # Check if it's already a canonical value
    try:
        MissedOpportunityType(value_lower)
        return value_lower
    except ValueError:
        pass
    
    # Unknown value, return None (non-throwing)
    return None


def compute_call_outcome_category(
    qualification_status: str | None,
    booking_status: str | None
) -> str | None:
    """
    Compute CallOutcomeCategory from qualification_status + booking_status.
    
    Per Shunya contract, this is a computed enum.
    
    Args:
        qualification_status: Qualification status (e.g., "qualified", "unqualified")
        booking_status: Booking status (e.g., "booked", "not_booked", "service_not_offered")
    
    Returns:
        Canonical CallOutcomeCategory value or None if cannot be computed
    """
    if not qualification_status or not booking_status:
        return None
    
    qual_lower = qualification_status.lower().strip()
    booking_lower = booking_status.lower().strip()
    
    # Only compute if qualified (but not unqualified)
    if "unqualified" in qual_lower or "qualified" not in qual_lower:
        return None
    
    # Map to canonical outcome category
    if booking_lower == BookingStatus.BOOKED.value:
        return CallOutcomeCategory.QUALIFIED_AND_BOOKED.value
    elif booking_lower == BookingStatus.SERVICE_NOT_OFFERED.value:
        return CallOutcomeCategory.QUALIFIED_SERVICE_NOT_OFFERED.value
    elif booking_lower == BookingStatus.NOT_BOOKED.value:
        return CallOutcomeCategory.QUALIFIED_BUT_UNBOOKED.value
    
    return None

