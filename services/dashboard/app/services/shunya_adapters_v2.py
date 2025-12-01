"""
Enhanced adapter layer for Shunya API responses.

This module provides adapters that translate Shunya's API responses into Otto's
internal format using contract stubs and mapping tables.

Architecture:
- Contracts (shunya_contracts.py): Define expected Shunya response shapes
- Mappings (shunya_mappings.py): Translate Shunya values → Otto enums
- Adapters (this file): Orchestrate validation, mapping, and transformation

All adapters are:
- Idempotent: Same input → same output always
- Graceful: Handle missing/unknown fields without breaking
- Evolvable: Easy to update when Shunya confirms schemas
- Tenant-agnostic: Multi-tenancy handled at integration layer, not adapters
"""
from typing import Optional, Dict, Any, List
from app.core.pii_masking import PIISafeLogger
from app.schemas.shunya_contracts import (
    ShunyaCSRCallAnalysis,
    ShunyaVisitAnalysis,
    ShunyaMeetingSegmentation,
    ShunyaWebhookPayload,
    ShunyaErrorEnvelope,
    validate_shunya_response,
)
from app.services.shunya_mappings import (
    map_shunya_csr_outcome_to_lead_status,
    map_shunya_visit_outcome_to_appointment_outcome,
    map_visit_outcome_to_appointment_status,
    map_visit_outcome_to_lead_status,
    normalize_shunya_objection_label,
    map_shunya_action_to_task_assignee,
    map_shunya_opportunity_to_signal_type,
    map_shunya_opportunity_severity_to_signal_severity,
    normalize_shunya_sop_stage,
)

logger = PIISafeLogger(__name__)


class ShunyaCSRCallAdapter:
    """
    Adapter for CSR call analysis responses.
    
    Transforms ShunyaCSRCallAnalysis contract → Otto domain models.
    """
    
    @classmethod
    def adapt(cls, raw_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt Shunya CSR call analysis response to Otto format.
        
        Args:
            raw_response: Raw response dictionary from Shunya
        
        Returns:
            Normalized dictionary ready for Otto domain model persistence
        """
        # Validate against contract (graceful - handles missing fields)
        contract = validate_shunya_response(raw_response, ShunyaCSRCallAnalysis)
        
        # Extract and map values
        normalized = {
            "job_id": contract.job_id,
            
            # Qualification → Lead Status
            "qualification": cls._adapt_qualification(contract.qualification) if contract.qualification else {},
            "lead_status": cls._adapt_qualification_to_lead_status(contract.qualification),
            
            # Objections
            "objections": cls._adapt_objections(contract.objections) if contract.objections else {},
            
            # SOP Compliance
            "compliance": cls._adapt_compliance(contract.compliance) if contract.compliance else {},
            
            # Summary
            "summary": cls._adapt_summary(contract.summary) if contract.summary else {},
            
            # Sentiment
            "sentiment_score": contract.sentiment_score,
            
            # Pending Actions
            "pending_actions": cls._adapt_pending_actions(contract.pending_actions or [], context="csr_call"),
            
            # Missed Opportunities
            "missed_opportunities": cls._adapt_missed_opportunities(contract.missed_opportunities or []),
            
            # Entities
            "entities": cls._adapt_entities(contract.entities) if contract.entities else {},
            
            # Metadata
            "analyzed_at": contract.analyzed_at,
            "confidence_score": contract.confidence_score,
        }
        
        return normalized
    
    @classmethod
    def _adapt_qualification(cls, qualification: Any) -> Dict[str, Any]:
        """Adapt qualification response."""
        if not qualification:
            return {}
        
        return {
            "qualification_status": qualification.qualification_status,
            "bant_scores": qualification.bant_scores.dict() if qualification.bant_scores else {},
            "overall_score": qualification.overall_score,
            "confidence_score": qualification.confidence_score,
            "decision_makers": qualification.decision_makers or [],
            "urgency_signals": qualification.urgency_signals or [],
            "budget_indicators": qualification.budget_indicators or [],
        }
    
    @classmethod
    def _adapt_qualification_to_lead_status(cls, qualification: Any) -> Optional[str]:
        """Map qualification status to LeadStatus."""
        if not qualification or not qualification.qualification_status:
            return None
        
        lead_status = map_shunya_csr_outcome_to_lead_status(qualification.qualification_status)
        return lead_status.value if lead_status else None
    
    @classmethod
    def _adapt_objections(cls, objections: Any) -> Dict[str, Any]:
        """Adapt objections response."""
        if not objections:
            return {"objections": [], "total_objections": 0}
        
        adapted_objections = []
        for obj in (objections.objections or []):
            adapted_objections.append({
                "objection_text": obj.objection_text,
                "objection_label": normalize_shunya_objection_label(obj.objection_label),
                "severity": obj.severity,
                "overcome": obj.overcome or False,
                "timestamp": obj.timestamp,
                "speaker_id": obj.speaker_id,
            })
        
        return {
            "objections": adapted_objections,
            "total_objections": objections.total_objections or len(adapted_objections),
            "severity_breakdown": objections.severity_breakdown or {},
        }
    
    @classmethod
    def _adapt_compliance(cls, compliance: Any) -> Dict[str, Any]:
        """Adapt SOP compliance response."""
        if not compliance:
            return {"stages_followed": [], "stages_missed": [], "compliance_score": None}
        
        # Normalize SOP stage names
        stages_followed = [
            normalize_shunya_sop_stage(stage) for stage in (compliance.stages_followed or [])
            if normalize_shunya_sop_stage(stage)
        ]
        stages_missed = [
            normalize_shunya_sop_stage(stage) for stage in (compliance.stages_missed or [])
            if normalize_shunya_sop_stage(stage)
        ]
        
        return {
            "stages_followed": stages_followed,
            "stages_missed": stages_missed,
            "compliance_score": compliance.compliance_score,
            "stage_details": [
                {
                    "stage_name": normalize_shunya_sop_stage(stage.stage_name) if hasattr(stage, 'stage_name') else None,
                    "completed": stage.completed if hasattr(stage, 'completed') else None,
                    "score": stage.score if hasattr(stage, 'score') else None,
                }
                for stage in (compliance.stage_details or [])
            ] if hasattr(compliance, 'stage_details') else [],
        }
    
    @classmethod
    def _adapt_summary(cls, summary: Any) -> Dict[str, Any]:
        """Adapt summary response."""
        if not summary:
            return {"summary": "", "key_points": [], "next_steps": []}
        
        return {
            "summary": summary.summary or "",
            "key_points": summary.key_points or [],
            "next_steps": summary.next_steps or [],
            "sentiment": summary.sentiment,
            "confidence": summary.confidence,
        }
    
    @classmethod
    def _adapt_pending_actions(cls, actions: List[Any], context: str = "csr_call") -> List[Dict[str, Any]]:
        """
        Adapt pending actions to Otto task format.
        
        Handles free-string action types from Shunya (e.g., "follow up tomorrow", "send technician").
        Maps common patterns to internal enums with graceful fallback to generic/custom type.
        """
        adapted = []
        for action in actions:
            # Get action type (free-string from Shunya)
            action_type_str = action.action_type or action.action or ""
            
            # Try to map common patterns to known types, fallback to generic
            mapped_assignee = map_shunya_action_to_task_assignee(action_type_str, context)
            
            adapted.append({
                "action": action.action or action_type_str or "",
                "action_type": action_type_str,  # Preserve original free-string
                "mapped_assignee": mapped_assignee.value,  # Internal mapping result
                "priority": action.priority,
                "due_at": action.due_at,
                "assignee_type": map_shunya_action_to_task_assignee(action.assignee_type, context).value if action.assignee_type else mapped_assignee.value,
                "context": action.context,
                # Flag to indicate if this is a known pattern or free-string
                "is_known_pattern": action_type_str.lower() in [
                    "follow_up", "follow up", "send_info", "send technician", "call_back",
                    "technician_visit", "technician visit", "follow_up_call", "follow up call"
                ],
            })
        return adapted
    
    @classmethod
    def _adapt_missed_opportunities(cls, opportunities: List[Any]) -> List[Dict[str, Any]]:
        """Adapt missed opportunities to Otto signal format."""
        adapted = []
        for opp in opportunities:
            adapted.append({
                "opportunity_text": opp.opportunity_text or "",
                "opportunity_type": opp.opportunity_type,
                "severity": map_shunya_opportunity_severity_to_signal_severity(opp.severity).value,
                "signal_type": map_shunya_opportunity_to_signal_type(opp.opportunity_type).value,
                "timestamp": opp.timestamp,
                "context": opp.context,
            })
        return adapted
    
    @classmethod
    def _adapt_entities(cls, entities: Any) -> Dict[str, Any]:
        """Adapt extracted entities."""
        if not entities:
            return {}
        
        return {
            "address": entities.address,
            "phone_number": entities.phone_number,
            "email": entities.email,
            "appointment_date": entities.appointment_date,
            "scheduled_time": entities.scheduled_time,
            "company_name": entities.company_name,
            "person_name": entities.person_name,
            "budget": entities.budget,
            "other": entities.other or {},
        }


class ShunyaVisitAdapter:
    """
    Adapter for sales visit analysis responses.
    
    Transforms ShunyaVisitAnalysis contract → Otto domain models.
    """
    
    @classmethod
    def adapt(cls, raw_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt Shunya visit analysis response to Otto format.
        
        Args:
            raw_response: Raw response dictionary from Shunya
        
        Returns:
            Normalized dictionary ready for Otto domain model persistence
        """
        # Validate against contract
        contract = validate_shunya_response(raw_response, ShunyaVisitAnalysis)
        
        # Determine outcome
        outcome_str = contract.outcome or contract.appointment_outcome or "pending"
        appointment_outcome = map_shunya_visit_outcome_to_appointment_outcome(outcome_str)
        appointment_status = map_visit_outcome_to_appointment_status(appointment_outcome) if appointment_outcome else None
        lead_status = map_visit_outcome_to_lead_status(appointment_outcome) if appointment_outcome else None
        
        # Extract and map values
        normalized = {
            "job_id": contract.job_id,
            
            # Outcome mapping
            "outcome": outcome_str,
            "appointment_outcome": appointment_outcome.value if appointment_outcome else None,
            "appointment_status": appointment_status.value if appointment_status else None,
            "lead_status": lead_status.value if lead_status else None,
            
            # Deal information
            "deal_size": contract.deal_size,
            "deal_currency": contract.deal_currency,
            
            # Analysis data (reuse CSR adapter methods)
            "qualification": ShunyaCSRCallAdapter._adapt_qualification(contract.qualification) if contract.qualification else {},
            "objections": ShunyaCSRCallAdapter._adapt_objections(contract.objections) if contract.objections else {},
            "compliance": ShunyaCSRCallAdapter._adapt_compliance(contract.compliance) if contract.compliance else {},
            "summary": ShunyaCSRCallAdapter._adapt_summary(contract.summary) if contract.summary else {},
            
            # Sentiment
            "sentiment_score": contract.sentiment_score,
            
            # Visit-specific actions
            "visit_actions": ShunyaCSRCallAdapter._adapt_pending_actions(
                contract.visit_actions or contract.pending_actions or [],
                context="visit"
            ),
            "missed_opportunities": ShunyaCSRCallAdapter._adapt_missed_opportunities(
                contract.missed_opportunities or []
            ),
            
            # Entities
            "entities": ShunyaCSRCallAdapter._adapt_entities(contract.entities) if contract.entities else {},
            
            # Metadata
            "analyzed_at": contract.analyzed_at,
            "confidence_score": contract.confidence_score,
        }
        
        return normalized


class ShunyaSegmentationAdapter:
    """
    Adapter for meeting segmentation responses.
    
    Transforms ShunyaMeetingSegmentation contract → Otto format.
    """
    
    @classmethod
    def adapt(cls, raw_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt Shunya segmentation response to Otto format.
        
        Args:
            raw_response: Raw response dictionary from Shunya
        
        Returns:
            Normalized dictionary ready for Otto domain model persistence
        """
        # Validate against contract
        contract = validate_shunya_response(raw_response, ShunyaMeetingSegmentation)
        
        # Adapt segmentation parts
        normalized = {
            "success": contract.success,
            "call_id": contract.call_id or contract.job_id,  # Fallback to job_id if call_id not present
            "job_id": contract.job_id,
            "part1": cls._adapt_segmentation_part(contract.part1) if contract.part1 else {},
            "part2": cls._adapt_segmentation_part(contract.part2) if contract.part2 else {},
            "transition_point": contract.transition_point,
            "transition_indicators": contract.transition_indicators or [],
            "segmentation_confidence": contract.segmentation_confidence,
            "meeting_structure_score": contract.meeting_structure_score,
            "call_type": contract.call_type,
            "created_at": contract.created_at or contract.analyzed_at,
            # Legacy fields (for backward compatibility)
            "outcome": contract.outcome,
            "analyzed_at": contract.analyzed_at or contract.created_at,
        }
        
        # Handle future parts if present (legacy support)
        if contract.part3:
            normalized["part3"] = cls._adapt_segmentation_part(contract.part3)
        if contract.part4:
            normalized["part4"] = cls._adapt_segmentation_part(contract.part4)
        
        return normalized
    
    @classmethod
    def _adapt_segmentation_part(cls, part: Any) -> Dict[str, Any]:
        """
        Adapt a single segmentation part.
        
        Aligned with final Shunya contract structure:
        {
            "start_time": 0,
            "end_time": 240,
            "duration": 240,
            "content": "Introduction, agenda setting, discovery, rapport building",
            "key_points": ["Introduction", "Agenda setting", "Discovery questions"]
        }
        """
        if not part:
            return {}
        
        # Handle both new structure (content, key_points) and legacy (summary, transcript)
        content = getattr(part, "content", None) or getattr(part, "summary", None) or getattr(part, "transcript", None) or ""
        key_points = getattr(part, "key_points", None) or getattr(part, "key_topics", None) or []
        
        return {
            "start_time": getattr(part, "start_time", None),
            "end_time": getattr(part, "end_time", None),
            "duration": getattr(part, "duration", None) or getattr(part, "duration_seconds", None),
            "content": content,
            "key_points": key_points,
            # Legacy fields (for backward compatibility)
            "transcript": getattr(part, "transcript", None) or content,
            "summary": getattr(part, "summary", None) or content,
            "sentiment_score": getattr(part, "sentiment_score", None),
            "key_topics": key_points,
            "duration_seconds": getattr(part, "duration_seconds", None) or getattr(part, "duration", None),
        }


class ShunyaWebhookAdapter:
    """
    Adapter for webhook payloads.
    
    Validates and extracts webhook payload structure.
    """
    
    @classmethod
    def adapt(cls, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt Shunya webhook payload to Otto format.
        
        Args:
            raw_payload: Raw webhook payload from Shunya
        
        Returns:
            Normalized payload dictionary
        """
        # Validate against contract
        contract = validate_shunya_response(raw_payload, ShunyaWebhookPayload)
        
        # Extract job ID (handle aliases)
        shunya_job_id = contract.shunya_job_id or contract.job_id or contract.task_id
        
        normalized = {
            "shunya_job_id": shunya_job_id,
            "status": (contract.status or "").lower(),
            "company_id": contract.company_id,
            "result": contract.result.dict() if hasattr(contract.result, 'dict') else contract.result,
            "error": contract.error.dict() if hasattr(contract.error, 'dict') and isinstance(contract.error, ShunyaErrorEnvelope) else contract.error,
            "timestamp": contract.timestamp or contract.created_at,
        }
        
        return normalized


class ShunyaErrorAdapter:
    """
    Adapter for error responses.
    
    Parses and normalizes Shunya error envelopes.
    """
    
    @classmethod
    def adapt(cls, raw_error: Any) -> Dict[str, Any]:
        """
        Adapt Shunya error response to Otto format.
        
        Args:
            raw_error: Raw error response (dict, string, or error envelope)
        
        Returns:
            Normalized error dictionary
        """
        # Handle string errors
        if isinstance(raw_error, str):
            return {
                "code": "UNKNOWN_ERROR",
                "message": raw_error,
                "details": {},
                "retryable": False,
            }
        
        # Validate against contract if dict
        if isinstance(raw_error, dict):
            contract = validate_shunya_response(raw_error, ShunyaErrorEnvelope)
            return {
                "code": contract.code or "UNKNOWN_ERROR",
                "message": contract.message or str(raw_error),
                "details": contract.details or {},
                "retryable": contract.retryable or False,
                "retry_after": contract.retry_after,
                "request_id": contract.request_id,
                "timestamp": contract.timestamp,
            }
        
        # Fallback
        return {
            "code": "UNKNOWN_ERROR",
            "message": str(raw_error),
            "details": {},
            "retryable": False,
        }


# ============================================================================
# Global adapter instances
# ============================================================================

csr_call_adapter = ShunyaCSRCallAdapter()
visit_adapter = ShunyaVisitAdapter()
segmentation_adapter = ShunyaSegmentationAdapter()
webhook_adapter = ShunyaWebhookAdapter()
error_adapter = ShunyaErrorAdapter()



This module provides adapters that translate Shunya's API responses into Otto's
internal format using contract stubs and mapping tables.

Architecture:
- Contracts (shunya_contracts.py): Define expected Shunya response shapes
- Mappings (shunya_mappings.py): Translate Shunya values → Otto enums
- Adapters (this file): Orchestrate validation, mapping, and transformation

All adapters are:
- Idempotent: Same input → same output always
- Graceful: Handle missing/unknown fields without breaking
- Evolvable: Easy to update when Shunya confirms schemas
- Tenant-agnostic: Multi-tenancy handled at integration layer, not adapters
"""
from typing import Optional, Dict, Any, List
from app.core.pii_masking import PIISafeLogger
from app.schemas.shunya_contracts import (
    ShunyaCSRCallAnalysis,
    ShunyaVisitAnalysis,
    ShunyaMeetingSegmentation,
    ShunyaWebhookPayload,
    ShunyaErrorEnvelope,
    validate_shunya_response,
)
from app.services.shunya_mappings import (
    map_shunya_csr_outcome_to_lead_status,
    map_shunya_visit_outcome_to_appointment_outcome,
    map_visit_outcome_to_appointment_status,
    map_visit_outcome_to_lead_status,
    normalize_shunya_objection_label,
    map_shunya_action_to_task_assignee,
    map_shunya_opportunity_to_signal_type,
    map_shunya_opportunity_severity_to_signal_severity,
    normalize_shunya_sop_stage,
)

logger = PIISafeLogger(__name__)


class ShunyaCSRCallAdapter:
    """
    Adapter for CSR call analysis responses.
    
    Transforms ShunyaCSRCallAnalysis contract → Otto domain models.
    """
    
    @classmethod
    def adapt(cls, raw_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt Shunya CSR call analysis response to Otto format.
        
        Args:
            raw_response: Raw response dictionary from Shunya
        
        Returns:
            Normalized dictionary ready for Otto domain model persistence
        """
        # Validate against contract (graceful - handles missing fields)
        contract = validate_shunya_response(raw_response, ShunyaCSRCallAnalysis)
        
        # Extract and map values
        normalized = {
            "job_id": contract.job_id,
            
            # Qualification → Lead Status
            "qualification": cls._adapt_qualification(contract.qualification) if contract.qualification else {},
            "lead_status": cls._adapt_qualification_to_lead_status(contract.qualification),
            
            # Objections
            "objections": cls._adapt_objections(contract.objections) if contract.objections else {},
            
            # SOP Compliance
            "compliance": cls._adapt_compliance(contract.compliance) if contract.compliance else {},
            
            # Summary
            "summary": cls._adapt_summary(contract.summary) if contract.summary else {},
            
            # Sentiment
            "sentiment_score": contract.sentiment_score,
            
            # Pending Actions
            "pending_actions": cls._adapt_pending_actions(contract.pending_actions or [], context="csr_call"),
            
            # Missed Opportunities
            "missed_opportunities": cls._adapt_missed_opportunities(contract.missed_opportunities or []),
            
            # Entities
            "entities": cls._adapt_entities(contract.entities) if contract.entities else {},
            
            # Metadata
            "analyzed_at": contract.analyzed_at,
            "confidence_score": contract.confidence_score,
        }
        
        return normalized
    
    @classmethod
    def _adapt_qualification(cls, qualification: Any) -> Dict[str, Any]:
        """Adapt qualification response."""
        if not qualification:
            return {}
        
        return {
            "qualification_status": qualification.qualification_status,
            "bant_scores": qualification.bant_scores.dict() if qualification.bant_scores else {},
            "overall_score": qualification.overall_score,
            "confidence_score": qualification.confidence_score,
            "decision_makers": qualification.decision_makers or [],
            "urgency_signals": qualification.urgency_signals or [],
            "budget_indicators": qualification.budget_indicators or [],
        }
    
    @classmethod
    def _adapt_qualification_to_lead_status(cls, qualification: Any) -> Optional[str]:
        """Map qualification status to LeadStatus."""
        if not qualification or not qualification.qualification_status:
            return None
        
        lead_status = map_shunya_csr_outcome_to_lead_status(qualification.qualification_status)
        return lead_status.value if lead_status else None
    
    @classmethod
    def _adapt_objections(cls, objections: Any) -> Dict[str, Any]:
        """Adapt objections response."""
        if not objections:
            return {"objections": [], "total_objections": 0}
        
        adapted_objections = []
        for obj in (objections.objections or []):
            adapted_objections.append({
                "objection_text": obj.objection_text,
                "objection_label": normalize_shunya_objection_label(obj.objection_label),
                "severity": obj.severity,
                "overcome": obj.overcome or False,
                "timestamp": obj.timestamp,
                "speaker_id": obj.speaker_id,
            })
        
        return {
            "objections": adapted_objections,
            "total_objections": objections.total_objections or len(adapted_objections),
            "severity_breakdown": objections.severity_breakdown or {},
        }
    
    @classmethod
    def _adapt_compliance(cls, compliance: Any) -> Dict[str, Any]:
        """Adapt SOP compliance response."""
        if not compliance:
            return {"stages_followed": [], "stages_missed": [], "compliance_score": None}
        
        # Normalize SOP stage names
        stages_followed = [
            normalize_shunya_sop_stage(stage) for stage in (compliance.stages_followed or [])
            if normalize_shunya_sop_stage(stage)
        ]
        stages_missed = [
            normalize_shunya_sop_stage(stage) for stage in (compliance.stages_missed or [])
            if normalize_shunya_sop_stage(stage)
        ]
        
        return {
            "stages_followed": stages_followed,
            "stages_missed": stages_missed,
            "compliance_score": compliance.compliance_score,
            "stage_details": [
                {
                    "stage_name": normalize_shunya_sop_stage(stage.stage_name) if hasattr(stage, 'stage_name') else None,
                    "completed": stage.completed if hasattr(stage, 'completed') else None,
                    "score": stage.score if hasattr(stage, 'score') else None,
                }
                for stage in (compliance.stage_details or [])
            ] if hasattr(compliance, 'stage_details') else [],
        }
    
    @classmethod
    def _adapt_summary(cls, summary: Any) -> Dict[str, Any]:
        """Adapt summary response."""
        if not summary:
            return {"summary": "", "key_points": [], "next_steps": []}
        
        return {
            "summary": summary.summary or "",
            "key_points": summary.key_points or [],
            "next_steps": summary.next_steps or [],
            "sentiment": summary.sentiment,
            "confidence": summary.confidence,
        }
    
    @classmethod
    def _adapt_pending_actions(cls, actions: List[Any], context: str = "csr_call") -> List[Dict[str, Any]]:
        """
        Adapt pending actions to Otto task format.
        
        Handles free-string action types from Shunya (e.g., "follow up tomorrow", "send technician").
        Maps common patterns to internal enums with graceful fallback to generic/custom type.
        """
        adapted = []
        for action in actions:
            # Get action type (free-string from Shunya)
            action_type_str = action.action_type or action.action or ""
            
            # Try to map common patterns to known types, fallback to generic
            mapped_assignee = map_shunya_action_to_task_assignee(action_type_str, context)
            
            adapted.append({
                "action": action.action or action_type_str or "",
                "action_type": action_type_str,  # Preserve original free-string
                "mapped_assignee": mapped_assignee.value,  # Internal mapping result
                "priority": action.priority,
                "due_at": action.due_at,
                "assignee_type": map_shunya_action_to_task_assignee(action.assignee_type, context).value if action.assignee_type else mapped_assignee.value,
                "context": action.context,
                # Flag to indicate if this is a known pattern or free-string
                "is_known_pattern": action_type_str.lower() in [
                    "follow_up", "follow up", "send_info", "send technician", "call_back",
                    "technician_visit", "technician visit", "follow_up_call", "follow up call"
                ],
            })
        return adapted
    
    @classmethod
    def _adapt_missed_opportunities(cls, opportunities: List[Any]) -> List[Dict[str, Any]]:
        """Adapt missed opportunities to Otto signal format."""
        adapted = []
        for opp in opportunities:
            adapted.append({
                "opportunity_text": opp.opportunity_text or "",
                "opportunity_type": opp.opportunity_type,
                "severity": map_shunya_opportunity_severity_to_signal_severity(opp.severity).value,
                "signal_type": map_shunya_opportunity_to_signal_type(opp.opportunity_type).value,
                "timestamp": opp.timestamp,
                "context": opp.context,
            })
        return adapted
    
    @classmethod
    def _adapt_entities(cls, entities: Any) -> Dict[str, Any]:
        """Adapt extracted entities."""
        if not entities:
            return {}
        
        return {
            "address": entities.address,
            "phone_number": entities.phone_number,
            "email": entities.email,
            "appointment_date": entities.appointment_date,
            "scheduled_time": entities.scheduled_time,
            "company_name": entities.company_name,
            "person_name": entities.person_name,
            "budget": entities.budget,
            "other": entities.other or {},
        }


class ShunyaVisitAdapter:
    """
    Adapter for sales visit analysis responses.
    
    Transforms ShunyaVisitAnalysis contract → Otto domain models.
    """
    
    @classmethod
    def adapt(cls, raw_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt Shunya visit analysis response to Otto format.
        
        Args:
            raw_response: Raw response dictionary from Shunya
        
        Returns:
            Normalized dictionary ready for Otto domain model persistence
        """
        # Validate against contract
        contract = validate_shunya_response(raw_response, ShunyaVisitAnalysis)
        
        # Determine outcome
        outcome_str = contract.outcome or contract.appointment_outcome or "pending"
        appointment_outcome = map_shunya_visit_outcome_to_appointment_outcome(outcome_str)
        appointment_status = map_visit_outcome_to_appointment_status(appointment_outcome) if appointment_outcome else None
        lead_status = map_visit_outcome_to_lead_status(appointment_outcome) if appointment_outcome else None
        
        # Extract and map values
        normalized = {
            "job_id": contract.job_id,
            
            # Outcome mapping
            "outcome": outcome_str,
            "appointment_outcome": appointment_outcome.value if appointment_outcome else None,
            "appointment_status": appointment_status.value if appointment_status else None,
            "lead_status": lead_status.value if lead_status else None,
            
            # Deal information
            "deal_size": contract.deal_size,
            "deal_currency": contract.deal_currency,
            
            # Analysis data (reuse CSR adapter methods)
            "qualification": ShunyaCSRCallAdapter._adapt_qualification(contract.qualification) if contract.qualification else {},
            "objections": ShunyaCSRCallAdapter._adapt_objections(contract.objections) if contract.objections else {},
            "compliance": ShunyaCSRCallAdapter._adapt_compliance(contract.compliance) if contract.compliance else {},
            "summary": ShunyaCSRCallAdapter._adapt_summary(contract.summary) if contract.summary else {},
            
            # Sentiment
            "sentiment_score": contract.sentiment_score,
            
            # Visit-specific actions
            "visit_actions": ShunyaCSRCallAdapter._adapt_pending_actions(
                contract.visit_actions or contract.pending_actions or [],
                context="visit"
            ),
            "missed_opportunities": ShunyaCSRCallAdapter._adapt_missed_opportunities(
                contract.missed_opportunities or []
            ),
            
            # Entities
            "entities": ShunyaCSRCallAdapter._adapt_entities(contract.entities) if contract.entities else {},
            
            # Metadata
            "analyzed_at": contract.analyzed_at,
            "confidence_score": contract.confidence_score,
        }
        
        return normalized


class ShunyaSegmentationAdapter:
    """
    Adapter for meeting segmentation responses.
    
    Transforms ShunyaMeetingSegmentation contract → Otto format.
    """
    
    @classmethod
    def adapt(cls, raw_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt Shunya segmentation response to Otto format.
        
        Args:
            raw_response: Raw response dictionary from Shunya
        
        Returns:
            Normalized dictionary ready for Otto domain model persistence
        """
        # Validate against contract
        contract = validate_shunya_response(raw_response, ShunyaMeetingSegmentation)
        
        # Adapt segmentation parts
        normalized = {
            "success": contract.success,
            "call_id": contract.call_id or contract.job_id,  # Fallback to job_id if call_id not present
            "job_id": contract.job_id,
            "part1": cls._adapt_segmentation_part(contract.part1) if contract.part1 else {},
            "part2": cls._adapt_segmentation_part(contract.part2) if contract.part2 else {},
            "transition_point": contract.transition_point,
            "transition_indicators": contract.transition_indicators or [],
            "segmentation_confidence": contract.segmentation_confidence,
            "meeting_structure_score": contract.meeting_structure_score,
            "call_type": contract.call_type,
            "created_at": contract.created_at or contract.analyzed_at,
            # Legacy fields (for backward compatibility)
            "outcome": contract.outcome,
            "analyzed_at": contract.analyzed_at or contract.created_at,
        }
        
        # Handle future parts if present (legacy support)
        if contract.part3:
            normalized["part3"] = cls._adapt_segmentation_part(contract.part3)
        if contract.part4:
            normalized["part4"] = cls._adapt_segmentation_part(contract.part4)
        
        return normalized
    
    @classmethod
    def _adapt_segmentation_part(cls, part: Any) -> Dict[str, Any]:
        """
        Adapt a single segmentation part.
        
        Aligned with final Shunya contract structure:
        {
            "start_time": 0,
            "end_time": 240,
            "duration": 240,
            "content": "Introduction, agenda setting, discovery, rapport building",
            "key_points": ["Introduction", "Agenda setting", "Discovery questions"]
        }
        """
        if not part:
            return {}
        
        # Handle both new structure (content, key_points) and legacy (summary, transcript)
        content = getattr(part, "content", None) or getattr(part, "summary", None) or getattr(part, "transcript", None) or ""
        key_points = getattr(part, "key_points", None) or getattr(part, "key_topics", None) or []
        
        return {
            "start_time": getattr(part, "start_time", None),
            "end_time": getattr(part, "end_time", None),
            "duration": getattr(part, "duration", None) or getattr(part, "duration_seconds", None),
            "content": content,
            "key_points": key_points,
            # Legacy fields (for backward compatibility)
            "transcript": getattr(part, "transcript", None) or content,
            "summary": getattr(part, "summary", None) or content,
            "sentiment_score": getattr(part, "sentiment_score", None),
            "key_topics": key_points,
            "duration_seconds": getattr(part, "duration_seconds", None) or getattr(part, "duration", None),
        }


class ShunyaWebhookAdapter:
    """
    Adapter for webhook payloads.
    
    Validates and extracts webhook payload structure.
    """
    
    @classmethod
    def adapt(cls, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt Shunya webhook payload to Otto format.
        
        Args:
            raw_payload: Raw webhook payload from Shunya
        
        Returns:
            Normalized payload dictionary
        """
        # Validate against contract
        contract = validate_shunya_response(raw_payload, ShunyaWebhookPayload)
        
        # Extract job ID (handle aliases)
        shunya_job_id = contract.shunya_job_id or contract.job_id or contract.task_id
        
        normalized = {
            "shunya_job_id": shunya_job_id,
            "status": (contract.status or "").lower(),
            "company_id": contract.company_id,
            "result": contract.result.dict() if hasattr(contract.result, 'dict') else contract.result,
            "error": contract.error.dict() if hasattr(contract.error, 'dict') and isinstance(contract.error, ShunyaErrorEnvelope) else contract.error,
            "timestamp": contract.timestamp or contract.created_at,
        }
        
        return normalized


class ShunyaErrorAdapter:
    """
    Adapter for error responses.
    
    Parses and normalizes Shunya error envelopes.
    """
    
    @classmethod
    def adapt(cls, raw_error: Any) -> Dict[str, Any]:
        """
        Adapt Shunya error response to Otto format.
        
        Args:
            raw_error: Raw error response (dict, string, or error envelope)
        
        Returns:
            Normalized error dictionary
        """
        # Handle string errors
        if isinstance(raw_error, str):
            return {
                "code": "UNKNOWN_ERROR",
                "message": raw_error,
                "details": {},
                "retryable": False,
            }
        
        # Validate against contract if dict
        if isinstance(raw_error, dict):
            contract = validate_shunya_response(raw_error, ShunyaErrorEnvelope)
            return {
                "code": contract.code or "UNKNOWN_ERROR",
                "message": contract.message or str(raw_error),
                "details": contract.details or {},
                "retryable": contract.retryable or False,
                "retry_after": contract.retry_after,
                "request_id": contract.request_id,
                "timestamp": contract.timestamp,
            }
        
        # Fallback
        return {
            "code": "UNKNOWN_ERROR",
            "message": str(raw_error),
            "details": {},
            "retryable": False,
        }


# ============================================================================
# Global adapter instances
# ============================================================================

csr_call_adapter = ShunyaCSRCallAdapter()
visit_adapter = ShunyaVisitAdapter()
segmentation_adapter = ShunyaSegmentationAdapter()
webhook_adapter = ShunyaWebhookAdapter()
error_adapter = ShunyaErrorAdapter()



This module provides adapters that translate Shunya's API responses into Otto's
internal format using contract stubs and mapping tables.

Architecture:
- Contracts (shunya_contracts.py): Define expected Shunya response shapes
- Mappings (shunya_mappings.py): Translate Shunya values → Otto enums
- Adapters (this file): Orchestrate validation, mapping, and transformation

All adapters are:
- Idempotent: Same input → same output always
- Graceful: Handle missing/unknown fields without breaking
- Evolvable: Easy to update when Shunya confirms schemas
- Tenant-agnostic: Multi-tenancy handled at integration layer, not adapters
"""
from typing import Optional, Dict, Any, List
from app.core.pii_masking import PIISafeLogger
from app.schemas.shunya_contracts import (
    ShunyaCSRCallAnalysis,
    ShunyaVisitAnalysis,
    ShunyaMeetingSegmentation,
    ShunyaWebhookPayload,
    ShunyaErrorEnvelope,
    validate_shunya_response,
)
from app.services.shunya_mappings import (
    map_shunya_csr_outcome_to_lead_status,
    map_shunya_visit_outcome_to_appointment_outcome,
    map_visit_outcome_to_appointment_status,
    map_visit_outcome_to_lead_status,
    normalize_shunya_objection_label,
    map_shunya_action_to_task_assignee,
    map_shunya_opportunity_to_signal_type,
    map_shunya_opportunity_severity_to_signal_severity,
    normalize_shunya_sop_stage,
)

logger = PIISafeLogger(__name__)


class ShunyaCSRCallAdapter:
    """
    Adapter for CSR call analysis responses.
    
    Transforms ShunyaCSRCallAnalysis contract → Otto domain models.
    """
    
    @classmethod
    def adapt(cls, raw_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt Shunya CSR call analysis response to Otto format.
        
        Args:
            raw_response: Raw response dictionary from Shunya
        
        Returns:
            Normalized dictionary ready for Otto domain model persistence
        """
        # Validate against contract (graceful - handles missing fields)
        contract = validate_shunya_response(raw_response, ShunyaCSRCallAnalysis)
        
        # Extract and map values
        normalized = {
            "job_id": contract.job_id,
            
            # Qualification → Lead Status
            "qualification": cls._adapt_qualification(contract.qualification) if contract.qualification else {},
            "lead_status": cls._adapt_qualification_to_lead_status(contract.qualification),
            
            # Objections
            "objections": cls._adapt_objections(contract.objections) if contract.objections else {},
            
            # SOP Compliance
            "compliance": cls._adapt_compliance(contract.compliance) if contract.compliance else {},
            
            # Summary
            "summary": cls._adapt_summary(contract.summary) if contract.summary else {},
            
            # Sentiment
            "sentiment_score": contract.sentiment_score,
            
            # Pending Actions
            "pending_actions": cls._adapt_pending_actions(contract.pending_actions or [], context="csr_call"),
            
            # Missed Opportunities
            "missed_opportunities": cls._adapt_missed_opportunities(contract.missed_opportunities or []),
            
            # Entities
            "entities": cls._adapt_entities(contract.entities) if contract.entities else {},
            
            # Metadata
            "analyzed_at": contract.analyzed_at,
            "confidence_score": contract.confidence_score,
        }
        
        return normalized
    
    @classmethod
    def _adapt_qualification(cls, qualification: Any) -> Dict[str, Any]:
        """Adapt qualification response."""
        if not qualification:
            return {}
        
        return {
            "qualification_status": qualification.qualification_status,
            "bant_scores": qualification.bant_scores.dict() if qualification.bant_scores else {},
            "overall_score": qualification.overall_score,
            "confidence_score": qualification.confidence_score,
            "decision_makers": qualification.decision_makers or [],
            "urgency_signals": qualification.urgency_signals or [],
            "budget_indicators": qualification.budget_indicators or [],
        }
    
    @classmethod
    def _adapt_qualification_to_lead_status(cls, qualification: Any) -> Optional[str]:
        """Map qualification status to LeadStatus."""
        if not qualification or not qualification.qualification_status:
            return None
        
        lead_status = map_shunya_csr_outcome_to_lead_status(qualification.qualification_status)
        return lead_status.value if lead_status else None
    
    @classmethod
    def _adapt_objections(cls, objections: Any) -> Dict[str, Any]:
        """Adapt objections response."""
        if not objections:
            return {"objections": [], "total_objections": 0}
        
        adapted_objections = []
        for obj in (objections.objections or []):
            adapted_objections.append({
                "objection_text": obj.objection_text,
                "objection_label": normalize_shunya_objection_label(obj.objection_label),
                "severity": obj.severity,
                "overcome": obj.overcome or False,
                "timestamp": obj.timestamp,
                "speaker_id": obj.speaker_id,
            })
        
        return {
            "objections": adapted_objections,
            "total_objections": objections.total_objections or len(adapted_objections),
            "severity_breakdown": objections.severity_breakdown or {},
        }
    
    @classmethod
    def _adapt_compliance(cls, compliance: Any) -> Dict[str, Any]:
        """Adapt SOP compliance response."""
        if not compliance:
            return {"stages_followed": [], "stages_missed": [], "compliance_score": None}
        
        # Normalize SOP stage names
        stages_followed = [
            normalize_shunya_sop_stage(stage) for stage in (compliance.stages_followed or [])
            if normalize_shunya_sop_stage(stage)
        ]
        stages_missed = [
            normalize_shunya_sop_stage(stage) for stage in (compliance.stages_missed or [])
            if normalize_shunya_sop_stage(stage)
        ]
        
        return {
            "stages_followed": stages_followed,
            "stages_missed": stages_missed,
            "compliance_score": compliance.compliance_score,
            "stage_details": [
                {
                    "stage_name": normalize_shunya_sop_stage(stage.stage_name) if hasattr(stage, 'stage_name') else None,
                    "completed": stage.completed if hasattr(stage, 'completed') else None,
                    "score": stage.score if hasattr(stage, 'score') else None,
                }
                for stage in (compliance.stage_details or [])
            ] if hasattr(compliance, 'stage_details') else [],
        }
    
    @classmethod
    def _adapt_summary(cls, summary: Any) -> Dict[str, Any]:
        """Adapt summary response."""
        if not summary:
            return {"summary": "", "key_points": [], "next_steps": []}
        
        return {
            "summary": summary.summary or "",
            "key_points": summary.key_points or [],
            "next_steps": summary.next_steps or [],
            "sentiment": summary.sentiment,
            "confidence": summary.confidence,
        }
    
    @classmethod
    def _adapt_pending_actions(cls, actions: List[Any], context: str = "csr_call") -> List[Dict[str, Any]]:
        """
        Adapt pending actions to Otto task format.
        
        Handles free-string action types from Shunya (e.g., "follow up tomorrow", "send technician").
        Maps common patterns to internal enums with graceful fallback to generic/custom type.
        """
        adapted = []
        for action in actions:
            # Get action type (free-string from Shunya)
            action_type_str = action.action_type or action.action or ""
            
            # Try to map common patterns to known types, fallback to generic
            mapped_assignee = map_shunya_action_to_task_assignee(action_type_str, context)
            
            adapted.append({
                "action": action.action or action_type_str or "",
                "action_type": action_type_str,  # Preserve original free-string
                "mapped_assignee": mapped_assignee.value,  # Internal mapping result
                "priority": action.priority,
                "due_at": action.due_at,
                "assignee_type": map_shunya_action_to_task_assignee(action.assignee_type, context).value if action.assignee_type else mapped_assignee.value,
                "context": action.context,
                # Flag to indicate if this is a known pattern or free-string
                "is_known_pattern": action_type_str.lower() in [
                    "follow_up", "follow up", "send_info", "send technician", "call_back",
                    "technician_visit", "technician visit", "follow_up_call", "follow up call"
                ],
            })
        return adapted
    
    @classmethod
    def _adapt_missed_opportunities(cls, opportunities: List[Any]) -> List[Dict[str, Any]]:
        """Adapt missed opportunities to Otto signal format."""
        adapted = []
        for opp in opportunities:
            adapted.append({
                "opportunity_text": opp.opportunity_text or "",
                "opportunity_type": opp.opportunity_type,
                "severity": map_shunya_opportunity_severity_to_signal_severity(opp.severity).value,
                "signal_type": map_shunya_opportunity_to_signal_type(opp.opportunity_type).value,
                "timestamp": opp.timestamp,
                "context": opp.context,
            })
        return adapted
    
    @classmethod
    def _adapt_entities(cls, entities: Any) -> Dict[str, Any]:
        """Adapt extracted entities."""
        if not entities:
            return {}
        
        return {
            "address": entities.address,
            "phone_number": entities.phone_number,
            "email": entities.email,
            "appointment_date": entities.appointment_date,
            "scheduled_time": entities.scheduled_time,
            "company_name": entities.company_name,
            "person_name": entities.person_name,
            "budget": entities.budget,
            "other": entities.other or {},
        }


class ShunyaVisitAdapter:
    """
    Adapter for sales visit analysis responses.
    
    Transforms ShunyaVisitAnalysis contract → Otto domain models.
    """
    
    @classmethod
    def adapt(cls, raw_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt Shunya visit analysis response to Otto format.
        
        Args:
            raw_response: Raw response dictionary from Shunya
        
        Returns:
            Normalized dictionary ready for Otto domain model persistence
        """
        # Validate against contract
        contract = validate_shunya_response(raw_response, ShunyaVisitAnalysis)
        
        # Determine outcome
        outcome_str = contract.outcome or contract.appointment_outcome or "pending"
        appointment_outcome = map_shunya_visit_outcome_to_appointment_outcome(outcome_str)
        appointment_status = map_visit_outcome_to_appointment_status(appointment_outcome) if appointment_outcome else None
        lead_status = map_visit_outcome_to_lead_status(appointment_outcome) if appointment_outcome else None
        
        # Extract and map values
        normalized = {
            "job_id": contract.job_id,
            
            # Outcome mapping
            "outcome": outcome_str,
            "appointment_outcome": appointment_outcome.value if appointment_outcome else None,
            "appointment_status": appointment_status.value if appointment_status else None,
            "lead_status": lead_status.value if lead_status else None,
            
            # Deal information
            "deal_size": contract.deal_size,
            "deal_currency": contract.deal_currency,
            
            # Analysis data (reuse CSR adapter methods)
            "qualification": ShunyaCSRCallAdapter._adapt_qualification(contract.qualification) if contract.qualification else {},
            "objections": ShunyaCSRCallAdapter._adapt_objections(contract.objections) if contract.objections else {},
            "compliance": ShunyaCSRCallAdapter._adapt_compliance(contract.compliance) if contract.compliance else {},
            "summary": ShunyaCSRCallAdapter._adapt_summary(contract.summary) if contract.summary else {},
            
            # Sentiment
            "sentiment_score": contract.sentiment_score,
            
            # Visit-specific actions
            "visit_actions": ShunyaCSRCallAdapter._adapt_pending_actions(
                contract.visit_actions or contract.pending_actions or [],
                context="visit"
            ),
            "missed_opportunities": ShunyaCSRCallAdapter._adapt_missed_opportunities(
                contract.missed_opportunities or []
            ),
            
            # Entities
            "entities": ShunyaCSRCallAdapter._adapt_entities(contract.entities) if contract.entities else {},
            
            # Metadata
            "analyzed_at": contract.analyzed_at,
            "confidence_score": contract.confidence_score,
        }
        
        return normalized


class ShunyaSegmentationAdapter:
    """
    Adapter for meeting segmentation responses.
    
    Transforms ShunyaMeetingSegmentation contract → Otto format.
    """
    
    @classmethod
    def adapt(cls, raw_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt Shunya segmentation response to Otto format.
        
        Args:
            raw_response: Raw response dictionary from Shunya
        
        Returns:
            Normalized dictionary ready for Otto domain model persistence
        """
        # Validate against contract
        contract = validate_shunya_response(raw_response, ShunyaMeetingSegmentation)
        
        # Adapt segmentation parts
        normalized = {
            "success": contract.success,
            "call_id": contract.call_id or contract.job_id,  # Fallback to job_id if call_id not present
            "job_id": contract.job_id,
            "part1": cls._adapt_segmentation_part(contract.part1) if contract.part1 else {},
            "part2": cls._adapt_segmentation_part(contract.part2) if contract.part2 else {},
            "transition_point": contract.transition_point,
            "transition_indicators": contract.transition_indicators or [],
            "segmentation_confidence": contract.segmentation_confidence,
            "meeting_structure_score": contract.meeting_structure_score,
            "call_type": contract.call_type,
            "created_at": contract.created_at or contract.analyzed_at,
            # Legacy fields (for backward compatibility)
            "outcome": contract.outcome,
            "analyzed_at": contract.analyzed_at or contract.created_at,
        }
        
        # Handle future parts if present (legacy support)
        if contract.part3:
            normalized["part3"] = cls._adapt_segmentation_part(contract.part3)
        if contract.part4:
            normalized["part4"] = cls._adapt_segmentation_part(contract.part4)
        
        return normalized
    
    @classmethod
    def _adapt_segmentation_part(cls, part: Any) -> Dict[str, Any]:
        """
        Adapt a single segmentation part.
        
        Aligned with final Shunya contract structure:
        {
            "start_time": 0,
            "end_time": 240,
            "duration": 240,
            "content": "Introduction, agenda setting, discovery, rapport building",
            "key_points": ["Introduction", "Agenda setting", "Discovery questions"]
        }
        """
        if not part:
            return {}
        
        # Handle both new structure (content, key_points) and legacy (summary, transcript)
        content = getattr(part, "content", None) or getattr(part, "summary", None) or getattr(part, "transcript", None) or ""
        key_points = getattr(part, "key_points", None) or getattr(part, "key_topics", None) or []
        
        return {
            "start_time": getattr(part, "start_time", None),
            "end_time": getattr(part, "end_time", None),
            "duration": getattr(part, "duration", None) or getattr(part, "duration_seconds", None),
            "content": content,
            "key_points": key_points,
            # Legacy fields (for backward compatibility)
            "transcript": getattr(part, "transcript", None) or content,
            "summary": getattr(part, "summary", None) or content,
            "sentiment_score": getattr(part, "sentiment_score", None),
            "key_topics": key_points,
            "duration_seconds": getattr(part, "duration_seconds", None) or getattr(part, "duration", None),
        }


class ShunyaWebhookAdapter:
    """
    Adapter for webhook payloads.
    
    Validates and extracts webhook payload structure.
    """
    
    @classmethod
    def adapt(cls, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt Shunya webhook payload to Otto format.
        
        Args:
            raw_payload: Raw webhook payload from Shunya
        
        Returns:
            Normalized payload dictionary
        """
        # Validate against contract
        contract = validate_shunya_response(raw_payload, ShunyaWebhookPayload)
        
        # Extract job ID (handle aliases)
        shunya_job_id = contract.shunya_job_id or contract.job_id or contract.task_id
        
        normalized = {
            "shunya_job_id": shunya_job_id,
            "status": (contract.status or "").lower(),
            "company_id": contract.company_id,
            "result": contract.result.dict() if hasattr(contract.result, 'dict') else contract.result,
            "error": contract.error.dict() if hasattr(contract.error, 'dict') and isinstance(contract.error, ShunyaErrorEnvelope) else contract.error,
            "timestamp": contract.timestamp or contract.created_at,
        }
        
        return normalized


class ShunyaErrorAdapter:
    """
    Adapter for error responses.
    
    Parses and normalizes Shunya error envelopes.
    """
    
    @classmethod
    def adapt(cls, raw_error: Any) -> Dict[str, Any]:
        """
        Adapt Shunya error response to Otto format.
        
        Args:
            raw_error: Raw error response (dict, string, or error envelope)
        
        Returns:
            Normalized error dictionary
        """
        # Handle string errors
        if isinstance(raw_error, str):
            return {
                "code": "UNKNOWN_ERROR",
                "message": raw_error,
                "details": {},
                "retryable": False,
            }
        
        # Validate against contract if dict
        if isinstance(raw_error, dict):
            contract = validate_shunya_response(raw_error, ShunyaErrorEnvelope)
            return {
                "code": contract.code or "UNKNOWN_ERROR",
                "message": contract.message or str(raw_error),
                "details": contract.details or {},
                "retryable": contract.retryable or False,
                "retry_after": contract.retry_after,
                "request_id": contract.request_id,
                "timestamp": contract.timestamp,
            }
        
        # Fallback
        return {
            "code": "UNKNOWN_ERROR",
            "message": str(raw_error),
            "details": {},
            "retryable": False,
        }


# ============================================================================
# Global adapter instances
# ============================================================================

csr_call_adapter = ShunyaCSRCallAdapter()
visit_adapter = ShunyaVisitAdapter()
segmentation_adapter = ShunyaSegmentationAdapter()
webhook_adapter = ShunyaWebhookAdapter()
error_adapter = ShunyaErrorAdapter()

