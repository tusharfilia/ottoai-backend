"""
Metrics service for computing role-scoped KPIs.

Supports:
- CSR overview metrics
- Sales Rep metrics (per-rep + team)
- Executive metrics (CSR tab + Sales tab)
"""
from datetime import datetime, timedelta
from typing import Optional, List, Literal
from sqlalchemy import func, and_, or_, distinct
from sqlalchemy.orm import Session

from app.models.call import Call
from app.models.call_analysis import CallAnalysis
from app.models.appointment import Appointment, AppointmentStatus, AppointmentOutcome
from app.models.recording_analysis import RecordingAnalysis
from app.models.recording_session import RecordingSession
from app.models.recording_transcript import RecordingTranscript
from app.models.task import Task, TaskStatus, TaskAssignee
from app.models.sales_rep import SalesRep
from app.models.user import User
from app.models.lead import Lead, LeadStatus, LeadSource
from app.models.contact_card import ContactCard
from app.models.enums import CallType, BookingStatus, CallOutcomeCategory
from app.obs.logging import get_logger
from app.schemas.metrics import (
    CSRMetrics,
    SalesRepMetrics,
    SalesTeamMetrics,
    SalesRepSummary,
    ExecCSRMetrics,
    ExecSalesMetrics,
    CSRBookingTrend,
    CSRBookingTrendPoint,
    CSRBookingTrendPointTimestamp,
    CSRUnbookedAppointmentsResponse,
    CSRUnbookedAppointmentItem,
    CSRTopObjectionsResponse,
    CSRObjectionMetric,
    CSRObjectionCallsResponse,
    CSRObjectionCallItem,
    AutoQueuedLeadsResponse,
    AutoQueuedLeadItem,
    CSRMissedCallRecoveryResponse,
    CSRMissedCallMetrics,
    CSRLeadStatusItem,
    ExecCompanyOverviewMetrics,
    ExecCompanyWinLossAttribution,
    ExecWhoDroppingBall,
    ExecCSRDashboardMetrics,
    TimeSeriesPoint,
    ObjectionSummary,
    CSRAgentCoachingSummary,
    ExecMissedCallRecoveryMetrics,
    ExecSalesTeamDashboardMetrics,
    SalesTeamStatsMetrics,
    SalesRepRecordingSummary,
    CSROverviewSelfResponse,
    CSRBookingTrendSelfResponse,
    CSRBookingTrendSummary,
    UnbookedCallsSelfResponse,
    UnbookedCallItem,
    CSRObjectionsSelfResponse,
    CSRObjectionSelfItem,
    CallsByObjectionSelfResponse,
    CallByObjectionItem,
    CSRMissedCallsSelfResponse,
    MissedLeadsSelfResponse,
    MissedLeadItem,
    RideAlongAppointmentsResponse,
    RideAlongAppointmentItem,
    SalesOpportunitiesResponse,
    SalesOpportunityItem
)

logger = get_logger(__name__)


class MetricsService:
    """
    Service for computing role-scoped metrics and KPIs.
    
    Supports:
    - CSR overview metrics (calls, qualification, booking, compliance, followups)
    - Sales Rep metrics (appointments, outcomes, compliance, sentiment)
    - Sales Team metrics (aggregate + per-rep summaries)
    - Executive metrics (CSR tab + Sales tab, company-wide)
    """
    
    def __init__(self, db: Session):
        """
        Initialize metrics service with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    @staticmethod
    def _compute_meeting_structure_score(meeting_segments: Optional[dict]) -> Optional[float]:
        """
        Compute meeting structure score from meeting_segments.
        
        Score is based on presence of expected phases (rapport_agenda, proposal_close).
        Returns a score between 0.0 and 1.0, or None if no segments.
        
        Args:
            meeting_segments: JSON dict with meeting segments
        
        Returns:
            Score between 0.0-1.0, or None
        """
        if not meeting_segments:
            return None
        
        # If it's a list, check for expected phases
        if isinstance(meeting_segments, list):
            phases = [seg.get("phase", "").lower() if isinstance(seg, dict) else str(seg).lower() 
                     for seg in meeting_segments]
            has_rapport = any("rapport" in phase or "agenda" in phase for phase in phases)
            has_proposal = any("proposal" in phase or "close" in phase for phase in phases)
            
            # Simple scoring: 0.5 for each phase present
            score = 0.0
            if has_rapport:
                score += 0.5
            if has_proposal:
                score += 0.5
            return score if score > 0 else None
        
        # If it's a dict, check for part1/part2 structure
        if isinstance(meeting_segments, dict):
            has_part1 = "part1" in meeting_segments or "rapport" in str(meeting_segments).lower()
            has_part2 = "part2" in meeting_segments or "proposal" in str(meeting_segments).lower()
            
            score = 0.0
            if has_part1:
                score += 0.5
            if has_part2:
                score += 0.5
            return score if score > 0 else None
        
        return None
    
    async def get_csr_overview_metrics(
        self,
        *,
        csr_user_id: Optional[str] = None,
        tenant_id: str,
        start: datetime,
        end: datetime,
    ) -> CSRMetrics:
        """
        Compute CSR overview metrics for a specific CSR within a date range.
        
        Query rules:
        - Only considers calls where:
          * Call.company_id == tenant_id
          * Call.call_type == CallType.CSR_CALL
          * Call.created_at between start and end
          * Call.owner_id == csr_user_id (if csr_user_id provided, for per-CSR scoping)
        - Joins to CallAnalysis for Shunya-derived fields
        - Joins to Task for followup tracking
        - Joins to Lead for pending leads count
        
        Args:
            csr_user_id: CSR user ID (optional, if None returns tenant-wide metrics)
            tenant_id: Company/tenant ID
            start: Start datetime (inclusive)
            end: End datetime (inclusive)
        
        Returns:
            CSRMetrics with all computed metrics
        """
        # Base query: CSR calls in date range
        base_query = self.db.query(Call).join(
            CallAnalysis,
            Call.call_id == CallAnalysis.call_id,
            isouter=True  # LEFT JOIN to include calls without analysis
        ).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.created_at >= start,
            Call.created_at <= end
        )
        
        # Filter by CSR owner if provided (per-CSR scoping)
        if csr_user_id:
            base_query = base_query.filter(Call.owner_id == csr_user_id)
        
        # Get all calls (with or without analysis)
        all_calls = base_query.all()
        total_calls = len(all_calls)
        
        # Get analysis records for these calls
        call_ids = [call.call_id for call in all_calls]
        analyses = self.db.query(CallAnalysis).filter(
            CallAnalysis.call_id.in_(call_ids),
            CallAnalysis.tenant_id == tenant_id
        ).all()
        
        # Create lookup dict: call_id -> analysis
        analysis_by_call_id = {analysis.call_id: analysis for analysis in analyses}
        
        # Qualification metrics
        qualified_calls = 0
        booked_calls = 0
        service_not_offered_calls = 0
        qualified_but_unbooked_calls = 0
        total_objections = 0
        compliance_scores = []
        
        # Track reasons for missed bookings (only from Shunya fields)
        missed_booking_reasons: dict[str, int] = {}
        
        # Get lead IDs for this CSR's calls (for pending leads count only - not for booking semantics)
        call_lead_ids = [call.lead_id for call in all_calls if call.lead_id]
        
        # Get pending leads count (this is metadata, not booking semantics)
        pending_leads_count = 0
        if call_lead_ids:
            pending_leads_count = self.db.query(Lead).filter(
                Lead.id.in_(call_lead_ids),
                Lead.company_id == tenant_id,
                Lead.status.in_([LeadStatus.NEW.value, LeadStatus.WARM.value, LeadStatus.NURTURING.value])
            ).count()
        
        for call in all_calls:
            analysis = analysis_by_call_id.get(call.call_id)
            if not analysis:
                continue
            
            # QUALIFICATION: Only use Shunya's lead_quality (which stores qualification_status)
            # Count as qualified only if Shunya says so (hot, warm, cold, qualified)
            lead_quality = analysis.lead_quality
            if lead_quality and lead_quality.lower() in ("hot", "warm", "cold", "qualified"):
                qualified_calls += 1
                
                # Count objections for qualified calls (from Shunya)
                if analysis.objections and isinstance(analysis.objections, list):
                    total_objections += len(analysis.objections)
            
            # BOOKING: Only use Shunya's booking_status enum - never infer from appointments
            if analysis.booking_status:
                if analysis.booking_status == BookingStatus.BOOKED.value:
                    booked_calls += 1
                elif analysis.booking_status == BookingStatus.SERVICE_NOT_OFFERED.value:
                    service_not_offered_calls += 1
                    missed_booking_reasons["service_not_offered"] = missed_booking_reasons.get("service_not_offered", 0) + 1
                elif analysis.booking_status == BookingStatus.NOT_BOOKED.value:
                    # Track reason for not booking (from Shunya objections)
                    if analysis.objections and isinstance(analysis.objections, list) and len(analysis.objections) > 0:
                        # Use first objection as reason (from Shunya)
                        first_obj = analysis.objections[0]
                        if isinstance(first_obj, str):
                            missed_booking_reasons[first_obj] = missed_booking_reasons.get(first_obj, 0) + 1
                        elif isinstance(first_obj, dict) and "type" in first_obj:
                            missed_booking_reasons[first_obj["type"]] = missed_booking_reasons.get(first_obj["type"], 0) + 1
                    else:
                        missed_booking_reasons["no_objection_recorded"] = missed_booking_reasons.get("no_objection_recorded", 0) + 1
            
            # OUTCOME CATEGORY: Only use Shunya's call_outcome_category - never compute ourselves
            if analysis.call_outcome_category == CallOutcomeCategory.QUALIFIED_BUT_UNBOOKED.value:
                qualified_but_unbooked_calls += 1
            
            # COMPLIANCE: Only use Shunya's sop_compliance_score
            if analysis.sop_compliance_score is not None:
                compliance_scores.append(analysis.sop_compliance_score)
        
        # Compute top reason for missed bookings
        top_reason_for_missed_bookings: Optional[str] = None
        if missed_booking_reasons:
            top_reason_for_missed_bookings = max(missed_booking_reasons.items(), key=lambda x: x[1])[0]
        
        # Compute rates (null-safe)
        qualified_rate = qualified_calls / total_calls if total_calls > 0 else None
        booking_rate = booked_calls / qualified_calls if qualified_calls > 0 else None
        service_not_offered_rate = service_not_offered_calls / qualified_calls if qualified_calls > 0 else None
        avg_objections_per_qualified_call = total_objections / qualified_calls if qualified_calls > 0 else None
        avg_compliance_score = sum(compliance_scores) / len(compliance_scores) if compliance_scores else None
        
        # Task metrics (followups)
        now = datetime.utcnow()
        
        # Query tasks assigned to CSR (use assignee_id if csr_user_id provided, else use role)
        open_tasks_query = self.db.query(Task).filter(
            Task.company_id == tenant_id,
            Task.status.in_([TaskStatus.OPEN.value, TaskStatus.PENDING.value])
        )
        
        if csr_user_id:
            # Filter by specific CSR user ID
            open_tasks_query = open_tasks_query.filter(
                (Task.assignee_id == csr_user_id) | 
                (Task.assigned_to == TaskAssignee.CSR.value)  # Fallback to role if assignee_id not set
            )
        else:
            # Tenant-wide: filter by CSR role
            open_tasks_query = open_tasks_query.filter(Task.assigned_to == TaskAssignee.CSR.value)
        
        all_open_tasks = open_tasks_query.all()
        
        # Filter by due date
        open_followups = sum(
            1 for task in all_open_tasks
            if task.due_at is None or task.due_at >= now
        )
        
        overdue_followups = sum(
            1 for task in all_open_tasks
            if task.due_at is not None and task.due_at < now
        )
        
        return CSRMetrics(
            total_calls=total_calls,
            qualified_calls=qualified_calls,
            qualified_rate=qualified_rate,
            booked_calls=booked_calls,
            booking_rate=booking_rate,
            service_not_offered_calls=service_not_offered_calls,
            service_not_offered_rate=service_not_offered_rate,
            avg_objections_per_qualified_call=avg_objections_per_qualified_call,
            qualified_but_unbooked_calls=qualified_but_unbooked_calls,
            avg_compliance_score=avg_compliance_score,
            open_followups=open_followups,
            overdue_followups=overdue_followups,
            top_reason_for_missed_bookings=top_reason_for_missed_bookings,
            pending_leads_count=pending_leads_count if pending_leads_count > 0 else None
        )
    
    async def get_sales_rep_overview_metrics(
        self,
        *,
        tenant_id: str,
        rep_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> SalesRepMetrics:
        """
        Compute sales rep overview metrics for a specific rep within a date range.
        
        Uses Appointment + RecordingAnalysis for outcomes and meeting scores.
        Relies on Shunya-derived fields from RecordingAnalysis.
        
        Args:
            tenant_id: Company/tenant ID
            rep_id: Sales rep user ID
            date_from: Start datetime (optional, defaults to 30 days ago)
            date_to: End datetime (optional, defaults to now)
        
        Returns:
            SalesRepMetrics with all computed metrics
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Query appointments for this rep
        appointments_query = self.db.query(Appointment).filter(
            Appointment.company_id == tenant_id,
            Appointment.assigned_rep_id == rep_id,
            Appointment.scheduled_start >= date_from,
            Appointment.scheduled_start <= date_to
        )
        
        all_appointments = appointments_query.all()
        total_appointments = len(all_appointments)
        
        # Get appointment IDs for analysis lookup
        appointment_ids = [apt.id for apt in all_appointments]
        
        # Get RecordingAnalysis records for these appointments
        analyses = self.db.query(RecordingAnalysis).filter(
            RecordingAnalysis.appointment_id.in_(appointment_ids),
            RecordingAnalysis.company_id == tenant_id
        ).all()
        
        # Create lookup: appointment_id -> analysis
        analysis_by_appointment_id = {analysis.appointment_id: analysis for analysis in analyses}
        
        # Count appointments by status and outcome
        # IMPORTANT: Use Shunya's RecordingAnalysis.outcome for won/lost, not Appointment.outcome
        completed_appointments = 0
        won_appointments = 0
        lost_appointments = 0
        pending_appointments = 0
        
        # Track first-touch vs follow-up wins
        first_touch_wins = 0
        first_touch_completed = 0
        followup_wins = 0
        followup_completed = 0
        
        # Aggregate metrics
        total_objections = 0
        compliance_scores = []
        meeting_structure_scores = []
        sentiment_scores = []
        
        # Track scheduled vs attended for attendance_rate
        scheduled_appointments = len(all_appointments)
        attended_appointments = 0
        
        # Track auto usage hours
        total_audio_duration_seconds = 0.0
        
        # Get RecordingSession records for these appointments to compute auto_usage_hours
        recording_sessions = self.db.query(RecordingSession).filter(
            RecordingSession.appointment_id.in_(appointment_ids),
            RecordingSession.company_id == tenant_id
        ).all()
        
        session_by_appointment_id = {session.appointment_id: session for session in recording_sessions if session.appointment_id}
        
        # Get lead IDs to track first-touch vs follow-up
        lead_ids = [apt.lead_id for apt in all_appointments if apt.lead_id]
        
        # For first-touch detection: get earliest appointment per lead for this rep
        # TODO: This is a simplified heuristic - we need full appointment history per lead to be accurate
        first_appointment_by_lead: dict[str, str] = {}
        if lead_ids:
            first_appts = self.db.query(
                Appointment.lead_id,
                func.min(Appointment.scheduled_start).label('first_scheduled')
            ).filter(
                Appointment.company_id == tenant_id,
                Appointment.assigned_rep_id == rep_id,
                Appointment.lead_id.in_(lead_ids)
            ).group_by(Appointment.lead_id).all()
            
            for lead_id, first_scheduled in first_appts:
                first_appointment_by_lead[lead_id] = first_scheduled
        
        for appointment in all_appointments:
            try:
                # Check if attended (has recording session or analysis)
                has_recording = appointment.id in session_by_appointment_id
                has_analysis = appointment.id in analysis_by_appointment_id
                if has_recording or has_analysis:
                    attended_appointments += 1
                
                # Count completed appointments (status-based)
                if appointment.status == AppointmentStatus.COMPLETED.value:
                    completed_appointments += 1
                
                # Get analysis for outcome (Shunya-first)
                analysis = analysis_by_appointment_id.get(appointment.id)
                
                # OUTCOME: Use Shunya's RecordingAnalysis.outcome for won/lost, not Appointment.outcome
                # Only count outcomes for completed appointments
                if appointment.status == AppointmentStatus.COMPLETED.value and analysis and analysis.outcome:
                    # Ensure outcome is a string (handle enum values if any)
                    try:
                        # Handle both string and enum values
                        outcome_value = analysis.outcome
                        
                        # If it's an enum, get the value
                        if hasattr(outcome_value, 'value'):
                            outcome_str = outcome_value.value
                        elif hasattr(outcome_value, 'name'):
                            # It's an enum but we want the value, not the name
                            outcome_str = getattr(outcome_value, 'value', str(outcome_value))
                        else:
                            # It's already a string or other type
                            outcome_str = str(outcome_value) if outcome_value else None
                        
                        if outcome_str:
                            outcome_lower = outcome_str.lower().strip()
                        else:
                            outcome_lower = None
                    except Exception as e:
                        # Log the error but continue processing
                        logger.warning(
                            f"Error processing outcome for appointment {appointment.id}: {str(e)}, "
                            f"outcome type: {type(analysis.outcome)}, outcome value: {analysis.outcome}",
                            exc_info=True
                        )
                        outcome_lower = None
                
                # Track first-touch vs follow-up
                is_first_touch = False
                if appointment.lead_id and appointment.lead_id in first_appointment_by_lead:
                    first_scheduled = first_appointment_by_lead[appointment.lead_id]
                    # If this appointment is the first one for this lead, it's first-touch
                    if appointment.scheduled_start == first_scheduled:
                        is_first_touch = True
                
                if outcome_lower and outcome_lower == "won":
                    won_appointments += 1
                    
                    if is_first_touch:
                        first_touch_wins += 1
                        first_touch_completed += 1
                    else:
                        followup_wins += 1
                        followup_completed += 1
                elif outcome_lower and outcome_lower == "lost":
                    lost_appointments += 1
                    
                    if is_first_touch:
                        first_touch_completed += 1
                    else:
                        followup_completed += 1
                elif outcome_lower and outcome_lower in ("pending", "qualified", "rescheduled"):
                    pending_appointments += 1
                    
                    if is_first_touch:
                        first_touch_completed += 1
                    else:
                        followup_completed += 1
                
                # Aggregate metrics from analysis
                if analysis:
                    # Objections
                    if analysis.objections and isinstance(analysis.objections, list):
                        total_objections += len(analysis.objections)
                    
                    # Compliance score
                    if analysis.sop_compliance_score is not None:
                        compliance_scores.append(analysis.sop_compliance_score)
                    
                    # Meeting structure score
                    structure_score = self._compute_meeting_structure_score(analysis.meeting_segments)
                    if structure_score is not None:
                        meeting_structure_scores.append(structure_score)
                    
                    # Sentiment score
                    if analysis.sentiment_score is not None:
                        sentiment_scores.append(analysis.sentiment_score)
                
                # Auto usage hours: sum RecordingSession.audio_duration_seconds
                session = session_by_appointment_id.get(appointment.id)
                if session and session.audio_duration_seconds:
                    total_audio_duration_seconds += session.audio_duration_seconds
            except Exception as e:
                # Log error for this appointment but continue processing others
                logger.error(
                    f"Error processing appointment {appointment.id} in metrics computation: {str(e)}",
                    exc_info=True
                )
                # Continue to next appointment
                continue
        
        # Compute rates (null-safe)
        win_rate = won_appointments / completed_appointments if completed_appointments > 0 else None
        
        # First-touch and follow-up win rates
        first_touch_win_rate = first_touch_wins / first_touch_completed if first_touch_completed > 0 else None
        followup_win_rate = followup_wins / followup_completed if followup_completed > 0 else None
        
        # TODO: First-touch and follow-up detection is simplified - we need full appointment history
        # per lead to accurately determine if an appointment is truly first-touch vs follow-up.
        # For now, we use a heuristic based on earliest scheduled_start per lead.
        # If we don't have enough historical data, these will be None.
        
        # Auto usage hours
        auto_usage_hours = total_audio_duration_seconds / 3600.0 if total_audio_duration_seconds > 0 else None
        
        # Attendance rate
        attendance_rate = attended_appointments / scheduled_appointments if scheduled_appointments > 0 else None
        
        avg_objections = total_objections / total_appointments if total_appointments > 0 else None
        avg_compliance = sum(compliance_scores) / len(compliance_scores) if compliance_scores else None
        avg_meeting_structure = sum(meeting_structure_scores) / len(meeting_structure_scores) if meeting_structure_scores else None
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else None
        
        # Follow-up rate: (# leads with ≥ 1 follow-up task completed) / (# leads owned by this rep)
        # Get all leads owned by this rep (assigned_rep_id == rep_id)
        from app.models.lead import Lead
        rep_leads = self.db.query(Lead).filter(
            Lead.company_id == tenant_id,
            Lead.assigned_rep_id == rep_id
        ).all()
        rep_lead_ids = [lead.id for lead in rep_leads]
        total_leads = len(rep_lead_ids)
        
        leads_with_followup = 0
        if rep_lead_ids:
            # Count distinct leads that have at least one completed follow-up task
            # Filter for follow-up action types using ActionType enum
            from app.models.enums import ActionType
            followup_action_types = [
                ActionType.CALL_BACK.value,
                ActionType.FOLLOW_UP_CALL.value,
                ActionType.SEND_QUOTE.value,
                ActionType.SCHEDULE_APPOINTMENT.value,
                ActionType.SEND_ESTIMATE.value,
                ActionType.SEND_CONTRACT.value,
                ActionType.SEND_INFO.value,
                ActionType.SEND_DETAILS.value,
                ActionType.CHECK_IN.value,
            ]
            
            completed_followup_leads = self.db.query(distinct(Task.lead_id)).filter(
                Task.company_id == tenant_id,
                Task.lead_id.in_(rep_lead_ids),
                Task.status == TaskStatus.COMPLETED.value,
                Task.assigned_to == TaskAssignee.REP.value,
                # Filter for follow-up action types
                Task.action_type.in_(followup_action_types) if hasattr(Task, 'action_type') else True
            ).count()
            leads_with_followup = completed_followup_leads
        
        followup_rate = leads_with_followup / total_leads if total_leads > 0 else None
        
        # Task metrics (followups)
        now = datetime.utcnow()
        open_tasks_query = self.db.query(Task).filter(
            Task.company_id == tenant_id,
            Task.status.in_([TaskStatus.OPEN.value, TaskStatus.PENDING.value])
        )
        
        # Filter by rep: prefer assignee_id if available, else fallback to assigned_to role
        if hasattr(Task, 'assignee_id'):
            open_tasks_query = open_tasks_query.filter(
                or_(
                    Task.assignee_id == rep_id,
                    and_(
                        Task.assignee_id.is_(None),
                        Task.assigned_to == TaskAssignee.REP.value
                    )
                )
            )
        else:
            # Fallback to role-based filtering
            open_tasks_query = open_tasks_query.filter(Task.assigned_to == TaskAssignee.REP.value)
        
        all_open_tasks = open_tasks_query.all()
        
        open_followups = sum(
            1 for task in all_open_tasks
            if task.due_at is None or task.due_at >= now
        )
        
        overdue_followups = sum(
            1 for task in all_open_tasks
            if task.due_at is not None and task.due_at < now
        )
        
        # Pending followups: open tasks with due_date >= today
        today = now.date()
        pending_followups_count = sum(
            1 for task in all_open_tasks
            if task.due_at is None or task.due_at.date() >= today
        )
        
        return SalesRepMetrics(
            total_appointments=total_appointments,
            completed_appointments=completed_appointments,
            won_appointments=won_appointments,
            lost_appointments=lost_appointments,
            pending_appointments=pending_appointments,
            win_rate=win_rate,
            first_touch_win_rate=first_touch_win_rate,
            followup_win_rate=followup_win_rate,
            auto_usage_hours=auto_usage_hours,
            attendance_rate=attendance_rate,
            followup_rate=followup_rate,
            avg_objections_per_appointment=avg_objections,
            avg_compliance_score=avg_compliance,
            avg_meeting_structure_score=avg_meeting_structure,
            avg_sentiment_score=avg_sentiment,
            open_followups=open_followups,
            overdue_followups=overdue_followups,
            pending_followups_count=pending_followups_count
        )
    
    async def get_sales_team_metrics(
        self,
        *,
        tenant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> SalesTeamMetrics:
        """
        Compute aggregate sales team metrics for all reps in a company.
        
        Returns team-wide aggregates plus per-rep summaries.
        
        Args:
            tenant_id: Company/tenant ID
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
        
        Returns:
            SalesTeamMetrics with team aggregates and per-rep summaries
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Get all sales reps for this company
        reps = self.db.query(SalesRep).filter(
            SalesRep.company_id == tenant_id
        ).all()
        
        # Aggregate metrics across all reps
        total_appointments = 0
        completed_appointments = 0
        won_appointments = 0
        total_objections = 0
        compliance_scores = []
        meeting_structure_scores = []
        sentiment_scores = []
        
        # Per-rep summaries
        rep_summaries: List[SalesRepSummary] = []
        
        for rep in reps:
            # Get rep metrics
            rep_metrics = await self.get_sales_rep_overview_metrics(
                tenant_id=tenant_id,
                rep_id=rep.user_id,
                date_from=date_from,
                date_to=date_to
            )
            
            # Accumulate team totals
            total_appointments += rep_metrics.total_appointments
            completed_appointments += rep_metrics.completed_appointments
            won_appointments += rep_metrics.won_appointments
            
            # For averages, we need to collect individual scores
            # (we'll recompute from appointments below)
            
            # Get rep name from User
            rep_name = None
            user = self.db.query(User).filter(User.id == rep.user_id).first()
            if user:
                rep_name = user.name
            
            # Create rep summary
            rep_summaries.append(SalesRepSummary(
                rep_id=rep.user_id,
                rep_name=rep_name,
                total_appointments=rep_metrics.total_appointments,
                completed_appointments=rep_metrics.completed_appointments,
                won_appointments=rep_metrics.won_appointments,
                win_rate=rep_metrics.win_rate,
                avg_compliance_score=rep_metrics.avg_compliance_score,
                auto_usage_rate=None  # Placeholder
            ))
        
        # Recompute team averages from all appointments
        all_appointments = self.db.query(Appointment).filter(
            Appointment.company_id == tenant_id,
            Appointment.scheduled_start >= date_from,
            Appointment.scheduled_start <= date_to
        ).all()
        
        appointment_ids = [apt.id for apt in all_appointments]
        all_analyses = self.db.query(RecordingAnalysis).filter(
            RecordingAnalysis.appointment_id.in_(appointment_ids),
            RecordingAnalysis.company_id == tenant_id
        ).all()
        
        for analysis in all_analyses:
            # Objections
            if analysis.objections and isinstance(analysis.objections, list):
                total_objections += len(analysis.objections)
            
            # Compliance
            if analysis.sop_compliance_score is not None:
                compliance_scores.append(analysis.sop_compliance_score)
            
            # Meeting structure
            structure_score = self._compute_meeting_structure_score(analysis.meeting_segments)
            if structure_score is not None:
                meeting_structure_scores.append(structure_score)
            
            # Sentiment
            if analysis.sentiment_score is not None:
                sentiment_scores.append(analysis.sentiment_score)
        
        # Compute team rates
        team_win_rate = won_appointments / completed_appointments if completed_appointments > 0 else None
        avg_objections = total_objections / total_appointments if total_appointments > 0 else None
        avg_compliance = sum(compliance_scores) / len(compliance_scores) if compliance_scores else None
        avg_meeting_structure = sum(meeting_structure_scores) / len(meeting_structure_scores) if meeting_structure_scores else None
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else None
        
        return SalesTeamMetrics(
            total_appointments=total_appointments,
            completed_appointments=completed_appointments,
            team_win_rate=team_win_rate,
            avg_objections_per_appointment=avg_objections,
            avg_compliance_score=avg_compliance,
            avg_meeting_structure_score=avg_meeting_structure,
            avg_sentiment_score=avg_sentiment,
            reps=rep_summaries
        )
    
    async def get_exec_csr_metrics(
        self,
        *,
        tenant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> ExecCSRMetrics:
        """
        Compute executive-level CSR metrics (company-wide, not per-user).
        
        Args:
            tenant_id: Company/tenant ID
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
        
        Returns:
            ExecCSRMetrics with company-wide CSR metrics
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Query all CSR calls in date range (company-wide)
        calls_query = self.db.query(Call).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.created_at >= date_from,
            Call.created_at <= date_to
        )
        
        all_calls = calls_query.all()
        total_calls = len(all_calls)
        
        # Get analyses
        call_ids = [call.call_id for call in all_calls]
        analyses = self.db.query(CallAnalysis).filter(
            CallAnalysis.call_id.in_(call_ids),
            CallAnalysis.tenant_id == tenant_id
        ).all()
        
        analysis_by_call_id = {analysis.call_id: analysis for analysis in analyses}
        
        # Aggregate metrics
        qualified_calls = 0
        booked_calls = 0
        total_objections = 0
        compliance_scores = []
        sentiment_scores = []
        
        for call in all_calls:
            analysis = analysis_by_call_id.get(call.call_id)
            if not analysis:
                continue
            
            # Qualification
            lead_quality = analysis.lead_quality
            if lead_quality and lead_quality.lower() in ("hot", "warm", "cold", "qualified"):
                qualified_calls += 1
            
            # Booking
            if analysis.booking_status == BookingStatus.BOOKED.value:
                booked_calls += 1
            
            # Objections
            if analysis.objections and isinstance(analysis.objections, list):
                total_objections += len(analysis.objections)
            
            # Compliance
            if analysis.sop_compliance_score is not None:
                compliance_scores.append(analysis.sop_compliance_score)
            
            # Sentiment
            if analysis.sentiment_score is not None:
                sentiment_scores.append(analysis.sentiment_score)
        
        # Compute rates
        qualified_rate = qualified_calls / total_calls if total_calls > 0 else None
        booking_rate = booked_calls / qualified_calls if qualified_calls > 0 else None
        avg_objections = total_objections / total_calls if total_calls > 0 else None
        avg_compliance = sum(compliance_scores) / len(compliance_scores) if compliance_scores else None
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else None
        
        # Task metrics (all CSRs)
        now = datetime.utcnow()
        open_tasks = self.db.query(Task).filter(
            Task.company_id == tenant_id,
            Task.assigned_to == TaskAssignee.CSR.value,
            Task.status.in_([TaskStatus.OPEN.value, TaskStatus.PENDING.value])
        ).all()
        
        open_followups = sum(1 for task in open_tasks if task.due_at is None or task.due_at >= now)
        overdue_followups = sum(1 for task in open_tasks if task.due_at is not None and task.due_at < now)
        
        return ExecCSRMetrics(
            total_calls=total_calls,
            qualified_calls=qualified_calls,
            qualified_rate=qualified_rate,
            booked_calls=booked_calls,
            booking_rate=booking_rate,
            avg_objections_per_call=avg_objections,
            avg_compliance_score=avg_compliance,
            avg_sentiment_score=avg_sentiment,
            open_followups=open_followups,
            overdue_followups=overdue_followups
        )
    
    async def get_exec_sales_metrics(
        self,
        *,
        tenant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> ExecSalesMetrics:
        """
        Compute executive-level Sales metrics (company-wide, not per-rep).
        
        Args:
            tenant_id: Company/tenant ID
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
        
        Returns:
            ExecSalesMetrics with company-wide sales metrics
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Query all appointments in date range (company-wide)
        appointments_query = self.db.query(Appointment).filter(
            Appointment.company_id == tenant_id,
            Appointment.scheduled_start >= date_from,
            Appointment.scheduled_start <= date_to
        )
        
        all_appointments = appointments_query.all()
        total_appointments = len(all_appointments)
        
        # Get analyses
        appointment_ids = [apt.id for apt in all_appointments]
        analyses = self.db.query(RecordingAnalysis).filter(
            RecordingAnalysis.appointment_id.in_(appointment_ids),
            RecordingAnalysis.company_id == tenant_id
        ).all()
        
        analysis_by_appointment_id = {analysis.appointment_id: analysis for analysis in analyses}
        
        # Aggregate metrics
        completed_appointments = 0
        won_appointments = 0
        lost_appointments = 0
        pending_appointments = 0
        total_objections = 0
        compliance_scores = []
        meeting_structure_scores = []
        sentiment_scores = []
        
        for appointment in all_appointments:
            if appointment.status == AppointmentStatus.COMPLETED.value:
                completed_appointments += 1
                
                if appointment.outcome == AppointmentOutcome.WON.value:
                    won_appointments += 1
                elif appointment.outcome == AppointmentOutcome.LOST.value:
                    lost_appointments += 1
                elif appointment.outcome == AppointmentOutcome.PENDING.value:
                    pending_appointments += 1
            
            analysis = analysis_by_appointment_id.get(appointment.id)
            if analysis:
                if analysis.objections and isinstance(analysis.objections, list):
                    total_objections += len(analysis.objections)
                
                if analysis.sop_compliance_score is not None:
                    compliance_scores.append(analysis.sop_compliance_score)
                
                structure_score = self._compute_meeting_structure_score(analysis.meeting_segments)
                if structure_score is not None:
                    meeting_structure_scores.append(structure_score)
                
                if analysis.sentiment_score is not None:
                    sentiment_scores.append(analysis.sentiment_score)
        
        # Compute rates
        team_win_rate = won_appointments / completed_appointments if completed_appointments > 0 else None
        avg_objections = total_objections / total_appointments if total_appointments > 0 else None
        avg_compliance = sum(compliance_scores) / len(compliance_scores) if compliance_scores else None
        avg_meeting_structure = sum(meeting_structure_scores) / len(meeting_structure_scores) if meeting_structure_scores else None
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else None
        
        return ExecSalesMetrics(
            total_appointments=total_appointments,
            completed_appointments=completed_appointments,
            won_appointments=won_appointments,
            lost_appointments=lost_appointments,
            pending_appointments=pending_appointments,
            team_win_rate=team_win_rate,
            avg_objections_per_appointment=avg_objections,
            avg_compliance_score=avg_compliance,
            avg_meeting_structure_score=avg_meeting_structure,
            avg_sentiment_score=avg_sentiment
        )
    
    # CSR Dashboard specific methods
    
    async def get_csr_booking_trend(
        self,
        *,
        tenant_id: str,
        csr_user_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        granularity: Literal["day", "week", "month"] = "month",
    ) -> CSRBookingTrend:
        """
        Compute CSR booking trend over time (time series).
        
        Args:
            tenant_id: Company/tenant ID
            csr_user_id: CSR user ID
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
            granularity: Time bucket size (day, week, month)
        
        Returns:
            CSRBookingTrend with time series points
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Query CSR calls in date range
        calls_query = self.db.query(Call).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.owner_id == csr_user_id,
            Call.created_at >= date_from,
            Call.created_at <= date_to
        )
        
        all_calls = calls_query.all()
        call_ids = [call.call_id for call in all_calls]
        
        # Get analyses
        analyses = self.db.query(CallAnalysis).filter(
            CallAnalysis.call_id.in_(call_ids),
            CallAnalysis.tenant_id == tenant_id
        ).all()
        
        analysis_by_call_id = {analysis.call_id: analysis for analysis in analyses}
        
        # Group by period based on granularity
        points: List[CSRBookingTrendPoint] = []
        current = date_from
        
        while current <= date_to:
            if granularity == "day":
                period_end = current + timedelta(days=1)
            elif granularity == "week":
                period_end = current + timedelta(weeks=1)
            else:  # month
                # Approximate month as 30 days
                period_end = current + timedelta(days=30)
            
            # Filter calls in this period
            period_calls = [c for c in all_calls if current <= c.created_at < period_end]
            
            # Count leads and qualified (only from Shunya fields)
            total_leads = len(period_calls)
            qualified_leads = 0
            booked_appointments = 0  # This is actually booked_calls from Shunya, not appointments
            
            for call in period_calls:
                analysis = analysis_by_call_id.get(call.call_id)
                if analysis:
                    # QUALIFICATION: Only use Shunya's lead_quality
                    lead_quality = analysis.lead_quality
                    if lead_quality and lead_quality.lower() in ("hot", "warm", "cold", "qualified"):
                        qualified_leads += 1
                    
                    # BOOKING: Only use Shunya's booking_status - never infer from appointments
                    if analysis.booking_status == BookingStatus.BOOKED.value:
                        booked_appointments += 1
            
            booking_rate = booked_appointments / qualified_leads if qualified_leads > 0 else None
            
            points.append(CSRBookingTrendPoint(
                period_start=current,
                period_end=period_end,
                booking_rate=booking_rate,
                total_leads=total_leads,
                qualified_leads=qualified_leads,
                booked_appointments=booked_appointments
            ))
            
            current = period_end
        
        return CSRBookingTrend(points=points)
    
    async def get_csr_unbooked_appointments(
        self,
        *,
        tenant_id: str,
        csr_user_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> CSRUnbookedAppointmentsResponse:
        """
        Get list of unbooked appointments/calls for a CSR.
        
        Args:
            tenant_id: Company/tenant ID
            csr_user_id: CSR user ID
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
        
        Returns:
            CSRUnbookedAppointmentsResponse with unbooked items
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Query CSR calls
        calls_query = self.db.query(Call).join(
            ContactCard, Call.contact_card_id == ContactCard.id, isouter=True
        ).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.owner_id == csr_user_id,
            Call.created_at >= date_from,
            Call.created_at <= date_to
        )
        
        all_calls = calls_query.all()
        call_ids = [call.call_id for call in all_calls]
        
        # Get analyses
        analyses = self.db.query(CallAnalysis).filter(
            CallAnalysis.call_id.in_(call_ids),
            CallAnalysis.tenant_id == tenant_id
        ).all()
        
        analysis_by_call_id = {analysis.call_id: analysis for analysis in analyses}
        
        # Filter unbooked calls
        items: List[CSRUnbookedAppointmentItem] = []
        
        for call in all_calls:
            analysis = analysis_by_call_id.get(call.call_id)
            
            # Check if unbooked
            is_unbooked = False
            if analysis:
                if analysis.booking_status and analysis.booking_status != BookingStatus.BOOKED.value:
                    is_unbooked = True
                elif analysis.call_outcome_category == CallOutcomeCategory.QUALIFIED_BUT_UNBOOKED.value:
                    is_unbooked = True
                elif analysis.call_outcome_category == CallOutcomeCategory.QUALIFIED_SERVICE_NOT_OFFERED.value:
                    is_unbooked = True
            
            if is_unbooked:
                # Get primary objection
                primary_objection: Optional[str] = None
                if analysis and analysis.objections and isinstance(analysis.objections, list) and len(analysis.objections) > 0:
                    first_obj = analysis.objections[0]
                    if isinstance(first_obj, str):
                        primary_objection = first_obj
                    elif isinstance(first_obj, dict) and "type" in first_obj:
                        primary_objection = first_obj["type"]
                
                # Get customer name and phone from contact card
                customer_name = None
                phone = None
                if call.contact_card:
                    customer_name = f"{call.contact_card.first_name or ''} {call.contact_card.last_name or ''}".strip() or None
                    phone = call.contact_card.primary_phone
                
                items.append(CSRUnbookedAppointmentItem(
                    call_id=call.call_id,
                    lead_id=call.lead_id,
                    customer_name=customer_name,
                    phone=phone,
                    created_at=call.created_at,
                    qualification_status=analysis.lead_quality if analysis else None,
                    booking_status=analysis.booking_status if analysis else None,
                    primary_objection=primary_objection
                ))
        
        return CSRUnbookedAppointmentsResponse(items=items)
    
    async def get_csr_top_objections(
        self,
        *,
        tenant_id: str,
        csr_user_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 5,
    ) -> CSRTopObjectionsResponse:
        """
        Get top objections for a CSR.
        
        Args:
            tenant_id: Company/tenant ID
            csr_user_id: CSR user ID
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
            limit: Number of top objections to return
        
        Returns:
            CSRTopObjectionsResponse with top objections
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Query CSR calls
        calls_query = self.db.query(Call).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.owner_id == csr_user_id,
            Call.created_at >= date_from,
            Call.created_at <= date_to
        )
        
        all_calls = calls_query.all()
        call_ids = [call.call_id for call in all_calls]
        
        # Get analyses
        analyses = self.db.query(CallAnalysis).filter(
            CallAnalysis.call_id.in_(call_ids),
            CallAnalysis.tenant_id == tenant_id
        ).all()
        
        # Count objections
        objection_counts: dict[str, int] = {}
        calls_with_analysis = 0
        
        for analysis in analyses:
            calls_with_analysis += 1
            if analysis.objections and isinstance(analysis.objections, list):
                for obj in analysis.objections:
                    if isinstance(obj, str):
                        key = obj
                        label = obj.replace("_", " ").title()
                    elif isinstance(obj, dict):
                        key = obj.get("type", "unknown")
                        label = obj.get("label", key.replace("_", " ").title())
                    else:
                        continue
                    
                    objection_counts[key] = objection_counts.get(key, 0) + 1
        
        # Sort by count and take top N
        sorted_objections = sorted(objection_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        
        top_objections: List[CSRObjectionMetric] = []
        for key, count in sorted_objections:
            # Find label from first occurrence
            label = key.replace("_", " ").title()
            for analysis in analyses:
                if analysis.objections and isinstance(analysis.objections, list):
                    for obj in analysis.objections:
                        if isinstance(obj, dict) and obj.get("type") == key:
                            label = obj.get("label", label)
                            break
                    if label != key.replace("_", " ").title():
                        break
            
            occurrence_rate = count / calls_with_analysis if calls_with_analysis > 0 else 0.0
            
            top_objections.append(CSRObjectionMetric(
                objection_key=key,
                label=label,
                occurrence_count=count,
                occurrence_rate=occurrence_rate
            ))
        
        return CSRTopObjectionsResponse(
            top_objections=top_objections,
            total_calls_considered=calls_with_analysis
        )
    
    async def get_csr_objection_calls(
        self,
        *,
        tenant_id: str,
        csr_user_id: str,
        objection_key: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> CSRObjectionCallsResponse:
        """
        Get calls where a specific objection occurred.
        
        Args:
            tenant_id: Company/tenant ID
            csr_user_id: CSR user ID
            objection_key: The objection key to filter by
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
        
        Returns:
            CSRObjectionCallsResponse with matching calls
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Query CSR calls
        calls_query = self.db.query(Call).join(
            ContactCard, Call.contact_card_id == ContactCard.id, isouter=True
        ).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.owner_id == csr_user_id,
            Call.created_at >= date_from,
            Call.created_at <= date_to
        )
        
        all_calls = calls_query.all()
        call_ids = [call.call_id for call in all_calls]
        
        # Get analyses
        analyses = self.db.query(CallAnalysis).filter(
            CallAnalysis.call_id.in_(call_ids),
            CallAnalysis.tenant_id == tenant_id
        ).all()
        
        analysis_by_call_id = {analysis.call_id: analysis for analysis in analyses}
        
        # Filter calls with this objection
        items: List[CSRObjectionCallItem] = []
        
        for call in all_calls:
            analysis = analysis_by_call_id.get(call.call_id)
            if not analysis or not analysis.objections:
                continue
            
            # Check if this objection exists
            has_objection = False
            for obj in analysis.objections:
                if isinstance(obj, str) and obj == objection_key:
                    has_objection = True
                    break
                elif isinstance(obj, dict) and obj.get("type") == objection_key:
                    has_objection = True
                    break
            
            if has_objection:
                # Get customer info
                customer_name = None
                phone = None
                if call.contact_card:
                    customer_name = f"{call.contact_card.first_name or ''} {call.contact_card.last_name or ''}".strip() or None
                    phone = call.contact_card.primary_phone
                
                # Get transcript snippet (first 200 chars)
                transcript_snippet = None
                if call.transcript:
                    transcript_snippet = call.transcript[:200] + "..." if len(call.transcript) > 200 else call.transcript
                
                # Audio URL (if available from call record)
                audio_url = None  # TODO: Wire audio URL from call/recording if available
                
                items.append(CSRObjectionCallItem(
                    call_id=call.call_id,
                    lead_id=call.lead_id,
                    customer_name=customer_name,
                    phone=phone,
                    created_at=call.created_at,
                    audio_url=audio_url,
                    transcript_snippet=transcript_snippet
                ))
        
        return CSRObjectionCallsResponse(
            objection_key=objection_key,
            items=items
        )
    
    async def get_auto_queued_leads(
        self,
        *,
        tenant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> AutoQueuedLeadsResponse:
        """
        Get auto-queued leads (AI recovery from missed calls).
        
        Args:
            tenant_id: Company/tenant ID
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
        
        Returns:
            AutoQueuedLeadsResponse with auto-queued leads
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Query leads marked as AI recovery (source = "ai_recovery" or similar)
        # For now, we'll use Lead.source or a flag - adjust based on actual implementation
        leads_query = self.db.query(Lead).join(
            ContactCard, Lead.contact_card_id == ContactCard.id, isouter=True
        ).filter(
            Lead.company_id == tenant_id,
            Lead.source.in_([LeadSource.INBOUND_CALL.value, "ai_recovery"]),  # Adjust based on actual source enum
            Lead.created_at >= date_from,
            Lead.created_at <= date_to
        )
        
        all_leads = leads_query.all()
        
        items: List[AutoQueuedLeadItem] = []
        for lead in all_leads:
            customer_name = None
            phone = None
            if lead.contact_card:
                customer_name = f"{lead.contact_card.first_name or ''} {lead.contact_card.last_name or ''}".strip() or None
                phone = lead.contact_card.primary_phone
            
            items.append(AutoQueuedLeadItem(
                lead_id=lead.id,
                customer_name=customer_name,
                phone=phone,
                last_contacted_at=lead.last_contacted_at,
                status=lead.status.value if hasattr(lead.status, 'value') else str(lead.status)
            ))
        
        return AutoQueuedLeadsResponse(items=items)
    
    async def get_csr_missed_call_recovery(
        self,
        *,
        tenant_id: str,
        csr_user_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> CSRMissedCallRecoveryResponse:
        """
        Get missed call recovery overview for a CSR.
        
        Args:
            tenant_id: Company/tenant ID
            csr_user_id: CSR user ID
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
        
        Returns:
            CSRMissedCallRecoveryResponse with metrics and lead lists
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Query missed calls for this CSR
        missed_calls_query = self.db.query(Call).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.owner_id == csr_user_id,
            Call.missed_call == True,
            Call.created_at >= date_from,
            Call.created_at <= date_to
        )
        
        missed_calls = missed_calls_query.all()
        missed_calls_count = len(missed_calls)
        
        # Get lead IDs and call IDs from missed calls
        missed_call_lead_ids = [call.lead_id for call in missed_calls if call.lead_id]
        missed_call_ids = [call.call_id for call in missed_calls]
        
        # Count saved calls using Shunya's CallAnalysis - never infer from appointments
        # A missed call is "saved" if there's a CallAnalysis with booking_status == "booked"
        # for that call or a subsequent call for the same lead
        saved_calls_count = 0
        saved_calls_via_auto_rescue_count = 0
        
        # Get analyses for missed calls
        missed_call_analyses = self.db.query(CallAnalysis).filter(
            CallAnalysis.call_id.in_(missed_call_ids),
            CallAnalysis.tenant_id == tenant_id
        ).all()
        
        # Also check for subsequent calls (follow-up calls) for the same leads
        # that might have been booked
        if missed_call_lead_ids:
            # Get all calls for these leads (including follow-ups)
            followup_calls = self.db.query(Call).filter(
                Call.lead_id.in_(missed_call_lead_ids),
                Call.company_id == tenant_id,
                Call.created_at >= date_from,
                Call.created_at <= date_to
            ).all()
            
            followup_call_ids = [call.call_id for call in followup_calls]
            
            # Get analyses for follow-up calls
            followup_analyses = self.db.query(CallAnalysis).filter(
                CallAnalysis.call_id.in_(followup_call_ids),
                CallAnalysis.tenant_id == tenant_id
            ).all()
            
            # Count saved calls: missed calls where Shunya says booking_status == "booked"
            # (either for the missed call itself or a follow-up call)
            saved_call_lead_ids = set()
            for analysis in followup_analyses:
                if analysis.booking_status == BookingStatus.BOOKED.value:
                    # Find the lead_id for this call
                    for call in followup_calls:
                        if call.call_id == analysis.call_id and call.lead_id:
                            saved_call_lead_ids.add(call.lead_id)
                            break
            
            saved_calls_count = len(saved_call_lead_ids)
            
            # Count auto-rescues: leads with source = "ai_recovery" that were saved
            for lead_id in saved_call_lead_ids:
                lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
                if lead and lead.source in [LeadSource.INBOUND_CALL.value, "ai_recovery"]:
                    saved_calls_via_auto_rescue_count += 1
        
        # Get leads and categorize
        booked_leads: List[CSRLeadStatusItem] = []
        pending_leads: List[CSRLeadStatusItem] = []
        dead_leads: List[CSRLeadStatusItem] = []
        
        if missed_call_lead_ids:
            leads = self.db.query(Lead).join(
                ContactCard, Lead.contact_card_id == ContactCard.id, isouter=True
            ).filter(
                Lead.id.in_(missed_call_lead_ids),
                Lead.company_id == tenant_id
            ).all()
            
            for lead in leads:
                customer_name = None
                phone = None
                if lead.contact_card:
                    customer_name = f"{lead.contact_card.first_name or ''} {lead.contact_card.last_name or ''}".strip() or None
                    phone = lead.contact_card.primary_phone
                
                # Get tasks for this lead (for pending_action and attempts_count)
                tasks = self.db.query(Task).filter(
                    Task.lead_id == lead.id,
                    Task.company_id == tenant_id
                ).all()
                
                pending_action = None
                attempts_count = len(tasks)
                
                if tasks:
                    open_tasks = [t for t in tasks if t.status in [TaskStatus.OPEN.value, TaskStatus.PENDING.value]]
                    if open_tasks:
                        pending_action = open_tasks[0].description
                
                # Categorize by Shunya's CallAnalysis - never use Lead.status for booking semantics
                # Check if any call for this lead has booking_status == "booked" from Shunya
                lead_calls = self.db.query(Call).filter(
                    Call.lead_id == lead.id,
                    Call.company_id == tenant_id
                ).all()
                
                lead_call_ids = [call.call_id for call in lead_calls]
                lead_analyses = self.db.query(CallAnalysis).filter(
                    CallAnalysis.call_id.in_(lead_call_ids),
                    CallAnalysis.tenant_id == tenant_id
                ).all()
                
                # Check Shunya's booking_status
                is_booked = any(
                    analysis.booking_status == BookingStatus.BOOKED.value
                    for analysis in lead_analyses
                )
                
                # Check if dead (using Lead.status for lead lifecycle, not booking semantics)
                is_dead = lead.status in [LeadStatus.ABANDONED.value, LeadStatus.CLOSED_LOST.value, LeadStatus.DORMANT.value]
                
                if is_booked:
                    booked_leads.append(CSRLeadStatusItem(
                        lead_id=lead.id,
                        customer_name=customer_name,
                        phone=phone,
                        status="booked",
                        pending_action=None,
                        last_contacted_at=lead.last_contacted_at,
                        attempts_count=attempts_count
                    ))
                elif is_dead:
                    dead_leads.append(CSRLeadStatusItem(
                        lead_id=lead.id,
                        customer_name=customer_name,
                        phone=phone,
                        status="dead",
                        pending_action=None,
                        last_contacted_at=lead.last_contacted_at,
                        attempts_count=attempts_count
                    ))
                else:
                    pending_leads.append(CSRLeadStatusItem(
                        lead_id=lead.id,
                        customer_name=customer_name,
                        phone=phone,
                        status="pending",
                        pending_action=pending_action,
                        last_contacted_at=lead.last_contacted_at,
                        attempts_count=attempts_count
                    ))
        
        return CSRMissedCallRecoveryResponse(
            metrics=CSRMissedCallMetrics(
                missed_calls_count=missed_calls_count,
                saved_calls_count=saved_calls_count,
                saved_calls_via_auto_rescue_count=saved_calls_via_auto_rescue_count
            ),
            booked_leads=booked_leads,
            pending_leads=pending_leads,
            dead_leads=dead_leads
        )
    
    # Executive Dashboard methods
    
    async def get_exec_company_overview_metrics(
        self,
        *,
        tenant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> ExecCompanyOverviewMetrics:
        """
        Compute executive company-wide overview metrics.
        
        Uses Shunya fields as single source of truth for:
        - qualified_leads: from CallAnalysis.lead_quality
        - total_closed_deals: from RecordingAnalysis.outcome == "won" or Appointment.outcome == WON
        - win/loss/pending rates: from Shunya outcome fields
        
        Args:
            tenant_id: Company/tenant ID
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
        
        Returns:
            ExecCompanyOverviewMetrics with company-wide funnel and attribution
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Total leads (from Lead model - metadata only)
        total_leads = self.db.query(Lead).filter(
            Lead.company_id == tenant_id,
            Lead.created_at >= date_from,
            Lead.created_at <= date_to
        ).count()
        
        # Qualified leads (from Shunya CallAnalysis.lead_quality)
        qualified_calls = self.db.query(CallAnalysis).join(
            Call, CallAnalysis.call_id == Call.call_id
        ).filter(
            CallAnalysis.tenant_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.created_at >= date_from,
            Call.created_at <= date_to,
            CallAnalysis.lead_quality.in_(["hot", "warm", "cold", "qualified"])
        ).count()
        
        qualified_leads = qualified_calls  # For now, 1:1 mapping (can refine later)
        
        # Total appointments (from Appointment model - metadata only)
        total_appointments = self.db.query(Appointment).filter(
            Appointment.company_id == tenant_id,
            Appointment.scheduled_start >= date_from,
            Appointment.scheduled_start <= date_to
        ).count()
        
        # Total closed deals (from Shunya RecordingAnalysis.outcome == "won")
        # Also check Appointment.outcome == WON as fallback (but prefer Shunya)
        closed_deals_from_recordings = self.db.query(RecordingAnalysis).join(
            Appointment, RecordingAnalysis.appointment_id == Appointment.id
        ).filter(
            RecordingAnalysis.company_id == tenant_id,
            Appointment.scheduled_start >= date_from,
            Appointment.scheduled_start <= date_to,
            RecordingAnalysis.outcome == "won"  # Shunya says won
        ).count()
        
        # Also count appointments marked as WON (if RecordingAnalysis not available)
        closed_deals_from_appointments = self.db.query(Appointment).filter(
            Appointment.company_id == tenant_id,
            Appointment.scheduled_start >= date_from,
            Appointment.scheduled_start <= date_to,
            Appointment.outcome == AppointmentOutcome.WON.value
        ).count()
        
        # Use Shunya as primary source, but include appointments if no Shunya data
        total_closed_deals = closed_deals_from_recordings if closed_deals_from_recordings > 0 else closed_deals_from_appointments
        
        # Compute ratios (null-safe)
        lead_to_sale_ratio = total_closed_deals / total_leads if total_leads > 0 else None
        close_rate = total_closed_deals / qualified_leads if qualified_leads > 0 else None
        win_rate = close_rate  # Same as close_rate
        
        # Win/loss/pending breakdown (from Shunya)
        # Count pending: RecordingAnalysis.outcome == "pending" or Appointment.outcome == PENDING
        pending_deals = self.db.query(RecordingAnalysis).join(
            Appointment, RecordingAnalysis.appointment_id == Appointment.id
        ).filter(
            RecordingAnalysis.company_id == tenant_id,
            Appointment.scheduled_start >= date_from,
            Appointment.scheduled_start <= date_to,
            RecordingAnalysis.outcome == "pending"
        ).count()
        
        if pending_deals == 0:
            # Fallback to Appointment.outcome
            pending_deals = self.db.query(Appointment).filter(
                Appointment.company_id == tenant_id,
                Appointment.scheduled_start >= date_from,
                Appointment.scheduled_start <= date_to,
                Appointment.outcome == AppointmentOutcome.PENDING.value
            ).count()
        
        # Count lost: RecordingAnalysis.outcome == "lost" or Appointment.outcome == LOST
        lost_deals = self.db.query(RecordingAnalysis).join(
            Appointment, RecordingAnalysis.appointment_id == Appointment.id
        ).filter(
            RecordingAnalysis.company_id == tenant_id,
            Appointment.scheduled_start >= date_from,
            Appointment.scheduled_start <= date_to,
            RecordingAnalysis.outcome == "lost"
        ).count()
        
        if lost_deals == 0:
            # Fallback to Appointment.outcome
            lost_deals = self.db.query(Appointment).filter(
                Appointment.company_id == tenant_id,
                Appointment.scheduled_start >= date_from,
                Appointment.scheduled_start <= date_to,
                Appointment.outcome == AppointmentOutcome.LOST.value
            ).count()
        
        pending_rate = pending_deals / qualified_leads if qualified_leads > 0 else None
        lost_rate = lost_deals / qualified_leads if qualified_leads > 0 else None
        
        # Attribution (approximate using Task.assignee_role and CallType)
        # TODO: Add more precise stage tags for better attribution
        attribution = None
        if qualified_leads > 0:
            # CSR initial call stage
            csr_initial_pending = 0
            csr_initial_lost = 0
            
            # CSR follow-up stage (tasks assigned to CSR)
            csr_followup_tasks = self.db.query(Task).filter(
                Task.company_id == tenant_id,
                Task.assigned_to == TaskAssignee.CSR.value,
                Task.created_at >= date_from,
                Task.created_at <= date_to
            ).count()
            
            # Sales follow-up stage (tasks assigned to REP)
            sales_followup_tasks = self.db.query(Task).filter(
                Task.company_id == tenant_id,
                Task.assigned_to == TaskAssignee.REP.value,
                Task.created_at >= date_from,
                Task.created_at <= date_to
            ).count()
            
            # Sales appointment stage (completed appointments)
            sales_appointments = self.db.query(Appointment).filter(
                Appointment.company_id == tenant_id,
                Appointment.status == AppointmentStatus.COMPLETED.value,
                Appointment.scheduled_start >= date_from,
                Appointment.scheduled_start <= date_to
            ).count()
            
            # For now, leave attribution as None if we can't confidently attribute
            # TODO: Add stage tags to calls/tasks for precise attribution
            attribution = ExecCompanyWinLossAttribution(
                pending_from_csr_initial_call=None,  # TODO: Add stage tracking
                lost_from_csr_initial_call=None,
                pending_from_csr_followup=None,
                lost_from_csr_followup=None,
                pending_from_sales_followup=None,
                lost_from_sales_followup=None,
                pending_from_sales_appointment=None,
                lost_from_sales_appointment=None
            )
        
        # Who is dropping the ball
        # Find worst CSR (lowest booking rate)
        worst_csr_id = None
        worst_csr_name = None
        worst_csr_booking_rate = None
        
        # Get all CSRs with calls in date range
        csr_calls_query = self.db.query(Call.owner_id, func.count(Call.call_id).label('total_calls')).join(
            CallAnalysis, Call.call_id == CallAnalysis.call_id, isouter=True
        ).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.owner_id.isnot(None),
            Call.created_at >= date_from,
            Call.created_at <= date_to
        ).group_by(Call.owner_id).having(func.count(Call.call_id) >= 5)  # Minimum activity threshold
        
        csr_stats = csr_calls_query.all()
        
        if csr_stats:
            csr_booking_rates = []
            for csr_id, total_calls in csr_stats:
                # Get booked calls for this CSR
                booked_calls = self.db.query(Call).join(
                    CallAnalysis, Call.call_id == CallAnalysis.call_id
                ).filter(
                    Call.company_id == tenant_id,
                    Call.call_type == CallType.CSR_CALL.value,
                    Call.owner_id == csr_id,
                    Call.created_at >= date_from,
                    Call.created_at <= date_to,
                    CallAnalysis.booking_status == BookingStatus.BOOKED.value
                ).count()
                
                booking_rate = booked_calls / total_calls if total_calls > 0 else 0.0
                csr_booking_rates.append((csr_id, booking_rate, total_calls))
            
            if csr_booking_rates:
                # Find worst (lowest booking rate)
                worst_csr_id, worst_csr_booking_rate, _ = min(csr_booking_rates, key=lambda x: x[1])
                
                # Get CSR name
                user = self.db.query(User).filter(User.id == worst_csr_id).first()
                if user:
                    worst_csr_name = user.name
        
        # Find worst Sales Rep (lowest win rate)
        worst_rep_id = None
        worst_rep_name = None
        worst_rep_win_rate = None
        
        # Get all reps with appointments in date range
        rep_appointments_query = self.db.query(
            Appointment.assigned_rep_id,
            func.count(Appointment.id).label('total_appointments')
        ).filter(
            Appointment.company_id == tenant_id,
            Appointment.assigned_rep_id.isnot(None),
            Appointment.scheduled_start >= date_from,
            Appointment.scheduled_start <= date_to
        ).group_by(Appointment.assigned_rep_id).having(func.count(Appointment.id) >= 3)  # Minimum activity threshold
        
        rep_stats = rep_appointments_query.all()
        
        if rep_stats:
            rep_win_rates = []
            for rep_id, total_appointments in rep_stats:
                # Get won appointments for this rep (from Shunya RecordingAnalysis)
                won_appointments = self.db.query(RecordingAnalysis).join(
                    Appointment, RecordingAnalysis.appointment_id == Appointment.id
                ).filter(
                    RecordingAnalysis.company_id == tenant_id,
                    Appointment.assigned_rep_id == rep_id,
                    Appointment.scheduled_start >= date_from,
                    Appointment.scheduled_start <= date_to,
                    RecordingAnalysis.outcome == "won"
                ).count()
                
                if won_appointments == 0:
                    # Fallback to Appointment.outcome
                    won_appointments = self.db.query(Appointment).filter(
                        Appointment.company_id == tenant_id,
                        Appointment.assigned_rep_id == rep_id,
                        Appointment.scheduled_start >= date_from,
                        Appointment.scheduled_start <= date_to,
                        Appointment.outcome == AppointmentOutcome.WON.value
                    ).count()
                
                win_rate = won_appointments / total_appointments if total_appointments > 0 else 0.0
                rep_win_rates.append((rep_id, win_rate, total_appointments))
            
            if rep_win_rates:
                # Find worst (lowest win rate)
                worst_rep_id, worst_rep_win_rate, _ = min(rep_win_rates, key=lambda x: x[1])
                
                # Get rep name
                user = self.db.query(User).filter(User.id == worst_rep_id).first()
                if user:
                    worst_rep_name = user.name
        
        who_dropping_ball = ExecWhoDroppingBall(
            worst_csr_id=worst_csr_id,
            worst_csr_name=worst_csr_name,
            worst_csr_booking_rate=worst_csr_booking_rate,
            worst_rep_id=worst_rep_id,
            worst_rep_name=worst_rep_name,
            worst_rep_win_rate=worst_rep_win_rate
        )
        
        return ExecCompanyOverviewMetrics(
            total_leads=total_leads if total_leads > 0 else None,
            qualified_leads=qualified_leads if qualified_leads > 0 else None,
            total_appointments=total_appointments if total_appointments > 0 else None,
            total_closed_deals=total_closed_deals if total_closed_deals > 0 else None,
            lead_to_sale_ratio=lead_to_sale_ratio,
            close_rate=close_rate,
            sales_output_amount=None,  # TODO: Revenue piping
            win_rate=win_rate,
            pending_rate=pending_rate,
            lost_rate=lost_rate,
            win_loss_attribution=attribution,
            who_dropping_ball=who_dropping_ball
        )
    
    async def get_exec_csr_dashboard_metrics(
        self,
        *,
        tenant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> ExecCSRDashboardMetrics:
        """
        Compute executive CSR dashboard metrics (company-wide CSR view).
        
        Args:
            tenant_id: Company/tenant ID
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
        
        Returns:
            ExecCSRDashboardMetrics with overview, trends, objections, and coaching opportunities
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Overview: reuse existing exec CSR metrics
        overview = await self.get_exec_csr_metrics(
            tenant_id=tenant_id,
            date_from=date_from,
            date_to=date_to
        )
        
        # Booking rate trend (aggregated across all CSRs)
        # Reuse CSR booking trend logic but company-wide
        all_csr_calls = self.db.query(Call).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.created_at >= date_from,
            Call.created_at <= date_to
        ).all()
        
        call_ids = [call.call_id for call in all_csr_calls]
        analyses = self.db.query(CallAnalysis).filter(
            CallAnalysis.call_id.in_(call_ids),
            CallAnalysis.tenant_id == tenant_id
        ).all()
        
        analysis_by_call_id = {analysis.call_id: analysis for analysis in analyses}
        
        # Group by month for trend
        booking_rate_trend: List[TimeSeriesPoint] = []
        current = date_from
        
        while current <= date_to:
            period_end = current + timedelta(days=30)  # Monthly buckets
            
            period_calls = [c for c in all_csr_calls if current <= c.created_at < period_end]
            
            total_leads = len(period_calls)
            qualified_leads = 0
            booked_calls = 0
            
            for call in period_calls:
                analysis = analysis_by_call_id.get(call.call_id)
                if analysis:
                    lead_quality = analysis.lead_quality
                    if lead_quality and lead_quality.lower() in ("hot", "warm", "cold", "qualified"):
                        qualified_leads += 1
                    
                    if analysis.booking_status == BookingStatus.BOOKED.value:
                        booked_calls += 1
            
            booking_rate = booked_calls / qualified_leads if qualified_leads > 0 else None
            
            booking_rate_trend.append(TimeSeriesPoint(
                bucket_start=current,
                bucket_end=period_end,
                value=booking_rate
            ))
            
            current = period_end
        
        # Unbooked calls count (CSR-wide)
        unbooked_calls_count = self.db.query(Call).join(
            CallAnalysis, Call.call_id == CallAnalysis.call_id
        ).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.created_at >= date_from,
            Call.created_at <= date_to,
            CallAnalysis.booking_status != BookingStatus.BOOKED.value
        ).count()
        
        # Top objections across all CSRs
        all_csr_analyses = self.db.query(CallAnalysis).join(
            Call, CallAnalysis.call_id == Call.call_id
        ).filter(
            CallAnalysis.tenant_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.created_at >= date_from,
            Call.created_at <= date_to
        ).all()
        
        objection_counts: dict[str, int] = {}
        total_calls_with_analysis = len(all_csr_analyses)
        qualified_unbooked_calls = 0
        
        for analysis in all_csr_analyses:
            # Count qualified but unbooked for rate calculation
            if (analysis.lead_quality and analysis.lead_quality.lower() in ("hot", "warm", "cold", "qualified") and
                analysis.booking_status and analysis.booking_status != BookingStatus.BOOKED.value):
                qualified_unbooked_calls += 1
            
            # Count objections
            if analysis.objections and isinstance(analysis.objections, list):
                for obj in analysis.objections:
                    if isinstance(obj, str):
                        key = obj
                        label = obj.replace("_", " ").title()
                    elif isinstance(obj, dict):
                        key = obj.get("type", "unknown")
                        label = obj.get("label", key.replace("_", " ").title())
                    else:
                        continue
                    
                    objection_counts[key] = objection_counts.get(key, 0) + 1
        
        # Sort and take top 5
        sorted_objections = sorted(objection_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        top_objections: List[ObjectionSummary] = []
        for key, count in sorted_objections:
            # Find label
            label = key.replace("_", " ").title()
            for analysis in all_csr_analyses:
                if analysis.objections and isinstance(analysis.objections, list):
                    for obj in analysis.objections:
                        if isinstance(obj, dict) and obj.get("type") == key:
                            label = obj.get("label", label)
                            break
                    if label != key.replace("_", " ").title():
                        break
            
            occurrence_rate = count / total_calls_with_analysis if total_calls_with_analysis > 0 else None
            occurrence_rate_over_qualified_unbooked = count / qualified_unbooked_calls if qualified_unbooked_calls > 0 else None
            
            top_objections.append(ObjectionSummary(
                objection_key=key,
                objection_label=label,
                occurrence_count=count,
                occurrence_rate=occurrence_rate,
                occurrence_rate_over_qualified_unbooked=occurrence_rate_over_qualified_unbooked
            ))
        
        # Coaching opportunities (per CSR)
        # Get all CSRs with calls
        csr_ids = self.db.query(Call.owner_id).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.owner_id.isnot(None),
            Call.created_at >= date_from,
            Call.created_at <= date_to
        ).distinct().all()
        
        coaching_opportunities: List[CSRAgentCoachingSummary] = []
        
        for (csr_id,) in csr_ids:
            # Get CSR metrics
            csr_metrics = await self.get_csr_overview_metrics(
                csr_user_id=csr_id,
                tenant_id=tenant_id,
                start=date_from,
                end=date_to
            )
            
            # Get CSR name
            csr_name = None
            user = self.db.query(User).filter(User.id == csr_id).first()
            if user:
                csr_name = user.name
            
            # Get top objections for this CSR
            csr_calls = self.db.query(Call).filter(
                Call.company_id == tenant_id,
                Call.call_type == CallType.CSR_CALL.value,
                Call.owner_id == csr_id,
                Call.created_at >= date_from,
                Call.created_at <= date_to
            ).all()
            
            csr_call_ids = [call.call_id for call in csr_calls]
            csr_analyses = self.db.query(CallAnalysis).filter(
                CallAnalysis.call_id.in_(csr_call_ids),
                CallAnalysis.tenant_id == tenant_id
            ).all()
            
            csr_objection_counts: dict[str, int] = {}
            for analysis in csr_analyses:
                if analysis.objections and isinstance(analysis.objections, list):
                    for obj in analysis.objections:
                        if isinstance(obj, str):
                            key = obj
                        elif isinstance(obj, dict):
                            key = obj.get("type", "unknown")
                        else:
                            continue
                        csr_objection_counts[key] = csr_objection_counts.get(key, 0) + 1
            
            # Top 3 objections for this CSR
            sorted_csr_objections = sorted(csr_objection_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            csr_top_objections: List[ObjectionSummary] = []
            
            for key, count in sorted_csr_objections:
                label = key.replace("_", " ").title()
                occurrence_rate = count / len(csr_analyses) if csr_analyses else None
                
                csr_top_objections.append(ObjectionSummary(
                    objection_key=key,
                    objection_label=label,
                    occurrence_count=count,
                    occurrence_rate=occurrence_rate,
                    occurrence_rate_over_qualified_unbooked=None  # Can compute if needed
                ))
            
            coaching_opportunities.append(CSRAgentCoachingSummary(
                csr_id=csr_id,
                csr_name=csr_name,
                total_calls=csr_metrics.total_calls,
                qualified_calls=csr_metrics.qualified_calls,
                booked_calls=csr_metrics.booked_calls,
                booking_rate=csr_metrics.booking_rate,
                sop_compliance_score=csr_metrics.avg_compliance_score,
                top_objections=csr_top_objections
            ))
        
        # Sort by worst booking rate (lowest first)
        coaching_opportunities.sort(key=lambda x: x.booking_rate if x.booking_rate is not None else 1.0)
        
        return ExecCSRDashboardMetrics(
            overview=overview,
            booking_rate_trend=booking_rate_trend if booking_rate_trend else None,
            unbooked_calls_count=unbooked_calls_count if unbooked_calls_count > 0 else None,
            top_objections=top_objections,
            coaching_opportunities=coaching_opportunities
        )
    
    async def get_exec_missed_call_recovery_metrics(
        self,
        *,
        tenant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> ExecMissedCallRecoveryMetrics:
        """
        Compute executive missed call recovery metrics (company-wide).
        
        Args:
            tenant_id: Company/tenant ID
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
        
        Returns:
            ExecMissedCallRecoveryMetrics with company-wide missed call recovery stats
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Total missed calls (company-wide)
        total_missed_calls = self.db.query(Call).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.missed_call == True,
            Call.created_at >= date_from,
            Call.created_at <= date_to
        ).count()
        
        # Get missed call lead IDs
        missed_calls = self.db.query(Call).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.missed_call == True,
            Call.created_at >= date_from,
            Call.created_at <= date_to
        ).all()
        
        missed_call_lead_ids = [call.lead_id for call in missed_calls if call.lead_id]
        missed_call_ids = [call.call_id for call in missed_calls]
        
        # Count saved calls using Shunya (follow-up calls with booking_status == "booked")
        if missed_call_lead_ids:
            # Get all calls for these leads (including follow-ups)
            followup_calls = self.db.query(Call).filter(
                Call.lead_id.in_(missed_call_lead_ids),
                Call.company_id == tenant_id,
                Call.created_at >= date_from,
                Call.created_at <= date_to
            ).all()
            
            followup_call_ids = [call.call_id for call in followup_calls]
            
            # Get analyses for follow-up calls
            followup_analyses = self.db.query(CallAnalysis).filter(
                CallAnalysis.call_id.in_(followup_call_ids),
                CallAnalysis.tenant_id == tenant_id
            ).all()
            
            # Count saved: missed calls where Shunya says booking_status == "booked" in follow-up
            saved_call_lead_ids = set()
            for analysis in followup_analyses:
                if analysis.booking_status == BookingStatus.BOOKED.value:
                    # Find the lead_id for this call
                    for call in followup_calls:
                        if call.call_id == analysis.call_id and call.lead_id:
                            saved_call_lead_ids.add(call.lead_id)
                            break
            
            total_saved_calls = len(saved_call_lead_ids)
            
            # Count saved by Otto (leads with source = "ai_recovery")
            total_saved_by_otto = 0
            for lead_id in saved_call_lead_ids:
                lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
                if lead and lead.source in [LeadSource.INBOUND_CALL.value, "ai_recovery"]:
                    total_saved_by_otto += 1
        else:
            total_saved_calls = 0
            total_saved_by_otto = 0
        
        # Count booked/pending/dead leads (using Shunya fields)
        booked_leads_count = 0
        pending_leads_count = 0
        dead_leads_count = 0
        
        if missed_call_lead_ids:
            # Get all calls for these leads
            all_lead_calls = self.db.query(Call).filter(
                Call.lead_id.in_(missed_call_lead_ids),
                Call.company_id == tenant_id
            ).all()
            
            lead_call_ids = [call.call_id for call in all_lead_calls]
            lead_analyses = self.db.query(CallAnalysis).filter(
                CallAnalysis.call_id.in_(lead_call_ids),
                CallAnalysis.tenant_id == tenant_id
            ).all()
            
            # Group by lead_id
            lead_analyses_by_lead: dict[str, List[CallAnalysis]] = {}
            for call in all_lead_calls:
                if call.lead_id not in lead_analyses_by_lead:
                    lead_analyses_by_lead[call.lead_id] = []
                for analysis in lead_analyses:
                    if analysis.call_id == call.call_id:
                        lead_analyses_by_lead[call.lead_id].append(analysis)
            
            # Categorize each lead
            for lead_id in missed_call_lead_ids:
                analyses_for_lead = lead_analyses_by_lead.get(lead_id, [])
                
                # Check Shunya's booking_status
                is_booked = any(
                    analysis.booking_status == BookingStatus.BOOKED.value
                    for analysis in analyses_for_lead
                )
                
                # Check if dead (using Lead.status for lifecycle, not booking semantics)
                lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
                is_dead = lead and lead.status in [
                    LeadStatus.ABANDONED.value,
                    LeadStatus.CLOSED_LOST.value,
                    LeadStatus.DORMANT.value
                ]
                
                if is_booked:
                    booked_leads_count += 1
                elif is_dead:
                    dead_leads_count += 1
                else:
                    pending_leads_count += 1
        
        return ExecMissedCallRecoveryMetrics(
            total_missed_calls=total_missed_calls if total_missed_calls > 0 else None,
            total_saved_calls=total_saved_calls if total_saved_calls > 0 else None,
            total_saved_by_otto=total_saved_by_otto if total_saved_by_otto > 0 else None,
            booked_leads_count=booked_leads_count if booked_leads_count > 0 else None,
            pending_leads_count=pending_leads_count if pending_leads_count > 0 else None,
            dead_leads_count=dead_leads_count if dead_leads_count > 0 else None
        )
    
    async def get_exec_sales_team_dashboard_metrics(
        self,
        *,
        tenant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> ExecSalesTeamDashboardMetrics:
        """
        Compute executive sales team dashboard metrics.
        
        Args:
            tenant_id: Company/tenant ID
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
        
        Returns:
            ExecSalesTeamDashboardMetrics with overview, team stats, reps, and objections
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Overview: reuse existing exec sales metrics
        overview = await self.get_exec_sales_metrics(
            tenant_id=tenant_id,
            date_from=date_from,
            date_to=date_to
        )
        
        # Team stats
        # Total conversations (RecordingAnalysis count)
        total_conversations = self.db.query(RecordingAnalysis).join(
            Appointment, RecordingAnalysis.appointment_id == Appointment.id
        ).filter(
            RecordingAnalysis.company_id == tenant_id,
            Appointment.scheduled_start >= date_from,
            Appointment.scheduled_start <= date_to
        ).count()
        
        # Average recording duration
        recording_sessions = self.db.query(RecordingSession).filter(
            RecordingSession.company_id == tenant_id,
            RecordingSession.started_at >= date_from,
            RecordingSession.started_at <= date_to,
            RecordingSession.audio_duration_seconds.isnot(None)
        ).all()
        
        durations = [rs.audio_duration_seconds for rs in recording_sessions if rs.audio_duration_seconds]
        avg_recording_duration_seconds = sum(durations) / len(durations) if durations else None
        
        # Follow-up rate (leads with more than one sales interaction)
        # TODO: This requires tracking interactions per lead - may need to leave as None
        followup_rate = None  # TODO: Implement when we have interaction tracking
        
        # Follow-up win rate and first-touch win rate
        # TODO: Requires tracking first vs follow-up interactions - may need to leave as None
        followup_win_rate = None  # TODO: Implement when we have interaction tracking
        first_touch_win_rate = None  # TODO: Implement when we have interaction tracking
        
        team_stats = SalesTeamStatsMetrics(
            total_conversations=total_conversations if total_conversations > 0 else None,
            avg_recording_duration_seconds=avg_recording_duration_seconds,
            followup_rate=followup_rate,
            followup_win_rate=followup_win_rate,
            first_touch_win_rate=first_touch_win_rate,
            team_win_rate=overview.team_win_rate
        )
        
        # Per-rep summaries
        # Get all reps
        reps = self.db.query(SalesRep).filter(SalesRep.company_id == tenant_id).all()
        
        rep_summaries: List[SalesRepRecordingSummary] = []
        
        for rep in reps:
            # Get rep metrics
            rep_metrics = await self.get_sales_rep_overview_metrics(
                tenant_id=tenant_id,
                rep_id=rep.user_id,
                date_from=date_from,
                date_to=date_to
            )
            
            # Get recording sessions for this rep
            rep_recordings = self.db.query(RecordingSession).filter(
                RecordingSession.company_id == tenant_id,
                RecordingSession.rep_id == rep.user_id,
                RecordingSession.started_at >= date_from,
                RecordingSession.started_at <= date_to
            ).all()
            
            total_recordings = len(rep_recordings)
            total_recording_hours = sum(
                (rs.audio_duration_seconds or 0) / 3600.0
                for rs in rep_recordings
            )
            
            # Get rep name
            rep_name = None
            user = self.db.query(User).filter(User.id == rep.user_id).first()
            if user:
                rep_name = user.name
            
            # Get compliance scores from RecordingAnalysis
            rep_appointment_ids = [rs.appointment_id for rs in rep_recordings if rs.appointment_id]
            rep_analyses = self.db.query(RecordingAnalysis).filter(
                RecordingAnalysis.appointment_id.in_(rep_appointment_ids),
                RecordingAnalysis.company_id == tenant_id
            ).all()
            
            compliance_scores = [
                analysis.sop_compliance_score
                for analysis in rep_analyses
                if analysis.sop_compliance_score is not None
            ]
            
            avg_sop_compliance = sum(compliance_scores) / len(compliance_scores) if compliance_scores else None
            sales_compliance_score = avg_sop_compliance  # Same as SOP for now
            
            rep_summaries.append(SalesRepRecordingSummary(
                rep_id=rep.user_id,
                rep_name=rep_name,
                total_recordings=total_recordings,
                total_recording_hours=total_recording_hours,
                win_rate=rep_metrics.win_rate,
                auto_usage_hours=None,  # TODO: Track auto usage hours
                sop_compliance_score=avg_sop_compliance,
                sales_compliance_score=sales_compliance_score
            ))
        
        # Top objections across all sales reps (from RecordingAnalysis)
        all_sales_analyses = self.db.query(RecordingAnalysis).join(
            Appointment, RecordingAnalysis.appointment_id == Appointment.id
        ).filter(
            RecordingAnalysis.company_id == tenant_id,
            Appointment.scheduled_start >= date_from,
            Appointment.scheduled_start <= date_to
        ).all()
        
        sales_objection_counts: dict[str, int] = {}
        total_sales_conversations = len(all_sales_analyses)
        
        for analysis in all_sales_analyses:
            if analysis.objections and isinstance(analysis.objections, list):
                for obj in analysis.objections:
                    if isinstance(obj, str):
                        key = obj
                        label = obj.replace("_", " ").title()
                    elif isinstance(obj, dict):
                        key = obj.get("type", "unknown")
                        label = obj.get("label", key.replace("_", " ").title())
                    else:
                        continue
                    
                    sales_objection_counts[key] = sales_objection_counts.get(key, 0) + 1
        
        # Sort and take top 5
        sorted_sales_objections = sorted(sales_objection_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        top_objections: List[ObjectionSummary] = []
        for key, count in sorted_sales_objections:
            # Find label
            label = key.replace("_", " ").title()
            for analysis in all_sales_analyses:
                if analysis.objections and isinstance(analysis.objections, list):
                    for obj in analysis.objections:
                        if isinstance(obj, dict) and obj.get("type") == key:
                            label = obj.get("label", label)
                            break
                    if label != key.replace("_", " ").title():
                        break
            
            occurrence_rate = count / total_sales_conversations if total_sales_conversations > 0 else None
            
            top_objections.append(ObjectionSummary(
                objection_key=key,
                objection_label=label,
                occurrence_count=count,
                occurrence_rate=occurrence_rate,
                occurrence_rate_over_qualified_unbooked=None  # Not applicable for sales
            ))
        
        return ExecSalesTeamDashboardMetrics(
            overview=overview,
            team_stats=team_stats,
            reps=rep_summaries,
            top_objections=top_objections
        )
    
    # CSR Self-Scoped Methods
    
    async def get_csr_overview_self(
        self,
        *,
        csr_user_id: str,
        tenant_id: str,
        start: datetime,
        end: datetime,
    ) -> CSROverviewSelfResponse:
        """
        Get CSR overview metrics for self (includes top_missed_booking_reason).
        
        Args:
            csr_user_id: CSR user ID (from auth)
            tenant_id: Company/tenant ID
            start: Start datetime
            end: End datetime
        
        Returns:
            CSROverviewSelfResponse with all CSR metrics plus top_missed_booking_reason
        """
        # Get base metrics
        base_metrics = await self.get_csr_overview_metrics(
            csr_user_id=csr_user_id,
            tenant_id=tenant_id,
            start=start,
            end=end
        )
        
        # top_missed_booking_reason is already in base_metrics.top_reason_for_missed_bookings
        return CSROverviewSelfResponse(
            total_calls=base_metrics.total_calls,
            qualified_calls=base_metrics.qualified_calls,
            qualified_rate=base_metrics.qualified_rate,
            booked_calls=base_metrics.booked_calls,
            booking_rate=base_metrics.booking_rate,
            service_not_offered_calls=base_metrics.service_not_offered_calls,
            service_not_offered_rate=base_metrics.service_not_offered_rate,
            avg_objections_per_qualified_call=base_metrics.avg_objections_per_qualified_call,
            qualified_but_unbooked_calls=base_metrics.qualified_but_unbooked_calls,
            avg_compliance_score=base_metrics.avg_compliance_score,
            open_followups=base_metrics.open_followups,
            overdue_followups=base_metrics.overdue_followups,
            top_reason_for_missed_bookings=base_metrics.top_reason_for_missed_bookings,
            pending_leads_count=base_metrics.pending_leads_count,
            top_missed_booking_reason=base_metrics.top_reason_for_missed_bookings
        )
    
    async def get_csr_booking_trend_self(
        self,
        *,
        csr_user_id: str,
        tenant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        granularity: Literal["day", "week", "month"] = "month",
    ) -> CSRBookingTrendSelfResponse:
        """
        Get CSR booking trend for self with summary.
        
        Args:
            csr_user_id: CSR user ID (from auth)
            tenant_id: Company/tenant ID
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
            granularity: Time bucket size (day, week, month)
        
        Returns:
            CSRBookingTrendSelfResponse with summary and trend points
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Get all CSR calls
        all_calls = self.db.query(Call).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.owner_id == csr_user_id,  # TODO: If owner_id not available, use fallback
            Call.created_at >= date_from,
            Call.created_at <= date_to
        ).all()
        
        call_ids = [call.call_id for call in all_calls]
        analyses = self.db.query(CallAnalysis).filter(
            CallAnalysis.call_id.in_(call_ids),
            CallAnalysis.tenant_id == tenant_id
        ).all()
        
        analysis_by_call_id = {analysis.call_id: analysis for analysis in analyses}
        
        # Compute summary (all from Shunya)
        total_leads = len(all_calls)
        total_qualified_leads = 0
        total_booked_calls = 0
        
        for call in all_calls:
            analysis = analysis_by_call_id.get(call.call_id)
            if analysis:
                # QUALIFICATION: Only from Shunya lead_quality
                lead_quality = analysis.lead_quality
                if lead_quality and lead_quality.lower() in ("hot", "warm", "cold", "qualified"):
                    total_qualified_leads += 1
                
                # BOOKING: Only from Shunya booking_status
                if analysis.booking_status == BookingStatus.BOOKED.value:
                    total_booked_calls += 1
        
        current_booking_rate = total_booked_calls / total_qualified_leads if total_qualified_leads > 0 else None
        
        summary = CSRBookingTrendSummary(
            total_leads=total_leads,
            total_qualified_leads=total_qualified_leads,
            total_booked_calls=total_booked_calls,
            current_booking_rate=current_booking_rate
        )
        
        # Compute trend points
        trend_points: List[CSRBookingTrendPointTimestamp] = []
        current = date_from
        
        while current <= date_to:
            if granularity == "day":
                period_end = current + timedelta(days=1)
            elif granularity == "week":
                period_end = current + timedelta(weeks=1)
            else:  # month
                period_end = current + timedelta(days=30)
            
            period_calls = [c for c in all_calls if current <= c.created_at < period_end]
            
            period_qualified = 0
            period_booked = 0
            
            for call in period_calls:
                analysis = analysis_by_call_id.get(call.call_id)
                if analysis:
                    lead_quality = analysis.lead_quality
                    if lead_quality and lead_quality.lower() in ("hot", "warm", "cold", "qualified"):
                        period_qualified += 1
                    
                    if analysis.booking_status == BookingStatus.BOOKED.value:
                        period_booked += 1
            
            booking_rate = period_booked / period_qualified if period_qualified > 0 else None
            
            trend_points.append(CSRBookingTrendPointTimestamp(
                timestamp=current.strftime("%Y-%m-%d"),
                value=booking_rate
            ))
            
            current = period_end
        
        return CSRBookingTrendSelfResponse(
            summary=summary,
            booking_rate_trend=trend_points
        )
    
    async def get_csr_unbooked_calls_self(
        self,
        *,
        csr_user_id: str,
        tenant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> UnbookedCallsSelfResponse:
        """
        Get paginated unbooked calls for CSR self.
        
        Unbooked = anything where Shunya says NOT booking_status == "booked".
        
        Args:
            csr_user_id: CSR user ID (from auth)
            tenant_id: Company/tenant ID
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
            page: Page number (1-indexed)
            page_size: Page size
        
        Returns:
            UnbookedCallsSelfResponse with paginated unbooked calls
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Query unbooked calls (Shunya says NOT booked)
        base_query = self.db.query(Call).join(
            CallAnalysis, Call.call_id == CallAnalysis.call_id, isouter=True
        ).join(
            ContactCard, Call.contact_card_id == ContactCard.id, isouter=True
        ).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.owner_id == csr_user_id,  # TODO: If owner_id not available, use fallback
            Call.created_at >= date_from,
            Call.created_at <= date_to
        )
        
        # Filter: unbooked = booking_status != "booked" OR no analysis
        unbooked_query = base_query.filter(
            or_(
                CallAnalysis.booking_status != BookingStatus.BOOKED.value,
                CallAnalysis.booking_status.is_(None)
            )
        )
        
        # Get total count
        total = unbooked_query.count()
        
        # Paginate
        calls = unbooked_query.order_by(Call.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        # Get analyses for these calls
        call_ids = [call.call_id for call in calls]
        analyses = self.db.query(CallAnalysis).filter(
            CallAnalysis.call_id.in_(call_ids),
            CallAnalysis.tenant_id == tenant_id
        ).all()
        
        analysis_by_call_id = {analysis.call_id: analysis for analysis in analyses}
        
        items: List[UnbookedCallItem] = []
        for call in calls:
            analysis = analysis_by_call_id.get(call.call_id)
            
            # Get customer name and phone
            customer_name = None
            phone = None
            if call.contact_card:
                customer_name = f"{call.contact_card.first_name or ''} {call.contact_card.last_name or ''}".strip() or None
                phone = call.contact_card.primary_phone
            
            # Determine qualified from Shunya
            qualified = None
            if analysis and analysis.lead_quality:
                qualified = analysis.lead_quality.lower() in ("hot", "warm", "cold", "qualified")
            
            # Get booking status from Shunya
            booking_status = analysis.booking_status if analysis else "not_analyzed"
            
            items.append(UnbookedCallItem(
                call_id=call.call_id,
                customer_name=customer_name,
                phone=phone,
                booking_status=booking_status or "not_analyzed",
                qualified=qualified,
                status="pending",
                last_contacted_at=call.created_at.isoformat() if call.created_at else None
            ))
        
        return UnbookedCallsSelfResponse(
            items=items,
            page=page,
            page_size=page_size,
            total=total
        )
    
    async def get_csr_objections_self(
        self,
        *,
        csr_user_id: str,
        tenant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> CSRObjectionsSelfResponse:
        """
        Get CSR objections for self view.
        
        Uses Shunya CallAnalysis.objections + booking/qualification fields.
        
        Args:
            csr_user_id: CSR user ID (from auth)
            tenant_id: Company/tenant ID
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
        
        Returns:
            CSRObjectionsSelfResponse with top and all objections
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Get CSR calls
        calls = self.db.query(Call).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.owner_id == csr_user_id,  # TODO: If owner_id not available, use fallback
            Call.created_at >= date_from,
            Call.created_at <= date_to
        ).all()
        
        call_ids = [call.call_id for call in calls]
        analyses = self.db.query(CallAnalysis).filter(
            CallAnalysis.call_id.in_(call_ids),
            CallAnalysis.tenant_id == tenant_id
        ).all()
        
        # Count objections and qualified_unbooked
        objection_counts: dict[str, int] = {}
        qualified_unbooked_counts: dict[str, int] = {}
        total_calls = len(analyses)
        qualified_unbooked_calls = 0
        
        for analysis in analyses:
            # Check if qualified but unbooked
            is_qualified_unbooked = False
            if analysis.lead_quality and analysis.lead_quality.lower() in ("hot", "warm", "cold", "qualified"):
                if analysis.booking_status and analysis.booking_status != BookingStatus.BOOKED.value:
                    is_qualified_unbooked = True
                    qualified_unbooked_calls += 1
            
            # Count objections (from Shunya)
            if analysis.objections and isinstance(analysis.objections, list):
                for obj in analysis.objections:
                    if isinstance(obj, str):
                        key = obj
                    elif isinstance(obj, dict):
                        key = obj.get("type", "unknown")
                    else:
                        continue
                    
                    objection_counts[key] = objection_counts.get(key, 0) + 1
                    if is_qualified_unbooked:
                        qualified_unbooked_counts[key] = qualified_unbooked_counts.get(key, 0) + 1
        
        # Build objection items
        all_objections: List[CSRObjectionSelfItem] = []
        for objection, count in sorted(objection_counts.items(), key=lambda x: x[1], reverse=True):
            occurrence_rate = count / total_calls if total_calls > 0 else 0.0
            qualified_unbooked_rate = qualified_unbooked_counts.get(objection, 0) / qualified_unbooked_calls if qualified_unbooked_calls > 0 else None
            
            all_objections.append(CSRObjectionSelfItem(
                objection=objection,
                occurrence_count=count,
                occurrence_rate=occurrence_rate,
                qualified_unbooked_occurrence_rate=qualified_unbooked_rate
            ))
        
        # Top objections (top 5)
        top_objections = all_objections[:5]
        
        return CSRObjectionsSelfResponse(
            top_objections=top_objections,
            all_objections=all_objections
        )
    
    async def get_csr_calls_by_objection_self(
        self,
        *,
        csr_user_id: str,
        tenant_id: str,
        objection: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> CallsByObjectionSelfResponse:
        """
        Get paginated calls filtered by objection for CSR self.
        
        Filters calls where Shunya objections list contains that objection string.
        
        Args:
            csr_user_id: CSR user ID (from auth)
            tenant_id: Company/tenant ID
            objection: Objection key to filter by
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
            page: Page number (1-indexed)
            page_size: Page size
        
        Returns:
            CallsByObjectionSelfResponse with paginated calls
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Get CSR calls
        calls = self.db.query(Call).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.owner_id == csr_user_id,  # TODO: If owner_id not available, use fallback
            Call.created_at >= date_from,
            Call.created_at <= date_to
        ).all()
        
        call_ids = [call.call_id for call in calls]
        analyses = self.db.query(CallAnalysis).filter(
            CallAnalysis.call_id.in_(call_ids),
            CallAnalysis.tenant_id == tenant_id
        ).all()
        
        # Filter calls that have this objection (from Shunya)
        matching_call_ids = set()
        for analysis in analyses:
            if analysis.objections and isinstance(analysis.objections, list):
                for obj in analysis.objections:
                    obj_key = obj if isinstance(obj, str) else obj.get("type", "")
                    if objection.lower() in obj_key.lower() or obj_key.lower() in objection.lower():
                        matching_call_ids.add(analysis.call_id)
                        break
        
        # Get matching calls
        matching_calls = [c for c in calls if c.call_id in matching_call_ids]
        
        # Get total
        total = len(matching_calls)
        
        # Paginate
        paginated_calls = matching_calls[(page - 1) * page_size:page * page_size]
        
        # Get analyses for paginated calls
        paginated_call_ids = [call.call_id for call in paginated_calls]
        paginated_analyses = {a.call_id: a for a in analyses if a.call_id in paginated_call_ids}
        
        items: List[CallByObjectionItem] = []
        for call in paginated_calls:
            analysis = paginated_analyses.get(call.call_id)
            
            # Get customer name
            customer_name = None
            if call.contact_card:
                customer_name = f"{call.contact_card.first_name or ''} {call.contact_card.last_name or ''}".strip() or None
            
            # Get duration (from Call model - non-Shunya)
            duration_seconds = None
            if call.duration:
                duration_seconds = int(call.duration.total_seconds())
            
            # Get audio URL (from Call model - non-Shunya)
            audio_url = call.audio_url
            
            items.append(CallByObjectionItem(
                call_id=call.call_id,
                customer_name=customer_name,
                started_at=call.created_at.isoformat() if call.created_at else "",
                duration_seconds=duration_seconds,
                booking_status=analysis.booking_status if analysis else None,
                audio_url=audio_url
            ))
        
        return CallsByObjectionSelfResponse(
            items=items,
            page=page,
            page_size=page_size,
            total=total
        )
    
    async def get_csr_missed_calls_self(
        self,
        *,
        csr_user_id: str,
        tenant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> CSRMissedCallsSelfResponse:
        """
        Get CSR missed calls metrics for self.
        
        Wrapper using existing missed-call logic but scoped to that CSR.
        
        Args:
            csr_user_id: CSR user ID (from auth)
            tenant_id: Company/tenant ID
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
        
        Returns:
            CSRMissedCallsSelfResponse with missed call metrics
        """
        # Reuse existing method
        recovery = await self.get_csr_missed_call_recovery(
            tenant_id=tenant_id,
            csr_user_id=csr_user_id,
            date_from=date_from,
            date_to=date_to
        )
        
        return CSRMissedCallsSelfResponse(
            total_missed_calls=recovery.metrics.missed_calls_count,
            total_saved_calls=recovery.metrics.saved_calls_count,
            total_saved_by_otto=recovery.metrics.saved_calls_via_auto_rescue_count,
            booked_leads_count=len(recovery.booked_leads),
            pending_leads_count=len(recovery.pending_leads),
            dead_leads_count=len(recovery.dead_leads)
        )
    
    async def get_csr_missed_leads_self(
        self,
        *,
        csr_user_id: str,
        tenant_id: str,
        status: Optional[Literal["booked", "pending", "dead"]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> MissedLeadsSelfResponse:
        """
        Get paginated missed leads for CSR self.
        
        Uses Shunya booking/outcome for status, plus Otto's call/twilio interaction counts for attempt_count.
        
        Args:
            csr_user_id: CSR user ID (from auth)
            tenant_id: Company/tenant ID
            status: Filter by status (booked, pending, dead)
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
            page: Page number (1-indexed)
            page_size: Page size
        
        Returns:
            MissedLeadsSelfResponse with paginated missed leads
        """
        if date_to is None:
            date_to = datetime.utcnow()
        if date_from is None:
            date_from = date_to - timedelta(days=30)
        
        # Get missed calls for this CSR
        missed_calls = self.db.query(Call).filter(
            Call.company_id == tenant_id,
            Call.call_type == CallType.CSR_CALL.value,
            Call.owner_id == csr_user_id,  # TODO: If owner_id not available, use fallback
            Call.missed_call == True,
            Call.created_at >= date_from,
            Call.created_at <= date_to
        ).all()
        
        missed_call_lead_ids = [call.lead_id for call in missed_calls if call.lead_id]
        
        if not missed_call_lead_ids:
            return MissedLeadsSelfResponse(items=[], page=page, page_size=page_size, total=0)
        
        # Get leads
        leads_query = self.db.query(Lead).filter(
            Lead.id.in_(missed_call_lead_ids),
            Lead.company_id == tenant_id
        )
        
        # Get all calls for these leads to check Shunya booking status
        all_lead_calls = self.db.query(Call).filter(
            Call.lead_id.in_(missed_call_lead_ids),
            Call.company_id == tenant_id
        ).all()
        
        lead_call_ids = [call.call_id for call in all_lead_calls]
        lead_analyses = self.db.query(CallAnalysis).filter(
            CallAnalysis.call_id.in_(lead_call_ids),
            CallAnalysis.tenant_id == tenant_id
        ).all()
        
        # Group analyses by lead_id
        analyses_by_lead: dict[str, List[CallAnalysis]] = {}
        for call in all_lead_calls:
            if call.lead_id not in analyses_by_lead:
                analyses_by_lead[call.lead_id] = []
            for analysis in lead_analyses:
                if analysis.call_id == call.call_id:
                    analyses_by_lead[call.lead_id].append(analysis)
        
        # Filter leads by status (from Shunya)
        filtered_leads: List[Lead] = []
        for lead in leads_query.all():
            analyses_for_lead = analyses_by_lead.get(lead.id, [])
            
            # Determine status from Shunya
            is_booked = any(
                a.booking_status == BookingStatus.BOOKED.value
                for a in analyses_for_lead
            )
            is_dead = lead.status in [
                LeadStatus.ABANDONED.value,
                LeadStatus.CLOSED_LOST.value,
                LeadStatus.DORMANT.value
            ]
            
            if is_booked:
                lead_status = "booked"
            elif is_dead:
                lead_status = "dead"
            else:
                lead_status = "pending"
            
            # Apply status filter
            if status is None or lead_status == status:
                filtered_leads.append(lead)
        
        # Get total
        total = len(filtered_leads)
        
        # Paginate
        paginated_leads = filtered_leads[(page - 1) * page_size:page * page_size]
        
        # Get tasks for next_action
        lead_ids = [lead.id for lead in paginated_leads]
        tasks = self.db.query(Task).filter(
            Task.lead_id.in_(lead_ids),
            Task.company_id == tenant_id,
            Task.status.in_([TaskStatus.OPEN.value, TaskStatus.PENDING.value])
        ).all()
        
        tasks_by_lead: dict[str, List[Task]] = {}
        for task in tasks:
            if task.lead_id not in tasks_by_lead:
                tasks_by_lead[task.lead_id] = []
            tasks_by_lead[task.lead_id].append(task)
        
        items: List[MissedLeadItem] = []
        for lead in paginated_leads:
            analyses_for_lead = analyses_by_lead.get(lead.id, [])
            
            # Determine status from Shunya
            is_booked = any(
                a.booking_status == BookingStatus.BOOKED.value
                for a in analyses_for_lead
            )
            is_dead = lead.status in [
                LeadStatus.ABANDONED.value,
                LeadStatus.CLOSED_LOST.value,
                LeadStatus.DORMANT.value
            ]
            
            if is_booked:
                lead_status = "booked"
            elif is_dead:
                lead_status = "dead"
            else:
                lead_status = "pending"
            
            # Get customer name
            customer_name = None
            if lead.contact_card:
                customer_name = f"{lead.contact_card.first_name or ''} {lead.contact_card.last_name or ''}".strip() or None
            
            # Determine source (missed_call or missed_text)
            source = "missed_call"  # Default, can be refined based on call type
            
            # Get next action from tasks
            lead_tasks = tasks_by_lead.get(lead.id, [])
            next_action = None
            next_action_due_at = None
            if lead_tasks:
                # Get first open task
                open_task = next((t for t in lead_tasks if t.status in [TaskStatus.OPEN.value, TaskStatus.PENDING.value]), None)
                if open_task:
                    next_action = open_task.description
                    next_action_due_at = open_task.due_at.isoformat() if open_task.due_at else None
            
            # Get attempt count (from Call count - non-Shunya, from CallRail/Twilio)
            attempt_count = len([c for c in all_lead_calls if c.lead_id == lead.id])
            
            items.append(MissedLeadItem(
                lead_id=lead.id,
                customer_name=customer_name,
                status=lead_status,
                source=source,
                last_contacted_at=lead.last_contacted_at.isoformat() if lead.last_contacted_at else None,
                next_action=next_action,
                next_action_due_at=next_action_due_at,
                attempt_count=attempt_count
            ))
        
        return MissedLeadsSelfResponse(
            items=items,
            page=page,
            page_size=page_size,
            total=total
        )
    
    # Exec Methods
    
    async def get_ride_along_appointments(
        self,
        *,
        tenant_id: str,
        date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> RideAlongAppointmentsResponse:
        """
        Get paginated ride-along appointments for exec view.
        
        Status/outcome must be derived from Shunya RecordingAnalysis.outcome + Otto local appointment state.
        
        Args:
            tenant_id: Company/tenant ID
            date: Date to filter by (optional, defaults to today)
            page: Page number (1-indexed)
            page_size: Page size
        
        Returns:
            RideAlongAppointmentsResponse with paginated appointments
        """
        if date is None:
            date = datetime.utcnow().date()
        
        # Query appointments for this date
        appointments_query = self.db.query(Appointment).filter(
            Appointment.company_id == tenant_id,
            Appointment.scheduled_start >= datetime.combine(date, datetime.min.time()),
            Appointment.scheduled_start < datetime.combine(date, datetime.min.time()) + timedelta(days=1)
        )
        
        # Get total
        total = appointments_query.count()
        
        # Paginate
        appointments = appointments_query.order_by(Appointment.scheduled_start.asc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        appointment_ids = [apt.id for apt in appointments]
        
        # Get RecordingAnalysis for these appointments (Shunya)
        analyses = self.db.query(RecordingAnalysis).filter(
            RecordingAnalysis.appointment_id.in_(appointment_ids),
            RecordingAnalysis.company_id == tenant_id
        ).all()
        
        analysis_by_appointment_id = {analysis.appointment_id: analysis for analysis in analyses}
        
        # Get recording sessions for SOP compliance scores
        recording_sessions = self.db.query(RecordingSession).filter(
            RecordingSession.appointment_id.in_(appointment_ids),
            RecordingSession.company_id == tenant_id
        ).all()
        
        session_by_appointment_id = {rs.appointment_id: rs for rs in recording_sessions}
        
        items: List[RideAlongAppointmentItem] = []
        for appointment in appointments:
            analysis = analysis_by_appointment_id.get(appointment.id)
            session = session_by_appointment_id.get(appointment.id)
            
            # Get customer name
            customer_name = None
            if appointment.contact_card:
                customer_name = f"{appointment.contact_card.first_name or ''} {appointment.contact_card.last_name or ''}".strip() or None
            
            # Get rep name
            rep_name = None
            if appointment.assigned_rep_id:
                user = self.db.query(User).filter(User.id == appointment.assigned_rep_id).first()
                if user:
                    rep_name = user.name
            
            # Determine status from Shunya + appointment state
            # Status: "won", "in_progress", "not_started", "rejected"
            if analysis:
                # Ensure outcome is a string (handle enum values if any)
                outcome = str(analysis.outcome) if analysis.outcome else None
                if outcome and outcome.lower() == "won":
                    status = "won"
                elif outcome and outcome.lower() == "lost":
                    status = "rejected"
                elif outcome and outcome.lower() == "pending":
                    status = "in_progress"
                else:
                    # Check appointment status
                    if appointment.status == AppointmentStatus.COMPLETED.value:
                        status = "in_progress"
                    elif appointment.status in [AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value]:
                        status = "not_started"
                    else:
                        status = "in_progress"
            else:
                # No Shunya analysis yet
                if appointment.status == AppointmentStatus.COMPLETED.value:
                    status = "in_progress"
                elif appointment.status in [AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value]:
                    status = "not_started"
                else:
                    status = "in_progress"
            
            # Get outcome from Shunya
            outcome_value = None
            if analysis and analysis.outcome:
                # Ensure outcome is a string (handle enum values if any)
                outcome_str = str(analysis.outcome).lower() if analysis.outcome else None
                if outcome_str == "won":
                    outcome_value = "won"
                elif outcome_str == "lost":
                    outcome_value = "lost"
                elif outcome_str == "pending":
                    outcome_value = "pending"
            
            # Get SOP compliance scores (from Shunya RecordingAnalysis)
            sop_scores = {}
            if analysis:
                # TODO: Extract phase-specific scores from meeting_segments or compliance fields
                # For now, use overall compliance score
                if analysis.sop_compliance_score is not None:
                    sop_scores["overall"] = analysis.sop_compliance_score
            
            # Build booking path (simplified - TODO: track actual path)
            booking_path = []
            if appointment.lead_id:
                # Check if there was a CSR call first
                csr_calls = self.db.query(Call).filter(
                    Call.lead_id == appointment.lead_id,
                    Call.company_id == tenant_id,
                    Call.call_type == CallType.CSR_CALL.value
                ).order_by(Call.created_at.asc()).all()
                
                if csr_calls:
                    booking_path.append("inbound_call_csr")
                    
                    # Check for follow-up calls
                    if len(csr_calls) > 1:
                        booking_path.append("csr_followup_call")
                
                booking_path.append("appointment_booked")
            
            items.append(RideAlongAppointmentItem(
                appointment_id=str(appointment.id),
                customer_name=customer_name,
                scheduled_at=appointment.scheduled_start.isoformat() if appointment.scheduled_start else "",
                rep_id=appointment.assigned_rep_id,
                rep_name=rep_name,
                status=status,
                outcome=outcome_value,
                sop_compliance_scores=sop_scores,
                booking_path=booking_path
            ))
        
        return RideAlongAppointmentsResponse(
            items=items,
            page=page,
            page_size=page_size,
            total=total
        )
    
    async def get_sales_opportunities(
        self,
        *,
        tenant_id: str,
    ) -> SalesOpportunitiesResponse:
        """
        Get sales opportunities per rep.
        
        Uses Task + Shunya booking/outcome to identify pending leads per rep.
        
        Args:
            tenant_id: Company/tenant ID
        
        Returns:
            SalesOpportunitiesResponse with opportunities per rep
        """
        # Get all sales reps
        reps = self.db.query(SalesRep).filter(SalesRep.company_id == tenant_id).all()
        
        items: List[SalesOpportunityItem] = []
        
        for rep in reps:
            # Get appointments assigned to this rep
            appointments = self.db.query(Appointment).filter(
                Appointment.company_id == tenant_id,
                Appointment.assigned_rep_id == rep.user_id
            ).all()
            
            appointment_ids = [apt.id for apt in appointments]
            lead_ids = [apt.lead_id for apt in appointments if apt.lead_id]
            
            # Get RecordingAnalysis for these appointments (Shunya)
            analyses = self.db.query(RecordingAnalysis).filter(
                RecordingAnalysis.appointment_id.in_(appointment_ids),
                RecordingAnalysis.company_id == tenant_id
            ).all()
            
            # Count pending leads (not won, not lost, not dead)
            pending_leads_count = 0
            for lead_id in lead_ids:
                if not lead_id:
                    continue
                
                # Check Shunya outcome
                lead_analyses = [a for a in analyses if a.appointment_id in appointment_ids]
                is_won = any(a.outcome == "won" for a in lead_analyses)
                is_lost = any(a.outcome == "lost" for a in lead_analyses)
                
                # Check lead status
                lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
                is_dead = lead and lead.status in [
                    LeadStatus.ABANDONED.value,
                    LeadStatus.CLOSED_LOST.value,
                    LeadStatus.DORMANT.value
                ]
                
                if not is_won and not is_lost and not is_dead:
                    pending_leads_count += 1
            
            # Get tasks for this rep
            tasks = self.db.query(Task).filter(
                Task.company_id == tenant_id,
                Task.assigned_to == TaskAssignee.REP.value,
                # TODO: Filter by rep_id when Task.assignee_id is available
            ).limit(10).all()  # Limit to 10 most recent
            
            task_descriptions = [t.description for t in tasks if t.description]
            
            # Get rep name
            rep_name = None
            user = self.db.query(User).filter(User.id == rep.user_id).first()
            if user:
                rep_name = user.name
            
            items.append(SalesOpportunityItem(
                rep_id=rep.user_id,
                rep_name=rep_name,
                pending_leads_count=pending_leads_count,
                tasks=task_descriptions
            ))
        
        return SalesOpportunitiesResponse(items=items)
    
    # Sales Rep App Methods
    
    async def get_sales_rep_today_appointments(
        self,
        *,
        tenant_id: str,
        rep_id: str,
        today: Optional[datetime] = None,
    ) -> List['SalesRepTodayAppointment']:
        """
        Get today's appointments for a sales rep.
        
        Args:
            tenant_id: Company/tenant ID
            rep_id: Sales rep user ID
            today: Date to filter by (defaults to current date)
        
        Returns:
            List of SalesRepTodayAppointment for today
        """
        from app.schemas.metrics import SalesRepTodayAppointment
        from app.models.contact_card import ContactCard
        
        if today is None:
            today = datetime.utcnow()
        
        # Get start and end of day
        start_of_day = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Query appointments for today
        appointments = self.db.query(Appointment).filter(
            Appointment.company_id == tenant_id,
            Appointment.assigned_rep_id == rep_id,
            Appointment.scheduled_start >= start_of_day,
            Appointment.scheduled_start <= end_of_day
        ).order_by(Appointment.scheduled_start).all()
        
        # Get appointment IDs for analysis lookup
        appointment_ids = [apt.id for apt in appointments]
        
        # Get RecordingAnalysis records
        analyses = self.db.query(RecordingAnalysis).filter(
            RecordingAnalysis.appointment_id.in_(appointment_ids),
            RecordingAnalysis.company_id == tenant_id
        ).all()
        
        analysis_by_appointment_id = {analysis.appointment_id: analysis for analysis in analyses}
        
        # Build response
        items: List[SalesRepTodayAppointment] = []
        for appointment in appointments:
            analysis = analysis_by_appointment_id.get(appointment.id)
            
            # Get customer name
            customer_name = None
            customer_id = None
            if appointment.contact_card_id:
                contact_card = self.db.query(ContactCard).filter(
                    ContactCard.id == appointment.contact_card_id
                ).first()
                if contact_card:
                    customer_name = f"{contact_card.first_name or ''} {contact_card.last_name or ''}".strip() or None
                    customer_id = contact_card.id
            elif appointment.lead_id:
                customer_id = appointment.lead_id
            
            # Get outcome from Shunya
            outcome = None
            if analysis and analysis.outcome:
                outcome = analysis.outcome.lower()
            
            # Get location data from Appointment (Shunya-enriched)
            location_address = appointment.location_address or appointment.location
            location_lat = appointment.location_lat or appointment.geo_lat
            location_lng = appointment.location_lng or appointment.geo_lng
            
            # Fallback to ContactCard if appointment doesn't have lat/lng
            if (location_lat is None or location_lng is None) and appointment.contact_card_id:
                contact_card = self.db.query(ContactCard).filter(
                    ContactCard.id == appointment.contact_card_id
                ).first()
                if contact_card and contact_card.property_snapshot:
                    prop_snapshot = contact_card.property_snapshot
                    if isinstance(prop_snapshot, dict):
                        lat = prop_snapshot.get("latitude") or prop_snapshot.get("lat") or prop_snapshot.get("geo_lat")
                        lng = prop_snapshot.get("longitude") or prop_snapshot.get("lng") or prop_snapshot.get("geo_lng")
                        if lat and lng:
                            try:
                                location_lat = float(lat)
                                location_lng = float(lng)
                            except (ValueError, TypeError):
                                pass
            
            items.append(SalesRepTodayAppointment(
                appointment_id=appointment.id,
                customer_id=customer_id,
                customer_name=customer_name,
                scheduled_time=appointment.scheduled_start,
                address_line=appointment.location,  # Legacy field
                location_address=location_address,  # New field from Shunya
                location_lat=location_lat,
                location_lng=location_lng,
                geofence_radius_meters=75,  # Constant as specified
                status=appointment.status.value if hasattr(appointment.status, 'value') else str(appointment.status),
                outcome=outcome
            ))
        
        return items
    
    async def get_sales_rep_followups(
        self,
        *,
        tenant_id: str,
        rep_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List['SalesRepFollowupTask']:
        """
        Get follow-up tasks for a sales rep.
        
        Args:
            tenant_id: Company/tenant ID
            rep_id: Sales rep user ID
            date_from: Start datetime (optional)
            date_to: End datetime (optional)
        
        Returns:
            List of SalesRepFollowupTask
        """
        from app.schemas.metrics import SalesRepFollowupTask
        from app.models.contact_card import ContactCard
        from app.models.lead import Lead
        
        # Query tasks assigned to this rep
        tasks_query = self.db.query(Task).filter(
            Task.company_id == tenant_id,
            Task.status.in_([TaskStatus.OPEN.value, TaskStatus.PENDING.value])
        )
        
        # Filter by rep: prefer assignee_id if available, else fallback to assigned_to role
        if hasattr(Task, 'assignee_id'):
            tasks_query = tasks_query.filter(
                or_(
                    Task.assignee_id == rep_id,
                    and_(
                        Task.assignee_id.is_(None),
                        Task.assigned_to == TaskAssignee.REP.value
                    )
                )
            )
        else:
            tasks_query = tasks_query.filter(Task.assigned_to == TaskAssignee.REP.value)
        
        # Apply date filters if provided
        if date_from:
            tasks_query = tasks_query.filter(Task.due_at >= date_from)
        if date_to:
            tasks_query = tasks_query.filter(Task.due_at <= date_to)
        
        tasks = tasks_query.order_by(Task.due_at).all()
        
        # Build response
        items: List[SalesRepFollowupTask] = []
        now = datetime.utcnow()
        
        for task in tasks:
            # Get customer name
            customer_name = None
            if task.contact_card_id:
                contact_card = self.db.query(ContactCard).filter(
                    ContactCard.id == task.contact_card_id
                ).first()
                if contact_card:
                    customer_name = f"{contact_card.first_name or ''} {contact_card.last_name or ''}".strip() or None
            elif task.lead_id:
                lead = self.db.query(Lead).filter(Lead.id == task.lead_id).first()
                if lead:
                    customer_name = lead.customer_name
            
            # Get task type
            task_type = None
            if task.action_type:
                task_type = task.action_type.value if hasattr(task.action_type, 'value') else str(task.action_type)
            
            # Determine if overdue
            overdue = False
            if task.due_at and task.due_at < now:
                overdue = True
            
            # TODO: Get last_contact_time from CallRail/Twilio integration
            # For now, set to None
            last_contact_time = None
            
            # TODO: Get next_step from Shunya follow-up recommendations
            # For now, set to None
            next_step = None
            
            items.append(SalesRepFollowupTask(
                task_id=task.id,
                lead_id=task.lead_id,
                customer_name=customer_name,
                title=task.description,
                type=task_type,
                due_date=task.due_at,
                status=task.status.value if hasattr(task.status, 'value') else str(task.status),
                last_contact_time=last_contact_time,
                next_step=next_step,
                overdue=overdue
            ))
        
        return items
    
    async def get_sales_rep_meeting_detail(
        self,
        *,
        tenant_id: str,
        rep_id: str,
        appointment_id: str,
    ) -> 'SalesRepMeetingDetail':
        """
        Get meeting detail for a sales rep appointment.
        
        Args:
            tenant_id: Company/tenant ID
            rep_id: Sales rep user ID
            appointment_id: Appointment ID
        
        Returns:
            SalesRepMeetingDetail with analysis, transcript, objections, etc.
        
        Raises:
            HTTPException: If appointment not found or not assigned to rep
        """
        from app.schemas.metrics import SalesRepMeetingDetail
        from app.models.recording_transcript import RecordingTranscript
        from fastapi import HTTPException
        
        # Get appointment with RBAC check
        appointment = self.db.query(Appointment).filter(
            Appointment.id == appointment_id,
            Appointment.company_id == tenant_id,
            Appointment.assigned_rep_id == rep_id
        ).first()
        
        if not appointment:
            raise HTTPException(
                status_code=404,
                detail="Appointment not found or not assigned to this rep"
            )
        
        # Get RecordingAnalysis
        analysis = self.db.query(RecordingAnalysis).filter(
            RecordingAnalysis.appointment_id == appointment_id,
            RecordingAnalysis.company_id == tenant_id
        ).first()
        
        # Get RecordingTranscript
        transcript = None
        if appointment_id:
            recording_transcript = self.db.query(RecordingTranscript).filter(
                RecordingTranscript.appointment_id == appointment_id,
                RecordingTranscript.company_id == tenant_id
            ).first()
            if recording_transcript:
                transcript = recording_transcript.transcript
        
        # Get call_id from RecordingSession if linked
        call_id = None
        recording_session = self.db.query(RecordingSession).filter(
            RecordingSession.appointment_id == appointment_id,
            RecordingSession.company_id == tenant_id
        ).first()
        if recording_session and recording_session.call_id:
            call_id = recording_session.call_id
        
        # Get follow-up recommendations from CallAnalysis if available
        followup_recommendations = None
        if call_id:
            call_analysis = self.db.query(CallAnalysis).filter(
                CallAnalysis.call_id == call_id,
                CallAnalysis.company_id == tenant_id
            ).first()
            if call_analysis and call_analysis.followup_recommendations:
                followup_recommendations = call_analysis.followup_recommendations
        
        # Get summary from RecordingTranscript if available, or use coaching_tips from analysis
        summary = None
        if transcript:
            # Use first 500 chars of transcript as summary if no dedicated summary field
            summary = transcript[:500] + "..." if len(transcript) > 500 else transcript
        elif analysis and analysis.coaching_tips:
            # Fallback to coaching tips as summary
            if isinstance(analysis.coaching_tips, list) and len(analysis.coaching_tips) > 0:
                summary = "; ".join([tip.get("tip", "") if isinstance(tip, dict) else str(tip) for tip in analysis.coaching_tips[:3]])
        
        return SalesRepMeetingDetail(
            appointment_id=appointment_id,
            call_id=call_id,
            summary=summary,
            transcript=transcript,
            objections=analysis.objections if analysis and analysis.objections else None,
            sop_compliance_score=analysis.sop_compliance_score if analysis else None,
            sentiment_score=analysis.sentiment_score if analysis else None,
            outcome=analysis.outcome.lower() if analysis and analysis.outcome else None,
            followup_recommendations=followup_recommendations
        )

