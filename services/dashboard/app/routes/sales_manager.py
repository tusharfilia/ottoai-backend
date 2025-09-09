from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, Query
from app.database import get_db
from app.models import call, company, user
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
import requests
import os
import httpx
import logging
from app.services.bland_ai import BlandAI
from app.utils.date_calculator import DateCalculator
from app.routes.dependencies import client, bland_ai, date_calculator
from app.models import sales_manager, sales_rep

# API key for Clerk integration
CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY")
if not CLERK_SECRET_KEY:
    raise ValueError("CLERK_SECRET_KEY environment variable is not set")
CLERK_API_BASE_URL = "https://api.clerk.dev/v1"

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

router = APIRouter(prefix="/sales-manager", tags=["sales-manager"])

@router.post("/")
async def create_sales_manager(
    name: str = Query(...),
    email: str = Query(...),
    phone_number: str = Query(...),
    company_id: str = Query(...),  # Now expects Clerk org ID
    password: str = Query(None),
    username: str = Query(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    # Verify company exists
    company_record = db.query(company.Company).filter_by(id=company_id).first()
    if not company_record:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Check if manager already exists in this company
    existing = db.query(sales_manager.SalesManager)\
        .join(user.User)\
        .filter(
            user.User.phone_number == phone_number,
            sales_manager.SalesManager.company_id == company_id
        ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Sales manager with this phone number already exists in this company"
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
        role="manager",
        company_id=company_id
    )
    
    db.add(new_user_record)
    db.commit()
    db.refresh(new_user_record)
    
    # Create the sales manager record
    new_manager = sales_manager.SalesManager(
        user_id=clerk_user_id,  # Use Clerk user ID as primary key
        company_id=company_id
    )
    
    db.add(new_manager)
    db.commit()
    db.refresh(new_manager)
    
    return {
        "status": "success",
        "manager_id": clerk_user_id,  # Return Clerk user ID
        "user_id": clerk_user_id,  # Return Clerk user ID
        "has_clerk_account": True,
        "clerk_user_id": clerk_user_id,
        "clerk_org_id": company_record.id
    }

@router.get("/{manager_id}")
async def get_sales_manager(manager_id: int, db: Session = Depends(get_db)):
    manager = db.query(sales_manager.SalesManager).filter_by(id=manager_id).first()
    if not manager:
        raise HTTPException(status_code=404, detail="Sales manager not found")
    return manager

@router.put("/{manager_id}")
async def update_sales_manager(manager_id: int, request: Request, db: Session = Depends(get_db)):
    params = dict(request.query_params)
    manager = db.query(sales_manager.SalesManager).filter_by(id=manager_id).first()
    
    if not manager:
        raise HTTPException(status_code=404, detail="Sales manager not found")
    
    if params.get("name"):
        manager.name = params.get("name")
    
    if params.get("username"):
        manager.username = params.get("username")
    
    if params.get("phone_number"):
        # Check if phone number exists in the same company
        existing = db.query(sales_manager.SalesManager)\
            .filter(
                sales_manager.SalesManager.phone_number == params.get("phone_number"),
                sales_manager.SalesManager.company_id == manager.company_id,
                sales_manager.SalesManager.id != manager_id  # Exclude current manager
            ).first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Sales manager with this phone number already exists in this company"
            )
        manager.phone_number = params.get("phone_number")
    
    if params.get("company_id"):
        # Verify new company exists
        company_record = db.query(company.Company).filter_by(id=int(params.get("company_id"))).first()
        if not company_record:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Check if phone number exists in the new company
        existing = db.query(sales_manager.SalesManager)\
            .filter_by(
                phone_number=manager.phone_number,
                company_id=int(params.get("company_id"))
            ).first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Sales manager with this phone number already exists in the target company"
            )
        
        manager.company_id = int(params.get("company_id"))
    
    db.commit()
    return {"status": "success", "manager_id": manager_id}

# Note: Delete endpoints have been moved to delete.py

@router.get("/{manager_id}/sales-reps")
async def list_manager_sales_reps(manager_id: int, db: Session = Depends(get_db)):
    # Verify manager exists
    manager_record = db.query(sales_manager.SalesManager)\
        .filter_by(id=manager_id)\
        .first()
    
    if not manager_record:
        raise HTTPException(status_code=404, detail="Sales manager not found")
    
    # Get company info
    company_record = db.query(company.Company)\
        .filter_by(id=manager_record.company_id)\
        .first()
    
    # Get all sales reps for this manager
    reps = db.query(sales_rep.SalesRep)\
        .filter_by(manager_id=manager_id)\
        .all()
    
    # Format the response
    return {
        "company": {
            "id": company_record.id,
            "name": company_record.name,
            "phone_number": company_record.phone_number
        },
        "manager": {
            "id": manager_record.id,
            "name": manager_record.name,
            "phone_number": manager_record.phone_number
        },
        "sales_reps": [
            {
                "id": rep.id,
                "name": rep.name,
                "phone_number": rep.phone_number
            }
            for rep in reps
        ],
        "total_reps": len(reps)
    } 
