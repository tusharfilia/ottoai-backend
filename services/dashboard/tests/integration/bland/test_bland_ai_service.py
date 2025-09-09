import pytest
from app.services.bland_ai import BlandAI
from unittest.mock import MagicMock

@pytest.fixture
def bland_ai_service():
    return BlandAI()

def test_make_sales_followup_call(bland_ai_service):
    bland_ai_service.make_call = MagicMock(return_value={"status": "success", "call_id": "12345"})
    customer_info = {
        "name": "John Doe",
        "phone": "+1234567890",
        "address": "123 Main St",
        "quote_date": "2023-10-15T10:00:00Z",
        "company_name": "Test Company"
    }
    response = bland_ai_service.make_sales_followup_call(
        customer_info=customer_info,
        sales_rep_phone="+1987654321",
        original_call_id=1,
        scheduled_call_id=2,
        start_time=None,
        db=None
    )
    assert response["status"] == "success"
    assert response["call_id"] == "12345"

def test_make_manager_call(bland_ai_service):
    bland_ai_service.make_call = MagicMock(return_value={"status": "success", "call_id": "67890"})
    customer_info = {
        "unassigned_calls": [
            {"name": "Jane Doe", "phone": "+1234567890", "address": "456 Elm St", "quote_date": "2023-10-16T15:00:00Z"}
        ],
        "total_unassigned": 1
    }
    response = bland_ai_service.make_manager_call(
        sales_rep_id=None,
        db=None,
        customer_info=customer_info,
        sales_rep_name=None,
        manager_name="Manager Name",
        start_time=None
    )
    assert response["status"] == "success"
    assert response["call_id"] == "67890"

def test_make_followup_call(bland_ai_service):
    bland_ai_service.make_call = MagicMock(return_value={"status": "success", "call_id": "54321"})
    request_data = {
        "name": "John Doe",
        "phone": "+1234567890",
        "address": "123 Main St",
        "quote_date": "2023-10-15T10:00:00Z",
        "company_name": "Test Company"
    }
    response = bland_ai_service.make_followup_call(
        customer_phone="+1234567890",
        request_data=request_data,
        reason_for_lost_sale="Price too high",
        call_record_id=1,
        scheduled_call_id=2,
        db=None,
        start_time=None
    )
    assert response["status"] == "success"
    assert response["call_id"] == "54321"

def test_analyze_call(bland_ai_service):
    bland_ai_service.analyze_call = MagicMock(return_value={"analysis": "Call analyzed successfully"})
    response = bland_ai_service.analyze_call(
        call_id="12345",
        questions=["What was the customer's main concern?"],
        goal="Understand customer objections"
    )
    assert response["analysis"] == "Call analyzed successfully"

def test_schedule_call(bland_ai_service):
    """Test scheduling a call."""
    bland_ai_service.make_call = MagicMock(return_value={"status": "success", "call_id": "11111"})
    response = bland_ai_service.make_call(
        phone_number="+1234567890",
        pathway="schedule_pathway",
        start_time="2025-04-02T10:00:00Z",
        metadata={"action": "schedule"}
    )
    assert response["status"] == "success"
    assert response["call_id"] == "11111"

def test_cancel_call(bland_ai_service):
    """Test canceling a call."""
    bland_ai_service.make_call = MagicMock(return_value={"status": "success", "call_id": "22222"})
    response = bland_ai_service.make_call(
        phone_number="+1234567890",
        pathway="cancel_pathway",
        metadata={"action": "cancel"}
    )
    assert response["status"] == "success"
    assert response["call_id"] == "22222"

def test_reschedule_call(bland_ai_service):
    """Test rescheduling a call."""
    bland_ai_service.make_call = MagicMock(return_value={"status": "success", "call_id": "33333"})
    response = bland_ai_service.make_call(
        phone_number="+1234567890",
        pathway="reschedule_pathway",
        start_time="2025-04-03T15:00:00Z",
        metadata={"action": "reschedule"}
    )
    assert response["status"] == "success"
    assert response["call_id"] == "33333"

def test_pickup_sales_rep_call(bland_ai_service):
    """Test picking up a sales rep call."""
    bland_ai_service.make_call = MagicMock(return_value={"status": "success", "call_id": "44444"})
    response = bland_ai_service.make_call(
        phone_number="+1987654321",
        pathway="sales_rep_pathway",
        metadata={"action": "pickup_sales_rep"}
    )
    assert response["status"] == "success"
    assert response["call_id"] == "44444"

def test_pickup_customer_call(bland_ai_service):
    """Test picking up a customer call."""
    bland_ai_service.make_call = MagicMock(return_value={"status": "success", "call_id": "55555"})
    response = bland_ai_service.make_call(
        phone_number="+1234567890",
        pathway="customer_pathway",
        metadata={"action": "pickup_customer"}
    )
    assert response["status"] == "success"
    assert response["call_id"] == "55555"