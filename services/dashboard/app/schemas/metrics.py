"""
Metrics schemas for role-scoped KPIs.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


class CSRMetrics(BaseModel):
    """
    CSR overview metrics computed from calls, analysis, and tasks.
    
    All metrics are computed for a specific CSR within a date range.
    """
    
    total_calls: int = Field(..., description="Total number of CSR calls in date range")
    
    qualified_calls: int = Field(..., description="Number of calls with qualification_status in (hot, warm, cold)")
    
    qualified_rate: Optional[float] = Field(
        None,
        description="Qualified calls / total calls (0.0-1.0), None if total_calls == 0"
    )
    
    booked_calls: int = Field(..., description="Number of calls with booking_status == 'booked'")
    
    booking_rate: Optional[float] = Field(
        None,
        description="Booked calls / qualified calls (0.0-1.0), None if qualified_calls == 0"
    )
    
    service_not_offered_calls: int = Field(
        ...,
        description="Number of calls with booking_status == 'service_not_offered'"
    )
    
    service_not_offered_rate: Optional[float] = Field(
        None,
        description="Service not offered calls / qualified calls (0.0-1.0), None if qualified_calls == 0"
    )
    
    avg_objections_per_qualified_call: Optional[float] = Field(
        None,
        description="Average number of objections per qualified call, None if no qualified calls"
    )
    
    qualified_but_unbooked_calls: int = Field(
        ...,
        description="Number of calls with call_outcome_category == 'qualified_but_unbooked'"
    )
    
    avg_compliance_score: Optional[float] = Field(
        None,
        description="Average SOP compliance score (0-10 scale), None if no scores available"
    )
    
    open_followups: int = Field(
        ...,
        description="Number of open/pending tasks assigned to CSR with due_at >= now"
    )
    
    overdue_followups: int = Field(
        ...,
        description="Number of open/pending tasks assigned to CSR with due_at < now"
    )
    
    top_reason_for_missed_bookings: Optional[str] = Field(
        None,
        description="Most frequent reason for qualified calls that did not result in bookings. None if not enough data."
    )
    
    pending_leads_count: Optional[int] = Field(
        None,
        description="Number of leads in pending/neutral state for this CSR"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_calls": 150,
                "qualified_calls": 120,
                "qualified_rate": 0.8,
                "booked_calls": 90,
                "booking_rate": 0.75,
                "service_not_offered_calls": 10,
                "service_not_offered_rate": 0.083,
                "avg_objections_per_qualified_call": 1.5,
                "qualified_but_unbooked_calls": 20,
                "avg_compliance_score": 8.5,
                "open_followups": 15,
                "overdue_followups": 3
            }
        }


class SalesRepMetrics(BaseModel):
    """
    Sales Rep overview metrics computed from appointments, recordings, and tasks.
    
    All metrics are computed for a specific sales rep within a date range.
    """
    
    total_appointments: int = Field(..., description="Total number of appointments in date range")
    
    completed_appointments: int = Field(..., description="Number of appointments with status == 'completed'")
    
    won_appointments: int = Field(..., description="Number of appointments with outcome == 'won'")
    
    lost_appointments: int = Field(..., description="Number of appointments with outcome == 'lost'")
    
    pending_appointments: int = Field(..., description="Number of appointments with outcome == 'pending'")
    
    win_rate: Optional[float] = Field(
        None,
        description="Won appointments / completed appointments (0.0-1.0), None if completed_appointments == 0"
    )
    
    avg_objections_per_appointment: Optional[float] = Field(
        None,
        description="Average number of objections per appointment (from RecordingAnalysis), None if no appointments"
    )
    
    avg_compliance_score: Optional[float] = Field(
        None,
        description="Average SOP compliance score (0-10 scale) from RecordingAnalysis, None if no scores available"
    )
    
    avg_meeting_structure_score: Optional[float] = Field(
        None,
        description="Average meeting structure score derived from meeting_segments, None if no segments available"
    )
    
    avg_sentiment_score: Optional[float] = Field(
        None,
        description="Average sentiment score (0.0-1.0) from RecordingAnalysis, None if no scores available"
    )
    
    open_followups: int = Field(
        ...,
        description="Number of open/pending tasks assigned to rep with due_at >= now"
    )
    
    overdue_followups: int = Field(
        ...,
        description="Number of open/pending tasks assigned to rep with due_at < now"
    )
    
    # Extended KPIs for Sales Rep app
    first_touch_win_rate: Optional[float] = Field(
        None,
        description="Win rate for first appointment with a lead/customer (0.0-1.0), None if insufficient data"
    )
    
    followup_win_rate: Optional[float] = Field(
        None,
        description="Win rate where > 1 appointment or follow-up happened before close (0.0-1.0), None if insufficient data"
    )
    
    auto_usage_hours: Optional[float] = Field(
        None,
        description="Total hours of meetings recorded with Otto for this rep (sum of RecordingSession.audio_duration_seconds / 3600)"
    )
    
    attendance_rate: Optional[float] = Field(
        None,
        description="Attended appointments / scheduled appointments (0.0-1.0), None if no scheduled appointments"
    )
    
    followup_rate: Optional[float] = Field(
        None,
        description="Leads with ≥ 1 follow-up task completed / total leads owned by rep (0.0-1.0), None if no leads"
    )
    
    pending_followups_count: int = Field(
        ...,
        description="Count of open follow-up tasks assigned to rep with due_date >= today and status in (pending, open)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_appointments": 50,
                "completed_appointments": 45,
                "won_appointments": 30,
                "lost_appointments": 10,
                "pending_appointments": 5,
                "win_rate": 0.667,
                "avg_objections_per_appointment": 1.2,
                "avg_compliance_score": 8.5,
                "avg_meeting_structure_score": 0.85,
                "avg_sentiment_score": 0.75,
                "open_followups": 8,
                "overdue_followups": 2
            }
        }


class SalesRepSummary(BaseModel):
    """
    Summary metrics for a single sales rep (used in team metrics).
    """
    
    rep_id: str = Field(..., description="Sales rep user ID")
    
    rep_name: Optional[str] = Field(None, description="Sales rep name (nullable)")
    
    total_appointments: int = Field(..., description="Total appointments for this rep")
    
    completed_appointments: int = Field(..., description="Completed appointments for this rep")
    
    won_appointments: int = Field(..., description="Won appointments for this rep")
    
    win_rate: Optional[float] = Field(
        None,
        description="Win rate for this rep, None if no completed appointments"
    )
    
    avg_compliance_score: Optional[float] = Field(
        None,
        description="Average compliance score for this rep, None if no scores available"
    )
    
    auto_usage_rate: Optional[float] = Field(
        None,
        description="Auto usage rate (placeholder, to be wired later)"
    )


class SalesTeamMetrics(BaseModel):
    """
    Aggregate sales team metrics for all reps in a company.
    """
    
    total_appointments: int = Field(..., description="Total appointments across all reps")
    
    completed_appointments: int = Field(..., description="Completed appointments across all reps")
    
    team_win_rate: Optional[float] = Field(
        None,
        description="Team win rate (won / completed), None if no completed appointments"
    )
    
    avg_objections_per_appointment: Optional[float] = Field(
        None,
        description="Average objections per appointment across team, None if no appointments"
    )
    
    avg_compliance_score: Optional[float] = Field(
        None,
        description="Average compliance score across team, None if no scores available"
    )
    
    avg_meeting_structure_score: Optional[float] = Field(
        None,
        description="Average meeting structure score across team, None if no scores available"
    )
    
    avg_sentiment_score: Optional[float] = Field(
        None,
        description="Average sentiment score across team, None if no scores available"
    )
    
    reps: List[SalesRepSummary] = Field(
        ...,
        description="List of per-rep summary metrics"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_appointments": 200,
                "completed_appointments": 180,
                "team_win_rate": 0.65,
                "avg_objections_per_appointment": 1.3,
                "avg_compliance_score": 8.2,
                "avg_meeting_structure_score": 0.82,
                "avg_sentiment_score": 0.73,
                "reps": [
                    {
                        "rep_id": "rep_001",
                        "rep_name": "John Doe",
                        "total_appointments": 50,
                        "completed_appointments": 45,
                        "won_appointments": 30,
                        "win_rate": 0.667,
                        "avg_compliance_score": 8.5,
                        "auto_usage_rate": None
                    }
                ]
            }
        }


class ExecCSRMetrics(BaseModel):
    """
    Executive-level CSR metrics (company-wide, not per-user).
    """
    
    total_calls: int = Field(..., description="Total CSR calls in date range")
    
    qualified_calls: int = Field(..., description="Number of qualified calls")
    
    qualified_rate: Optional[float] = Field(
        None,
        description="Qualified calls / total calls, None if total_calls == 0"
    )
    
    booked_calls: int = Field(..., description="Number of booked calls")
    
    booking_rate: Optional[float] = Field(
        None,
        description="Booked calls / qualified calls, None if qualified_calls == 0"
    )
    
    avg_objections_per_call: Optional[float] = Field(
        None,
        description="Average objections per call, None if no calls"
    )
    
    avg_compliance_score: Optional[float] = Field(
        None,
        description="Average compliance score, None if no scores available"
    )
    
    avg_sentiment_score: Optional[float] = Field(
        None,
        description="Average sentiment score, None if no scores available"
    )
    
    open_followups: int = Field(..., description="Total open followups across all CSRs")
    
    overdue_followups: int = Field(..., description="Total overdue followups across all CSRs")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_calls": 500,
                "qualified_calls": 400,
                "qualified_rate": 0.8,
                "booked_calls": 300,
                "booking_rate": 0.75,
                "avg_objections_per_call": 1.2,
                "avg_compliance_score": 8.3,
                "avg_sentiment_score": 0.72,
                "open_followups": 50,
                "overdue_followups": 10
            }
        }


class ExecSalesMetrics(BaseModel):
    """
    Executive-level Sales metrics (company-wide, not per-rep).
    """
    
    total_appointments: int = Field(..., description="Total appointments in date range")
    
    completed_appointments: int = Field(..., description="Completed appointments")
    
    won_appointments: int = Field(..., description="Won appointments")
    
    lost_appointments: int = Field(..., description="Lost appointments")
    
    pending_appointments: int = Field(..., description="Pending appointments")
    
    team_win_rate: Optional[float] = Field(
        None,
        description="Team win rate (won / completed), None if completed_appointments == 0"
    )
    
    avg_objections_per_appointment: Optional[float] = Field(
        None,
        description="Average objections per appointment, None if no appointments"
    )
    
    avg_compliance_score: Optional[float] = Field(
        None,
        description="Average compliance score, None if no scores available"
    )
    
    avg_meeting_structure_score: Optional[float] = Field(
        None,
        description="Average meeting structure score, None if no scores available"
    )
    
    avg_sentiment_score: Optional[float] = Field(
        None,
        description="Average sentiment score, None if no scores available"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_appointments": 200,
                "completed_appointments": 180,
                "won_appointments": 120,
                "lost_appointments": 50,
                "pending_appointments": 30,
                "team_win_rate": 0.667,
                "avg_objections_per_appointment": 1.3,
                "avg_compliance_score": 8.2,
                "avg_meeting_structure_score": 0.82,
                "avg_sentiment_score": 0.73
            }
        }


# CSR Dashboard specific schemas

class CSRBookingTrendPoint(BaseModel):
    """Single data point in CSR booking trend."""
    
    period_start: datetime = Field(..., description="Start of the time period")
    period_end: datetime = Field(..., description="End of the time period")
    booking_rate: Optional[float] = Field(None, description="Booking rate for this period (0.0-1.0), None if no qualified leads")
    total_leads: int = Field(..., description="Total leads in this period")
    qualified_leads: int = Field(..., description="Qualified leads in this period")
    booked_appointments: int = Field(..., description="Booked appointments in this period")


class CSRBookingTrend(BaseModel):
    """Time series of CSR booking metrics."""
    
    points: List[CSRBookingTrendPoint] = Field(..., description="List of booking trend data points")


class CSRUnbookedAppointmentItem(BaseModel):
    """Single unbooked appointment/call item."""
    
    call_id: int = Field(..., description="Call ID")
    lead_id: Optional[str] = Field(None, description="Lead ID if available")
    customer_name: Optional[str] = Field(None, description="Customer name")
    phone: Optional[str] = Field(None, description="Customer phone number")
    created_at: datetime = Field(..., description="When the call was created")
    qualification_status: Optional[str] = Field(None, description="Qualification status from Shunya")
    booking_status: Optional[str] = Field(None, description="Booking status from Shunya")
    primary_objection: Optional[str] = Field(None, description="Primary objection if available from Shunya")


class CSRUnbookedAppointmentsResponse(BaseModel):
    """Response for unbooked appointments list."""
    
    items: List[CSRUnbookedAppointmentItem] = Field(..., description="List of unbooked appointments")


class CSRObjectionMetric(BaseModel):
    """Objection metric for CSR dashboard."""
    
    objection_key: str = Field(..., description="Canonical objection key/category")
    label: str = Field(..., description="Display label for the objection")
    occurrence_count: int = Field(..., description="Number of times this objection occurred")
    occurrence_rate: float = Field(..., description="Occurrence rate (0.0-1.0)")


class CSRTopObjectionsResponse(BaseModel):
    """Response for top objections."""
    
    top_objections: List[CSRObjectionMetric] = Field(..., description="List of top objections")
    total_calls_considered: int = Field(..., description="Total number of calls considered")


class CSRObjectionCallItem(BaseModel):
    """Call item in objection drilldown."""
    
    call_id: int = Field(..., description="Call ID")
    lead_id: Optional[str] = Field(None, description="Lead ID if available")
    customer_name: Optional[str] = Field(None, description="Customer name")
    phone: Optional[str] = Field(None, description="Customer phone number")
    created_at: datetime = Field(..., description="When the call was created")
    audio_url: Optional[str] = Field(None, description="Audio URL if available")
    transcript_snippet: Optional[str] = Field(None, description="Short transcript snippet if available")


class CSRObjectionCallsResponse(BaseModel):
    """Response for calls with a specific objection."""
    
    objection_key: str = Field(..., description="The objection key")
    items: List[CSRObjectionCallItem] = Field(..., description="List of calls with this objection")


class AutoQueuedLeadItem(BaseModel):
    """Auto-queued lead item (AI recovery)."""
    
    lead_id: str = Field(..., description="Lead ID")
    customer_name: Optional[str] = Field(None, description="Customer name")
    phone: Optional[str] = Field(None, description="Customer phone number")
    last_contacted_at: Optional[datetime] = Field(None, description="Last contact timestamp")
    status: str = Field(..., description="Lead status (e.g., pending, scheduled)")


class AutoQueuedLeadsResponse(BaseModel):
    """Response for auto-queued leads."""
    
    items: List[AutoQueuedLeadItem] = Field(..., description="List of auto-queued leads")


class CSRMissedCallMetrics(BaseModel):
    """Missed call recovery metrics."""
    
    missed_calls_count: int = Field(..., description="Total number of missed calls")
    saved_calls_count: int = Field(..., description="Number of saved calls (eventually booked/converted)")
    saved_calls_via_auto_rescue_count: int = Field(..., description="Number of saves via Otto AI auto-rescue")


class CSRLeadStatusItem(BaseModel):
    """Lead status item for missed call recovery."""
    
    lead_id: str = Field(..., description="Lead ID")
    customer_name: Optional[str] = Field(None, description="Customer name")
    phone: Optional[str] = Field(None, description="Customer phone number")
    status: Literal["booked", "pending", "dead"] = Field(..., description="Lead status: booked, pending, dead")
    pending_action: Optional[str] = Field(None, description="Pending action if status is pending")
    last_contacted_at: Optional[datetime] = Field(None, description="Last contact timestamp")
    attempts_count: Optional[int] = Field(None, description="Number of contact attempts")


class CSRMissedCallRecoveryResponse(BaseModel):
    """Response for missed call recovery overview."""
    
    metrics: CSRMissedCallMetrics = Field(..., description="Missed call metrics")
    booked_leads: List[CSRLeadStatusItem] = Field(..., description="Booked leads")
    pending_leads: List[CSRLeadStatusItem] = Field(..., description="Pending leads requiring nurturing")
    dead_leads: List[CSRLeadStatusItem] = Field(..., description="Dead/unresponsive leads")


# Executive Dashboard schemas

class TimeSeriesPoint(BaseModel):
    """Reusable time series data point."""
    
    bucket_start: datetime = Field(..., description="Start of the time bucket")
    bucket_end: datetime = Field(..., description="End of the time bucket")
    value: Optional[float] = Field(None, description="Value for this time bucket")


class ExecCompanyWinLossAttribution(BaseModel):
    """Attribution of where deals stall or die (fractions over qualified leads at CSR level)."""
    
    pending_from_csr_initial_call: Optional[float] = Field(None, description="Fraction of qualified leads pending at CSR initial call stage")
    lost_from_csr_initial_call: Optional[float] = Field(None, description="Fraction of qualified leads lost at CSR initial call stage")
    pending_from_csr_followup: Optional[float] = Field(None, description="Fraction of qualified leads pending at CSR follow-up stage")
    lost_from_csr_followup: Optional[float] = Field(None, description="Fraction of qualified leads lost at CSR follow-up stage")
    pending_from_sales_followup: Optional[float] = Field(None, description="Fraction of qualified leads pending at sales follow-up stage")
    lost_from_sales_followup: Optional[float] = Field(None, description="Fraction of qualified leads lost at sales follow-up stage")
    pending_from_sales_appointment: Optional[float] = Field(None, description="Fraction of qualified leads pending at sales appointment stage")
    lost_from_sales_appointment: Optional[float] = Field(None, description="Fraction of qualified leads lost at sales appointment stage")


class ExecWhoDroppingBall(BaseModel):
    """Identifies worst-performing CSR and Sales Rep."""
    
    worst_csr_id: Optional[str] = Field(None, description="CSR with lowest booking rate")
    worst_csr_name: Optional[str] = Field(None, description="CSR name")
    worst_csr_booking_rate: Optional[float] = Field(None, description="Worst CSR booking rate")
    
    worst_rep_id: Optional[str] = Field(None, description="Sales rep with lowest win rate")
    worst_rep_name: Optional[str] = Field(None, description="Sales rep name")
    worst_rep_win_rate: Optional[float] = Field(None, description="Worst rep win rate")


class ExecCompanyOverviewMetrics(BaseModel):
    """Executive company-wide overview metrics."""
    
    # High-level funnel
    total_leads: Optional[int] = Field(None, description="Total leads in date range")
    qualified_leads: Optional[int] = Field(None, description="Qualified leads from CSR qualification (Shunya)")
    total_appointments: Optional[int] = Field(None, description="Total appointments (from Appointment model)")
    total_closed_deals: Optional[int] = Field(None, description="Total closed deals (Shunya-booked at sales outcome level)")
    
    # Ratios
    lead_to_sale_ratio: Optional[float] = Field(None, description="closed_deals / total_leads")
    close_rate: Optional[float] = Field(None, description="closed_deals / qualified_leads")
    sales_output_amount: Optional[float] = Field(None, description="Placeholder for revenue (TODO: revenue piping)")
    
    # Win/loss breakdown
    win_rate: Optional[float] = Field(None, description="Same as close_rate, but kept for compatibility")
    pending_rate: Optional[float] = Field(None, description="pending / qualified")
    lost_rate: Optional[float] = Field(None, description="lost / qualified")
    
    # Attribution
    win_loss_attribution: Optional[ExecCompanyWinLossAttribution] = Field(None, description="Where deals stall or die")
    
    # Who is dropping the ball
    who_dropping_ball: Optional[ExecWhoDroppingBall] = Field(None, description="Worst-performing CSR and Sales Rep")


class ObjectionSummary(BaseModel):
    """Objection summary for exec dashboards."""
    
    objection_key: str = Field(..., description="Canonical objection key")
    objection_label: Optional[str] = Field(None, description="Display label")
    occurrence_count: int = Field(..., description="Number of occurrences")
    occurrence_rate: Optional[float] = Field(None, description="Fraction over total calls")
    occurrence_rate_over_qualified_unbooked: Optional[float] = Field(None, description="Fraction over qualified but unbooked calls")


class CSRAgentCoachingSummary(BaseModel):
    """CSR agent coaching summary for exec dashboard."""
    
    csr_id: str = Field(..., description="CSR user ID")
    csr_name: Optional[str] = Field(None, description="CSR name")
    total_calls: int = Field(..., description="Total calls")
    qualified_calls: int = Field(..., description="Qualified calls")
    booked_calls: int = Field(..., description="Booked calls")
    booking_rate: Optional[float] = Field(None, description="Booking rate")
    sop_compliance_score: Optional[float] = Field(None, description="Average SOP compliance score")
    top_objections: List[ObjectionSummary] = Field(default_factory=list, description="Top objections for this CSR")


class ExecCSRDashboardMetrics(BaseModel):
    """Executive CSR dashboard metrics."""
    
    overview: ExecCSRMetrics = Field(..., description="Reuse existing ExecCSRMetrics")
    booking_rate_trend: Optional[List[TimeSeriesPoint]] = Field(None, description="Booking rate trend over time")
    unbooked_calls_count: Optional[int] = Field(None, description="Unbooked calls count (CSR-wide)")
    top_objections: List[ObjectionSummary] = Field(default_factory=list, description="Top objections across all CSRs")
    coaching_opportunities: List[CSRAgentCoachingSummary] = Field(default_factory=list, description="Coaching summaries per CSR")


class ExecMissedCallRecoveryMetrics(BaseModel):
    """Executive missed call recovery metrics (company-wide)."""
    
    total_missed_calls: Optional[int] = Field(None, description="Total missed calls")
    total_saved_calls: Optional[int] = Field(None, description="Total saved calls")
    total_saved_by_otto: Optional[int] = Field(None, description="Total saved by Otto AI")
    booked_leads_count: Optional[int] = Field(None, description="Booked leads count")
    pending_leads_count: Optional[int] = Field(None, description="Pending leads count")
    dead_leads_count: Optional[int] = Field(None, description="Dead leads count")


class SalesTeamStatsMetrics(BaseModel):
    """Sales team statistics metrics."""
    
    total_conversations: Optional[int] = Field(None, description="Total conversations/recordings")
    avg_recording_duration_seconds: Optional[float] = Field(None, description="Average recording duration")
    followup_rate: Optional[float] = Field(None, description="Fraction of leads with >=1 followup")
    followup_win_rate: Optional[float] = Field(None, description="Win rate for leads with followups (TODO: may be None if insufficient data)")
    first_touch_win_rate: Optional[float] = Field(None, description="Win rate for first appointment (TODO: may be None if insufficient data)")
    team_win_rate: Optional[float] = Field(None, description="Overall team win rate")


class SalesRepRecordingSummary(BaseModel):
    """Sales rep recording summary for exec dashboard."""
    
    rep_id: str = Field(..., description="Sales rep user ID")
    rep_name: Optional[str] = Field(None, description="Sales rep name")
    total_recordings: int = Field(..., description="Total recordings")
    total_recording_hours: float = Field(..., description="Total recording hours")
    win_rate: Optional[float] = Field(None, description="Win rate")
    auto_usage_hours: Optional[float] = Field(None, description="Auto usage hours (placeholder/TODO)")
    sop_compliance_score: Optional[float] = Field(None, description="Average SOP compliance score from Shunya")
    sales_compliance_score: Optional[float] = Field(None, description="Sales compliance score from Shunya")


class ExecSalesTeamDashboardMetrics(BaseModel):
    """Executive sales team dashboard metrics."""
    
    overview: ExecSalesMetrics = Field(..., description="Reuse existing ExecSalesMetrics")
    team_stats: SalesTeamStatsMetrics = Field(..., description="Team statistics")
    reps: List[SalesRepRecordingSummary] = Field(default_factory=list, description="Per-rep summaries")
    top_objections: List[ObjectionSummary] = Field(default_factory=list, description="Top objections across all sales reps")


# CSR Self-Scoped Endpoint Schemas

class CSROverviewSelfResponse(BaseModel):
    """CSR overview metrics for self (includes top_missed_booking_reason)."""
    
    # All fields from CSRMetrics
    total_calls: int
    qualified_calls: int
    qualified_rate: Optional[float] = None
    booked_calls: int
    booking_rate: Optional[float] = None
    service_not_offered_calls: int
    service_not_offered_rate: Optional[float] = None
    avg_objections_per_qualified_call: Optional[float] = None
    qualified_but_unbooked_calls: int
    avg_compliance_score: Optional[float] = None
    open_followups: int
    overdue_followups: int
    top_reason_for_missed_bookings: Optional[str] = None
    pending_leads_count: Optional[int] = None
    
    # New field
    top_missed_booking_reason: Optional[str] = Field(None, description="Top reason for missed bookings (from Shunya objections)")


class CSRBookingTrendSummary(BaseModel):
    """Summary for booking trend."""
    
    total_leads: int = Field(..., description="Total leads")
    total_qualified_leads: int = Field(..., description="Total qualified leads (from Shunya lead_quality)")
    total_booked_calls: int = Field(..., description="Total booked calls (from Shunya booking_status)")
    current_booking_rate: Optional[float] = Field(None, description="Current booking rate (booked / qualified)")


class CSRBookingTrendPointTimestamp(BaseModel):
    """Single point in booking trend (with timestamp format)."""
    
    timestamp: str = Field(..., description="Date in YYYY-MM-DD format")
    value: Optional[float] = Field(None, description="Booking rate for this period")


class CSRBookingTrendSelfResponse(BaseModel):
    """CSR booking trend for self."""
    
    summary: CSRBookingTrendSummary = Field(..., description="Summary metrics")
    booking_rate_trend: List[CSRBookingTrendPointTimestamp] = Field(default_factory=list, description="Booking rate trend over time")


class UnbookedCallItem(BaseModel):
    """Unbooked call item for CSR self view."""
    
    call_id: int = Field(..., description="Call ID")
    customer_name: Optional[str] = Field(None, description="Customer name")
    phone: Optional[str] = Field(None, description="Phone number")
    booking_status: str = Field(..., description="Booking status from Shunya enum")
    qualified: Optional[bool] = Field(None, description="Whether qualified (derived from lead_quality)")
    status: Literal["pending"] = Field("pending", description="Status (always pending for unbooked)")
    last_contacted_at: Optional[str] = Field(None, description="Last contacted timestamp (ISO8601)")


class UnbookedCallsSelfResponse(BaseModel):
    """Paginated unbooked calls for CSR self."""
    
    items: List[UnbookedCallItem] = Field(default_factory=list, description="Unbooked calls")
    page: int = Field(..., description="Current page (1-indexed)")
    page_size: int = Field(..., description="Page size")
    total: int = Field(..., description="Total count")


class CSRObjectionSelfItem(BaseModel):
    """Objection item for CSR self view."""
    
    objection: str = Field(..., description="Objection key/text")
    occurrence_count: int = Field(..., description="Number of occurrences")
    occurrence_rate: float = Field(..., description="Occurrence rate over total calls")
    qualified_unbooked_occurrence_rate: Optional[float] = Field(None, description="Occurrence rate over qualified but unbooked calls")


class CSRObjectionsSelfResponse(BaseModel):
    """CSR objections for self view."""
    
    top_objections: List[CSRObjectionSelfItem] = Field(default_factory=list, description="Top objections")
    all_objections: List[CSRObjectionSelfItem] = Field(default_factory=list, description="All objections")


class CallByObjectionItem(BaseModel):
    """Call item filtered by objection."""
    
    call_id: int = Field(..., description="Call ID")
    customer_name: Optional[str] = Field(None, description="Customer name")
    started_at: str = Field(..., description="Call start timestamp (ISO8601)")
    duration_seconds: Optional[int] = Field(None, description="Call duration in seconds")
    booking_status: Optional[str] = Field(None, description="Booking status from Shunya")
    audio_url: Optional[str] = Field(None, description="Audio URL if available")


class CallsByObjectionSelfResponse(BaseModel):
    """Paginated calls filtered by objection."""
    
    items: List[CallByObjectionItem] = Field(default_factory=list, description="Calls with this objection")
    page: int = Field(..., description="Current page (1-indexed)")
    page_size: int = Field(..., description="Page size")
    total: int = Field(..., description="Total count")


class CSRMissedCallsSelfResponse(BaseModel):
    """CSR missed calls metrics for self."""
    
    total_missed_calls: int = Field(..., description="Total missed calls")
    total_saved_calls: int = Field(..., description="Total saved calls (from Shunya booking_status)")
    total_saved_by_otto: int = Field(..., description="Total saved by Otto AI")
    booked_leads_count: int = Field(..., description="Booked leads count (from Shunya)")
    pending_leads_count: int = Field(..., description="Pending leads count")
    dead_leads_count: int = Field(..., description="Dead leads count")


class MissedLeadItem(BaseModel):
    """Missed lead item for CSR self view."""
    
    lead_id: str = Field(..., description="Lead ID")
    customer_name: Optional[str] = Field(None, description="Customer name")
    status: Literal["booked", "pending", "dead"] = Field(..., description="Status (from Shunya booking/outcome)")
    source: Literal["missed_call", "missed_text"] = Field(..., description="Source of missed lead")
    last_contacted_at: Optional[str] = Field(None, description="Last contacted timestamp (ISO8601)")
    next_action: Optional[str] = Field(None, description="Next action description")
    next_action_due_at: Optional[str] = Field(None, description="Next action due timestamp (ISO8601)")
    attempt_count: int = Field(..., description="Attempt count (from CallRail/Twilio, non-Shunya)")


class MissedLeadsSelfResponse(BaseModel):
    """Paginated missed leads for CSR self."""
    
    items: List[MissedLeadItem] = Field(default_factory=list, description="Missed leads")
    page: int = Field(..., description="Current page (1-indexed)")
    page_size: int = Field(..., description="Page size")
    total: int = Field(..., description="Total count")


# Exec Endpoint Schemas

class RideAlongAppointmentItem(BaseModel):
    """Ride-along appointment item."""
    
    appointment_id: int = Field(..., description="Appointment ID")
    customer_name: Optional[str] = Field(None, description="Customer name")
    scheduled_at: str = Field(..., description="Scheduled timestamp (ISO8601)")
    rep_id: Optional[str] = Field(None, description="Sales rep user ID")
    rep_name: Optional[str] = Field(None, description="Sales rep name")
    status: Literal["won", "in_progress", "not_started", "rejected"] = Field(..., description="Status (from Shunya + appointment state)")
    outcome: Optional[Literal["won", "lost", "pending"]] = Field(None, description="Outcome from Shunya RecordingAnalysis")
    sop_compliance_scores: dict = Field(default_factory=dict, description="SOP compliance scores by phase")
    booking_path: List[str] = Field(default_factory=list, description="Booking path (e.g., ['inbound_call_csr', 'csr_followup_call', 'appointment_booked'])")


class RideAlongAppointmentsResponse(BaseModel):
    """Paginated ride-along appointments."""
    
    items: List[RideAlongAppointmentItem] = Field(default_factory=list, description="Ride-along appointments")
    page: int = Field(..., description="Current page (1-indexed)")
    page_size: int = Field(..., description="Page size")
    total: int = Field(..., description="Total count")


class SalesOpportunityItem(BaseModel):
    """Sales opportunity item."""
    
    rep_id: str = Field(..., description="Sales rep user ID")
    rep_name: Optional[str] = Field(None, description="Sales rep name")
    pending_leads_count: int = Field(..., description="Pending leads count (from Shunya + Task)")
    tasks: List[str] = Field(default_factory=list, description="Short task descriptions")


class SalesOpportunitiesResponse(BaseModel):
    """Sales opportunities response."""
    
    items: List[SalesOpportunityItem] = Field(default_factory=list, description="Sales opportunities per rep")


# Sales Rep App Schemas

class SalesRepTodayAppointment(BaseModel):
    """Today's appointment for Sales Rep app."""
    
    appointment_id: str = Field(..., description="Appointment ID")
    customer_id: Optional[str] = Field(None, description="Customer/lead ID")
    customer_name: Optional[str] = Field(None, description="Customer name")
    scheduled_time: datetime = Field(..., description="Scheduled start time")
    address_line: Optional[str] = Field(None, description="Address/location")
    status: str = Field(..., description="Appointment status (scheduled, in_progress, completed, cancelled)")
    outcome: Optional[str] = Field(None, description="Outcome from Shunya RecordingAnalysis (won, lost, pending)")


class SalesRepFollowupTask(BaseModel):
    """Follow-up task for Sales Rep app."""
    
    task_id: str = Field(..., description="Task ID")
    lead_id: Optional[str] = Field(None, description="Lead ID")
    customer_name: Optional[str] = Field(None, description="Customer name")
    title: Optional[str] = Field(None, description="Task title/description")
    type: Optional[str] = Field(None, description="Task type (aligned with ActionType enum)")
    due_date: Optional[datetime] = Field(None, description="Due date/time")
    status: str = Field(..., description="Task status (open, completed, overdue, cancelled)")
    last_contact_time: Optional[datetime] = Field(None, description="Last contact time from CallRail/Twilio")
    next_step: Optional[str] = Field(None, description="Next step from Shunya recommendations")
    overdue: bool = Field(..., description="Whether task is overdue")


class SalesRepMeetingDetail(BaseModel):
    """Meeting detail for Sales Rep app."""
    
    appointment_id: str = Field(..., description="Appointment ID")
    call_id: Optional[int] = Field(None, description="Call ID if linked")
    summary: Optional[str] = Field(None, description="AI meeting summary from RecordingAnalysis")
    transcript: Optional[str] = Field(None, description="Transcript from RecordingTranscript")
    objections: Optional[List[dict]] = Field(None, description="Objections from RecordingAnalysis")
    sop_compliance_score: Optional[float] = Field(None, description="SOP compliance score (0-10) from RecordingAnalysis")
    sentiment_score: Optional[float] = Field(None, description="Sentiment score (0.0-1.0) from RecordingAnalysis")
    outcome: Optional[str] = Field(None, description="Outcome from RecordingAnalysis (won, lost, pending)")
    followup_recommendations: Optional[dict] = Field(None, description="Follow-up recommendations from Shunya (normalized structure)")

