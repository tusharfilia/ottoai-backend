from fastapi import APIRouter, Depends, HTTPException, Request, Query
from app.database import get_db
from app.models import call, company, sales_rep, sales_manager, scheduled_call, user
from app.models.call_analysis import CallAnalysis
from app.models.appointment import Appointment
from app.models.lead import Lead
from sqlalchemy.orm import Session, selectinload, joinedload
import json
from sqlalchemy import func, text, and_, or_, cast, Date
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel, Field
from app.services.bland_ai import BlandAI
from app.middleware.rbac import require_role
from app.middleware.tenant import get_tenant_id
from app.schemas.responses import APIResponse

router = APIRouter(prefix="/api/v1")

@router.post("/add-company")
@require_role("manager")  # Only managers can create companies
async def add_company(request: Request, db: Session = Depends(get_db)):
    params = dict(request.query_params)
    
    # Validate required fields
    if not params.get("name"):
        raise HTTPException(status_code=400, detail="Company name is required")
    if not params.get("address"):
        raise HTTPException(status_code=400, detail="Company address is required")
    
    # Check if company with this name already exists
    existing_company = db.query(company.Company)\
        .filter_by(name=params.get("name"))\
        .first()
    
    if existing_company:
        raise HTTPException(
            status_code=400,
            detail="Company with this name already exists"
        )
    
    # Create new company
    new_company = company.Company(
        name=params.get("name"),
        address=params.get("address"),
        phone_number=params.get("phone_number")  # Optional
    )
    
    db.add(new_company)
    db.commit()
    db.refresh(new_company)
    
    return {
        "status": "success",
        "company_id": new_company.id,
        "message": f"Company {new_company.name} created successfully"
    } 

@router.get("/companies")
@require_role("manager")  # Only managers can list all companies
async def list_companies(request: Request, db: Session = Depends(get_db)):
    # Get all companies
    companies = db.query(company.Company).order_by(company.Company.id.asc()).all()
    
    # Format the response
    return {
        "companies": [
            {
                "id": c.id,
                "name": c.name,
                "phone_number": c.phone_number,
                "address": c.address
            }
            for c in companies
        ],
        "total_companies": len(companies)
    }

@router.get("/dashboard/metrics")
@require_role("manager", "csr", "sales_rep")  # All authenticated roles can view metrics
async def get_dashboard_metrics(
    company_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    # Validate tenant_id from JWT matches company_id from query
    tenant_id = get_tenant_id(request)
    if company_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: company_id does not match your organization"
        )
    # Get base query for company's calls
    base_query = db.query(call.Call).filter_by(company_id=company_id)
    
    # Calculate total value lost from price_if_bought for lost sales
    value_lost = db.query(func.coalesce(func.sum(call.Call.price_if_bought), 0))\
        .filter(
            call.Call.company_id == company_id,
            call.Call.booked == True,
            call.Call.bought == False,
            call.Call.reason_for_lost_sale.isnot(None),
            call.Call.price_if_bought.isnot(None)
        ).scalar()
    
    # Add still deciding count
    still_deciding_count = db.query(call.Call).filter(
        call.Call.company_id == company_id,
        call.Call.still_deciding == True
    ).count()

    # Count calls with transcript discrepancies defined
    calls_with_discrepancies = db.query(call.Call).filter(
        call.Call.company_id == company_id,
        call.Call.transcript_discrepancies.isnot(None)
    ).all()
    
    # Count calls where has_discrepancies is true
    discrepancies_count = 0
    for c in calls_with_discrepancies:
        try:
            discrepancy_data = json.loads(c.transcript_discrepancies)
            if discrepancy_data.get("has_discrepancies") == True:
                discrepancies_count += 1
        except (json.JSONDecodeError, TypeError):
            # Skip if JSON is invalid or transcript_discrepancies is not a string
            pass

    metrics = {
        "still_deciding": base_query.filter_by(booked=True, still_deciding=True).count(),
        "awaiting_quote": base_query.filter_by(booked=True, bought=False, still_deciding=False, cancelled=False, reason_for_lost_sale=None).count(),
        "purchased_service": base_query.filter_by(bought=True, cancelled=False).count(),
        "missed_calls": base_query.filter_by(missed_call=True, cancelled=False).count(),
        "cancelled_appointments": base_query.filter_by(cancelled=True).count(),
        "discrepancies": discrepancies_count,
        "lost_quotes": {
            "total": base_query.filter(
                call.Call.booked == True,
                call.Call.bought == False,
                call.Call.reason_for_lost_sale.isnot(None)
            ).count(),
            "value_lost": float(value_lost or 0),  # Convert to float and handle None
            # "reasons": {
            #     "budget_constraints": base_query.filter(
            #         call.Call.reason_for_lost_sale.ilike('%budget%')
            #     ).count(),
            #     "changed_mind": base_query.filter(
            #         call.Call.reason_for_lost_sale.ilike('%changed mind%')
            #     ).count(),
            #     "chose_competitor": base_query.filter(
            #         call.Call.reason_for_lost_sale.ilike('%competitor%')
            #     ).count(),
            #     "decided_to_postpone": base_query.filter(
            #         call.Call.reason_for_lost_sale.ilike('%postpone%')
            #     ).count(),
            #     "insurance_denied": base_query.filter(
            #         call.Call.reason_for_lost_sale.ilike('%insurance%')
            #     ).count(),
            # }
        },
        "still_deciding_count": still_deciding_count
    }
    
    return metrics


class BookingRateDataPoint(BaseModel):
    """Single booking rate data point for chart."""
    date: str = Field(..., description="ISO date string (YYYY-MM-DD)")
    rate: float = Field(..., description="Booking rate percentage (0-100)")


@router.get("/dashboard/booking-rate", response_model=APIResponse[List[BookingRateDataPoint]])
@require_role("manager", "csr", "sales_rep")
async def get_booking_rate(
    request: Request,
    start_date: Optional[str] = Query(None, description="Start date (ISO format YYYY-MM-DD), defaults to 30 days ago"),
    end_date: Optional[str] = Query(None, description="End date (ISO format YYYY-MM-DD), defaults to today"),
    db: Session = Depends(get_db),
) -> APIResponse[List[BookingRateDataPoint]]:
    """
    Get time-series booking rate data for dashboard chart.
    
    Returns booking rate (percentage) per day for the specified date range.
    Booking rate = (booked appointments / qualified calls) * 100
    
    Default: last 30 days, grouped by day.
    Multi-tenant: scoped by company_id from JWT tenant context.
    """
    tenant_id = get_tenant_id(request)
    
    # Parse date range (default to last 30 days)
    # Handle YYYY-MM-DD format dates
    try:
        if end_date:
            end_dt = datetime.strptime(end_date.split('T')[0], '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        else:
            end_dt = datetime.utcnow().replace(hour=23, minute=59, second=59)
        
        if start_date:
            start_dt = datetime.strptime(start_date.split('T')[0], '%Y-%m-%d').replace(hour=0, minute=0, second=0)
        else:
            start_dt = (end_dt - timedelta(days=30)).replace(hour=0, minute=0, second=0)
        
        # Ensure start is before end
        if start_dt > end_dt:
            raise HTTPException(status_code=400, detail="start_date must be before end_date")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format. Use YYYY-MM-DD format. Error: {str(e)}")
    
    # Generate list of dates in range
    current_date = start_dt.date()
    end_date_obj = end_dt.date()
    date_list = []
    while current_date <= end_date_obj:
        date_list.append(current_date)
        current_date += timedelta(days=1)
    
    # Query booked appointments grouped by date
    booked_by_date = db.query(
        func.date(Appointment.scheduled_start).label('appointment_date'),
        func.count(Appointment.id).label('booked_count')
    ).filter(
        Appointment.company_id == tenant_id,
        Appointment.scheduled_start >= start_dt,
        Appointment.scheduled_start <= end_dt,
        Appointment.status.in_(['scheduled', 'confirmed', 'completed']),  # Count active appointments
    ).group_by(func.date(Appointment.scheduled_start)).all()
    
    booked_dict = {str(row.appointment_date): row.booked_count for row in booked_by_date}
    
    # Query qualified calls/leads grouped by date
    # Use calls that have lead_id (qualified) as denominator
    qualified_by_date = db.query(
        func.date(call.Call.created_at).label('call_date'),
        func.count(func.distinct(call.Call.call_id)).label('qualified_count')
    ).filter(
        call.Call.company_id == tenant_id,
        call.Call.created_at >= start_dt,
        call.Call.created_at <= end_dt,
        call.Call.lead_id.isnot(None),  # Only qualified calls have lead_id
    ).group_by(func.date(call.Call.created_at)).all()
    
    qualified_dict = {str(row.call_date): row.qualified_count for row in qualified_by_date}
    
    # Build response data points
    data_points = []
    for date_obj in date_list:
        date_str = date_obj.isoformat()
        booked = booked_dict.get(date_str, 0)
        qualified = qualified_dict.get(date_str, 0)
        
        # Calculate booking rate percentage
        if qualified > 0:
            rate = (booked / qualified) * 100.0
        else:
            rate = 0.0
        
        data_points.append(BookingRateDataPoint(
            date=date_str,
            rate=round(rate, 2)
        ))
    
    return APIResponse(data=data_points)


class TopObjectionItem(BaseModel):
    """Single objection item with label and percentage."""
    label: str = Field(..., description="Objection text or category")
    percentage: float = Field(..., description="Percentage (0-100) of calls with this objection")


@router.get("/dashboard/top-objections", response_model=APIResponse[List[TopObjectionItem]])
@require_role("manager", "csr", "sales_rep")
async def get_top_objections(
    request: Request,
    start_date: Optional[str] = Query(None, description="Start date (ISO format YYYY-MM-DD), defaults to 30 days ago"),
    end_date: Optional[str] = Query(None, description="End date (ISO format YYYY-MM-DD), defaults to today"),
    limit: int = Query(5, description="Maximum number of objections to return", ge=1, le=20),
    db: Session = Depends(get_db),
) -> APIResponse[List[TopObjectionItem]]:
    """
    Get top objections with percentages for dashboard.
    
    Returns objections aggregated from CallAnalysis.objections JSON field.
    Percentage represents share of calls with that objection among all calls that had objections.
    
    Default: last 30 days, top 5 objections.
    Multi-tenant: scoped by company_id from JWT tenant context.
    """
    tenant_id = get_tenant_id(request)
    
    # Parse date range (default to last 30 days)
    # Handle YYYY-MM-DD format dates
    try:
        if end_date:
            end_dt = datetime.strptime(end_date.split('T')[0], '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        else:
            end_dt = datetime.utcnow().replace(hour=23, minute=59, second=59)
        
        if start_date:
            start_dt = datetime.strptime(start_date.split('T')[0], '%Y-%m-%d').replace(hour=0, minute=0, second=0)
        else:
            start_dt = (end_dt - timedelta(days=30)).replace(hour=0, minute=0, second=0)
        
        # Ensure start is before end
        if start_dt > end_dt:
            raise HTTPException(status_code=400, detail="start_date must be before end_date")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format. Use YYYY-MM-DD format. Error: {str(e)}")
    
    # Query CallAnalysis records with objections in date range
    analyses = db.query(CallAnalysis).filter(
        CallAnalysis.tenant_id == tenant_id,
        CallAnalysis.analyzed_at >= start_dt,
        CallAnalysis.analyzed_at <= end_dt,
        CallAnalysis.objections.isnot(None),
    ).all()
    
    # Aggregate objections
    objection_counts = {}
    total_calls_with_objections = 0
    
    for analysis in analyses:
        if not analysis.objections:
            continue
        
        # Handle JSON array of objections
        objections_list = analysis.objections
        if isinstance(objections_list, str):
            try:
                objections_list = json.loads(objections_list)
            except (json.JSONDecodeError, TypeError):
                continue
        
        if not isinstance(objections_list, list):
            continue
        
        # Track unique objections per call
        call_objections = set()
        
        for obj in objections_list:
            if isinstance(obj, dict):
                # Extract objection label from dict
                obj_label = obj.get('label') or obj.get('type') or obj.get('objection_text') or str(obj)
            elif isinstance(obj, str):
                obj_label = obj
            else:
                obj_label = str(obj)
            
            if obj_label:
                call_objections.add(obj_label)
        
        # Count objections for this call
        for obj_label in call_objections:
            objection_counts[obj_label] = objection_counts.get(obj_label, 0) + 1
        
        if call_objections:
            total_calls_with_objections += 1
    
    # Convert to percentages and sort
    if total_calls_with_objections == 0:
        return APIResponse(data=[])
    
    objection_items = []
    for label, count in objection_counts.items():
        percentage = (count / total_calls_with_objections) * 100.0
        objection_items.append({
            'label': label,
            'percentage': round(percentage, 2),
            'count': count
        })
    
    # Sort by percentage descending and take top N
    objection_items.sort(key=lambda x: x['percentage'], reverse=True)
    top_objections = objection_items[:limit]
    
    # Build response
    response_items = [
        TopObjectionItem(label=item['label'], percentage=item['percentage'])
        for item in top_objections
    ]
    
    return APIResponse(data=response_items)


@router.get("/dashboard/calls")
@require_role("manager", "csr", "sales_rep")  # All authenticated roles can view calls
async def get_calls(
    status: str,
    company_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of calls to return"),
    offset: int = Query(0, ge=0, description="Number of calls to skip"),
    db: Session = Depends(get_db)
):
    # Validate tenant_id from JWT matches company_id from query
    tenant_id = get_tenant_id(request)
    if company_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: company_id does not match your organization"
        )
    query = db.query(call.Call).filter_by(company_id=company_id)
    
    if status == "cancelled":
        query = query.filter_by(cancelled=True)
    elif status == "awaiting_quote":
        # Apply filters directly (removed debug loop that loaded all calls)
        query = query.filter_by(booked=True, bought=False, still_deciding=False, cancelled=False, reason_for_lost_sale=None)
    elif status == "still_deciding":
        query = query.filter_by(booked=True, still_deciding=True)
    elif status == "purchased":
        query = query.filter_by(bought=True, cancelled=False)
    elif status == "missed":
        query = query.filter_by(missed_call=True, cancelled=False)
    elif status == "lost":
        query = query.filter(
            call.Call.booked == True,
            call.Call.bought == False,
            call.Call.reason_for_lost_sale.isnot(None)
        )
    elif status == "discrepancies":
        query = query.filter(call.Call.transcript_discrepancies.isnot(None))
        query = query.filter(
            text("(transcript_discrepancies::json->>'has_discrepancies') = 'true'")
        )
    
    # Apply pagination
    total_count = query.count()
    calls = query.order_by(call.Call.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "calls": calls,
        "total": total_count,
        "limit": limit,
        "offset": offset
    }

@router.get("/sales-managers")
@require_role("manager", "csr", "sales_rep")  # All authenticated roles can view managers
async def get_sales_managers(
    company_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    # Validate tenant_id from JWT matches company_id from query
    tenant_id = get_tenant_id(request)
    if str(company_id) != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: company_id does not match your organization"
        )
    managers = db.query(sales_manager.SalesManager)\
        .filter_by(company_id=company_id)\
        .all()
    return {
        "managers": [
            {
                "id": m.id,
                "name": m.name,
                "phone_number": m.phone_number,
            } for m in managers
        ]
    }

@router.get("/sales-reps")
@require_role("manager", "csr", "sales_rep")  # All authenticated roles can view sales reps
async def get_sales_reps(
    company_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    # Validate tenant_id from JWT matches company_id from query
    tenant_id = get_tenant_id(request)
    if company_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: company_id does not match your organization"
        )
    print(f"Fetching sales reps for company ID: {company_id!r}")
    
    # First check if the company exists
    company_obj = db.query(company.Company).filter(company.Company.id == company_id).first()
    if company_obj:
        print(f"Company exists with ID {company_id!r}, name: {company_obj.name}")
    else:
        print(f"WARNING: Company with ID {company_id!r} not found in database")
    
    # Check for all users in the database
    all_users = db.query(user.User).all()
    print(f"Total users in database: {len(all_users)}")
    
    # Get all sales reps without filtering
    all_reps = db.query(sales_rep.SalesRep).all()
    print(f"Total sales reps in database: {len(all_reps)}")
    for rep in all_reps:
        print(f"  Rep user_id: {rep.user_id}, company_id: {rep.company_id}")
    
    # Get sales reps with eager loading to avoid N+1 queries
    # Use joinedload to fetch user relationship in single query
    sales_reps = (
        db.query(sales_rep.SalesRep)
        .options(joinedload(sales_rep.SalesRep.user))
        .filter(sales_rep.SalesRep.company_id == company_id)
        .all()
    )
    
    # Build response (user is already loaded, no additional queries)
    return {
        "sales_reps": [
            {
                "id": sr.user_id,
                "name": sr.user.name if sr.user else "Unknown",
                "phone_number": sr.user.phone_number if sr.user else None,
                "manager_id": sr.manager_id
            } for sr in sales_reps
        ]
    }

# Note: Delete endpoints have been moved to delete.py

@router.get("/diagnostics")
@require_role("manager")  # Only managers can access diagnostics
async def get_diagnostics(request: Request, db: Session = Depends(get_db)):
    # Get all companies
    all_companies = db.query(company.Company).all()
    companies_data = []
    
    for comp in all_companies:
        # Count all calls for this company
        all_calls = db.query(call.Call).filter(call.Call.company_id == comp.id).all()
        # Count unassigned and booked calls
        unassigned_booked = db.query(call.Call).filter(
            call.Call.company_id == comp.id,
            call.Call.assigned_rep_id.is_(None),
            call.Call.booked.is_(True)
        ).all()
        # Count all sales reps for this company
        company_reps = db.query(sales_rep.SalesRep).filter(sales_rep.SalesRep.company_id == comp.id).all()
        
        companies_data.append({
            "company_id": comp.id,
            "company_name": comp.name,
            "total_calls": len(all_calls),
            "unassigned_booked_calls": len(unassigned_booked),
            "total_sales_reps": len(company_reps),
            "calls": [
                {
                    "call_id": c.call_id,
                    "name": c.name,
                    "booked": c.booked,
                    "assigned_rep_id": c.assigned_rep_id
                } for c in all_calls[:5]  # Just show first 5 for brevity
            ],
            "sales_reps": [
                {
                    "user_id": sr.user_id,
                    "manager_id": sr.manager_id
                } for sr in company_reps[:5]  # Just show first 5 for brevity
            ]
        })
    
    return {
        "total_companies": len(all_companies),
        "companies": companies_data
    }
    
    # Query CallAnalysis records with objections in date range
    analyses = db.query(CallAnalysis).filter(
        CallAnalysis.tenant_id == tenant_id,
        CallAnalysis.analyzed_at >= start_dt,
        CallAnalysis.analyzed_at <= end_dt,
        CallAnalysis.objections.isnot(None),
    ).all()
    
    # Aggregate objections
    objection_counts = {}
    total_calls_with_objections = 0
    
    for analysis in analyses:
        if not analysis.objections:
            continue
        
        # Handle JSON array of objections
        objections_list = analysis.objections
        if isinstance(objections_list, str):
            try:
                objections_list = json.loads(objections_list)
            except (json.JSONDecodeError, TypeError):
                continue
        
        if not isinstance(objections_list, list):
            continue
        
        # Track unique objections per call
        call_objections = set()
        
        for obj in objections_list:
            if isinstance(obj, dict):
                # Extract objection label from dict
                obj_label = obj.get('label') or obj.get('type') or obj.get('objection_text') or str(obj)
            elif isinstance(obj, str):
                obj_label = obj
            else:
                obj_label = str(obj)
            
            if obj_label:
                call_objections.add(obj_label)
        
        # Count objections for this call
        for obj_label in call_objections:
            objection_counts[obj_label] = objection_counts.get(obj_label, 0) + 1
        
        if call_objections:
            total_calls_with_objections += 1
    
    # Convert to percentages and sort
    if total_calls_with_objections == 0:
        return APIResponse(data=[])
    
    objection_items = []
    for label, count in objection_counts.items():
        percentage = (count / total_calls_with_objections) * 100.0
        objection_items.append({
            'label': label,
            'percentage': round(percentage, 2),
            'count': count
        })
    
    # Sort by percentage descending and take top N
    objection_items.sort(key=lambda x: x['percentage'], reverse=True)
    top_objections = objection_items[:limit]
    
    # Build response
    response_items = [
        TopObjectionItem(label=item['label'], percentage=item['percentage'])
        for item in top_objections
    ]
    
    return APIResponse(data=response_items)


@router.get("/dashboard/calls")
@require_role("manager", "csr", "sales_rep")  # All authenticated roles can view calls
async def get_calls(
    status: str,
    company_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of calls to return"),
    offset: int = Query(0, ge=0, description="Number of calls to skip"),
    db: Session = Depends(get_db)
):
    # Validate tenant_id from JWT matches company_id from query
    tenant_id = get_tenant_id(request)
    if company_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: company_id does not match your organization"
        )
    query = db.query(call.Call).filter_by(company_id=company_id)
    
    if status == "cancelled":
        query = query.filter_by(cancelled=True)
    elif status == "awaiting_quote":
        # Apply filters directly (removed debug loop that loaded all calls)
        query = query.filter_by(booked=True, bought=False, still_deciding=False, cancelled=False, reason_for_lost_sale=None)
    elif status == "still_deciding":
        query = query.filter_by(booked=True, still_deciding=True)
    elif status == "purchased":
        query = query.filter_by(bought=True, cancelled=False)
    elif status == "missed":
        query = query.filter_by(missed_call=True, cancelled=False)
    elif status == "lost":
        query = query.filter(
            call.Call.booked == True,
            call.Call.bought == False,
            call.Call.reason_for_lost_sale.isnot(None)
        )
    elif status == "discrepancies":
        query = query.filter(call.Call.transcript_discrepancies.isnot(None))
        query = query.filter(
            text("(transcript_discrepancies::json->>'has_discrepancies') = 'true'")
        )
    
    # Apply pagination
    total_count = query.count()
    calls = query.order_by(call.Call.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "calls": calls,
        "total": total_count,
        "limit": limit,
        "offset": offset
    }

@router.get("/sales-managers")
@require_role("manager", "csr", "sales_rep")  # All authenticated roles can view managers
async def get_sales_managers(
    company_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    # Validate tenant_id from JWT matches company_id from query
    tenant_id = get_tenant_id(request)
    if str(company_id) != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: company_id does not match your organization"
        )
    managers = db.query(sales_manager.SalesManager)\
        .filter_by(company_id=company_id)\
        .all()
    return {
        "managers": [
            {
                "id": m.id,
                "name": m.name,
                "phone_number": m.phone_number,
            } for m in managers
        ]
    }

@router.get("/sales-reps")
@require_role("manager", "csr", "sales_rep")  # All authenticated roles can view sales reps
async def get_sales_reps(
    company_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    # Validate tenant_id from JWT matches company_id from query
    tenant_id = get_tenant_id(request)
    if company_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: company_id does not match your organization"
        )
    print(f"Fetching sales reps for company ID: {company_id!r}")
    
    # First check if the company exists
    company_obj = db.query(company.Company).filter(company.Company.id == company_id).first()
    if company_obj:
        print(f"Company exists with ID {company_id!r}, name: {company_obj.name}")
    else:
        print(f"WARNING: Company with ID {company_id!r} not found in database")
    
    # Check for all users in the database
    all_users = db.query(user.User).all()
    print(f"Total users in database: {len(all_users)}")
    
    # Get all sales reps without filtering
    all_reps = db.query(sales_rep.SalesRep).all()
    print(f"Total sales reps in database: {len(all_reps)}")
    for rep in all_reps:
        print(f"  Rep user_id: {rep.user_id}, company_id: {rep.company_id}")
    
    # Get sales reps with eager loading to avoid N+1 queries
    # Use joinedload to fetch user relationship in single query
    sales_reps = (
        db.query(sales_rep.SalesRep)
        .options(joinedload(sales_rep.SalesRep.user))
        .filter(sales_rep.SalesRep.company_id == company_id)
        .all()
    )
    
    # Build response (user is already loaded, no additional queries)
    return {
        "sales_reps": [
            {
                "id": sr.user_id,
                "name": sr.user.name if sr.user else "Unknown",
                "phone_number": sr.user.phone_number if sr.user else None,
                "manager_id": sr.manager_id
            } for sr in sales_reps
        ]
    }

# Note: Delete endpoints have been moved to delete.py

@router.get("/diagnostics")
@require_role("manager")  # Only managers can access diagnostics
async def get_diagnostics(request: Request, db: Session = Depends(get_db)):
    # Get all companies
    all_companies = db.query(company.Company).all()
    companies_data = []
    
    for comp in all_companies:
        # Count all calls for this company
        all_calls = db.query(call.Call).filter(call.Call.company_id == comp.id).all()
        # Count unassigned and booked calls
        unassigned_booked = db.query(call.Call).filter(
            call.Call.company_id == comp.id,
            call.Call.assigned_rep_id.is_(None),
            call.Call.booked.is_(True)
        ).all()
        # Count all sales reps for this company
        company_reps = db.query(sales_rep.SalesRep).filter(sales_rep.SalesRep.company_id == comp.id).all()
        
        companies_data.append({
            "company_id": comp.id,
            "company_name": comp.name,
            "total_calls": len(all_calls),
            "unassigned_booked_calls": len(unassigned_booked),
            "total_sales_reps": len(company_reps),
            "calls": [
                {
                    "call_id": c.call_id,
                    "name": c.name,
                    "booked": c.booked,
                    "assigned_rep_id": c.assigned_rep_id
                } for c in all_calls[:5]  # Just show first 5 for brevity
            ],
            "sales_reps": [
                {
                    "user_id": sr.user_id,
                    "manager_id": sr.manager_id
                } for sr in company_reps[:5]  # Just show first 5 for brevity
            ]
        })
    
    return {
        "total_companies": len(all_companies),
        "companies": companies_data
    }
    
    # Query CallAnalysis records with objections in date range
    analyses = db.query(CallAnalysis).filter(
        CallAnalysis.tenant_id == tenant_id,
        CallAnalysis.analyzed_at >= start_dt,
        CallAnalysis.analyzed_at <= end_dt,
        CallAnalysis.objections.isnot(None),
    ).all()
    
    # Aggregate objections
    objection_counts = {}
    total_calls_with_objections = 0
    
    for analysis in analyses:
        if not analysis.objections:
            continue
        
        # Handle JSON array of objections
        objections_list = analysis.objections
        if isinstance(objections_list, str):
            try:
                objections_list = json.loads(objections_list)
            except (json.JSONDecodeError, TypeError):
                continue
        
        if not isinstance(objections_list, list):
            continue
        
        # Track unique objections per call
        call_objections = set()
        
        for obj in objections_list:
            if isinstance(obj, dict):
                # Extract objection label from dict
                obj_label = obj.get('label') or obj.get('type') or obj.get('objection_text') or str(obj)
            elif isinstance(obj, str):
                obj_label = obj
            else:
                obj_label = str(obj)
            
            if obj_label:
                call_objections.add(obj_label)
        
        # Count objections for this call
        for obj_label in call_objections:
            objection_counts[obj_label] = objection_counts.get(obj_label, 0) + 1
        
        if call_objections:
            total_calls_with_objections += 1
    
    # Convert to percentages and sort
    if total_calls_with_objections == 0:
        return APIResponse(data=[])
    
    objection_items = []
    for label, count in objection_counts.items():
        percentage = (count / total_calls_with_objections) * 100.0
        objection_items.append({
            'label': label,
            'percentage': round(percentage, 2),
            'count': count
        })
    
    # Sort by percentage descending and take top N
    objection_items.sort(key=lambda x: x['percentage'], reverse=True)
    top_objections = objection_items[:limit]
    
    # Build response
    response_items = [
        TopObjectionItem(label=item['label'], percentage=item['percentage'])
        for item in top_objections
    ]
    
    return APIResponse(data=response_items)


@router.get("/dashboard/calls")
@require_role("manager", "csr", "sales_rep")  # All authenticated roles can view calls
async def get_calls(
    status: str,
    company_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of calls to return"),
    offset: int = Query(0, ge=0, description="Number of calls to skip"),
    db: Session = Depends(get_db)
):
    # Validate tenant_id from JWT matches company_id from query
    tenant_id = get_tenant_id(request)
    if company_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: company_id does not match your organization"
        )
    query = db.query(call.Call).filter_by(company_id=company_id)
    
    if status == "cancelled":
        query = query.filter_by(cancelled=True)
    elif status == "awaiting_quote":
        # Apply filters directly (removed debug loop that loaded all calls)
        query = query.filter_by(booked=True, bought=False, still_deciding=False, cancelled=False, reason_for_lost_sale=None)
    elif status == "still_deciding":
        query = query.filter_by(booked=True, still_deciding=True)
    elif status == "purchased":
        query = query.filter_by(bought=True, cancelled=False)
    elif status == "missed":
        query = query.filter_by(missed_call=True, cancelled=False)
    elif status == "lost":
        query = query.filter(
            call.Call.booked == True,
            call.Call.bought == False,
            call.Call.reason_for_lost_sale.isnot(None)
        )
    elif status == "discrepancies":
        query = query.filter(call.Call.transcript_discrepancies.isnot(None))
        query = query.filter(
            text("(transcript_discrepancies::json->>'has_discrepancies') = 'true'")
        )
    
    # Apply pagination
    total_count = query.count()
    calls = query.order_by(call.Call.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "calls": calls,
        "total": total_count,
        "limit": limit,
        "offset": offset
    }

@router.get("/sales-managers")
@require_role("manager", "csr", "sales_rep")  # All authenticated roles can view managers
async def get_sales_managers(
    company_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    # Validate tenant_id from JWT matches company_id from query
    tenant_id = get_tenant_id(request)
    if str(company_id) != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: company_id does not match your organization"
        )
    managers = db.query(sales_manager.SalesManager)\
        .filter_by(company_id=company_id)\
        .all()
    return {
        "managers": [
            {
                "id": m.id,
                "name": m.name,
                "phone_number": m.phone_number,
            } for m in managers
        ]
    }

@router.get("/sales-reps")
@require_role("manager", "csr", "sales_rep")  # All authenticated roles can view sales reps
async def get_sales_reps(
    company_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    # Validate tenant_id from JWT matches company_id from query
    tenant_id = get_tenant_id(request)
    if company_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: company_id does not match your organization"
        )
    print(f"Fetching sales reps for company ID: {company_id!r}")
    
    # First check if the company exists
    company_obj = db.query(company.Company).filter(company.Company.id == company_id).first()
    if company_obj:
        print(f"Company exists with ID {company_id!r}, name: {company_obj.name}")
    else:
        print(f"WARNING: Company with ID {company_id!r} not found in database")
    
    # Check for all users in the database
    all_users = db.query(user.User).all()
    print(f"Total users in database: {len(all_users)}")
    
    # Get all sales reps without filtering
    all_reps = db.query(sales_rep.SalesRep).all()
    print(f"Total sales reps in database: {len(all_reps)}")
    for rep in all_reps:
        print(f"  Rep user_id: {rep.user_id}, company_id: {rep.company_id}")
    
    # Get sales reps with eager loading to avoid N+1 queries
    # Use joinedload to fetch user relationship in single query
    sales_reps = (
        db.query(sales_rep.SalesRep)
        .options(joinedload(sales_rep.SalesRep.user))
        .filter(sales_rep.SalesRep.company_id == company_id)
        .all()
    )
    
    # Build response (user is already loaded, no additional queries)
    return {
        "sales_reps": [
            {
                "id": sr.user_id,
                "name": sr.user.name if sr.user else "Unknown",
                "phone_number": sr.user.phone_number if sr.user else None,
                "manager_id": sr.manager_id
            } for sr in sales_reps
        ]
    }

# Note: Delete endpoints have been moved to delete.py

@router.get("/diagnostics")
@require_role("manager")  # Only managers can access diagnostics
async def get_diagnostics(request: Request, db: Session = Depends(get_db)):
    # Get all companies
    all_companies = db.query(company.Company).all()
    companies_data = []
    
    for comp in all_companies:
        # Count all calls for this company
        all_calls = db.query(call.Call).filter(call.Call.company_id == comp.id).all()
        # Count unassigned and booked calls
        unassigned_booked = db.query(call.Call).filter(
            call.Call.company_id == comp.id,
            call.Call.assigned_rep_id.is_(None),
            call.Call.booked.is_(True)
        ).all()
        # Count all sales reps for this company
        company_reps = db.query(sales_rep.SalesRep).filter(sales_rep.SalesRep.company_id == comp.id).all()
        
        companies_data.append({
            "company_id": comp.id,
            "company_name": comp.name,
            "total_calls": len(all_calls),
            "unassigned_booked_calls": len(unassigned_booked),
            "total_sales_reps": len(company_reps),
            "calls": [
                {
                    "call_id": c.call_id,
                    "name": c.name,
                    "booked": c.booked,
                    "assigned_rep_id": c.assigned_rep_id
                } for c in all_calls[:5]  # Just show first 5 for brevity
            ],
            "sales_reps": [
                {
                    "user_id": sr.user_id,
                    "manager_id": sr.manager_id
                } for sr in company_reps[:5]  # Just show first 5 for brevity
            ]
        })
    
    return {
        "total_companies": len(all_companies),
        "companies": companies_data    
        }
