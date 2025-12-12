"""
Smoke tests for recording session endpoints.

Tests:
- Start recording session
- Stop recording session
- RBAC enforcement
- Validation errors
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from uuid import uuid4

from app.main import app
from app.models.appointment import Appointment, AppointmentStatus
from app.models.recording_session import RecordingSession
from app.models.contact_card import ContactCard
from app.models.lead import Lead


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def mock_verify_clerk_jwt():
    """Mock JWT verification for sales rep."""
    with patch("app.middleware.tenant.verify_clerk_jwt") as mock:
        def verify(token: str):
            return {
                "sub": "rep_user_123",
                "org_id": "company_123",
                "metadata": {"role": "sales_rep"}
            }
        mock.return_value = verify
        yield mock


@pytest.fixture
def mock_db_session(client, mock_verify_clerk_jwt):
    """Mock database session with test data."""
    with patch("app.database.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        # Mock appointment
        appointment = MagicMock()
        appointment.id = str(uuid4())
        appointment.company_id = "company_123"
        appointment.assigned_rep_id = "rep_user_123"
        appointment.scheduled_start = datetime.utcnow() + timedelta(hours=1)
        appointment.status = AppointmentStatus.SCHEDULED
        
        # Mock query chain for appointment lookup
        mock_appointment_query = MagicMock()
        mock_appointment_query.filter.return_value.first.return_value = appointment
        mock_db.query.return_value = mock_appointment_query
        
        # Mock recording session query (for existing session check)
        mock_session_query = MagicMock()
        mock_session_query.filter.return_value.first.return_value = None  # No existing session
        mock_db.query.side_effect = lambda model: (
            mock_session_query if model == RecordingSession
            else mock_appointment_query
        )
        
        # Mock add/commit/refresh
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()
        
        # Mock created session
        created_session = MagicMock()
        created_session.id = str(uuid4())
        created_session.appointment_id = appointment.id
        created_session.started_at = datetime.utcnow()
        created_session.ended_at = None
        created_session.status = "recording"
        created_session.audio_url = None
        created_session.shunya_analysis_job_id = None
        
        def refresh_side_effect(obj):
            if hasattr(obj, 'id') and not obj.id:
                obj.id = created_session.id
                obj.appointment_id = appointment.id
                obj.started_at = created_session.started_at
                obj.status = created_session.status
        
        mock_db.refresh.side_effect = refresh_side_effect
        
        yield mock_db


def test_start_recording_session_returns_200(client, mock_db_session, mock_verify_clerk_jwt):
    """Test starting a recording session returns 200 with correct schema."""
    # Set request state for TestClient
    with patch("app.middleware.tenant.get_tenant_id") as mock_tenant:
        mock_tenant.return_value = "company_123"
        
        response = client.post(
            "/api/v1/recordings/sessions/start",
            json={"appointment_id": "appt_123"},
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "id" in data["data"]
        assert "appointment_id" in data["data"]
        assert "status" in data["data"]
        assert data["data"]["status"] == "recording"


def test_start_recording_session_forbidden_non_sales_rep(client):
    """Test that non-sales-rep roles are forbidden."""
    with patch("app.middleware.tenant.verify_clerk_jwt") as mock_verify:
        def verify(token: str):
            return {
                "sub": "user_123",
                "org_id": "company_123",
                "metadata": {"role": "csr"}  # Wrong role
            }
        mock_verify.return_value = verify
        
        response = client.post(
            "/api/v1/recordings/sessions/start",
            json={"appointment_id": "appt_123"},
            headers={"Authorization": "Bearer test_token"}
        )
        
        assert response.status_code == 403


def test_stop_recording_session_returns_200(client, mock_verify_clerk_jwt):
    """Test stopping a recording session returns 200 with correct schema."""
    with patch("app.database.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        # Mock existing recording session
        session = MagicMock()
        session.id = "session_123"
        session.appointment_id = "appt_123"
        session.company_id = "company_123"
        session.rep_id = "rep_user_123"
        session.status = "recording"
        session.started_at = datetime.utcnow() - timedelta(minutes=30)
        session.ended_at = None
        session.audio_url = None
        session.shunya_analysis_job_id = None
        
        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = session
        mock_db.query.return_value = mock_query
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()
        
        # Mock ShunyaJobService
        with patch("app.services.recording_session_service.ShunyaJobService") as mock_job_service:
            mock_job_instance = MagicMock()
            mock_job = MagicMock()
            mock_job.id = "job_123"
            mock_job_instance.create_job.return_value = mock_job
            mock_job_service.return_value = mock_job_instance
            
            with patch("app.middleware.tenant.get_tenant_id") as mock_tenant:
                mock_tenant.return_value = "company_123"
                
                response = client.post(
                    "/api/v1/recordings/sessions/session_123/stop",
                    json={"audio_url": "https://s3.example.com/audio.mp3"},
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "data" in data
                assert data["data"]["id"] == "session_123"
                assert data["data"]["status"] == "completed"
                assert data["data"]["audio_url"] == "https://s3.example.com/audio.mp3"


def test_start_session_error_when_rep_not_assigned(client, mock_verify_clerk_jwt):
    """Test error when rep tries to record appointment not assigned to them."""
    with patch("app.database.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        # Mock appointment assigned to different rep
        appointment = MagicMock()
        appointment.id = "appt_123"
        appointment.company_id = "company_123"
        appointment.assigned_rep_id = "other_rep_456"  # Different rep
        
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = appointment
        mock_db.query.return_value = mock_query
        
        with patch("app.middleware.tenant.get_tenant_id") as mock_tenant:
            mock_tenant.return_value = "company_123"
            
            response = client.post(
                "/api/v1/recordings/sessions/start",
                json={"appointment_id": "appt_123"},
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 400
            assert "not assigned" in response.json()["detail"].lower()


def test_todays_appointments_include_geofence_fields(client, mock_verify_clerk_jwt):
    """Test that today's appointments endpoint includes geofence fields."""
    with patch("app.database.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        # Mock appointment with location data
        appointment = MagicMock()
        appointment.id = "appt_123"
        appointment.company_id = "company_123"
        appointment.assigned_rep_id = "rep_user_123"
        appointment.scheduled_start = datetime.utcnow()
        appointment.location = "123 Main St"
        appointment.location_address = "123 Main St"
        appointment.location_lat = 37.7749
        appointment.location_lng = -122.4194
        appointment.geo_lat = 37.7749
        appointment.geo_lng = -122.4194
        appointment.status = AppointmentStatus.SCHEDULED
        appointment.contact_card_id = "contact_123"
        
        # Mock contact card
        contact_card = MagicMock()
        contact_card.id = "contact_123"
        contact_card.first_name = "John"
        contact_card.last_name = "Doe"
        contact_card.property_snapshot = None
        
        # Mock queries
        def query_side_effect(model):
            mock_query = MagicMock()
            if model == Appointment:
                mock_query.filter.return_value.order_by.return_value.all.return_value = [appointment]
            elif model.__name__ == "ContactCard":
                mock_query.filter.return_value.first.return_value = contact_card
            else:
                mock_query.filter.return_value.all.return_value = []
            return mock_query
        
        mock_db.query.side_effect = query_side_effect
        
        with patch("app.middleware.tenant.get_tenant_id") as mock_tenant:
            mock_tenant.return_value = "company_123"
            
            response = client.get(
                "/api/v1/metrics/appointments/today/self",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "data" in data
            if data["data"]:  # If appointments exist
                appointment_data = data["data"][0]
                assert "location_address" in appointment_data
                assert "location_lat" in appointment_data
                assert "location_lng" in appointment_data
                assert "geofence_radius_meters" in appointment_data
                assert appointment_data["geofence_radius_meters"] == 75



