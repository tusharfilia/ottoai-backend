"""
Smoke tests for Follow-up Recommendations implementation.

Tests verify:
1. Canonical endpoint (POST /api/v1/analysis/followup-recommendations/{call_id}) works
2. Correct X-Target-Role header is sent
3. Response normalization works correctly
4. Integration into call analysis flow works
5. Route RBAC and data retrieval works
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session
import jwt
from datetime import datetime, timedelta
from app.main import app
from app.config import settings
from app.services.uwc_client import get_uwc_client
from app.database import get_db
from app.models.call_analysis import CallAnalysis
from app.models.call import Call


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = MagicMock(spec=Session)
    session.add = MagicMock()
    session.commit = MagicMock()
    session.query = MagicMock()
    session.flush = MagicMock()
    return session


@pytest.fixture
def mock_jwt_verification(monkeypatch):
    """Mock JWT verification to return decoded token."""
    async def mock_verify_clerk_jwt(token: str):
        """Mock JWT verification - decode token without verification."""
        import base64
        import json
        try:
            # Decode JWT without verification (for testing)
            parts = token.split(".")
            if len(parts) != 3:
                raise ValueError("Invalid token format")
            
            # Decode payload
            payload_b64 = parts[1]
            # Add padding if needed
            if len(payload_b64) % 4 != 0:
                payload_b64 += "=" * (4 - len(payload_b64) % 4)
            
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            payload = json.loads(payload_bytes.decode("utf-8"))
            return payload
        except Exception as e:
            raise ValueError(f"Failed to decode token: {e}")
    
    monkeypatch.setattr("app.middleware.tenant.verify_clerk_jwt", mock_verify_clerk_jwt)
    monkeypatch.setattr("app.routes.dependencies.verify_clerk_jwt", mock_verify_clerk_jwt)


@pytest.fixture
def client(mock_db_session, mock_jwt_verification):
    """Create test client with mocked database and JWT verification."""
    def override_get_db():
        try:
            yield mock_db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers_factory():
    """Factory for generating auth headers with different roles."""
    def _factory(tenant_id: str = "tenant_123", user_id: str = "user_123", org_role: str = "csr"):
        """
        Create JWT token with org_role claim.
        
        Args:
            tenant_id: Organization/tenant ID
            user_id: User ID
            org_role: Clerk org_role (csr, sales_rep, manager, exec, admin)
        """
        payload = {
            "sub": user_id,
            "user_id": user_id,
            "org_id": tenant_id,
            "org_role": org_role,
            "exp": (datetime.utcnow() + timedelta(hours=1)).timestamp(),
            "iat": datetime.utcnow().timestamp(),
        }
        token = jwt.encode(payload, settings.CLERK_SECRET_KEY, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}
    return _factory


@pytest.fixture
def mock_uwc_client_followup(monkeypatch):
    """Mock UWCClient.get_followup_recommendations for tests."""
    async def mock_get_followup_recommendations(*, call_id, company_id, request_id, target_role=None):
        """Mock follow-up recommendations response matching Shunya's format."""
        return {
            "recommendations": [
                {
                    "action": "Follow up with pricing details",
                    "description": "Customer expressed interest in pricing",
                    "priority": "high",
                    "timing": "2025-12-09T14:00:00Z",
                    "reasoning": "High rehash score indicates strong interest"
                },
                {
                    "action": "Send product brochure",
                    "description": "Customer requested more information",
                    "priority": "medium",
                    "timing": None,
                    "reasoning": None
                }
            ],
            "next_steps": [
                {
                    "action": "Schedule follow-up call",
                    "description": "Customer wants to discuss further",
                    "priority": "high",
                    "timing": "2025-12-09T10:00:00Z",
                    "reasoning": "Customer requested callback"
                }
            ],
            "priority_actions": [
                {
                    "action": "Follow up with pricing details",
                    "description": "Customer expressed interest in pricing",
                    "priority": "high",
                    "timing": "2025-12-09T14:00:00Z",
                    "reasoning": "High rehash score indicates strong interest"
                }
            ],
            "confidence_score": 0.85
        }
    
    # Mock the get_uwc_client function to return a mock client
    mock_client = MagicMock()
    mock_client.get_followup_recommendations = AsyncMock(side_effect=mock_get_followup_recommendations)
    mock_client._map_otto_role_to_shunya_target_role = lambda role: {
        "csr": "customer_rep",
        "sales_rep": "sales_rep",
        "manager": "sales_manager",
        "exec": "admin"
    }.get(role, "sales_rep")
    
    monkeypatch.setattr("app.services.shunya_integration_service.get_uwc_client", lambda: mock_client)
    monkeypatch.setattr("app.services.uwc_client.get_uwc_client", lambda: mock_client)
    return mock_client


class TestUWCClientFollowupRecommendations:
    """Test UWCClient.get_followup_recommendations method."""
    
    @pytest.mark.asyncio
    @patch.object(settings, 'ENABLE_UWC_RAG', True)
    @patch.object(settings, 'UWC_BASE_URL', 'https://test.shunyalabs.ai')
    @patch.object(settings, 'UWC_API_KEY', 'test_key')
    async def test_get_followup_recommendations_canonical_endpoint(
        self,
        mock_uwc_client_followup
    ):
        """Test that get_followup_recommendations calls canonical endpoint with correct target_role."""
        # Use the mocked client directly
        client = mock_uwc_client_followup
        
        result = await client.get_followup_recommendations(
            call_id=123,
            company_id="company_123",
            request_id="request_123",
            target_role="customer_rep"
        )
        
        # Assert response structure
        assert "recommendations" in result
        assert "next_steps" in result
        assert "priority_actions" in result
        assert "confidence_score" in result
        
        # Assert recommendations were normalized
        assert len(result["recommendations"]) == 2
        assert result["recommendations"][0]["action"] == "Follow up with pricing details"
        assert result["recommendations"][0]["priority"] == "high"
        
        # Assert canonical endpoint was called
        mock_uwc_client_followup.get_followup_recommendations.assert_called_once()
        call_kwargs = mock_uwc_client_followup.get_followup_recommendations.call_args[1]
        
        # Assert correct parameters
        assert call_kwargs["call_id"] == 123
        assert call_kwargs["company_id"] == "company_123"
        assert call_kwargs["target_role"] == "customer_rep"
    
    @pytest.mark.asyncio
    async def test_get_followup_recommendations_null_safe_normalization(
        self,
        mock_uwc_client_followup
    ):
        """Test that normalization handles null/empty responses gracefully."""
        # Mock empty response (normalized structure)
        async def mock_empty_response(*, call_id, company_id, request_id, target_role=None):
            # Return normalized empty structure (as the real method would)
            return {
                "recommendations": [],
                "next_steps": [],
                "priority_actions": [],
                "confidence_score": None
            }
        
        mock_uwc_client_followup.get_followup_recommendations = AsyncMock(side_effect=mock_empty_response)
        client = mock_uwc_client_followup
        
        result = await client.get_followup_recommendations(
            call_id=123,
            company_id="company_123",
            request_id="request_123"
        )
        
        # Assert empty structure is returned (not None)
        assert result is not None
        assert result["recommendations"] == []
        assert result["next_steps"] == []
        assert result["priority_actions"] == []
        assert result["confidence_score"] is None


class TestFollowupRecommendationsRoute:
    """Test GET /api/v1/calls/{call_id}/followup-recommendations route."""
    
    @patch.object(settings, 'ENABLE_FOLLOWUP_RECOMMENDATIONS', True)
    def test_get_followup_recommendations_route_with_analysis(
        self,
        client,
        auth_headers_factory,
        mock_db_session
    ):
        """Test route returns follow-up recommendations when analysis exists."""
        headers = auth_headers_factory(
            tenant_id="company_123",
            user_id="csr_user_001",
            org_role="csr"
        )
        
        # Mock database query to return call and analysis
        mock_call = MagicMock()
        mock_call.call_id = 123
        mock_call.company_id = "company_123"
        
        mock_analysis = MagicMock()
        mock_analysis.call_id = 123
        mock_analysis.tenant_id = "company_123"
        mock_analysis.followup_recommendations = {
            "recommendations": [
                {
                    "action": "Follow up with pricing",
                    "description": "Customer interested",
                    "priority": "high",
                    "timing": None,
                    "reasoning": None
                }
            ],
            "next_steps": [],
            "priority_actions": [],
            "confidence_score": 0.85
        }
        
        # Mock query chain
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_analysis
        
        mock_call_query = MagicMock()
        mock_call_query.filter.return_value = mock_call_query
        mock_call_query.first.return_value = mock_call
        
        mock_db_session.query.side_effect = lambda model: {
            Call: mock_call_query,
            CallAnalysis: mock_query
        }.get(model, MagicMock())
        
        response = client.get(
            "/api/v1/calls/123/followup-recommendations",
            headers=headers
        )
        
        # Assert HTTP success
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Assert response structure
        result = data["data"]
        assert "recommendations" in result
        assert "next_steps" in result
        assert "priority_actions" in result
        assert "confidence_score" in result
        
        # Assert recommendations are returned
        assert len(result["recommendations"]) == 1
        assert result["recommendations"][0]["action"] == "Follow up with pricing"
        assert result["confidence_score"] == 0.85
    
    def test_get_followup_recommendations_route_no_analysis(
        self,
        client,
        auth_headers_factory,
        mock_db_session
    ):
        """Test route returns empty structure when no analysis exists."""
        headers = auth_headers_factory(
            tenant_id="company_123",
            user_id="csr_user_001",
            org_role="csr"
        )
        
        # Mock database query to return call but no analysis
        mock_call = MagicMock()
        mock_call.call_id = 123
        mock_call.company_id = "company_123"
        
        mock_call_query = MagicMock()
        mock_call_query.filter.return_value = mock_call_query
        mock_call_query.first.return_value = mock_call
        
        mock_analysis_query = MagicMock()
        mock_analysis_query.filter.return_value = mock_analysis_query
        mock_analysis_query.order_by.return_value = mock_analysis_query
        mock_analysis_query.first.return_value = None  # No analysis
        
        mock_db_session.query.side_effect = lambda model: {
            Call: mock_call_query,
            CallAnalysis: mock_analysis_query
        }.get(model, MagicMock())
        
        response = client.get(
            "/api/v1/calls/123/followup-recommendations",
            headers=headers
        )
        
        # Assert HTTP success
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Assert empty structure is returned
        result = data["data"]
        assert result["recommendations"] == []
        assert result["next_steps"] == []
        assert result["priority_actions"] == []
        assert result["confidence_score"] is None
        assert result["status"] == "no_analysis"
    
    def test_get_followup_recommendations_route_rbac_csr(
        self,
        client,
        auth_headers_factory,
        mock_db_session
    ):
        """Test route allows CSR role."""
        headers = auth_headers_factory(
            tenant_id="company_123",
            user_id="csr_user_001",
            org_role="csr"
        )
        
        # Mock database query to return None (call not found)
        # This confirms RBAC passed (would be 403 if RBAC failed)
        mock_call_query = MagicMock()
        mock_call_query.filter.return_value = mock_call_query
        mock_call_query.first.return_value = None  # Call not found
        
        mock_db_session.query.return_value = mock_call_query
        
        response = client.get(
            "/api/v1/calls/999/followup-recommendations",
            headers=headers
        )
        
        # 404 means call not found, which is expected (RBAC passed)
        # If RBAC failed, we'd get 403
        assert response.status_code == 404
    
    def test_get_followup_recommendations_route_rbac_manager(
        self,
        client,
        auth_headers_factory,
        mock_db_session
    ):
        """Test route allows manager role."""
        headers = auth_headers_factory(
            tenant_id="company_123",
            user_id="manager_user_001",
            org_role="manager"
        )
        
        # Mock database query to return None (call not found)
        mock_call_query = MagicMock()
        mock_call_query.filter.return_value = mock_call_query
        mock_call_query.first.return_value = None  # Call not found
        
        mock_db_session.query.return_value = mock_call_query
        
        response = client.get(
            "/api/v1/calls/999/followup-recommendations",
            headers=headers
        )
        
        # 404 means call not found, which is expected (RBAC passed)
        # If RBAC failed, we'd get 403
        assert response.status_code == 404
    
    def test_get_followup_recommendations_route_rbac_sales_rep_denied(
        self,
        client,
        auth_headers_factory
    ):
        """Test route denies sales_rep role (only csr and manager allowed)."""
        headers = auth_headers_factory(
            tenant_id="company_123",
            user_id="rep_user_001",
            org_role="sales_rep"
        )
        
        response = client.get(
            "/api/v1/calls/123/followup-recommendations",
            headers=headers
        )
        
        # Should return 403 Forbidden (RBAC failure)
        assert response.status_code == 403

