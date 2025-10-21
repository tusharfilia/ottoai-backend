from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, Query
from app.database import get_db
from app.models import call, company, user
from app.middleware.rbac import require_role, require_tenant_ownership
from sqlalchemy.orm import Session
from sqlalchemy import and_ # Added for combining query conditions
from datetime import datetime, timedelta
import json
import requests
import os
import httpx
from app.models import sales_rep, sales_manager, scheduled_call
from app.routes.dependencies import get_user_from_clerk_token # Added for authentication
from pydantic import BaseModel # Added for response models
from typing import List, Optional # Added for response models
import logging
import traceback # Added for detailed error logging
from app.services.sales_rep_notification_service import send_appointment_assignment_notification # Import notification service

# API key for Clerk integration
from app.config import settings

CLERK_SECRET_KEY = settings.CLERK_SECRET_KEY
CLERK_API_BASE_URL = settings.CLERK_API_URL

# Helper function to make authenticated requests to Clerk
async def clerk_request(method, url, json_data=None):
    headers = {
        "Authorization": f"Bearer {CLERK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    logging.info(f"Making Clerk request: {method} {url}")
    if json_data:
        logging.info(f"Request body: {json.dumps(json_data, indent=2)}")
    
    async with httpx.AsyncClient() as client:
        try:
            if method == "GET":
                response = await client.get(f"{CLERK_API_BASE_URL}{url}", headers=headers)
            elif method == "POST":
                response = await client.post(f"{CLERK_API_BASE_URL}{url}", headers=headers, json=json_data)
            elif method == "PATCH":
                response = await client.patch(f"{CLERK_API_BASE_URL}{url}", headers=headers, json=json_data)
            elif method == "DELETE":
                response = await client.delete(f"{CLERK_API_BASE_URL}{url}", headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            logging.info(f"Clerk response status: {response.status_code}")
            logging.info(f"Clerk response headers: {dict(response.headers)}")
            response_text = response.text
            logging.info(f"Clerk response body: {response_text}")
            
            if response.status_code >= 400:
                logging.error(f"Clerk API error: {response_text}")
            
            return response
        except Exception as e:
            logging.error(f"Exception in clerk_request: {str(e)}", exc_info=True)
            raise

# Create a Clerk user
async def create_clerk_user(user_data):
    """Create a new user in Clerk"""
    try:
        # Split name into first and last name
        name_parts = user_data["name"].split()
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
        
        # Format phone number (strip any non-digit characters except +)
        phone_number = user_data["phone_number"]
        formatted_phone = "".join([c for c in phone_number if c.isdigit() or c == '+'])
        if not formatted_phone.startswith('+'):
            formatted_phone = '+1' + formatted_phone  # Add US country code if missing
            
        # Exact payload structure from Clerk API docs
        clerk_user_data = {
            "first_name": first_name,
            "last_name": last_name,
            "email_address": [user_data["email"]],
            "phone_number": [formatted_phone],
            "username": user_data.get("username"),
            "password": user_data.get("password", "ChangeMe123!")
        }
        
        response = await clerk_request("POST", "/users", clerk_user_data)
        
        if response.status_code != 200:
            error_msg = f"Clerk API error: {response.text}"
            logging.error(error_msg)
            return None
        
        clerk_user = response.json()
        logging.info(f"Clerk user creation response: {json.dumps(clerk_user, indent=2)}")
        
        if not clerk_user or "id" not in clerk_user:
            error_msg = "Clerk API returned invalid response - missing user ID"
            logging.error(error_msg)
            return None
            
        return clerk_user
    except Exception as e:
        logging.error(f"Error creating Clerk user: {str(e)}", exc_info=True)
        return None

# Cancel a Bland call (stub function - implement as needed)
async def cancel_bland_call(bland_call_id):
    """Cancel a Bland AI call"""
    # Implement as needed - this is a stub
    logging.info(f"Cancelling Bland call {bland_call_id}")
    return True

router = APIRouter(prefix="/sales-rep", tags=["sales-rep"])

# Define Response Models
class RepBase(BaseModel):
    id: str # Clerk User ID
    name: str
    email: str
    phone_number: Optional[str] = None

class RepsListResponse(BaseModel):
    reps: List[RepBase]

class RepAppointment(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    date: Optional[str] = None # Stored as datetime, formatted as string
    time: Optional[str] = None
    full_datetime: Optional[datetime] = None
    status: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    location: Optional[str] = None
    created_at: Optional[datetime] = None
    duration: Optional[int] = None
    is_past: bool
    bought: Optional[bool] = None
    cancelled: bool
    price_quote: Optional[float] = None

class RepAppointmentsResponse(BaseModel):
    appointments: List[RepAppointment]
    total: int
    show_past: bool
    rep_name: str # Name of the rep whose appointments are being shown

@router.get("", response_model=RepsListResponse)
@require_role("admin", "csr", "rep")
async def get_company_reps(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_user_from_clerk_token)
):
    """
    Get all sales representatives for the company that the authenticated user belongs to.
    Requires user to be authenticated.
    """
    try:
        # Get company ID from the authenticated user's custom claims or database lookup
        # Assuming Clerk token contains organization memberships or a custom claim
        org_memberships = current_user.get("organization_memberships", [])
        if not org_memberships:
            # Fallback: Check user record in DB if org info not in token
            user_id = current_user.get("id")
            user_record = db.query(user.User).filter_by(id=user_id).first()
            if not user_record or not user_record.company_id:
                 raise HTTPException(status_code=403, detail="User is not associated with a company")
            company_id = user_record.company_id
        else:
            # Assuming the first organization is the relevant one
            company_id = org_memberships[0]["organization"]["id"]

        if not company_id:
            raise HTTPException(status_code=403, detail="Could not determine user's company")

        # Fetch all sales reps (users with role 'rep') associated with this company_id
        reps_query = db.query(user.User).join(sales_rep.SalesRep, user.User.id == sales_rep.SalesRep.user_id).filter(
            user.User.company_id == company_id,
            user.User.role == 'rep' # Ensure we only get reps
        ).all()
        
        rep_list = [
            RepBase(
                id=rep.id,
                name=rep.name,
                email=rep.email,
                phone_number=rep.phone_number
            )
            for rep in reps_query
        ]

        return RepsListResponse(reps=rep_list)

    except HTTPException:
        raise # Re-raise HTTP exceptions
    except Exception as e:
        stack_trace = traceback.format_exc()
        logging.error(f"Error fetching company reps: {str(e)}\n{stack_trace}")
        raise HTTPException(status_code=500, detail="Failed to retrieve company representatives")


@router.get("/{rep_id}/appointments", response_model=RepAppointmentsResponse)
@require_role("admin", "rep")
async def get_rep_appointments(
    rep_id: str, # Clerk User ID of the rep
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_user_from_clerk_token),
    show_past: bool = False,
    show_all: bool = False  # New parameter to show all appointments
):
    """
    Get all appointments for a specific sales rep.
    Requires the authenticated user to be in the same company as the rep.
    Can filter to show past, upcoming, or all appointments.
    """
    try:
        # Get company ID for the authenticated user (same logic as get_company_reps)
        auth_user_id = current_user.get("id")
        org_memberships = current_user.get("organization_memberships", [])
        if not org_memberships:
            auth_user_record = db.query(user.User).filter_by(id=auth_user_id).first()
            if not auth_user_record or not auth_user_record.company_id:
                 raise HTTPException(status_code=403, detail="Authenticated user not associated with a company")
            auth_company_id = auth_user_record.company_id
        else:
            auth_company_id = org_memberships[0]["organization"]["id"]

        if not auth_company_id:
            raise HTTPException(status_code=403, detail="Could not determine authenticated user's company")

        # Verify the requested rep exists and belongs to the *same company* as the authenticated user
        target_rep_user_record = db.query(user.User).filter(
             user.User.id == rep_id,
             user.User.company_id == auth_company_id,
             user.User.role == 'rep' 
            ).first()

        if not target_rep_user_record:
            # Check if rep exists but in another company (for better error message)
            rep_exists_elsewhere = db.query(user.User).filter(user.User.id == rep_id, user.User.role == 'rep').first()
            if rep_exists_elsewhere:
                 raise HTTPException(status_code=403, detail="You do not have permission to view this representative's appointments (different company).")
            else:
                 raise HTTPException(status_code=404, detail="Sales representative not found.")

        # Query appointments assigned to this specific rep
        query_conditions = [
            call.Call.assigned_rep_id == rep_id,
            call.Call.company_id == auth_company_id, # Redundant check, but good practice
            call.Call.booked.is_(True),
            call.Call.cancelled.is_(False) # Exclude cancelled appointments
        ]

        # Add date condition based on show_past parameter, unless show_all is True
        now = datetime.now()
        if not show_all:  # Only apply date filtering if not showing all
            if show_past:
                query_conditions.append(call.Call.quote_date < now)
                order_by_clause = call.Call.quote_date.desc()
            else:
                query_conditions.append(call.Call.quote_date >= now)
                order_by_clause = call.Call.quote_date.asc()
        else:
            # If showing all, sort by date descending (newest first)
            order_by_clause = call.Call.quote_date.desc()

        appointments_query = db.query(call.Call).filter(
            and_(*query_conditions)
        ).order_by(order_by_clause).all()

        # Format appointments for response
        appointment_list = []
        for appt in appointments_query:
            appointment_list.append(RepAppointment(
                id=appt.call_id,
                title=f"Appointment with {appt.name}",
                description=appt.address or "No address provided",
                date=appt.quote_date.strftime("%Y-%m-%d") if appt.quote_date else None,
                time=appt.quote_date.strftime("%H:%M:%S") if appt.quote_date else None,
                full_datetime=appt.quote_date,
                status="cancelled" if appt.cancelled else ("past" if appt.quote_date and appt.quote_date < now else "upcoming"),
                customer_name=appt.name,
                customer_phone=appt.phone_number,
                location=appt.address,
                created_at=appt.created_at,
                duration=60,  # Assuming default duration, adjust if available in model
                is_past=appt.quote_date < now if appt.quote_date else False,
                bought=appt.bought,
                cancelled=appt.cancelled,
                price_quote=float(appt.price_if_bought) if appt.price_if_bought else None
            ))

        return RepAppointmentsResponse(
            appointments=appointment_list,
            total=len(appointment_list),
            show_past=show_past,
            rep_name=target_rep_user_record.name # Return the rep's name for confirmation
        )

    except HTTPException:
        raise # Re-raise HTTP exceptions
    except Exception as e:
        stack_trace = traceback.format_exc()
        logging.error(f"Error fetching appointments for rep {rep_id}: {str(e)}\n{stack_trace}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve appointments for representative: {str(e)}")

@router.post("/")
@require_role("admin")
async def create_sales_rep(
    request: Request,
    name: str = Query(...),
    email: str = Query(...),
    phone_number: str = Query(...),
    company_id: str = Query(...),  # Now expects Clerk org ID
    manager_id: str = Query(...),  # Now expects Clerk user ID
    password: str = Query(None),
    username: str = Query(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    # Verify company exists
    company_record = db.query(company.Company).filter_by(id=company_id).first()
    if not company_record:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Verify manager exists and belongs to the same company
    manager = db.query(sales_manager.SalesManager)\
        .filter_by(
            user_id=manager_id,  # Now using Clerk user ID
            company_id=company_id
        ).first()
    
    if not manager:
        raise HTTPException(
            status_code=404,
            detail="Sales manager not found or does not belong to the specified company"
        )
    
    # Check if rep already exists in this company
    existing = db.query(sales_rep.SalesRep)\
        .join(user.User)\
        .filter(
            user.User.phone_number == phone_number,
            sales_rep.SalesRep.company_id == company_id
        ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Sales rep with this phone number already exists in this company"
        )
    
    # Ensure username is set - if not provided, use the name (lowercase with spaces removed)
    if not username:
        username = name.lower().replace(" ", "")
    
    # If password is not provided, generate a default one
    if not password:
        password = "ChangeMe123!"
    
    # Create Clerk user first
    clerk_user_data = {
        "first_name": name.split()[0] if name.split() else "",
        "last_name": " ".join(name.split()[1:]) if len(name.split()) > 1 else "",
        "email_address": [email],
        "phone_number": ["+1" + "".join([c for c in phone_number if c.isdigit()]) if not phone_number.startswith('+') else phone_number],
        "username": username,
        "password": password
    }
    
    logging.info(f"Creating Clerk user with data: {json.dumps(clerk_user_data, indent=2)}")
    user_response = await clerk_request("POST", "/users", clerk_user_data)
    
    if user_response.status_code != 200:
        error_msg = f"Clerk API error: {user_response.text}"
        logging.error(error_msg)
        return {
            "status": "error",
            "message": "Failed to create Clerk user",
            "details": error_msg
        }
    
    # Parse the full user response
    clerk_user_response = user_response.json()
    logging.info(f"Full Clerk user response: {json.dumps(clerk_user_response, indent=2)}")
    
    # Get the Clerk user ID from the response
    clerk_user_id = clerk_user_response["id"]
    
    # Create the user record with Clerk ID
    new_user_record = user.User(
        id=clerk_user_id,  # Use Clerk user ID as primary key
        name=name,
        email=email,
        username=username,
        phone_number=phone_number,
        role="rep",
        company_id=company_id
    )
    
    db.add(new_user_record)
    db.commit()
    db.refresh(new_user_record)
    
    # Create the sales rep record
    new_rep = sales_rep.SalesRep(
        user_id=clerk_user_id,  # Use Clerk user ID as primary key
        company_id=company_id,
        manager_id=manager_id  # Now using Clerk user ID
    )
    
    db.add(new_rep)
    db.commit()
    db.refresh(new_rep)
    
    return {
        "status": "success",
        "rep_id": clerk_user_id,  # Return Clerk user ID
        "user_id": clerk_user_id,  # Return Clerk user ID
        "has_clerk_account": True,
        "clerk_user_id": clerk_user_id,
        "clerk_org_id": company_record.id
    }

@router.get("/{rep_id}")
async def get_sales_rep(rep_id: str, db: Session = Depends(get_db)):
    print(f"Fetching sales rep with ID: {rep_id}, type: {type(rep_id).__name__}")
    
    # Try first as a user_id (Clerk ID)
    rep = db.query(sales_rep.SalesRep).filter_by(user_id=rep_id).first()
    
    # If not found and it's a numeric ID, try as old-style ID
    if not rep and rep_id.isdigit():
        rep = db.query(sales_rep.SalesRep).filter_by(id=int(rep_id)).first()
    
    if not rep:
        print(f"Sales rep not found with ID: {rep_id}")
        raise HTTPException(status_code=404, detail="Sales rep not found")
    
    # Get the user data
    user_record = db.query(user.User).filter_by(id=rep.user_id).first()
    
    # Return combined data
    rep_data = {
        "id": rep.user_id,  # Using user_id as ID
        "name": user_record.name if user_record else "Unknown",
        "email": user_record.email if user_record else "",
        "phone_number": user_record.phone_number if user_record else "",
        "company_id": rep.company_id,
        "manager_id": rep.manager_id
    }
    
    print(f"Returning sales rep data: {rep_data}")
    return rep_data

@router.put("/{rep_id}")
@require_role("admin")
async def update_sales_rep(rep_id: int, request: Request, db: Session = Depends(get_db)):
    params = dict(request.query_params)
    rep = db.query(sales_rep.SalesRep).filter_by(id=rep_id).first()
    
    if not rep:
        raise HTTPException(status_code=404, detail="Sales rep not found")
    
    # Update user fields
    if params.get("name"):
        rep.user.name = params.get("name")
    if params.get("phone_number"):
        rep.user.phone_number = params.get("phone_number")
    if params.get("username"):
        rep.user.username = params.get("username")
    if params.get("email"):
        rep.user.email = params.get("email")
    
    # Update rep-specific fields
    if params.get("manager_id"):
        # Verify new manager exists and belongs to the same company
        manager = db.query(sales_manager.SalesManager)\
            .filter_by(
                id=int(params.get("manager_id")),
                company_id=rep.company_id
            ).first()
        if not manager:
            raise HTTPException(status_code=404, detail="Sales manager not found or does not belong to the same company")
        rep.manager_id = int(params.get("manager_id"))
    if params.get("company_id"):
        # Verify new company exists
        company_record = db.query(company.Company).filter_by(id=int(params.get("company_id"))).first()
        if not company_record:
            raise HTTPException(status_code=404, detail="Company not found")
        rep.company_id = int(params.get("company_id"))
        rep.user.company_id = int(params.get("company_id"))
    
    db.commit()
    return {"status": "success", "rep_id": rep_id}

# Note: Delete endpoints have been moved to delete.py

@router.post("/assign-sales-rep")
@require_role("admin", "csr")
async def assign_sales_rep(
    call_id: int,
    new_sales_rep_id: str,  # Changed to string to match the Call model
    db: Session = Depends(get_db)
):
    try:
        print(f"Assigning call ID: {call_id} to sales rep ID: {new_sales_rep_id!r}")
        call_record = db.query(call.Call).filter(call.Call.call_id == call_id).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call not found")

        # Get company ID from the call record
        company_id = call_record.company_id
        if not company_id:
            raise HTTPException(status_code=400, detail="Call has no associated company")

        # Verify the sales rep exists and belongs to the same company
        sales_rep_record = db.query(sales_rep.SalesRep).filter(
            sales_rep.SalesRep.user_id == new_sales_rep_id,
            sales_rep.SalesRep.company_id == company_id
        ).first()
        
        if not sales_rep_record:
            raise HTTPException(
                status_code=400, 
                detail=f"Sales rep with ID {new_sales_rep_id} not found or does not belong to the same company"
            )

        old_sales_rep_id = call_record.assigned_rep_id
        print(f"Previous assigned rep ID: {old_sales_rep_id!r}")

        # Update the call record with the new sales rep ID
        call_record.assigned_rep_id = new_sales_rep_id
        print(f"Updated call record assigned_rep_id to {new_sales_rep_id!r}")

        # Handles Scenario 2: Previous rep exists
        if old_sales_rep_id:
            existing_follow_up = db.query(scheduled_call.ScheduledCall).filter(
                scheduled_call.ScheduledCall.call_id == str(call_id),  # Convert to string if needed
            ).first()
            
            if existing_follow_up and existing_follow_up.bland_call_id:
                print(f"Canceling existing follow-up with bland_call_id: {existing_follow_up.bland_call_id}")
                try:
                    await cancel_bland_call(existing_follow_up.bland_call_id)
                except Exception as e:
                    print(f"Warning: Failed to cancel bland call: {e}")
                
                db.delete(existing_follow_up)

        # Handles both Scenario 1 & 2: Schedule new follow-up
        if call_record.quote_date:
            follow_up_time = call_record.quote_date + timedelta(hours=2)
            
            # Create the scheduled call without the non-existent sales_rep_id field
            new_scheduled_call = scheduled_call.ScheduledCall(
                call_id=str(call_id),  # Convert to string if the model expects string
                company_id=company_id,
                scheduled_time=follow_up_time,
                call_type=scheduled_call.CallType.SALES_FOLLOWUP
            )
            db.add(new_scheduled_call)
            print(f"Scheduled new follow-up for {follow_up_time}")
        
        db.commit()
        
        # Send notification to the newly assigned sales rep
        customer_name = call_record.name or "Customer"
        appointment_date = call_record.quote_date.isoformat() if call_record.quote_date else None
        address = call_record.address or None
        
        # Send notification asynchronously (don't wait for result)
        notification_result = send_appointment_assignment_notification(
            db=db,
            call_id=call_id,
            sales_rep_id=new_sales_rep_id,
            customer_name=customer_name,
            appointment_date=appointment_date,
            address=address
        )
        
        print(f"Notification result: {notification_result}")
        
        print(f"Successfully assigned sales rep {new_sales_rep_id!r} to call {call_id}")
        return {"message": "Sales rep assigned and follow-up scheduled"}
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log any other exceptions
        print(f"Error assigning sales rep: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to assign sales rep: {str(e)}")
