"""
CRITICAL: Tests for _derive_outcome() fix - must use Shunya data only, no inference.

These tests verify the fix for semantic inference violation:
- Must return None when Shunya data is missing (no inference from appointments/leads)
- Must use CallAnalysis.call_outcome_category when available
- Must use RecordingAnalysis.outcome when available
"""
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.call import Call
from app.models.call_analysis import CallAnalysis
from app.models.lead import Lead, LeadStatus, LeadSource
from app.models.appointment import Appointment, AppointmentOutcome, AppointmentStatus
from app.models.recording_analysis import RecordingAnalysis
from app.models.company import Company
from app.models.contact_card import ContactCard
from app.models.enums import CallOutcomeCategory
from app.config import settings
import json

client = TestClient(app)


def create_test_company(db: Session, company_id: str) -> Company:
    """Create a test company."""
    company = Company(
        id=company_id,
        name=f"Test Company {company_id}",
        address="123 Test St",
    )
    db.add(company)
    db.commit()
    return company


def create_test_call(
    db: Session,
    company_id: str,
    rep_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    with_analysis: bool = False,
) -> Call:
    """Create a test call with optional analysis."""
    call = Call(
        call_id=None,  # Auto-increment
        company_id=company_id,
        assigned_rep_id=rep_id,
        lead_id=lead_id,
        phone_number="+12025551234",
        created_at=datetime.utcnow(),
        last_call_duration=300,
    )
    db.add(call)
    db.flush()
    
    if with_analysis:
        analysis = CallAnalysis(
            id=f"analysis_{call.call_id}",
            call_id=call.call_id,
            tenant_id=company_id,
            uwc_job_id=f"job_{call.call_id}",
            analyzed_at=datetime.utcnow(),
        )
        db.add(analysis)
    
    db.commit()
    db.refresh(call)
    return call


def create_test_lead(
    db: Session,
    company_id: str,
    contact_card_id: str,
    status: str = "new",
) -> Lead:
    """Create a test lead."""
    lead = Lead(
        id=f"lead_{company_id}_{datetime.utcnow().timestamp()}",
        company_id=company_id,
        contact_card_id=contact_card_id,
        status=LeadStatus(status),
        source=LeadSource.INBOUND_CALL,
    )
    db.add(lead)
    db.commit()
    return lead


def create_test_appointment(
    db: Session,
    company_id: str,
    lead_id: str,
    rep_id: Optional[str] = None,
    outcome: str = "pending",
) -> Appointment:
    """Create a test appointment."""
    appointment = Appointment(
        id=f"apt_{company_id}_{datetime.utcnow().timestamp()}",
        company_id=company_id,
        lead_id=lead_id,
        assigned_rep_id=rep_id,
        scheduled_start=datetime.utcnow(),
        outcome=AppointmentOutcome(outcome),
        status=AppointmentStatus.SCHEDULED,
    )
    db.add(appointment)
    db.commit()
    return appointment


@pytest.fixture
def test_company_1(db: Session):
    """Create test company 1."""
    return create_test_company(db, "company_1")


@pytest.fixture
def ai_internal_token():
    """Get AI internal token from settings."""
    return settings.AI_INTERNAL_TOKEN or "test_token"


class TestAISearchOutcomeDerivation:
    """
    CRITICAL: Test that _derive_outcome() uses Shunya data only, no inference.
    
    These tests verify the fix for semantic inference violation:
    - Must return None when Shunya data is missing (no inference from appointments/leads)
    - Must use CallAnalysis.call_outcome_category when available
    - Must use RecordingAnalysis.outcome when available
    """
    
    def test_outcome_returns_none_when_shunya_data_missing(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """
        CRITICAL: Outcome must be None when Shunya data is missing.
        
        This test FAILS if inference logic returns non-null without Shunya data.
        """
        # Create call with appointment and lead but NO Shunya analysis
        contact_card = ContactCard(
            id=f"contact_{test_company_1.id}",
            company_id=test_company_1.id,
            phone_number="+12025551234",
        )
        db.add(contact_card)
        db.flush()
        
        lead = create_test_lead(db, test_company_1.id, contact_card.id, status="qualified_booked")
        call = create_test_call(db, test_company_1.id, None, lead.id, with_analysis=False)
        appointment = create_test_appointment(db, test_company_1.id, lead.id, outcome="won")
        
        # Search - outcome should be None (no Shunya data)
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_calls": True, "include_aggregates": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 1
        # CRITICAL: Outcome must be None, not inferred from appointment.outcome or lead.status
        assert data["calls"][0]["outcome"] is None
        
        # Aggregates should not count this call in any outcome bucket
        if data["aggregates"] and data["aggregates"].get("calls_by_outcome"):
            # Should not have "won" or "booked" in outcomes if Shunya didn't provide it
            assert "won" not in data["aggregates"]["calls_by_outcome"]
    
    def test_outcome_uses_call_analysis_call_outcome_category(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """Outcome uses CallAnalysis.call_outcome_category when available."""
        # Create call with Shunya analysis including call_outcome_category
        call = create_test_call(db, test_company_1.id, None, None, with_analysis=True)
        
        # Update analysis with Shunya call_outcome_category
        analysis = db.query(CallAnalysis).filter(CallAnalysis.call_id == call.call_id).first()
        analysis.call_outcome_category = CallOutcomeCategory.QUALIFIED_AND_BOOKED
        db.commit()
        
        # Search
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_calls": True, "include_aggregates": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 1
        # Should use Shunya call_outcome_category
        assert data["calls"][0]["outcome"] == CallOutcomeCategory.QUALIFIED_AND_BOOKED.value
        
        # Aggregates should count this
        if data["aggregates"] and data["aggregates"].get("calls_by_outcome"):
            assert data["aggregates"]["calls_by_outcome"].get(CallOutcomeCategory.QUALIFIED_AND_BOOKED.value) == 1
    
    def test_outcome_uses_recording_analysis_outcome(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """Outcome uses RecordingAnalysis.outcome for sales visits when available."""
        # Create call, lead, appointment, and recording analysis
        contact_card = ContactCard(
            id=f"contact_{test_company_1.id}",
            company_id=test_company_1.id,
            phone_number="+12025551234",
        )
        db.add(contact_card)
        db.flush()
        
        lead = create_test_lead(db, test_company_1.id, contact_card.id)
        call = create_test_call(db, test_company_1.id, None, lead.id)
        appointment = create_test_appointment(db, test_company_1.id, lead.id)
        
        # Create RecordingAnalysis with Shunya outcome
        recording_analysis = RecordingAnalysis(
            id=f"rec_analysis_{appointment.id}",
            recording_session_id=f"session_{appointment.id}",
            company_id=test_company_1.id,
            appointment_id=appointment.id,
            lead_id=lead.id,
            outcome="won",  # Shunya-provided outcome
            analyzed_at=datetime.utcnow(),
        )
        db.add(recording_analysis)
        db.commit()
        
        # Search
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_calls": True, "include_aggregates": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 1
        # Should use RecordingAnalysis.outcome (Shunya data)
        assert data["calls"][0]["outcome"] == "won"
        
        # Aggregates should count this
        if data["aggregates"] and data["aggregates"].get("calls_by_outcome"):
            assert data["aggregates"]["calls_by_outcome"].get("won") == 1
    
    def test_outcome_prioritizes_recording_analysis_over_call_analysis(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """RecordingAnalysis.outcome takes priority over CallAnalysis.call_outcome_category."""
        contact_card = ContactCard(
            id=f"contact_{test_company_1.id}",
            company_id=test_company_1.id,
            phone_number="+12025551234",
        )
        db.add(contact_card)
        db.flush()
        
        lead = create_test_lead(db, test_company_1.id, contact_card.id)
        call = create_test_call(db, test_company_1.id, None, lead.id, with_analysis=True)
        appointment = create_test_appointment(db, test_company_1.id, lead.id)
        
        # Set CallAnalysis.call_outcome_category
        analysis = db.query(CallAnalysis).filter(CallAnalysis.call_id == call.call_id).first()
        analysis.call_outcome_category = CallOutcomeCategory.QUALIFIED_BUT_UNBOOKED
        db.flush()
        
        # Create RecordingAnalysis with different outcome (should take priority)
        recording_analysis = RecordingAnalysis(
            id=f"rec_analysis_{appointment.id}",
            recording_session_id=f"session_{appointment.id}",
            company_id=test_company_1.id,
            appointment_id=appointment.id,
            lead_id=lead.id,
            outcome="lost",  # Shunya-provided outcome (should take priority)
            analyzed_at=datetime.utcnow(),
        )
        db.add(recording_analysis)
        db.commit()
        
        # Search
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_calls": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 1
        # Should use RecordingAnalysis.outcome (priority), not CallAnalysis
        assert data["calls"][0]["outcome"] == "lost"



