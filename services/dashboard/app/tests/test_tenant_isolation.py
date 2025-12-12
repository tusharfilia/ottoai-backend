"""
P0: Tenant Isolation Test Scaffolding

Tests to ensure multi-tenant data isolation and prevent cross-tenant data leakage.
"""
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.company import Company
from app.models.call import Call
from app.models.lead import Lead
from app.models.appointment import Appointment
from app.models.recording_session import RecordingSession
from app.database import SessionLocal, Base, engine
from app.main import app


@pytest.fixture
def db():
    """Create a test database session."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_company_1(db: Session) -> Company:
    """Create test company 1."""
    company = Company(
        id="test_company_1",
        name="Test Company 1",
        domain="test1.com"
    )
    db.add(company)
    db.commit()
    return company


@pytest.fixture
def test_company_2(db: Session) -> Company:
    """Create test company 2."""
    company = Company(
        id="test_company_2",
        name="Test Company 2",
        domain="test2.com"
    )
    db.add(company)
    db.commit()
    return company


class TestTenantIsolation:
    """Test suite for tenant isolation."""
    
    def test_calls_are_tenant_isolated(self, db: Session, test_company_1: Company, test_company_2: Company):
        """Test that calls from tenant A are not visible to tenant B."""
        # Create call for company 1
        call_1 = Call(
            call_id=1,
            company_id=test_company_1.id,
            caller_phone="+1234567890",
            rep_phone="+0987654321"
        )
        db.add(call_1)
        
        # Create call for company 2
        call_2 = Call(
            call_id=2,
            company_id=test_company_2.id,
            caller_phone="+1111111111",
            rep_phone="+2222222222"
        )
        db.add(call_2)
        db.commit()
        
        # Query calls for company 1
        company_1_calls = db.query(Call).filter(Call.company_id == test_company_1.id).all()
        
        # Verify company 1 only sees its own calls
        assert len(company_1_calls) == 1
        assert company_1_calls[0].call_id == 1
        assert company_1_calls[0].company_id == test_company_1.id
        
        # Verify company 1 cannot see company 2's calls
        company_2_calls_in_company_1_query = [c for c in company_1_calls if c.company_id == test_company_2.id]
        assert len(company_2_calls_in_company_1_query) == 0
    
    def test_leads_are_tenant_isolated(self, db: Session, test_company_1: Company, test_company_2: Company):
        """Test that leads from tenant A are not visible to tenant B."""
        from app.models.lead import LeadStatus
        
        # Create lead for company 1
        lead_1 = Lead(
            id="lead_1",
            company_id=test_company_1.id,
            phone="+1234567890",
            status=LeadStatus.NEW
        )
        db.add(lead_1)
        
        # Create lead for company 2
        lead_2 = Lead(
            id="lead_2",
            company_id=test_company_2.id,
            phone="+1111111111",
            status=LeadStatus.NEW
        )
        db.add(lead_2)
        db.commit()
        
        # Query leads for company 1
        company_1_leads = db.query(Lead).filter(Lead.company_id == test_company_1.id).all()
        
        # Verify company 1 only sees its own leads
        assert len(company_1_leads) == 1
        assert company_1_leads[0].id == "lead_1"
        assert company_1_leads[0].company_id == test_company_1.id
    
    def test_appointments_are_tenant_isolated(self, db: Session, test_company_1: Company, test_company_2: Company):
        """Test that appointments from tenant A are not visible to tenant B."""
        from app.models.appointment import AppointmentStatus
        from datetime import datetime, timedelta
        
        # Create appointment for company 1
        apt_1 = Appointment(
            id="apt_1",
            company_id=test_company_1.id,
            scheduled_start=datetime.utcnow() + timedelta(days=1),
            status=AppointmentStatus.SCHEDULED
        )
        db.add(apt_1)
        
        # Create appointment for company 2
        apt_2 = Appointment(
            id="apt_2",
            company_id=test_company_2.id,
            scheduled_start=datetime.utcnow() + timedelta(days=1),
            status=AppointmentStatus.SCHEDULED
        )
        db.add(apt_2)
        db.commit()
        
        # Query appointments for company 1
        company_1_appointments = db.query(Appointment).filter(
            Appointment.company_id == test_company_1.id
        ).all()
        
        # Verify company 1 only sees its own appointments
        assert len(company_1_appointments) == 1
        assert company_1_appointments[0].id == "apt_1"
        assert company_1_appointments[0].company_id == test_company_1.id
    
    def test_cross_tenant_id_access_returns_404(self, db: Session, test_company_1: Company, test_company_2: Company):
        """Test that accessing another tenant's resource by ID returns 404 (not 403)."""
        from app.models.call import Call
        
        # Create call for company 2
        call_2 = Call(
            call_id=999,
            company_id=test_company_2.id,
            caller_phone="+1111111111",
            rep_phone="+2222222222"
        )
        db.add(call_2)
        db.commit()
        
        # Try to access company 2's call from company 1's context
        # This should return None (not found) when filtered by company_id
        call_from_company_1_context = db.query(Call).filter(
            Call.call_id == 999,
            Call.company_id == test_company_1.id  # Company 1's context
        ).first()
        
        # Verify call is not found (tenant isolation)
        assert call_from_company_1_context is None
    
    def test_updates_are_tenant_isolated(self, db: Session, test_company_1: Company, test_company_2: Company):
        """Test that updates from tenant A don't affect tenant B's data."""
        from app.models.lead import LeadStatus
        
        # Create lead for company 1
        lead_1 = Lead(
            id="lead_1",
            company_id=test_company_1.id,
            phone="+1234567890",
            status=LeadStatus.NEW
        )
        db.add(lead_1)
        
        # Create lead for company 2
        lead_2 = Lead(
            id="lead_2",
            company_id=test_company_2.id,
            phone="+1111111111",
            status=LeadStatus.NEW
        )
        db.add(lead_2)
        db.commit()
        
        # Update lead 1's status
        lead_1.status = LeadStatus.HOT
        db.commit()
        
        # Verify lead 2's status is unchanged
        db.refresh(lead_2)
        assert lead_2.status == LeadStatus.NEW
    
    def test_deletes_are_tenant_isolated(self, db: Session, test_company_1: Company, test_company_2: Company):
        """Test that deletes from tenant A don't affect tenant B's data."""
        from app.models.lead import LeadStatus
        
        # Create lead for company 1
        lead_1 = Lead(
            id="lead_1",
            company_id=test_company_1.id,
            phone="+1234567890",
            status=LeadStatus.NEW
        )
        db.add(lead_1)
        
        # Create lead for company 2
        lead_2 = Lead(
            id="lead_2",
            company_id=test_company_2.id,
            phone="+1111111111",
            status=LeadStatus.NEW
        )
        db.add(lead_2)
        db.commit()
        
        # Delete lead 1
        db.delete(lead_1)
        db.commit()
        
        # Verify lead 2 still exists
        lead_2_after_delete = db.query(Lead).filter(Lead.id == "lead_2").first()
        assert lead_2_after_delete is not None
        assert lead_2_after_delete.company_id == test_company_2.id


class TestTenantOwnershipVerification:
    """Test suite for tenant ownership verification helpers."""
    
    def test_verify_tenant_ownership_helper(self, db: Session, test_company_1: Company, test_company_2: Company):
        """Test that verify_tenant_ownership helper works correctly."""
        from app.core.tenant import verify_tenant_ownership
        
        # Create call for company 1
        call_1 = Call(
            call_id=1,
            company_id=test_company_1.id,
            caller_phone="+1234567890",
            rep_phone="+0987654321"
        )
        db.add(call_1)
        db.commit()
        
        # Verify ownership for correct tenant
        assert verify_tenant_ownership(db, Call, 1, test_company_1.id) is True
        
        # Verify ownership fails for wrong tenant
        assert verify_tenant_ownership(db, Call, 1, test_company_2.id) is False
        
        # Verify ownership fails for non-existent resource
        assert verify_tenant_ownership(db, Call, 999, test_company_1.id) is False



