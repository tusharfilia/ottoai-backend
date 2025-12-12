#!/usr/bin/env python3
"""
Demo data seed script for OttoAI backend.
Creates realistic demo data for CSR, Sales Rep, and Executive/Manager platforms.

This script creates:
- Demo company/tenant (otto-demo-co)
- Demo CSR user (csr@otto-demo.com) - High-performing
- Demo Sales Rep user (salesrep@otto-demo.com) - High-performing
- Demo Manager/Executive user (manager@otto-demo.com)
- Contact cards with leads
- Calls with transcripts and analyses (CSR dashboard + Sales Rep assigned)
- Appointments (CSR dashboard + Sales Rep assigned)
- Rep shifts and recording sessions (Sales Rep mobile app)
- Sales reps (generic, with high/low performance variation)
- Tasks and pending actions
- SMS message threads

Usage:
    python scripts/seed_demo_data.py
    
    or
    
    python -m scripts.seed_demo_data

Environment Variables:
    DATABASE_URL: Database connection string (required)
    
The script is idempotent - safe to run multiple times.
It will reuse existing demo company/user and update or recreate other data.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta, time, date
from uuid import uuid4
import random

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from sqlalchemy import inspect
from app.database import SessionLocal, Base
from app.config import settings

# Import all models
from app.models import (
    company,
    user,
    contact_card,
    lead,
    call,
    appointment,
    task,
    message_thread,
    sales_rep,
    sales_manager,
    rep_shift,
    recording_session,
    recording_transcript,
    recording_analysis,
    key_signal,
    event_log,
    sop_compliance_result,
    lead_status_history,
    rep_assignment_history,
    onboarding,
    call_transcript,
    call_analysis,
    missed_call_queue,
)

from app.models import (
    lead_status_history,
    rep_assignment_history,
)

# Use the imported modules
Company = company.Company
User = user.User
ContactCard = contact_card.ContactCard
Lead = lead.Lead
Call = call.Call
Appointment = appointment.Appointment
Task = task.Task
MessageThread = message_thread.MessageThread
SalesRep = sales_rep.SalesRep
SalesManager = sales_manager.SalesManager
RepShift = rep_shift.RepShift
ShiftStatus = rep_shift.ShiftStatus
RecordingSession = recording_session.RecordingSession
RecordingMode = recording_session.RecordingMode
AudioStorageMode = recording_session.AudioStorageMode
TranscriptionStatus = recording_session.TranscriptionStatus
AnalysisStatus = recording_session.AnalysisStatus
CallTranscript = call_transcript.CallTranscript
CallAnalysis = call_analysis.CallAnalysis
MissedCallQueue = missed_call_queue.MissedCallQueue
MissedCallStatus = missed_call_queue.MissedCallStatus
MissedCallPriority = missed_call_queue.MissedCallPriority
MissedCallSLA = missed_call_queue.MissedCallSLA


def ensure_core_contact_tables(db: Session):
    """
    Ensure core contact/lead/appointment tables exist in the target database.
    This is a defensive helper for environments where Alembic migrations
    haven't fully applied but models expect these tables.
    """
    inspector = inspect(db.bind)
    existing = set(inspector.get_table_names())
    tables_to_create = []

    if "contact_cards" not in existing:
        tables_to_create.append(ContactCard.__table__)
    if "leads" not in existing:
        tables_to_create.append(Lead.__table__)
    if "appointments" not in existing:
        tables_to_create.append(Appointment.__table__)
    # Ensure rep_shifts exists as SalesRep may have FK/relationships to it
    if "rep_shifts" not in existing:
        tables_to_create.append(rep_shift.RepShift.__table__)
    # Ensure recording_sessions exists as SalesRep is related to it
    if "recording_sessions" not in existing:
        tables_to_create.append(recording_session.RecordingSession.__table__)

    if tables_to_create:
        Base.metadata.create_all(bind=db.bind, tables=tables_to_create)

# Demo entity IDs from Clerk
# Note: The org ID format in JWT tokens may differ slightly from the seed constant
# If you see a different org ID in your JWT token, update this constant to match
DEMO_CLERK_ORG_ID = "org_36EW2DYBw4gpJaL4ASL2ZxFZPO9"  # Updated to match JWT token org ID

# CSR Demo User
DEMO_CLERK_USER_ID = "user_36EWfrANnNFNL2dN3wdAo9z2FK2"
DEMO_USER_EMAIL = "csr@otto-demo.com"
DEMO_USER_USERNAME = "csrdemo"

# Sales Rep Demo User
DEMO_SALES_REP_USER_ID = "user_36M3F0kllDOemX3prAPP1Zb8C5f"
DEMO_SALES_REP_EMAIL = "salesrep@otto-demo.com"
DEMO_SALES_REP_USERNAME = "salesrep"

# Manager/Executive Demo User
DEMO_MANAGER_USER_ID = "user_36M3Kp5NQjnGhcmu5NM8nhOCqg2"
DEMO_MANAGER_EMAIL = "manager@otto-demo.com"
DEMO_MANAGER_USERNAME = "managerdemo"

DEMO_COMPANY_NAME = "otto-demo-co"

# Demo data markers
DEMO_MARKER = "__DEMO__"


def get_or_create_demo_company(db: Session) -> Company:
    """Get or create the demo company."""
    demo_company = db.query(Company).filter(Company.id == DEMO_CLERK_ORG_ID).first()
    
    if not demo_company:
        # Check if another company with the demo name exists
        existing_with_name = db.query(Company).filter(
            Company.name == DEMO_COMPANY_NAME,
            Company.id != DEMO_CLERK_ORG_ID
        ).first()
        
        if existing_with_name:
            # Rename the old company to avoid conflict
            existing_with_name.name = f"{DEMO_COMPANY_NAME}-old-{existing_with_name.id[:8]}"
            db.commit()
            print(f"ℹ️  Renamed existing company with name '{DEMO_COMPANY_NAME}' to avoid conflict")
        
        demo_company = Company(
            id=DEMO_CLERK_ORG_ID,
            name=DEMO_COMPANY_NAME,
            phone_number="+1-555-123-4567",
            address="123 Demo Street, Demo City, DC 12345",
            industry="Roofing",
            timezone="America/New_York",
            subscription_status="active",
            onboarding_completed=True,
            onboarding_completed_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(demo_company)
        db.commit()
        db.refresh(demo_company)
        print(f"✓ Created demo company: {DEMO_COMPANY_NAME} ({DEMO_CLERK_ORG_ID})")
    else:
        # Update existing company to ensure it's properly configured
        # Check if name update would conflict
        existing_with_name = db.query(Company).filter(
            Company.name == DEMO_COMPANY_NAME,
            Company.id != DEMO_CLERK_ORG_ID
        ).first()
        
        if existing_with_name:
            # Rename the conflicting company first
            existing_with_name.name = f"{DEMO_COMPANY_NAME}-old-{existing_with_name.id[:8]}"
            db.commit()
            print(f"ℹ️  Renamed existing company with name '{DEMO_COMPANY_NAME}' to avoid conflict")
        
        # Now safely update the name
        demo_company.name = DEMO_COMPANY_NAME
        demo_company.phone_number = "+1-555-123-4567"
        demo_company.industry = "Roofing"
        demo_company.subscription_status = "active"
        demo_company.onboarding_completed = True
        demo_company.updated_at = datetime.utcnow()
        db.commit()
        print(f"✓ Using existing demo company: {DEMO_COMPANY_NAME} ({DEMO_CLERK_ORG_ID})")
    
    return demo_company


def get_or_create_demo_user(db: Session, company: Company) -> User:
    """Get or create the demo CSR user."""
    demo_user = db.query(User).filter(User.id == DEMO_CLERK_USER_ID).first()
    
    if not demo_user:
        demo_user = User(
            id=DEMO_CLERK_USER_ID,
            email=DEMO_USER_EMAIL,
            username=DEMO_USER_USERNAME,
            name="Demo CSR",
            role="csr",
            company_id=company.id,
        )
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)
        print(f"✓ Created demo CSR user: {DEMO_USER_EMAIL} ({DEMO_CLERK_USER_ID})")
    else:
        # Update existing user
        demo_user.email = DEMO_USER_EMAIL
        demo_user.username = DEMO_USER_USERNAME
        demo_user.name = "Demo CSR"
        demo_user.role = "csr"
        demo_user.company_id = company.id
        db.commit()
        print(f"✓ Using existing demo CSR user: {DEMO_USER_EMAIL} ({DEMO_CLERK_USER_ID})")
    
    return demo_user


def create_demo_contact_cards(db: Session, company: Company) -> list[ContactCard]:
    """Create demo contact cards with realistic data."""
    # Ensure required tables exist (especially on partially-migrated databases)
    ensure_core_contact_tables(db)
    # For idempotency, wipe existing demo data for this company in the right FK order:
    # 1) Delete missed_call_queue (which reference calls)
    # 2) Delete tasks (which reference appointments, calls, contact_cards, leads)
    # 3) Delete message_threads (which reference contact_cards and calls)
    # 4) Delete call_analyses and call_transcripts (which reference calls) - AFTER calls would be better but we delete by tenant_id
    # 5) Delete calls (which reference contact_cards and leads)
    # 6) Delete recording_sessions (which reference appointments)
    # 7) Delete appointments (which reference leads/contact_cards)
    # 8) Delete leads (which reference contact_cards)
    # 9) Delete contact_cards
    inspector = inspect(db.bind)
    if "missed_call_queue" in inspector.get_table_names():
        db.query(MissedCallQueue).filter(MissedCallQueue.company_id == company.id).delete(synchronize_session=False)
    if "tasks" in inspector.get_table_names():
        db.query(Task).filter(Task.company_id == company.id).delete(synchronize_session=False)
    if "message_threads" in inspector.get_table_names():
        db.query(MessageThread).filter(MessageThread.company_id == company.id).delete(synchronize_session=False)
    # Delete call_analyses and call_transcripts by finding calls first, then deleting analyses/transcripts
    if "calls" in inspector.get_table_names():
        call_ids = [c.call_id for c in db.query(Call).filter(Call.company_id == company.id).all()]
        table_names = inspector.get_table_names()
        if call_ids:
            if "call_analysis" in table_names:
                db.query(CallAnalysis).filter(CallAnalysis.call_id.in_(call_ids)).delete(synchronize_session=False)
            if "call_analyses" in table_names:
                db.query(CallAnalysis).filter(CallAnalysis.call_id.in_(call_ids)).delete(synchronize_session=False)
            if "call_transcript" in table_names:
                db.query(CallTranscript).filter(CallTranscript.call_id.in_(call_ids)).delete(synchronize_session=False)
            if "call_transcripts" in table_names:
                db.query(CallTranscript).filter(CallTranscript.call_id.in_(call_ids)).delete(synchronize_session=False)
        db.query(Call).filter(Call.company_id == company.id).delete(synchronize_session=False)
    if "recording_sessions" in inspector.get_table_names():
        db.query(RecordingSession).filter(RecordingSession.company_id == company.id).delete(synchronize_session=False)
    db.query(Appointment).filter(Appointment.company_id == company.id).delete(synchronize_session=False)
    db.query(Lead).filter(Lead.company_id == company.id).delete(synchronize_session=False)
    db.query(ContactCard).filter(ContactCard.company_id == company.id).delete(synchronize_session=False)
    db.commit()
    
    # Sample contact data
    contact_data = [
        {"first": "John", "last": "Smith", "phone": "+1-555-0101", "email": "john.smith@example.com", "address": "123 Oak St, Springfield, IL 62701", "tags": ["HVAC", "Urgent"]},
        {"first": "Sarah", "last": "Johnson", "phone": "+1-555-0102", "email": "sarah.j@example.com", "address": "456 Maple Ave, Springfield, IL 62702", "tags": ["Roofing"]},
        {"first": "Michael", "last": "Williams", "phone": "+1-555-0103", "email": "mike.williams@example.com", "address": "789 Pine Rd, Springfield, IL 62703", "tags": ["Solar", "High Value"]},
        {"first": "Emily", "last": "Brown", "phone": "+1-555-0104", "email": "emily.brown@example.com", "address": "321 Elm St, Springfield, IL 62704", "tags": ["HVAC"]},
        {"first": "David", "last": "Jones", "phone": "+1-555-0105", "email": "david.jones@example.com", "address": "654 Cedar Ln, Springfield, IL 62705", "tags": ["Roofing", "Warm"]},
        {"first": "Jessica", "last": "Garcia", "phone": "+1-555-0106", "email": "jessica.g@example.com", "address": "987 Birch Dr, Springfield, IL 62706", "tags": ["Solar"]},
        {"first": "Robert", "last": "Miller", "phone": "+1-555-0107", "email": None, "address": "147 Spruce Way, Springfield, IL 62707", "tags": ["HVAC"]},  # Missing email
        {"first": "Amanda", "last": "Davis", "phone": "+1-555-0108", "email": "amanda.davis@example.com", "address": "258 Willow Ct, Springfield, IL 62708", "tags": ["Roofing", "Qualified"]},
        {"first": "James", "last": "Rodriguez", "phone": "+1-555-0109", "email": "james.r@example.com", "address": "369 Ash Blvd, Springfield, IL 62709", "tags": ["Solar", "Hot"]},
        {"first": "Lisa", "last": "Martinez", "phone": "+1-555-0110", "email": "lisa.m@example.com", "address": "741 Hickory St, Springfield, IL 62710", "tags": ["HVAC"]},
        {"first": "Christopher", "last": "Hernandez", "phone": "+1-555-0111", "email": "chris.h@example.com", "address": "852 Poplar Ave, Springfield, IL 62711", "tags": ["Roofing"]},
        {"first": "Michelle", "last": "Lopez", "phone": "+1-555-0112", "email": "michelle.l@example.com", "address": "963 Sycamore Rd, Springfield, IL 62712", "tags": ["Solar", "Warm"]},
        {"first": "Daniel", "last": "Gonzalez", "phone": "+1-555-0113", "email": None, "address": "159 Magnolia Ln, Springfield, IL 62713", "tags": ["HVAC"]},  # Missing email
        {"first": "Ashley", "last": "Wilson", "phone": "+1-555-0114", "email": "ashley.w@example.com", "address": "357 Dogwood Dr, Springfield, IL 62714", "tags": ["Roofing", "Hot"]},
        {"first": "Matthew", "last": "Anderson", "phone": "+1-555-0115", "email": "matt.anderson@example.com", "address": "468 Redwood Way, Springfield, IL 62715", "tags": ["Solar"]},
    ]
    
    contact_cards = []
    for data in contact_data:
        contact = ContactCard(
            id=str(uuid4()),
            company_id=company.id,
            primary_phone=data["phone"],
            email=data["email"],
            first_name=data["first"],
            last_name=data["last"],
            address=data["address"],
            city="Springfield",
            state="IL",
            postal_code=data["address"].split()[-1],
            custom_metadata={"demo": True, "tags": data["tags"]},
            created_at=datetime.utcnow() - timedelta(days=random.randint(1, 60)),
            updated_at=datetime.utcnow(),
        )
        db.add(contact)
        contact_cards.append(contact)
    
    db.commit()
    print(f"✓ Created {len(contact_cards)} demo contact cards")
    return contact_cards


def create_demo_leads(db: Session, company: Company, contact_cards: list[ContactCard]) -> list[Lead]:
    """Create demo leads with various statuses."""
    # Delete existing demo leads
    existing_leads = db.query(Lead).filter(Lead.company_id == company.id).all()
    for lead_obj in existing_leads:
        db.delete(lead_obj)
    db.commit()
    
    lead_statuses = [
        "new",
        "warm",
        "hot",
        "qualified_booked",
        "qualified_unbooked",
        "nurturing",
        "closed_won",
        "closed_lost",
    ]
    
    leads = []
    for i, contact_card_obj in enumerate(contact_cards):
        # Vary lead statuses
        status = lead_statuses[i % len(lead_statuses)]
        
        tags_value = contact_card_obj.custom_metadata.get("tags", [])
        # Store tags as an object to align with schema expectation (dict JSON)
        lead_obj = Lead(
            id=str(uuid4()),
            company_id=company.id,
            contact_card_id=contact_card_obj.id,
            status=status,
            source="inbound_call" if i % 2 == 0 else "inbound_web",
            priority="high" if status in ["hot", "qualified_booked"] else "medium",
            score=random.randint(50, 100),
            tags={"labels": tags_value} if isinstance(tags_value, list) else tags_value,
            last_contacted_at=datetime.utcnow() - timedelta(days=random.randint(0, 7)),
            last_qualified_at=datetime.utcnow() - timedelta(days=random.randint(0, 14)) if status in ["qualified_booked", "qualified_unbooked"] else None,
            deal_status="won" if status == "closed_won" else ("lost" if status == "closed_lost" else "new"),
            deal_size=random.uniform(5000, 50000) if status in ["closed_won", "qualified_booked"] else None,
            closed_at=datetime.utcnow() - timedelta(days=random.randint(1, 30)) if status in ["closed_won", "closed_lost"] else None,
            created_at=datetime.utcnow() - timedelta(days=random.randint(1, 60)),
            updated_at=datetime.utcnow(),
        )
        db.add(lead_obj)
        leads.append(lead_obj)
    
    db.commit()
    print(f"✓ Created {len(leads)} demo leads with various statuses")
    return leads


def create_demo_calls(db: Session, company: Company, contact_cards: list[ContactCard], leads: list[Lead]) -> list[Call]:
    """Create demo calls with realistic data."""
    # Delete existing demo call data in correct FK order:
    # 1) Delete call analyses (FK to calls)
    # 2) Delete call transcripts (FK to calls)
    # 3) Delete calls
    db.query(CallAnalysis).filter(CallAnalysis.tenant_id == company.id).delete(synchronize_session=False)
    db.query(CallTranscript).filter(CallTranscript.tenant_id == company.id).delete(synchronize_session=False)
    db.query(Call).filter(Call.company_id == company.id).delete(synchronize_session=False)
    db.commit()
    
    calls = []
    call_directions = ["inbound", "outbound", "missed"]
    
    for i, contact_card_obj in enumerate(contact_cards):
        # Create 1-3 calls per contact
        num_calls = random.randint(1, 3)
        lead_obj = leads[i] if i < len(leads) else None
        # Store lead_id before accessing to avoid session expiration issues
        lead_id = lead_obj.id if lead_obj else None
        lead_status = lead_obj.status if lead_obj else None
        
        for j in range(num_calls):
            call_time = datetime.utcnow() - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
            direction = call_directions[random.randint(0, len(call_directions) - 1)]
            duration = random.randint(30, 600) if direction != "missed" else 0
            
            call_obj = Call(
                call_id=None,  # Auto-increment
                company_id=company.id,
                contact_card_id=contact_card_obj.id,
                lead_id=lead_id,
                phone_number=contact_card_obj.primary_phone,
                name=f"{contact_card_obj.first_name} {contact_card_obj.last_name}",
                missed_call=(direction == "missed"),
                transcript=f"Demo transcript for call {i+1}-{j+1}. Customer: 'I need a quote for {random.choice(['roofing', 'HVAC', 'solar'])} work.' Rep: 'I can help with that. When would be a good time for an estimate?'" if direction != "missed" else None,
                status="completed" if direction != "missed" else "missed",
                last_call_duration=duration,
                last_call_timestamp=call_time.isoformat(),
                booked=random.choice([True, False]) if direction == "inbound" and not (direction == "missed") else False,
                bought=random.choice([True, False]) if lead_status == "closed_won" else False,
                price_if_bought=random.uniform(10000, 40000) if random.choice([True, False]) else None,
                created_at=call_time,
                updated_at=call_time,
            )
            db.add(call_obj)
            calls.append(call_obj)
    
    db.commit()
    db.flush()  # Get call_ids assigned
    print(f"✓ Created {len(calls)} demo calls")
    return calls


def create_demo_call_transcripts(db: Session, company: Company, calls: list[Call]) -> list[CallTranscript]:
    """Create demo call transcripts for some calls."""
    # Delete existing demo transcripts
    existing_transcripts = db.query(CallTranscript).filter(CallTranscript.tenant_id == company.id).all()
    for transcript in existing_transcripts:
        db.delete(transcript)
    db.commit()
    
    transcripts = []
    # Create transcripts for about 60% of calls
    calls_with_transcripts = random.sample(calls, int(len(calls) * 0.6))
    
    sample_transcripts = [
        "Rep: Hello, this is John from Otto Roofing. How can I help you today?\nCustomer: Hi, I'm interested in getting a quote for a new roof.\nRep: Great! I'd be happy to help. What's your address?\nCustomer: 123 Oak Street, Springfield.\nRep: Perfect. When would be a good time for one of our estimators to come out?\nCustomer: How about this Saturday?\nRep: Saturday works. I can schedule you for 10 AM. Does that work?\nCustomer: Yes, that's perfect. Thank you!",
        "Rep: Good morning, this is Sarah with Otto. I'm following up on your inquiry.\nCustomer: Oh yes, I was looking at your website.\nRep: Wonderful. Are you still interested in getting an estimate?\nCustomer: Yes, but I need to talk to my spouse first.\nRep: I understand. Would it help if I sent you some information about our financing options?\nCustomer: That would be great.\nRep: I'll send that over today. When would be a good time to follow up?\nCustomer: Maybe next week?\nRep: Perfect. I'll call you next Tuesday.",
        "Rep: Hi, this is Mike from Otto. I see you called earlier.\nCustomer: Yes, I missed your call. I'm looking for HVAC services.\nRep: No problem. What kind of HVAC work are you looking for?\nCustomer: My AC unit is making strange noises.\nRep: That doesn't sound good. We can send a technician out to take a look. When's convenient?\nCustomer: Tomorrow afternoon would work.\nRep: I can schedule you for 2 PM tomorrow. Does that work?\nCustomer: Yes, thank you!",
    ]
    
    for call_obj in calls_with_transcripts:
        if call_obj.missed_call or not call_obj.transcript:
            continue
            
        transcript_text = random.choice(sample_transcripts)
        word_count = len(transcript_text.split())
        
        transcript = CallTranscript(
            id=str(uuid4()),
            call_id=call_obj.call_id,
            tenant_id=company.id,
            uwc_job_id=f"uwc-demo-{call_obj.call_id}",
            transcript_text=transcript_text,
            speaker_labels=[
                {"speaker": "rep", "text": "Hello, this is John from Otto Roofing.", "start_time": 0.0, "end_time": 3.5},
                {"speaker": "customer", "text": "Hi, I'm interested in getting a quote.", "start_time": 4.0, "end_time": 7.2},
            ],
            confidence_score=random.uniform(0.85, 0.98),
            language="en-US",
            word_count=word_count,
            processing_time_ms=random.randint(2000, 5000),
            model_version="v1",
            created_at=call_obj.created_at,
            updated_at=call_obj.created_at,
        )
        db.add(transcript)
        transcripts.append(transcript)
    
    db.commit()
    print(f"✓ Created {len(transcripts)} demo call transcripts")
    return transcripts


def create_demo_call_analyses(db: Session, company: Company, calls: list[Call]) -> list[CallAnalysis]:
    """Create demo call analyses with AI insights."""
    # Delete existing demo analyses
    existing_analyses = db.query(CallAnalysis).filter(CallAnalysis.tenant_id == company.id).all()
    for analysis in existing_analyses:
        db.delete(analysis)
    db.commit()
    
    analyses = []
    # Create analyses for calls with transcripts
    calls_with_analyses = [c for c in calls if not c.missed_call and c.transcript]
    
    sample_objections = [
        ["price", "timeline"],
        ["competitor"],
        ["need_spouse_approval"],
        [],
    ]
    
    sample_coaching_tips = [
        [
            {"tip": "Set agenda earlier in conversation", "priority": "high", "category": "sales_process", "timestamp": 5.2},
            {"tip": "Ask more open-ended questions", "priority": "medium", "category": "questioning", "timestamp": 45.0},
        ],
        [
            {"tip": "Address price objection with value proposition", "priority": "high", "category": "objection_handling", "timestamp": 120.5},
        ],
        [],
    ]
    
    for call_obj in calls_with_analyses[:int(len(calls_with_analyses) * 0.7)]:  # 70% of calls with transcripts
        objections = random.choice(sample_objections)
        coaching_tips = random.choice(sample_coaching_tips)
        
        analysis = CallAnalysis(
            id=str(uuid4()),
            call_id=call_obj.call_id,
            tenant_id=company.id,
            uwc_job_id=f"uwc-analysis-{call_obj.call_id}",
            objections=objections if objections else None,
            objection_details=[
                {
                    "type": obj,
                    "timestamp": random.uniform(30, 300),
                    "quote": f"Customer said: 'That's too {obj} for me'",
                    "resolved": random.choice([True, False])
                }
                for obj in objections
            ] if objections else None,
            sentiment_score=random.uniform(0.6, 0.95),
            engagement_score=random.uniform(0.5, 0.9),
            coaching_tips=coaching_tips if coaching_tips else None,
            sop_stages_completed=["connect", "agenda", "assess"],
            sop_stages_missed=["close", "referral"],
            sop_compliance_score=random.uniform(6.0, 9.0),
            rehash_score=random.uniform(5.0, 8.5),
            talk_time_ratio=random.uniform(0.25, 0.45),
            lead_quality=random.choice(["qualified", "hot", "warm", "cold"]),
            conversion_probability=random.uniform(0.3, 0.85),
            meeting_segments=[
                {"type": "rapport", "start": 0.0, "end": 120.5},
                {"type": "agenda", "start": 120.5, "end": 180.0},
                {"type": "proposal", "start": 180.0, "end": 400.0}
            ],
            analyzed_at=call_obj.created_at + timedelta(minutes=5),
            analysis_version="v1",
            processing_time_ms=random.randint(3000, 8000),
            created_at=call_obj.created_at + timedelta(minutes=5),
            updated_at=call_obj.created_at + timedelta(minutes=5),
        )
        db.add(analysis)
        analyses.append(analysis)
    
    db.commit()
    print(f"✓ Created {len(analyses)} demo call analyses")
    return analyses


def create_demo_sales_reps(db: Session, company: Company) -> list[SalesRep]:
    """Create demo sales reps (including one low-performing rep for comparison)."""
    # Ensure core tables (including rep_shifts) exist before working with reps
    ensure_core_contact_tables(db)
    
    # Create demo rep users first
    rep_users = []
    rep_data = [
        {"name": "Jane Installer", "email": "jane.installer@otto-demo.com", "username": "janeinstaller", "is_high_performing": True},
        {"name": "Bob Closer", "email": "bob.closer@otto-demo.com", "username": "bobcloser", "is_high_performing": False},  # Low-performing
    ]
    
    for rep_info in rep_data:
        rep_user = db.query(User).filter(User.email == rep_info["email"]).first()
        if not rep_user:
            rep_user = User(
                id=str(uuid4()),
                email=rep_info["email"],
                username=rep_info["username"],
                name=rep_info["name"],
                role="sales_rep",
                company_id=company.id,
            )
            db.add(rep_user)
            rep_users.append(rep_user)
        else:
            rep_user.role = "sales_rep"
            rep_user.company_id = company.id
            rep_users.append(rep_user)
    
    db.commit()
    
    # Create or get sales rep profiles
    reps = []
    rep_performance_map = {}  # Track which reps are high/low performing
    for i, rep_user in enumerate(rep_users):
        # Check if SalesRep already exists for this user
        rep = db.query(SalesRep).filter(SalesRep.user_id == rep_user.id).first()
        is_high_performing = rep_data[i].get("is_high_performing", True)
        rep_performance_map[rep_user.id] = is_high_performing
        
        if not rep:
            rep = SalesRep(
                user_id=rep_user.id,
                company_id=company.id,
                recording_mode="normal",
                allow_location_tracking=True,
                allow_recording=True,
            )
            db.add(rep)
        else:
            # Update existing rep to ensure correct company_id
            rep.company_id = company.id
            rep.recording_mode = "normal"
            rep.allow_location_tracking = True
            rep.allow_recording = True
        reps.append(rep)
    
    db.commit()
    print(f"✓ Created/updated {len(reps)} demo sales reps (1 high-performing, 1 low-performing)")
    # Return both reps list and performance map
    return reps, rep_performance_map


def create_demo_appointments(db: Session, company: Company, contact_cards: list[ContactCard], leads: list[Lead], reps: list[SalesRep], performance_map: dict = None) -> list[Appointment]:
    """Create demo appointments (upcoming and past) with performance variation."""
    # Delete existing demo appointments (must delete recording_sessions first due to FK)
    # Check if recording_sessions table exists
    inspector = inspect(db.bind)
    if "recording_sessions" in inspector.get_table_names():
        db.query(RecordingSession).filter(RecordingSession.company_id == company.id).delete(synchronize_session=False)
    existing_appointments = db.query(Appointment).filter(Appointment.company_id == company.id).all()
    for apt in existing_appointments:
        db.delete(apt)
    db.commit()
    
    appointments = []
    # Create appointments for ~5 contacts
    selected_contacts = random.sample(contact_cards, min(5, len(contact_cards)))
    
    performance_map = performance_map or {}
    
    for i, contact_card_obj in enumerate(selected_contacts):
        lead_obj = leads[contact_cards.index(contact_card_obj)] if contact_card_obj in contact_cards else None
        rep = reps[random.randint(0, len(reps) - 1)] if reps else None
        is_rep_high_performing = performance_map.get(rep.user_id, True) if rep else True
        
        # Mix of upcoming and past appointments
        if i < 3:
            # Upcoming appointments
            scheduled_start = datetime.utcnow() + timedelta(days=random.randint(1, 7), hours=random.randint(9, 17))
            status = "scheduled"
        else:
            # Past appointments
            scheduled_start = datetime.utcnow() - timedelta(days=random.randint(1, 30), hours=random.randint(9, 17))
            status = random.choice([
                "completed",
                "no_show",
                "cancelled",
            ])
        
        scheduled_end = scheduled_start + timedelta(hours=1)
        
        # Performance-based outcomes: high-performing reps win more
        # IMPORTANT: Always use string values, never enum objects, to avoid AttributeError issues
        if status == "completed":
            win_prob = 0.75 if is_rep_high_performing else 0.35
            outcome = "won" if random.random() < win_prob else "lost"
        else:
            outcome = "pending"  # String value, not enum
        
        apt = Appointment(
            id=str(uuid4()),
            company_id=company.id,
            lead_id=lead_obj.id if lead_obj else None,
            contact_card_id=contact_card_obj.id,
            assigned_rep_id=rep.user_id if rep else None,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            status=status,
            outcome=outcome,
            location=contact_card_obj.address,
            geo_lat=random.uniform(39.7, 39.9),
            geo_lng=random.uniform(-89.7, -89.5),
            service_type=random.choice(["Roofing", "HVAC", "Solar"]),
            notes=f"Demo appointment notes for {contact_card_obj.first_name} {contact_card_obj.last_name}",
            deal_size=random.uniform(12000, 45000) if outcome == "won" else (random.uniform(8000, 20000) if status == "completed" else None),
            material_type=random.choice(["Asphalt", "Metal", "Tile"]) if random.choice([True, False]) else None,
            financing_type=random.choice(["Cash", "Financing", "Lease"]) if random.choice([True, False]) else None,
            arrival_at=scheduled_start + timedelta(minutes=5) if status == "completed" else None,
            departure_at=scheduled_end if status == "completed" else None,
            on_site_duration=random.randint(45, 90) if status == "completed" else None,
            created_at=scheduled_start - timedelta(days=random.randint(1, 14)),
            updated_at=datetime.utcnow(),
        )
        db.add(apt)
        appointments.append(apt)
    
    db.commit()
    print(f"✓ Created {len(appointments)} demo appointments")
    return appointments


def create_demo_tasks(db: Session, company: Company, contact_cards: list[ContactCard], leads: list[Lead], appointments: list[Appointment], calls: list[Call], user: User) -> list[Task]:
    """Create demo tasks for the CSR user."""
    # If tasks table doesn't exist in this DB (e.g. partial migrations), skip gracefully
    inspector = inspect(db.bind)
    if "tasks" not in inspector.get_table_names():
        print("ℹ️ 'tasks' table not found in this database; skipping task seeding.")
        return []
    # Delete existing demo tasks
    existing_tasks = db.query(Task).filter(Task.company_id == company.id).all()
    for task_obj in existing_tasks:
        db.delete(task_obj)
    db.commit()
    
    tasks = []
    task_descriptions = [
        "Call back about quote follow-up",
        "Text ETA for technician",
        "Send financing options",
        "Follow up on appointment confirmation",
        "Send contract documents",
        "Schedule follow-up call",
        "Update customer on project status",
        "Request photos for estimate",
    ]
    
    for i in range(8):
        contact_card_obj = contact_cards[i % len(contact_cards)]
        lead_obj = leads[i % len(leads)] if i < len(leads) else None
        appointment_obj = appointments[i % len(appointments)] if appointments and i < len(appointments) else None
        call_obj = calls[i % len(calls)] if calls and i < len(calls) else None
        
        # Mix of statuses
        if i < 3:
            status = "open"
            due_at = datetime.utcnow() + timedelta(days=random.randint(0, 2))
            completed_at = None
            completed_by = None
        elif i < 5:
            status = "overdue"
            due_at = datetime.utcnow() - timedelta(days=random.randint(1, 5))
            completed_at = None
            completed_by = None
        else:
            status = "completed"
            due_at = datetime.utcnow() - timedelta(days=random.randint(1, 7))
            completed_at = due_at + timedelta(hours=2)
            completed_by = user.id
        
        task_obj = Task(
            id=str(uuid4()),
            company_id=company.id,
            contact_card_id=contact_card_obj.id,
            lead_id=lead_obj.id if lead_obj else None,
            appointment_id=appointment_obj.id if appointment_obj else None,
            call_id=call_obj.call_id if call_obj else None,
            description=task_descriptions[i % len(task_descriptions)],
            assigned_to="csr",
            source="manual",
            due_at=due_at,
            status=status,
            completed_at=completed_at,
            completed_by=completed_by,
            priority=random.choice(["high", "medium", "low"]),
            created_at=due_at - timedelta(days=random.randint(1, 5)),
            updated_at=datetime.utcnow(),
        )
        db.add(task_obj)
        tasks.append(task_obj)
    
    db.commit()
    print(f"✓ Created {len(tasks)} demo tasks")
    return tasks


def create_demo_message_threads(db: Session, company: Company, contact_cards: list[ContactCard], calls: list[Call]) -> list[MessageThread]:
    """Create demo SMS message threads."""
    # If message_threads table doesn't exist (e.g. partial migrations), skip gracefully
    inspector = inspect(db.bind)
    if "message_threads" not in inspector.get_table_names():
        print("ℹ️ 'message_threads' table not found in this database; skipping SMS thread seeding.")
        return []

    # Delete existing demo messages
    existing_messages = db.query(MessageThread).filter(MessageThread.company_id == company.id).all()
    for msg in existing_messages:
        db.delete(msg)
    db.commit()
    
    threads = []
    # Create threads for 3-4 contacts
    selected_contacts = random.sample(contact_cards, min(4, len(contact_cards)))
    
    sample_conversations = [
        [
            {"role": "customer", "direction": "inbound", "body": "Hi, I called earlier about a roofing quote. When can someone come out?", "time_offset": 0},
            {"role": "csr", "direction": "outbound", "body": "Hi! Thanks for reaching out. I can schedule an estimator for this Saturday at 10 AM. Does that work?", "time_offset": 5},
            {"role": "customer", "direction": "inbound", "body": "Yes, that works perfect. Thank you!", "time_offset": 10},
        ],
        [
            {"role": "customer", "direction": "inbound", "body": "I need to reschedule my appointment. Can we do next week instead?", "time_offset": 0},
            {"role": "csr", "direction": "outbound", "body": "Of course! What day works best for you next week?", "time_offset": 3},
            {"role": "customer", "direction": "inbound", "body": "Tuesday or Wednesday afternoon would be great", "time_offset": 8},
            {"role": "csr", "direction": "outbound", "body": "I can schedule you for Tuesday at 2 PM. Sound good?", "time_offset": 12},
            {"role": "customer", "direction": "inbound", "body": "Perfect, see you then!", "time_offset": 15},
        ],
        [
            {"role": "csr", "direction": "outbound", "body": "Hi! This is a reminder that your appointment is tomorrow at 10 AM. Please reply to confirm.", "time_offset": 0},
            {"role": "customer", "direction": "inbound", "body": "Yes, I'll be there. Thanks for the reminder!", "time_offset": 2},
        ],
        [
            {"role": "customer", "direction": "inbound", "body": "What's the ETA for the technician? I've been waiting.", "time_offset": 0},
            {"role": "csr", "direction": "outbound", "body": "I apologize for the delay. Let me check and get back to you in 5 minutes.", "time_offset": 3},
            {"role": "csr", "direction": "outbound", "body": "Update: Technician should arrive within 30 minutes. Sorry for the wait!", "time_offset": 8},
            {"role": "customer", "direction": "inbound", "body": "Thanks for the update!", "time_offset": 10},
        ],
    ]
    
    for i, contact_card_obj in enumerate(selected_contacts):
        conversation = sample_conversations[i % len(sample_conversations)]
        call_obj = calls[contact_cards.index(contact_card_obj)] if contact_card_obj in contact_cards and contact_cards.index(contact_card_obj) < len(calls) else None
        
        base_time = datetime.utcnow() - timedelta(days=random.randint(1, 14))
        
        for msg_data in conversation:
            sender_role_map = {
                "customer": "customer",
                "csr": "csr",
            }
            
            direction_map = {
                "inbound": "inbound",
                "outbound": "outbound",
            }
            
            msg = MessageThread(
                id=str(uuid4()),
                company_id=company.id,
                contact_card_id=contact_card_obj.id,
                call_id=call_obj.call_id if call_obj else None,
                sender=contact_card_obj.primary_phone if msg_data["role"] == "customer" else company.phone_number,
                sender_role=sender_role_map[msg_data["role"]],
                body=msg_data["body"],
                message_type="manual",
                direction=direction_map[msg_data["direction"]],
                provider="Twilio",
                message_sid=f"SM{random.randint(1000000000000000, 9999999999999999)}",
                delivered=True,
                delivered_at=base_time + timedelta(minutes=msg_data["time_offset"]),
                read=msg_data["direction"] == "inbound",
                read_at=base_time + timedelta(minutes=msg_data["time_offset"] + 1) if msg_data["direction"] == "inbound" else None,
                created_at=base_time + timedelta(minutes=msg_data["time_offset"]),
                updated_at=base_time + timedelta(minutes=msg_data["time_offset"]),
            )
            db.add(msg)
            threads.append(msg)
    
    db.commit()
    print(f"✓ Created {len(threads)} demo SMS messages in {len(selected_contacts)} threads")
    return threads


def get_or_create_demo_sales_rep_user(db: Session, company: Company) -> User:
    """Get or create the demo Sales Rep user."""
    demo_rep_user = db.query(User).filter(User.id == DEMO_SALES_REP_USER_ID).first()
    
    if not demo_rep_user:
        demo_rep_user = User(
            id=DEMO_SALES_REP_USER_ID,
            email=DEMO_SALES_REP_EMAIL,
            username=DEMO_SALES_REP_USERNAME,
            name="Sales Rep Demo",
            role="sales_rep",
            company_id=company.id,
        )
        db.add(demo_rep_user)
        db.commit()
        db.refresh(demo_rep_user)
        print(f"✓ Created demo Sales Rep user: {DEMO_SALES_REP_EMAIL} ({DEMO_SALES_REP_USER_ID})")
    else:
        # Update existing user
        demo_rep_user.email = DEMO_SALES_REP_EMAIL
        demo_rep_user.username = DEMO_SALES_REP_USERNAME
        demo_rep_user.name = "Sales Rep Demo"
        demo_rep_user.role = "sales_rep"
        demo_rep_user.company_id = company.id
        db.commit()
        print(f"✓ Using existing demo Sales Rep user: {DEMO_SALES_REP_EMAIL} ({DEMO_SALES_REP_USER_ID})")
    
    # Ensure SalesRep profile exists
    rep_profile = db.query(SalesRep).filter(SalesRep.user_id == DEMO_SALES_REP_USER_ID).first()
    if not rep_profile:
        rep_profile = SalesRep(
            user_id=demo_rep_user.id,
            company_id=company.id,
            recording_mode="normal",
            allow_location_tracking=True,
            allow_recording=True,
        )
        db.add(rep_profile)
        db.commit()
        print(f"✓ Created SalesRep profile for {DEMO_SALES_REP_EMAIL}")
    
    return demo_rep_user


def get_or_create_demo_manager_user(db: Session, company: Company) -> User:
    """Get or create the demo Manager/Executive user."""
    demo_manager_user = db.query(User).filter(User.id == DEMO_MANAGER_USER_ID).first()
    
    if not demo_manager_user:
        demo_manager_user = User(
            id=DEMO_MANAGER_USER_ID,
            email=DEMO_MANAGER_EMAIL,
            username=DEMO_MANAGER_USERNAME,
            name="Manager Demo",
            role="manager",
            company_id=company.id,
        )
        db.add(demo_manager_user)
        db.commit()
        db.refresh(demo_manager_user)
        print(f"✓ Created demo Manager user: {DEMO_MANAGER_EMAIL} ({DEMO_MANAGER_USER_ID})")
    else:
        # Update existing user
        demo_manager_user.email = DEMO_MANAGER_EMAIL
        demo_manager_user.username = DEMO_MANAGER_USERNAME
        demo_manager_user.name = "Manager Demo"
        demo_manager_user.role = "manager"
        demo_manager_user.company_id = company.id
        db.commit()
        print(f"✓ Using existing demo Manager user: {DEMO_MANAGER_EMAIL} ({DEMO_MANAGER_USER_ID})")
    
    # Ensure SalesManager profile exists
    manager_profile = db.query(SalesManager).filter(SalesManager.user_id == DEMO_MANAGER_USER_ID).first()
    if not manager_profile:
        manager_profile = SalesManager(
            user_id=demo_manager_user.id,
            company_id=company.id,
        )
        db.add(manager_profile)
        db.commit()
        print(f"✓ Created SalesManager profile for {DEMO_MANAGER_EMAIL}")
    
    return demo_manager_user


def create_demo_rep_shifts(db: Session, company: Company, sales_rep_user: User) -> list[RepShift]:
    """Create demo rep shifts for the Sales Rep (past 2 weeks)."""
    # Check if rep_shifts table exists
    inspector = inspect(db.bind)
    if "rep_shifts" not in inspector.get_table_names():
        print("ℹ️ 'rep_shifts' table not found; skipping rep shift seeding.")
        return []
    
    # Delete existing shifts for this rep
    existing_shifts = db.query(RepShift).filter(
        RepShift.rep_id == sales_rep_user.id,
        RepShift.company_id == company.id
    ).all()
    for shift in existing_shifts:
        db.delete(shift)
    db.commit()
    
    shifts = []
    today = datetime.utcnow().date()
    
    # Create shifts for past 14 days (workdays only, Mon-Fri)
    for day_offset in range(14, 0, -1):
        shift_date = today - timedelta(days=day_offset)
        # Skip weekends (5 = Saturday, 6 = Sunday)
        if shift_date.weekday() >= 5:
            continue
        
        # Determine shift status based on day
        if day_offset <= 2:
            # Recent days: active or completed
            status = random.choice([ShiftStatus.ACTIVE, ShiftStatus.COMPLETED])
            clock_in_at = datetime.combine(shift_date, datetime.min.time().replace(hour=7, minute=random.randint(0, 30)))
            clock_out_at = None
            if status == ShiftStatus.COMPLETED:
                clock_out_at = clock_in_at + timedelta(hours=random.randint(8, 10))
        elif day_offset <= 7:
            # Past week: mostly completed, some skipped
            if random.random() < 0.15:  # 15% chance of skipped
                status = ShiftStatus.SKIPPED
                clock_in_at = None
                clock_out_at = None
            else:
                status = ShiftStatus.COMPLETED
                clock_in_at = datetime.combine(shift_date, datetime.min.time().replace(hour=7, minute=random.randint(0, 30)))
                clock_out_at = clock_in_at + timedelta(hours=random.randint(8, 10))
        else:
            # Older days: completed
            status = ShiftStatus.COMPLETED
            clock_in_at = datetime.combine(shift_date, datetime.min.time().replace(hour=7, minute=random.randint(0, 30)))
            clock_out_at = clock_in_at + timedelta(hours=random.randint(8, 10))
        
        shift = RepShift(
            id=str(uuid4()),
            rep_id=sales_rep_user.id,
            company_id=company.id,
            shift_date=shift_date,
            clock_in_at=clock_in_at,
            clock_out_at=clock_out_at,
            scheduled_start=time(7, 0),
            scheduled_end=time(17, 0),
            status=status,
            notes=None if status != ShiftStatus.SKIPPED else "Demo skipped shift",
            created_at=clock_in_at if clock_in_at else datetime.combine(shift_date, datetime.min.time()),
            updated_at=clock_out_at if clock_out_at else (clock_in_at if clock_in_at else datetime.combine(shift_date, datetime.min.time())),
        )
        db.add(shift)
        shifts.append(shift)
    
    db.commit()
    print(f"✓ Created {len(shifts)} demo rep shifts for Sales Rep")
    return shifts


def create_demo_sales_rep_appointments(db: Session, company: Company, sales_rep_user: User, contact_cards: list[ContactCard], leads: list[Lead]) -> list[Appointment]:
    """Create demo appointments assigned to the Sales Rep (high-performing scenario)."""
    # Delete existing appointments for this rep
    existing_appointments = db.query(Appointment).filter(
        Appointment.assigned_rep_id == sales_rep_user.id,
        Appointment.company_id == company.id
    ).all()
    for apt in existing_appointments:
        db.delete(apt)
    db.commit()
    
    appointments = []
    # Create 10 appointments for the Sales Rep (high-performing: more appointments, better outcomes)
    selected_contacts = random.sample(contact_cards, min(10, len(contact_cards)))
    
    for i, contact_card_obj in enumerate(selected_contacts):
        lead_obj = leads[contact_cards.index(contact_card_obj)] if contact_card_obj in contact_cards else None
        
        # High-performing rep: 70% completed with wins, 20% upcoming, 10% no-show/cancelled
        # IMPORTANT: Always use string values, never enum objects, to avoid AttributeError issues
        if i < 7:
            # Completed appointments (mostly won)
            scheduled_start = datetime.utcnow() - timedelta(days=random.randint(1, 20), hours=random.randint(9, 17))
            status = "completed"
            outcome = "won" if random.random() < 0.75 else "lost"  # 75% win rate (high-performing) - string value
        elif i < 9:
            # Upcoming appointments
            scheduled_start = datetime.utcnow() + timedelta(days=random.randint(1, 7), hours=random.randint(9, 17))
            status = "scheduled"
            outcome = "pending"  # String value, not enum
        else:
            # Past no-show or cancelled
            scheduled_start = datetime.utcnow() - timedelta(days=random.randint(1, 14), hours=random.randint(9, 17))
            status = random.choice(["no_show", "cancelled"])
            outcome = "lost" if status == "no_show" else "pending"  # String values, not enums
        
        scheduled_end = scheduled_start + timedelta(hours=1)
        
        apt = Appointment(
            id=str(uuid4()),
            company_id=company.id,
            lead_id=lead_obj.id if lead_obj else None,
            contact_card_id=contact_card_obj.id,
            assigned_rep_id=sales_rep_user.id,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            status=status,
            outcome=outcome,
            location=contact_card_obj.address,
            geo_lat=random.uniform(39.7, 39.9),
            geo_lng=random.uniform(-89.7, -89.5),
            service_type=random.choice(["Roofing", "HVAC", "Solar"]),
            notes=f"Demo appointment for {contact_card_obj.first_name} {contact_card_obj.last_name}",
            deal_size=random.uniform(12000, 45000) if outcome == "won" else None,
            material_type=random.choice(["Asphalt", "Metal", "Tile"]) if random.choice([True, False]) else None,
            financing_type=random.choice(["Cash", "Financing", "Lease"]) if random.choice([True, False]) else None,
            arrival_at=scheduled_start + timedelta(minutes=5) if status == "completed" else None,
            departure_at=scheduled_end if status == "completed" else None,
            on_site_duration=random.randint(60, 120) if status == "completed" else None,
            created_at=scheduled_start - timedelta(days=random.randint(1, 14)),
            updated_at=datetime.utcnow(),
        )
        db.add(apt)
        appointments.append(apt)
    
    db.commit()
    print(f"✓ Created {len(appointments)} demo appointments for Sales Rep (high-performing profile)")
    return appointments


def create_demo_recording_sessions(db: Session, company: Company, sales_rep_user: User, appointments: list[Appointment], shifts: list[RepShift]) -> list[RecordingSession]:
    """Create demo recording sessions for Sales Rep appointments."""
    # Check if recording_sessions table exists
    inspector = inspect(db.bind)
    if "recording_sessions" not in inspector.get_table_names():
        print("ℹ️ 'recording_sessions' table not found; skipping recording session seeding.")
        return []
    
    # Delete existing recording sessions for this rep
    existing_sessions = db.query(RecordingSession).filter(
        RecordingSession.rep_id == sales_rep_user.id,
        RecordingSession.company_id == company.id
    ).all()
    for session in existing_sessions:
        db.delete(session)
    db.commit()
    
    sessions = []
    # Create recording sessions for completed appointments
    completed_appointments = [apt for apt in appointments if apt.status == "completed"]
    sessions_to_create = random.sample(completed_appointments, min(5, len(completed_appointments)))
    
    for apt in sessions_to_create:
        # Find a shift that matches the appointment date
        apt_date = apt.scheduled_start.date()
        matching_shift = next((s for s in shifts if s.shift_date == apt_date and s.status == ShiftStatus.COMPLETED), None)
        
        started_at = apt.scheduled_start - timedelta(minutes=5)
        ended_at = apt.scheduled_end + timedelta(minutes=5)
        duration = (ended_at - started_at).total_seconds()
        
        session = RecordingSession(
            id=str(uuid4()),
            company_id=company.id,
            rep_id=sales_rep_user.id,
            appointment_id=apt.id,
            shift_id=matching_shift.id if matching_shift else None,
            mode=RecordingMode.NORMAL,
            audio_storage_mode=AudioStorageMode.PERSISTENT,
            started_at=started_at,
            ended_at=ended_at,
            start_lat=apt.geo_lat,
            start_lng=apt.geo_lng,
            end_lat=apt.geo_lat,
            end_lng=apt.geo_lng,
            geofence_radius_start=200.0,
            geofence_radius_stop=500.0,
            audio_url=f"https://demo-storage.s3.amazonaws.com/recordings/{apt.id}.mp3",
            audio_duration_seconds=duration,
            audio_size_bytes=random.randint(5000000, 15000000),  # 5-15 MB
            transcription_status=TranscriptionStatus.COMPLETED,
            analysis_status=AnalysisStatus.COMPLETED,
            shunya_asr_job_id=f"uwc-asr-{apt.id}",
            shunya_analysis_job_id=f"uwc-analysis-{apt.id}",
            created_at=started_at,
            updated_at=ended_at,
        )
        db.add(session)
        sessions.append(session)
    
    db.commit()
    print(f"✓ Created {len(sessions)} demo recording sessions for Sales Rep")
    return sessions


def create_demo_sales_rep_calls(db: Session, company: Company, sales_rep_user: User, contact_cards: list[ContactCard], leads: list[Lead], is_high_performing: bool = True) -> list[Call]:
    """Create demo calls assigned to the Sales Rep (high or low performing scenario)."""
    # Delete existing calls for this rep
    existing_calls = db.query(Call).filter(
        Call.assigned_rep_id == sales_rep_user.id,
        Call.company_id == company.id
    ).all()
    for call_obj in existing_calls:
        db.delete(call_obj)
    db.commit()
    
    calls = []
    # High-performing: 15 calls, low-performing: 8 calls
    num_calls = 15 if is_high_performing else 8
    selected_contacts = random.sample(contact_cards, min(num_calls, len(contact_cards)))
    
    for i, contact_card_obj in enumerate(selected_contacts):
        lead_obj = leads[contact_cards.index(contact_card_obj)] if contact_card_obj in contact_cards else None
        
        call_time = datetime.utcnow() - timedelta(days=random.randint(0, 30), hours=random.randint(9, 17))
        
        # High-performing: 80% booked, 60% bought; Low-performing: 40% booked, 20% bought
        booked_prob = 0.8 if is_high_performing else 0.4
        bought_prob = 0.6 if is_high_performing else 0.2
        
        direction = random.choice(["inbound", "outbound"])
        duration = random.randint(120, 600) if is_high_performing else random.randint(60, 300)  # Longer calls for high-performers
        missed = False
        
        booked = random.random() < booked_prob
        bought = booked and random.random() < bought_prob
        
        call_obj = Call(
            call_id=None,  # Auto-increment
            company_id=company.id,
            contact_card_id=contact_card_obj.id,
            lead_id=lead_obj.id if lead_obj else None,
            assigned_rep_id=sales_rep_user.id,
            phone_number=contact_card_obj.primary_phone,
            name=f"{contact_card_obj.first_name} {contact_card_obj.last_name}",
            missed_call=missed,
            transcript=f"Demo transcript for {'high-performing' if is_high_performing else 'low-performing'} rep call {i+1}. Customer: 'I'm interested in getting a quote.' Rep: 'Great! I'd be happy to help. When would be a good time for an estimate?'" if not missed else None,
            status="completed" if not missed else "missed",
            last_call_duration=duration,
            last_call_timestamp=call_time.isoformat(),
            booked=booked,
            bought=bought,
            price_if_bought=random.uniform(15000, 50000) if bought else None,
            created_at=call_time,
            updated_at=call_time,
        )
        db.add(call_obj)
        calls.append(call_obj)
    
    db.commit()
    db.flush()  # Get call_ids assigned
    print(f"✓ Created {len(calls)} demo calls for Sales Rep ({'high-performing' if is_high_performing else 'low-performing'} profile)")
    return calls


def create_demo_missed_call_queue_entries(db: Session, company: Company, calls: list[Call]) -> list[MissedCallQueue]:
    """
    Create demo missed call queue entries from existing calls.
    Creates entries with various statuses to populate metrics.
    """
    print("📞 Creating missed call queue entries...")
    
    # Filter for missed calls or create some from existing calls
    missed_calls = [c for c in calls if c.missed_call]
    
    # If we don't have enough missed calls, create some from regular calls
    if len(missed_calls) < 10:
        # Take some regular calls and mark them as missed for queue purposes
        regular_calls = [c for c in calls if not c.missed_call][:15]
        missed_calls.extend(regular_calls)
    
    # Ensure we have SLA settings
    sla_settings = db.query(MissedCallSLA).filter_by(company_id=company.id).first()
    if not sla_settings:
        sla_settings = MissedCallSLA(
            company_id=company.id,
            response_time_hours=2,
            escalation_time_hours=48,
            max_retries=3
        )
        db.add(sla_settings)
        db.commit()
    
    queue_entries = []
    now = datetime.utcnow()
    
    # Status distribution for realistic metrics
    status_distribution = [
        (MissedCallStatus.QUEUED, 5),
        (MissedCallStatus.PROCESSING, 3),
        (MissedCallStatus.AI_RESCUED_PENDING, 4),
        (MissedCallStatus.RECOVERED, 8),
        (MissedCallStatus.ESCALATED, 4),
        (MissedCallStatus.FAILED, 2),
        (MissedCallStatus.EXPIRED, 1),
    ]
    
    entry_index = 0
    for status, count in status_distribution:
        for i in range(count):
            if entry_index >= len(missed_calls):
                break
            
            call_obj = missed_calls[entry_index]
            entry_index += 1
            
            # Determine priority based on customer type
            if call_obj.lead_id:
                lead_obj = db.query(Lead).filter_by(id=call_obj.lead_id).first()
                if lead_obj and lead_obj.status == "new":
                    priority = MissedCallPriority.HIGH
                else:
                    priority = MissedCallPriority.MEDIUM
            else:
                priority = MissedCallPriority.MEDIUM
            
            # Calculate deadlines
            # Create entries with dates spread over the last 30 days to ensure they show up in date range queries
            # This ensures entries are visible when frontend queries with date ranges
            days_ago = random.randint(0, 30)
            created_time = call_obj.created_at if call_obj.created_at else now - timedelta(days=days_ago)
            sla_deadline = created_time + timedelta(hours=sla_settings.response_time_hours)
            escalation_deadline = created_time + timedelta(hours=sla_settings.escalation_time_hours)
            
            # Set processed_at for recovered entries (needed for metrics)
            processed_at = None
            if status == MissedCallStatus.RECOVERED:
                # Processed within 1-3 hours of creation
                processed_at = created_time + timedelta(hours=random.uniform(1, 3))
            
            # Set retry count based on status
            retry_count = 0
            if status in [MissedCallStatus.PROCESSING, MissedCallStatus.AI_RESCUED_PENDING]:
                retry_count = random.randint(1, 2)
            elif status == MissedCallStatus.RECOVERED:
                retry_count = random.randint(1, 3)
            elif status == MissedCallStatus.FAILED:
                retry_count = sla_settings.max_retries
            
            # Determine customer type
            customer_type = "new" if not call_obj.lead_id else "existing"
            
            queue_entry = MissedCallQueue(
                call_id=call_obj.call_id,
                customer_phone=call_obj.phone_number,
                company_id=company.id,
                status=status,
                priority=priority,
                sla_deadline=sla_deadline,
                escalation_deadline=escalation_deadline,
                retry_count=retry_count,
                max_retries=sla_settings.max_retries,
                customer_type=customer_type,
                lead_value=random.uniform(5000, 30000) if call_obj.lead_id else None,
                conversation_context=json.dumps({
                    "initial_missed_call": True,
                    "customer_type": customer_type,
                    "priority": priority.value,
                    "call_id": call_obj.call_id
                }),
                processed_at=processed_at,
                created_at=created_time,
                updated_at=created_time,
            )
            
            # Set additional fields based on status
            if status == MissedCallStatus.AI_RESCUED_PENDING:
                queue_entry.ai_rescue_attempted = True
                queue_entry.next_attempt_at = now + timedelta(hours=random.randint(2, 6))
            elif status == MissedCallStatus.RECOVERED:
                queue_entry.ai_rescue_attempted = True
                queue_entry.customer_responded = True
                queue_entry.recovery_method = random.choice(["sms", "call"])
            elif status == MissedCallStatus.ESCALATED:
                queue_entry.escalated_at = created_time + timedelta(hours=random.randint(24, 48))
            
            db.add(queue_entry)
            queue_entries.append(queue_entry)
    
    db.commit()
    print(f"✓ Created {len(queue_entries)} missed call queue entries")
    return queue_entries


def seed_demo_data(db: Session):
    """Main function to seed all demo data for CSR, Sales Rep, and Executive platforms."""
    print("🌱 Seeding demo data for all platforms (CSR, Sales Rep, Executive)...\n")
    
    # 1. Create or get demo company
    company = get_or_create_demo_company(db)
    
    # 2. Create or get demo CSR user
    csr_user = get_or_create_demo_user(db, company)
    
    # 3. Create contact cards
    contact_cards = create_demo_contact_cards(db, company)
    
    # 4. Create leads
    leads = create_demo_leads(db, company, contact_cards)
    
    # 5. Create generic sales reps (for CSR dashboard)
    generic_reps, rep_performance_map = create_demo_sales_reps(db, company)
    
    # 6. Create calls (CSR dashboard data)
    calls = create_demo_calls(db, company, contact_cards, leads)
    
    # 7. Create call transcripts
    transcripts = create_demo_call_transcripts(db, company, calls)
    
    # 8. Create call analyses
    analyses = create_demo_call_analyses(db, company, calls)
    
    # 9. Create appointments (CSR dashboard)
    appointments = create_demo_appointments(db, company, contact_cards, leads, generic_reps, rep_performance_map)
    
    # 10. Create tasks
    tasks = create_demo_tasks(db, company, contact_cards, leads, appointments, calls, csr_user)
    
    # 11. Create message threads
    message_threads = create_demo_message_threads(db, company, contact_cards, calls)
    
    # 12. Create or get demo Sales Rep user
    print("\n📱 Creating Sales Rep platform demo data...")
    sales_rep_user = get_or_create_demo_sales_rep_user(db, company)
    
    # 13. Create rep shifts for Sales Rep
    rep_shifts = create_demo_rep_shifts(db, company, sales_rep_user)
    
    # 14. Create appointments assigned to Sales Rep (high-performing)
    sales_rep_appointments = create_demo_sales_rep_appointments(db, company, sales_rep_user, contact_cards, leads)
    
    # 15. Create recording sessions for Sales Rep
    recording_sessions = create_demo_recording_sessions(db, company, sales_rep_user, sales_rep_appointments, rep_shifts)
    
    # 16. Create calls assigned to Sales Rep (high-performing)
    sales_rep_calls = create_demo_sales_rep_calls(db, company, sales_rep_user, contact_cards, leads, is_high_performing=True)
    
    # 16b. Create calls for generic reps (high and low performing)
    generic_rep_calls = []
    for rep in generic_reps:
        is_high_perf = rep_performance_map.get(rep.user_id, True)
        # Get the User object from the SalesRep
        rep_user = db.query(User).filter(User.id == rep.user_id).first()
        if rep_user:
            rep_calls = create_demo_sales_rep_calls(db, company, rep_user, contact_cards, leads, is_high_performing=is_high_perf)
            generic_rep_calls.extend(rep_calls)
    
    # 17. Create or get demo Manager/Executive user
    print("\n👔 Creating Executive/Manager platform demo data...")
    print(f"   Looking for manager user: {DEMO_MANAGER_EMAIL} ({DEMO_MANAGER_USER_ID})")
    manager_user = get_or_create_demo_manager_user(db, company)
    print(f"   ✓ Manager user ready: {manager_user.email} (role: {manager_user.role})")
    
    # Note: Manager sees all company data (calls, leads, appointments, etc.) - no additional seeding needed
    # The existing company-wide data is sufficient for executive dashboard
    
    # 18. Create missed call queue entries (for CSR and Manager dashboards)
    print("\n📞 Creating missed call queue entries...")
    all_calls = calls + sales_rep_calls + generic_rep_calls
    missed_call_queue_entries = create_demo_missed_call_queue_entries(db, company, all_calls)
    
    print("\n✅ Demo data seeded successfully!")
    print(f"\n📋 Demo Credentials:")
    print(f"   Company ID (Clerk Org): {DEMO_CLERK_ORG_ID}")
    print(f"   Company Name: {DEMO_COMPANY_NAME}")
    print(f"\n   👤 CSR User:")
    print(f"      User ID: {DEMO_CLERK_USER_ID}")
    print(f"      Email: {DEMO_USER_EMAIL}")
    print(f"      Role: CSR")
    print(f"\n   📱 Sales Rep User:")
    print(f"      User ID: {DEMO_SALES_REP_USER_ID}")
    print(f"      Email: {DEMO_SALES_REP_EMAIL}")
    print(f"      Role: Sales Rep (High-Performing)")
    print(f"\n   👔 Manager/Executive User:")
    print(f"      User ID: {DEMO_MANAGER_USER_ID}")
    print(f"      Email: {DEMO_MANAGER_EMAIL}")
    print(f"      Role: Manager")
    print(f"\n📊 Data Created:")
    print(f"   - {len(contact_cards)} contact cards")
    print(f"   - {len(leads)} leads")
    print(f"   - {len(calls)} calls (CSR dashboard)")
    print(f"   - {len(sales_rep_calls)} calls (Sales Rep demo user assigned)")
    print(f"   - {len(generic_rep_calls)} calls (Generic reps assigned)")
    print(f"   - {len(transcripts)} call transcripts")
    print(f"   - {len(analyses)} call analyses")
    print(f"   - {len(generic_reps)} generic sales reps")
    print(f"   - {len(appointments)} appointments (CSR dashboard)")
    print(f"   - {len(sales_rep_appointments)} appointments (Sales Rep assigned)")
    print(f"   - {len(rep_shifts)} rep shifts")
    print(f"   - {len(recording_sessions)} recording sessions")
    print(f"   - {len(tasks)} tasks")
    print(f"   - {len(message_threads)} SMS messages")
    print(f"\n💡 You can now log in as:")
    print(f"   - {DEMO_USER_EMAIL} for CSR dashboard")
    print(f"   - {DEMO_SALES_REP_EMAIL} for Sales Rep mobile app")
    print(f"   - {DEMO_MANAGER_EMAIL} for Executive/Manager dashboard")


if __name__ == "__main__":
    print("🌱 Starting demo data seed script...\n")
    
    # Create session and seed data
    db = SessionLocal()
    try:
        seed_demo_data(db)
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error seeding demo data: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

