from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import user, company, sales_manager, sales_rep
from app.routes.dependencies import get_user_from_clerk_token
import os
import httpx
import logging
from typing import Optional
from app.services.idempotency import with_idempotency

router = APIRouter(prefix="/user", tags=["user"])

# API key for Clerk integration
from app.config import settings

CLERK_SECRET_KEY = settings.CLERK_SECRET_KEY
CLERK_API_BASE_URL = settings.CLERK_API_URL

# Helper function to make authenticated requests to Clerk
async def clerk_request(method, url, json=None):
    headers = {
        "Authorization": f"Bearer {CLERK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        if method == "GET":
            response = await client.get(f"{CLERK_API_BASE_URL}{url}", headers=headers)
        elif method == "POST":
            response = await client.post(f"{CLERK_API_BASE_URL}{url}", headers=headers, json=json)
        elif method == "PATCH":
            response = await client.patch(f"{CLERK_API_BASE_URL}{url}", headers=headers, json=json)
        elif method == "DELETE":
            response = await client.delete(f"{CLERK_API_BASE_URL}{url}", headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        return response

# Create a Clerk user for a manager
async def create_clerk_user(user_data: dict) -> Optional[dict]:
    """Create a user in Clerk with proper password handling"""
    email = user_data.get("email")
    username = user_data.get("username")
    password = user_data.get("password")
    
    if not all([email, username, password]):
        logging.error("Missing required fields for Clerk user creation")
        return None
    
    # Create user in Clerk
    clerk_user_data = {
        "email_addresses": [{"email": email}],
        "username": username,
        "first_name": user_data.get("first_name", ""),
        "last_name": user_data.get("last_name", ""),
        "password": password,
        "public_metadata": {
            "role": "manager",
            "company_id": user_data.get("company_id")
        }
    }
    
    try:
        response = await clerk_request("POST", "/users", clerk_user_data)
        
        if response.status_code != 200:
            logging.error(f"Failed to create Clerk user: {response.text}")
            return None
        
        return response.json()
    except Exception as e:
        logging.error(f"Error creating Clerk user: {str(e)}")
        return None

# Add a user to a Clerk organization
async def add_user_to_organization(clerk_user_id: str, clerk_org_id: str, role: str = "basic_member") -> Optional[dict]:
    """Add a user to a Clerk organization with proper role"""
    membership_data = {
        "role": role,
        "user_id": clerk_user_id,
        "public_metadata": {
            "role": role
        }
    }
    
    try:
        response = await clerk_request("POST", f"/organizations/{clerk_org_id}/memberships", membership_data)
        
        if response.status_code != 200:
            logging.error(f"Failed to add user to organization: {response.text}")
            return None
        
        return response.json()
    except Exception as e:
        logging.error(f"Error adding user to organization: {str(e)}")
        return None

@router.post("/")
async def create_user(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Create a new user (either manager or rep)"""
    payload = await request.json()
    
    # Basic validation
    required_fields = ["name", "email", "username", "role", "company_id"]
    for field in required_fields:
        if field not in payload:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
    
    # Check if user already exists
    existing_user = db.query(user.User).filter(
        (user.User.email == payload["email"]) | 
        (user.User.username == payload["username"])
    ).first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email or username already exists")
    
    # Validate company
    company_record = db.query(company.Company).filter_by(id=payload["company_id"]).first()
    if not company_record:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Create user in database
    new_user = user.User(
        name=payload["name"],
        email=payload["email"],
        username=payload["username"],
        phone_number=payload.get("phone_number"),
        role=payload["role"],
        company_id=payload["company_id"]
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create associated profile based on role
    if payload["role"] == "manager":
        # Create manager profile
        new_manager = sales_manager.SalesManager(
            user_id=new_user.id,
            company_id=payload["company_id"]
        )
        db.add(new_manager)
        db.commit()
        
        # Only create Clerk account for managers
        try:
            # Create user in Clerk
            clerk_user = await create_clerk_user({
                "email": payload["email"],
                "username": payload["username"],
                "password": payload.get("password", "ChangeMe123!"),
                "first_name": payload.get("first_name", payload["name"].split()[0] if " " in payload["name"] else payload["name"]),
                "last_name": payload.get("last_name", payload["name"].split()[-1] if " " in payload["name"] else ""),
                "company_id": payload["company_id"]
            })
            
            if clerk_user:
                # Update user record with Clerk ID
                new_user.clerk_id = clerk_user["id"]
                db.commit()
                
                # If company has a Clerk org, add user to it
                if company_record.clerk_org_id:
                    background_tasks.add_task(
                        add_user_to_organization, 
                        clerk_user["id"], 
                        company_record.clerk_org_id, 
                        "org:admin"
                    )
        except Exception as e:
            logging.error(f"Failed to create Clerk user: {str(e)}")
            # Continue without error, we'll still return the user
    else:
        # Create rep profile
        new_rep = sales_rep.SalesRep(
            user_id=new_user.id,
            company_id=payload["company_id"],
            manager_id=payload.get("manager_id")
        )
        db.add(new_rep)
        db.commit()
    
    return {"success": True, "user_id": new_user.id}

@router.get("/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user details"""
    user_record = db.query(user.User).filter_by(id=user_id).first()
    if not user_record:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get profile information
    profile = None
    if user_record.role == "manager":
        manager = db.query(sales_manager.SalesManager).filter_by(user_id=user_id).first()
        if manager:
            profile = {
                "id": manager.id,
                "reps_count": db.query(sales_rep.SalesRep).filter_by(manager_id=manager.id).count()
            }
    else:
        rep = db.query(sales_rep.SalesRep).filter_by(user_id=user_id).first()
        if rep:
            profile = {
                "id": rep.id,
                "manager_id": rep.manager_id
            }
    
    return {
        "id": user_record.id,
        "name": user_record.name,
        "email": user_record.email,
        "username": user_record.username,
        "phone_number": user_record.phone_number,
        "role": user_record.role,
        "company_id": user_record.company_id,
        "has_clerk_account": bool(user_record.clerk_id),
        "profile": profile
    }

@router.put("/{user_id}")
async def update_user(user_id: int, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Update user details"""
    payload = await request.json()
    
    user_record = db.query(user.User).filter_by(id=user_id).first()
    if not user_record:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update user fields
    if "name" in payload:
        user_record.name = payload["name"]
    if "email" in payload:
        user_record.email = payload["email"]
    if "phone_number" in payload:
        user_record.phone_number = payload["phone_number"]
    
    # If it's a rep and being promoted to manager
    if user_record.role == "rep" and payload.get("role") == "manager":
        # Delete rep profile
        rep = db.query(sales_rep.SalesRep).filter_by(user_id=user_id).first()
        if rep:
            db.delete(rep)
        
        # Create manager profile
        new_manager = sales_manager.SalesManager(
            user_id=user_id,
            company_id=user_record.company_id
        )
        db.add(new_manager)
        
        # Create Clerk account
        try:
            clerk_user = await create_clerk_user({
                "email": user_record.email,
                "username": user_record.username,
                "first_name": payload.get("first_name", user_record.name.split()[0] if " " in user_record.name else user_record.name),
                "last_name": payload.get("last_name", user_record.name.split()[-1] if " " in user_record.name else ""),
                "temporary_password": payload.get("temporary_password"),
                "company_id": user_record.company_id
            })
            
            user_record.clerk_id = clerk_user["id"]
            user_record.role = "manager"
            
            # If company has a Clerk org, add user to it
            company_record = db.query(company.Company).filter_by(id=user_record.company_id).first()
            if company_record and company_record.clerk_org_id:
                background_tasks.add_task(
                    add_user_to_organization, 
                    clerk_user["id"], 
                    company_record.clerk_org_id, 
                    "org:admin"
                )
        except Exception as e:
            print(f"Failed to create Clerk user: {str(e)}")
            # Still update the role in our database
            user_record.role = "manager"
    
    # If it's a manager and being demoted to rep
    elif user_record.role == "manager" and payload.get("role") == "rep":
        # Delete manager profile
        manager = db.query(sales_manager.SalesManager).filter_by(user_id=user_id).first()
        if manager:
            db.delete(manager)
        
        # Create rep profile
        new_rep = sales_rep.SalesRep(
            user_id=user_id,
            company_id=user_record.company_id,
            manager_id=payload.get("manager_id")
        )
        db.add(new_rep)
        
        # Delete Clerk account if exists
        if user_record.clerk_id:
            try:
                response = await clerk_request("DELETE", f"/users/{user_record.clerk_id}")
                if response.status_code == 200 or response.status_code == 204:
                    user_record.clerk_id = None
            except Exception as e:
                print(f"Failed to delete Clerk user: {str(e)}")
        
        user_record.role = "rep"
    
    # If it's a manager with Clerk account, update Clerk data
    elif user_record.role == "manager" and user_record.clerk_id:
        try:
            # Prepare data for Clerk update
            clerk_data = {}
            
            if "email" in payload:
                clerk_data["email_addresses"] = [{"email": payload["email"]}]
            
            if "name" in payload:
                name_parts = payload["name"].split()
                clerk_data["first_name"] = name_parts[0] if name_parts else ""
                clerk_data["last_name"] = name_parts[-1] if len(name_parts) > 1 else ""
            
            # Only update if we have data to update
            if clerk_data:
                await clerk_request("PATCH", f"/users/{user_record.clerk_id}", clerk_data)
        except Exception as e:
            print(f"Failed to update Clerk user: {str(e)}")
    
    db.commit()
    return {"success": True, "user_id": user_id}

# Note: Delete endpoints have been moved to delete.py

@router.get("/by-username/{username}")
async def get_user_by_username(username: str, db: Session = Depends(get_db)):
    """Get user by username"""
    user_record = db.query(user.User).filter_by(username=username).first()
    if not user_record:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user_record.id,
        "name": user_record.name,
        "email": user_record.email,
        "username": user_record.username,
        "role": user_record.role,
        "company_id": user_record.company_id
    }

@router.post("/clerk-webhook")
async def handle_clerk_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Handle webhooks from Clerk"""
    # Verify webhook signature
    webhook_secret = settings.CLERK_WEBHOOK_SECRET
    signature = request.headers.get("svix-signature")
    
    if not webhook_secret or not signature:
        raise HTTPException(status_code=400, detail="Missing webhook secret or signature")
    
    # TODO: Implement signature verification using svix library
    # For now, we'll trust the webhook
    
    payload = await request.json()
    event_type = payload.get("type")
    data = payload.get("data", {})
    
    # Extract tenant_id from payload (organization context)
    tenant_id = data.get("organization_id") or "default_tenant"
    
    # Derive external_id from Clerk payload - prefer event_id, then data.id
    external_id = payload.get("event_id") or data.get("id") or f"{event_type}-{data.get('id', 'unknown')}"
    
    def process_webhook():
    
    if event_type == "user.created":
        # A user was created in Clerk - we should create/link in our DB
        clerk_id = data.get("id")
        email = data.get("email_addresses", [{}])[0].get("email_address", "")
        username = data.get("username", "")
        
        # Check if user already exists by email or username
        user_record = db.query(user.User).filter(
            (user.User.email == email) | 
            (user.User.username == username)
        ).first()
        
        if user_record:
            # Link existing user with Clerk ID
            user_record.clerk_id = clerk_id
            db.commit()
        else:
            # Create new user (need to determine company_id from metadata or other source)
            company_id = data.get("public_metadata", {}).get("company_id")
            if not company_id:
                logging.error(f"Warning: Clerk user created without company_id: {clerk_id}")
                return {"success": False, "error": "No company_id in metadata"}
            
            # Create user record
            new_user = user.User(
                clerk_id=clerk_id,
                email=email,
                username=username,
                name=f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
                role="manager",  # Assume managers only in Clerk
                company_id=company_id
            )
            
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            # Create manager profile
            new_manager = sales_manager.SalesManager(
                user_id=new_user.id,
                company_id=company_id
            )
            db.add(new_manager)
            db.commit()
    
    elif event_type == "user.updated":
        # Update user in our DB when updated in Clerk
        clerk_id = data.get("id")
        user_record = db.query(user.User).filter_by(clerk_id=clerk_id).first()
        
        if user_record:
            # Update fields
            if "email_addresses" in data and data["email_addresses"]:
                user_record.email = data["email_addresses"][0].get("email_address", user_record.email)
            
            if "username" in data:
                user_record.username = data["username"]
            
            name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
            if name:
                user_record.name = name
            
            # Update role if changed in metadata
            if "public_metadata" in data and "role" in data["public_metadata"]:
                user_record.role = data["public_metadata"]["role"]
            
            db.commit()
    
    elif event_type == "user.deleted":
        # Delete or deactivate user in our DB
        clerk_id = data.get("id")
        user_record = db.query(user.User).filter_by(clerk_id=clerk_id).first()
        
        if user_record:
            # Option 1: Delete user from our DB
            # background_tasks.add_task(delete_user, user_record.id, db)
            
            # Option 2: Just remove clerk_id reference but keep user
            user_record.clerk_id = None
            db.commit()
    
    elif event_type == "user.password.updated":
        # Handle password updates (could be used for audit logging)
        clerk_id = data.get("id")
        user_record = db.query(user.User).filter_by(clerk_id=clerk_id).first()
        
        if user_record:
            logging.info(f"Password updated for user {user_record.email}")
    
    elif event_type == "organization.created":
        # Link organization to company
        org_id = data.get("id")
        org_name = data.get("name")
        
        # Try to find matching company by name
        company_record = db.query(company.Company).filter_by(name=org_name).first()
        
        if company_record:
            company_record.clerk_org_id = org_id
            db.commit()
    
    elif event_type == "organization.updated":
        # Update company name if organization name changed
        org_id = data.get("id")
        org_name = data.get("name")
        
        company_record = db.query(company.Company).filter_by(clerk_org_id=org_id).first()
        if company_record:
            company_record.name = org_name
            db.commit()
    
    elif event_type == "organization.deleted":
        # Handle organization deletion
        org_id = data.get("id")
        company_record = db.query(company.Company).filter_by(clerk_org_id=org_id).first()
        
        if company_record:
            # Option 1: Delete company
            # db.delete(company_record)
            
            # Option 2: Just remove clerk_org_id reference
            company_record.clerk_org_id = None
            db.commit()
        
        return {"status": "processed", "event_type": event_type, "data_id": data.get("id")}
    
    # Apply idempotency protection
    response_data, status_code = with_idempotency(
        provider="clerk",
        external_id=external_id,
        tenant_id=tenant_id,
        process_fn=process_webhook,
        trace_id=getattr(request.state, 'trace_id', None)
    )
    
    return response_data

# Route to sync a user from our database to Clerk
@router.post("/{user_id}/sync-to-clerk")
async def sync_user_to_clerk(user_id: int, db: Session = Depends(get_db)):
    """Force sync a user from database to Clerk"""
    user_record = db.query(user.User).filter_by(id=user_id).first()
    if not user_record:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Only managers should have Clerk accounts
    if user_record.role != "manager":
        raise HTTPException(status_code=400, detail="Only managers can have Clerk accounts")
    
    # If user already has Clerk ID, update existing account
    if user_record.clerk_id:
        clerk_data = {
            "first_name": user_record.name.split()[0] if " " in user_record.name else user_record.name,
            "last_name": user_record.name.split()[-1] if " " in user_record.name else "",
            "email_addresses": [{"email": user_record.email}],
            "username": user_record.username
        }
        
        try:
            response = await clerk_request("PATCH", f"/users/{user_record.clerk_id}", clerk_data)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, 
                                    detail=f"Failed to update Clerk user: {response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating Clerk user: {str(e)}")
    
    # If user doesn't have Clerk ID, create new account
    else:
        try:
            clerk_user = await create_clerk_user({
                "email": user_record.email,
                "username": user_record.username,
                "first_name": user_record.name.split()[0] if " " in user_record.name else user_record.name,
                "last_name": user_record.name.split()[-1] if " " in user_record.name else "",
                "company_id": user_record.company_id
            })
            
            user_record.clerk_id = clerk_user["id"]
            db.commit()
            
            # Add to organization if applicable
            company_record = db.query(company.Company).filter_by(id=user_record.company_id).first()
            if company_record and company_record.clerk_org_id:
                await add_user_to_organization(
                    clerk_user["id"], 
                    company_record.clerk_org_id, 
                    "org:admin"
                )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error creating Clerk user: {str(e)}")
    
    return {"success": True, "user_id": user_id}

# List all Clerk users
async def list_clerk_users(limit: int = 100, offset: int = 0) -> list:
    """List all Clerk users
    
    Args:
        limit: Maximum number of users to return (default: 100)
        offset: Offset for pagination (default: 0)
        
    Returns:
        list: List of user objects
    """
    try:
        logging.info(f"Listing Clerk users (limit: {limit}, offset: {offset})")
        response = await clerk_request("GET", f"/users?limit={limit}&offset={offset}")
        
        if response.status_code == 200:
            # The response is already a list of users
            return response.json()
        else:
            logging.error(f"Failed to list Clerk users. Status: {response.status_code}, Response: {response.text}")
            return []
    except Exception as e:
        logging.error(f"Error listing Clerk users: {str(e)}")
        return []

@router.patch("/metadata/{user_id}")
async def update_user_metadata(user_id: str, request: Request, db: Session = Depends(get_db)):
    """Update a user's metadata in Clerk
    
    Args:
        user_id: The Clerk user ID
        request: The request object containing the metadata to update
        
    Returns:
        The updated user data
    """
    try:
        data = await request.json()
        
        if not data.get("publicMetadata") and not data.get("privateMetadata"):
            raise HTTPException(status_code=400, detail="Either publicMetadata or privateMetadata must be provided")
        
        # Prepare the request data
        update_data = {}
        if "publicMetadata" in data:
            update_data["public_metadata"] = data["publicMetadata"]
        if "privateMetadata" in data:
            update_data["private_metadata"] = data["privateMetadata"]
        
        # Make the request to Clerk
        logging.info(f"Updating metadata for user {user_id} with data: {update_data}")
        response = await clerk_request("PATCH", f"/users/{user_id}", update_data)
        
        if response.status_code != 200:
            error_detail = f"Failed to update user metadata. Status: {response.status_code}, Response: {response.text}"
            logging.error(error_detail)
            raise HTTPException(status_code=response.status_code, detail=error_detail)
        
        return response.json()
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"Error updating user metadata: {str(e)}"
        logging.error(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)

@router.get("/company")
async def get_user_company(db: Session = Depends(get_db), current_user: dict = Depends(get_user_from_clerk_token)):
    """Get the company for the current authenticated user"""
    
    # Get the user record from the database
    user_record = db.query(user.User).filter_by(id=current_user["id"]).first()
    
    if not user_record:
        raise HTTPException(status_code=404, detail="User not found in database")
    
    # Find the company record
    company_record = db.query(company.Company).filter_by(id=user_record.company_id).first()
    
    if not company_record:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return {
        "company_id": company_record.id,
        "company_name": company_record.name,
        "user_role": user_record.role
    } 