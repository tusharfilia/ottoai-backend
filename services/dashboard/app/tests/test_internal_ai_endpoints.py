"""
Test suite for internal AI API endpoints.

Tests authentication, tenant isolation, and endpoint functionality.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime

from app.main import app
from app.models.call import Call
from app.models.sales_rep import SalesRep
from app.models.company import Company
from app.models.lead import Lead
from app.models.contact_card import ContactCard
from app.models.appointment import Appointment, AppointmentStatus, AppointmentOutcome
from app.models.service import Service
from app.models.user import User
from app.config import settings


@pytest.fixture
def ai_internal_token():
    """Test token for internal AI API."""
    return "test-ai-internal-token-12345"


@pytest.fixture
def company_id():
    """Test company ID."""
    return "test_company_123"


@pytest.fixture
def other_company_id():
    """Other company ID for isolation tests."""
    return "other_company_456"


@pytest.fixture
def ai_internal_headers(ai_internal_token, company_id):
    """Headers for internal AI API authentication."""
    return {
        "Authorization": f"Bearer {ai_internal_token}",
        "X-Company-Id": company_id,
    }


@pytest.fixture
def mock_ai_internal_token(ai_internal_token):
    """Mock AI_INTERNAL_TOKEN in settings."""
    with patch.object(settings, 'AI_INTERNAL_TOKEN', ai_internal_token):
        yield


@pytest.fixture
def test_company(db_session: Session, company_id):
    """Create a test company."""
    company = Company(
        id=company_id,
        name="Test Company",
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture
def test_contact_card(db_session: Session, company_id):
    """Create a test contact card."""
    contact = ContactCard(
        id="contact_123",
        company_id=company_id,
        primary_phone="+1234567890",
        secondary_phone="+0987654321",
        email="test@example.com",
        first_name="John",
        last_name="Doe",
        address="123 Main St",
        city="Test City",
        state="TS",
        postal_code="12345",
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)
    return contact


@pytest.fixture
def test_lead(db_session: Session, company_id, test_contact_card):
    """Create a test lead."""
    from app.models.lead import Lead, LeadStatus, LeadSource
    
    lead = Lead(
        id="lead_123",
        company_id=company_id,
        contact_card_id=test_contact_card.id,
        status=LeadStatus.NEW,
        source=LeadSource.INBOUND_CALL,
        priority="high",
        score=85,
    )
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)
    return lead


@pytest.fixture
def test_call(db_session: Session, company_id, test_lead, test_contact_card):
    """Create a test call."""
    call = Call(
        call_id=12345,
        company_id=company_id,
        lead_id=test_lead.id,
        contact_card_id=test_contact_card.id,
        phone_number="+1234567890",
        missed_call=False,
        booked=True,
        last_call_duration=300,  # 5 minutes
    )
    db_session.add(call)
    db_session.commit()
    db_session.refresh(call)
    return call


@pytest.fixture
def test_user(db_session: Session, company_id):
    """Create a test user."""
    user = User(
        id="user_123",
        company_id=company_id,
        email="rep@example.com",
        username="testrep",
        name="Test Rep",
        phone_number="+1111111111",
        role="rep",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_rep(db_session: Session, company_id, test_user):
    """Create a test sales rep."""
    from app.models.sales_rep import SalesRep, RecordingMode, ShiftConfigSource
    
    rep = SalesRep(
        user_id=test_user.id,
        company_id=company_id,
        recording_mode=RecordingMode.NORMAL,
        allow_location_tracking=True,
        allow_recording=True,
        shift_config_source=ShiftConfigSource.TENANT_DEFAULT,
    )
    db_session.add(rep)
    db_session.commit()
    db_session.refresh(rep)
    return rep


@pytest.fixture
def test_appointment(db_session: Session, company_id, test_lead, test_contact_card, test_rep):
    """Create a test appointment."""
    appointment = Appointment(
        id="appt_123",
        company_id=company_id,
        lead_id=test_lead.id,
        contact_card_id=test_contact_card.id,
        assigned_rep_id=test_rep.user_id,
        scheduled_start=datetime(2025, 1, 20, 10, 0, 0),
        scheduled_end=datetime(2025, 1, 20, 11, 0, 0),
        status=AppointmentStatus.SCHEDULED,
        outcome=AppointmentOutcome.PENDING,
        service_type="roofing",
        location="123 Main St",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)
    return appointment


class TestAuthFailures:
    """Test authentication failure cases."""
    
    def test_missing_authorization_header(
        self, client: TestClient, mock_ai_internal_token, company_id
    ):
        """Test that missing Authorization header returns 401."""
        response = client.get(
            f"/internal/ai/companies/{company_id}",
            headers={"X-Company-Id": company_id},
        )
        assert response.status_code == 401
        assert "Missing Authorization header" in response.json()["detail"]
    
    def test_invalid_token_format(
        self, client: TestClient, mock_ai_internal_token, company_id
    ):
        """Test that invalid token format returns 401."""
        response = client.get(
            f"/internal/ai/companies/{company_id}",
            headers={
                "Authorization": "InvalidFormat token",
                "X-Company-Id": company_id,
            },
        )
        assert response.status_code == 401
        assert "Invalid authorization format" in response.json()["detail"]
    
    def test_invalid_token(
        self, client: TestClient, mock_ai_internal_token, company_id
    ):
        """Test that invalid token returns 401."""
        response = client.get(
            f"/internal/ai/companies/{company_id}",
            headers={
                "Authorization": "Bearer wrong-token",
                "X-Company-Id": company_id,
            },
        )
        assert response.status_code == 401
        assert "Invalid authentication token" in response.json()["detail"]
    
    def test_missing_company_id_header(
        self, client: TestClient, mock_ai_internal_token, ai_internal_token
    ):
        """Test that missing X-Company-Id header returns 400."""
        response = client.get(
            "/internal/ai/companies/test_company_123",
            headers={"Authorization": f"Bearer {ai_internal_token}"},
        )
        assert response.status_code == 400
        assert "Missing X-Company-Id header" in response.json()["detail"]
    
    def test_empty_company_id_header(
        self, client: TestClient, mock_ai_internal_token, ai_internal_token
    ):
        """Test that empty X-Company-Id header returns 400."""
        response = client.get(
            "/internal/ai/companies/test_company_123",
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": "",
            },
        )
        assert response.status_code == 400
        assert "X-Company-Id header cannot be empty" in response.json()["detail"]


class TestTenantIsolation:
    """Test tenant isolation for internal AI API."""
    
    def test_company_mismatch(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        company_id,
        other_company_id,
    ):
        """Test that accessing another company returns 403."""
        response = client.get(
            f"/internal/ai/companies/{other_company_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 403
        assert "Company ID mismatch" in response.json()["detail"]
    
    def test_call_from_other_company(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        db_session: Session,
        other_company_id,
    ):
        """Test that accessing call from another company returns 404."""
        # Create call for other company
        other_call = Call(
            call_id=99999,
            company_id=other_company_id,
            phone_number="+9999999999",
        )
        db_session.add(other_call)
        db_session.commit()
        
        response = client.get(
            f"/internal/ai/calls/{other_call.call_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404
    
    def test_rep_from_other_company(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        db_session: Session,
        other_company_id,
    ):
        """Test that accessing rep from another company returns 404."""
        from app.models.sales_rep import SalesRep, RecordingMode, ShiftConfigSource
        from app.models.user import User
        
        # Create user and rep for other company
        other_user = User(
            id="other_user_123",
            company_id=other_company_id,
            email="other@example.com",
            username="otherrep",
            name="Other Rep",
            role="rep",
        )
        db_session.add(other_user)
        
        other_rep = SalesRep(
            user_id=other_user.id,
            company_id=other_company_id,
            recording_mode=RecordingMode.NORMAL,
            allow_location_tracking=True,
            allow_recording=True,
            shift_config_source=ShiftConfigSource.TENANT_DEFAULT,
        )
        db_session.add(other_rep)
        db_session.commit()
        
        response = client.get(
            f"/internal/ai/reps/{other_rep.user_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404


class TestHappyPaths:
    """Test happy path scenarios for each endpoint."""
    
    def test_get_call_metadata(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_call: Call,
    ):
        """Test GET /internal/ai/calls/{call_id} returns correct metadata."""
        response = client.get(
            f"/internal/ai/calls/{test_call.call_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["call_id"] == test_call.call_id
        assert data["company_id"] == test_call.company_id
        assert data["lead_id"] == test_call.lead_id
        assert data["contact_card_id"] == test_call.contact_card_id
        assert data["phone_number"] == test_call.phone_number
        assert data["duration_seconds"] == test_call.last_call_duration
        assert "booking_outcome" in data
    
    def test_get_rep_metadata(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_rep: SalesRep,
    ):
        """Test GET /internal/ai/reps/{rep_id} returns correct metadata."""
        response = client.get(
            f"/internal/ai/reps/{test_rep.user_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["rep_id"] == test_rep.user_id
        assert data["company_id"] == test_rep.company_id
        assert "name" in data
        assert "email" in data
        assert "active" in data
    
    def test_get_company_metadata(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_company: Company,
        company_id,
    ):
        """Test GET /internal/ai/companies/{company_id} returns correct metadata."""
        response = client.get(
            f"/internal/ai/companies/{company_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["company_id"] == company_id
        assert data["name"] == test_company.name
        assert "services_offered" in data
    
    def test_get_lead_metadata(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_lead: Lead,
    ):
        """Test GET /internal/ai/leads/{lead_id} returns correct metadata."""
        response = client.get(
            f"/internal/ai/leads/{test_lead.id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "lead" in data
        assert "contact" in data
        assert "appointments" in data
        
        assert data["lead"]["id"] == test_lead.id
        assert data["lead"]["company_id"] == test_lead.company_id
        assert "name" in data["contact"]
        assert isinstance(data["appointments"], list)
    
    def test_get_appointment_metadata(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_appointment: Appointment,
    ):
        """Test GET /internal/ai/appointments/{appointment_id} returns correct metadata."""
        response = client.get(
            f"/internal/ai/appointments/{test_appointment.id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "appointment" in data
        assert "lead" in data
        assert "contact" in data
        
        assert data["appointment"]["id"] == test_appointment.id
        assert data["appointment"]["company_id"] == test_appointment.company_id
        assert "name" in data["contact"]
    
    def test_get_service_catalog(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_company: Company,
        db_session: Session,
        company_id,
    ):
        """Test GET /internal/ai/services/{company_id} returns service catalog."""
        # Create a test service
        service = Service(
            name="Test Service",
            description="Test service description",
            base_price=100.0,
            company_id=company_id,
        )
        db_session.add(service)
        db_session.commit()
        
        response = client.get(
            f"/internal/ai/services/{company_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["company_id"] == company_id
        assert "services" in data
        assert isinstance(data["services"], list)
        assert len(data["services"]) > 0
        assert data["services"][0]["name"] == "Test Service"
    
    def test_get_service_catalog_empty(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_company: Company,
        company_id,
    ):
        """Test GET /internal/ai/services/{company_id} returns empty list when no services."""
        response = client.get(
            f"/internal/ai/services/{company_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["company_id"] == company_id
        assert "services" in data
        assert isinstance(data["services"], list)


class TestNotFound:
    """Test not found scenarios."""
    
    def test_call_not_found(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
    ):
        """Test that non-existent call returns 404."""
        response = client.get(
            "/internal/ai/calls/999999",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404
    
    def test_rep_not_found(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
    ):
        """Test that non-existent rep returns 404."""
        response = client.get(
            "/internal/ai/reps/nonexistent_rep",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404
    
    def test_company_not_found(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
    ):
        """Test that non-existent company returns 404."""
        response = client.get(
            "/internal/ai/companies/nonexistent_company",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404
    
    def test_lead_not_found(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
    ):
        """Test that non-existent lead returns 404."""
        response = client.get(
            "/internal/ai/leads/nonexistent_lead",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404
    
    def test_appointment_not_found(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
    ):
        """Test that non-existent appointment returns 404."""
        response = client.get(
            "/internal/ai/appointments/nonexistent_appointment",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404



Test suite for internal AI API endpoints.

Tests authentication, tenant isolation, and endpoint functionality.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime

from app.main import app
from app.models.call import Call
from app.models.sales_rep import SalesRep
from app.models.company import Company
from app.models.lead import Lead
from app.models.contact_card import ContactCard
from app.models.appointment import Appointment, AppointmentStatus, AppointmentOutcome
from app.models.service import Service
from app.models.user import User
from app.config import settings


@pytest.fixture
def ai_internal_token():
    """Test token for internal AI API."""
    return "test-ai-internal-token-12345"


@pytest.fixture
def company_id():
    """Test company ID."""
    return "test_company_123"


@pytest.fixture
def other_company_id():
    """Other company ID for isolation tests."""
    return "other_company_456"


@pytest.fixture
def ai_internal_headers(ai_internal_token, company_id):
    """Headers for internal AI API authentication."""
    return {
        "Authorization": f"Bearer {ai_internal_token}",
        "X-Company-Id": company_id,
    }


@pytest.fixture
def mock_ai_internal_token(ai_internal_token):
    """Mock AI_INTERNAL_TOKEN in settings."""
    with patch.object(settings, 'AI_INTERNAL_TOKEN', ai_internal_token):
        yield


@pytest.fixture
def test_company(db_session: Session, company_id):
    """Create a test company."""
    company = Company(
        id=company_id,
        name="Test Company",
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture
def test_contact_card(db_session: Session, company_id):
    """Create a test contact card."""
    contact = ContactCard(
        id="contact_123",
        company_id=company_id,
        primary_phone="+1234567890",
        secondary_phone="+0987654321",
        email="test@example.com",
        first_name="John",
        last_name="Doe",
        address="123 Main St",
        city="Test City",
        state="TS",
        postal_code="12345",
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)
    return contact


@pytest.fixture
def test_lead(db_session: Session, company_id, test_contact_card):
    """Create a test lead."""
    from app.models.lead import Lead, LeadStatus, LeadSource
    
    lead = Lead(
        id="lead_123",
        company_id=company_id,
        contact_card_id=test_contact_card.id,
        status=LeadStatus.NEW,
        source=LeadSource.INBOUND_CALL,
        priority="high",
        score=85,
    )
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)
    return lead


@pytest.fixture
def test_call(db_session: Session, company_id, test_lead, test_contact_card):
    """Create a test call."""
    call = Call(
        call_id=12345,
        company_id=company_id,
        lead_id=test_lead.id,
        contact_card_id=test_contact_card.id,
        phone_number="+1234567890",
        missed_call=False,
        booked=True,
        last_call_duration=300,  # 5 minutes
    )
    db_session.add(call)
    db_session.commit()
    db_session.refresh(call)
    return call


@pytest.fixture
def test_user(db_session: Session, company_id):
    """Create a test user."""
    user = User(
        id="user_123",
        company_id=company_id,
        email="rep@example.com",
        username="testrep",
        name="Test Rep",
        phone_number="+1111111111",
        role="rep",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_rep(db_session: Session, company_id, test_user):
    """Create a test sales rep."""
    from app.models.sales_rep import SalesRep, RecordingMode, ShiftConfigSource
    
    rep = SalesRep(
        user_id=test_user.id,
        company_id=company_id,
        recording_mode=RecordingMode.NORMAL,
        allow_location_tracking=True,
        allow_recording=True,
        shift_config_source=ShiftConfigSource.TENANT_DEFAULT,
    )
    db_session.add(rep)
    db_session.commit()
    db_session.refresh(rep)
    return rep


@pytest.fixture
def test_appointment(db_session: Session, company_id, test_lead, test_contact_card, test_rep):
    """Create a test appointment."""
    appointment = Appointment(
        id="appt_123",
        company_id=company_id,
        lead_id=test_lead.id,
        contact_card_id=test_contact_card.id,
        assigned_rep_id=test_rep.user_id,
        scheduled_start=datetime(2025, 1, 20, 10, 0, 0),
        scheduled_end=datetime(2025, 1, 20, 11, 0, 0),
        status=AppointmentStatus.SCHEDULED,
        outcome=AppointmentOutcome.PENDING,
        service_type="roofing",
        location="123 Main St",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)
    return appointment


class TestAuthFailures:
    """Test authentication failure cases."""
    
    def test_missing_authorization_header(
        self, client: TestClient, mock_ai_internal_token, company_id
    ):
        """Test that missing Authorization header returns 401."""
        response = client.get(
            f"/internal/ai/companies/{company_id}",
            headers={"X-Company-Id": company_id},
        )
        assert response.status_code == 401
        assert "Missing Authorization header" in response.json()["detail"]
    
    def test_invalid_token_format(
        self, client: TestClient, mock_ai_internal_token, company_id
    ):
        """Test that invalid token format returns 401."""
        response = client.get(
            f"/internal/ai/companies/{company_id}",
            headers={
                "Authorization": "InvalidFormat token",
                "X-Company-Id": company_id,
            },
        )
        assert response.status_code == 401
        assert "Invalid authorization format" in response.json()["detail"]
    
    def test_invalid_token(
        self, client: TestClient, mock_ai_internal_token, company_id
    ):
        """Test that invalid token returns 401."""
        response = client.get(
            f"/internal/ai/companies/{company_id}",
            headers={
                "Authorization": "Bearer wrong-token",
                "X-Company-Id": company_id,
            },
        )
        assert response.status_code == 401
        assert "Invalid authentication token" in response.json()["detail"]
    
    def test_missing_company_id_header(
        self, client: TestClient, mock_ai_internal_token, ai_internal_token
    ):
        """Test that missing X-Company-Id header returns 400."""
        response = client.get(
            "/internal/ai/companies/test_company_123",
            headers={"Authorization": f"Bearer {ai_internal_token}"},
        )
        assert response.status_code == 400
        assert "Missing X-Company-Id header" in response.json()["detail"]
    
    def test_empty_company_id_header(
        self, client: TestClient, mock_ai_internal_token, ai_internal_token
    ):
        """Test that empty X-Company-Id header returns 400."""
        response = client.get(
            "/internal/ai/companies/test_company_123",
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": "",
            },
        )
        assert response.status_code == 400
        assert "X-Company-Id header cannot be empty" in response.json()["detail"]


class TestTenantIsolation:
    """Test tenant isolation for internal AI API."""
    
    def test_company_mismatch(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        company_id,
        other_company_id,
    ):
        """Test that accessing another company returns 403."""
        response = client.get(
            f"/internal/ai/companies/{other_company_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 403
        assert "Company ID mismatch" in response.json()["detail"]
    
    def test_call_from_other_company(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        db_session: Session,
        other_company_id,
    ):
        """Test that accessing call from another company returns 404."""
        # Create call for other company
        other_call = Call(
            call_id=99999,
            company_id=other_company_id,
            phone_number="+9999999999",
        )
        db_session.add(other_call)
        db_session.commit()
        
        response = client.get(
            f"/internal/ai/calls/{other_call.call_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404
    
    def test_rep_from_other_company(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        db_session: Session,
        other_company_id,
    ):
        """Test that accessing rep from another company returns 404."""
        from app.models.sales_rep import SalesRep, RecordingMode, ShiftConfigSource
        from app.models.user import User
        
        # Create user and rep for other company
        other_user = User(
            id="other_user_123",
            company_id=other_company_id,
            email="other@example.com",
            username="otherrep",
            name="Other Rep",
            role="rep",
        )
        db_session.add(other_user)
        
        other_rep = SalesRep(
            user_id=other_user.id,
            company_id=other_company_id,
            recording_mode=RecordingMode.NORMAL,
            allow_location_tracking=True,
            allow_recording=True,
            shift_config_source=ShiftConfigSource.TENANT_DEFAULT,
        )
        db_session.add(other_rep)
        db_session.commit()
        
        response = client.get(
            f"/internal/ai/reps/{other_rep.user_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404


class TestHappyPaths:
    """Test happy path scenarios for each endpoint."""
    
    def test_get_call_metadata(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_call: Call,
    ):
        """Test GET /internal/ai/calls/{call_id} returns correct metadata."""
        response = client.get(
            f"/internal/ai/calls/{test_call.call_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["call_id"] == test_call.call_id
        assert data["company_id"] == test_call.company_id
        assert data["lead_id"] == test_call.lead_id
        assert data["contact_card_id"] == test_call.contact_card_id
        assert data["phone_number"] == test_call.phone_number
        assert data["duration_seconds"] == test_call.last_call_duration
        assert "booking_outcome" in data
    
    def test_get_rep_metadata(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_rep: SalesRep,
    ):
        """Test GET /internal/ai/reps/{rep_id} returns correct metadata."""
        response = client.get(
            f"/internal/ai/reps/{test_rep.user_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["rep_id"] == test_rep.user_id
        assert data["company_id"] == test_rep.company_id
        assert "name" in data
        assert "email" in data
        assert "active" in data
    
    def test_get_company_metadata(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_company: Company,
        company_id,
    ):
        """Test GET /internal/ai/companies/{company_id} returns correct metadata."""
        response = client.get(
            f"/internal/ai/companies/{company_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["company_id"] == company_id
        assert data["name"] == test_company.name
        assert "services_offered" in data
    
    def test_get_lead_metadata(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_lead: Lead,
    ):
        """Test GET /internal/ai/leads/{lead_id} returns correct metadata."""
        response = client.get(
            f"/internal/ai/leads/{test_lead.id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "lead" in data
        assert "contact" in data
        assert "appointments" in data
        
        assert data["lead"]["id"] == test_lead.id
        assert data["lead"]["company_id"] == test_lead.company_id
        assert "name" in data["contact"]
        assert isinstance(data["appointments"], list)
    
    def test_get_appointment_metadata(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_appointment: Appointment,
    ):
        """Test GET /internal/ai/appointments/{appointment_id} returns correct metadata."""
        response = client.get(
            f"/internal/ai/appointments/{test_appointment.id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "appointment" in data
        assert "lead" in data
        assert "contact" in data
        
        assert data["appointment"]["id"] == test_appointment.id
        assert data["appointment"]["company_id"] == test_appointment.company_id
        assert "name" in data["contact"]
    
    def test_get_service_catalog(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_company: Company,
        db_session: Session,
        company_id,
    ):
        """Test GET /internal/ai/services/{company_id} returns service catalog."""
        # Create a test service
        service = Service(
            name="Test Service",
            description="Test service description",
            base_price=100.0,
            company_id=company_id,
        )
        db_session.add(service)
        db_session.commit()
        
        response = client.get(
            f"/internal/ai/services/{company_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["company_id"] == company_id
        assert "services" in data
        assert isinstance(data["services"], list)
        assert len(data["services"]) > 0
        assert data["services"][0]["name"] == "Test Service"
    
    def test_get_service_catalog_empty(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_company: Company,
        company_id,
    ):
        """Test GET /internal/ai/services/{company_id} returns empty list when no services."""
        response = client.get(
            f"/internal/ai/services/{company_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["company_id"] == company_id
        assert "services" in data
        assert isinstance(data["services"], list)


class TestNotFound:
    """Test not found scenarios."""
    
    def test_call_not_found(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
    ):
        """Test that non-existent call returns 404."""
        response = client.get(
            "/internal/ai/calls/999999",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404
    
    def test_rep_not_found(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
    ):
        """Test that non-existent rep returns 404."""
        response = client.get(
            "/internal/ai/reps/nonexistent_rep",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404
    
    def test_company_not_found(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
    ):
        """Test that non-existent company returns 404."""
        response = client.get(
            "/internal/ai/companies/nonexistent_company",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404
    
    def test_lead_not_found(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
    ):
        """Test that non-existent lead returns 404."""
        response = client.get(
            "/internal/ai/leads/nonexistent_lead",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404
    
    def test_appointment_not_found(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
    ):
        """Test that non-existent appointment returns 404."""
        response = client.get(
            "/internal/ai/appointments/nonexistent_appointment",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404



Test suite for internal AI API endpoints.

Tests authentication, tenant isolation, and endpoint functionality.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime

from app.main import app
from app.models.call import Call
from app.models.sales_rep import SalesRep
from app.models.company import Company
from app.models.lead import Lead
from app.models.contact_card import ContactCard
from app.models.appointment import Appointment, AppointmentStatus, AppointmentOutcome
from app.models.service import Service
from app.models.user import User
from app.config import settings


@pytest.fixture
def ai_internal_token():
    """Test token for internal AI API."""
    return "test-ai-internal-token-12345"


@pytest.fixture
def company_id():
    """Test company ID."""
    return "test_company_123"


@pytest.fixture
def other_company_id():
    """Other company ID for isolation tests."""
    return "other_company_456"


@pytest.fixture
def ai_internal_headers(ai_internal_token, company_id):
    """Headers for internal AI API authentication."""
    return {
        "Authorization": f"Bearer {ai_internal_token}",
        "X-Company-Id": company_id,
    }


@pytest.fixture
def mock_ai_internal_token(ai_internal_token):
    """Mock AI_INTERNAL_TOKEN in settings."""
    with patch.object(settings, 'AI_INTERNAL_TOKEN', ai_internal_token):
        yield


@pytest.fixture
def test_company(db_session: Session, company_id):
    """Create a test company."""
    company = Company(
        id=company_id,
        name="Test Company",
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture
def test_contact_card(db_session: Session, company_id):
    """Create a test contact card."""
    contact = ContactCard(
        id="contact_123",
        company_id=company_id,
        primary_phone="+1234567890",
        secondary_phone="+0987654321",
        email="test@example.com",
        first_name="John",
        last_name="Doe",
        address="123 Main St",
        city="Test City",
        state="TS",
        postal_code="12345",
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)
    return contact


@pytest.fixture
def test_lead(db_session: Session, company_id, test_contact_card):
    """Create a test lead."""
    from app.models.lead import Lead, LeadStatus, LeadSource
    
    lead = Lead(
        id="lead_123",
        company_id=company_id,
        contact_card_id=test_contact_card.id,
        status=LeadStatus.NEW,
        source=LeadSource.INBOUND_CALL,
        priority="high",
        score=85,
    )
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)
    return lead


@pytest.fixture
def test_call(db_session: Session, company_id, test_lead, test_contact_card):
    """Create a test call."""
    call = Call(
        call_id=12345,
        company_id=company_id,
        lead_id=test_lead.id,
        contact_card_id=test_contact_card.id,
        phone_number="+1234567890",
        missed_call=False,
        booked=True,
        last_call_duration=300,  # 5 minutes
    )
    db_session.add(call)
    db_session.commit()
    db_session.refresh(call)
    return call


@pytest.fixture
def test_user(db_session: Session, company_id):
    """Create a test user."""
    user = User(
        id="user_123",
        company_id=company_id,
        email="rep@example.com",
        username="testrep",
        name="Test Rep",
        phone_number="+1111111111",
        role="rep",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_rep(db_session: Session, company_id, test_user):
    """Create a test sales rep."""
    from app.models.sales_rep import SalesRep, RecordingMode, ShiftConfigSource
    
    rep = SalesRep(
        user_id=test_user.id,
        company_id=company_id,
        recording_mode=RecordingMode.NORMAL,
        allow_location_tracking=True,
        allow_recording=True,
        shift_config_source=ShiftConfigSource.TENANT_DEFAULT,
    )
    db_session.add(rep)
    db_session.commit()
    db_session.refresh(rep)
    return rep


@pytest.fixture
def test_appointment(db_session: Session, company_id, test_lead, test_contact_card, test_rep):
    """Create a test appointment."""
    appointment = Appointment(
        id="appt_123",
        company_id=company_id,
        lead_id=test_lead.id,
        contact_card_id=test_contact_card.id,
        assigned_rep_id=test_rep.user_id,
        scheduled_start=datetime(2025, 1, 20, 10, 0, 0),
        scheduled_end=datetime(2025, 1, 20, 11, 0, 0),
        status=AppointmentStatus.SCHEDULED,
        outcome=AppointmentOutcome.PENDING,
        service_type="roofing",
        location="123 Main St",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)
    return appointment


class TestAuthFailures:
    """Test authentication failure cases."""
    
    def test_missing_authorization_header(
        self, client: TestClient, mock_ai_internal_token, company_id
    ):
        """Test that missing Authorization header returns 401."""
        response = client.get(
            f"/internal/ai/companies/{company_id}",
            headers={"X-Company-Id": company_id},
        )
        assert response.status_code == 401
        assert "Missing Authorization header" in response.json()["detail"]
    
    def test_invalid_token_format(
        self, client: TestClient, mock_ai_internal_token, company_id
    ):
        """Test that invalid token format returns 401."""
        response = client.get(
            f"/internal/ai/companies/{company_id}",
            headers={
                "Authorization": "InvalidFormat token",
                "X-Company-Id": company_id,
            },
        )
        assert response.status_code == 401
        assert "Invalid authorization format" in response.json()["detail"]
    
    def test_invalid_token(
        self, client: TestClient, mock_ai_internal_token, company_id
    ):
        """Test that invalid token returns 401."""
        response = client.get(
            f"/internal/ai/companies/{company_id}",
            headers={
                "Authorization": "Bearer wrong-token",
                "X-Company-Id": company_id,
            },
        )
        assert response.status_code == 401
        assert "Invalid authentication token" in response.json()["detail"]
    
    def test_missing_company_id_header(
        self, client: TestClient, mock_ai_internal_token, ai_internal_token
    ):
        """Test that missing X-Company-Id header returns 400."""
        response = client.get(
            "/internal/ai/companies/test_company_123",
            headers={"Authorization": f"Bearer {ai_internal_token}"},
        )
        assert response.status_code == 400
        assert "Missing X-Company-Id header" in response.json()["detail"]
    
    def test_empty_company_id_header(
        self, client: TestClient, mock_ai_internal_token, ai_internal_token
    ):
        """Test that empty X-Company-Id header returns 400."""
        response = client.get(
            "/internal/ai/companies/test_company_123",
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": "",
            },
        )
        assert response.status_code == 400
        assert "X-Company-Id header cannot be empty" in response.json()["detail"]


class TestTenantIsolation:
    """Test tenant isolation for internal AI API."""
    
    def test_company_mismatch(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        company_id,
        other_company_id,
    ):
        """Test that accessing another company returns 403."""
        response = client.get(
            f"/internal/ai/companies/{other_company_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 403
        assert "Company ID mismatch" in response.json()["detail"]
    
    def test_call_from_other_company(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        db_session: Session,
        other_company_id,
    ):
        """Test that accessing call from another company returns 404."""
        # Create call for other company
        other_call = Call(
            call_id=99999,
            company_id=other_company_id,
            phone_number="+9999999999",
        )
        db_session.add(other_call)
        db_session.commit()
        
        response = client.get(
            f"/internal/ai/calls/{other_call.call_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404
    
    def test_rep_from_other_company(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        db_session: Session,
        other_company_id,
    ):
        """Test that accessing rep from another company returns 404."""
        from app.models.sales_rep import SalesRep, RecordingMode, ShiftConfigSource
        from app.models.user import User
        
        # Create user and rep for other company
        other_user = User(
            id="other_user_123",
            company_id=other_company_id,
            email="other@example.com",
            username="otherrep",
            name="Other Rep",
            role="rep",
        )
        db_session.add(other_user)
        
        other_rep = SalesRep(
            user_id=other_user.id,
            company_id=other_company_id,
            recording_mode=RecordingMode.NORMAL,
            allow_location_tracking=True,
            allow_recording=True,
            shift_config_source=ShiftConfigSource.TENANT_DEFAULT,
        )
        db_session.add(other_rep)
        db_session.commit()
        
        response = client.get(
            f"/internal/ai/reps/{other_rep.user_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404


class TestHappyPaths:
    """Test happy path scenarios for each endpoint."""
    
    def test_get_call_metadata(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_call: Call,
    ):
        """Test GET /internal/ai/calls/{call_id} returns correct metadata."""
        response = client.get(
            f"/internal/ai/calls/{test_call.call_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["call_id"] == test_call.call_id
        assert data["company_id"] == test_call.company_id
        assert data["lead_id"] == test_call.lead_id
        assert data["contact_card_id"] == test_call.contact_card_id
        assert data["phone_number"] == test_call.phone_number
        assert data["duration_seconds"] == test_call.last_call_duration
        assert "booking_outcome" in data
    
    def test_get_rep_metadata(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_rep: SalesRep,
    ):
        """Test GET /internal/ai/reps/{rep_id} returns correct metadata."""
        response = client.get(
            f"/internal/ai/reps/{test_rep.user_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["rep_id"] == test_rep.user_id
        assert data["company_id"] == test_rep.company_id
        assert "name" in data
        assert "email" in data
        assert "active" in data
    
    def test_get_company_metadata(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_company: Company,
        company_id,
    ):
        """Test GET /internal/ai/companies/{company_id} returns correct metadata."""
        response = client.get(
            f"/internal/ai/companies/{company_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["company_id"] == company_id
        assert data["name"] == test_company.name
        assert "services_offered" in data
    
    def test_get_lead_metadata(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_lead: Lead,
    ):
        """Test GET /internal/ai/leads/{lead_id} returns correct metadata."""
        response = client.get(
            f"/internal/ai/leads/{test_lead.id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "lead" in data
        assert "contact" in data
        assert "appointments" in data
        
        assert data["lead"]["id"] == test_lead.id
        assert data["lead"]["company_id"] == test_lead.company_id
        assert "name" in data["contact"]
        assert isinstance(data["appointments"], list)
    
    def test_get_appointment_metadata(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_appointment: Appointment,
    ):
        """Test GET /internal/ai/appointments/{appointment_id} returns correct metadata."""
        response = client.get(
            f"/internal/ai/appointments/{test_appointment.id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "appointment" in data
        assert "lead" in data
        assert "contact" in data
        
        assert data["appointment"]["id"] == test_appointment.id
        assert data["appointment"]["company_id"] == test_appointment.company_id
        assert "name" in data["contact"]
    
    def test_get_service_catalog(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_company: Company,
        db_session: Session,
        company_id,
    ):
        """Test GET /internal/ai/services/{company_id} returns service catalog."""
        # Create a test service
        service = Service(
            name="Test Service",
            description="Test service description",
            base_price=100.0,
            company_id=company_id,
        )
        db_session.add(service)
        db_session.commit()
        
        response = client.get(
            f"/internal/ai/services/{company_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["company_id"] == company_id
        assert "services" in data
        assert isinstance(data["services"], list)
        assert len(data["services"]) > 0
        assert data["services"][0]["name"] == "Test Service"
    
    def test_get_service_catalog_empty(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
        test_company: Company,
        company_id,
    ):
        """Test GET /internal/ai/services/{company_id} returns empty list when no services."""
        response = client.get(
            f"/internal/ai/services/{company_id}",
            headers=ai_internal_headers,
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["company_id"] == company_id
        assert "services" in data
        assert isinstance(data["services"], list)


class TestNotFound:
    """Test not found scenarios."""
    
    def test_call_not_found(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
    ):
        """Test that non-existent call returns 404."""
        response = client.get(
            "/internal/ai/calls/999999",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404
    
    def test_rep_not_found(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
    ):
        """Test that non-existent rep returns 404."""
        response = client.get(
            "/internal/ai/reps/nonexistent_rep",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404
    
    def test_company_not_found(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
    ):
        """Test that non-existent company returns 404."""
        response = client.get(
            "/internal/ai/companies/nonexistent_company",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404
    
    def test_lead_not_found(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
    ):
        """Test that non-existent lead returns 404."""
        response = client.get(
            "/internal/ai/leads/nonexistent_lead",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404
    
    def test_appointment_not_found(
        self,
        client: TestClient,
        mock_ai_internal_token,
        ai_internal_headers,
    ):
        """Test that non-existent appointment returns 404."""
        response = client.get(
            "/internal/ai/appointments/nonexistent_appointment",
            headers=ai_internal_headers,
        )
        assert response.status_code == 404



