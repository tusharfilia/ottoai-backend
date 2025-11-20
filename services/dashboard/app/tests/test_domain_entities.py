from datetime import datetime, timedelta

import pytest

from app.models.appointment import Appointment, AppointmentOutcome, AppointmentStatus
from app.models.call import Call
from app.models.company import Company
from app.models.contact_card import ContactCard
from app.models.lead import Lead, LeadSource, LeadStatus
from app.schemas.shared_manifest import LEAD_STATUS_ENUM, APPOINTMENT_OUTCOME_ENUM


@pytest.fixture
def captured_events(monkeypatch):
    emitted = []

    def fake_emit(event_name: str, payload, *, tenant_id, lead_id=None, severity="info", version="1"):
        emitted.append(
            {
                "event": event_name,
                "tenant_id": tenant_id,
                "lead_id": lead_id,
                "payload": payload,
            }
        )

    monkeypatch.setattr("app.services.domain_events.emit_event", fake_emit)
    return emitted


@pytest.fixture
def seeded_domain_entities(db_session, tenant_id):
    """Seed minimal company/contact/lead/appointment/call graph."""
    company = Company(id=tenant_id, name="Test Tenant")
    db_session.add(company)

    contact = ContactCard(
        company_id=tenant_id,
        primary_phone="+15555550111",
        first_name="Pat",
        last_name="Customer",
        property_snapshot={
            "roof_type": "asphalt",
            "square_feet": 2400,
            "stories": 2,
        },
    )
    db_session.add(contact)
    db_session.flush()

    lead = Lead(
        id="lead-test-001",
        company_id=tenant_id,
        contact_card_id=contact.id,
        status=LeadStatus.NEW,
        source=LeadSource.INBOUND_CALL,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(lead)
    db_session.flush()

    appointment = Appointment(
        id="appt-test-001",
        company_id=tenant_id,
        contact_card_id=contact.id,
        lead_id=lead.id,
        assigned_rep_id=None,
        scheduled_start=datetime.utcnow() + timedelta(hours=2),
        scheduled_end=datetime.utcnow() + timedelta(hours=3),
        status=AppointmentStatus.SCHEDULED,
        outcome=AppointmentOutcome.PENDING,
    )
    db_session.add(appointment)

    call = Call(
        phone_number="+15555550111",
        company_id=tenant_id,
        contact_card_id=contact.id,
        lead_id=lead.id,
        created_at=datetime.utcnow(),
        missed_call=False,
        status="incoming",
    )
    db_session.add(call)

    db_session.commit()

    return {
        "company": company,
        "contact": contact,
        "lead": lead,
        "appointment": appointment,
        "call": call,
    }


def test_get_contact_card(client, auth_headers_exec, seeded_domain_entities):
    contact = seeded_domain_entities["contact"]
    response = client.get(f"/api/v1/contact-cards/{contact.id}", headers=auth_headers_exec)
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["id"] == contact.id
    assert payload["company_id"] == contact.company_id
    assert payload["primary_phone"] == contact.primary_phone
    assert len(payload["leads"]) == 1
    assert len(payload["appointments"]) == 1
    assert payload["recent_call_ids"]
    assert payload["property_snapshot"]["roof_type"] == "asphalt"


def test_get_lead(client, auth_headers_exec, seeded_domain_entities):
    lead = seeded_domain_entities["lead"]
    response = client.get(f"/api/v1/leads/{lead.id}", headers=auth_headers_exec)
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["lead"]["id"] == lead.id
    assert payload["lead"]["status"] == lead.status.value
    assert payload["contact"]["id"] == lead.contact_card_id
    assert len(payload["appointments"]) == 1


def test_get_appointment(client, auth_headers_exec, seeded_domain_entities):
    appointment = seeded_domain_entities["appointment"]
    response = client.get(f"/api/v1/appointments/{appointment.id}", headers=auth_headers_exec)
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["appointment"]["id"] == appointment.id
    assert payload["appointment"]["status"] == appointment.status.value
    assert payload["lead"]["id"] == appointment.lead_id


def test_create_lead_emits_event(client, auth_headers_exec, seeded_domain_entities, captured_events):
    contact = seeded_domain_entities["contact"]
    response = client.post(
        "/api/v1/leads",
        headers=auth_headers_exec,
        json={
            "contact_card_id": contact.id,
            "status": "qualified_booked",
            "source": "inbound_call",
            "priority": "high",
        },
    )
    assert response.status_code == 200
    assert any(event["event"] == "lead.created" for event in captured_events)


def test_update_appointment_emits_event(client, auth_headers_exec, seeded_domain_entities, captured_events):
    appointment = seeded_domain_entities["appointment"]
    response = client.patch(
        f"/api/v1/appointments/{appointment.id}",
        headers=auth_headers_exec,
        json={
            "outcome": "won",
            "status": "completed",
        },
    )
    assert response.status_code == 200
    matching = [event for event in captured_events if event["event"] == "appointment.updated"]
    assert matching
    assert matching[0]["payload"]["outcome"] == "won"


def test_enums_match_shared_manifest():
    assert set(item.value for item in LeadStatus) == LEAD_STATUS_ENUM
    assert set(item.value for item in AppointmentOutcome) == APPOINTMENT_OUTCOME_ENUM

