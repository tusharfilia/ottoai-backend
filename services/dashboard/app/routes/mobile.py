from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import call, sales_rep, sales_manager, company, user
from datetime import datetime, timedelta
from app.services.bland_ai import BlandAI
import json

router = APIRouter()

@router.post("/mobile/register-push-token")
async def register_push_token(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Endpoint for mobile app to register the user's Expo push token (works for both sales reps and managers)
    """
    try:
        params = dict(request.query_params)
        
        # Validate required parameters
        if not params.get("user_id"):
            raise HTTPException(status_code=400, detail="user_id is required")
        
        if not params.get("expo_push_token"):
            raise HTTPException(status_code=400, detail="expo_push_token is required")
        
        # Get the user record to determine their role
        user_record = db.query(user.User).filter_by(id=params.get("user_id")).first()
        if not user_record:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Handle based on user role
        if user_record.role == "manager":
            # Update sales manager record
            manager_record = db.query(sales_manager.SalesManager).filter_by(user_id=params.get("user_id")).first()
            if not manager_record:
                # Create a new sales manager record if it doesn't exist
                manager_record = sales_manager.SalesManager(
                    user_id=params.get("user_id"),
                    company_id=user_record.company_id
                )
                db.add(manager_record)
            
            manager_record.expo_push_token = params.get("expo_push_token")
            
        else:
            # Handle sales rep
            sales_rep_record = db.query(sales_rep.SalesRep).filter_by(user_id=params.get("user_id")).first()
            if not sales_rep_record:
                # Create a new sales rep record if it doesn't exist
                sales_rep_record = sales_rep.SalesRep(
                    user_id=params.get("user_id"),
                    company_id=user_record.company_id
                )
                db.add(sales_rep_record)
            
            sales_rep_record.expo_push_token = params.get("expo_push_token")
        
        db.commit()
        
        return {
            "success": True,
            "message": "Push token registered successfully",
            "user_id": params.get("user_id"),
            "role": user_record.role
        }
        
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"Error registering push token: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/mobile/sales-report/submit")
async def submit_sales_report(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Endpoint for sales reps to submit sales report data through the mobile app
    when recording fails or is incomplete.
    """
    try:
        params = dict(request.query_params)
        
        # Validate required parameters
        if not params.get("call_id"):
            raise HTTPException(status_code=400, detail="call_id is required")
        
        if "bought" not in params:
            raise HTTPException(status_code=400, detail="bought status is required")
        
        # Parse boolean parameters
        bought = params.get("bought").lower() == "true"
        still_deciding = params.get("still_deciding", "").lower() == "true"
        
        # Get the call record
        call_record = db.query(call.Call).filter_by(call_id=params.get("call_id")).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call record not found")
        
        # Update call record with sales report data
        call_record.bought = bought
        call_record.updated_at = datetime.utcnow()
        
        # Add price if provided and sale was made
        if bought and params.get("price_if_bought"):
            try:
                call_record.price_if_bought = float(params.get("price_if_bought"))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid price format")
        
        # Handle still deciding status
        call_record.still_deciding = still_deciding
        if still_deciding and params.get("reason_for_deciding"):
            call_record.reason_for_deciding = params.get("reason_for_deciding")
        
        # Handle lost sale reason
        if not bought and not still_deciding and params.get("reason_for_lost_sale"):
            call_record.reason_for_lost_sale = params.get("reason_for_lost_sale")
        
        # Commit changes to database
        db.commit()
        
        # Only schedule a follow-up call to the customer when needed
        # Get company name
        company_name = None
        company_address = None
        if call_record.company_id:
            company_record = db.query(company.Company).filter_by(id=call_record.company_id).first()
            if company_record:
                company_name = company_record.name
                company_address = company_record.address
        
        # Get sales rep name
        sales_rep_name = None
        if call_record.assigned_rep_id:
            rep = db.query(sales_rep.SalesRep).filter_by(user_id=call_record.assigned_rep_id).first()
            if rep:
                user_record = db.query(user.User).filter_by(id=rep.user_id).first()
                if user_record:
                    sales_rep_name = user_record.name
        
        # Create customer info dict
        request_data = {
            "name": call_record.name,
            "phone": call_record.phone_number,
            "address": call_record.address,
            "quote_date": call_record.quote_date.isoformat() if call_record.quote_date else None,
            "company_name": company_name,
            "sales_rep_name": sales_rep_name,
            "bought": bought,
            "still_deciding": still_deciding
        }
        
        # Schedule follow-up call to customer if needed
        outbound_call_scheduled = False
        if not bought and not still_deciding:
            # Initialize BlandAI service
            bland_ai = BlandAI()
            
            # Let the service determine the appropriate call time based on local timezone
            background_tasks.add_task(
                bland_ai.make_followup_call,
                customer_phone=call_record.phone_number,
                request_data=request_data,
                reason_for_lost_sale=call_record.reason_for_lost_sale or "General followup",
                call_record_id=call_record.call_id,
                db=db
                # No start_time - let the service determine it based on address
            )
            outbound_call_scheduled = True
        
        return {
            "success": True,
            "message": "Sales report submitted successfully",
            "call_id": call_record.call_id,
            "outbound_call_scheduled": outbound_call_scheduled
        }
        
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"Error submitting sales report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/mobile/check-missing-reports")
async def check_missing_reports(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Endpoint to check for appointments that should have reports by now
    but don't have recording or sales outcome data.
    """
    try:
        # Look for appointments in the past 48 hours
        cutoff_time = datetime.utcnow() - timedelta(hours=48)
        
        # Find appointments where recording is missing and no sales outcome is recorded
        missing_reports = db.query(call.Call).filter(
            call.Call.quote_date < datetime.utcnow(),
            call.Call.quote_date > cutoff_time,
            call.Call.assigned_rep_id.isnot(None),
            call.Call.booked == True,
            call.Call.bought.is_(None),
            call.Call.still_deciding.is_(None),
            call.Call.recording_duration_s.is_(None) | (call.Call.recording_duration_s < 60)
        ).all()
        
        return {
            "success": True,
            "missing_reports_count": len(missing_reports),
            "missing_reports": [
                {
                    "call_id": report.call_id,
                    "customer_name": report.name,
                    "appointment_date": report.quote_date.isoformat() if report.quote_date else None,
                    "assigned_rep_id": report.assigned_rep_id
                }
                for report in missing_reports
            ]
        }
    except Exception as e:
        print(f"Error checking missing reports: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") 