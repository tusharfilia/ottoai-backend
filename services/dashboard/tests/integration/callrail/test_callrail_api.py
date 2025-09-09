import pytest
from unittest.mock import MagicMock
from app.routes.call_rail import pre_call_webhook, call_complete_webhook
from app.models import call, company
from sqlalchemy.orm import Session
from datetime import datetime

@pytest.fixture
def mock_db_session():
    """Fixture to mock the database session."""
    session = MagicMock(spec=Session)
    return session

@pytest.fixture
def mock_company():
    """Fixture to mock a company."""
    return company.Company(id=1, name="Test Company", phone_number="+1234567890")

@pytest.fixture
def mock_call():
    """Fixture to mock a call."""
    return call.Call(
        id=1,
        phone_number="+1987654321",
        company_id=1,
        created_at=datetime.utcnow(),
        missed_call=False,
    )

def test_pre_call_webhook_company_not_found(mock_db_session):
    """Test the pre_call_webhook function when the company is not found."""
    mock_db_session.query.return_value.filter_by.return_value.first.return_value = None
    params = {"trackingnum": "+0", "callernum": "+1987654321", "answered": "true"}
    pre_call_webhook(params, db=mock_db_session)


