"""
Mapping tables for Shunya → Otto transformations.

These mappings translate Shunya's API values (enums, categories, etc.)
into Otto's internal domain model values.

All mappings are idempotent and handle unknown values gracefully.
"""
from typing import Optional, Dict, List
from app.models.lead import LeadStatus
from app.models.appointment import AppointmentOutcome, AppointmentStatus
from app.models.task import TaskSource, TaskAssignee, TaskStatus
from app.models.key_signal import SignalType, SignalSeverity


# ============================================================================
# CSR Call Outcome → Lead Status Mapping
# ============================================================================

SHUNYA_CSR_OUTCOME_TO_LEAD_STATUS: Dict[str, LeadStatus] = {
    # Primary mappings (to be confirmed by Shunya)
    "qualified_and_booked": LeadStatus.QUALIFIED_BOOKED,
    "qualified_not_booked": LeadStatus.QUALIFIED_UNBOOKED,
    "qualified_service_not_offered": LeadStatus.QUALIFIED_SERVICE_NOT_OFFERED,
    "not_qualified": LeadStatus.CLOSED_LOST,
    
    # Aliases (handle variations)
    "qualified": LeadStatus.QUALIFIED_UNBOOKED,
    "booked": LeadStatus.QUALIFIED_BOOKED,
    "unqualified": LeadStatus.CLOSED_LOST,
    "not_qual": LeadStatus.CLOSED_LOST,
}

# Reverse mapping for reference
LEAD_STATUS_TO_SHUNYA_CSR_OUTCOME: Dict[LeadStatus, str] = {
    v: k for k, v in SHUNYA_CSR_OUTCOME_TO_LEAD_STATUS.items()
    if k not in ["qualified", "booked", "unqualified", "not_qual"]  # Skip aliases
}


def map_shunya_csr_outcome_to_lead_status(shunya_value: Optional[str]) -> Optional[LeadStatus]:
    """
    Map Shunya CSR outcome to Otto LeadStatus.
    
    Args:
        shunya_value: Raw outcome value from Shunya
    
    Returns:
        LeadStatus enum or None if unmappable
    """
    if not shunya_value:
        return None
    
    normalized = shunya_value.lower().strip()
    return SHUNYA_CSR_OUTCOME_TO_LEAD_STATUS.get(
        normalized,
        None  # Return None for unknown values (graceful degradation)
    )


# ============================================================================
# Visit Outcome → Appointment Outcome Mapping
# ============================================================================

SHUNYA_VISIT_OUTCOME_TO_APPOINTMENT_OUTCOME: Dict[str, AppointmentOutcome] = {
    # Primary mappings (to be confirmed by Shunya)
    "won": AppointmentOutcome.WON,
    "lost": AppointmentOutcome.LOST,
    "pending_decision": AppointmentOutcome.PENDING,
    "pending": AppointmentOutcome.PENDING,
    "no_show": AppointmentOutcome.NO_SHOW,
    "rescheduled": AppointmentOutcome.RESCHEDULED,
    
    # Aliases
    "closed_won": AppointmentOutcome.WON,
    "closed_lost": AppointmentOutcome.LOST,
    "in_progress": AppointmentOutcome.PENDING,
    "decision_pending": AppointmentOutcome.PENDING,
}

# Reverse mapping for reference
APPOINTMENT_OUTCOME_TO_SHUNYA_VISIT_OUTCOME: Dict[AppointmentOutcome, str] = {
    v: k for k, v in SHUNYA_VISIT_OUTCOME_TO_APPOINTMENT_OUTCOME.items()
    if k not in ["pending", "closed_won", "closed_lost", "in_progress", "decision_pending"]
}


def map_shunya_visit_outcome_to_appointment_outcome(shunya_value: Optional[str]) -> Optional[AppointmentOutcome]:
    """
    Map Shunya visit outcome to Otto AppointmentOutcome.
    
    Args:
        shunya_value: Raw outcome value from Shunya
    
    Returns:
        AppointmentOutcome enum or None if unmappable
    """
    if not shunya_value:
        return None
    
    normalized = shunya_value.lower().strip()
    return SHUNYA_VISIT_OUTCOME_TO_APPOINTMENT_OUTCOME.get(
        normalized,
        AppointmentOutcome.PENDING  # Default to PENDING for unknown (safe default)
    )


# ============================================================================
# Visit Outcome → Appointment Status Mapping
# ============================================================================

def map_visit_outcome_to_appointment_status(outcome: AppointmentOutcome) -> AppointmentStatus:
    """
    Map AppointmentOutcome to AppointmentStatus.
    
    Completed appointments should have status COMPLETED.
    
    Args:
        outcome: Appointment outcome
    
    Returns:
        Appropriate AppointmentStatus
    """
    if outcome in [AppointmentOutcome.WON, AppointmentOutcome.LOST]:
        return AppointmentStatus.COMPLETED
    
    # Keep existing status for pending/rescheduled/no_show
    # (don't change status, caller should handle)
    return AppointmentStatus.SCHEDULED  # Safe default


# ============================================================================
# Visit Outcome → Lead Status Mapping
# ============================================================================

VISIT_OUTCOME_TO_LEAD_STATUS: Dict[AppointmentOutcome, LeadStatus] = {
    AppointmentOutcome.WON: LeadStatus.CLOSED_WON,
    AppointmentOutcome.LOST: LeadStatus.CLOSED_LOST,
    # Other outcomes don't change lead status
}


def map_visit_outcome_to_lead_status(outcome: AppointmentOutcome) -> Optional[LeadStatus]:
    """
    Map AppointmentOutcome to LeadStatus.
    
    Only WON/LOST outcomes change lead status.
    
    Args:
        outcome: Appointment outcome
    
    Returns:
        LeadStatus or None if outcome doesn't change lead status
    """
    return VISIT_OUTCOME_TO_LEAD_STATUS.get(outcome, None)


# ============================================================================
# Objection Label Mapping
# ============================================================================

# Shunya objection labels (to be confirmed)
# These are the expected categories from Shunya's objection taxonomy
SHUNYA_OBJECTION_LABELS: List[str] = [
    "price",
    "timing",
    "trust",
    "competitor",
    "need",
    "authority",
    # TODO: Add more once Shunya confirms taxonomy
]

# Mapping from Shunya objection labels to Otto's understanding
# For now, this is a pass-through (no transformation needed)
# Future: Could map to internal categories if needed
SHUNYA_OBJECTION_TO_OTTO_CATEGORY: Dict[str, str] = {
    # Currently 1:1 mapping (no transformation)
    label: label for label in SHUNYA_OBJECTION_LABELS
}


def normalize_shunya_objection_label(shunya_label: Optional[str]) -> Optional[str]:
    """
    Normalize Shunya objection label to Otto format.
    
    Args:
        shunya_label: Raw objection label from Shunya
    
    Returns:
        Normalized label or None
    """
    if not shunya_label:
        return None
    
    normalized = shunya_label.lower().strip()
    return SHUNYA_OBJECTION_TO_OTTO_CATEGORY.get(normalized, normalized)  # Pass through if unknown


# ============================================================================
# Pending Action → Task Mapping
# ============================================================================

# Mapping from Shunya action types to Otto TaskAssignee
SHUNYA_ACTION_ASSIGNEE_TYPE_TO_TASK_ASSIGNEE: Dict[str, TaskAssignee] = {
    "csr": TaskAssignee.CSR,
    "rep": TaskAssignee.REP,
    "sales_rep": TaskAssignee.REP,
    "manager": TaskAssignee.MANAGER,
    "ai": TaskAssignee.AI,
}

# Default assignee if Shunya doesn't specify
DEFAULT_TASK_ASSIGNEE_FOR_SHUNYA_ACTIONS = TaskAssignee.CSR


def map_shunya_action_to_task_assignee(action_type: Optional[str], context: str = "csr_call") -> TaskAssignee:
    """
    Map Shunya action assignee type to Otto TaskAssignee.
    
    Args:
        action_type: Assignee type from Shunya (csr, rep, manager, etc.)
        context: Context for default assignment ("csr_call" vs "visit")
    
    Returns:
        TaskAssignee enum
    """
    if not action_type:
        # Default based on context
        return TaskAssignee.CSR if context == "csr_call" else TaskAssignee.REP
    
    normalized = action_type.lower().strip()
    return SHUNYA_ACTION_ASSIGNEE_TYPE_TO_TASK_ASSIGNEE.get(
        normalized,
        DEFAULT_TASK_ASSIGNEE_FOR_SHUNYA_ACTIONS
    )


# ============================================================================
# Missed Opportunity → KeySignal Mapping
# ============================================================================

# Mapping from Shunya missed opportunity types to Otto SignalType
SHUNYA_OPPORTUNITY_TYPE_TO_SIGNAL_TYPE: Dict[str, SignalType] = {
    "upsell": SignalType.OPPORTUNITY,
    "cross_sell": SignalType.OPPORTUNITY,
    "addon": SignalType.OPPORTUNITY,
    "renewal": SignalType.OPPORTUNITY,
    "referral": SignalType.OPPORTUNITY,
    # Default: all missed opportunities are OPPORTUNITY signals
}

# Mapping from Shunya opportunity severity to Otto SignalSeverity
SHUNYA_OPPORTUNITY_SEVERITY_TO_SIGNAL_SEVERITY: Dict[str, SignalSeverity] = {
    "low": SignalSeverity.LOW,
    "medium": SignalSeverity.MEDIUM,
    "high": SignalSeverity.HIGH,
    "critical": SignalSeverity.CRITICAL,
}


def map_shunya_opportunity_to_signal_type(opportunity_type: Optional[str]) -> SignalType:
    """
    Map Shunya missed opportunity type to Otto SignalType.
    
    Args:
        opportunity_type: Type of missed opportunity from Shunya
    
    Returns:
        SignalType enum (defaults to OPPORTUNITY)
    """
    if not opportunity_type:
        return SignalType.OPPORTUNITY
    
    normalized = opportunity_type.lower().strip()
    return SHUNYA_OPPORTUNITY_TYPE_TO_SIGNAL_TYPE.get(
        normalized,
        SignalType.OPPORTUNITY  # Default to OPPORTUNITY
    )


def map_shunya_opportunity_severity_to_signal_severity(severity: Optional[str]) -> SignalSeverity:
    """
    Map Shunya opportunity severity to Otto SignalSeverity.
    
    Args:
        severity: Severity from Shunya (low, medium, high, critical)
    
    Returns:
        SignalSeverity enum (defaults to MEDIUM)
    """
    if not severity:
        return SignalSeverity.MEDIUM
    
    normalized = severity.lower().strip()
    return SHUNYA_OPPORTUNITY_SEVERITY_TO_SIGNAL_SEVERITY.get(
        normalized,
        SignalSeverity.MEDIUM  # Default to MEDIUM
    )


# ============================================================================
# SOP Stage Mapping
# ============================================================================

# Expected SOP stage names from Shunya (to be confirmed)
SHUNYA_SOP_STAGES: List[str] = [
    "greeting",
    "qualification",
    "presentation",
    "closing",
    "follow_up",
    # TODO: Add more once Shunya confirms SOP taxonomy
]


def normalize_shunya_sop_stage(stage_name: Optional[str]) -> Optional[str]:
    """
    Normalize Shunya SOP stage name to Otto format.
    
    Args:
        stage_name: Raw SOP stage name from Shunya
    
    Returns:
        Normalized stage name or None
    """
    if not stage_name:
        return None
    
    normalized = stage_name.lower().strip()
    
    # Validate against known stages (optional)
    if normalized in SHUNYA_SOP_STAGES:
        return normalized
    
    # Pass through even if unknown (for flexibility)
    return normalized


# ============================================================================
# Idempotency Helpers for Mapping
# ============================================================================

def ensure_idempotent_mapping(mapping_func, *args, **kwargs):
    """
    Wrapper to ensure mapping functions are idempotent.
    
    Same input → same output always.
    
    Args:
        mapping_func: Mapping function to call
        *args, **kwargs: Arguments to pass to mapping function
    
    Returns:
        Mapping result
    """
    # For now, this is a no-op (mappings are already idempotent)
    # Can add caching or validation here if needed
    return mapping_func(*args, **kwargs)

