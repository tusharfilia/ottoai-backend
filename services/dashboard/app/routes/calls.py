from fastapi import APIRouter, Depends, HTTPException, Request
from app.database import get_db
from app.models import call, company
from app.models.call_analysis import CallAnalysis
from app.core.tenant import get_tenant_id
from app.middleware.rbac import require_role
from sqlalchemy.orm import Session
from datetime import datetime
from fastapi import BackgroundTasks
from sqlalchemy import and_
from typing import List, Optional
from ..services.manager_notification_service import send_unassigned_appointment_notification
from app.services.domain_entities import ensure_contact_card_and_lead
from app.services.uwc_client import get_uwc_client
from app.schemas.responses import APIResponse
from uuid import uuid4
import logging
import traceback

router = APIRouter()
logger = logging.getLogger(__name__)

# Note: Delete endpoints have been moved to delete.py

@router.get("/call/{call_id}")
@require_role("manager", "csr", "sales_rep")
async def get_call_details(
    request: Request,
    call_id: int,
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    # Tenant isolation: tenant_id is automatically enforced by get_db dependency
    # No need to manually verify company - tenant scoping is automatic
    
    # Get call details (tenant-scoped automatically)
    call_record = db.query(call.Call)\
        .filter_by(call_id=call_id)\
        .first()
    
    if not call_record:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Convert to dict for JSON serialization
    call_data = {
        "call_id": call_record.call_id,
        "name": call_record.name,
        "phone_number": call_record.phone_number,
        "address": call_record.address,
        "created_at": call_record.created_at.isoformat() if call_record.created_at else None,
        "quote_date": call_record.quote_date.isoformat() if call_record.quote_date else None,
        "price_if_bought": float(call_record.price_if_bought) if call_record.price_if_bought else None,
        "reason_for_lost_sale": call_record.reason_for_lost_sale,
        "booked": call_record.booked,
        "bought": call_record.bought,
        "missed_call": call_record.missed_call,
        "cancelled": call_record.cancelled,
        "reason_for_cancellation": call_record.reason_for_cancellation,
        "transcript": call_record.transcript,
        "homeowner_followup_transcript": call_record.homeowner_followup_transcript,
        "in_person_transcript": call_record.in_person_transcript,
        "mobile_transcript": call_record.mobile_transcript,
        "mobile_calls_count": call_record.mobile_calls_count or 0,
        "mobile_texts_count": call_record.mobile_texts_count or 0,
        "assigned_rep_id": call_record.assigned_rep_id,
        "reason_not_bought_homeowner": call_record.reason_not_bought_homeowner,
        "transcript_discrepancies": call_record.transcript_discrepancies,
        "problem": call_record.problem,
        "still_deciding": call_record.still_deciding,
        "reason_for_deciding": call_record.reason_for_deciding,
        "call_sid": call_record.call_sid,
        "last_call_status": call_record.last_call_status,
        "last_call_timestamp": call_record.last_call_timestamp,
        "last_call_duration": call_record.last_call_duration
    }
    
    return call_data

@router.get("/unassigned-calls")
@require_role("manager")
async def get_unassigned_calls(
    request: Request, 
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    # Tenant isolation: tenant_id is automatically enforced by get_db dependency
    # All queries are automatically scoped to the tenant
    
    # Get the unassigned calls (tenant-scoped automatically)
    calls = db.query(call.Call)\
        .filter(
            call.Call.assigned_rep_id.is_(None),
            call.Call.booked.is_(True)  # Only show booked calls that need assignment
        )\
        .order_by(call.Call.created_at.desc())\
        .all()
    
    print(f"Found {len(calls)} unassigned+booked calls")
    for c in calls:
        print(f"  Call ID: {c.call_id}, Name: {c.name}, Booked: {c.booked}, Assigned Rep ID: {c.assigned_rep_id}")
    
    return {
        "calls": [
            {
                "id": c.call_id,  # Use call_id as the id field expected by frontend
                "name": c.name,
                "phone_number": c.phone_number,
                "quote_date": c.quote_date,
                "created_at": c.created_at
            } for c in calls
        ]
    }


@router.post("/add-call")
@require_role("manager", "csr")
async def add_call(
    request: Request,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    params = dict(request.query_params)
    
    # Tenant isolation: tenant_id is automatically enforced by get_db dependency
    # No need to manually verify company - tenant scoping is automatic
    
    # Create new call record with tenant context
    phone_number = params.get("phone_number")
    if not phone_number:
        raise HTTPException(status_code=400, detail="phone_number is required")

    contact_card, lead = ensure_contact_card_and_lead(
        db,
        company_id=tenant_id,
        phone_number=phone_number,
    )

    new_call = call.Call(
        phone_number=phone_number,
        name=params.get("name"),
        address=params.get("address"),
        quote_date=datetime.strptime(params.get("quote_date"), "%Y-%m-%d %H:%M:%S") if params.get("quote_date") else None,
        booked=params.get("booked", "false").lower() == "true",
        transcript=params.get("transcript"),
        missed_call=params.get("missed_call", "false").lower() == "true",
        created_at=datetime.utcnow(),
        company_id=tenant_id,  # Use tenant_id from context
        contact_card_id=contact_card.id,
        lead_id=lead.id,
        bland_call_id=params.get("bland_call_id")
    )
    
    db.add(new_call)
    db.commit()
    db.refresh(new_call)
    
    # If the call is booked and has an address, create a geofence in the background
    if new_call.booked and new_call.address:
        from app.routes.mobile_routes.location_geofence_stuff import create_geofence_for_call
        background_tasks.add_task(create_geofence_for_call, new_call.call_id, db)
    
    # If the call is booked and not assigned to a rep, send a notification to managers
    if new_call.booked and not new_call.assigned_rep_id:
        logger.info(f"Sending notification to managers for unassigned call {new_call.call_id}")
        # Use background task so the notification doesn't block the response
        background_tasks.add_task(
            send_unassigned_appointment_notification,
            db,
            new_call.company_id,
            new_call.call_id,
            new_call.name,
            new_call.quote_date.isoformat() if new_call.quote_date else None
        )
    
    return {
        "status": "success",
        "call_id": new_call.call_id,
        "message": "Call record created successfully"
    }

@router.post("/update-call-status")
async def update_call_status(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Update a call's status (bought/not bought) and automatically handle geofence removal
    """
    data = await request.json()
    
    # Validate required fields
    if not data.get("call_id"):
        raise HTTPException(status_code=400, detail="Call ID is required")
    
    # Get the call
    call_record = db.query(call.Call).filter(call.Call.call_id == data.get("call_id")).first()
    if not call_record:
        raise HTTPException(status_code=404, detail=f"Call with ID {data.get('call_id')} not found")
    
    # Track if we need to remove geofence
    should_remove_geofence = False
    previous_status = {
        "bought": call_record.bought,
        "cancelled": call_record.cancelled
    }
    
    # Track the previous rep ID to check if rep changed
    previous_rep_id = call_record.assigned_rep_id
    
    # Update call status fields
    if "bought" in data:
        call_record.bought = data["bought"]
        # If bought status changed to true or explicitly set to false, we should remove geofence
        if data["bought"] or (not data["bought"] and "bought" in data):
            should_remove_geofence = True
        
    if "price_if_bought" in data and call_record.bought:
        call_record.price_if_bought = data["price_if_bought"]
        
    if "reason_not_bought_homeowner" in data and not call_record.bought:
        call_record.reason_not_bought_homeowner = data["reason_not_bought_homeowner"]
        should_remove_geofence = True  # If providing reason for not buying, remove geofence
    
    if "cancelled" in data:
        call_record.cancelled = data["cancelled"]
        if data["cancelled"]:
            should_remove_geofence = True  # If cancelled, remove geofence
            
    if "reason_for_cancellation" in data and call_record.cancelled:
        call_record.reason_for_cancellation = data["reason_for_cancellation"]
        
    if "rescheduled" in data:
        call_record.rescheduled = data["rescheduled"]
        
    if "quote_date" in data:
        try:
            call_record.quote_date = datetime.fromisoformat(data["quote_date"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS).")
    
    # Handle assigned_rep_id updates
    if "assigned_rep_id" in data:
        call_record.assigned_rep_id = data["assigned_rep_id"]
        
        # If a rep is assigned and the call has an address but no geofence yet, create one
        if call_record.assigned_rep_id and call_record.address and not call_record.geofence and not call_record.cancelled:
            from app.routes.mobile_routes.location_geofence_stuff import create_geofence_for_call
            background_tasks.add_task(create_geofence_for_call, call_record.call_id, db)
        
        # Sync geofences for both the old rep and new rep if there's a change
        if call_record.assigned_rep_id != previous_rep_id:
            from app.routes.mobile_routes.location_geofence_stuff import sync_rep_geofences
            
            # Sync new rep's geofences
            if call_record.assigned_rep_id:
                background_tasks.add_task(sync_rep_geofences, call_record.assigned_rep_id, db)
            
            # Also sync previous rep's geofences if there was one
            if previous_rep_id:
                background_tasks.add_task(sync_rep_geofences, previous_rep_id, db)
    
    # Remove geofence if needed
    if should_remove_geofence and call_record.assigned_rep_id:
        # If a call has assigned rep and geofence needs to be removed
        from app.models.sales_rep import SalesRep
        
        sales_rep = db.query(SalesRep).filter(SalesRep.user_id == call_record.assigned_rep_id).first()
        if sales_rep and sales_rep.active_geofences:
            # If rep has active geofences, filter out this call's geofence
            active_geofences = sales_rep.active_geofences
            if isinstance(active_geofences, list):
                # Check if we actually have a geofence for this call
                had_geofence = any(g.get("call_id") == call_record.call_id for g in active_geofences)
                
                if had_geofence:
                    # Remove geofence for this call
                    active_geofences = [g for g in active_geofences if g.get("call_id") != call_record.call_id]
                    
                    # Update sales rep
                    sales_rep.active_geofences = active_geofences
                    
                    # Clear geofence data from the call
                    call_record.geofence = None
                    
                    print(f"Removed geofence for call {call_record.call_id} from rep {sales_rep.user_id}")
    
    # Save changes
    db.commit()
    
    return {
        "status": "success",
        "message": f"Call {call_record.call_id} status updated successfully",
        "geofence_removed": should_remove_geofence
    }


@router.get("/api/v1/calls/{call_id}/followup-recommendations", response_model=APIResponse[dict])
@require_role("csr", "manager")
async def get_followup_recommendations(
    request: Request,
    call_id: int,
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get follow-up recommendations for a call.
    
    Returns AI-generated follow-up recommendations from Shunya analysis,
    including action items, next steps, and priority actions.
    
    RBAC: csr, manager
    """
    # Verify call exists and belongs to tenant
    call_record = db.query(call.Call)\
        .filter(
            call.Call.call_id == call_id,
            call.Call.company_id == tenant_id
        )\
        .first()
    
    if not call_record:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Get CallAnalysis for this call
    call_analysis = db.query(CallAnalysis)\
        .filter(
            CallAnalysis.call_id == call_id,
            CallAnalysis.tenant_id == tenant_id
        )\
        .order_by(CallAnalysis.analyzed_at.desc())\
        .first()
    
    if not call_analysis:
        # Return empty structure if no analysis exists yet
        return APIResponse(
            success=True,
            data={
                "recommendations": [],
                "next_steps": [],
                "priority_actions": [],
                "confidence_score": None,
                "status": "no_analysis"
            }
        )
    
    # Return follow-up recommendations (or empty structure if not available)
    followup_recommendations = call_analysis.followup_recommendations or {
        "recommendations": [],
        "next_steps": [],
        "priority_actions": [],
        "confidence_score": None
    }
    
    return APIResponse(
        success=True,
        data=followup_recommendations
    )


@router.post("/api/v1/compliance/run/{call_id}", response_model=APIResponse[dict])
@require_role("csr", "manager")
async def run_compliance_check(
    request: Request,
    call_id: int,
    force: bool = False,  # If True, re-run even if compliance already exists
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Run a new SOP compliance check for a call.
    
    This endpoint triggers a fresh compliance check via Shunya's POST endpoint
    and updates the CallAnalysis record with the results.
    
    RBAC: csr, manager
    
    Args:
        call_id: Call ID to run compliance check for
        force: If True, re-run compliance check even if results already exist
    """
    from app.services.uwc_client import get_uwc_client
    from uuid import uuid4
    
    # Verify call exists and belongs to tenant
    call_record = db.query(call.Call)\
        .filter(
            call.Call.call_id == call_id,
            call.Call.company_id == tenant_id
        )\
        .first()
    
    if not call_record:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Get or create CallAnalysis for this call
    call_analysis = db.query(CallAnalysis)\
        .filter(
            CallAnalysis.call_id == call_id,
            CallAnalysis.tenant_id == tenant_id
        )\
        .order_by(CallAnalysis.analyzed_at.desc())\
        .first()
    
    if not call_analysis:
        raise HTTPException(
            status_code=404,
            detail="Call analysis not found. Please run call analysis first."
        )
    
    # Idempotency check: if compliance already exists and force=False, return existing
    if not force and (
        call_analysis.compliance_violations is not None or
        call_analysis.compliance_positive_behaviors is not None or
        call_analysis.compliance_recommendations is not None
    ):
        # Return existing compliance data
        return APIResponse(
            success=True,
            data={
                "compliance_score": call_analysis.sop_compliance_score,
                "stages_followed": call_analysis.sop_stages_completed or [],
                "stages_missed": call_analysis.sop_stages_missed or [],
                "violations": call_analysis.compliance_violations or [],
                "positive_behaviors": call_analysis.compliance_positive_behaviors or [],
                "recommendations": call_analysis.compliance_recommendations or [],
                "status": "existing"
            }
        )
    
    # Run compliance check via Shunya
    try:
        uwc_client = get_uwc_client()
        
        # Map user role to Shunya target_role
        user_role = getattr(request.state, 'user_role', 'csr')
        target_role = uwc_client._map_otto_role_to_shunya_target_role(user_role)
        
        # Run compliance check
        compliance_request_id = str(uuid4())
        compliance_result = await uwc_client.run_compliance_check(
            call_id=call_id,
            company_id=tenant_id,
            request_id=compliance_request_id,
            target_role=target_role
        )
        
        # Update CallAnalysis with compliance results
        if compliance_result:
            # Update compliance score if provided
            if compliance_result.get("compliance_score") is not None:
                call_analysis.sop_compliance_score = compliance_result["compliance_score"]
            
            # Update stages (merge with existing if any)
            if compliance_result.get("stages_followed"):
                existing_stages = call_analysis.sop_stages_completed or []
                merged_stages = list(set(existing_stages + compliance_result["stages_followed"]))
                call_analysis.sop_stages_completed = merged_stages
            
            if compliance_result.get("stages_missed"):
                existing_missed = call_analysis.sop_stages_missed or []
                merged_missed = list(set(existing_missed + compliance_result["stages_missed"]))
                call_analysis.sop_stages_missed = merged_missed
            
            # Store detailed compliance data
            call_analysis.compliance_violations = compliance_result.get("violations", [])
            call_analysis.compliance_positive_behaviors = compliance_result.get("positive_behaviors", [])
            call_analysis.compliance_recommendations = compliance_result.get("recommendations", [])
            
            db.commit()
            
            logger.info(
                f"Compliance check completed for call {call_id}",
                extra={
                    "call_id": call_id,
                    "compliance_score": compliance_result.get("compliance_score"),
                    "violations_count": len(compliance_result.get("violations", []))
                }
            )
            
            return APIResponse(
                success=True,
                data={
                    "compliance_score": compliance_result.get("compliance_score"),
                    "stages_followed": compliance_result.get("stages_followed", []),
                    "stages_missed": compliance_result.get("stages_missed", []),
                    "violations": compliance_result.get("violations", []),
                    "positive_behaviors": compliance_result.get("positive_behaviors", []),
                    "recommendations": compliance_result.get("recommendations", []),
                    "status": "completed"
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Compliance check returned empty result"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to run compliance check for call {call_id}: {str(e)}",
            extra={"call_id": call_id},
            exc_info=True
        )
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run compliance check: {str(e)}"
        ) 