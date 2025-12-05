"""
Contract stubs for Shunya API structures.

These Pydantic models represent the expected shapes of Shunya API responses.
They are normalized, expected structures that will be populated once Shunya
confirms final schemas.

All fields are Optional to handle graceful degradation when Shunya sends
incomplete data. These models serve as contracts, not validation schemas.
"""
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# ============================================================================
# Enums (Expected from Shunya - to be confirmed)
# ============================================================================

class ShunyaCSROutcome(str, Enum):
    """
    Expected CSR call outcome values from Shunya.
    
    TODO: Replace with actual enum values once Shunya confirms.
    """
    QUALIFIED_AND_BOOKED = "qualified_and_booked"
    QUALIFIED_NOT_BOOKED = "qualified_not_booked"
    QUALIFIED_SERVICE_NOT_OFFERED = "qualified_service_not_offered"
    NOT_QUALIFIED = "not_qualified"
    # Placeholder for unknown values
    UNKNOWN = "unknown"


class ShunyaVisitOutcome(str, Enum):
    """
    Expected sales visit outcome values from Shunya.
    
    TODO: Replace with actual enum values once Shunya confirms.
    """
    WON = "won"
    LOST = "lost"
    PENDING_DECISION = "pending_decision"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"
    # Placeholder for unknown values
    UNKNOWN = "unknown"


class ShunyaObjectionLabel(str, Enum):
    """
    Expected objection label taxonomy from Shunya.
    
    TODO: Replace with complete taxonomy once Shunya confirms.
    """
    PRICE = "price"
    TIMING = "timing"
    TRUST = "trust"
    COMPETITOR = "competitor"
    NEED = "need"
    AUTHORITY = "authority"
    # Placeholder for unknown values
    UNKNOWN = "unknown"


class ShunyaSOPSStage(str, Enum):
    """
    Expected SOP stage identifiers from Shunya.
    
    TODO: Replace with actual SOP taxonomy once Shunya confirms.
    """
    GREETING = "greeting"
    QUALIFICATION = "qualification"
    PRESENTATION = "presentation"
    CLOSING = "closing"
    FOLLOW_UP = "follow_up"
    # Placeholder for unknown values
    UNKNOWN = "unknown"


# ============================================================================
# Objection Structures
# ============================================================================

class ShunyaObjection(BaseModel):
    """Expected structure for a single objection from Shunya."""
    
    objection_text: Optional[str] = Field(None, description="Full text of the objection")
    objection_label: Optional[str] = Field(None, description="Categorized label (price, timing, etc.)")
    severity: Optional[str] = Field(None, description="Severity: low, medium, high")
    overcome: Optional[bool] = Field(None, description="Whether objection was overcome")
    timestamp: Optional[datetime] = Field(None, description="When objection was raised")
    speaker_id: Optional[str] = Field(None, description="Speaker who raised objection")
    category_id: Optional[str] = Field(None, description="Internal category ID")
    category_text: Optional[str] = Field(None, description="Human-readable category")


class ShunyaObjectionsResponse(BaseModel):
    """Expected structure for objections response from Shunya."""
    
    objections: List[ShunyaObjection] = Field(default_factory=list, description="List of objections")
    total_objections: Optional[int] = Field(None, description="Total count of objections")
    severity_breakdown: Optional[Dict[str, int]] = Field(None, description="Count by severity")


# ============================================================================
# Qualification Structures
# ============================================================================

class ShunyaBANTScores(BaseModel):
    """Expected BANT scoring structure from Shunya."""
    
    budget: Optional[float] = Field(None, description="Budget score (0-1)")
    authority: Optional[float] = Field(None, description="Authority score (0-1)")
    need: Optional[float] = Field(None, description="Need score (0-1)")
    timeline: Optional[float] = Field(None, description="Timeline score (0-1)")


class ShunyaQualificationResponse(BaseModel):
    """Expected structure for qualification response from Shunya."""
    
    qualification_status: Optional[str] = Field(None, description="Overall qualification status")
    bant_scores: Optional[ShunyaBANTScores] = Field(None, description="BANT scoring breakdown")
    overall_score: Optional[float] = Field(None, description="Overall qualification score (0-1)")
    confidence_score: Optional[float] = Field(None, description="Confidence in qualification (0-1)")
    decision_makers: Optional[List[str]] = Field(None, description="Identified decision makers")
    urgency_signals: Optional[List[str]] = Field(None, description="Urgency indicators")
    budget_indicators: Optional[List[str]] = Field(None, description="Budget indicators")


# ============================================================================
# SOP Compliance Structures
# ============================================================================

class ShunyaSOPStage(BaseModel):
    """Expected structure for a single SOP stage."""
    
    stage_name: Optional[str] = Field(None, description="Name of SOP stage")
    completed: Optional[bool] = Field(None, description="Whether stage was completed")
    score: Optional[float] = Field(None, description="Score for this stage (0-1)")
    notes: Optional[str] = Field(None, description="Notes about stage execution")


class ShunyaComplianceResponse(BaseModel):
    """Expected structure for SOP compliance response from Shunya."""
    
    stages_followed: Optional[List[str]] = Field(None, description="List of stages that were followed")
    stages_missed: Optional[List[str]] = Field(None, description="List of stages that were missed")
    compliance_score: Optional[float] = Field(None, description="Overall compliance score (0-1)")
    stage_details: Optional[List[ShunyaSOPStage]] = Field(None, description="Detailed stage information")
    recommendations: Optional[List[str]] = Field(None, description="Recommendations for improvement")


# ============================================================================
# Pending Action Structures
# ============================================================================

class ShunyaPendingAction(BaseModel):
    """
    Expected structure for a pending action from Shunya.
    
    Aligned with final Shunya contract: Action types are free-string (e.g., "follow up tomorrow", "send technician").
    Shunya may later freeze these into enums, but we must be tolerant of arbitrary strings.
    """
    
    action: Optional[str] = Field(None, description="Action text/description (free-string)")
    action_type: Optional[str] = Field(None, description="Type of action - FREE STRING (e.g., 'follow up tomorrow', 'send technician', not enum)")
    priority: Optional[str] = Field(None, description="Priority: high, medium, low")
    due_at: Optional[Union[datetime, str]] = Field(None, description="When action is due")
    assignee_type: Optional[str] = Field(None, description="Who should complete (csr, rep, manager)")
    context: Optional[str] = Field(None, description="Additional context for action")
    
    # Note: action_type accepts any string value - adapters must map common patterns to internal enums
    # with graceful fallback to generic/custom type for unknown strings


# ============================================================================
# Missed Opportunity Structures
# ============================================================================

class ShunyaMissedOpportunity(BaseModel):
    """Expected structure for a missed opportunity from Shunya."""
    
    opportunity_text: Optional[str] = Field(None, description="Description of missed opportunity")
    opportunity_type: Optional[str] = Field(None, description="Type (upsell, cross_sell, etc.)")
    severity: Optional[str] = Field(None, description="Severity: low, medium, high")
    timestamp: Optional[datetime] = Field(None, description="When opportunity was identified")
    context: Optional[str] = Field(None, description="Context where opportunity occurred")


# ============================================================================
# Entity Extraction Structures
# ============================================================================

class ShunyaEntities(BaseModel):
    """Expected structure for extracted entities from Shunya."""
    
    address: Optional[str] = Field(None, description="Extracted address")
    phone_number: Optional[str] = Field(None, description="Extracted phone number")
    email: Optional[str] = Field(None, description="Extracted email")
    appointment_date: Optional[Union[datetime, str]] = Field(None, description="Extracted appointment date")
    scheduled_time: Optional[Union[datetime, str]] = Field(None, description="Extracted scheduled time")
    company_name: Optional[str] = Field(None, description="Extracted company name")
    person_name: Optional[str] = Field(None, description="Extracted person name")
    budget: Optional[float] = Field(None, description="Extracted budget amount")
    other: Optional[Dict[str, Any]] = Field(None, description="Other extracted entities")


# ============================================================================
# Summary Structures
# ============================================================================

class ShunyaSummaryResponse(BaseModel):
    """Expected structure for call/visit summary from Shunya."""
    
    summary: Optional[str] = Field(None, description="Full summary text")
    key_points: Optional[List[str]] = Field(None, description="Key points extracted")
    next_steps: Optional[List[str]] = Field(None, description="Recommended next steps")
    sentiment: Optional[str] = Field(None, description="Overall sentiment")
    confidence: Optional[float] = Field(None, description="Confidence in summary (0-1)")


# ============================================================================
# CSR Call Analysis (Complete Structure)
# ============================================================================

class ShunyaCSRCallAnalysis(BaseModel):
    """
    Expected complete structure for CSR call analysis from Shunya.
    
    This is the main contract for CSR call analysis responses.
    """
    
    job_id: Optional[str] = Field(None, description="Shunya job ID for this analysis")
    call_id: Optional[int] = Field(None, description="Otto call ID")
    
    qualification: Optional[ShunyaQualificationResponse] = Field(None, description="Lead qualification data")
    objections: Optional[ShunyaObjectionsResponse] = Field(None, description="Objections data")
    compliance: Optional[ShunyaComplianceResponse] = Field(None, description="SOP compliance data")
    summary: Optional[ShunyaSummaryResponse] = Field(None, description="Call summary")
    
    sentiment_score: Optional[float] = Field(None, description="Sentiment score (-1 to 1 or 0 to 1)")
    
    pending_actions: Optional[List[ShunyaPendingAction]] = Field(None, description="Pending actions identified")
    missed_opportunities: Optional[List[ShunyaMissedOpportunity]] = Field(None, description="Missed opportunities")
    
    entities: Optional[ShunyaEntities] = Field(None, description="Extracted entities")
    
    analyzed_at: Optional[datetime] = Field(None, description="When analysis was completed")
    confidence_score: Optional[float] = Field(None, description="Overall confidence in analysis (0-1)")


# ============================================================================
# Visit Analysis (Complete Structure)
# ============================================================================

class ShunyaVisitAnalysis(BaseModel):
    """
    Expected complete structure for sales visit analysis from Shunya.
    
    This is the main contract for visit analysis responses.
    """
    
    job_id: Optional[str] = Field(None, description="Shunya job ID for this analysis")
    appointment_id: Optional[str] = Field(None, description="Otto appointment ID")
    
    outcome: Optional[str] = Field(None, description="Visit outcome (won, lost, pending, etc.)")
    appointment_outcome: Optional[str] = Field(None, description="Alias for outcome")
    
    qualification: Optional[ShunyaQualificationResponse] = Field(None, description="Qualification data")
    objections: Optional[ShunyaObjectionsResponse] = Field(None, description="Objections raised")
    compliance: Optional[ShunyaComplianceResponse] = Field(None, description="SOP compliance")
    summary: Optional[ShunyaSummaryResponse] = Field(None, description="Visit summary")
    
    sentiment_score: Optional[float] = Field(None, description="Sentiment score")
    
    visit_actions: Optional[List[ShunyaPendingAction]] = Field(None, description="Actions from visit")
    pending_actions: Optional[List[ShunyaPendingAction]] = Field(None, description="Alias for visit_actions")
    missed_opportunities: Optional[List[ShunyaMissedOpportunity]] = Field(None, description="Missed opportunities")
    
    entities: Optional[ShunyaEntities] = Field(None, description="Extracted entities")
    
    deal_size: Optional[float] = Field(None, description="Deal size if outcome is won")
    deal_currency: Optional[str] = Field(None, description="Currency for deal size")
    
    analyzed_at: Optional[datetime] = Field(None, description="When analysis was completed")
    confidence_score: Optional[float] = Field(None, description="Overall confidence (0-1)")


# ============================================================================
# Meeting Segmentation Structures
# ============================================================================

class ShunyaSegmentationPart(BaseModel):
    """
    Expected structure for a single segmentation part (Part1 or Part2).
    
    Aligned with final Shunya contract.
    """
    
    start_time: Optional[Union[float, int]] = Field(None, description="Start time offset in seconds")
    end_time: Optional[Union[float, int]] = Field(None, description="End time offset in seconds")
    duration: Optional[Union[float, int]] = Field(None, description="Duration in seconds")
    content: Optional[str] = Field(None, description="Content/summary text for this part")
    key_points: Optional[List[str]] = Field(None, description="Key points discussed in this part")
    
    # Legacy fields (for backward compatibility during transition)
    transcript: Optional[str] = Field(None, description="Legacy: transcript for this part")
    summary: Optional[str] = Field(None, description="Legacy: summary of this part")
    sentiment_score: Optional[float] = Field(None, description="Legacy: sentiment score for this part")
    key_topics: Optional[List[str]] = Field(None, description="Legacy: key topics discussed")
    duration_seconds: Optional[int] = Field(None, description="Legacy: duration of this part")


class ShunyaMeetingSegmentation(BaseModel):
    """
    Expected structure for meeting segmentation response from Shunya.
    
    Aligned with final Shunya contract structure:
    {
        "success": true,
        "call_id": 3070,
        "part1": {...},
        "part2": {...},
        "segmentation_confidence": 0.8,
        "transition_point": 240,
        "transition_indicators": [...],
        "meeting_structure_score": 4,
        "call_type": "sales_appointment",
        "created_at": null
    }
    
    Segments sales visit into Part1 (rapport/agenda) and Part2 (proposal/close).
    """
    
    success: Optional[bool] = Field(True, description="Success indicator (true for valid segmentation)")
    call_id: Optional[Union[int, str]] = Field(None, description="Otto call/appointment ID")
    job_id: Optional[str] = Field(None, description="Legacy: Shunya job ID for segmentation")
    
    part1: Optional[ShunyaSegmentationPart] = Field(None, description="Part 1: Rapport/Agenda (Introduction, agenda setting, discovery)")
    part2: Optional[ShunyaSegmentationPart] = Field(None, description="Part 2: Proposal/Close (Presentation, proposal, closing, next steps)")
    
    segmentation_confidence: Optional[float] = Field(None, description="Confidence in segmentation (0-1)")
    transition_point: Optional[Union[float, int]] = Field(None, description="Time offset in seconds where Part1 transitions to Part2")
    transition_indicators: Optional[List[str]] = Field(None, description="Indicators that signal the transition (e.g., 'Scheduling of appointment')")
    meeting_structure_score: Optional[Union[int, float]] = Field(None, description="Overall structure quality score (integer or float)")
    call_type: Optional[str] = Field(None, description="Type of call (e.g., 'sales_appointment')")
    
    created_at: Optional[Union[datetime, str]] = Field(None, description="When segmentation was created")
    
    # Legacy fields (for backward compatibility)
    part3: Optional[ShunyaSegmentationPart] = Field(None, description="Legacy: Future expansion")
    part4: Optional[ShunyaSegmentationPart] = Field(None, description="Legacy: Future expansion")
    outcome: Optional[str] = Field(None, description="Legacy: Overall outcome derived from segmentation")
    analyzed_at: Optional[datetime] = Field(None, description="Legacy: When segmentation was completed")


# ============================================================================
# Error Envelope Structures
# ============================================================================

class ShunyaErrorDetails(BaseModel):
    """Expected structure for error details from Shunya."""
    
    field: Optional[str] = Field(None, description="Field that caused error")
    reason: Optional[str] = Field(None, description="Reason for error")
    suggestion: Optional[str] = Field(None, description="Suggestion for resolution")


class ShunyaErrorEnvelope(BaseModel):
    """
    Expected structure for error responses from Shunya.
    
    Aligned with final Shunya canonical error envelope format:
    {
        "success": false,
        "error": {
            "error_code": "string",
            "error_type": "string",
            "message": "string",
            "retryable": true,
            "details": {},
            "timestamp": "2025-11-28T10:15:42.123Z",
            "request_id": "uuid"
        }
    }
    """
    
    success: Optional[bool] = Field(False, description="Success indicator (always false for errors)")
    error: Optional[Dict[str, Any]] = Field(None, description="Error object (nested structure)")
    
    # Error object fields (directly accessible for convenience)
    error_code: Optional[str] = Field(None, description="Machine-readable error code (e.g., TRANSCRIPTION_FAILED)")
    error_type: Optional[str] = Field(None, description="Error type category")
    message: Optional[str] = Field(None, description="Human-readable error message")
    retryable: Optional[bool] = Field(None, description="Whether error is retryable (affects retry logic)")
    details: Optional[Union[Dict[str, Any], List[ShunyaErrorDetails]]] = Field(None, description="Additional error details")
    timestamp: Optional[Union[datetime, str]] = Field(None, description="When error occurred (ISO 8601)")
    request_id: Optional[str] = Field(None, description="Request ID for tracing/correlation")
    
    # Legacy fields (for backward compatibility)
    code: Optional[str] = Field(None, description="Legacy: Error code (use error_code)")
    retry_after: Optional[int] = Field(None, description="Legacy: Seconds to wait before retry")


# ============================================================================
# Webhook Payload Structures
# ============================================================================

class ShunyaWebhookPayload(BaseModel):
    """
    Expected structure for Shunya webhook payloads.
    
    Used for job completion notifications.
    """
    
    shunya_job_id: Optional[str] = Field(None, description="Shunya job ID")
    job_id: Optional[str] = Field(None, description="Alias for shunya_job_id")
    task_id: Optional[str] = Field(None, description="Alias for shunya_job_id")
    
    status: Optional[str] = Field(None, description="Job status: completed, failed, processing")
    company_id: Optional[str] = Field(None, description="Company ID (required for tenant verification)")
    
    result: Optional[Union[ShunyaCSRCallAnalysis, ShunyaVisitAnalysis, ShunyaMeetingSegmentation, Dict[str, Any]]] = Field(
        None, description="Analysis result (type depends on job_type)"
    )
    error: Optional[Union[str, ShunyaErrorEnvelope, Dict[str, Any]]] = Field(
        None, description="Error information if status is failed"
    )
    
    timestamp: Optional[datetime] = Field(None, description="Webhook timestamp")
    created_at: Optional[datetime] = Field(None, description="Alias for timestamp")


# ============================================================================
# Helper Functions for Contract Validation
# ============================================================================

def validate_shunya_response(
    response: Dict[str, Any],
    expected_contract: type[BaseModel]
) -> BaseModel:
    """
    Validate a Shunya response against an expected contract.
    
    This is a graceful validator that:
    - Handles missing fields by setting them to None (all fields are Optional)
    - Handles type mismatches by attempting conversion
    - Handles None/empty response gracefully
    - Returns a valid model instance even with incomplete data
    
    Args:
        response: Raw response dictionary from Shunya (or None/empty dict)
        expected_contract: Pydantic model class (contract)
    
    Returns:
        Validated model instance (may have None fields)
    """
    if not response or not isinstance(response, dict):
        # Return empty instance if response is invalid
        return expected_contract()
    
    try:
        # Pydantic will automatically handle:
        # - Missing fields (they're all Optional, so will be None)
        # - Type conversions where possible
        # - Unknown fields (will be ignored if model doesn't define them)
        return expected_contract(**response)
    except Exception as e:
        # Log error but return empty contract to prevent breaking
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Failed to validate Shunya response against {expected_contract.__name__}: {e}",
            extra={"response_keys": list(response.keys()) if isinstance(response, dict) else None}
        )
        
        # Return empty instance (all fields will be None)
        return expected_contract()





These Pydantic models represent the expected shapes of Shunya API responses.
They are normalized, expected structures that will be populated once Shunya
confirms final schemas.

All fields are Optional to handle graceful degradation when Shunya sends
incomplete data. These models serve as contracts, not validation schemas.
"""
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# ============================================================================
# Enums (Expected from Shunya - to be confirmed)
# ============================================================================

class ShunyaCSROutcome(str, Enum):
    """
    Expected CSR call outcome values from Shunya.
    
    TODO: Replace with actual enum values once Shunya confirms.
    """
    QUALIFIED_AND_BOOKED = "qualified_and_booked"
    QUALIFIED_NOT_BOOKED = "qualified_not_booked"
    QUALIFIED_SERVICE_NOT_OFFERED = "qualified_service_not_offered"
    NOT_QUALIFIED = "not_qualified"
    # Placeholder for unknown values
    UNKNOWN = "unknown"


class ShunyaVisitOutcome(str, Enum):
    """
    Expected sales visit outcome values from Shunya.
    
    TODO: Replace with actual enum values once Shunya confirms.
    """
    WON = "won"
    LOST = "lost"
    PENDING_DECISION = "pending_decision"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"
    # Placeholder for unknown values
    UNKNOWN = "unknown"


class ShunyaObjectionLabel(str, Enum):
    """
    Expected objection label taxonomy from Shunya.
    
    TODO: Replace with complete taxonomy once Shunya confirms.
    """
    PRICE = "price"
    TIMING = "timing"
    TRUST = "trust"
    COMPETITOR = "competitor"
    NEED = "need"
    AUTHORITY = "authority"
    # Placeholder for unknown values
    UNKNOWN = "unknown"


class ShunyaSOPSStage(str, Enum):
    """
    Expected SOP stage identifiers from Shunya.
    
    TODO: Replace with actual SOP taxonomy once Shunya confirms.
    """
    GREETING = "greeting"
    QUALIFICATION = "qualification"
    PRESENTATION = "presentation"
    CLOSING = "closing"
    FOLLOW_UP = "follow_up"
    # Placeholder for unknown values
    UNKNOWN = "unknown"


# ============================================================================
# Objection Structures
# ============================================================================

class ShunyaObjection(BaseModel):
    """Expected structure for a single objection from Shunya."""
    
    objection_text: Optional[str] = Field(None, description="Full text of the objection")
    objection_label: Optional[str] = Field(None, description="Categorized label (price, timing, etc.)")
    severity: Optional[str] = Field(None, description="Severity: low, medium, high")
    overcome: Optional[bool] = Field(None, description="Whether objection was overcome")
    timestamp: Optional[datetime] = Field(None, description="When objection was raised")
    speaker_id: Optional[str] = Field(None, description="Speaker who raised objection")
    category_id: Optional[str] = Field(None, description="Internal category ID")
    category_text: Optional[str] = Field(None, description="Human-readable category")


class ShunyaObjectionsResponse(BaseModel):
    """Expected structure for objections response from Shunya."""
    
    objections: List[ShunyaObjection] = Field(default_factory=list, description="List of objections")
    total_objections: Optional[int] = Field(None, description="Total count of objections")
    severity_breakdown: Optional[Dict[str, int]] = Field(None, description="Count by severity")


# ============================================================================
# Qualification Structures
# ============================================================================

class ShunyaBANTScores(BaseModel):
    """Expected BANT scoring structure from Shunya."""
    
    budget: Optional[float] = Field(None, description="Budget score (0-1)")
    authority: Optional[float] = Field(None, description="Authority score (0-1)")
    need: Optional[float] = Field(None, description="Need score (0-1)")
    timeline: Optional[float] = Field(None, description="Timeline score (0-1)")


class ShunyaQualificationResponse(BaseModel):
    """Expected structure for qualification response from Shunya."""
    
    qualification_status: Optional[str] = Field(None, description="Overall qualification status")
    bant_scores: Optional[ShunyaBANTScores] = Field(None, description="BANT scoring breakdown")
    overall_score: Optional[float] = Field(None, description="Overall qualification score (0-1)")
    confidence_score: Optional[float] = Field(None, description="Confidence in qualification (0-1)")
    decision_makers: Optional[List[str]] = Field(None, description="Identified decision makers")
    urgency_signals: Optional[List[str]] = Field(None, description="Urgency indicators")
    budget_indicators: Optional[List[str]] = Field(None, description="Budget indicators")


# ============================================================================
# SOP Compliance Structures
# ============================================================================

class ShunyaSOPStage(BaseModel):
    """Expected structure for a single SOP stage."""
    
    stage_name: Optional[str] = Field(None, description="Name of SOP stage")
    completed: Optional[bool] = Field(None, description="Whether stage was completed")
    score: Optional[float] = Field(None, description="Score for this stage (0-1)")
    notes: Optional[str] = Field(None, description="Notes about stage execution")


class ShunyaComplianceResponse(BaseModel):
    """Expected structure for SOP compliance response from Shunya."""
    
    stages_followed: Optional[List[str]] = Field(None, description="List of stages that were followed")
    stages_missed: Optional[List[str]] = Field(None, description="List of stages that were missed")
    compliance_score: Optional[float] = Field(None, description="Overall compliance score (0-1)")
    stage_details: Optional[List[ShunyaSOPStage]] = Field(None, description="Detailed stage information")
    recommendations: Optional[List[str]] = Field(None, description="Recommendations for improvement")


# ============================================================================
# Pending Action Structures
# ============================================================================

class ShunyaPendingAction(BaseModel):
    """
    Expected structure for a pending action from Shunya.
    
    Aligned with final Shunya contract: Action types are free-string (e.g., "follow up tomorrow", "send technician").
    Shunya may later freeze these into enums, but we must be tolerant of arbitrary strings.
    """
    
    action: Optional[str] = Field(None, description="Action text/description (free-string)")
    action_type: Optional[str] = Field(None, description="Type of action - FREE STRING (e.g., 'follow up tomorrow', 'send technician', not enum)")
    priority: Optional[str] = Field(None, description="Priority: high, medium, low")
    due_at: Optional[Union[datetime, str]] = Field(None, description="When action is due")
    assignee_type: Optional[str] = Field(None, description="Who should complete (csr, rep, manager)")
    context: Optional[str] = Field(None, description="Additional context for action")
    
    # Note: action_type accepts any string value - adapters must map common patterns to internal enums
    # with graceful fallback to generic/custom type for unknown strings


# ============================================================================
# Missed Opportunity Structures
# ============================================================================

class ShunyaMissedOpportunity(BaseModel):
    """Expected structure for a missed opportunity from Shunya."""
    
    opportunity_text: Optional[str] = Field(None, description="Description of missed opportunity")
    opportunity_type: Optional[str] = Field(None, description="Type (upsell, cross_sell, etc.)")
    severity: Optional[str] = Field(None, description="Severity: low, medium, high")
    timestamp: Optional[datetime] = Field(None, description="When opportunity was identified")
    context: Optional[str] = Field(None, description="Context where opportunity occurred")


# ============================================================================
# Entity Extraction Structures
# ============================================================================

class ShunyaEntities(BaseModel):
    """Expected structure for extracted entities from Shunya."""
    
    address: Optional[str] = Field(None, description="Extracted address")
    phone_number: Optional[str] = Field(None, description="Extracted phone number")
    email: Optional[str] = Field(None, description="Extracted email")
    appointment_date: Optional[Union[datetime, str]] = Field(None, description="Extracted appointment date")
    scheduled_time: Optional[Union[datetime, str]] = Field(None, description="Extracted scheduled time")
    company_name: Optional[str] = Field(None, description="Extracted company name")
    person_name: Optional[str] = Field(None, description="Extracted person name")
    budget: Optional[float] = Field(None, description="Extracted budget amount")
    other: Optional[Dict[str, Any]] = Field(None, description="Other extracted entities")


# ============================================================================
# Summary Structures
# ============================================================================

class ShunyaSummaryResponse(BaseModel):
    """Expected structure for call/visit summary from Shunya."""
    
    summary: Optional[str] = Field(None, description="Full summary text")
    key_points: Optional[List[str]] = Field(None, description="Key points extracted")
    next_steps: Optional[List[str]] = Field(None, description="Recommended next steps")
    sentiment: Optional[str] = Field(None, description="Overall sentiment")
    confidence: Optional[float] = Field(None, description="Confidence in summary (0-1)")


# ============================================================================
# CSR Call Analysis (Complete Structure)
# ============================================================================

class ShunyaCSRCallAnalysis(BaseModel):
    """
    Expected complete structure for CSR call analysis from Shunya.
    
    This is the main contract for CSR call analysis responses.
    """
    
    job_id: Optional[str] = Field(None, description="Shunya job ID for this analysis")
    call_id: Optional[int] = Field(None, description="Otto call ID")
    
    qualification: Optional[ShunyaQualificationResponse] = Field(None, description="Lead qualification data")
    objections: Optional[ShunyaObjectionsResponse] = Field(None, description="Objections data")
    compliance: Optional[ShunyaComplianceResponse] = Field(None, description="SOP compliance data")
    summary: Optional[ShunyaSummaryResponse] = Field(None, description="Call summary")
    
    sentiment_score: Optional[float] = Field(None, description="Sentiment score (-1 to 1 or 0 to 1)")
    
    pending_actions: Optional[List[ShunyaPendingAction]] = Field(None, description="Pending actions identified")
    missed_opportunities: Optional[List[ShunyaMissedOpportunity]] = Field(None, description="Missed opportunities")
    
    entities: Optional[ShunyaEntities] = Field(None, description="Extracted entities")
    
    analyzed_at: Optional[datetime] = Field(None, description="When analysis was completed")
    confidence_score: Optional[float] = Field(None, description="Overall confidence in analysis (0-1)")


# ============================================================================
# Visit Analysis (Complete Structure)
# ============================================================================

class ShunyaVisitAnalysis(BaseModel):
    """
    Expected complete structure for sales visit analysis from Shunya.
    
    This is the main contract for visit analysis responses.
    """
    
    job_id: Optional[str] = Field(None, description="Shunya job ID for this analysis")
    appointment_id: Optional[str] = Field(None, description="Otto appointment ID")
    
    outcome: Optional[str] = Field(None, description="Visit outcome (won, lost, pending, etc.)")
    appointment_outcome: Optional[str] = Field(None, description="Alias for outcome")
    
    qualification: Optional[ShunyaQualificationResponse] = Field(None, description="Qualification data")
    objections: Optional[ShunyaObjectionsResponse] = Field(None, description="Objections raised")
    compliance: Optional[ShunyaComplianceResponse] = Field(None, description="SOP compliance")
    summary: Optional[ShunyaSummaryResponse] = Field(None, description="Visit summary")
    
    sentiment_score: Optional[float] = Field(None, description="Sentiment score")
    
    visit_actions: Optional[List[ShunyaPendingAction]] = Field(None, description="Actions from visit")
    pending_actions: Optional[List[ShunyaPendingAction]] = Field(None, description="Alias for visit_actions")
    missed_opportunities: Optional[List[ShunyaMissedOpportunity]] = Field(None, description="Missed opportunities")
    
    entities: Optional[ShunyaEntities] = Field(None, description="Extracted entities")
    
    deal_size: Optional[float] = Field(None, description="Deal size if outcome is won")
    deal_currency: Optional[str] = Field(None, description="Currency for deal size")
    
    analyzed_at: Optional[datetime] = Field(None, description="When analysis was completed")
    confidence_score: Optional[float] = Field(None, description="Overall confidence (0-1)")


# ============================================================================
# Meeting Segmentation Structures
# ============================================================================

class ShunyaSegmentationPart(BaseModel):
    """
    Expected structure for a single segmentation part (Part1 or Part2).
    
    Aligned with final Shunya contract.
    """
    
    start_time: Optional[Union[float, int]] = Field(None, description="Start time offset in seconds")
    end_time: Optional[Union[float, int]] = Field(None, description="End time offset in seconds")
    duration: Optional[Union[float, int]] = Field(None, description="Duration in seconds")
    content: Optional[str] = Field(None, description="Content/summary text for this part")
    key_points: Optional[List[str]] = Field(None, description="Key points discussed in this part")
    
    # Legacy fields (for backward compatibility during transition)
    transcript: Optional[str] = Field(None, description="Legacy: transcript for this part")
    summary: Optional[str] = Field(None, description="Legacy: summary of this part")
    sentiment_score: Optional[float] = Field(None, description="Legacy: sentiment score for this part")
    key_topics: Optional[List[str]] = Field(None, description="Legacy: key topics discussed")
    duration_seconds: Optional[int] = Field(None, description="Legacy: duration of this part")


class ShunyaMeetingSegmentation(BaseModel):
    """
    Expected structure for meeting segmentation response from Shunya.
    
    Aligned with final Shunya contract structure:
    {
        "success": true,
        "call_id": 3070,
        "part1": {...},
        "part2": {...},
        "segmentation_confidence": 0.8,
        "transition_point": 240,
        "transition_indicators": [...],
        "meeting_structure_score": 4,
        "call_type": "sales_appointment",
        "created_at": null
    }
    
    Segments sales visit into Part1 (rapport/agenda) and Part2 (proposal/close).
    """
    
    success: Optional[bool] = Field(True, description="Success indicator (true for valid segmentation)")
    call_id: Optional[Union[int, str]] = Field(None, description="Otto call/appointment ID")
    job_id: Optional[str] = Field(None, description="Legacy: Shunya job ID for segmentation")
    
    part1: Optional[ShunyaSegmentationPart] = Field(None, description="Part 1: Rapport/Agenda (Introduction, agenda setting, discovery)")
    part2: Optional[ShunyaSegmentationPart] = Field(None, description="Part 2: Proposal/Close (Presentation, proposal, closing, next steps)")
    
    segmentation_confidence: Optional[float] = Field(None, description="Confidence in segmentation (0-1)")
    transition_point: Optional[Union[float, int]] = Field(None, description="Time offset in seconds where Part1 transitions to Part2")
    transition_indicators: Optional[List[str]] = Field(None, description="Indicators that signal the transition (e.g., 'Scheduling of appointment')")
    meeting_structure_score: Optional[Union[int, float]] = Field(None, description="Overall structure quality score (integer or float)")
    call_type: Optional[str] = Field(None, description="Type of call (e.g., 'sales_appointment')")
    
    created_at: Optional[Union[datetime, str]] = Field(None, description="When segmentation was created")
    
    # Legacy fields (for backward compatibility)
    part3: Optional[ShunyaSegmentationPart] = Field(None, description="Legacy: Future expansion")
    part4: Optional[ShunyaSegmentationPart] = Field(None, description="Legacy: Future expansion")
    outcome: Optional[str] = Field(None, description="Legacy: Overall outcome derived from segmentation")
    analyzed_at: Optional[datetime] = Field(None, description="Legacy: When segmentation was completed")


# ============================================================================
# Error Envelope Structures
# ============================================================================

class ShunyaErrorDetails(BaseModel):
    """Expected structure for error details from Shunya."""
    
    field: Optional[str] = Field(None, description="Field that caused error")
    reason: Optional[str] = Field(None, description="Reason for error")
    suggestion: Optional[str] = Field(None, description="Suggestion for resolution")


class ShunyaErrorEnvelope(BaseModel):
    """
    Expected structure for error responses from Shunya.
    
    Aligned with final Shunya canonical error envelope format:
    {
        "success": false,
        "error": {
            "error_code": "string",
            "error_type": "string",
            "message": "string",
            "retryable": true,
            "details": {},
            "timestamp": "2025-11-28T10:15:42.123Z",
            "request_id": "uuid"
        }
    }
    """
    
    success: Optional[bool] = Field(False, description="Success indicator (always false for errors)")
    error: Optional[Dict[str, Any]] = Field(None, description="Error object (nested structure)")
    
    # Error object fields (directly accessible for convenience)
    error_code: Optional[str] = Field(None, description="Machine-readable error code (e.g., TRANSCRIPTION_FAILED)")
    error_type: Optional[str] = Field(None, description="Error type category")
    message: Optional[str] = Field(None, description="Human-readable error message")
    retryable: Optional[bool] = Field(None, description="Whether error is retryable (affects retry logic)")
    details: Optional[Union[Dict[str, Any], List[ShunyaErrorDetails]]] = Field(None, description="Additional error details")
    timestamp: Optional[Union[datetime, str]] = Field(None, description="When error occurred (ISO 8601)")
    request_id: Optional[str] = Field(None, description="Request ID for tracing/correlation")
    
    # Legacy fields (for backward compatibility)
    code: Optional[str] = Field(None, description="Legacy: Error code (use error_code)")
    retry_after: Optional[int] = Field(None, description="Legacy: Seconds to wait before retry")


# ============================================================================
# Webhook Payload Structures
# ============================================================================

class ShunyaWebhookPayload(BaseModel):
    """
    Expected structure for Shunya webhook payloads.
    
    Used for job completion notifications.
    """
    
    shunya_job_id: Optional[str] = Field(None, description="Shunya job ID")
    job_id: Optional[str] = Field(None, description="Alias for shunya_job_id")
    task_id: Optional[str] = Field(None, description="Alias for shunya_job_id")
    
    status: Optional[str] = Field(None, description="Job status: completed, failed, processing")
    company_id: Optional[str] = Field(None, description="Company ID (required for tenant verification)")
    
    result: Optional[Union[ShunyaCSRCallAnalysis, ShunyaVisitAnalysis, ShunyaMeetingSegmentation, Dict[str, Any]]] = Field(
        None, description="Analysis result (type depends on job_type)"
    )
    error: Optional[Union[str, ShunyaErrorEnvelope, Dict[str, Any]]] = Field(
        None, description="Error information if status is failed"
    )
    
    timestamp: Optional[datetime] = Field(None, description="Webhook timestamp")
    created_at: Optional[datetime] = Field(None, description="Alias for timestamp")


# ============================================================================
# Helper Functions for Contract Validation
# ============================================================================

def validate_shunya_response(
    response: Dict[str, Any],
    expected_contract: type[BaseModel]
) -> BaseModel:
    """
    Validate a Shunya response against an expected contract.
    
    This is a graceful validator that:
    - Handles missing fields by setting them to None (all fields are Optional)
    - Handles type mismatches by attempting conversion
    - Handles None/empty response gracefully
    - Returns a valid model instance even with incomplete data
    
    Args:
        response: Raw response dictionary from Shunya (or None/empty dict)
        expected_contract: Pydantic model class (contract)
    
    Returns:
        Validated model instance (may have None fields)
    """
    if not response or not isinstance(response, dict):
        # Return empty instance if response is invalid
        return expected_contract()
    
    try:
        # Pydantic will automatically handle:
        # - Missing fields (they're all Optional, so will be None)
        # - Type conversions where possible
        # - Unknown fields (will be ignored if model doesn't define them)
        return expected_contract(**response)
    except Exception as e:
        # Log error but return empty contract to prevent breaking
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Failed to validate Shunya response against {expected_contract.__name__}: {e}",
            extra={"response_keys": list(response.keys()) if isinstance(response, dict) else None}
        )
        
        # Return empty instance (all fields will be None)
        return expected_contract()



