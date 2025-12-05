"""
Contact Card Assembler Service (Section 7.2).

Assembles the complete Contact Card Detail with Top/Middle/Bottom sections
and Global blocks from all related entities.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, or_

from app.models.contact_card import ContactCard
from app.models.lead import Lead
from app.models.appointment import Appointment
from app.models.call import Call
from app.models.task import Task, TaskStatus
from app.models.key_signal import KeySignal
from app.models.event_log import EventLog, EventType
from app.models.call_transcript import CallTranscript
from app.models.call_analysis import CallAnalysis
from app.models.recording_session import RecordingSession
from app.models.recording_transcript import RecordingTranscript
from app.models.recording_analysis import RecordingAnalysis
from app.models.sop_compliance_result import SopComplianceResult
from app.models.sales_rep import SalesRep
from app.models.lead_status_history import LeadStatusHistory
from app.models.rep_assignment_history import RepAssignmentHistory
from app.models.message_thread import MessageThread
from app.schemas.domain import (
    ContactCardDetail,
    ContactCardTopSection,
    ContactCardMiddleSection,
    ContactCardBottomSection,
    ContactCardGlobalBlocks,
    PropertyIntelligence,
    TaskSummary,
    KeySignalSummary,
    EventLogSummary,
    CallSummary,
    CallTranscriptSummary,
    CallAnalysisSummary,
    MessageSummary,
    RecordingSessionSummary,
    SopComplianceItem,
    AppointmentDetailExtended,
    AppointmentSummary,
    LeadSummary,
    LeadStatusHistoryEntry,
    RepAssignmentHistoryEntry,
)
from app.core.pii_masking import PIISafeLogger
import json

logger = PIISafeLogger(__name__)


class ContactCardAssembler:
    """
    Assembles complete Contact Card Detail from all related entities.
    
    This service is responsible for:
    - Building Top Section (status, deal health, rep assignment, signals, tasks)
    - Building Middle Section (appointment details, property, recording, SOP, timeline)
    - Building Bottom Section (how booked, call/SMS history, timeline)
    - Including Global Blocks (all calls, messages, automation, insights)
    - Mapping Shunya/UWC outputs (transcripts, objections, SOP compliance)
    """
    
    def assemble_contact_card(
        self,
        db: Session,
        contact: ContactCard,
        company_id: str,
    ) -> ContactCardDetail:
        """
        Assemble complete Contact Card Detail from all related entities.
        
        Args:
            db: Database session
            contact: ContactCard instance
            company_id: Company/tenant ID
            
        Returns:
            Complete ContactCardDetail with all sections populated
        """
        # Get primary lead (most recent or active)
        primary_lead = self._get_primary_lead(db, contact.id, company_id)
        
        # Get active appointment
        active_appointment = self._get_active_appointment(db, contact.id, company_id)
        
        # Build Top Section
        top_section = self._build_top_section(db, contact, primary_lead, company_id)
        
        # Build Middle Section (only if appointment exists)
        middle_section = None
        if active_appointment:
            middle_section = self._build_middle_section(
                db, contact, primary_lead, active_appointment, company_id
            )
        
        # Build Bottom Section
        bottom_section = self._build_bottom_section(
            db, contact, primary_lead, company_id
        )
        
        # Build Global Blocks
        global_blocks = self._build_global_blocks(
            db, contact, primary_lead, company_id
        )
        
        # Build property intelligence
        property_intelligence = self._build_property_intelligence(contact)
        
        # Get all leads and appointments (backward compatibility)
        all_leads = [
            LeadSummary.model_validate(lead) for lead in contact.leads
        ]
        all_appointments = [
            AppointmentSummary.model_validate(apt) for apt in contact.appointments
        ]
        
        # Get recent call IDs
        recent_calls = (
            db.query(Call)
            .filter(Call.contact_card_id == contact.id)
            .order_by(Call.created_at.desc())
            .limit(10)
            .all()
        )
        recent_call_ids = [call.call_id for call in recent_calls]
        
        return ContactCardDetail(
            id=contact.id,
            company_id=contact.company_id,
            primary_phone=contact.primary_phone,
            secondary_phone=contact.secondary_phone,
            email=contact.email,
            first_name=contact.first_name,
            last_name=contact.last_name,
            address=contact.address,
            city=contact.city,
            state=contact.state,
            postal_code=contact.postal_code,
            metadata=contact.custom_metadata,
            property_snapshot=contact.property_snapshot,
            created_at=contact.created_at,
            updated_at=contact.updated_at,
            full_name=contact.full_name(),
            top_section=top_section,
            middle_section=middle_section,
            bottom_section=bottom_section,
            global_blocks=global_blocks,
            property_intelligence=property_intelligence,
            leads=all_leads,
            appointments=all_appointments,
            recent_call_ids=recent_call_ids,
        )
    
    def _get_primary_lead(
        self, db: Session, contact_card_id: str, company_id: str
    ) -> Optional[Lead]:
        """Get primary/active lead for this contact."""
        return (
            db.query(Lead)
            .filter(
                Lead.contact_card_id == contact_card_id,
                Lead.company_id == company_id,
            )
            .order_by(Lead.updated_at.desc())
            .first()
        )
    
    def _get_active_appointment(
        self, db: Session, contact_card_id: str, company_id: str
    ) -> Optional[Appointment]:
        """Get active/scheduled appointment for this contact."""
        return (
            db.query(Appointment)
            .filter(
                Appointment.contact_card_id == contact_card_id,
                Appointment.company_id == company_id,
                Appointment.status.in_(["scheduled", "confirmed", "completed"]),
            )
            .order_by(Appointment.scheduled_start.desc())
            .first()
        )
    
    def _build_top_section(
        self,
        db: Session,
        contact: ContactCard,
        primary_lead: Optional[Lead],
        company_id: str,
    ) -> ContactCardTopSection:
        """Build Top Section - Current Status & Priority."""
        # Customer Snapshot
        lead_source = primary_lead.source.value if primary_lead else None
        lead_age_days = None
        if primary_lead:
            age_delta = datetime.utcnow() - primary_lead.created_at
            lead_age_days = age_delta.days
        
        # Last activity (max of all activity timestamps)
        last_activity_at = self._compute_last_activity(db, contact.id, company_id)
        
        # Deal Status
        deal_status = None
        deal_size = None
        deal_summary = None
        closed_at = None
        if primary_lead:
            deal_status = primary_lead.deal_status
            deal_size = primary_lead.deal_size
            deal_summary = primary_lead.deal_summary
            closed_at = primary_lead.closed_at
        
        # Rep Assignment
        assigned_rep_id = None
        assigned_rep_name = None
        assigned_at = None
        rep_claimed = False
        route_position = None
        route_group = None
        distance_from_previous_stop = None
        
        if primary_lead:
            assigned_rep_id = primary_lead.assigned_rep_id
            assigned_at = primary_lead.assigned_at
            rep_claimed = primary_lead.rep_claimed or False
            
            if assigned_rep_id:
                rep = db.query(SalesRep).filter(
                    SalesRep.user_id == assigned_rep_id
                ).first()
                if rep:
                    # Get rep name from User or SalesRep
                    assigned_rep_name = getattr(rep, 'name', None) or assigned_rep_id
        
        # Get most recent appointment for routing info
        recent_apt = (
            db.query(Appointment)
            .filter(Appointment.contact_card_id == contact.id)
            .order_by(Appointment.scheduled_start.desc())
            .first()
        )
        if recent_apt:
            route_position = recent_apt.route_position
            route_group = recent_apt.route_group
            distance_from_previous_stop = recent_apt.distance_from_previous_stop
        
        # Lead Status History (Section 3.4)
        lead_status = None
        lead_status_history = []
        if primary_lead:
            lead_status = primary_lead.status.value if primary_lead.status else None
            status_history_entries = (
                db.query(LeadStatusHistory)
                .filter(LeadStatusHistory.lead_id == primary_lead.id)
                .order_by(LeadStatusHistory.created_at.desc())
                .limit(20)
                .all()
            )
            for entry in status_history_entries:
                context_dict = None
                if entry.context:
                    try:
                        context_dict = json.loads(entry.context) if isinstance(entry.context, str) else entry.context
                    except (json.JSONDecodeError, TypeError):
                        pass
                lead_status_history.append(LeadStatusHistoryEntry(
                    from_status=entry.from_status,
                    to_status=entry.to_status,
                    reason=entry.reason,
                    triggered_by=entry.triggered_by,
                    created_at=entry.created_at,
                    context=context_dict,
                ))
            lead_status_history.reverse()  # Show oldest first
        
        # Rep Assignment History (Section 3.3) + Lead Pool tracking
        rep_assignment_history = []
        requested_by_reps = []
        pool_status = None
        if primary_lead:
            # Get pool status
            from app.models.lead import PoolStatus
            pool_status = primary_lead.pool_status.value if primary_lead.pool_status else None
            
            # Get requested by rep IDs from denormalized field
            if primary_lead.requested_by_rep_ids:
                requested_by_reps = primary_lead.requested_by_rep_ids.copy()
            
            # Get assignment history
            assignment_history_entries = (
                db.query(RepAssignmentHistory)
                .filter(RepAssignmentHistory.lead_id == primary_lead.id)
                .order_by(RepAssignmentHistory.created_at.desc())
                .limit(20)
                .all()
            )
            for entry in assignment_history_entries:
                rep_name = None
                if entry.rep_id:
                    rep = db.query(SalesRep).filter(SalesRep.user_id == entry.rep_id).first()
                    if rep:
                        rep_name = getattr(rep, 'name', None) or entry.rep_id
                rep_assignment_history.append(RepAssignmentHistoryEntry(
                    rep_id=entry.rep_id,
                    rep_name=rep_name,
                    assigned_by=entry.assigned_by,
                    assignment_type=entry.assignment_type,
                    status=getattr(entry, 'status', None) or entry.assignment_type,
                    route_position=entry.route_position,
                    route_group=entry.route_group,
                    distance_from_previous_stop=entry.distance_from_previous_stop,
                    rep_claimed=entry.rep_claimed,
                    notes=entry.notes,
                    requested_at=getattr(entry, 'requested_at', None),
                    assigned_at=getattr(entry, 'assigned_at', None),
                    created_at=entry.created_at,
                ))
                # Track reps who requested (from history entries)
                if entry.assignment_type in ["requested", "claimed"] and entry.rep_id and entry.rep_id not in requested_by_reps:
                    requested_by_reps.append(entry.rep_id)
            rep_assignment_history.reverse()  # Show oldest first
            
            # Ensure requested_by_reps includes all from denormalized field
            if primary_lead.requested_by_rep_ids:
                for rep_id in primary_lead.requested_by_rep_ids:
                    if rep_id not in requested_by_reps:
                        requested_by_reps.append(rep_id)
        
        # Tasks
        tasks = (
            db.query(Task)
            .filter(
                Task.contact_card_id == contact.id,
                Task.company_id == company_id,
            )
            .order_by(Task.due_at.asc().nullslast(), Task.created_at.desc())
            .limit(20)
            .all()
        )
        task_summaries = [TaskSummary.model_validate(task) for task in tasks]
        overdue_count = sum(1 for task in tasks if task.due_at and task.due_at < datetime.utcnow() and task.status == TaskStatus.OPEN)
        
        # Key Signals
        signals = (
            db.query(KeySignal)
            .filter(
                KeySignal.contact_card_id == contact.id,
                KeySignal.company_id == company_id,
                KeySignal.acknowledged == False,
            )
            .order_by(KeySignal.created_at.desc())
            .limit(10)
            .all()
        )
        signal_summaries = [KeySignalSummary.model_validate(signal) for signal in signals]
        
        return ContactCardTopSection(
            lead_source=lead_source,
            lead_age_days=lead_age_days,
            last_activity_at=last_activity_at,
            lead_status=lead_status,
            lead_status_history=lead_status_history,
            deal_status=deal_status,
            deal_size=deal_size,
            deal_summary=deal_summary,
            closed_at=closed_at,
            assigned_rep_id=assigned_rep_id,
            assigned_rep_name=assigned_rep_name,
            assigned_at=assigned_at,
            rep_claimed=rep_claimed,
            route_position=route_position,
            route_group=route_group,
            distance_from_previous_stop=distance_from_previous_stop,
            rep_assignment_history=rep_assignment_history,
            requested_by_reps=requested_by_reps,
            pool_status=pool_status,
            tasks=task_summaries,
            overdue_count=overdue_count,
            key_signals=signal_summaries,
        )
    
    def _build_middle_section(
        self,
        db: Session,
        contact: ContactCard,
        primary_lead: Optional[Lead],
        active_appointment: Appointment,
        company_id: str,
    ) -> ContactCardMiddleSection:
        """Build Middle Section - Sales Appointment & Performance."""
        # Get rep name
        assigned_rep_name = None
        if active_appointment.assigned_rep_id:
            rep = db.query(SalesRep).filter(
                SalesRep.user_id == active_appointment.assigned_rep_id
            ).first()
            if rep:
                assigned_rep_name = getattr(rep, 'name', None) or active_appointment.assigned_rep_id
        
        # Build appointment detail
        appointment_detail = AppointmentDetailExtended(
            id=active_appointment.id,
            lead_id=active_appointment.lead_id,
            contact_card_id=active_appointment.contact_card_id,
            company_id=active_appointment.company_id,
            assigned_rep_id=active_appointment.assigned_rep_id,
            scheduled_start=active_appointment.scheduled_start,
            scheduled_end=active_appointment.scheduled_end,
            status=active_appointment.status,
            outcome=active_appointment.outcome,
            location=active_appointment.location,
            service_type=active_appointment.service_type,
            created_at=active_appointment.created_at,
            updated_at=active_appointment.updated_at,
            notes=active_appointment.notes,
            external_id=active_appointment.external_id,
            deal_size=active_appointment.deal_size,
            material_type=active_appointment.material_type,
            financing_type=active_appointment.financing_type,
            assigned_rep_name=assigned_rep_name,
            assigned_at=active_appointment.assigned_at,
            rep_claimed=active_appointment.rep_claimed or False,
            route_position=active_appointment.route_position,
            route_group=active_appointment.route_group,
            arrival_at=active_appointment.arrival_at,
            departure_at=active_appointment.departure_at,
            on_site_duration=active_appointment.on_site_duration,
            recording_sessions=[],
            sop_compliance=[],
        )
        
        # Recording Sessions
        recording_sessions = (
            db.query(RecordingSession)
            .filter(RecordingSession.appointment_id == active_appointment.id)
            .order_by(RecordingSession.started_at.desc())
            .all()
        )
        session_summaries = []
        for session in recording_sessions:
            # Get analysis for outcome/sentiment
            analysis = (
                db.query(RecordingAnalysis)
                .filter(RecordingAnalysis.recording_session_id == session.id)
                .first()
            )
            
            session_summary = RecordingSessionSummary(
                id=session.id,
                appointment_id=session.appointment_id,
                started_at=session.started_at,
                ended_at=session.ended_at,
                duration_seconds=session.audio_duration_seconds,
                mode=session.mode,
                audio_url=session.audio_url,  # Will be None in Ghost Mode
                transcription_status=session.transcription_status,
                analysis_status=session.analysis_status,
                outcome_classification=analysis.outcome if analysis else None,
                sentiment_score=analysis.sentiment_score if analysis else None,
            )
            session_summaries.append(session_summary)
        
        appointment_detail.recording_sessions = session_summaries
        
        # SOP Compliance
        sop_results = (
            db.query(SopComplianceResult)
            .filter(SopComplianceResult.appointment_id == active_appointment.id)
            .all()
        )
        sop_items = [
            SopComplianceItem.model_validate(result) for result in sop_results
        ]
        appointment_detail.sop_compliance = sop_items
        
        # Visit Activity Timeline (geofence/recording events)
        visit_timeline_events = (
            db.query(EventLog)
            .filter(
                EventLog.appointment_id == active_appointment.id,
                EventLog.event_type.in_([
                    EventType.REP_EN_ROUTE,
                    EventType.REP_ARRIVED,
                    EventType.RECORDING_STARTED,
                    EventType.INSPECTION_MILESTONE,
                    EventType.OBJECTION_MOMENT,
                    EventType.DECISION_MOMENT,
                    EventType.RECORDING_ENDED,
                    EventType.REP_DEPARTED,
                    EventType.APPOINTMENT_OUTCOME,
                ])
            )
            .order_by(EventLog.timestamp.asc())
            .all()
        )
        visit_timeline = [
            EventLogSummary.model_validate(event) for event in visit_timeline_events
        ]
        
        # Appointment-specific tasks
        appointment_tasks = (
            db.query(Task)
            .filter(
                Task.appointment_id == active_appointment.id,
                Task.company_id == company_id,
            )
            .all()
        )
        appointment_task_summaries = [
            TaskSummary.model_validate(task) for task in appointment_tasks
        ]
        
        # Escalation Warnings
        escalation_warnings = self._compute_escalation_warnings(
            db, active_appointment, appointment_tasks
        )
        
        # Transcript Intelligence (from recording analysis)
        transcript_intelligence = None
        if recording_sessions:
            # Get most recent analysis
            for session in recording_sessions:
                analysis = (
                    db.query(RecordingAnalysis)
                    .filter(RecordingAnalysis.recording_session_id == session.id)
                    .first()
                )
                if analysis:
                    transcript_intelligence = CallAnalysisSummary.model_validate(analysis)
                    break
        
        return ContactCardMiddleSection(
            active_appointment=appointment_detail,
            property_intelligence=self._build_property_intelligence(contact),
            sop_compliance=sop_items,
            visit_timeline=visit_timeline,
            recording_sessions=session_summaries,
            appointment_tasks=appointment_task_summaries,
            escalation_warnings=escalation_warnings,
            transcript_intelligence=transcript_intelligence,
        )
    
    def _build_bottom_section(
        self,
        db: Session,
        contact: ContactCard,
        primary_lead: Optional[Lead],
        company_id: str,
    ) -> ContactCardBottomSection:
        """Build Bottom Section - How Customer Was Booked."""
        # Narrative Summary (generated)
        narrative_summary = self._generate_narrative_summary(
            db, contact, primary_lead, company_id
        )
        
        # Booking Risk/Context Chips
        booking_chips = self._compute_booking_chips(
            db, contact, primary_lead, company_id
        )
        
        # Call Recordings (with transcripts/analysis)
        calls = (
            db.query(Call)
            .filter(Call.contact_card_id == contact.id)
            .order_by(Call.created_at.desc())
            .limit(20)
            .all()
        )
        call_summaries = []
        for call_obj in calls:
            # Get transcript
            transcript = (
                db.query(CallTranscript)
                .filter(CallTranscript.call_id == call_obj.call_id)
                .first()
            )
            transcript_summary = None
            if transcript:
                transcript_summary = CallTranscriptSummary(
                    id=transcript.id,
                    transcript_text=transcript.transcript_text,
                    confidence_score=transcript.confidence_score,
                    word_count=transcript.word_count,
                    created_at=transcript.created_at,
                )
            
            # Get analysis
            analysis = (
                db.query(CallAnalysis)
                .filter(CallAnalysis.call_id == call_obj.call_id)
                .first()
            )
            analysis_summary = None
            if analysis:
                analysis_summary = CallAnalysisSummary.model_validate(analysis)
            
            call_summary = CallSummary(
                call_id=call_obj.call_id,
                phone_number=call_obj.phone_number or contact.primary_phone,
                direction="inbound",  # Default, could be determined from metadata
                missed_call=call_obj.missed_call or False,
                booked=call_obj.booked or False,
                bought=call_obj.bought or False,
                created_at=call_obj.created_at,
                duration_seconds=call_obj.last_call_duration,
                transcript=transcript_summary,
                analysis=analysis_summary,
                recording_url=None,  # Could extract from call metadata
            )
            call_summaries.append(call_summary)
        
        # Text Messages (from MessageThread table and Call.text_messages fallback)
        all_messages = []
        
        # First, get messages from MessageThread table (primary source)
        message_threads = (
            db.query(MessageThread)
            .filter(MessageThread.contact_card_id == contact.id)
            .order_by(MessageThread.created_at.desc())
            .limit(100)
            .all()
        )
        for msg_thread in message_threads:
            message_summary = MessageSummary(
                timestamp=msg_thread.created_at,
                sender=msg_thread.sender,
                role=msg_thread.sender_role.value if msg_thread.sender_role else "customer",
                body=msg_thread.body,
                direction=msg_thread.direction.value if msg_thread.direction else "inbound",
                type=msg_thread.message_type.value if msg_thread.message_type else "manual",
                message_sid=msg_thread.message_sid,
            )
            all_messages.append(message_summary)
        
        # Fallback: Also check Call.text_messages for backward compatibility
        for call_obj in calls:
            if call_obj.text_messages:
                try:
                    messages = json.loads(call_obj.text_messages) if isinstance(call_obj.text_messages, str) else call_obj.text_messages
                    if isinstance(messages, list):
                        for msg in messages:
                            message_summary = MessageSummary(
                                timestamp=datetime.fromisoformat(msg.get("timestamp")) if msg.get("timestamp") else call_obj.created_at,
                                sender=msg.get("sender", call_obj.phone_number or contact.primary_phone),
                                role=msg.get("role", "customer"),
                                body=msg.get("message", ""),
                                direction=msg.get("direction", "inbound"),
                                type=msg.get("type", "automated"),
                                message_sid=msg.get("message_sid"),
                            )
                            all_messages.append(message_summary)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Failed to parse text_messages for call {call_obj.call_id}")
        
        # Sort messages by timestamp
        all_messages.sort(key=lambda m: m.timestamp, reverse=True)
        
        # Booking Timeline (all events)
        booking_events = (
            db.query(EventLog)
            .filter(
                EventLog.contact_card_id == contact.id,
                EventLog.company_id == company_id,
            )
            .order_by(EventLog.timestamp.asc())
            .limit(100)
            .all()
        )
        booking_timeline = [
            EventLogSummary.model_validate(event) for event in booking_events
        ]
        
        return ContactCardBottomSection(
            narrative_summary=narrative_summary,
            booking_chips=booking_chips,
            call_recordings=call_summaries,
            text_messages=all_messages,
            booking_timeline=booking_timeline,
        )
    
    def _build_global_blocks(
        self,
        db: Session,
        contact: ContactCard,
        primary_lead: Optional[Lead],
        company_id: str,
    ) -> ContactCardGlobalBlocks:
        """Build Global Data Blocks."""
        # All Calls
        all_calls_query = (
            db.query(Call)
            .filter(Call.contact_card_id == contact.id)
            .order_by(Call.created_at.desc())
        )
        # Build summaries (simplified for performance - could be optimized)
        all_calls = []
        for call_obj in all_calls_query.limit(50).all():
            all_calls.append(CallSummary(
                call_id=call_obj.call_id,
                phone_number=call_obj.phone_number or contact.primary_phone,
                direction="inbound",
                missed_call=call_obj.missed_call or False,
                booked=call_obj.booked or False,
                bought=call_obj.bought or False,
                created_at=call_obj.created_at,
                duration_seconds=call_obj.last_call_duration,
                transcript=None,  # Omitted for performance (already in bottom_section)
                analysis=None,
                recording_url=None,
            ))
        
        # All Messages (from MessageThread table and Call.text_messages fallback)
        all_messages = []
        
        # Primary source: MessageThread table
        message_threads = (
            db.query(MessageThread)
            .filter(MessageThread.contact_card_id == contact.id)
            .order_by(MessageThread.created_at.desc())
            .limit(200)
            .all()
        )
        for msg_thread in message_threads:
            all_messages.append(MessageSummary(
                timestamp=msg_thread.created_at,
                sender=msg_thread.sender,
                role=msg_thread.sender_role.value if msg_thread.sender_role else "customer",
                body=msg_thread.body,
                direction=msg_thread.direction.value if msg_thread.direction else "inbound",
                type=msg_thread.message_type.value if msg_thread.message_type else "manual",
                message_sid=msg_thread.message_sid,
            ))
        
        # Fallback: Call.text_messages for backward compatibility
        for call_obj in all_calls_query.all():
            if call_obj.text_messages:
                try:
                    messages = json.loads(call_obj.text_messages) if isinstance(call_obj.text_messages, str) else call_obj.text_messages
                    if isinstance(messages, list):
                        for msg in messages:
                            all_messages.append(MessageSummary(
                                timestamp=datetime.fromisoformat(msg.get("timestamp")) if msg.get("timestamp") else call_obj.created_at,
                                sender=msg.get("sender", call_obj.phone_number or contact.primary_phone),
                                role=msg.get("role", "customer"),
                                body=msg.get("message", ""),
                                direction=msg.get("direction", "inbound"),
                                type=msg.get("type", "automated"),
                                message_sid=msg.get("message_sid"),
                            ))
                except (json.JSONDecodeError, TypeError):
                    pass
        
        all_messages.sort(key=lambda m: m.timestamp, reverse=True)
        
        # Automation Events
        automation_events = (
            db.query(EventLog)
            .filter(
                EventLog.contact_card_id == contact.id,
                EventLog.company_id == company_id,
                EventLog.event_type.in_([
                    EventType.AUTOMATION_NURTURE,
                    EventType.AUTOMATION_FOLLOWUP,
                    EventType.AUTOMATION_SCHEDULED,
                    EventType.AUTOMATION_TASK_CREATED,
                    EventType.AUTOMATION_ESCALATED,
                ])
            )
            .order_by(EventLog.timestamp.desc())
            .limit(50)
            .all()
        )
        automation_event_summaries = [
            EventLogSummary.model_validate(event) for event in automation_events
        ]
        
        # Pending Action Items
        pending_tasks = (
            db.query(Task)
            .filter(
                Task.contact_card_id == contact.id,
                Task.company_id == company_id,
                Task.status == TaskStatus.OPEN,
            )
            .order_by(Task.due_at.asc().nullslast())
            .all()
        )
        pending_task_summaries = [
            TaskSummary.model_validate(task) for task in pending_tasks
        ]
        
        # AI Insights (aggregated)
        ai_insights = self._compute_ai_insights(db, contact, primary_lead, company_id)
        
        return ContactCardGlobalBlocks(
            all_calls=all_calls[:20],  # Limit for performance
            all_messages=all_messages[:50],  # Limit for performance
            automation_events=automation_event_summaries,
            pending_actions=pending_task_summaries,
            ai_insights=ai_insights,
        )
    
    def _build_property_intelligence(
        self, contact: ContactCard
    ) -> Optional[PropertyIntelligence]:
        """Build Property Intelligence from contact's property_snapshot."""
        if not contact.property_snapshot:
            return None
        
        snapshot = contact.property_snapshot.copy()
        sources = snapshot.pop("_sources", [])
        google_earth_url = snapshot.pop("_google_earth_url", None)
        
        return PropertyIntelligence(
            roof_type=snapshot.get("roof_type"),
            square_feet=snapshot.get("square_feet"),
            stories=snapshot.get("stories"),
            year_built=snapshot.get("year_built"),
            access_notes=snapshot.get("access_notes"),
            solar=snapshot.get("solar"),
            hoa=snapshot.get("hoa"),
            subdivision=snapshot.get("subdivision"),
            last_sale_date=snapshot.get("last_sale_date"),
            last_sale_price=snapshot.get("last_sale_price"),
            est_value_range=snapshot.get("est_value_range"),
            potential_equity=snapshot.get("potential_equity"),
            is_for_sale=snapshot.get("is_for_sale"),
            sources=sources if isinstance(sources, list) else [],
            google_earth_url=google_earth_url,
            updated_at=contact.property_snapshot_updated_at,
        )
    
    def _compute_last_activity(
        self, db: Session, contact_card_id: str, company_id: str
    ) -> Optional[datetime]:
        """Compute last activity timestamp across all entities."""
        # Get max from calls, appointments, tasks, event_logs
        last_call = (
            db.query(func.max(Call.updated_at))
            .filter(Call.contact_card_id == contact_card_id)
            .scalar()
        )
        last_appointment = (
            db.query(func.max(Appointment.updated_at))
            .filter(Appointment.contact_card_id == contact_card_id)
            .scalar()
        )
        last_task = (
            db.query(func.max(Task.updated_at))
            .filter(Task.contact_card_id == contact_card_id)
            .scalar()
        )
        last_event = (
            db.query(func.max(EventLog.timestamp))
            .filter(
                EventLog.contact_card_id == contact_card_id,
                EventLog.company_id == company_id,
            )
            .scalar()
        )
        
        timestamps = [t for t in [last_call, last_appointment, last_task, last_event] if t]
        return max(timestamps) if timestamps else None
    
    def _compute_escalation_warnings(
        self, db: Session, appointment: Appointment, tasks: List[Task]
    ) -> List[str]:
        """Compute escalation warnings for appointment."""
        warnings = []
        
        # Task overdue
        now = datetime.utcnow()
        overdue_tasks = [t for t in tasks if t.due_at and t.due_at < now and t.status == TaskStatus.OPEN]
        if overdue_tasks:
            warnings.append(f"{len(overdue_tasks)} task(s) overdue")
        
        # Rep late (if scheduled start has passed and no arrival)
        if appointment.scheduled_start < now and not appointment.arrival_at:
            warnings.append("Rep late to appointment")
        
        # No property intelligence
        contact = appointment.contact_card
        if contact and appointment.location and not contact.property_snapshot:
            warnings.append("Property intelligence not fetched")
        
        # Manual override needed (if recording not started but rep arrived)
        if appointment.arrival_at and not appointment.recording_sessions:
            # Check if there should be a recording
            warnings.append("Recording not started (manual override may be needed)")
        
        return warnings
    
    def _generate_narrative_summary(
        self,
        db: Session,
        contact: ContactCard,
        primary_lead: Optional[Lead],
        company_id: str,
    ) -> str:
        """Generate narrative summary of how customer was booked."""
        # TODO: Use AI to generate narrative summary
        # For now, generate basic summary
        
        parts = []
        
        if primary_lead:
            if primary_lead.source.value == "inbound_call":
                parts.append(f"Customer reached out via phone call.")
            elif primary_lead.source.value == "inbound_web":
                parts.append(f"Customer reached out via website.")
            elif primary_lead.source.value == "referral":
                parts.append(f"Customer referred to us.")
            else:
                parts.append(f"Lead created from {primary_lead.source.value}.")
        
        # Check for missed call
        missed_calls = (
            db.query(Call)
            .filter(
                Call.contact_card_id == contact.id,
                Call.missed_call == True,
            )
            .count()
        )
        if missed_calls > 0:
            parts.append(f"Initial call was missed. Otto automation initiated nurture sequence.")
        
        # Check for appointment
        appointments = contact.appointments
        if appointments:
            apt = appointments[0]
            parts.append(f"Appointment scheduled for {apt.scheduled_start.strftime('%B %d, %Y at %I:%M %p')}.")
            if apt.assigned_rep_id:
                parts.append(f"Assigned to sales rep.")
        
        return " ".join(parts) if parts else "No activity recorded yet."
    
    def _compute_booking_chips(
        self,
        db: Session,
        contact: ContactCard,
        primary_lead: Optional[Lead],
        company_id: str,
    ) -> List[dict]:
        """Compute booking risk/context chips."""
        chips = []
        
        # Check for missed initial call
        first_call = (
            db.query(Call)
            .filter(Call.contact_card_id == contact.id)
            .order_by(Call.created_at.asc())
            .first()
        )
        if first_call and first_call.missed_call:
            chips.append({
                "label": "Missed initial call",
                "severity": "medium",
                "metadata": {"call_id": first_call.call_id}
            })
        
        # Check for high responsiveness
        messages_count = sum(
            len(json.loads(c.text_messages)) if c.text_messages and isinstance(c.text_messages, str) else 0
            for c in contact.calls
            if c.text_messages
        )
        if messages_count > 5:
            chips.append({
                "label": "High responsiveness",
                "severity": "low",
                "metadata": {"message_count": messages_count}
            })
        
        # Check for automation involvement
        automation_count = (
            db.query(EventLog)
            .filter(
                EventLog.contact_card_id == contact.id,
                EventLog.company_id == company_id,
                EventLog.event_type.in_([
                    EventType.AUTOMATION_NURTURE,
                    EventType.AUTOMATION_FOLLOWUP,
                ])
            )
            .count()
        )
        if automation_count > 0:
            chips.append({
                "label": "Otto booked majority",
                "severity": "low",
                "metadata": {"automation_count": automation_count}
            })
        
        return chips
    
    def _compute_ai_insights(
        self,
        db: Session,
        contact: ContactCard,
        primary_lead: Optional[Lead],
        company_id: str,
    ) -> dict:
        """Compute aggregated AI insights."""
        # Aggregate objections across all calls/recordings
        all_objections = []
        all_sop_scores = []
        buying_signals = []
        
        # From call analyses
        call_analyses = (
            db.query(CallAnalysis)
            .join(Call, CallAnalysis.call_id == Call.call_id)
            .filter(Call.contact_card_id == contact.id)
            .all()
        )
        for analysis in call_analyses:
            if analysis.objections:
                all_objections.extend(analysis.objections if isinstance(analysis.objections, list) else [])
            if analysis.sop_compliance_score:
                all_sop_scores.append(analysis.sop_compliance_score)
            if analysis.conversion_probability and analysis.conversion_probability > 0.7:
                buying_signals.append("High conversion probability")
        
        # From recording analyses
        recording_analyses = (
            db.query(RecordingAnalysis)
            .join(RecordingSession, RecordingAnalysis.recording_session_id == RecordingSession.id)
            .join(Appointment, RecordingSession.appointment_id == Appointment.id)
            .filter(Appointment.contact_card_id == contact.id)
            .all()
        )
        for analysis in recording_analyses:
            if analysis.objections:
                all_objections.extend(analysis.objections if isinstance(analysis.objections, list) else [])
            if analysis.sop_compliance_score:
                all_sop_scores.append(analysis.sop_compliance_score)
            if analysis.conversion_probability and analysis.conversion_probability > 0.7:
                buying_signals.append("High conversion probability")
        
        # Count objection types
        objection_counts = {}
        for obj in all_objections:
            objection_counts[obj] = objection_counts.get(obj, 0) + 1
        
        # Average SOP score
        avg_sop_score = sum(all_sop_scores) / len(all_sop_scores) if all_sop_scores else None
        
        # Deal risk (computed from various factors)
        deal_risk = "low"
        if primary_lead:
            if primary_lead.status.value in ["dormant", "abandoned"]:
                deal_risk = "high"
            elif primary_lead.status.value in ["nurturing"]:
                deal_risk = "medium"
        
        return {
            "missed_opportunities": [],  # TODO: Extract from analyses
            "sop_compliance_score": avg_sop_score,
            "objection_clusters": objection_counts,
            "buying_signals": list(set(buying_signals)),
            "deal_risk_score": deal_risk,
            "suggested_next_actions": [],  # TODO: Generate from AI
        }


# Global assembler instance
contact_card_assembler = ContactCardAssembler()


