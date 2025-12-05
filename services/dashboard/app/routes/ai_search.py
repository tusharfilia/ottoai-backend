"""
Internal AI search endpoint for Ask Otto.

Provides flexible search and analytics over calls with structured filters.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc, cast, String

from app.database import get_db
from app.deps.ai_internal_auth import get_ai_internal_context, AIInternalContext
from app.schemas.ai_search import (
    AISearchRequest,
    AISearchResponse,
    AISearchCallItem,
    AISearchAggregates,
)
from app.models.call import Call
from app.models.call_analysis import CallAnalysis
from app.models.lead import Lead
from app.models.appointment import Appointment
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)

router = APIRouter(prefix="/internal/ai", tags=["AI Internal"])


def _derive_outcome(call: Call, lead: Optional[Lead], appointment: Optional[Appointment]) -> Optional[str]:
    """Derive outcome string from call/lead/appointment state."""
    if appointment and appointment.outcome:
        return appointment.outcome.value
    if lead and lead.status:
        status_value = lead.status.value
        if "won" in status_value:
            return "won"
        elif "lost" in status_value:
            return "lost"
        elif "booked" in status_value:
            return "booked"
        elif "nurturing" in status_value:
            return "nurturing"
    if call.booked:
        return "booked"
    if call.missed_call:
        return "missed"
    if call.cancelled:
        return "cancelled"
    return "pending"


def _get_main_objection_label(objections: Optional[List]) -> Optional[str]:
    """Extract the first/main objection label from objections list."""
    if not objections:
        return None
    if isinstance(objections, list) and len(objections) > 0:
        return str(objections[0])
    return None


@router.post("/search", response_model=AISearchResponse)
def search_calls(
    request: AISearchRequest,
    ctx: AIInternalContext = Depends(get_ai_internal_context),
    db: Session = Depends(get_db),
) -> AISearchResponse:
    """
    Search and analyze calls with structured filters.
    
    Returns a list of matching calls and aggregate analytics.
    Used by Ask Otto backend for natural language queries.
    """
    company_id = ctx.company_id
    filters = request.filters
    options = request.options
    
    # Default date range: last 30 days
    now = datetime.utcnow()
    date_from = filters.date_from or (now - timedelta(days=30))
    date_to = filters.date_to or now
    
    # Build base query: Call with LEFT JOINs to Analysis, Lead, Appointment
    query = db.query(
        Call,
        CallAnalysis,
        Lead,
        Appointment
    ).outerjoin(
        CallAnalysis, and_(
            CallAnalysis.call_id == Call.call_id,
            CallAnalysis.tenant_id == company_id
        )
    ).outerjoin(
        Lead, and_(
            Lead.id == Call.lead_id,
            Lead.company_id == company_id
        )
    ).outerjoin(
        Appointment, and_(
            Appointment.lead_id == Call.lead_id,
            Appointment.company_id == company_id
        )
    ).filter(
        Call.company_id == company_id
    )
    
    # Apply date filter (use created_at as proxy for started_at)
    query = query.filter(
        Call.created_at >= date_from,
        Call.created_at <= date_to
    )
    
    # Filter by rep_ids
    if filters.rep_ids:
        query = query.filter(
            or_(
                Call.assigned_rep_id.in_(filters.rep_ids),
                Appointment.assigned_rep_id.in_(filters.rep_ids)
            )
        )
    
    # Filter by lead_statuses
    if filters.lead_statuses:
        query = query.filter(Lead.status.in_(filters.lead_statuses))
    
    # Filter by appointment_outcomes
    if filters.appointment_outcomes:
        query = query.filter(Appointment.outcome.in_(filters.appointment_outcomes))
    
    # Filter by has_objections
    if filters.has_objections is not None:
        if filters.has_objections:
            # Has objections: objections field is not null and not empty
            query = query.filter(
                and_(
                    CallAnalysis.objections.isnot(None),
                    CallAnalysis.objections != json.dumps([]),
                    CallAnalysis.objections != "[]"
                )
            )
        else:
            # No objections: objections is null or empty
            query = query.filter(
                or_(
                    CallAnalysis.objections.is_(None),
                    CallAnalysis.objections == json.dumps([]),
                    CallAnalysis.objections == "[]"
                )
            )
    
    # Filter by objection_labels
    if filters.objection_labels:
        # Check if any of the objection labels appear in the objections JSON array
        # Convert JSON to string and check if escaped label appears (works for both PostgreSQL and SQLite)
        objection_conditions = []
        for label in filters.objection_labels:
            # Escape label as JSON string and check if it appears in the JSON array
            label_escaped = json.dumps(label)  # e.g., "price" -> "\"price\""
            objection_conditions.append(
                cast(CallAnalysis.objections, String).contains(label_escaped)
            )
        if objection_conditions:
            query = query.filter(or_(*objection_conditions))
    
    # Filter by sentiment range
    if filters.sentiment_min is not None:
        query = query.filter(CallAnalysis.sentiment_score >= filters.sentiment_min)
    if filters.sentiment_max is not None:
        query = query.filter(CallAnalysis.sentiment_score <= filters.sentiment_max)
    
    # Filter by SOP score range
    if filters.min_sop_score is not None:
        query = query.filter(CallAnalysis.sop_compliance_score >= filters.min_sop_score)
    if filters.max_sop_score is not None:
        query = query.filter(CallAnalysis.sop_compliance_score <= filters.max_sop_score)
    
    # Apply sorting
    if options.sort_by:
        if options.sort_by == "started_at" or options.sort_by == "-started_at":
            order_func = desc if options.sort_by.startswith("-") else asc
            query = query.order_by(order_func(Call.created_at))
        elif options.sort_by == "sentiment_score" or options.sort_by == "-sentiment_score":
            order_func = desc if options.sort_by.startswith("-") else asc
            query = query.order_by(order_func(CallAnalysis.sentiment_score))
        else:
            # Default to started_at descending
            query = query.order_by(desc(Call.created_at))
    else:
        query = query.order_by(desc(Call.created_at))
    
    # Get total count before pagination (for aggregates)
    total_count = query.count()
    
    # Apply pagination if including calls
    if options.include_calls:
        query = query.offset(options.offset).limit(options.limit)
    
    # Execute query
    results = query.all()
    
    # Build call items
    call_items = []
    if options.include_calls:
        for call, analysis, lead, appointment in results:
            # Get appointment_id (use first appointment if multiple)
            appointment_id = None
            if appointment:
                appointment_id = appointment.id
            elif call.lead_id:
                # Try to get first appointment for this lead
                first_appt = db.query(Appointment).filter(
                    Appointment.lead_id == call.lead_id,
                    Appointment.company_id == company_id
                ).order_by(Appointment.scheduled_start.desc()).first()
                if first_appt:
                    appointment_id = first_appt.id
            
            # Parse objections JSON
            objections_list = None
            if analysis and analysis.objections:
                try:
                    if isinstance(analysis.objections, str):
                        objections_list = json.loads(analysis.objections)
                    else:
                        objections_list = analysis.objections
                except (json.JSONDecodeError, TypeError):
                    objections_list = None
            
            # Derive outcome
            outcome = _derive_outcome(call, lead, appointment)
            
            # Get main objection label
            main_objection = _get_main_objection_label(objections_list)
            
            call_item = AISearchCallItem(
                call_id=call.call_id,
                rep_id=call.assigned_rep_id or (appointment.assigned_rep_id if appointment else None),
                lead_id=call.lead_id,
                appointment_id=appointment_id,
                contact_card_id=call.contact_card_id,
                company_id=company_id,
                started_at=call.created_at,  # Use created_at as proxy
                ended_at=None,  # Not directly stored
                duration_seconds=call.last_call_duration,
                outcome=outcome,
                sentiment_score=analysis.sentiment_score if analysis else None,
                main_objection_label=main_objection,
                has_objections=bool(objections_list and len(objections_list) > 0),
                sop_score=analysis.sop_compliance_score if analysis else None,
            )
            call_items.append(call_item)
    
    # Build aggregates
    aggregates = None
    if options.include_aggregates:
        # Re-query for aggregates (without pagination)
        agg_query = db.query(
            Call,
            CallAnalysis,
            Lead,
            Appointment
        ).outerjoin(
            CallAnalysis, and_(
                CallAnalysis.call_id == Call.call_id,
                CallAnalysis.tenant_id == company_id
            )
        ).outerjoin(
            Lead, and_(
                Lead.id == Call.lead_id,
                Lead.company_id == company_id
            )
        ).outerjoin(
            Appointment, and_(
                Appointment.lead_id == Call.lead_id,
                Appointment.company_id == company_id
            )
        ).filter(
            Call.company_id == company_id,
            Call.created_at >= date_from,
            Call.created_at <= date_to
        )
        
        # Re-apply all filters for aggregates
        if filters.rep_ids:
            agg_query = agg_query.filter(
                or_(
                    Call.assigned_rep_id.in_(filters.rep_ids),
                    Appointment.assigned_rep_id.in_(filters.rep_ids)
                )
            )
        if filters.lead_statuses:
            agg_query = agg_query.filter(Lead.status.in_(filters.lead_statuses))
        if filters.appointment_outcomes:
            agg_query = agg_query.filter(Appointment.outcome.in_(filters.appointment_outcomes))
        if filters.has_objections is not None:
            if filters.has_objections:
                agg_query = agg_query.filter(
                    and_(
                        CallAnalysis.objections.isnot(None),
                        CallAnalysis.objections != json.dumps([]),
                        CallAnalysis.objections != "[]"
                    )
                )
            else:
                agg_query = agg_query.filter(
                    or_(
                        CallAnalysis.objections.is_(None),
                        CallAnalysis.objections == json.dumps([]),
                        CallAnalysis.objections == "[]"
                    )
                )
        if filters.objection_labels:
            objection_conditions = []
            for label in filters.objection_labels:
                label_escaped = json.dumps(label)
                objection_conditions.append(
                    cast(CallAnalysis.objections, String).contains(label_escaped)
                )
            if objection_conditions:
                agg_query = agg_query.filter(or_(*objection_conditions))
        if filters.sentiment_min is not None:
            agg_query = agg_query.filter(CallAnalysis.sentiment_score >= filters.sentiment_min)
        if filters.sentiment_max is not None:
            agg_query = agg_query.filter(CallAnalysis.sentiment_score <= filters.sentiment_max)
        if filters.min_sop_score is not None:
            agg_query = agg_query.filter(CallAnalysis.sop_compliance_score >= filters.min_sop_score)
        if filters.max_sop_score is not None:
            agg_query = agg_query.filter(CallAnalysis.sop_compliance_score <= filters.max_sop_score)
        
        agg_results = agg_query.all()
        
        # Calculate aggregates
        calls_by_outcome: Dict[str, int] = {}
        calls_by_rep: Dict[str, int] = {}
        calls_with_objections = 0
        objection_label_counts: Dict[str, int] = {}
        sentiment_scores = []
        sop_scores = []
        
        for call, analysis, lead, appointment in agg_results:
            # Outcome distribution
            outcome = _derive_outcome(call, lead, appointment)
            if outcome:
                calls_by_outcome[outcome] = calls_by_outcome.get(outcome, 0) + 1
            
            # Rep distribution
            rep_id = call.assigned_rep_id or (appointment.assigned_rep_id if appointment else None)
            if rep_id:
                calls_by_rep[rep_id] = calls_by_rep.get(rep_id, 0) + 1
            
            # Objections
            if analysis and analysis.objections:
                try:
                    if isinstance(analysis.objections, str):
                        objections_list = json.loads(analysis.objections)
                    else:
                        objections_list = analysis.objections
                    
                    if objections_list and len(objections_list) > 0:
                        calls_with_objections += 1
                        for label in objections_list:
                            objection_label_counts[str(label)] = objection_label_counts.get(str(label), 0) + 1
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Sentiment and SOP scores
            if analysis:
                if analysis.sentiment_score is not None:
                    sentiment_scores.append(analysis.sentiment_score)
                if analysis.sop_compliance_score is not None:
                    sop_scores.append(analysis.sop_compliance_score)
        
        # Calculate averages
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else None
        avg_sop_score = sum(sop_scores) / len(sop_scores) if sop_scores else None
        
        aggregates = AISearchAggregates(
            total_calls=total_count,
            calls_by_outcome=calls_by_outcome,
            calls_by_rep=calls_by_rep,
            calls_with_objections=calls_with_objections,
            objection_label_counts=objection_label_counts,
            avg_sentiment=round(avg_sentiment, 3) if avg_sentiment is not None else None,
            avg_sop_score=round(avg_sop_score, 2) if avg_sop_score is not None else None,
        )
    
    return AISearchResponse(
        calls=call_items,
        aggregates=aggregates,
    )



