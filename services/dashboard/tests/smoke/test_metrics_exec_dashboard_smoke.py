"""
Smoke tests for Executive Dashboard metrics endpoints.

Tests:
- HTTP 200 for manager role
- HTTP 403 for non-manager roles (csr, sales_rep)
- Response has correct shape (keys present, types correct, even if values are None)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app


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
            "org_role": "manager",
            "organization_memberships": [{"organization": {"id": "test_company_123"}}]
        }
    
    monkeypatch.setattr("app.middleware.tenant.verify_clerk_jwt", mock_verify)
    return mock_verify


@pytest.fixture
def auth_headers_factory():
    """Factory for creating auth headers."""
    def _create_headers(tenant_id: str, user_id: str, org_role: str = "manager"):
        return {
            "Authorization": f"Bearer test_token_{user_id}",
            "X-Company-ID": tenant_id
        }
    return _create_headers


@patch('app.routes.metrics_kpis.MetricsService')
def test_exec_company_overview_manager_ok(mock_service_class, client, auth_headers_factory, mock_verify_clerk_jwt):
    """Test that manager can access exec company overview endpoint."""
    from app.schemas.metrics import ExecCompanyOverviewMetrics, ExecWhoDroppingBall
    
    mock_service = MagicMock()
    mock_service_class.return_value = mock_service
    
    mock_metrics = ExecCompanyOverviewMetrics(
        total_leads=None,
        qualified_leads=None,
        total_appointments=None,
        total_closed_deals=None,
        lead_to_sale_ratio=None,
        close_rate=None,
        sales_output_amount=None,
        win_rate=None,
        pending_rate=None,
        lost_rate=None,
        win_loss_attribution=None,
        who_dropping_ball=ExecWhoDroppingBall(
            worst_csr_id=None,
            worst_csr_name=None,
            worst_csr_booking_rate=None,
            worst_rep_id=None,
            worst_rep_name=None,
            worst_rep_win_rate=None
        )
    )
    mock_service.get_exec_company_overview_metrics = AsyncMock(return_value=mock_metrics)
    
    headers = auth_headers_factory(
        tenant_id="test_company_123",
        user_id="test_manager_001",
        org_role="manager"
    )
    
    response = client.get("/api/v1/metrics/exec/company-overview", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    
    # Verify response shape
    metrics = data["data"]
    assert "total_leads" in metrics
    assert "qualified_leads" in metrics
    assert "total_appointments" in metrics
    assert "total_closed_deals" in metrics
    assert "lead_to_sale_ratio" in metrics
    assert "close_rate" in metrics
    assert "win_rate" in metrics
    assert "who_dropping_ball" in metrics


def test_exec_company_overview_csr_forbidden(client, auth_headers_factory, mock_verify_clerk_jwt):
    """Test that CSR role is forbidden from exec company overview."""
    def mock_verify_csr(*args, **kwargs):
        return {
            "id": "test_csr_001",
            "org_role": "csr",
            "organization_memberships": [{"organization": {"id": "test_company_123"}}]
        }
    
    with patch("app.middleware.tenant.verify_clerk_jwt", side_effect=mock_verify_csr):
        headers = auth_headers_factory(
            tenant_id="test_company_123",
            user_id="test_csr_001",
            org_role="csr"
        )
        response = client.get("/api/v1/metrics/exec/company-overview", headers=headers)
        assert response.status_code == 403


def test_exec_company_overview_sales_rep_forbidden(client, auth_headers_factory, mock_verify_clerk_jwt):
    """Test that sales_rep role is forbidden from exec company overview."""
    def mock_verify_rep(*args, **kwargs):
        return {
            "id": "test_rep_001",
            "org_role": "sales_rep",
            "organization_memberships": [{"organization": {"id": "test_company_123"}}]
        }
    
    with patch("app.middleware.tenant.verify_clerk_jwt", side_effect=mock_verify_rep):
        headers = auth_headers_factory(
            tenant_id="test_company_123",
            user_id="test_rep_001",
            org_role="sales_rep"
        )
        response = client.get("/api/v1/metrics/exec/company-overview", headers=headers)
        assert response.status_code == 403


@patch('app.routes.metrics_kpis.MetricsService')
def test_exec_csr_dashboard_manager_ok(mock_service_class, client, auth_headers_factory, mock_verify_clerk_jwt):
    """Test that manager can access exec CSR dashboard endpoint."""
    from app.schemas.metrics import ExecCSRDashboardMetrics, ExecCSRMetrics
    
    mock_service = MagicMock()
    mock_service_class.return_value = mock_service
    
    mock_metrics = ExecCSRDashboardMetrics(
        overview=ExecCSRMetrics(
            total_calls=0,
            qualified_calls=0,
            qualified_rate=None,
            booked_calls=0,
            booking_rate=None,
            avg_objections_per_call=None,
            avg_compliance_score=None,
            avg_sentiment_score=None,
            open_followups=0,
            overdue_followups=0
        ),
        booking_rate_trend=None,
        unbooked_calls_count=None,
        top_objections=[],
        coaching_opportunities=[]
    )
    mock_service.get_exec_csr_dashboard_metrics = AsyncMock(return_value=mock_metrics)
    
    headers = auth_headers_factory(
        tenant_id="test_company_123",
        user_id="test_manager_001",
        org_role="manager"
    )
    
    response = client.get("/api/v1/metrics/exec/csr/dashboard", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    
    # Verify response shape
    metrics = data["data"]
    assert "overview" in metrics
    assert "booking_rate_trend" in metrics
    assert "unbooked_calls_count" in metrics
    assert "top_objections" in metrics
    assert "coaching_opportunities" in metrics
    
    # Verify overview shape
    overview = metrics["overview"]
    assert "total_calls" in overview
    assert "qualified_calls" in overview
    assert "booked_calls" in overview


def test_exec_csr_dashboard_csr_forbidden(client, auth_headers_factory, mock_verify_clerk_jwt):
    """Test that CSR role is forbidden from exec CSR dashboard."""
    def mock_verify_csr(*args, **kwargs):
        return {
            "id": "test_csr_001",
            "org_role": "csr",
            "organization_memberships": [{"organization": {"id": "test_company_123"}}]
        }
    
    with patch("app.middleware.tenant.verify_clerk_jwt", side_effect=mock_verify_csr):
        headers = auth_headers_factory(
            tenant_id="test_company_123",
            user_id="test_csr_001",
            org_role="csr"
        )
        response = client.get("/api/v1/metrics/exec/csr/dashboard", headers=headers)
        assert response.status_code == 403


@patch('app.routes.metrics_kpis.MetricsService')
def test_exec_missed_calls_manager_ok(mock_service_class, client, auth_headers_factory, mock_verify_clerk_jwt):
    """Test that manager can access exec missed calls endpoint."""
    from app.schemas.metrics import ExecMissedCallRecoveryMetrics
    
    mock_service = MagicMock()
    mock_service_class.return_value = mock_service
    
    mock_metrics = ExecMissedCallRecoveryMetrics(
        total_missed_calls=None,
        total_saved_calls=None,
        total_saved_by_otto=None,
        booked_leads_count=None,
        pending_leads_count=None,
        dead_leads_count=None
    )
    mock_service.get_exec_missed_call_recovery_metrics = AsyncMock(return_value=mock_metrics)
    
    headers = auth_headers_factory(
        tenant_id="test_company_123",
        user_id="test_manager_001",
        org_role="manager"
    )
    
    response = client.get("/api/v1/metrics/exec/missed-calls", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    
    # Verify response shape
    metrics = data["data"]
    assert "total_missed_calls" in metrics
    assert "total_saved_calls" in metrics
    assert "total_saved_by_otto" in metrics
    assert "booked_leads_count" in metrics
    assert "pending_leads_count" in metrics
    assert "dead_leads_count" in metrics


def test_exec_missed_calls_sales_rep_forbidden(client, auth_headers_factory, mock_verify_clerk_jwt):
    """Test that sales_rep role is forbidden from exec missed calls."""
    def mock_verify_rep(*args, **kwargs):
        return {
            "id": "test_rep_001",
            "org_role": "sales_rep",
            "organization_memberships": [{"organization": {"id": "test_company_123"}}]
        }
    
    with patch("app.middleware.tenant.verify_clerk_jwt", side_effect=mock_verify_rep):
        headers = auth_headers_factory(
            tenant_id="test_company_123",
            user_id="test_rep_001",
            org_role="sales_rep"
        )
        response = client.get("/api/v1/metrics/exec/missed-calls", headers=headers)
        assert response.status_code == 403


@patch('app.routes.metrics_kpis.MetricsService')
def test_exec_sales_team_dashboard_manager_ok(mock_service_class, client, auth_headers_factory, mock_verify_clerk_jwt):
    """Test that manager can access exec sales team dashboard endpoint."""
    from app.schemas.metrics import ExecSalesTeamDashboardMetrics, ExecSalesMetrics, SalesTeamStatsMetrics
    
    mock_service = MagicMock()
    mock_service_class.return_value = mock_service
    
    mock_metrics = ExecSalesTeamDashboardMetrics(
        overview=ExecSalesMetrics(
            total_appointments=0,
            completed_appointments=0,
            won_appointments=0,
            lost_appointments=0,
            pending_appointments=0,
            team_win_rate=None,
            avg_objections_per_appointment=None,
            avg_compliance_score=None,
            avg_meeting_structure_score=None,
            avg_sentiment_score=None
        ),
        team_stats=SalesTeamStatsMetrics(
            total_conversations=None,
            avg_recording_duration_seconds=None,
            followup_rate=None,
            followup_win_rate=None,
            first_touch_win_rate=None,
            team_win_rate=None
        ),
        reps=[],
        top_objections=[]
    )
    mock_service.get_exec_sales_team_dashboard_metrics = AsyncMock(return_value=mock_metrics)
    
    headers = auth_headers_factory(
        tenant_id="test_company_123",
        user_id="test_manager_001",
        org_role="manager"
    )
    
    response = client.get("/api/v1/metrics/exec/sales/dashboard", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    
    # Verify response shape
    metrics = data["data"]
    assert "overview" in metrics
    assert "team_stats" in metrics
    assert "reps" in metrics
    assert "top_objections" in metrics
    
    # Verify overview shape
    overview = metrics["overview"]
    assert "total_appointments" in overview
    assert "won_appointments" in overview
    assert "team_win_rate" in overview
    
    # Verify team_stats shape
    team_stats = metrics["team_stats"]
    assert "total_conversations" in team_stats
    assert "avg_recording_duration_seconds" in team_stats
    assert "followup_rate" in team_stats


def test_exec_sales_team_dashboard_csr_forbidden(client, auth_headers_factory, mock_verify_clerk_jwt):
    """Test that CSR role is forbidden from exec sales team dashboard."""
    def mock_verify_csr(*args, **kwargs):
        return {
            "id": "test_csr_001",
            "org_role": "csr",
            "organization_memberships": [{"organization": {"id": "test_company_123"}}]
        }
    
    with patch("app.middleware.tenant.verify_clerk_jwt", side_effect=mock_verify_csr):
        headers = auth_headers_factory(
            tenant_id="test_company_123",
            user_id="test_csr_001",
            org_role="csr"
        )
        response = client.get("/api/v1/metrics/exec/sales/dashboard", headers=headers)
        assert response.status_code == 403


@patch('app.routes.metrics_kpis.MetricsService')
def test_exec_endpoints_date_params(mock_service_class, client, auth_headers_factory, mock_verify_clerk_jwt):
    """Test that date parameters are parsed correctly."""
    from app.schemas.metrics import ExecCompanyOverviewMetrics, ExecWhoDroppingBall
    
    mock_service = MagicMock()
    mock_service_class.return_value = mock_service
    
    mock_metrics = ExecCompanyOverviewMetrics(
        total_leads=None,
        qualified_leads=None,
        total_appointments=None,
        total_closed_deals=None,
        lead_to_sale_ratio=None,
        close_rate=None,
        sales_output_amount=None,
        win_rate=None,
        pending_rate=None,
        lost_rate=None,
        win_loss_attribution=None,
        who_dropping_ball=ExecWhoDroppingBall(
            worst_csr_id=None,
            worst_csr_name=None,
            worst_csr_booking_rate=None,
            worst_rep_id=None,
            worst_rep_name=None,
            worst_rep_win_rate=None
        )
    )
    mock_service.get_exec_company_overview_metrics = AsyncMock(return_value=mock_metrics)
    
    headers = auth_headers_factory(
        tenant_id="test_company_123",
        user_id="test_manager_001",
        org_role="manager"
    )
    
    date_from = (datetime.utcnow() - timedelta(days=60)).isoformat()
    date_to = datetime.utcnow().isoformat()
    
    response = client.get(
        "/api/v1/metrics/exec/company-overview",
        params={"date_from": date_from, "date_to": date_to},
        headers=headers
    )
    
    assert response.status_code == 200
    # Verify service was called with parsed dates
    mock_service.get_exec_company_overview_metrics.assert_called_once()
    call_args = mock_service.get_exec_company_overview_metrics.call_args[1]
    assert call_args["tenant_id"] == "test_company_123"
    assert call_args["date_from"] is not None
    assert call_args["date_to"] is not None

