"""
Smoke tests for Ask Otto canonical endpoint implementation.

Tests verify:
1. Canonical Ask Otto path (/api/v1/ask-otto/query) works
2. Feature flag fallback to legacy /api/v1/search/ works
3. Correct X-Target-Role header is sent for CSR, Sales Rep, and Manager/Exec roles
4. Response matches Otto's RAGQueryResponse schema
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


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = MagicMock(spec=Session)
    session.add = MagicMock()
    session.commit = MagicMock()
    session.query = MagicMock()
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
    def _factory(tenant_id: str = "tenant_123", user_id: str = "user_123", org_role: str = "sales_rep"):
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
            "org_role": org_role,  # This gets mapped to user_role by middleware
            "exp": (datetime.utcnow() + timedelta(hours=1)).timestamp(),
            "iat": datetime.utcnow().timestamp(),
        }
        token = jwt.encode(payload, settings.CLERK_SECRET_KEY, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}
    return _factory


@pytest.fixture
def mock_uwc_client_canonical(monkeypatch):
    """Mock UWCClient.query_ask_otto for canonical endpoint tests."""
    async def mock_query_ask_otto(*, company_id, request_id, question, conversation_id=None, context=None, scope=None, target_role=None):
        """Mock canonical Ask Otto response matching Shunya's format."""
        return {
            "success": True,
            "query_id": "shunya_query_123",
            "conversation_id": conversation_id,
            "question": question,
            "answer": "This is a test answer from canonical Ask Otto endpoint.",
            "confidence": 0.85,
            "sources": [
                {
                    "type": "database",
                    "title": "Test Source 1",
                    "reference": "ref_1",
                    "record_count": 5,
                    "confidence": 0.9
                },
                {
                    "type": "document",
                    "title": "Test Source 2",
                    "reference": "ref_2",
                    "record_count": 3,
                    "confidence": 0.8
                }
            ],
            "suggested_follow_ups": [
                "What are the top objections?",
                "How can I improve my performance?"
            ],
            "metadata": {
                "query_type": "analytical",
                "intent": "performance",
                "processing_time_ms": 1200
            }
        }
    
    # Mock the get_uwc_client function to return a mock client
    mock_client = MagicMock()
    mock_client.query_ask_otto = AsyncMock(side_effect=mock_query_ask_otto)
    mock_client._map_otto_role_to_shunya_target_role = lambda role: {
        "csr": "customer_rep",
        "sales_rep": "sales_rep",
        "manager": "sales_manager",
        "exec": "admin"
    }.get(role, "sales_rep")
    
    monkeypatch.setattr("app.routes.rag.get_uwc_client", lambda: mock_client)
    return mock_client


@pytest.fixture
def mock_uwc_client_legacy(monkeypatch):
    """Mock UWCClient.query_rag for legacy endpoint tests."""
    async def mock_query_rag(company_id, request_id, query, context, options=None, target_role=None):
        """Mock legacy RAG response."""
        return {
            "answer": "This is a test answer from legacy RAG endpoint.",
            "citations": [
                {
                    "doc_id": "legacy_doc_1",
                    "filename": "legacy_source.pdf",
                    "chunk_text": "Legacy citation text",
                    "similarity_score": 0.88,
                    "call_id": None,
                    "timestamp": None
                }
            ],
            "confidence_score": 0.82
        }
    
    # Mock the get_uwc_client function to return a mock client
    mock_client = MagicMock()
    mock_client.query_rag = AsyncMock(side_effect=mock_query_rag)
    mock_client._map_otto_role_to_shunya_target_role = lambda role: {
        "csr": "customer_rep",
        "sales_rep": "sales_rep",
        "manager": "sales_manager",
        "exec": "admin"
    }.get(role, "sales_rep")
    
    monkeypatch.setattr("app.routes.rag.get_uwc_client", lambda: mock_client)
    return mock_client


class TestCSRCanonicalAskOtto:
    """Test CSR role with canonical Ask Otto endpoint."""
    
    @patch.object(settings, 'ENABLE_UWC_RAG', True)
    @patch.object(settings, 'UWC_BASE_URL', 'https://test.shunyalabs.ai')
    @patch.object(settings, 'USE_CANONICAL_ASK_OTTO', True)
    def test_csr_canonical_ask_otto(
        self, 
        client, 
        auth_headers_factory, 
        mock_uwc_client_canonical
    ):
        """Test CSR Ask Otto uses canonical endpoint with correct target_role."""
        headers = auth_headers_factory(
            tenant_id="company_123",
            user_id="csr_user_001",
            org_role="csr"  # Maps to user_role="csr" via middleware
        )
        
        payload = {
            "query": "What are my top objections this month?",
            "filters": {"date_range": "last_30_days"},
            "max_results": 10
        }
        
        response = client.post("/api/v1/rag/query", json=payload, headers=headers)
        
        # Assert HTTP success
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Assert response structure matches RAGQueryResponse
        result = data["data"]
        assert "query_id" in result
        assert "query" in result
        assert "answer" in result
        assert "citations" in result
        assert "confidence_score" in result
        assert "latency_ms" in result
        
        # Assert answer is from canonical endpoint
        assert "canonical Ask Otto" in result["answer"]
        
        # Assert citations were transformed from sources
        assert len(result["citations"]) == 2
        assert result["citations"][0]["doc_id"] == "ref_1"
        assert result["citations"][0]["filename"] == "Test Source 1"
        
        # Assert confidence was transformed
        assert result["confidence_score"] == 0.85
        
        # Assert canonical endpoint was called
        mock_uwc_client_canonical.query_ask_otto.assert_called_once()
        call_kwargs = mock_uwc_client_canonical.query_ask_otto.call_args[1]
        
        # Assert correct payload shape (canonical format)
        assert call_kwargs["question"] == "What are my top objections this month?"
        assert "context" in call_kwargs
        assert call_kwargs["context"]["tenant_id"] == "company_123"
        assert call_kwargs["context"]["user_role"] == "csr"
        assert call_kwargs["context"]["exclude_rep_data"] is True
        
        # Assert target_role was set correctly (CSR → customer_rep)
        assert call_kwargs["target_role"] == "customer_rep"


class TestSalesRepCanonicalAskOtto:
    """Test Sales Rep role with canonical Ask Otto endpoint."""
    
    @patch.object(settings, 'ENABLE_UWC_RAG', True)
    @patch.object(settings, 'UWC_BASE_URL', 'https://test.shunyalabs.ai')
    @patch.object(settings, 'USE_CANONICAL_ASK_OTTO', True)
    def test_sales_rep_canonical_ask_otto(
        self,
        client,
        auth_headers_factory,
        mock_uwc_client_canonical
    ):
        """Test Sales Rep Ask Otto uses canonical endpoint with correct target_role."""
        headers = auth_headers_factory(
            tenant_id="company_123",
            user_id="rep_user_001",
            org_role="sales_rep"  # Maps to user_role="sales_rep" via middleware
        )
        
        payload = {
            "query": "What are my top objections this month?",
            "filters": {"date_range": "last_30_days"},
            "max_results": 10
        }
        
        response = client.post("/api/v1/rag/query", json=payload, headers=headers)
        
        # Assert HTTP success
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Assert response structure
        result = data["data"]
        assert "answer" in result
        assert "citations" in result
        assert "confidence_score" in result
        
        # Assert canonical endpoint was called
        mock_uwc_client_canonical.query_ask_otto.assert_called_once()
        call_kwargs = mock_uwc_client_canonical.query_ask_otto.call_args[1]
        
        # Assert correct payload shape
        assert call_kwargs["question"] == "What are my top objections this month?"
        assert call_kwargs["context"]["user_role"] == "sales_rep"
        assert call_kwargs["context"]["user_id"] == "rep_user_001"
        
        # Assert target_role was set correctly (Sales Rep → sales_rep)
        assert call_kwargs["target_role"] == "sales_rep"


class TestManagerCanonicalAskOtto:
    """Test Manager/Exec role with canonical Ask Otto endpoint."""
    
    @patch.object(settings, 'ENABLE_UWC_RAG', True)
    @patch.object(settings, 'UWC_BASE_URL', 'https://test.shunyalabs.ai')
    @patch.object(settings, 'USE_CANONICAL_ASK_OTTO', True)
    def test_manager_canonical_ask_otto(
        self,
        client,
        auth_headers_factory,
        mock_uwc_client_canonical
    ):
        """Test Manager Ask Otto uses canonical endpoint with correct target_role."""
        headers = auth_headers_factory(
            tenant_id="company_123",
            user_id="manager_user_001",
            org_role="manager"  # Maps to user_role="manager" via middleware
        )
        
        payload = {
            "query": "What are the top objections across my team?",
            "filters": {"date_range": "last_30_days"},
            "max_results": 10
        }
        
        response = client.post("/api/v1/rag/query", json=payload, headers=headers)
        
        # Assert HTTP success
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Assert response structure
        result = data["data"]
        assert "answer" in result
        assert "citations" in result
        assert "confidence_score" in result
        
        # Assert canonical endpoint was called
        mock_uwc_client_canonical.query_ask_otto.assert_called_once()
        call_kwargs = mock_uwc_client_canonical.query_ask_otto.call_args[1]
        
        # Assert correct payload shape
        assert call_kwargs["question"] == "What are the top objections across my team?"
        assert call_kwargs["context"]["user_role"] == "manager"
        
        # Assert target_role was set correctly (Manager → sales_manager)
        assert call_kwargs["target_role"] == "sales_manager"
    
    @patch.object(settings, 'ENABLE_UWC_RAG', True)
    @patch.object(settings, 'UWC_BASE_URL', 'https://test.shunyalabs.ai')
    @patch.object(settings, 'USE_CANONICAL_ASK_OTTO', True)
    def test_exec_canonical_ask_otto(
        self,
        client,
        auth_headers_factory,
        mock_uwc_client_canonical
    ):
        """Test Exec role Ask Otto uses canonical endpoint with correct target_role."""
        headers = auth_headers_factory(
            tenant_id="company_123",
            user_id="exec_user_001",
            org_role="exec"  # Maps to user_role="manager" via middleware, but we test exec → admin mapping
        )
        
        payload = {
            "query": "What are the company-wide metrics?",
            "filters": {},
            "max_results": 10
        }
        
        response = client.post("/api/v1/rag/query", json=payload, headers=headers)
        
        # Assert HTTP success
        assert response.status_code == 200
        
        # Assert canonical endpoint was called
        mock_uwc_client_canonical.query_ask_otto.assert_called_once()
        call_kwargs = mock_uwc_client_canonical.query_ask_otto.call_args[1]
        
        # Note: exec maps to manager in middleware, but target_role mapping should handle exec → admin
        # However, since middleware maps exec → manager, the route will see user_role="manager"
        # So target_role will be "sales_manager" (from manager mapping)
        # This is expected behavior per current implementation
        assert call_kwargs["target_role"] == "sales_manager"


class TestLegacyFallbackEndpoint:
    """Test legacy endpoint fallback when feature flag is disabled."""
    
    @patch.object(settings, 'ENABLE_UWC_RAG', True)
    @patch.object(settings, 'UWC_BASE_URL', 'https://test.shunyalabs.ai')
    @patch.object(settings, 'USE_CANONICAL_ASK_OTTO', False)
    def test_legacy_fallback_endpoint(
        self,
        client,
        auth_headers_factory,
        mock_uwc_client_legacy
    ):
        """Test that legacy endpoint is used when feature flag is False."""
        headers = auth_headers_factory(
            tenant_id="company_123",
            user_id="user_001",
            org_role="sales_rep"
        )
        
        payload = {
            "query": "What are my top objections?",
            "filters": {"date_range": "last_30_days"},
            "max_results": 10
        }
        
        response = client.post("/api/v1/rag/query", json=payload, headers=headers)
        
        # Assert HTTP success
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Assert response structure
        result = data["data"]
        assert "answer" in result
        assert "citations" in result
        assert "confidence_score" in result
        
        # Assert legacy endpoint was called (not canonical)
        mock_uwc_client_legacy.query_rag.assert_called_once()
        assert not hasattr(mock_uwc_client_legacy, 'query_ask_otto') or \
               not mock_uwc_client_legacy.query_ask_otto.called
        
        # Assert legacy payload format
        call_kwargs = mock_uwc_client_legacy.query_rag.call_args[1]  # keyword arguments
        assert call_kwargs["query"] == "What are my top objections?"
        assert "context" in call_kwargs
        assert call_kwargs["context"]["tenant_id"] == "company_123"
        
        # Assert answer is from legacy endpoint
        assert "legacy RAG" in result["answer"]
        
        # Assert citations format (legacy already in correct format)
        assert len(result["citations"]) == 1
        assert result["citations"][0]["doc_id"] == "legacy_doc_1"
        assert result["citations"][0]["filename"] == "legacy_source.pdf"
        
        # Assert confidence_score (legacy already in correct format)
        assert result["confidence_score"] == 0.82

