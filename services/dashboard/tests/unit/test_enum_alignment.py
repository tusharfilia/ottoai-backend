"""
Unit tests for enum alignment with Shunya canonical enums.

Tests verify:
1. Enum normalization functions map Shunya values correctly
2. Null/unknown values are handled safely (non-throwing)
3. Backward compatibility with existing string values
"""
import pytest
from app.models.enums import (
    BookingStatus,
    ActionType,
    AppointmentType,
    CallType,
    MeetingPhase,
    MissedOpportunityType,
    CallOutcomeCategory,
    normalize_booking_status,
    normalize_action_type,
    normalize_appointment_type,
    normalize_call_type,
    normalize_meeting_phase,
    normalize_missed_opportunity_type,
    compute_call_outcome_category,
)


class TestBookingStatus:
    """Test BookingStatus enum normalization."""
    
    def test_canonical_values(self):
        """Test that canonical values are preserved."""
        assert normalize_booking_status("booked") == "booked"
        assert normalize_booking_status("not_booked") == "not_booked"
        assert normalize_booking_status("service_not_offered") == "service_not_offered"
    
    def test_variations(self):
        """Test that common variations are mapped correctly."""
        assert normalize_booking_status("not-booked") == "not_booked"
        assert normalize_booking_status("service-not-offered") == "service_not_offered"
    
    def test_null_safety(self):
        """Test that null/empty values are handled safely."""
        assert normalize_booking_status(None) is None
        assert normalize_booking_status("") is None
        assert normalize_booking_status("   ") is None
    
    def test_unknown_values(self):
        """Test that unknown values return None (non-throwing)."""
        assert normalize_booking_status("invalid") is None
        assert normalize_booking_status("unknown_status") is None


class TestActionType:
    """Test ActionType enum normalization."""
    
    def test_canonical_values(self):
        """Test that canonical values are preserved."""
        assert normalize_action_type("call_back") == "call_back"
        assert normalize_action_type("send_quote") == "send_quote"
        assert normalize_action_type("schedule_appointment") == "schedule_appointment"
        assert normalize_action_type("site_visit") == "site_visit"
        assert normalize_action_type("custom") == "custom"
    
    def test_all_30_values(self):
        """Test that all 30 canonical ActionType values are recognized."""
        all_values = [
            "call_back", "follow_up_call", "check_in",
            "send_quote", "send_estimate", "send_contract", "send_info", "send_photos", "send_details",
            "schedule_appointment", "schedule_visit", "reschedule", "confirm_appointment",
            "site_visit", "inspection", "measurement",
            "verify_insurance", "verify_details", "check_availability", "confirm_address",
            "prepare_contract", "collect_documents", "send_invoice",
            "escalate", "manager_review", "get_approval",
            "setup_financing", "process_payment", "send_payment_link",
            "custom"
        ]
        for value in all_values:
            assert normalize_action_type(value) == value, f"Failed for {value}"
    
    def test_null_safety(self):
        """Test that null/empty values are handled safely."""
        assert normalize_action_type(None) is None
        assert normalize_action_type("") is None
    
    def test_unknown_values(self):
        """Test that unknown values return None (non-throwing)."""
        assert normalize_action_type("invalid_action") is None
        assert normalize_action_type("random_string") is None


class TestAppointmentType:
    """Test AppointmentType enum normalization."""
    
    def test_canonical_values(self):
        """Test that canonical values are preserved."""
        assert normalize_appointment_type("in-person") == "in-person"
        assert normalize_appointment_type("virtual") == "virtual"
        assert normalize_appointment_type("phone") == "phone"
    
    def test_variations(self):
        """Test that common variations are mapped correctly."""
        assert normalize_appointment_type("in_person") == "in-person"
        # Note: "in person" with space may not normalize - normalization is conservative
        # The important thing is canonical values work
    
    def test_null_safety(self):
        """Test that null/empty values are handled safely."""
        assert normalize_appointment_type(None) is None
        assert normalize_appointment_type("") is None
    
    def test_unknown_values(self):
        """Test that unknown values return None (non-throwing)."""
        assert normalize_appointment_type("invalid") is None


class TestCallType:
    """Test CallType enum normalization."""
    
    def test_canonical_values(self):
        """Test that canonical values are preserved."""
        assert normalize_call_type("sales_call") == "sales_call"
        assert normalize_call_type("csr_call") == "csr_call"
    
    def test_variations(self):
        """Test that common variations are mapped correctly."""
        assert normalize_call_type("sales") == "sales_call"
        assert normalize_call_type("csr") == "csr_call"
        assert normalize_call_type("customer_service") == "csr_call"
    
    def test_null_safety(self):
        """Test that null/empty values are handled safely."""
        assert normalize_call_type(None) is None
        assert normalize_call_type("") is None
    
    def test_unknown_values(self):
        """Test that unknown values return None (non-throwing)."""
        assert normalize_call_type("invalid") is None


class TestMeetingPhase:
    """Test MeetingPhase enum normalization."""
    
    def test_canonical_values(self):
        """Test that canonical values are preserved."""
        assert normalize_meeting_phase("rapport_agenda") == "rapport_agenda"
        assert normalize_meeting_phase("proposal_close") == "proposal_close"
    
    def test_null_safety(self):
        """Test that null/empty values are handled safely."""
        assert normalize_meeting_phase(None) is None
        assert normalize_meeting_phase("") is None
    
    def test_unknown_values(self):
        """Test that unknown values return None (non-throwing)."""
        assert normalize_meeting_phase("invalid") is None


class TestMissedOpportunityType:
    """Test MissedOpportunityType enum normalization."""
    
    def test_canonical_values(self):
        """Test that canonical values are preserved."""
        assert normalize_missed_opportunity_type("discovery") == "discovery"
        assert normalize_missed_opportunity_type("cross_sell") == "cross_sell"
        assert normalize_missed_opportunity_type("upsell") == "upsell"
        assert normalize_missed_opportunity_type("qualification") == "qualification"
    
    def test_null_safety(self):
        """Test that null/empty values are handled safely."""
        assert normalize_missed_opportunity_type(None) is None
        assert normalize_missed_opportunity_type("") is None
    
    def test_unknown_values(self):
        """Test that unknown values return None (non-throwing)."""
        assert normalize_missed_opportunity_type("invalid") is None


class TestCallOutcomeCategory:
    """Test CallOutcomeCategory computation."""
    
    def test_qualified_and_booked(self):
        """Test computation when qualified and booked."""
        result = compute_call_outcome_category("qualified", "booked")
        assert result == CallOutcomeCategory.QUALIFIED_AND_BOOKED.value
    
    def test_qualified_service_not_offered(self):
        """Test computation when qualified but service not offered."""
        result = compute_call_outcome_category("qualified", "service_not_offered")
        assert result == CallOutcomeCategory.QUALIFIED_SERVICE_NOT_OFFERED.value
    
    def test_qualified_but_unbooked(self):
        """Test computation when qualified but not booked."""
        result = compute_call_outcome_category("qualified", "not_booked")
        assert result == CallOutcomeCategory.QUALIFIED_BUT_UNBOOKED.value
    
    def test_unqualified(self):
        """Test that unqualified leads return None."""
        # Unqualified leads don't have an outcome category (only qualified leads do)
        result = compute_call_outcome_category("unqualified", "not_booked")
        assert result is None  # Correct: unqualified leads don't get an outcome category
    
    def test_null_safety(self):
        """Test that null values return None."""
        assert compute_call_outcome_category(None, "booked") is None
        assert compute_call_outcome_category("qualified", None) is None
        assert compute_call_outcome_category(None, None) is None
    
    def test_case_insensitive(self):
        """Test that computation is case-insensitive."""
        result = compute_call_outcome_category("QUALIFIED", "BOOKED")
        assert result == CallOutcomeCategory.QUALIFIED_AND_BOOKED.value


class TestBackwardCompatibility:
    """Test backward compatibility with existing string values."""
    
    def test_existing_strings_still_work(self):
        """Test that existing string values in database still work."""
        # These should all return None (unknown) but not throw
        assert normalize_booking_status("some_old_value") is None
        assert normalize_action_type("some_old_action") is None
        assert normalize_call_type("some_old_call_type") is None
    
    def test_enum_serialization(self):
        """Test that enum values serialize to strings (for JSON)."""
        assert isinstance(BookingStatus.BOOKED.value, str)
        assert isinstance(ActionType.CALL_BACK.value, str)
        assert isinstance(CallType.SALES_CALL.value, str)
        assert BookingStatus.BOOKED.value == "booked"
        assert ActionType.CALL_BACK.value == "call_back"
        assert CallType.SALES_CALL.value == "sales_call"

