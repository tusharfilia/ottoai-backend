"""
Shunya Response Normalizer

Provides defensive parsing and normalization for Shunya API responses.
Handles variations in response format and provides consistent output structure.
"""
from typing import Dict, Any, List, Optional
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)


class ShunyaResponseNormalizer:
    """
    Normalizes Shunya API responses to consistent structure.
    
    Handles:
    - Variations in response format
    - Missing/null fields
    - Type conversions
    - Nested data extraction
    - Default values
    """
    
    @staticmethod
    def normalize_complete_analysis(response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize complete analysis response from Shunya.
        
        Expected endpoints:
        - GET /api/v1/analysis/complete/{call_id}
        - May include: qualification, objections, compliance, summary, sentiment
        
        Returns normalized structure with all fields present (even if None).
        """
        if not isinstance(response, dict):
            logger.warning(f"Expected dict, got {type(response)}")
            return ShunyaResponseNormalizer._empty_analysis()
        
        normalized = {
            "qualification": ShunyaResponseNormalizer._normalize_qualification(
                response.get("qualification") or response.get("lead_qualification") or {}
            ),
            "objections": ShunyaResponseNormalizer._normalize_objections(
                response.get("objections") or {}
            ),
            "compliance": ShunyaResponseNormalizer._normalize_compliance(
                response.get("compliance") or response.get("sop_compliance") or {}
            ),
            "summary": ShunyaResponseNormalizer._normalize_summary(
                response.get("summary") or response.get("call_summary") or {}
            ),
            "sentiment_score": ShunyaResponseNormalizer._normalize_float(
                response.get("sentiment_score") or response.get("sentiment") or response.get("sentiment_analysis", {}).get("score")
            ),
            "pending_actions": ShunyaResponseNormalizer._normalize_pending_actions(
                response.get("pending_actions") or response.get("action_items") or response.get("next_steps") or []
            ),
            "missed_opportunities": ShunyaResponseNormalizer._normalize_missed_opportunities(
                response.get("missed_opportunities") or response.get("missed_opps") or []
            ),
            "entities": ShunyaResponseNormalizer._normalize_entities(
                response.get("entities") or response.get("extracted_entities") or {}
            ),
            "job_id": response.get("job_id") or response.get("task_id"),
        }
        
        return normalized
    
    @staticmethod
    def _normalize_qualification(qualification: Any) -> Dict[str, Any]:
        """Normalize qualification response."""
        if not isinstance(qualification, dict):
            return {
                "qualification_status": None,
                "bant_scores": {},
                "overall_score": None,
                "confidence_score": None,
                "decision_makers": [],
                "urgency_signals": [],
                "budget_indicators": [],
            }
        
        # Handle different formats for qualification_status
        status = qualification.get("qualification_status") or qualification.get("status") or qualification.get("classification")
        if isinstance(status, str):
            status = status.lower().strip()
        
        return {
            "qualification_status": status,
            "bant_scores": qualification.get("bant_scores") or {},
            "overall_score": ShunyaResponseNormalizer._normalize_float(qualification.get("overall_score")),
            "confidence_score": ShunyaResponseNormalizer._normalize_float(qualification.get("confidence_score")),
            "decision_makers": ShunyaResponseNormalizer._normalize_list(qualification.get("decision_makers")),
            "urgency_signals": ShunyaResponseNormalizer._normalize_list(qualification.get("urgency_signals")),
            "budget_indicators": ShunyaResponseNormalizer._normalize_list(qualification.get("budget_indicators")),
        }
    
    @staticmethod
    def _normalize_objections(objections: Any) -> Dict[str, Any]:
        """Normalize objections response."""
        if not isinstance(objections, dict):
            # If it's a list, convert to expected format
            if isinstance(objections, list):
                return {
                    "objections": [ShunyaResponseNormalizer._normalize_objection_item(obj) for obj in objections],
                    "total_objections": len(objections),
                }
            return {
                "objections": [],
                "total_objections": 0,
            }
        
        objections_list = objections.get("objections", [])
        if not isinstance(objections_list, list):
            objections_list = []
        
        normalized_objections = [
            ShunyaResponseNormalizer._normalize_objection_item(obj)
            for obj in objections_list
        ]
        
        return {
            "objections": normalized_objections,
            "total_objections": len(normalized_objections),
            "severity_breakdown": objections.get("severity_breakdown", {}),
        }
    
    @staticmethod
    def _normalize_objection_item(obj: Any) -> Dict[str, Any]:
        """Normalize a single objection item."""
        if isinstance(obj, str):
            # Simple string objection
            return {
                "objection_text": obj,
                "category_id": None,
                "category_text": None,
                "severity": "medium",
                "overcome": False,
                "timestamp": None,
                "speaker_id": None,
            }
        elif isinstance(obj, dict):
            return {
                "objection_text": obj.get("objection_text") or obj.get("text") or obj.get("objection") or "",
                "category_id": obj.get("category_id"),
                "category_text": obj.get("category_text") or obj.get("category"),
                "severity": (obj.get("severity") or "medium").lower(),
                "overcome": bool(obj.get("overcome") or False),
                "timestamp": obj.get("timestamp"),
                "speaker_id": obj.get("speaker_id"),
                "response_suggestions": ShunyaResponseNormalizer._normalize_list(obj.get("response_suggestions")),
                "confidence_score": ShunyaResponseNormalizer._normalize_float(obj.get("confidence_score")),
            }
        else:
            return {
                "objection_text": str(obj),
                "category_id": None,
                "category_text": None,
                "severity": "medium",
                "overcome": False,
                "timestamp": None,
                "speaker_id": None,
            }
    
    @staticmethod
    def _normalize_compliance(compliance: Any) -> Dict[str, Any]:
        """Normalize SOP compliance response."""
        if not isinstance(compliance, dict):
            return {
                "compliance_score": None,
                "stages_followed": [],
                "stages_missed": [],
                "violations": [],
                "positive_behaviors": [],
                "recommendations": [],
            }
        
        return {
            "compliance_score": ShunyaResponseNormalizer._normalize_float(compliance.get("compliance_score")),
            "stages_followed": ShunyaResponseNormalizer._normalize_list(compliance.get("stages_followed") or compliance.get("stages_completed")),
            "stages_missed": ShunyaResponseNormalizer._normalize_list(compliance.get("stages_missed") or compliance.get("stages_not_completed")),
            "violations": ShunyaResponseNormalizer._normalize_list(compliance.get("violations")),
            "positive_behaviors": ShunyaResponseNormalizer._normalize_list(compliance.get("positive_behaviors")),
            "recommendations": ShunyaResponseNormalizer._normalize_list(compliance.get("recommendations")),
        }
    
    @staticmethod
    def _normalize_summary(summary: Any) -> Dict[str, Any]:
        """Normalize call/visit summary response."""
        if isinstance(summary, str):
            return {
                "summary": summary,
                "key_points": [],
                "action_items": [],
                "next_steps": [],
                "confidence_score": None,
            }
        elif not isinstance(summary, dict):
            return {
                "summary": "",
                "key_points": [],
                "action_items": [],
                "next_steps": [],
                "confidence_score": None,
            }
        
        return {
            "summary": summary.get("summary") or summary.get("text") or "",
            "key_points": ShunyaResponseNormalizer._normalize_list(summary.get("key_points") or summary.get("main_points")),
            "action_items": ShunyaResponseNormalizer._normalize_list(summary.get("action_items") or summary.get("actions")),
            "next_steps": ShunyaResponseNormalizer._normalize_list(summary.get("next_steps") or summary.get("follow_ups")),
            "confidence_score": ShunyaResponseNormalizer._normalize_float(summary.get("confidence_score")),
        }
    
    @staticmethod
    def _normalize_pending_actions(actions: Any) -> List[Dict[str, Any]]:
        """Normalize pending actions list."""
        if not isinstance(actions, list):
            return []
        
        normalized = []
        for action in actions:
            if isinstance(action, str):
                normalized.append({
                    "action": action,
                    "due_at": None,
                    "priority": "medium",
                })
            elif isinstance(action, dict):
                normalized.append({
                    "action": action.get("action") or action.get("text") or action.get("description") or "",
                    "due_at": action.get("due_at") or action.get("due_date"),
                    "priority": (action.get("priority") or "medium").lower(),
                })
        
        return normalized
    
    @staticmethod
    def _normalize_missed_opportunities(opps: Any) -> List[Dict[str, Any]]:
        """Normalize missed opportunities list."""
        if not isinstance(opps, list):
            return []
        
        normalized = []
        for opp in opps:
            if isinstance(opp, str):
                normalized.append({
                    "opportunity": opp,
                    "severity": "medium",
                    "timestamp": None,
                })
            elif isinstance(opp, dict):
                normalized.append({
                    "opportunity": opp.get("opportunity") or opp.get("text") or opp.get("description") or "",
                    "severity": (opp.get("severity") or "medium").lower(),
                    "timestamp": opp.get("timestamp"),
                })
        
        return normalized
    
    @staticmethod
    def _normalize_entities(entities: Any) -> Dict[str, Any]:
        """Normalize extracted entities (address, date, etc.)."""
        if not isinstance(entities, dict):
            return {}
        
        return {
            "address": entities.get("address") or entities.get("property_address"),
            "appointment_date": entities.get("appointment_date") or entities.get("scheduled_time") or entities.get("date"),
            "scheduled_time": entities.get("scheduled_time") or entities.get("time"),
            "name": entities.get("name") or entities.get("customer_name"),
            "phone": entities.get("phone") or entities.get("phone_number"),
            "email": entities.get("email"),
        }
    
    @staticmethod
    def _normalize_float(value: Any) -> Optional[float]:
        """Safely convert to float."""
        if value is None:
            return None
        try:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                return float(value.strip())
        except (ValueError, TypeError):
            pass
        return None
    
    @staticmethod
    def _normalize_list(value: Any) -> List:
        """Safely convert to list."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, (str, int, float)):
            return [value]
        return []
    
    @staticmethod
    def _empty_analysis() -> Dict[str, Any]:
        """Return empty analysis structure."""
        return {
            "qualification": {
                "qualification_status": None,
                "bant_scores": {},
                "overall_score": None,
                "confidence_score": None,
                "decision_makers": [],
                "urgency_signals": [],
                "budget_indicators": [],
            },
            "objections": {
                "objections": [],
                "total_objections": 0,
            },
            "compliance": {
                "compliance_score": None,
                "stages_followed": [],
                "stages_missed": [],
                "violations": [],
                "positive_behaviors": [],
                "recommendations": [],
            },
            "summary": {
                "summary": "",
                "key_points": [],
                "action_items": [],
                "next_steps": [],
                "confidence_score": None,
            },
            "sentiment_score": None,
            "pending_actions": [],
            "missed_opportunities": [],
            "entities": {},
            "job_id": None,
        }
    
    @staticmethod
    def normalize_transcript_response(response: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize transcript response from Shunya."""
        if not isinstance(response, dict):
            logger.warning(f"Expected dict for transcript, got {type(response)}")
            return {
                "transcript_text": "",
                "speaker_labels": [],
                "confidence_score": None,
                "transcript_id": None,
                "task_id": None,
            }
        
        return {
            "transcript_text": response.get("transcript_text") or response.get("transcript") or response.get("text") or "",
            "speaker_labels": ShunyaResponseNormalizer._normalize_list(response.get("speaker_labels") or response.get("speakers") or response.get("diarization")),
            "confidence_score": ShunyaResponseNormalizer._normalize_float(response.get("confidence_score") or response.get("confidence")),
            "transcript_id": response.get("transcript_id"),
            "task_id": response.get("task_id") or response.get("job_id"),
        }
    
    @staticmethod
    def normalize_meeting_segmentation(response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize meeting segmentation response for sales visits.
        
        Aligned with final Shunya contract structure:
        {
            "success": true,
            "call_id": 3070,
            "part1": {"start_time": 0, "end_time": 240, "duration": 240, "content": "...", "key_points": [...]},
            "part2": {"start_time": 240, "end_time": 420, "duration": 180, "content": "...", "key_points": [...]},
            "segmentation_confidence": 0.8,
            "transition_point": 240,
            "transition_indicators": [...],
            "meeting_structure_score": 4,
            "call_type": "sales_appointment",
            "created_at": null
        }
        """
        if not isinstance(response, dict):
            return {
                "part1": {},
                "part2": {},
                "segmentation_confidence": None,
                "transition_point": None,
            }
        
        # Extract part1 and part2 (tolerant of missing fields)
        part1_raw = response.get("part1") or {}
        part2_raw = response.get("part2") or {}
        
        return {
            "success": response.get("success", True),
            "call_id": response.get("call_id"),
            "part1": {
                "start_time": part1_raw.get("start_time"),
                "end_time": part1_raw.get("end_time"),
                "duration": part1_raw.get("duration"),
                "content": part1_raw.get("content") or part1_raw.get("summary") or "",
                "key_points": part1_raw.get("key_points") or part1_raw.get("key_topics") or [],
            },
            "part2": {
                "start_time": part2_raw.get("start_time"),
                "end_time": part2_raw.get("end_time"),
                "duration": part2_raw.get("duration"),
                "content": part2_raw.get("content") or part2_raw.get("summary") or "",
                "key_points": part2_raw.get("key_points") or part2_raw.get("key_topics") or [],
            },
            "segmentation_confidence": ShunyaResponseNormalizer._normalize_float(response.get("segmentation_confidence")),
            "transition_point": response.get("transition_point"),
            "transition_indicators": response.get("transition_indicators") or [],
            "meeting_structure_score": response.get("meeting_structure_score"),
            "call_type": response.get("call_type"),
            "created_at": response.get("created_at") or response.get("analyzed_at"),
            # Legacy fields (for backward compatibility)
            "outcome": (response.get("outcome") or "").lower() if response.get("outcome") else None,
        }


# Global normalizer instance
shunya_normalizer = ShunyaResponseNormalizer()
