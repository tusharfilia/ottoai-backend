"""
Simulation tests for Shunya adapter layer.

These tests use synthetic test payloads (not real Shunya data) to ensure
all adapter methods can run end-to-end with placeholder data.

All tests are marked as `xfail` or `skip` until Shunya provides final schemas.

These tests verify:
- Adapters handle missing fields gracefully
- Adapters handle unknown enums gracefully
- Adapters are idempotent
- Adapters produce consistent outputs
"""
import pytest
from typing import Dict, Any
from datetime import datetime

from app.services.shunya_adapters_v2 import (
    ShunyaCSRCallAdapter,
    ShunyaVisitAdapter,
    ShunyaSegmentationAdapter,
    ShunyaWebhookAdapter,
    ShunyaErrorAdapter,
)
from app.services.shunya_mappings import (
    map_shunya_csr_outcome_to_lead_status,
    map_shunya_visit_outcome_to_appointment_outcome,
    normalize_shunya_objection_label,
    map_shunya_action_to_task_assignee,
)


# ============================================================================
# Synthetic Test Payloads
# ============================================================================

def make_synthetic_csr_analysis() -> Dict[str, Any]:
    """Create synthetic CSR call analysis payload."""
    return {
        "job_id": "test_job_123",
        "call_id": 456,
        "qualification": {
            "qualification_status": "qualified_and_booked",
            "bant_scores": {
                "budget": 0.8,
                "authority": 0.9,
                "need": 0.7,
                "timeline": 0.6,
            },
            "overall_score": 0.75,
            "confidence_score": 0.85,
            "decision_makers": ["John Doe"],
            "urgency_signals": ["Needs roof repair ASAP"],
            "budget_indicators": ["Mentioned $15k budget"],
        },
        "objections": {
            "objections": [
                {
                    "objection_text": "Price seems high",
                    "objection_label": "price",
                    "severity": "medium",
                    "overcome": False,
                }
            ],
            "total_objections": 1,
        },
        "compliance": {
            "stages_followed": ["greeting", "qualification", "closing"],
            "stages_missed": ["presentation"],
            "compliance_score": 0.75,
        },
        "summary": {
            "summary": "Customer interested in roof repair, needs quote",
            "key_points": ["Budget: $15k", "Urgent need"],
            "next_steps": ["Send quote", "Follow up tomorrow"],
        },
        "sentiment_score": 0.6,
        "pending_actions": [
            {
                "action": "Send quote",
                "action_type": "follow_up_tomorrow",  # Free-string action type
                "priority": "high",
                "due_at": "2025-11-25T10:00:00Z",
                "assignee_type": "csr",
            }
        ],
        "missed_opportunities": [],
        "entities": {
            "address": "123 Main St",
            "phone_number": "555-1234",
        },
        "analyzed_at": "2025-11-24T12:00:00Z",
        "confidence_score": 0.85,
    }


def make_synthetic_visit_analysis() -> Dict[str, Any]:
    """Create synthetic visit analysis payload."""
    return {
        "job_id": "test_visit_job_456",
        "appointment_id": "appt_789",
        "outcome": "won",
        "qualification": {
            "qualification_status": "qualified_and_booked",
        },
        "objections": {
            "objections": [],
            "total_objections": 0,
        },
        "sentiment_score": 0.8,
        "visit_actions": [
            {
                "action": "Send contract",
                "assignee_type": "rep",
            }
        ],
        "missed_opportunities": [
            {
                "opportunity_text": "Could have upsold gutter cleaning",
                "opportunity_type": "upsell",
                "severity": "medium",
            }
        ],
        "deal_size": 15000.0,
        "deal_currency": "USD",
        "analyzed_at": "2025-11-24T14:00:00Z",
    }


def make_synthetic_segmentation() -> Dict[str, Any]:
    """
    Create synthetic segmentation payload aligned with final Shunya contract.
    
    New structure:
    {
        "success": true,
        "call_id": 999,
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
    return {
        "success": True,
        "call_id": 999,
        "job_id": "test_seg_job_789",  # Legacy field for backward compatibility
        "part1": {
            "start_time": 0,
            "end_time": 240,
            "duration": 240,
            "content": "Introduction, agenda setting, discovery, rapport building",
            "key_points": ["Introduction", "Agenda setting", "Discovery questions"],
            # Legacy fields for backward compatibility
            "transcript": "Part 1 transcript...",
            "summary": "Rapport building and agenda setting",
            "sentiment_score": 0.7,
            "key_topics": ["Small talk", "Agenda"],
            "duration_seconds": 300,
        },
        "part2": {
            "start_time": 240,
            "end_time": 420,
            "duration": 180,
            "content": "Presentation, proposal, closing, next steps",
            "key_points": ["Presentation of solution", "Scheduling of appointment"],
            # Legacy fields for backward compatibility
            "transcript": "Part 2 transcript...",
            "summary": "Proposal and closing",
            "sentiment_score": 0.8,
            "key_topics": ["Proposal", "Pricing"],
            "duration_seconds": 600,
        },
        "transition_point": 240,
        "transition_indicators": ["Scheduling of appointment", "Confirmation of details"],
        "segmentation_confidence": 0.8,
        "meeting_structure_score": 4,
        "call_type": "sales_appointment",
        "created_at": "2025-11-24T15:00:00Z",
        # Legacy fields for backward compatibility
        "outcome": "won",
        "analyzed_at": "2025-11-24T15:00:00Z",
    }


def make_synthetic_webhook() -> Dict[str, Any]:
    """Create synthetic webhook payload."""
    return {
        "shunya_job_id": "webhook_job_123",
        "status": "completed",
        "company_id": "company_abc",
        "result": make_synthetic_csr_analysis(),
        "timestamp": "2025-11-24T16:00:00Z",
    }


def make_synthetic_error() -> Dict[str, Any]:
    """Create synthetic error payload aligned with canonical error envelope."""
    return {
        "success": False,
        "error": {
            "error_code": "TRANSCRIPTION_FAILED",
            "error_type": "processing_error",
            "message": "Audio quality too poor",
            "retryable": True,
            "details": {},
            "timestamp": "2025-11-28T10:15:42.123Z",
            "request_id": "error_req_123",
        }
    }


# ============================================================================
# CSR Call Adapter Tests
# ============================================================================

@pytest.mark.skip(reason="Waiting for Shunya to confirm final CSR analysis schema")
class TestCSRCallAdapterSimulation:
    """Test CSR call adapter with synthetic payloads."""
    
    def test_adapter_handles_complete_payload(self):
        """Test adapter with complete synthetic payload."""
        payload = make_synthetic_csr_analysis()
        result = ShunyaCSRCallAdapter.adapt(payload)
        
        assert result is not None
        assert result["job_id"] == "test_job_123"
        assert result["lead_status"] is not None  # Should map to LeadStatus
        assert "qualification" in result
        assert "objections" in result
    
    def test_adapter_handles_missing_fields(self):
        """Test adapter with missing optional fields."""
        payload = {
            "job_id": "test_job_incomplete",
            "qualification": {
                "qualification_status": "qualified_and_booked",
            },
            # Missing objections, compliance, summary, etc.
        }
        result = ShunyaCSRCallAdapter.adapt(payload)
        
        assert result is not None
        assert result["objections"] == {"objections": [], "total_objections": 0}
        assert result["compliance"] is not None
        assert result["summary"] is not None
    
    def test_adapter_handles_unknown_outcome(self):
        """Test adapter with unknown outcome enum."""
        payload = {
            "job_id": "test_unknown_outcome",
            "qualification": {
                "qualification_status": "unknown_shunya_value",  # Unknown enum
            },
        }
        result = ShunyaCSRCallAdapter.adapt(payload)
        
        # Should not break, should handle gracefully
        assert result is not None
        assert result["lead_status"] is None  # Unknown → None (graceful)
    
    def test_adapter_idempotency(self):
        """Test that adapter produces same output for same input."""
        payload = make_synthetic_csr_analysis()
        
        result1 = ShunyaCSRCallAdapter.adapt(payload)
        result2 = ShunyaCSRCallAdapter.adapt(payload)
        
        # Should be identical (idempotent)
        assert result1 == result2


# ============================================================================
# Visit Adapter Tests
# ============================================================================

@pytest.mark.skip(reason="Waiting for Shunya to confirm final visit analysis schema")
class TestVisitAdapterSimulation:
    """Test visit adapter with synthetic payloads."""
    
    def test_adapter_handles_complete_payload(self):
        """Test adapter with complete synthetic payload."""
        payload = make_synthetic_visit_analysis()
        result = ShunyaVisitAdapter.adapt(payload)
        
        assert result is not None
        assert result["appointment_outcome"] == "won"
        assert result["deal_size"] == 15000.0
    
    def test_adapter_handles_missing_outcome(self):
        """Test adapter with missing outcome."""
        payload = {
            "job_id": "test_no_outcome",
            # Missing outcome field
        }
        result = ShunyaVisitAdapter.adapt(payload)
        
        assert result is not None
        assert result["outcome"] == "pending"  # Should default to pending
    
    def test_adapter_maps_outcome_to_appointment_status(self):
        """Test that outcome maps correctly to appointment status."""
        payload = make_synthetic_visit_analysis()
        result = ShunyaVisitAdapter.adapt(payload)
        
        assert result["appointment_outcome"] == "won"
        assert result["appointment_status"] == "completed"  # Won → completed


# ============================================================================
# Segmentation Adapter Tests
# ============================================================================

class TestSegmentationAdapterSimulation:
    """Test segmentation adapter with synthetic payloads (aligned with final Shunya contract)."""
    
    def test_adapter_handles_new_segmentation_structure(self):
        """Test adapter with new segmentation structure (content, key_points, etc.)."""
        payload = make_synthetic_segmentation()
        result = ShunyaSegmentationAdapter.adapt(payload)
        
        assert result is not None
        assert result["success"] is True
        assert result["call_id"] == 999
        assert "part1" in result
        assert "part2" in result
        assert result["transition_point"] == 240
        assert result["segmentation_confidence"] == 0.8
        assert result["transition_indicators"] == ["Scheduling of appointment", "Confirmation of details"]
        assert result["meeting_structure_score"] == 4
        assert result["call_type"] == "sales_appointment"
        
        # Verify part1 structure
        part1 = result["part1"]
        assert part1["start_time"] == 0
        assert part1["end_time"] == 240
        assert part1["duration"] == 240
        assert "Introduction, agenda setting" in part1.get("content", "")
        assert "Introduction" in part1.get("key_points", [])
    
    def test_adapter_handles_missing_parts(self):
        """Test adapter with missing part2 (graceful degradation)."""
        payload = {
            "success": True,
            "call_id": 999,
            "job_id": "test_partial",
            "part1": {
                "start_time": 0,
                "end_time": 120,
                "duration": 120,
                "content": "Part 1 only",
                "key_points": ["Introduction"],
            },
            # Missing part2
        }
        result = ShunyaSegmentationAdapter.adapt(payload)
        
        assert result is not None
        assert "part1" in result
        assert result["part2"] == {}  # Should default to empty dict
        assert result["call_id"] == 999
    
    def test_adapter_handles_missing_optional_fields(self):
        """Test adapter handles missing optional fields gracefully."""
        payload = {
            "success": True,
            "call_id": 999,
            "part1": {
                "content": "Part 1 content",
                # Missing start_time, end_time, duration, key_points
            },
            "part2": {
                "content": "Part 2 content",
            },
            # Missing transition_indicators, call_type, meeting_structure_score
        }
        result = ShunyaSegmentationAdapter.adapt(payload)
        
        # Should not crash
        assert result is not None
        assert "part1" in result
        assert "part2" in result
        # Optional fields should be None or empty
        assert result.get("transition_indicators") is None or result.get("transition_indicators") == []
    
    def test_adapter_idempotency(self):
        """Test that adapter produces same output for same input (idempotent)."""
        payload = make_synthetic_segmentation()
        
        result1 = ShunyaSegmentationAdapter.adapt(payload)
        result2 = ShunyaSegmentationAdapter.adapt(payload)
        
        # Should be identical (idempotent)
        assert result1 == result2
        
        # Verify key fields match
        assert result1["call_id"] == result2["call_id"]
        assert result1["transition_point"] == result2["transition_point"]
        assert result1["part1"]["start_time"] == result2["part1"]["start_time"]


# ============================================================================
# Webhook Adapter Tests
# ============================================================================

@pytest.mark.skip(reason="Waiting for Shunya to confirm final webhook schema")
class TestWebhookAdapterSimulation:
    """Test webhook adapter with synthetic payloads."""
    
    def test_adapter_handles_complete_payload(self):
        """Test adapter with complete synthetic payload."""
        payload = make_synthetic_webhook()
        result = ShunyaWebhookAdapter.adapt(payload)
        
        assert result is not None
        assert result["shunya_job_id"] == "webhook_job_123"
        assert result["status"] == "completed"
        assert result["company_id"] == "company_abc"
    
    def test_adapter_handles_job_id_aliases(self):
        """Test adapter handles different job ID field names."""
        payload = {
            "task_id": "alias_job_123",  # Using task_id alias
            "status": "completed",
        }
        result = ShunyaWebhookAdapter.adapt(payload)
        
        assert result["shunya_job_id"] == "alias_job_123"


# ============================================================================
# Error Adapter Tests
# ============================================================================

@pytest.mark.skip(reason="Waiting for Shunya to confirm final error schema")
class TestErrorAdapterSimulation:
    """Test error adapter with synthetic payloads."""
    
    def test_adapter_handles_error_envelope(self):
        """Test adapter with structured error envelope."""
        payload = make_synthetic_error()
        result = ShunyaErrorAdapter.adapt(payload)
        
        assert result is not None
        assert result["code"] == "TRANSCRIPTION_FAILED"
        assert result["retryable"] is True
    
    def test_adapter_handles_string_error(self):
        """Test adapter with string error."""
        payload = "Simple error message"
        result = ShunyaErrorAdapter.adapt(payload)
        
        assert result is not None
        assert result["code"] == "UNKNOWN_ERROR"
        assert result["message"] == "Simple error message"


# ============================================================================
# Mapping Function Tests
# ============================================================================

@pytest.mark.skip(reason="Waiting for Shunya to confirm final enum values")
class TestMappingFunctionsSimulation:
    """Test mapping functions with synthetic values."""
    
    def test_csr_outcome_mapping(self):
        """Test CSR outcome to LeadStatus mapping."""
        # Known value
        result = map_shunya_csr_outcome_to_lead_status("qualified_and_booked")
        assert result is not None
        
        # Unknown value
        result = map_shunya_csr_outcome_to_lead_status("unknown_value")
        assert result is None  # Should return None gracefully
    
    def test_visit_outcome_mapping(self):
        """Test visit outcome to AppointmentOutcome mapping."""
        result = map_shunya_visit_outcome_to_appointment_outcome("won")
        assert result is not None
        assert result.value == "won"
        
        # Unknown value should default to PENDING
        result = map_shunya_visit_outcome_to_appointment_outcome("unknown")
        assert result is not None
        assert result.value == "pending"
    
    def test_objection_label_normalization(self):
        """Test objection label normalization."""
        result = normalize_shunya_objection_label("price")
        assert result == "price"
        
        # Unknown label should pass through
        result = normalize_shunya_objection_label("unknown_category")
        assert result == "unknown_category"  # Pass through
    
    def test_action_assignee_mapping(self):
        """Test action assignee type mapping."""
        result = map_shunya_action_to_task_assignee("csr", context="csr_call")
        assert result.value == "csr"
        
        # Unknown type should default
        result = map_shunya_action_to_task_assignee("unknown", context="csr_call")
        assert result.value == "csr"  # Default for CSR context
    
    def test_pending_action_free_string_handling(self):
        """Test that free-string action types are handled gracefully (aligned with final Shunya contract)."""
        from app.services.shunya_adapters_v2 import ShunyaCSRCallAdapter
        from app.schemas.shunya_contracts import ShunyaPendingAction
        
        # Known pattern (should map to internal type)
        known_action = ShunyaPendingAction(
            action="Follow up tomorrow",
            action_type="follow_up_tomorrow",  # Known pattern
            priority="high",
        )
        
        # Random/free-string action (should handle gracefully)
        random_action = ShunyaPendingAction(
            action="Custom action description",
            action_type="weird_custom_action_999",  # Unknown free-string
            priority="medium",
        )
        
        # Test with known action
        known_result = ShunyaCSRCallAdapter._adapt_pending_actions([known_action], "csr_call")
        assert len(known_result) == 1
        assert known_result[0]["action_type"] == "follow_up_tomorrow"  # Preserved
        assert known_result[0].get("mapped_assignee") is not None  # Should map to assignee
        
        # Test with unknown/free-string action (should not crash)
        random_result = ShunyaCSRCallAdapter._adapt_pending_actions([random_action], "csr_call")
        assert len(random_result) == 1
        assert random_result[0]["action_type"] == "weird_custom_action_999"  # Preserved original
        # Should have graceful mapping without exceptions
        assert random_result[0].get("mapped_assignee") is not None  # Should map to default


# ============================================================================
# Integration Flow Tests (End-to-End)
# ============================================================================

@pytest.mark.skip(reason="Waiting for Shunya to confirm all schemas")
class TestEndToEndAdapterFlows:
    """Test end-to-end adapter flows with synthetic payloads."""
    
    def test_csr_call_complete_flow(self):
        """Test complete CSR call analysis flow."""
        # Simulate: Shunya response → Adapter → Otto format
        raw_response = make_synthetic_csr_analysis()
        adapted = ShunyaCSRCallAdapter.adapt(raw_response)
        
        # Verify structure is correct
        assert adapted is not None
        assert "lead_status" in adapted
        assert "pending_actions" in adapted
        
        # Verify mappings worked
        assert adapted["lead_status"] is not None
    
    def test_visit_complete_flow(self):
        """Test complete visit analysis flow."""
        raw_response = make_synthetic_visit_analysis()
        adapted = ShunyaVisitAdapter.adapt(raw_response)
        
        assert adapted is not None
        assert adapted["appointment_outcome"] == "won"
        assert adapted["lead_status"] == "closed_won"  # Won → closed_won
    
    def test_webhook_to_analysis_flow(self):
        """Test webhook → analysis extraction flow."""
        webhook_payload = make_synthetic_webhook()
        webhook_result = ShunyaWebhookAdapter.adapt(webhook_payload)
        
        # Extract result and adapt
        if webhook_result.get("result"):
            analysis_result = ShunyaCSRCallAdapter.adapt(webhook_result["result"])
            assert analysis_result is not None


# ============================================================================
# Edge Case Tests
# ============================================================================

@pytest.mark.skip(reason="Waiting for Shunya to confirm schemas")
class TestAdapterEdgeCases:
    """Test adapter edge cases and error handling."""
    
    def test_empty_payload(self):
        """Test adapter with empty payload."""
        result = ShunyaCSRCallAdapter.adapt({})
        assert result is not None  # Should not crash
    
    def test_none_payload(self):
        """Test adapter with None payload."""
        result = ShunyaCSRCallAdapter.adapt(None)
        assert result is not None  # Should handle gracefully
    
    def test_malformed_nested_structure(self):
        """Test adapter with malformed nested structure."""
        payload = {
            "qualification": "not_a_dict",  # Should be dict
            "objections": None,  # Should be dict or list
        }
        result = ShunyaCSRCallAdapter.adapt(payload)
        assert result is not None  # Should not crash





These tests use synthetic test payloads (not real Shunya data) to ensure
all adapter methods can run end-to-end with placeholder data.

All tests are marked as `xfail` or `skip` until Shunya provides final schemas.

These tests verify:
- Adapters handle missing fields gracefully
- Adapters handle unknown enums gracefully
- Adapters are idempotent
- Adapters produce consistent outputs
"""
import pytest
from typing import Dict, Any
from datetime import datetime

from app.services.shunya_adapters_v2 import (
    ShunyaCSRCallAdapter,
    ShunyaVisitAdapter,
    ShunyaSegmentationAdapter,
    ShunyaWebhookAdapter,
    ShunyaErrorAdapter,
)
from app.services.shunya_mappings import (
    map_shunya_csr_outcome_to_lead_status,
    map_shunya_visit_outcome_to_appointment_outcome,
    normalize_shunya_objection_label,
    map_shunya_action_to_task_assignee,
)


# ============================================================================
# Synthetic Test Payloads
# ============================================================================

def make_synthetic_csr_analysis() -> Dict[str, Any]:
    """Create synthetic CSR call analysis payload."""
    return {
        "job_id": "test_job_123",
        "call_id": 456,
        "qualification": {
            "qualification_status": "qualified_and_booked",
            "bant_scores": {
                "budget": 0.8,
                "authority": 0.9,
                "need": 0.7,
                "timeline": 0.6,
            },
            "overall_score": 0.75,
            "confidence_score": 0.85,
            "decision_makers": ["John Doe"],
            "urgency_signals": ["Needs roof repair ASAP"],
            "budget_indicators": ["Mentioned $15k budget"],
        },
        "objections": {
            "objections": [
                {
                    "objection_text": "Price seems high",
                    "objection_label": "price",
                    "severity": "medium",
                    "overcome": False,
                }
            ],
            "total_objections": 1,
        },
        "compliance": {
            "stages_followed": ["greeting", "qualification", "closing"],
            "stages_missed": ["presentation"],
            "compliance_score": 0.75,
        },
        "summary": {
            "summary": "Customer interested in roof repair, needs quote",
            "key_points": ["Budget: $15k", "Urgent need"],
            "next_steps": ["Send quote", "Follow up tomorrow"],
        },
        "sentiment_score": 0.6,
        "pending_actions": [
            {
                "action": "Send quote",
                "action_type": "follow_up_tomorrow",  # Free-string action type
                "priority": "high",
                "due_at": "2025-11-25T10:00:00Z",
                "assignee_type": "csr",
            }
        ],
        "missed_opportunities": [],
        "entities": {
            "address": "123 Main St",
            "phone_number": "555-1234",
        },
        "analyzed_at": "2025-11-24T12:00:00Z",
        "confidence_score": 0.85,
    }


def make_synthetic_visit_analysis() -> Dict[str, Any]:
    """Create synthetic visit analysis payload."""
    return {
        "job_id": "test_visit_job_456",
        "appointment_id": "appt_789",
        "outcome": "won",
        "qualification": {
            "qualification_status": "qualified_and_booked",
        },
        "objections": {
            "objections": [],
            "total_objections": 0,
        },
        "sentiment_score": 0.8,
        "visit_actions": [
            {
                "action": "Send contract",
                "assignee_type": "rep",
            }
        ],
        "missed_opportunities": [
            {
                "opportunity_text": "Could have upsold gutter cleaning",
                "opportunity_type": "upsell",
                "severity": "medium",
            }
        ],
        "deal_size": 15000.0,
        "deal_currency": "USD",
        "analyzed_at": "2025-11-24T14:00:00Z",
    }


def make_synthetic_segmentation() -> Dict[str, Any]:
    """
    Create synthetic segmentation payload aligned with final Shunya contract.
    
    New structure:
    {
        "success": true,
        "call_id": 999,
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
    return {
        "success": True,
        "call_id": 999,
        "job_id": "test_seg_job_789",  # Legacy field for backward compatibility
        "part1": {
            "start_time": 0,
            "end_time": 240,
            "duration": 240,
            "content": "Introduction, agenda setting, discovery, rapport building",
            "key_points": ["Introduction", "Agenda setting", "Discovery questions"],
            # Legacy fields for backward compatibility
            "transcript": "Part 1 transcript...",
            "summary": "Rapport building and agenda setting",
            "sentiment_score": 0.7,
            "key_topics": ["Small talk", "Agenda"],
            "duration_seconds": 300,
        },
        "part2": {
            "start_time": 240,
            "end_time": 420,
            "duration": 180,
            "content": "Presentation, proposal, closing, next steps",
            "key_points": ["Presentation of solution", "Scheduling of appointment"],
            # Legacy fields for backward compatibility
            "transcript": "Part 2 transcript...",
            "summary": "Proposal and closing",
            "sentiment_score": 0.8,
            "key_topics": ["Proposal", "Pricing"],
            "duration_seconds": 600,
        },
        "transition_point": 240,
        "transition_indicators": ["Scheduling of appointment", "Confirmation of details"],
        "segmentation_confidence": 0.8,
        "meeting_structure_score": 4,
        "call_type": "sales_appointment",
        "created_at": "2025-11-24T15:00:00Z",
        # Legacy fields for backward compatibility
        "outcome": "won",
        "analyzed_at": "2025-11-24T15:00:00Z",
    }


def make_synthetic_webhook() -> Dict[str, Any]:
    """Create synthetic webhook payload."""
    return {
        "shunya_job_id": "webhook_job_123",
        "status": "completed",
        "company_id": "company_abc",
        "result": make_synthetic_csr_analysis(),
        "timestamp": "2025-11-24T16:00:00Z",
    }


def make_synthetic_error() -> Dict[str, Any]:
    """Create synthetic error payload aligned with canonical error envelope."""
    return {
        "success": False,
        "error": {
            "error_code": "TRANSCRIPTION_FAILED",
            "error_type": "processing_error",
            "message": "Audio quality too poor",
            "retryable": True,
            "details": {},
            "timestamp": "2025-11-28T10:15:42.123Z",
            "request_id": "error_req_123",
        }
    }


# ============================================================================
# CSR Call Adapter Tests
# ============================================================================

@pytest.mark.skip(reason="Waiting for Shunya to confirm final CSR analysis schema")
class TestCSRCallAdapterSimulation:
    """Test CSR call adapter with synthetic payloads."""
    
    def test_adapter_handles_complete_payload(self):
        """Test adapter with complete synthetic payload."""
        payload = make_synthetic_csr_analysis()
        result = ShunyaCSRCallAdapter.adapt(payload)
        
        assert result is not None
        assert result["job_id"] == "test_job_123"
        assert result["lead_status"] is not None  # Should map to LeadStatus
        assert "qualification" in result
        assert "objections" in result
    
    def test_adapter_handles_missing_fields(self):
        """Test adapter with missing optional fields."""
        payload = {
            "job_id": "test_job_incomplete",
            "qualification": {
                "qualification_status": "qualified_and_booked",
            },
            # Missing objections, compliance, summary, etc.
        }
        result = ShunyaCSRCallAdapter.adapt(payload)
        
        assert result is not None
        assert result["objections"] == {"objections": [], "total_objections": 0}
        assert result["compliance"] is not None
        assert result["summary"] is not None
    
    def test_adapter_handles_unknown_outcome(self):
        """Test adapter with unknown outcome enum."""
        payload = {
            "job_id": "test_unknown_outcome",
            "qualification": {
                "qualification_status": "unknown_shunya_value",  # Unknown enum
            },
        }
        result = ShunyaCSRCallAdapter.adapt(payload)
        
        # Should not break, should handle gracefully
        assert result is not None
        assert result["lead_status"] is None  # Unknown → None (graceful)
    
    def test_adapter_idempotency(self):
        """Test that adapter produces same output for same input."""
        payload = make_synthetic_csr_analysis()
        
        result1 = ShunyaCSRCallAdapter.adapt(payload)
        result2 = ShunyaCSRCallAdapter.adapt(payload)
        
        # Should be identical (idempotent)
        assert result1 == result2


# ============================================================================
# Visit Adapter Tests
# ============================================================================

@pytest.mark.skip(reason="Waiting for Shunya to confirm final visit analysis schema")
class TestVisitAdapterSimulation:
    """Test visit adapter with synthetic payloads."""
    
    def test_adapter_handles_complete_payload(self):
        """Test adapter with complete synthetic payload."""
        payload = make_synthetic_visit_analysis()
        result = ShunyaVisitAdapter.adapt(payload)
        
        assert result is not None
        assert result["appointment_outcome"] == "won"
        assert result["deal_size"] == 15000.0
    
    def test_adapter_handles_missing_outcome(self):
        """Test adapter with missing outcome."""
        payload = {
            "job_id": "test_no_outcome",
            # Missing outcome field
        }
        result = ShunyaVisitAdapter.adapt(payload)
        
        assert result is not None
        assert result["outcome"] == "pending"  # Should default to pending
    
    def test_adapter_maps_outcome_to_appointment_status(self):
        """Test that outcome maps correctly to appointment status."""
        payload = make_synthetic_visit_analysis()
        result = ShunyaVisitAdapter.adapt(payload)
        
        assert result["appointment_outcome"] == "won"
        assert result["appointment_status"] == "completed"  # Won → completed


# ============================================================================
# Segmentation Adapter Tests
# ============================================================================

class TestSegmentationAdapterSimulation:
    """Test segmentation adapter with synthetic payloads (aligned with final Shunya contract)."""
    
    def test_adapter_handles_new_segmentation_structure(self):
        """Test adapter with new segmentation structure (content, key_points, etc.)."""
        payload = make_synthetic_segmentation()
        result = ShunyaSegmentationAdapter.adapt(payload)
        
        assert result is not None
        assert result["success"] is True
        assert result["call_id"] == 999
        assert "part1" in result
        assert "part2" in result
        assert result["transition_point"] == 240
        assert result["segmentation_confidence"] == 0.8
        assert result["transition_indicators"] == ["Scheduling of appointment", "Confirmation of details"]
        assert result["meeting_structure_score"] == 4
        assert result["call_type"] == "sales_appointment"
        
        # Verify part1 structure
        part1 = result["part1"]
        assert part1["start_time"] == 0
        assert part1["end_time"] == 240
        assert part1["duration"] == 240
        assert "Introduction, agenda setting" in part1.get("content", "")
        assert "Introduction" in part1.get("key_points", [])
    
    def test_adapter_handles_missing_parts(self):
        """Test adapter with missing part2 (graceful degradation)."""
        payload = {
            "success": True,
            "call_id": 999,
            "job_id": "test_partial",
            "part1": {
                "start_time": 0,
                "end_time": 120,
                "duration": 120,
                "content": "Part 1 only",
                "key_points": ["Introduction"],
            },
            # Missing part2
        }
        result = ShunyaSegmentationAdapter.adapt(payload)
        
        assert result is not None
        assert "part1" in result
        assert result["part2"] == {}  # Should default to empty dict
        assert result["call_id"] == 999
    
    def test_adapter_handles_missing_optional_fields(self):
        """Test adapter handles missing optional fields gracefully."""
        payload = {
            "success": True,
            "call_id": 999,
            "part1": {
                "content": "Part 1 content",
                # Missing start_time, end_time, duration, key_points
            },
            "part2": {
                "content": "Part 2 content",
            },
            # Missing transition_indicators, call_type, meeting_structure_score
        }
        result = ShunyaSegmentationAdapter.adapt(payload)
        
        # Should not crash
        assert result is not None
        assert "part1" in result
        assert "part2" in result
        # Optional fields should be None or empty
        assert result.get("transition_indicators") is None or result.get("transition_indicators") == []
    
    def test_adapter_idempotency(self):
        """Test that adapter produces same output for same input (idempotent)."""
        payload = make_synthetic_segmentation()
        
        result1 = ShunyaSegmentationAdapter.adapt(payload)
        result2 = ShunyaSegmentationAdapter.adapt(payload)
        
        # Should be identical (idempotent)
        assert result1 == result2
        
        # Verify key fields match
        assert result1["call_id"] == result2["call_id"]
        assert result1["transition_point"] == result2["transition_point"]
        assert result1["part1"]["start_time"] == result2["part1"]["start_time"]


# ============================================================================
# Webhook Adapter Tests
# ============================================================================

@pytest.mark.skip(reason="Waiting for Shunya to confirm final webhook schema")
class TestWebhookAdapterSimulation:
    """Test webhook adapter with synthetic payloads."""
    
    def test_adapter_handles_complete_payload(self):
        """Test adapter with complete synthetic payload."""
        payload = make_synthetic_webhook()
        result = ShunyaWebhookAdapter.adapt(payload)
        
        assert result is not None
        assert result["shunya_job_id"] == "webhook_job_123"
        assert result["status"] == "completed"
        assert result["company_id"] == "company_abc"
    
    def test_adapter_handles_job_id_aliases(self):
        """Test adapter handles different job ID field names."""
        payload = {
            "task_id": "alias_job_123",  # Using task_id alias
            "status": "completed",
        }
        result = ShunyaWebhookAdapter.adapt(payload)
        
        assert result["shunya_job_id"] == "alias_job_123"


# ============================================================================
# Error Adapter Tests
# ============================================================================

@pytest.mark.skip(reason="Waiting for Shunya to confirm final error schema")
class TestErrorAdapterSimulation:
    """Test error adapter with synthetic payloads."""
    
    def test_adapter_handles_error_envelope(self):
        """Test adapter with structured error envelope."""
        payload = make_synthetic_error()
        result = ShunyaErrorAdapter.adapt(payload)
        
        assert result is not None
        assert result["code"] == "TRANSCRIPTION_FAILED"
        assert result["retryable"] is True
    
    def test_adapter_handles_string_error(self):
        """Test adapter with string error."""
        payload = "Simple error message"
        result = ShunyaErrorAdapter.adapt(payload)
        
        assert result is not None
        assert result["code"] == "UNKNOWN_ERROR"
        assert result["message"] == "Simple error message"


# ============================================================================
# Mapping Function Tests
# ============================================================================

@pytest.mark.skip(reason="Waiting for Shunya to confirm final enum values")
class TestMappingFunctionsSimulation:
    """Test mapping functions with synthetic values."""
    
    def test_csr_outcome_mapping(self):
        """Test CSR outcome to LeadStatus mapping."""
        # Known value
        result = map_shunya_csr_outcome_to_lead_status("qualified_and_booked")
        assert result is not None
        
        # Unknown value
        result = map_shunya_csr_outcome_to_lead_status("unknown_value")
        assert result is None  # Should return None gracefully
    
    def test_visit_outcome_mapping(self):
        """Test visit outcome to AppointmentOutcome mapping."""
        result = map_shunya_visit_outcome_to_appointment_outcome("won")
        assert result is not None
        assert result.value == "won"
        
        # Unknown value should default to PENDING
        result = map_shunya_visit_outcome_to_appointment_outcome("unknown")
        assert result is not None
        assert result.value == "pending"
    
    def test_objection_label_normalization(self):
        """Test objection label normalization."""
        result = normalize_shunya_objection_label("price")
        assert result == "price"
        
        # Unknown label should pass through
        result = normalize_shunya_objection_label("unknown_category")
        assert result == "unknown_category"  # Pass through
    
    def test_action_assignee_mapping(self):
        """Test action assignee type mapping."""
        result = map_shunya_action_to_task_assignee("csr", context="csr_call")
        assert result.value == "csr"
        
        # Unknown type should default
        result = map_shunya_action_to_task_assignee("unknown", context="csr_call")
        assert result.value == "csr"  # Default for CSR context
    
    def test_pending_action_free_string_handling(self):
        """Test that free-string action types are handled gracefully (aligned with final Shunya contract)."""
        from app.services.shunya_adapters_v2 import ShunyaCSRCallAdapter
        from app.schemas.shunya_contracts import ShunyaPendingAction
        
        # Known pattern (should map to internal type)
        known_action = ShunyaPendingAction(
            action="Follow up tomorrow",
            action_type="follow_up_tomorrow",  # Known pattern
            priority="high",
        )
        
        # Random/free-string action (should handle gracefully)
        random_action = ShunyaPendingAction(
            action="Custom action description",
            action_type="weird_custom_action_999",  # Unknown free-string
            priority="medium",
        )
        
        # Test with known action
        known_result = ShunyaCSRCallAdapter._adapt_pending_actions([known_action], "csr_call")
        assert len(known_result) == 1
        assert known_result[0]["action_type"] == "follow_up_tomorrow"  # Preserved
        assert known_result[0].get("mapped_assignee") is not None  # Should map to assignee
        
        # Test with unknown/free-string action (should not crash)
        random_result = ShunyaCSRCallAdapter._adapt_pending_actions([random_action], "csr_call")
        assert len(random_result) == 1
        assert random_result[0]["action_type"] == "weird_custom_action_999"  # Preserved original
        # Should have graceful mapping without exceptions
        assert random_result[0].get("mapped_assignee") is not None  # Should map to default


# ============================================================================
# Integration Flow Tests (End-to-End)
# ============================================================================

@pytest.mark.skip(reason="Waiting for Shunya to confirm all schemas")
class TestEndToEndAdapterFlows:
    """Test end-to-end adapter flows with synthetic payloads."""
    
    def test_csr_call_complete_flow(self):
        """Test complete CSR call analysis flow."""
        # Simulate: Shunya response → Adapter → Otto format
        raw_response = make_synthetic_csr_analysis()
        adapted = ShunyaCSRCallAdapter.adapt(raw_response)
        
        # Verify structure is correct
        assert adapted is not None
        assert "lead_status" in adapted
        assert "pending_actions" in adapted
        
        # Verify mappings worked
        assert adapted["lead_status"] is not None
    
    def test_visit_complete_flow(self):
        """Test complete visit analysis flow."""
        raw_response = make_synthetic_visit_analysis()
        adapted = ShunyaVisitAdapter.adapt(raw_response)
        
        assert adapted is not None
        assert adapted["appointment_outcome"] == "won"
        assert adapted["lead_status"] == "closed_won"  # Won → closed_won
    
    def test_webhook_to_analysis_flow(self):
        """Test webhook → analysis extraction flow."""
        webhook_payload = make_synthetic_webhook()
        webhook_result = ShunyaWebhookAdapter.adapt(webhook_payload)
        
        # Extract result and adapt
        if webhook_result.get("result"):
            analysis_result = ShunyaCSRCallAdapter.adapt(webhook_result["result"])
            assert analysis_result is not None


# ============================================================================
# Edge Case Tests
# ============================================================================

@pytest.mark.skip(reason="Waiting for Shunya to confirm schemas")
class TestAdapterEdgeCases:
    """Test adapter edge cases and error handling."""
    
    def test_empty_payload(self):
        """Test adapter with empty payload."""
        result = ShunyaCSRCallAdapter.adapt({})
        assert result is not None  # Should not crash
    
    def test_none_payload(self):
        """Test adapter with None payload."""
        result = ShunyaCSRCallAdapter.adapt(None)
        assert result is not None  # Should handle gracefully
    
    def test_malformed_nested_structure(self):
        """Test adapter with malformed nested structure."""
        payload = {
            "qualification": "not_a_dict",  # Should be dict
            "objections": None,  # Should be dict or list
        }
        result = ShunyaCSRCallAdapter.adapt(payload)
        assert result is not None  # Should not crash



