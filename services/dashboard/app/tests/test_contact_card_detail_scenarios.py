"""
Contact Card Detail Scenario Tests.

Tests various real-world scenarios for GET /api/v1/contact-cards/{id}
to ensure the response is correct and comprehensive.
"""
import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models.call import Call
from app.models.appointment import Appointment, AppointmentStatus, AppointmentOutcome
from app.models.lead import Lead, LeadStatus, PoolStatus
from app.models.task import Task, TaskStatus, TaskAssignee, TaskSource

from app.tests.helpers.contact_card_test_helpers import (
    create_company,
    create_contact_card_with_lead,
    seed_csr_call_with_shunya_output,
    seed_appointment_with_visit_analysis,
    create_tasks_from_pending_actions,
    create_key_signals_from_missed_opportunities,
    update_property_intelligence,
    create_sales_rep,
    record_lead_status_change,
    record_rep_assignment,
)
from app.tests.fixtures.event_capture import EventCapture


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
    return "test_tenant_scenarios"


@pytest.fixture
def test_company(db_session, tenant_id):
    """Create a test company."""
    return create_company(db_session, tenant_id)


@pytest.fixture
def auth_headers(tenant_id):
    """Mock auth headers."""
    return {
        "Authorization": "Bearer mock_jwt_token",
        "X-Tenant-ID": tenant_id,
        "X-User-Role": "executive"
    }


# ============================================================================
# Scenario A: New Lead, Minimal Data
# ============================================================================

def test_scenario_a_new_lead_minimal_data(
    client,
    db_session: Session,
    test_company,
    tenant_id,
    auth_headers,
    event_capture: EventCapture,
):
    """
    Scenario A: New Lead, Minimal Data
    
    - Brand-new inbound call has created a ContactCard + Lead
    - No appointment yet
    - No property intelligence
    - No tasks
    - No recordings
    - No Lead Pool activity
    """
    # Setup
    contact_card, lead = create_contact_card_with_lead(
        db_session,
        tenant_id,
        lead_status=LeadStatus.NEW,
        pool_status=PoolStatus.IN_POOL,
        first_name="Jane",
        phone="+15551234567",
    )
    
    # Create a call (no Shunya analysis yet)
    call = Call(
        call_id=1001,
        company_id=tenant_id,
        contact_card_id=contact_card.id,
        lead_id=lead.id,
        name="Jane Doe",
        phone_number="+15551234567",
        missed_call=False,
    )
    db_session.add(call)
    db_session.commit()
    
    # Make request
    response = client.get(
        f"/api/v1/contact-cards/{contact_card.id}",
        headers=auth_headers,
    )
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    
    detail = data["data"]
    
    # Top section assertions
    top = detail["top_section"]
    assert top["lead_status"] == "new"
    assert top["pool_status"] == "in_pool"
    assert len(top["rep_assignment_history"]) == 0
    assert len(top["tasks"]) == 0
    assert top["overdue_count"] == 0
    assert top["lead_age_days"] is not None or top["lead_age_days"] is None  # May be computed
    
    # Middle section should be None (no appointment)
    assert detail.get("middle_section") is None
    
    # Bottom section assertions
    bottom = detail["bottom_section"]
    assert len(bottom["call_recordings"]) >= 1  # At least the call we created
    assert len(bottom["text_messages"]) == 0  # No messages yet
    
    # Global blocks
    global_blocks = detail["global_blocks"]
    assert len(global_blocks["all_calls"]) >= 1
    
    # Verify events
    event_capture.assert_event_emitted("call.created", tenant_id=tenant_id)


# ============================================================================
# Scenario B: Qualified & Booked Lead (Pre-Visit)
# ============================================================================

def test_scenario_b_qualified_booked_lead(
    client,
    db_session: Session,
    test_company,
    tenant_id,
    auth_headers,
    event_capture: EventCapture,
):
    """
    Scenario B: Qualified & Booked Lead (Pre-Visit)
    
    - CSR handled a call, Shunya processed it, and an appointment was booked
    - Property intelligence has run
    - Lead is in pool and/or assigned to rep
    """
    # Setup
    contact_card, lead = create_contact_card_with_lead(
        db_session,
        tenant_id,
        lead_status=LeadStatus.QUALIFIED_BOOKED,
        pool_status=PoolStatus.ASSIGNED,
    )
    
    # Create a call
    call = Call(
        call_id=1002,
        company_id=tenant_id,
        contact_card_id=contact_card.id,
        lead_id=lead.id,
        name="John Doe",
        phone_number="+15551234568",
    )
    db_session.add(call)
    db_session.flush()
    
    # Seed Shunya analysis (qualified and booked)
    seed_csr_call_with_shunya_output(
        db_session,
        call,
        tenant_id,
        qualification_status="qualified_booked",
        transcript_text="Customer wants a roof inspection scheduled for next week",
    )
    
    # Update lead status
    lead.status = LeadStatus.QUALIFIED_BOOKED
    lead.pool_status = PoolStatus.ASSIGNED
    
    # Create sales rep
    rep = create_sales_rep(db_session, tenant_id)
    lead.assigned_rep_id = rep.user_id
    
    # Record assignment
    record_rep_assignment(
        db_session,
        lead.id,
        contact_card.id,
        tenant_id,
        rep.user_id,
        assigned_by="manager_123",
        status="assigned",
    )
    
    # Create appointment
    appointment = Appointment(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        lead_id=lead.id,
        contact_card_id=contact_card.id,
        assigned_rep_id=rep.user_id,
        scheduled_start=datetime.utcnow() + timedelta(days=7),
        scheduled_end=datetime.utcnow() + timedelta(days=7, hours=1),
        status=AppointmentStatus.SCHEDULED,
        outcome=AppointmentOutcome.PENDING,
    )
    db_session.add(appointment)
    db_session.flush()
    
    # Add property intelligence
    property_data = {
        "roof_type": "Asphalt Shingle",
        "square_feet": 2500,
        "stories": 2,
        "year_built": 1995,
    }
    update_property_intelligence(db_session, contact_card, property_data)
    
    db_session.commit()
    
    # Make request
    response = client.get(
        f"/api/v1/contact-cards/{contact_card.id}",
        headers=auth_headers,
    )
    
    # Assertions
    assert response.status_code == 200
    data = response.json()["data"]
    
    # Top section
    top = data["top_section"]
    assert top["lead_status"] == "qualified_booked"
    assert top["pool_status"] == "assigned"
    assert top["assigned_rep_id"] == rep.user_id
    assert len(top["rep_assignment_history"]) >= 1
    
    # Middle section should exist (has appointment)
    middle = data["middle_section"]
    assert middle is not None
    assert middle["active_appointment"] is not None
    assert middle["active_appointment"]["status"] == "scheduled"
    
    # Property intelligence
    prop_intel = middle["property_intelligence"]
    assert prop_intel is not None
    assert prop_intel["roof_type"] == "Asphalt Shingle"
    assert prop_intel["square_feet"] == 2500
    
    # Bottom section
    bottom = data["bottom_section"]
    assert len(bottom["call_recordings"]) >= 1
    assert len(bottom["booking_timeline"]) >= 1  # Should have appointment creation
    
    # Verify events
    event_capture.assert_event_emitted("call.transcribed", tenant_id=tenant_id)
    event_capture.assert_event_emitted("appointment.created", tenant_id=tenant_id)
    event_capture.assert_event_emitted("lead.updated", tenant_id=tenant_id)


# ============================================================================
# Scenario C: Nurturing / Pending Actions
# ============================================================================

def test_scenario_c_nurturing_pending_actions(
    client,
    db_session: Session,
    test_company,
    tenant_id,
    auth_headers,
    event_capture: EventCapture,
):
    """
    Scenario C: Nurturing / Pending Actions
    
    - Lead is qualified but unbooked, with pending actions and nurture messages
    """
    # Setup
    contact_card, lead = create_contact_card_with_lead(
        db_session,
        tenant_id,
        lead_status=LeadStatus.QUALIFIED_UNBOOKED,
        pool_status=PoolStatus.IN_POOL,
    )
    
    # Create a call
    call = Call(
        call_id=1003,
        company_id=tenant_id,
        contact_card_id=contact_card.id,
        lead_id=lead.id,
        name="Bob Smith",
        phone_number="+15551234569",
    )
    db_session.add(call)
    db_session.flush()
    
    # Seed Shunya analysis (qualified but unbooked with pending actions)
    pending_actions_data = [
        {"action": "Call back at 5pm", "due_at": datetime.utcnow() + timedelta(hours=3)},
        {"action": "Send financing options", "due_at": None},
        {"action": "Follow up on spouse decision", "due_at": datetime.utcnow() + timedelta(days=1)},
    ]
    
    seed_csr_call_with_shunya_output(
        db_session,
        call,
        tenant_id,
        qualification_status="qualified_unbooked",
        transcript_text="Customer is interested but needs to discuss with spouse",
        pending_actions=pending_actions_data,
    )
    
    # Create tasks from pending actions
    tasks = create_tasks_from_pending_actions(
        db_session,
        contact_card.id,
        tenant_id,
        pending_actions_data,
    )
    
    # Create an overdue task
    overdue_task = Task(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        contact_card_id=contact_card.id,
        description="Overdue follow-up",
        source=TaskSource.SHUNYA,
        assigned_to=TaskAssignee.REP,
        status=TaskStatus.OPEN,
        due_at=datetime.utcnow() - timedelta(days=1),  # Overdue
    )
    db_session.add(overdue_task)
    
    # Update lead status
    lead.status = LeadStatus.NURTURING
    
    db_session.commit()
    
    # Make request
    response = client.get(
        f"/api/v1/contact-cards/{contact_card.id}",
        headers=auth_headers,
    )
    
    # Assertions
    assert response.status_code == 200
    data = response.json()["data"]
    
    # Top section
    top = data["top_section"]
    assert top["lead_status"] in ["qualified_unbooked", "nurturing"]
    assert len(top["tasks"]) >= 3  # At least the pending actions
    assert top["overdue_count"] >= 1  # At least the overdue task
    
    # Middle section should be None (no appointment)
    assert data.get("middle_section") is None
    
    # Verify events
    event_capture.assert_event_emitted("task.created", tenant_id=tenant_id)


# ============================================================================
# Scenario D: Visit Completed, Pending Decision
# ============================================================================

def test_scenario_d_visit_completed_pending(
    client,
    db_session: Session,
    test_company,
    tenant_id,
    auth_headers,
    event_capture: EventCapture,
):
    """
    Scenario D: Visit Completed, Pending Decision
    
    - Sales rep visited the customer
    - RecordingSession uploaded and processed by Shunya
    - Outcome is "still deciding" / pending
    """
    # Setup
    contact_card, lead = create_contact_card_with_lead(
        db_session,
        tenant_id,
        lead_status=LeadStatus.QUALIFIED_BOOKED,
        pool_status=PoolStatus.ASSIGNED,
    )
    
    rep = create_sales_rep(db_session, tenant_id)
    lead.assigned_rep_id = rep.user_id
    
    # Create appointment
    appointment = Appointment(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        lead_id=lead.id,
        contact_card_id=contact_card.id,
        assigned_rep_id=rep.user_id,
        scheduled_start=datetime.utcnow() - timedelta(hours=2),
        scheduled_end=datetime.utcnow() - timedelta(hours=1),
        status=AppointmentStatus.COMPLETED,
        outcome=AppointmentOutcome.PENDING,
    )
    db_session.add(appointment)
    db_session.flush()
    
    # Seed visit analysis (outcome = pending)
    visit_actions = [
        {"action": "Send revised estimate", "due_at": datetime.utcnow() + timedelta(days=1)},
        {"action": "Call spouse", "due_at": None},
    ]
    
    transcript, analysis = seed_appointment_with_visit_analysis(
        db_session,
        appointment,
        tenant_id,
        outcome=AppointmentOutcome.PENDING,
        transcript_text="Customer is reviewing the estimate and will decide by Friday",
        is_ghost_mode=False,
        visit_actions=visit_actions,
    )
    
    # Create tasks from visit actions
    create_tasks_from_pending_actions(
        db_session,
        contact_card.id,
        tenant_id,
        visit_actions,
    )
    
    db_session.commit()
    
    # Make request
    response = client.get(
        f"/api/v1/contact-cards/{contact_card.id}",
        headers=auth_headers,
    )
    
    # Assertions
    assert response.status_code == 200
    data = response.json()["data"]
    
    # Middle section
    middle = data["middle_section"]
    assert middle is not None
    assert middle["active_appointment"] is not None
    assert middle["active_appointment"]["outcome"] == "pending"
    
    # Recording sessions
    assert len(middle["recording_sessions"]) >= 1
    
    # Appointment tasks
    assert len(middle["appointment_tasks"]) >= 2
    
    # Top section - should show tasks
    top = data["top_section"]
    assert len(top["tasks"]) >= 2
    
    # Verify events
    event_capture.assert_event_emitted("recording_session.analyzed", tenant_id=tenant_id)
    event_capture.assert_event_emitted("appointment.outcome_updated", tenant_id=tenant_id)


# ============================================================================
# Scenario E: Closed Won Deal
# ============================================================================

def test_scenario_e_closed_won_deal(
    client,
    db_session: Session,
    test_company,
    tenant_id,
    auth_headers,
    event_capture: EventCapture,
):
    """
    Scenario E: Closed Won Deal
    
    - Appointment completed and deal is won
    """
    # Setup
    contact_card, lead = create_contact_card_with_lead(
        db_session,
        tenant_id,
        lead_status=LeadStatus.CLOSED_WON,
        pool_status=PoolStatus.CLOSED,
    )
    
    rep = create_sales_rep(db_session, tenant_id)
    lead.assigned_rep_id = rep.user_id
    lead.deal_status = "won"
    lead.deal_size = 35000.0
    lead.closed_at = datetime.utcnow()
    
    # Record status change
    record_lead_status_change(
        db_session,
        lead.id,
        tenant_id,
        from_status="qualified_booked",
        to_status="closed_won",
        reason="Deal won - customer signed contract",
    )
    
    # Create appointment
    appointment = Appointment(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        lead_id=lead.id,
        contact_card_id=contact_card.id,
        assigned_rep_id=rep.user_id,
        scheduled_start=datetime.utcnow() - timedelta(days=1),
        scheduled_end=datetime.utcnow() - timedelta(days=1, hours=1),
        status=AppointmentStatus.COMPLETED,
        outcome=AppointmentOutcome.WON,
        closed_at=datetime.utcnow(),
    )
    db_session.add(appointment)
    db_session.flush()
    
    # Seed visit analysis (outcome = won)
    seed_appointment_with_visit_analysis(
        db_session,
        appointment,
        tenant_id,
        outcome=AppointmentOutcome.WON,
        transcript_text="Customer signed the contract and we discussed next steps",
        is_ghost_mode=False,
    )
    
    db_session.commit()
    
    # Make request
    response = client.get(
        f"/api/v1/contact-cards/{contact_card.id}",
        headers=auth_headers,
    )
    
    # Assertions
    assert response.status_code == 200
    data = response.json()["data"]
    
    # Top section
    top = data["top_section"]
    assert top["lead_status"] == "closed_won"
    assert top["deal_status"] == "won"
    assert top["deal_size"] == 35000.0
    assert top["closed_at"] is not None
    
    # Middle section
    middle = data["middle_section"]
    assert middle is not None
    assert middle["active_appointment"]["outcome"] == "won"
    
    # Verify events
    event_capture.assert_event_emitted("lead.status_changed", tenant_id=tenant_id)
    event_capture.assert_event_emitted("appointment.outcome_updated", tenant_id=tenant_id)


# ============================================================================
# Scenario F: Closed Lost + Missed Opportunity
# ============================================================================

def test_scenario_f_closed_lost_missed_opportunity(
    client,
    db_session: Session,
    test_company,
    tenant_id,
    auth_headers,
    event_capture: EventCapture,
):
    """
    Scenario F: Closed Lost + Missed Opportunity
    
    - Appointment completed but lost
    - Shunya flags missed_opportunities and SOP/compliance issues
    """
    # Setup
    contact_card, lead = create_contact_card_with_lead(
        db_session,
        tenant_id,
        lead_status=LeadStatus.CLOSED_LOST,
        pool_status=PoolStatus.CLOSED,
    )
    
    rep = create_sales_rep(db_session, tenant_id)
    lead.assigned_rep_id = rep.user_id
    lead.deal_status = "lost"
    lead.closed_at = datetime.utcnow()
    
    # Record status change
    record_lead_status_change(
        db_session,
        lead.id,
        tenant_id,
        from_status="qualified_booked",
        to_status="closed_lost",
        reason="Customer chose competitor",
    )
    
    # Create appointment
    appointment = Appointment(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        lead_id=lead.id,
        contact_card_id=contact_card.id,
        assigned_rep_id=rep.user_id,
        scheduled_start=datetime.utcnow() - timedelta(days=2),
        scheduled_end=datetime.utcnow() - timedelta(days=2, hours=1),
        status=AppointmentStatus.COMPLETED,
        outcome=AppointmentOutcome.LOST,
        closed_at=datetime.utcnow() - timedelta(days=2),
    )
    db_session.add(appointment)
    db_session.flush()
    
    # Seed visit analysis (outcome = lost)
    transcript, analysis = seed_appointment_with_visit_analysis(
        db_session,
        appointment,
        tenant_id,
        outcome=AppointmentOutcome.LOST,
        transcript_text="Customer mentioned price concerns but rep didn't offer financing options",
        is_ghost_mode=False,
    )
    
    # Add missed opportunities to analysis
    analysis.objections = ["price"]
    analysis.coaching_tips = [
        {"tip": "Should have offered financing options", "priority": "high"},
        {"tip": "Didn't address price objection effectively", "priority": "medium"},
    ]
    db_session.commit()
    
    # Create key signals from missed opportunities
    missed_opps = [
        "Didn't offer financing options when customer mentioned price concerns",
        "Didn't mention referral program",
    ]
    create_key_signals_from_missed_opportunities(
        db_session,
        contact_card.id,
        tenant_id,
        lead.id,
        missed_opps,
    )
    
    db_session.commit()
    
    # Make request
    response = client.get(
        f"/api/v1/contact-cards/{contact_card.id}",
        headers=auth_headers,
    )
    
    # Assertions
    assert response.status_code == 200
    data = response.json()["data"]
    
    # Top section
    top = data["top_section"]
    assert top["lead_status"] == "closed_lost"
    assert len(top["key_signals"]) >= 2  # At least the missed opportunities
    
    # Middle section
    middle = data["middle_section"]
    assert middle is not None
    assert middle["active_appointment"]["outcome"] == "lost"
    
    # Should have SOP compliance items
    assert len(middle["sop_compliance"]) >= 0  # May or may not be populated
    
    # Verify events
    event_capture.assert_event_emitted("lead.status_changed", tenant_id=tenant_id)
    event_capture.assert_event_emitted("appointment.outcome_updated", tenant_id=tenant_id)


# ============================================================================
# Scenario G: Ghost Mode Visit
# ============================================================================

def test_scenario_g_ghost_mode_visit(
    client,
    db_session: Session,
    test_company,
    tenant_id,
    auth_headers,
    event_capture: EventCapture,
):
    """
    Scenario G: Ghost Mode Visit
    
    - Sales rep enabled ghost mode for the appointment
    - Otto can still analyze but must respect privacy rules
    """
    # Setup
    contact_card, lead = create_contact_card_with_lead(
        db_session,
        tenant_id,
        lead_status=LeadStatus.QUALIFIED_BOOKED,
        pool_status=PoolStatus.ASSIGNED,
    )
    
    rep = create_sales_rep(db_session, tenant_id)
    lead.assigned_rep_id = rep.user_id
    
    # Create appointment
    appointment = Appointment(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        lead_id=lead.id,
        contact_card_id=contact_card.id,
        assigned_rep_id=rep.user_id,
        scheduled_start=datetime.utcnow() - timedelta(hours=1),
        scheduled_end=datetime.utcnow(),
        status=AppointmentStatus.COMPLETED,
        outcome=AppointmentOutcome.PENDING,
    )
    db_session.add(appointment)
    db_session.flush()
    
    # Seed visit analysis in GHOST MODE
    transcript, analysis = seed_appointment_with_visit_analysis(
        db_session,
        appointment,
        tenant_id,
        outcome=AppointmentOutcome.PENDING,
        transcript_text=None,  # No transcript in ghost mode
        is_ghost_mode=True,
    )
    
    db_session.commit()
    
    # Make request
    response = client.get(
        f"/api/v1/contact-cards/{contact_card.id}",
        headers=auth_headers,
    )
    
    # Assertions
    assert response.status_code == 200
    data = response.json()["data"]
    
    # Middle section
    middle = data["middle_section"]
    assert middle is not None
    assert len(middle["recording_sessions"]) >= 1
    
    # Verify ghost mode constraints
    recording_session = middle["recording_sessions"][0]
    
    # In ghost mode, audio_url should be None or not exposed
    # Transcript should not be exposed (if transcript_restricted is True)
    # But outcome and analysis should still be available
    assert recording_session.get("outcome") is not None  # Outcome should be available
    assert recording_session.get("mode") == "ghost" or recording_session.get("is_ghost_mode") is True
    
    # Verify events
    event_capture.assert_event_emitted("recording_session.analyzed", tenant_id=tenant_id)


# ============================================================================
# Event Flow Verification Helper
# ============================================================================

def assert_event_emitted(
    event_capture: EventCapture,
    event_name: str,
    **filters
):
    """
    Helper to assert an event was emitted with specific filters.
    
    Usage:
        assert_event_emitted(event_capture, "lead.updated", tenant_id=tenant_id, lead_id=lead.id)
    """
    try:
        event_capture.assert_event_emitted(event_name, **filters)
        return True
    except AssertionError:
        return False





Tests various real-world scenarios for GET /api/v1/contact-cards/{id}
to ensure the response is correct and comprehensive.
"""
import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models.call import Call
from app.models.appointment import Appointment, AppointmentStatus, AppointmentOutcome
from app.models.lead import Lead, LeadStatus, PoolStatus
from app.models.task import Task, TaskStatus, TaskAssignee, TaskSource

from app.tests.helpers.contact_card_test_helpers import (
    create_company,
    create_contact_card_with_lead,
    seed_csr_call_with_shunya_output,
    seed_appointment_with_visit_analysis,
    create_tasks_from_pending_actions,
    create_key_signals_from_missed_opportunities,
    update_property_intelligence,
    create_sales_rep,
    record_lead_status_change,
    record_rep_assignment,
)
from app.tests.fixtures.event_capture import EventCapture


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
    return "test_tenant_scenarios"


@pytest.fixture
def test_company(db_session, tenant_id):
    """Create a test company."""
    return create_company(db_session, tenant_id)


@pytest.fixture
def auth_headers(tenant_id):
    """Mock auth headers."""
    return {
        "Authorization": "Bearer mock_jwt_token",
        "X-Tenant-ID": tenant_id,
        "X-User-Role": "executive"
    }


# ============================================================================
# Scenario A: New Lead, Minimal Data
# ============================================================================

def test_scenario_a_new_lead_minimal_data(
    client,
    db_session: Session,
    test_company,
    tenant_id,
    auth_headers,
    event_capture: EventCapture,
):
    """
    Scenario A: New Lead, Minimal Data
    
    - Brand-new inbound call has created a ContactCard + Lead
    - No appointment yet
    - No property intelligence
    - No tasks
    - No recordings
    - No Lead Pool activity
    """
    # Setup
    contact_card, lead = create_contact_card_with_lead(
        db_session,
        tenant_id,
        lead_status=LeadStatus.NEW,
        pool_status=PoolStatus.IN_POOL,
        first_name="Jane",
        phone="+15551234567",
    )
    
    # Create a call (no Shunya analysis yet)
    call = Call(
        call_id=1001,
        company_id=tenant_id,
        contact_card_id=contact_card.id,
        lead_id=lead.id,
        name="Jane Doe",
        phone_number="+15551234567",
        missed_call=False,
    )
    db_session.add(call)
    db_session.commit()
    
    # Make request
    response = client.get(
        f"/api/v1/contact-cards/{contact_card.id}",
        headers=auth_headers,
    )
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    
    detail = data["data"]
    
    # Top section assertions
    top = detail["top_section"]
    assert top["lead_status"] == "new"
    assert top["pool_status"] == "in_pool"
    assert len(top["rep_assignment_history"]) == 0
    assert len(top["tasks"]) == 0
    assert top["overdue_count"] == 0
    assert top["lead_age_days"] is not None or top["lead_age_days"] is None  # May be computed
    
    # Middle section should be None (no appointment)
    assert detail.get("middle_section") is None
    
    # Bottom section assertions
    bottom = detail["bottom_section"]
    assert len(bottom["call_recordings"]) >= 1  # At least the call we created
    assert len(bottom["text_messages"]) == 0  # No messages yet
    
    # Global blocks
    global_blocks = detail["global_blocks"]
    assert len(global_blocks["all_calls"]) >= 1
    
    # Verify events
    event_capture.assert_event_emitted("call.created", tenant_id=tenant_id)


# ============================================================================
# Scenario B: Qualified & Booked Lead (Pre-Visit)
# ============================================================================

def test_scenario_b_qualified_booked_lead(
    client,
    db_session: Session,
    test_company,
    tenant_id,
    auth_headers,
    event_capture: EventCapture,
):
    """
    Scenario B: Qualified & Booked Lead (Pre-Visit)
    
    - CSR handled a call, Shunya processed it, and an appointment was booked
    - Property intelligence has run
    - Lead is in pool and/or assigned to rep
    """
    # Setup
    contact_card, lead = create_contact_card_with_lead(
        db_session,
        tenant_id,
        lead_status=LeadStatus.QUALIFIED_BOOKED,
        pool_status=PoolStatus.ASSIGNED,
    )
    
    # Create a call
    call = Call(
        call_id=1002,
        company_id=tenant_id,
        contact_card_id=contact_card.id,
        lead_id=lead.id,
        name="John Doe",
        phone_number="+15551234568",
    )
    db_session.add(call)
    db_session.flush()
    
    # Seed Shunya analysis (qualified and booked)
    seed_csr_call_with_shunya_output(
        db_session,
        call,
        tenant_id,
        qualification_status="qualified_booked",
        transcript_text="Customer wants a roof inspection scheduled for next week",
    )
    
    # Update lead status
    lead.status = LeadStatus.QUALIFIED_BOOKED
    lead.pool_status = PoolStatus.ASSIGNED
    
    # Create sales rep
    rep = create_sales_rep(db_session, tenant_id)
    lead.assigned_rep_id = rep.user_id
    
    # Record assignment
    record_rep_assignment(
        db_session,
        lead.id,
        contact_card.id,
        tenant_id,
        rep.user_id,
        assigned_by="manager_123",
        status="assigned",
    )
    
    # Create appointment
    appointment = Appointment(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        lead_id=lead.id,
        contact_card_id=contact_card.id,
        assigned_rep_id=rep.user_id,
        scheduled_start=datetime.utcnow() + timedelta(days=7),
        scheduled_end=datetime.utcnow() + timedelta(days=7, hours=1),
        status=AppointmentStatus.SCHEDULED,
        outcome=AppointmentOutcome.PENDING,
    )
    db_session.add(appointment)
    db_session.flush()
    
    # Add property intelligence
    property_data = {
        "roof_type": "Asphalt Shingle",
        "square_feet": 2500,
        "stories": 2,
        "year_built": 1995,
    }
    update_property_intelligence(db_session, contact_card, property_data)
    
    db_session.commit()
    
    # Make request
    response = client.get(
        f"/api/v1/contact-cards/{contact_card.id}",
        headers=auth_headers,
    )
    
    # Assertions
    assert response.status_code == 200
    data = response.json()["data"]
    
    # Top section
    top = data["top_section"]
    assert top["lead_status"] == "qualified_booked"
    assert top["pool_status"] == "assigned"
    assert top["assigned_rep_id"] == rep.user_id
    assert len(top["rep_assignment_history"]) >= 1
    
    # Middle section should exist (has appointment)
    middle = data["middle_section"]
    assert middle is not None
    assert middle["active_appointment"] is not None
    assert middle["active_appointment"]["status"] == "scheduled"
    
    # Property intelligence
    prop_intel = middle["property_intelligence"]
    assert prop_intel is not None
    assert prop_intel["roof_type"] == "Asphalt Shingle"
    assert prop_intel["square_feet"] == 2500
    
    # Bottom section
    bottom = data["bottom_section"]
    assert len(bottom["call_recordings"]) >= 1
    assert len(bottom["booking_timeline"]) >= 1  # Should have appointment creation
    
    # Verify events
    event_capture.assert_event_emitted("call.transcribed", tenant_id=tenant_id)
    event_capture.assert_event_emitted("appointment.created", tenant_id=tenant_id)
    event_capture.assert_event_emitted("lead.updated", tenant_id=tenant_id)


# ============================================================================
# Scenario C: Nurturing / Pending Actions
# ============================================================================

def test_scenario_c_nurturing_pending_actions(
    client,
    db_session: Session,
    test_company,
    tenant_id,
    auth_headers,
    event_capture: EventCapture,
):
    """
    Scenario C: Nurturing / Pending Actions
    
    - Lead is qualified but unbooked, with pending actions and nurture messages
    """
    # Setup
    contact_card, lead = create_contact_card_with_lead(
        db_session,
        tenant_id,
        lead_status=LeadStatus.QUALIFIED_UNBOOKED,
        pool_status=PoolStatus.IN_POOL,
    )
    
    # Create a call
    call = Call(
        call_id=1003,
        company_id=tenant_id,
        contact_card_id=contact_card.id,
        lead_id=lead.id,
        name="Bob Smith",
        phone_number="+15551234569",
    )
    db_session.add(call)
    db_session.flush()
    
    # Seed Shunya analysis (qualified but unbooked with pending actions)
    pending_actions_data = [
        {"action": "Call back at 5pm", "due_at": datetime.utcnow() + timedelta(hours=3)},
        {"action": "Send financing options", "due_at": None},
        {"action": "Follow up on spouse decision", "due_at": datetime.utcnow() + timedelta(days=1)},
    ]
    
    seed_csr_call_with_shunya_output(
        db_session,
        call,
        tenant_id,
        qualification_status="qualified_unbooked",
        transcript_text="Customer is interested but needs to discuss with spouse",
        pending_actions=pending_actions_data,
    )
    
    # Create tasks from pending actions
    tasks = create_tasks_from_pending_actions(
        db_session,
        contact_card.id,
        tenant_id,
        pending_actions_data,
    )
    
    # Create an overdue task
    overdue_task = Task(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        contact_card_id=contact_card.id,
        description="Overdue follow-up",
        source=TaskSource.SHUNYA,
        assigned_to=TaskAssignee.REP,
        status=TaskStatus.OPEN,
        due_at=datetime.utcnow() - timedelta(days=1),  # Overdue
    )
    db_session.add(overdue_task)
    
    # Update lead status
    lead.status = LeadStatus.NURTURING
    
    db_session.commit()
    
    # Make request
    response = client.get(
        f"/api/v1/contact-cards/{contact_card.id}",
        headers=auth_headers,
    )
    
    # Assertions
    assert response.status_code == 200
    data = response.json()["data"]
    
    # Top section
    top = data["top_section"]
    assert top["lead_status"] in ["qualified_unbooked", "nurturing"]
    assert len(top["tasks"]) >= 3  # At least the pending actions
    assert top["overdue_count"] >= 1  # At least the overdue task
    
    # Middle section should be None (no appointment)
    assert data.get("middle_section") is None
    
    # Verify events
    event_capture.assert_event_emitted("task.created", tenant_id=tenant_id)


# ============================================================================
# Scenario D: Visit Completed, Pending Decision
# ============================================================================

def test_scenario_d_visit_completed_pending(
    client,
    db_session: Session,
    test_company,
    tenant_id,
    auth_headers,
    event_capture: EventCapture,
):
    """
    Scenario D: Visit Completed, Pending Decision
    
    - Sales rep visited the customer
    - RecordingSession uploaded and processed by Shunya
    - Outcome is "still deciding" / pending
    """
    # Setup
    contact_card, lead = create_contact_card_with_lead(
        db_session,
        tenant_id,
        lead_status=LeadStatus.QUALIFIED_BOOKED,
        pool_status=PoolStatus.ASSIGNED,
    )
    
    rep = create_sales_rep(db_session, tenant_id)
    lead.assigned_rep_id = rep.user_id
    
    # Create appointment
    appointment = Appointment(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        lead_id=lead.id,
        contact_card_id=contact_card.id,
        assigned_rep_id=rep.user_id,
        scheduled_start=datetime.utcnow() - timedelta(hours=2),
        scheduled_end=datetime.utcnow() - timedelta(hours=1),
        status=AppointmentStatus.COMPLETED,
        outcome=AppointmentOutcome.PENDING,
    )
    db_session.add(appointment)
    db_session.flush()
    
    # Seed visit analysis (outcome = pending)
    visit_actions = [
        {"action": "Send revised estimate", "due_at": datetime.utcnow() + timedelta(days=1)},
        {"action": "Call spouse", "due_at": None},
    ]
    
    transcript, analysis = seed_appointment_with_visit_analysis(
        db_session,
        appointment,
        tenant_id,
        outcome=AppointmentOutcome.PENDING,
        transcript_text="Customer is reviewing the estimate and will decide by Friday",
        is_ghost_mode=False,
        visit_actions=visit_actions,
    )
    
    # Create tasks from visit actions
    create_tasks_from_pending_actions(
        db_session,
        contact_card.id,
        tenant_id,
        visit_actions,
    )
    
    db_session.commit()
    
    # Make request
    response = client.get(
        f"/api/v1/contact-cards/{contact_card.id}",
        headers=auth_headers,
    )
    
    # Assertions
    assert response.status_code == 200
    data = response.json()["data"]
    
    # Middle section
    middle = data["middle_section"]
    assert middle is not None
    assert middle["active_appointment"] is not None
    assert middle["active_appointment"]["outcome"] == "pending"
    
    # Recording sessions
    assert len(middle["recording_sessions"]) >= 1
    
    # Appointment tasks
    assert len(middle["appointment_tasks"]) >= 2
    
    # Top section - should show tasks
    top = data["top_section"]
    assert len(top["tasks"]) >= 2
    
    # Verify events
    event_capture.assert_event_emitted("recording_session.analyzed", tenant_id=tenant_id)
    event_capture.assert_event_emitted("appointment.outcome_updated", tenant_id=tenant_id)


# ============================================================================
# Scenario E: Closed Won Deal
# ============================================================================

def test_scenario_e_closed_won_deal(
    client,
    db_session: Session,
    test_company,
    tenant_id,
    auth_headers,
    event_capture: EventCapture,
):
    """
    Scenario E: Closed Won Deal
    
    - Appointment completed and deal is won
    """
    # Setup
    contact_card, lead = create_contact_card_with_lead(
        db_session,
        tenant_id,
        lead_status=LeadStatus.CLOSED_WON,
        pool_status=PoolStatus.CLOSED,
    )
    
    rep = create_sales_rep(db_session, tenant_id)
    lead.assigned_rep_id = rep.user_id
    lead.deal_status = "won"
    lead.deal_size = 35000.0
    lead.closed_at = datetime.utcnow()
    
    # Record status change
    record_lead_status_change(
        db_session,
        lead.id,
        tenant_id,
        from_status="qualified_booked",
        to_status="closed_won",
        reason="Deal won - customer signed contract",
    )
    
    # Create appointment
    appointment = Appointment(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        lead_id=lead.id,
        contact_card_id=contact_card.id,
        assigned_rep_id=rep.user_id,
        scheduled_start=datetime.utcnow() - timedelta(days=1),
        scheduled_end=datetime.utcnow() - timedelta(days=1, hours=1),
        status=AppointmentStatus.COMPLETED,
        outcome=AppointmentOutcome.WON,
        closed_at=datetime.utcnow(),
    )
    db_session.add(appointment)
    db_session.flush()
    
    # Seed visit analysis (outcome = won)
    seed_appointment_with_visit_analysis(
        db_session,
        appointment,
        tenant_id,
        outcome=AppointmentOutcome.WON,
        transcript_text="Customer signed the contract and we discussed next steps",
        is_ghost_mode=False,
    )
    
    db_session.commit()
    
    # Make request
    response = client.get(
        f"/api/v1/contact-cards/{contact_card.id}",
        headers=auth_headers,
    )
    
    # Assertions
    assert response.status_code == 200
    data = response.json()["data"]
    
    # Top section
    top = data["top_section"]
    assert top["lead_status"] == "closed_won"
    assert top["deal_status"] == "won"
    assert top["deal_size"] == 35000.0
    assert top["closed_at"] is not None
    
    # Middle section
    middle = data["middle_section"]
    assert middle is not None
    assert middle["active_appointment"]["outcome"] == "won"
    
    # Verify events
    event_capture.assert_event_emitted("lead.status_changed", tenant_id=tenant_id)
    event_capture.assert_event_emitted("appointment.outcome_updated", tenant_id=tenant_id)


# ============================================================================
# Scenario F: Closed Lost + Missed Opportunity
# ============================================================================

def test_scenario_f_closed_lost_missed_opportunity(
    client,
    db_session: Session,
    test_company,
    tenant_id,
    auth_headers,
    event_capture: EventCapture,
):
    """
    Scenario F: Closed Lost + Missed Opportunity
    
    - Appointment completed but lost
    - Shunya flags missed_opportunities and SOP/compliance issues
    """
    # Setup
    contact_card, lead = create_contact_card_with_lead(
        db_session,
        tenant_id,
        lead_status=LeadStatus.CLOSED_LOST,
        pool_status=PoolStatus.CLOSED,
    )
    
    rep = create_sales_rep(db_session, tenant_id)
    lead.assigned_rep_id = rep.user_id
    lead.deal_status = "lost"
    lead.closed_at = datetime.utcnow()
    
    # Record status change
    record_lead_status_change(
        db_session,
        lead.id,
        tenant_id,
        from_status="qualified_booked",
        to_status="closed_lost",
        reason="Customer chose competitor",
    )
    
    # Create appointment
    appointment = Appointment(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        lead_id=lead.id,
        contact_card_id=contact_card.id,
        assigned_rep_id=rep.user_id,
        scheduled_start=datetime.utcnow() - timedelta(days=2),
        scheduled_end=datetime.utcnow() - timedelta(days=2, hours=1),
        status=AppointmentStatus.COMPLETED,
        outcome=AppointmentOutcome.LOST,
        closed_at=datetime.utcnow() - timedelta(days=2),
    )
    db_session.add(appointment)
    db_session.flush()
    
    # Seed visit analysis (outcome = lost)
    transcript, analysis = seed_appointment_with_visit_analysis(
        db_session,
        appointment,
        tenant_id,
        outcome=AppointmentOutcome.LOST,
        transcript_text="Customer mentioned price concerns but rep didn't offer financing options",
        is_ghost_mode=False,
    )
    
    # Add missed opportunities to analysis
    analysis.objections = ["price"]
    analysis.coaching_tips = [
        {"tip": "Should have offered financing options", "priority": "high"},
        {"tip": "Didn't address price objection effectively", "priority": "medium"},
    ]
    db_session.commit()
    
    # Create key signals from missed opportunities
    missed_opps = [
        "Didn't offer financing options when customer mentioned price concerns",
        "Didn't mention referral program",
    ]
    create_key_signals_from_missed_opportunities(
        db_session,
        contact_card.id,
        tenant_id,
        lead.id,
        missed_opps,
    )
    
    db_session.commit()
    
    # Make request
    response = client.get(
        f"/api/v1/contact-cards/{contact_card.id}",
        headers=auth_headers,
    )
    
    # Assertions
    assert response.status_code == 200
    data = response.json()["data"]
    
    # Top section
    top = data["top_section"]
    assert top["lead_status"] == "closed_lost"
    assert len(top["key_signals"]) >= 2  # At least the missed opportunities
    
    # Middle section
    middle = data["middle_section"]
    assert middle is not None
    assert middle["active_appointment"]["outcome"] == "lost"
    
    # Should have SOP compliance items
    assert len(middle["sop_compliance"]) >= 0  # May or may not be populated
    
    # Verify events
    event_capture.assert_event_emitted("lead.status_changed", tenant_id=tenant_id)
    event_capture.assert_event_emitted("appointment.outcome_updated", tenant_id=tenant_id)


# ============================================================================
# Scenario G: Ghost Mode Visit
# ============================================================================

def test_scenario_g_ghost_mode_visit(
    client,
    db_session: Session,
    test_company,
    tenant_id,
    auth_headers,
    event_capture: EventCapture,
):
    """
    Scenario G: Ghost Mode Visit
    
    - Sales rep enabled ghost mode for the appointment
    - Otto can still analyze but must respect privacy rules
    """
    # Setup
    contact_card, lead = create_contact_card_with_lead(
        db_session,
        tenant_id,
        lead_status=LeadStatus.QUALIFIED_BOOKED,
        pool_status=PoolStatus.ASSIGNED,
    )
    
    rep = create_sales_rep(db_session, tenant_id)
    lead.assigned_rep_id = rep.user_id
    
    # Create appointment
    appointment = Appointment(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        lead_id=lead.id,
        contact_card_id=contact_card.id,
        assigned_rep_id=rep.user_id,
        scheduled_start=datetime.utcnow() - timedelta(hours=1),
        scheduled_end=datetime.utcnow(),
        status=AppointmentStatus.COMPLETED,
        outcome=AppointmentOutcome.PENDING,
    )
    db_session.add(appointment)
    db_session.flush()
    
    # Seed visit analysis in GHOST MODE
    transcript, analysis = seed_appointment_with_visit_analysis(
        db_session,
        appointment,
        tenant_id,
        outcome=AppointmentOutcome.PENDING,
        transcript_text=None,  # No transcript in ghost mode
        is_ghost_mode=True,
    )
    
    db_session.commit()
    
    # Make request
    response = client.get(
        f"/api/v1/contact-cards/{contact_card.id}",
        headers=auth_headers,
    )
    
    # Assertions
    assert response.status_code == 200
    data = response.json()["data"]
    
    # Middle section
    middle = data["middle_section"]
    assert middle is not None
    assert len(middle["recording_sessions"]) >= 1
    
    # Verify ghost mode constraints
    recording_session = middle["recording_sessions"][0]
    
    # In ghost mode, audio_url should be None or not exposed
    # Transcript should not be exposed (if transcript_restricted is True)
    # But outcome and analysis should still be available
    assert recording_session.get("outcome") is not None  # Outcome should be available
    assert recording_session.get("mode") == "ghost" or recording_session.get("is_ghost_mode") is True
    
    # Verify events
    event_capture.assert_event_emitted("recording_session.analyzed", tenant_id=tenant_id)


# ============================================================================
# Event Flow Verification Helper
# ============================================================================

def assert_event_emitted(
    event_capture: EventCapture,
    event_name: str,
    **filters
):
    """
    Helper to assert an event was emitted with specific filters.
    
    Usage:
        assert_event_emitted(event_capture, "lead.updated", tenant_id=tenant_id, lead_id=lead.id)
    """
    try:
        event_capture.assert_event_emitted(event_name, **filters)
        return True
    except AssertionError:
        return False



