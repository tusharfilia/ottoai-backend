from fastapi import APIRouter, Depends, HTTPException, Request
from app.database import get_db
from app.models import call, company, sales_rep, sales_manager, scheduled_call, user
from sqlalchemy.orm import Session
import json
from sqlalchemy import func, text
from datetime import datetime, timedelta
from app.services.bland_ai import BlandAI

router = APIRouter()

@router.post("/add-company")
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
async def list_companies(db: Session = Depends(get_db)):
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
async def get_dashboard_metrics(company_id: str, db: Session = Depends(get_db)):
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

@router.get("/dashboard/calls")
async def get_calls(
    status: str,
    company_id: str,
    db: Session = Depends(get_db)
):
    query = db.query(call.Call).filter_by(company_id=company_id)
    
    if status == "cancelled":
        query = query.filter_by(cancelled=True)
    elif status == "awaiting_quote":
        print(f"=== QUERYING AWAITING_QUOTE CALLS ===")
        # Debug all calls for this company first
        all_company_calls = db.query(call.Call).filter_by(company_id=company_id).all()
        print(f"Total calls for company {company_id}: {len(all_company_calls)}")
        
        # Check each call against criteria 
        for c in all_company_calls:
            booked_status = "✓" if c.booked else "✗"
            bought_status = "✓" if c.bought else "✗" 
            deciding_status = "✓" if c.still_deciding else "✗"
            cancelled_status = "✓" if c.cancelled else "✗"
            lost_status = "✓" if c.reason_for_lost_sale else "✗"
            
            # Calculate if it meets all awaiting_quote criteria
            meets_criteria = (
                c.booked and 
                not c.bought and 
                not c.still_deciding and 
                not c.cancelled and 
                not c.reason_for_lost_sale
            )
            criteria_status = "MEETS CRITERIA ✓" if meets_criteria else "FAILS CRITERIA ✗"
            
            print(f"Call ID: {c.call_id} | Booked: {booked_status} | Bought: {bought_status} | " +
                  f"Still Deciding: {deciding_status} | Cancelled: {cancelled_status} | " +
                  f"Lost Sale Reason: {lost_status} | {criteria_status}")
        
        # Now apply filters
        query = query.filter_by(booked=True, bought=False, still_deciding=False, cancelled=False, reason_for_lost_sale=None)
        # Get the filtered count for debugging
        awaiting_count = query.count()
        print(f"After filtering, {awaiting_count} calls match awaiting_quote criteria")
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
    
    calls = query.order_by(call.Call.created_at.desc()).all()
    return {"calls": calls}

@router.get("/sales-managers")
async def get_sales_managers(company_id: int, db: Session = Depends(get_db)):
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
async def get_sales_reps(company_id: str, db: Session = Depends(get_db)):
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
    
    # Now get sales reps for this company
    sales_reps = db.query(sales_rep.SalesRep).filter(sales_rep.SalesRep.company_id == company_id).all()
    print(f"Found {len(sales_reps)} sales reps for company {company_id!r}")
    for sr in sales_reps:
        user_obj = db.query(user.User).filter(user.User.id == sr.user_id).first()
        if user_obj:
            print(f"  Rep user_id: {sr.user_id}, name: {user_obj.name}, company_id: {sr.company_id}")
        else:
            print(f"  Rep user_id: {sr.user_id}, NO USER FOUND, company_id: {sr.company_id}")
    
    return {
        "sales_reps": [
            {
                "id": sr.user_id,
                "name": db.query(user.User).filter(user.User.id == sr.user_id).first().name if db.query(user.User).filter(user.User.id == sr.user_id).first() else "Unknown",
                "phone_number": db.query(user.User).filter(user.User.id == sr.user_id).first().phone_number if db.query(user.User).filter(user.User.id == sr.user_id).first() else None, 
                "manager_id": sr.manager_id
            } for sr in sales_reps
        ]
    }

# Note: Delete endpoints have been moved to delete.py

@router.get("/diagnostics")
async def get_diagnostics(db: Session = Depends(get_db)):
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