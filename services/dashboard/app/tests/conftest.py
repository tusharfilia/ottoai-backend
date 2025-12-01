"""
Test configuration and fixtures for foundation validation tests.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock
import os
import tempfile

# Import the FastAPI app
from app.main import app
from app.database import get_db, Base
from app.config import settings

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def test_db():
    """Create test database tables."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(test_db):
    """Create a fresh database session for each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def client(db_session):
    """Create test client with database session override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

@pytest.fixture
def tenant_id():
    """Generate a test tenant ID."""
    return "test_tenant_123"

@pytest.fixture
def auth_headers_exec(tenant_id):
    """Mock auth headers for executive role."""
    return {
        "Authorization": "Bearer mock_jwt_token",
        "X-Tenant-ID": tenant_id,
        "X-User-Role": "executive"
    }

@pytest.fixture
def auth_headers_manager(tenant_id):
    """Mock auth headers for manager role."""
    return {
        "Authorization": "Bearer mock_jwt_token", 
        "X-Tenant-ID": tenant_id,
        "X-User-Role": "manager"
    }

@pytest.fixture
def auth_headers_csr(tenant_id):
    """Mock auth headers for CSR role."""
    return {
        "Authorization": "Bearer mock_jwt_token",
        "X-Tenant-ID": tenant_id,
        "X-User-Role": "csr"
    }

@pytest.fixture
def auth_headers_rep(tenant_id):
    """Mock auth headers for sales rep role."""
    return {
        "Authorization": "Bearer mock_jwt_token",
        "X-Tenant-ID": tenant_id,
        "X-User-Role": "rep"
    }

@pytest.fixture
def mock_auth():
    """Mock authentication dependency."""
    with patch('app.middleware.tenant.get_current_user') as mock:
        mock.return_value = {
            "tenant_id": "test_tenant_123",
            "user_id": "test_user_123", 
            "role": "executive"
        }
        yield mock

@pytest.fixture
def audit_log():
    """Capture audit log entries for testing."""
    log_entries = []
    
    def mock_audit_log(tenant_id, user_id, action, details=None):
        log_entries.append({
            "tenant_id": tenant_id,
            "user_id": user_id,
            "action": action,
            "details": details,
            "timestamp": "2025-09-22T13:50:00Z"
        })
    
    with patch('app.utils.audit_test_shim.log_audit', side_effect=mock_audit_log):
        yield log_entries

@pytest.fixture
def mock_twilio():
    """Mock Twilio client to prevent actual SMS sends."""
    with patch('app.services.twilio_service.send_sms') as mock:
        mock.return_value = {"status": "sent", "sid": "mock_sid"}
        yield mock

@pytest.fixture
def mock_redis():
    """Mock Redis client for rate limiting tests."""
    with patch('app.middleware.rate_limiter.redis_client') as mock:
        mock.get.return_value = None
        mock.setex.return_value = True
        yield mock


# Import event capture fixture from fixtures module
from app.tests.fixtures.event_capture import event_capture

__all__ = [
    "test_db",
    "db_session",
    "client",
    "tenant_id",
    "auth_headers_exec",
    "auth_headers_manager",
    "auth_headers_csr",
    "auth_headers_rep",
    "mock_auth",
    "audit_log",
    "mock_twilio",
    "mock_redis",
    "event_capture",
]


# Import event capture fixture from fixtures module
from app.tests.fixtures.event_capture import event_capture

__all__ = [
    "test_db",
    "db_session",
    "client",
    "tenant_id",
    "auth_headers_exec",
    "auth_headers_manager",
    "auth_headers_csr",
    "auth_headers_rep",
    "mock_auth",
    "audit_log",
    "mock_twilio",
    "mock_redis",
    "event_capture",
]


# Import event capture fixture from fixtures module
from app.tests.fixtures.event_capture import event_capture

__all__ = [
    "test_db",
    "db_session",
    "client",
    "tenant_id",
    "auth_headers_exec",
    "auth_headers_manager",
    "auth_headers_csr",
    "auth_headers_rep",
    "mock_auth",
    "audit_log",
    "mock_twilio",
    "mock_redis",
    "event_capture",
]
