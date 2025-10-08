"""
Tests for B001: Tenant validation middleware audit + cross-tenant unit tests.
Ensures all data access paths enforce {tenant_id} (reads & writes).
Negative tests proving cross-tenant access is blocked.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models import user, company, call
from app.database import get_db, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import jwt
from datetime import datetime, timedelta
from app.config import settings

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_tenant_validation.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client(db_session):
    """Create test client with database override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def tenant_factory():
    """Factory for generating unique tenant IDs."""
    def _factory(prefix="tenant"):
        return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    return _factory

@pytest.fixture
def auth_headers_factory():
    """Factory for generating auth headers with tenant context."""
    def _factory(tenant_id: str, user_id: str = "user_123", role: str = "rep"):
        # Create a mock JWT token
        payload = {
            "sub": user_id,
            "user_id": user_id,
            "org_id": tenant_id,
            "org_role": role,
            "exp": (datetime.utcnow() + timedelta(hours=1)).timestamp(),
            "iat": datetime.utcnow().timestamp(),
        }
        token = jwt.encode(payload, settings.CLERK_SECRET_KEY, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}
    return _factory


class TestTenantValidation:
    """Test suite for tenant validation and cross-tenant access prevention."""
    
    def test_missing_auth_header_returns_403(self, client):
        """Test that requests without Authorization header are rejected."""
        response = client.get("/api/v1/users/")
        assert response.status_code == 403
        assert "Missing or invalid tenant_id" in response.json()["detail"] or "Authorization" in response.json()["detail"]
    
    def test_invalid_token_returns_403(self, client):
        """Test that requests with invalid tokens are rejected."""
        headers = {"Authorization": "Bearer invalid_token_xyz"}
        response = client.get("/api/v1/users/", headers=headers)
        assert response.status_code == 403
    
    def test_valid_token_with_tenant_context_succeeds(self, client, auth_headers_factory, tenant_factory):
        """Test that valid tokens with tenant context are accepted."""
        tenant_id = tenant_factory()
        headers = auth_headers_factory(tenant_id)
        
        # This should succeed (even if it returns 404 for no data)
        response = client.get("/api/v1/users/", headers=headers)
        assert response.status_code in [200, 404]  # Either success or not found
    
    def test_cross_tenant_user_access_blocked(self, client, db_session, auth_headers_factory, tenant_factory):
        """Test that users cannot access data from other tenants."""
        tenant1_id = tenant_factory("tenant1")
        tenant2_id = tenant_factory("tenant2")
        
        # Create companies for both tenants
        company1 = company.Company(
            id=tenant1_id,
            name="Company 1",
            phone_number="+1234567890"
        )
        company2 = company.Company(
            id=tenant2_id,
            name="Company 2",
            phone_number="+1234567891"
        )
        db_session.add_all([company1, company2])
        db_session.commit()
        
        # Create users in each tenant
        user1 = user.User(
            name="User 1",
            email="user1@company1.com",
            username="user1",
            company_id=tenant1_id,
            role="rep"
        )
        user2 = user.User(
            name="User 2",
            email="user2@company2.com",
            username="user2",
            company_id=tenant2_id,
            role="rep"
        )
        db_session.add_all([user1, user2])
        db_session.commit()
        
        # Tenant 1 user tries to access their own data - should succeed
        headers1 = auth_headers_factory(tenant1_id, user_id=str(user1.id))
        response = client.get("/api/v1/users/", headers=headers1)
        assert response.status_code == 200
        users_data = response.json()
        # Should only see user1, not user2
        assert len([u for u in users_data if u["company_id"] == tenant1_id]) >= 1
        assert len([u for u in users_data if u["company_id"] == tenant2_id]) == 0
        
        # Tenant 2 user tries to access their own data - should succeed
        headers2 = auth_headers_factory(tenant2_id, user_id=str(user2.id))
        response = client.get("/api/v1/users/", headers=headers2)
        assert response.status_code == 200
        users_data = response.json()
        # Should only see user2, not user1
        assert len([u for u in users_data if u["company_id"] == tenant2_id]) >= 1
        assert len([u for u in users_data if u["company_id"] == tenant1_id]) == 0
    
    def test_cross_tenant_call_access_blocked(self, client, db_session, auth_headers_factory, tenant_factory):
        """Test that calls are properly scoped by tenant."""
        tenant1_id = tenant_factory("tenant1")
        tenant2_id = tenant_factory("tenant2")
        
        # Create companies
        company1 = company.Company(id=tenant1_id, name="Company 1", phone_number="+1234567890")
        company2 = company.Company(id=tenant2_id, name="Company 2", phone_number="+1234567891")
        db_session.add_all([company1, company2])
        db_session.commit()
        
        # Create calls for each tenant
        call1 = call.Call(
            call_id="call1",
            company_id=tenant1_id,
            direction="inbound",
            customer_phone_number="+1111111111"
        )
        call2 = call.Call(
            call_id="call2",
            company_id=tenant2_id,
            direction="inbound",
            customer_phone_number="+2222222222"
        )
        db_session.add_all([call1, call2])
        db_session.commit()
        
        # Tenant 1 tries to access calls - should only see call1
        headers1 = auth_headers_factory(tenant1_id)
        response = client.get("/api/v1/calls/", headers=headers1)
        assert response.status_code == 200
        calls_data = response.json()
        call_ids = [c["call_id"] for c in calls_data]
        assert "call1" in call_ids
        assert "call2" not in call_ids
        
        # Tenant 2 tries to access calls - should only see call2
        headers2 = auth_headers_factory(tenant2_id)
        response = client.get("/api/v1/calls/", headers=headers2)
        assert response.status_code == 200
        calls_data = response.json()
        call_ids = [c["call_id"] for c in calls_data]
        assert "call2" in call_ids
        assert "call1" not in call_ids
    
    def test_tenant_scoped_session_filters_queries(self, db_session, tenant_factory):
        """Test that TenantScopedSession automatically filters queries."""
        from app.database import TenantScopedSession
        
        tenant1_id = tenant_factory("tenant1")
        tenant2_id = tenant_factory("tenant2")
        
        # Create companies
        company1 = company.Company(id=tenant1_id, name="Company 1", phone_number="+1234567890")
        company2 = company.Company(id=tenant2_id, name="Company 2", phone_number="+1234567891")
        db_session.add_all([company1, company2])
        db_session.commit()
        
        # Create calls for each tenant
        call1 = call.Call(call_id="call1", company_id=tenant1_id, direction="inbound")
        call2 = call.Call(call_id="call2", company_id=tenant2_id, direction="inbound")
        db_session.add_all([call1, call2])
        db_session.commit()
        
        # Create tenant-scoped session for tenant1
        tenant1_session = TenantScopedSession(tenant1_id, bind=engine)
        calls = tenant1_session.query(call.Call).all()
        tenant1_session.close()
        
        # Should only see call1
        assert len(calls) == 1
        assert calls[0].call_id == "call1"
        
        # Create tenant-scoped session for tenant2
        tenant2_session = TenantScopedSession(tenant2_id, bind=engine)
        calls = tenant2_session.query(call.Call).all()
        tenant2_session.close()
        
        # Should only see call2
        assert len(calls) == 1
        assert calls[0].call_id == "call2"
    
    def test_company_creation_validates_tenant(self, client, auth_headers_factory, tenant_factory):
        """Test that company creation validates tenant ownership."""
        tenant_id = tenant_factory()
        headers = auth_headers_factory(tenant_id, role="exec")
        
        # Try to create a company with matching tenant_id - should succeed
        response = client.post(
            "/api/v1/companies/",
            headers=headers,
            json={
                "name": "Test Company",
                "phone_number": "+1234567890",
                "id": tenant_id
            }
        )
        # Should succeed or return validation error (but not 403)
        assert response.status_code in [200, 201, 400, 422]
        
        # Try to create a company with different tenant_id - should fail
        other_tenant_id = tenant_factory("other")
        response = client.post(
            "/api/v1/companies/",
            headers=headers,
            json={
                "name": "Other Company",
                "phone_number": "+1234567891",
                "id": other_tenant_id
            }
        )
        # Should be rejected with 403
        assert response.status_code == 403


class TestTenantScopingEdgeCases:
    """Test edge cases and boundary conditions for tenant scoping."""
    
    def test_health_endpoint_skips_tenant_validation(self, client):
        """Test that health endpoints don't require authentication."""
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_metrics_endpoint_skips_tenant_validation(self, client):
        """Test that metrics endpoints don't require authentication."""
        response = client.get("/metrics")
        assert response.status_code == 200
    
    def test_expired_token_returns_403(self, client, tenant_factory):
        """Test that expired tokens are rejected."""
        tenant_id = tenant_factory()
        
        # Create an expired token
        payload = {
            "sub": "user_123",
            "org_id": tenant_id,
            "org_role": "rep",
            "exp": (datetime.utcnow() - timedelta(hours=1)).timestamp(),  # Expired
            "iat": (datetime.utcnow() - timedelta(hours=2)).timestamp(),
        }
        token = jwt.encode(payload, settings.CLERK_SECRET_KEY, algorithm="HS256")
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get("/api/v1/users/", headers=headers)
        assert response.status_code == 403

