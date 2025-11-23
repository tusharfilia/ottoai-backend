"""
Test helpers for Contact Card scenario tests.

Provides factories and helpers for creating test data for Contact Card scenarios.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.contact_card import ContactCard
from app.models.lead import Lead, LeadStatus, PoolStatus, LeadSource
from app.models.call import Call
from app.models.appointment import Appointment, AppointmentStatus, AppointmentOutcome
from app.models.task import Task, TaskSource, TaskAssignee, TaskStatus
from app.models.key_signal import KeySignal, SignalType, SignalSeverity
from app.models.call_transcript import CallTranscript
from app.models.call_analysis import CallAnalysis
from app.models.recording_session import RecordingSession, RecordingMode, AudioStorageMode, TranscriptionStatus, AnalysisStatus
from app.models.recording_transcript import RecordingTranscript
from app.models.recording_analysis import RecordingAnalysis
from app.models.rep_assignment_history import RepAssignmentHistory
from app.models.lead_status_history import LeadStatusHistory
from app.models.message_thread import MessageThread, MessageRole
from app.models.sales_rep import SalesRep


def create_company(db: Session, company_id: Optional[str] = None) -> Company:
    """Create a test company."""
    company = Company(
        id=company_id or f"company_{uuid4().hex[:8]}",
        name="Test Company",
        address="123 Test St",
        phone_number="+15551234567",
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def create_contact_card_with_lead(
    db: Session,
    company_id: str,
    lead_status: LeadStatus = LeadStatus.NEW,
    pool_status: PoolStatus = PoolStatus.IN_POOL,
    first_name: Optional[str] = None,
    phone: Optional[str] = None,
) -> tuple[ContactCard, Lead]:
    """Create a ContactCard with a linked Lead."""
    contact_card = ContactCard(
        id=str(uuid4()),
        company_id=company_id,
        primary_phone=phone or "+15551234567",
        first_name=first_name or "John",
        last_name="Doe",
    )
    db.add(contact_card)
    db.flush()
    
    lead = Lead(
        id=str(uuid4()),
        company_id=company_id,
        contact_card_id=contact_card.id,
        status=lead_status,
        pool_status=pool_status,
        source=LeadSource.INBOUND_CALL,
    )
    db.add(lead)
    db.flush()
    
    # Link them
    contact_card.leads.append(lead)
    db.commit()
    db.refresh(contact_card)
    db.refresh(lead)
    
    return contact_card, lead


def seed_csr_call_with_shunya_output(
    db: Session,
    call: Call,
    company_id: str,
    qualification_status: str = "qualified_booked",
    transcript_text: str = "Hello, I need a roof quote",
    objections: List[str] = None,
    pending_actions: List[Dict[str, Any]] = None,
) -> tuple[CallTranscript, CallAnalysis]:
    """
    Seed a CSR call with Shunya analysis results.
    
    This simulates the output from Shunya integration service without actually calling Shunya.
    """
    from datetime import datetime
    
    # Create transcript
    transcript = CallTranscript(
        id=str(uuid4()),
        call_id=call.call_id,
        tenant_id=company_id,
        uwc_job_id=f"uwc_job_{uuid4().hex[:8]}",
        transcript_text=transcript_text,
        confidence_score=0.95,
        language="en-US",
        word_count=len(transcript_text.split()),
    )
    db.add(transcript)
    db.flush()
    
    # Create analysis
    analysis = CallAnalysis(
        id=str(uuid4()),
        call_id=call.call_id,
        tenant_id=company_id,
        uwc_job_id=f"uwc_analysis_{uuid4().hex[:8]}",
        objections=objections or [],
        sentiment_score=0.75,
        sop_stages_completed=["connect", "agenda", "assess"],
        sop_stages_missed=[],
        sop_compliance_score=8.5,
        lead_quality=qualification_status,
        analyzed_at=datetime.utcnow(),
    )
    db.add(analysis)
    db.flush()
    
    # Update call with transcript
    call.transcript = transcript_text
    db.commit()
    db.refresh(transcript)
    db.refresh(analysis)
    
    return transcript, analysis


def seed_appointment_with_visit_analysis(
    db: Session,
    appointment: Appointment,
    company_id: str,
    recording_session_id: Optional[str] = None,
    outcome: AppointmentOutcome = AppointmentOutcome.PENDING,
    transcript_text: Optional[str] = None,
    is_ghost_mode: bool = False,
    visit_actions: List[Dict[str, Any]] = None,
) -> tuple[Optional[RecordingTranscript], RecordingAnalysis]:
    """
    Seed an appointment with visit analysis (simulates Shunya visit processing).
    
    Returns transcript (None if ghost mode) and analysis.
    """
    from datetime import datetime
    
    recording_session_id = recording_session_id or str(uuid4())
    
    # Create recording session if it doesn't exist
    recording_session = db.query(RecordingSession).filter(
        RecordingSession.id == recording_session_id
    ).first()
    
    if not recording_session:
        recording_session = RecordingSession(
            id=recording_session_id,
            company_id=company_id,
            appointment_id=appointment.id,
            rep_id=appointment.assigned_rep_id,
            mode=RecordingMode.GHOST if is_ghost_mode else RecordingMode.NORMAL,
            audio_storage_mode=AudioStorageMode.NOT_STORED if is_ghost_mode else AudioStorageMode.PERSISTENT,
            started_at=datetime.utcnow() - timedelta(hours=1),
            ended_at=datetime.utcnow(),
            transcription_status=TranscriptionStatus.COMPLETED,
            analysis_status=AnalysisStatus.COMPLETED,
        )
        if not is_ghost_mode:
            recording_session.audio_url = f"https://s3.example.com/audio/{recording_session_id}.wav"
        db.add(recording_session)
        db.flush()
    
    # Create transcript (only if not ghost mode)
    transcript = None
    if not is_ghost_mode and transcript_text:
        transcript = RecordingTranscript(
            id=str(uuid4()),
            recording_session_id=recording_session_id,
            company_id=company_id,
            appointment_id=appointment.id,
            uwc_job_id=f"uwc_visit_{uuid4().hex[:8]}",
            transcript_text=transcript_text,
            is_ghost_mode=False,
            transcript_restricted=False,
            word_count=len(transcript_text.split()) if transcript_text else 0,
            language="en-US",
        )
        db.add(transcript)
        db.flush()
    
    # Create analysis (always, even in ghost mode)
    analysis = RecordingAnalysis(
        id=str(uuid4()),
        recording_session_id=recording_session_id,
        company_id=company_id,
        appointment_id=appointment.id,
        lead_id=appointment.lead_id,
        outcome=outcome.value,
        sentiment_score=0.7,
        sop_compliance_score=7.5,
        is_ghost_mode=is_ghost_mode,
        analyzed_at=datetime.utcnow(),
    )
    db.add(analysis)
    db.flush()
    
    # Update appointment outcome
    appointment.outcome = outcome
    if outcome in [AppointmentOutcome.WON, AppointmentOutcome.LOST]:
        appointment.status = AppointmentStatus.COMPLETED
        appointment.closed_at = datetime.utcnow()
    
    db.commit()
    if transcript:
        db.refresh(transcript)
    db.refresh(analysis)
    
    return transcript, analysis


def create_tasks_from_pending_actions(
    db: Session,
    contact_card_id: str,
    company_id: str,
    pending_actions: List[Dict[str, Any]],
) -> List[Task]:
    """Create Task records from Shunya pending actions."""
    tasks = []
    for action in pending_actions:
        action_text = action.get("action") or action.get("text") or str(action)
        due_at = action.get("due_at")
        
        task = Task(
            id=str(uuid4()),
            company_id=company_id,
            contact_card_id=contact_card_id,
            description=action_text,
            source=TaskSource.SHUNYA,
            assigned_to=TaskAssignee.REP,  # Default to rep
            status=TaskStatus.OPEN,
            due_at=due_at,
        )
        db.add(task)
        tasks.append(task)
    
    db.commit()
    for task in tasks:
        db.refresh(task)
    
    return tasks


def create_key_signals_from_missed_opportunities(
    db: Session,
    contact_card_id: str,
    company_id: str,
    lead_id: str,
    missed_opportunities: List[str],
) -> List[KeySignal]:
    """Create KeySignal records from missed opportunities."""
    signals = []
    for opp_text in missed_opportunities:
        signal = KeySignal(
            id=str(uuid4()),
            company_id=company_id,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            signal_type=SignalType.OPPORTUNITY,
            severity=SignalSeverity.MEDIUM,
            title=f"Missed Opportunity: {opp_text[:50]}",
            description=opp_text,
        )
        db.add(signal)
        signals.append(signal)
    
    db.commit()
    for signal in signals:
        db.refresh(signal)
    
    return signals


def update_property_intelligence(
    db: Session,
    contact_card: ContactCard,
    property_data: Dict[str, Any],
) -> ContactCard:
    """Update contact card with property intelligence data."""
    contact_card.property_snapshot = property_data
    db.commit()
    db.refresh(contact_card)
    return contact_card


def create_sales_rep(db: Session, company_id: str, user_id: Optional[str] = None) -> SalesRep:
    """Create a test sales rep."""
    rep = SalesRep(
        user_id=user_id or f"rep_{uuid4().hex[:8]}",
        company_id=company_id,
        name="Test Rep",
        email="rep@test.com",
        phone_number="+15559876543",
    )
    db.add(rep)
    db.commit()
    db.refresh(rep)
    return rep


def create_message_thread(
    db: Session,
    contact_card_id: str,
    company_id: str,
    messages: List[Dict[str, Any]],
) -> MessageThread:
    """Create a message thread with messages."""
    thread = MessageThread(
        id=str(uuid4()),
        company_id=company_id,
        contact_card_id=contact_card_id,
        phone_number="+15551234567",
    )
    db.add(thread)
    db.flush()
    
    # Add messages to thread (would normally be done via Message model)
    # For now, we'll just create the thread
    
    db.commit()
    db.refresh(thread)
    return thread


def record_lead_status_change(
    db: Session,
    lead_id: str,
    company_id: str,
    from_status: Optional[str],
    to_status: str,
    reason: str,
    triggered_by: str = "test",
) -> LeadStatusHistory:
    """Record a lead status change."""
    history = LeadStatusHistory(
        id=str(uuid4()),
        lead_id=lead_id,
        company_id=company_id,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        triggered_by=triggered_by,
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


def record_rep_assignment(
    db: Session,
    lead_id: str,
    contact_card_id: str,
    company_id: str,
    rep_id: str,
    assigned_by: str,
    status: str = "assigned",
) -> RepAssignmentHistory:
    """Record a rep assignment."""
    history = RepAssignmentHistory(
        id=str(uuid4()),
        lead_id=lead_id,
        contact_card_id=contact_card_id,
        company_id=company_id,
        rep_id=rep_id,
        assigned_by=assigned_by,
        status=status,
        assigned_at=datetime.utcnow() if status == "assigned" else None,
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


