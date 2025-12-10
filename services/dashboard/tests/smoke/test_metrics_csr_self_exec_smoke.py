"""
Smoke tests for CSR self-scoped and Exec metrics endpoints.

Tests verify:
- HTTP 200 for correct roles
- HTTP 403 for incorrect roles
- Response has correct shape (keys present, types correct)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.metrics import (
    CSROverviewSelfResponse,
    CSRBookingTrendSelfResponse,
    UnbookedCallsSelfResponse,
    CSRObjectionsSelfResponse,
    CallsByObjectionSelfResponse,
    CSRMissedCallsSelfResponse,
    MissedLeadsSelfResponse,
    RideAlongAppointmentsResponse,
    SalesOpportunitiesResponse
)


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def mock_verify_clerk_jwt(monkeypatch):
    """Mock JWT verification to allow test requests."""
    def mock_verify(*args, **kwargs):
        return {
            "id": "test_user_001",
            "org_role": "csr",
            "organization_memberships": [{"organization": {"id": "test_company_123"}}]
        }
    
    monkeypatch.setattr("app.middleware.tenant.verify_clerk_jwt", mock_verify)
    return mock_verify


@pytest.fixture
def mock_verify_clerk_jwt_manager(monkeypatch):
    """Mock JWT verification for manager role."""
    def mock_verify(*args, **kwargs):
        return {
            "id": "test_manager_001",
            "org_role": "manager",
            "organization_memberships": [{"organization": {"id": "test_company_123"}}]
        }
    
    monkeypatch.setattr("app.middleware.tenant.verify_clerk_jwt", mock_verify)
    return mock_verify


@pytest.fixture
def auth_headers_factory():
    """Factory for creating auth headers."""
    def _create_headers(tenant_id: str, user_id: str, org_role: str = "csr"):
        return {
            "Authorization": f"Bearer test_token_{user_id}",
            "X-Company-ID": tenant_id
        }
    return _create_headers


class TestCSRSelfScopedEndpoints:
    """Test CSR self-scoped endpoints."""
    
    @patch('app.routes.metrics_kpis.MetricsService')
    def test_csr_overview_self_returns_200(
        self,
        mock_service_class,
        client,
        auth_headers_factory,
        mock_verify_clerk_jwt
    ):
        """Test CSR overview self endpoint returns 200 and valid schema."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        
        mock_metrics = CSROverviewSelfResponse(
            total_calls=100,
            qualified_calls=80,
            qualified_rate=0.8,
            booked_calls=60,
            booking_rate=0.75,
            service_not_offered_calls=5,
            service_not_offered_rate=0.0625,
            avg_objections_per_qualified_call=1.2,
            qualified_but_unbooked_calls=15,
            avg_compliance_score=8.5,
            open_followups=10,
            overdue_followups=2,
            top_reason_for_missed_bookings="price",
            pending_leads_count=5,
            top_missed_booking_reason="price"
        )
        mock_service.get_csr_overview_self = AsyncMock(return_value=mock_metrics)
        
        headers = auth_headers_factory(
            tenant_id="test_company_123",
            user_id="test_csr_001",
            org_role="csr"
        )
        
        response = client.get("/api/v1/metrics/csr/overview/self", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "top_missed_booking_reason" in data["data"]
    
    def test_csr_overview_self_manager_forbidden(
        self,
        client,
        auth_headers_factory,
        mock_verify_clerk_jwt_manager
    ):
        """Test that manager role is forbidden from CSR self endpoints."""
        headers = auth_headers_factory(
            tenant_id="test_company_123",
            user_id="test_manager_001",
            org_role="manager"
        )
        
        response = client.get("/api/v1/metrics/csr/overview/self", headers=headers)
        assert response.status_code == 403
    
    @patch('app.routes.metrics_kpis.MetricsService')
    def test_csr_booking_trend_self_returns_200(
        self,
        mock_service_class,
        client,
        auth_headers_factory,
        mock_verify_clerk_jwt
    ):
        """Test CSR booking trend self endpoint returns 200."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        
        from app.schemas.metrics import CSRBookingTrendSummary, CSRBookingTrendPoint
        
        mock_metrics = CSRBookingTrendSelfResponse(
            summary=CSRBookingTrendSummary(
                total_leads=100,
                total_qualified_leads=80,
                total_booked_calls=60,
                current_booking_rate=0.75
            ),
            booking_rate_trend=[
                CSRBookingTrendPoint(timestamp="2025-01-01", value=0.7),
                CSRBookingTrendPoint(timestamp="2025-01-02", value=0.75)
            ]
        )
        mock_service.get_csr_booking_trend_self = AsyncMock(return_value=mock_metrics)
        
        headers = auth_headers_factory(
            tenant_id="test_company_123",
            user_id="test_csr_001",
            org_role="csr"
        )
        
        response = client.get("/api/v1/metrics/csr/booking-trend/self", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "summary" in data["data"]
        assert "booking_rate_trend" in data["data"]
    
    @patch('app.routes.metrics_kpis.MetricsService')
    def test_calls_unbooked_self_returns_200(
        self,
        mock_service_class,
        client,
        auth_headers_factory,
        mock_verify_clerk_jwt
    ):
        """Test unbooked calls self endpoint returns 200."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        
        from app.schemas.metrics import UnbookedCallItem
        
        mock_response = UnbookedCallsSelfResponse(
            items=[
                UnbookedCallItem(
                    call_id=1,
                    customer_name="John Doe",
                    phone="+1234567890",
                    booking_status="not_booked",
                    qualified=True,
                    status="pending",
                    last_contacted_at="2025-01-01T12:00:00Z"
                )
            ],
            page=1,
            page_size=50,
            total=1
        )
        mock_service.get_csr_unbooked_calls_self = AsyncMock(return_value=mock_response)
        
        headers = auth_headers_factory(
            tenant_id="test_company_123",
            user_id="test_csr_001",
            org_role="csr"
        )
        
        response = client.get("/api/v1/calls/unbooked/self", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "items" in data["data"]
        assert "page" in data["data"]
        assert "total" in data["data"]
    
    @patch('app.routes.metrics_kpis.MetricsService')
    def test_csr_objections_self_returns_200(
        self,
        mock_service_class,
        client,
        auth_headers_factory,
        mock_verify_clerk_jwt
    ):
        """Test CSR objections self endpoint returns 200."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        
        from app.schemas.metrics import CSRObjectionSelfItem
        
        mock_response = CSRObjectionsSelfResponse(
            top_objections=[
                CSRObjectionSelfItem(
                    objection="price",
                    occurrence_count=10,
                    occurrence_rate=0.1,
                    qualified_unbooked_occurrence_rate=0.15
                )
            ],
            all_objections=[]
        )
        mock_service.get_csr_objections_self = AsyncMock(return_value=mock_response)
        
        headers = auth_headers_factory(
            tenant_id="test_company_123",
            user_id="test_csr_001",
            org_role="csr"
        )
        
        response = client.get("/api/v1/metrics/csr/objections/self", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "top_objections" in data["data"]
        assert "all_objections" in data["data"]
    
    @patch('app.routes.metrics_kpis.MetricsService')
    def test_calls_by_objection_self_returns_200(
        self,
        mock_service_class,
        client,
        auth_headers_factory,
        mock_verify_clerk_jwt
    ):
        """Test calls by objection self endpoint returns 200."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        
        from app.schemas.metrics import CallByObjectionItem
        
        mock_response = CallsByObjectionSelfResponse(
            items=[
                CallByObjectionItem(
                    call_id=1,
                    customer_name="John Doe",
                    started_at="2025-01-01T12:00:00Z",
                    duration_seconds=300,
                    booking_status="not_booked",
                    audio_url="https://example.com/audio.mp3"
                )
            ],
            page=1,
            page_size=50,
            total=1
        )
        mock_service.get_csr_calls_by_objection_self = AsyncMock(return_value=mock_response)
        
        headers = auth_headers_factory(
            tenant_id="test_company_123",
            user_id="test_csr_001",
            org_role="csr"
        )
        
        response = client.get("/api/v1/calls/by-objection/self?objection=price", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "items" in data["data"]
    
    @patch('app.routes.metrics_kpis.MetricsService')
    def test_csr_missed_calls_self_returns_200(
        self,
        mock_service_class,
        client,
        auth_headers_factory,
        mock_verify_clerk_jwt
    ):
        """Test CSR missed calls self endpoint returns 200."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        
        mock_response = CSRMissedCallsSelfResponse(
            total_missed_calls=10,
            total_saved_calls=5,
            total_saved_by_otto=3,
            booked_leads_count=2,
            pending_leads_count=2,
            dead_leads_count=1
        )
        mock_service.get_csr_missed_calls_self = AsyncMock(return_value=mock_response)
        
        headers = auth_headers_factory(
            tenant_id="test_company_123",
            user_id="test_csr_001",
            org_role="csr"
        )
        
        response = client.get("/api/v1/metrics/csr/missed-calls/self", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "total_missed_calls" in data["data"]
    
    @patch('app.routes.metrics_kpis.MetricsService')
    def test_leads_missed_self_returns_200(
        self,
        mock_service_class,
        client,
        auth_headers_factory,
        mock_verify_clerk_jwt
    ):
        """Test missed leads self endpoint returns 200."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        
        from app.schemas.metrics import MissedLeadItem
        
        mock_response = MissedLeadsSelfResponse(
            items=[
                MissedLeadItem(
                    lead_id="lead_1",
                    customer_name="John Doe",
                    status="pending",
                    source="missed_call",
                    last_contacted_at="2025-01-01T12:00:00Z",
                    next_action="Follow up",
                    next_action_due_at="2025-01-02T12:00:00Z",
                    attempt_count=3
                )
            ],
            page=1,
            page_size=50,
            total=1
        )
        mock_service.get_csr_missed_leads_self = AsyncMock(return_value=mock_response)
        
        headers = auth_headers_factory(
            tenant_id="test_company_123",
            user_id="test_csr_001",
            org_role="csr"
        )
        
        response = client.get("/api/v1/leads/missed/self", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "items" in data["data"]


class TestExecEndpoints:
    """Test Exec endpoints."""
    
    @patch('app.routes.metrics_kpis.MetricsService')
    def test_ride_along_appointments_returns_200(
        self,
        mock_service_class,
        client,
        auth_headers_factory,
        mock_verify_clerk_jwt_manager
    ):
        """Test ride-along appointments endpoint returns 200."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        
        from app.schemas.metrics import RideAlongAppointmentItem
        
        mock_response = RideAlongAppointmentsResponse(
            items=[
                RideAlongAppointmentItem(
                    appointment_id="appt_1",
                    customer_name="John Doe",
                    scheduled_at="2025-01-01T12:00:00Z",
                    rep_id="rep_1",
                    rep_name="Jane Rep",
                    status="in_progress",
                    outcome="pending",
                    sop_compliance_scores={"overall": 8.5},
                    booking_path=["inbound_call_csr", "appointment_booked"]
                )
            ],
            page=1,
            page_size=50,
            total=1
        )
        mock_service.get_ride_along_appointments = AsyncMock(return_value=mock_response)
        
        headers = auth_headers_factory(
            tenant_id="test_company_123",
            user_id="test_manager_001",
            org_role="manager"
        )
        
        response = client.get("/api/v1/metrics/appointments/ride-along", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "items" in data["data"]
        assert "page" in data["data"]
    
    def test_ride_along_appointments_csr_forbidden(
        self,
        client,
        auth_headers_factory,
        mock_verify_clerk_jwt
    ):
        """Test that CSR role is forbidden from ride-along appointments."""
        headers = auth_headers_factory(
            tenant_id="test_company_123",
            user_id="test_csr_001",
            org_role="csr"
        )
        
        response = client.get("/api/v1/metrics/appointments/ride-along", headers=headers)
        assert response.status_code == 403
    
    @patch('app.routes.metrics_kpis.MetricsService')
    def test_sales_opportunities_returns_200(
        self,
        mock_service_class,
        client,
        auth_headers_factory,
        mock_verify_clerk_jwt_manager
    ):
        """Test sales opportunities endpoint returns 200."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        
        from app.schemas.metrics import SalesOpportunityItem
        
        mock_response = SalesOpportunitiesResponse(
            items=[
                SalesOpportunityItem(
                    rep_id="rep_1",
                    rep_name="Jane Rep",
                    pending_leads_count=5,
                    tasks=["Follow up with pricing", "Schedule demo"]
                )
            ]
        )
        mock_service.get_sales_opportunities = AsyncMock(return_value=mock_response)
        
        headers = auth_headers_factory(
            tenant_id="test_company_123",
            user_id="test_manager_001",
            org_role="manager"
        )
        
        response = client.get("/api/v1/metrics/sales/opportunities", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "items" in data["data"]
    
    def test_sales_opportunities_csr_forbidden(
        self,
        client,
        auth_headers_factory,
        mock_verify_clerk_jwt
    ):
        """Test that CSR role is forbidden from sales opportunities."""
        headers = auth_headers_factory(
            tenant_id="test_company_123",
            user_id="test_csr_001",
            org_role="csr"
        )
        
        response = client.get("/api/v1/metrics/sales/opportunities", headers=headers)
        assert response.status_code == 403

