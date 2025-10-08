from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, Query
from app.database import get_db
from app.models import call, company, sales_manager, sales_rep, user
from app.middleware.rbac import require_role, require_tenant_ownership
from sqlalchemy.orm import Session
import os
import httpx
import logging
from typing import Optional
import re
import json
from datetime import datetime

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
            logging.info(f"Clerk response body: {response.text}")
            return response
        except Exception as e:
            logging.error(f"Exception in clerk_request: {str(e)}")
            raise

def generate_slug(name: str) -> str:
    """Generate a URL-friendly slug from a company name"""
    # Convert to lowercase and replace spaces with hyphens
    slug = name.lower().replace(" ", "-")
    # Remove any non-alphanumeric characters except hyphens
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    # Remove multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    # Remove leading and trailing hyphens
    slug = slug.strip('-')
    return slug

# Create a Clerk organization
async def create_clerk_organization(name: str, created_by: Optional[str] = None) -> Optional[dict]:
    """Create a Clerk organization with proper slug handling"""
    # Generate a unique slug
    base_slug = generate_slug(name)
    slug = base_slug
    counter = 1
    
    while True:
        organization_data = {
            "name": name,
            "slug": slug,
            "public_metadata": {
                "type": "company"
            }
        }
        
        if created_by:
            organization_data["created_by"] = created_by
        
        try:
            logging.info(f"Creating Clerk organization with data: {json.dumps(organization_data, indent=2)}")
            response = await clerk_request("POST", "/organizations", organization_data)
            
            if response.status_code == 200:
                logging.info(f"Successfully created Clerk organization: {response.text}")
                return response.json()
            elif response.status_code == 409:  # Slug conflict
                # Try with a numbered suffix
                slug = f"{base_slug}-{counter}"
                counter += 1
            else:
                logging.error(f"Failed to create Clerk organization. Status: {response.status_code}, Response: {response.text}")
                return None
        except Exception as e:
            logging.error(f"Error creating Clerk organization: {str(e)}")
            return None

# Delete a Clerk organization by ID
async def delete_clerk_organization(org_id: str) -> bool:
    """Delete a Clerk organization by ID
    
    Args:
        org_id: The ID of the organization to delete
        
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        logging.info(f"Deleting Clerk organization: {org_id}")
        response = await clerk_request("DELETE", f"/organizations/{org_id}")
        
        if response.status_code == 200:
            logging.info(f"Successfully deleted Clerk organization: {org_id}")
            return True
        else:
            logging.error(f"Failed to delete Clerk organization. Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        logging.error(f"Error deleting Clerk organization: {str(e)}")
        return False

# List all Clerk organizations
async def list_clerk_organizations(limit: int = 100, offset: int = 0) -> list:
    """List all Clerk organizations
    
    Args:
        limit: Maximum number of organizations to return (default: 100)
        offset: Offset for pagination (default: 0)
        
    Returns:
        list: List of organization objects
    """
    try:
        logging.info(f"Listing Clerk organizations (limit: {limit}, offset: {offset})")
        response = await clerk_request("GET", f"/organizations?limit={limit}&offset={offset}")
        
        if response.status_code == 200:
            data = response.json()
            return data.get("data", [])
        else:
            logging.error(f"Failed to list Clerk organizations. Status: {response.status_code}, Response: {response.text}")
            return []
    except Exception as e:
        logging.error(f"Error listing Clerk organizations: {str(e)}")
        return []

router = APIRouter(prefix="/company", tags=["company"])

@router.post("/")
@require_role("exec")
async def create_company(
    request: Request,
    name: str = Query(...),
    phone_number: str = Query(...),
    address: str = Query(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    # B004 FIX: Validate that user is creating company for their own tenant
    # The Clerk org ID will be used as company ID, so we validate it matches JWT
    user_tenant_id = getattr(request.state, 'tenant_id', None)
    if not user_tenant_id:
        raise HTTPException(
            status_code=401,
            detail="Tenant context not found in request"
        )
    
    # Check if company already exists
    existing = db.query(company.Company).filter_by(name=name).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Company with this name already exists"
        )
    
    # Create Clerk organization first
    clerk_org_data = {
        "name": name,
        "slug": name.lower().replace(" ", "-")
    }
    
    logging.info(f"Creating Clerk organization with data: {json.dumps(clerk_org_data, indent=2)}")
    org_response = await clerk_request("POST", "/organizations", clerk_org_data)
    
    if org_response.status_code != 200:
        error_msg = f"Clerk API error: {org_response.text}"
        logging.error(error_msg)
        return {
            "status": "error",
            "message": "Failed to create Clerk organization",
            "details": error_msg
        }
    
    # Parse the full organization response
    clerk_org_response = org_response.json()
    logging.info(f"Full Clerk organization response: {json.dumps(clerk_org_response, indent=2)}")
    
    # Get the Clerk organization ID from the response
    clerk_org_id = clerk_org_response["id"]
    
    # B004 FIX: Validate that created org ID matches user's tenant
    # This prevents cross-tenant company creation
    if clerk_org_id != user_tenant_id:
        logging.warning(
            f"Cross-tenant company creation attempt: user tenant={user_tenant_id}, "
            f"created org={clerk_org_id}"
        )
        # Clean up: delete the Clerk org we just created
        await delete_clerk_organization(clerk_org_id)
        raise HTTPException(
            status_code=403,
            detail="Cannot create company for different tenant"
        )
    
    # Create the company record with Clerk org ID
    new_company = company.Company(
        id=clerk_org_id,  # Use Clerk org ID as primary key
        name=name,
        phone_number=phone_number,
        address=address
    )
    
    db.add(new_company)
    db.commit()
    db.refresh(new_company)
    
    return {
        "status": "success",
        "company_id": clerk_org_id,  # Return Clerk org ID
        "clerk_org_id": clerk_org_id
    }

@router.get("/get-user-company/{username}")
async def get_user_company(username: str, db: Session = Depends(get_db)):
     print(username)
     # Check if username exists in users table first
     user_record = db.query(user.User).filter_by(username=username).first()
     if user_record:
         return {"company_id": user_record.company_id}
     
     # Check if username exists in sales_manager table
     manager = db.query(sales_manager.SalesManager).filter_by(username=username).first()
     if manager:
         return {"company_id": manager.company_id}
     
     # Check if username exists in sales_rep table
     sales_rep_record = db.query(sales_rep.SalesRep).filter_by(username=username).first()
     if sales_rep_record:
         return {"company_id": sales_rep_record.company_id}
     
     # If username not found in any table
     raise HTTPException(status_code=404, detail="User not found in users, sales managers, or sales representatives")
 
@router.get("/{company_id}")
async def get_company(company_id: str, db: Session = Depends(get_db)):
    company_record = db.query(company.Company).filter_by(id=company_id).first()
    if not company_record:
        raise HTTPException(status_code=404, detail="Company not found")
    return company_record

@router.put("/{company_id}")
@require_role("exec")
@require_tenant_ownership("company_id")
async def update_company(
    request: Request,
    company_id: str,
    db: Session = Depends(get_db)):
    params = dict(request.query_params)
    company_record = db.query(company.Company).filter_by(id=company_id).first()
    
    if not company_record:
        raise HTTPException(status_code=404, detail="Company not found")
    
    if params.get("name"):
        company_record.name = params.get("name")
    if params.get("phone_number"):
        company_record.phone_number = params.get("phone_number")
    if params.get("address"):
        company_record.address = params.get("address")
    
    db.commit()
    return {"status": "success", "company_id": company_id}


@router.get("/{company_id}/sales-managers")
async def list_company_sales_managers(company_id: str, db: Session = Depends(get_db)):
    # Verify company exists
    company_record = db.query(company.Company).filter_by(id=company_id).first()
    if not company_record:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Get all sales managers for this company
    managers = db.query(sales_manager.SalesManager)\
        .filter_by(company_id=company_id)\
        .all()
    
    # Format the response
    return {
        "company": {
            "id": company_record.id,
            "name": company_record.name,
            "phone_number": company_record.phone_number
        },
        "sales_managers": [
            {
                "id": manager.id,
                "name": manager.name,
                "phone_number": manager.phone_number
            }
            for manager in managers
        ],
        "total_managers": len(managers)
    } 

@router.get("/list-organizations")
async def list_organizations(limit: int = Query(100), offset: int = Query(0)):
    """List all organizations in Clerk"""
    try:
        # Get organizations from Clerk
        orgs = await list_clerk_organizations(limit=limit, offset=offset)
        
        # Format response with detailed information
        if orgs:
            # Add more details for clarity
            result = {
                "total": len(orgs),
                "organizations": orgs,
                "clerk_url": CLERK_API_BASE_URL,
                "timestamp": datetime.now().isoformat()
            }
            return result
        else:
            return {
                "total": 0,
                "organizations": [],
                "clerk_url": CLERK_API_BASE_URL,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logging.error(f"Error listing organizations: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/organizations/{org_id}/memberships")
async def add_user_to_organization(
    org_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Add a user to a Clerk organization
    
    Args:
        org_id: The ID of the organization to add the user to (this is the Clerk org ID)
        request: The request containing user_id and role in the body
        
    Returns:
        dict: Response containing success status and details
    """
    try:
        # Get data from request body
        data = await request.json()
        user_id = data.get("user_id")
        role = data.get("role")
        
        if not user_id or not role:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: user_id and role"
            )
        
        # Verify the organization exists in our database
        company_record = db.query(company.Company).filter_by(id=org_id).first()
        if not company_record:
            raise HTTPException(
                status_code=404,
                detail=f"Organization {org_id} not found in database"
            )
        
        # Prepare the request to Clerk
        membership_data = {
            "user_id": user_id,
            "role": role
        }
        
        logging.info(f"Adding user {user_id} to organization {org_id} with role {role}")
        logging.info(f"Organization membership data: {json.dumps(membership_data, indent=2)}")
        
        # Make the request to Clerk
        response = await clerk_request("POST", f"/organizations/{org_id}/memberships", membership_data)
        
        if response.status_code != 200:
            error_msg = f"Failed to add user to organization: {response.text}"
            logging.error(error_msg)
            raise HTTPException(
                status_code=response.status_code,
                detail=error_msg
            )
        
        response_data = response.json()
        logging.info(f"Organization membership response: {json.dumps(response_data, indent=2)}")
        
        return {
            "status": "success",
            "message": f"User {user_id} added to organization {org_id} with role {role}",
            "data": response_data
        }
    except Exception as e:
        logging.error(f"Error adding user to organization: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error adding user to organization: {str(e)}"
        )

@router.post("/set-callrail-api-key/{company_id}")
@require_role("exec")
@require_tenant_ownership("company_id")
async def set_callrail_api_key(
    request: Request,
    company_id: str,
    api_key: str,
    db: Session = Depends(get_db)
):
    """
    Manually set the CallRail API key for a company.
    """
    # Get the company
    company_record = db.query(company.Company).filter_by(id=company_id).first()
    if not company_record:
        raise HTTPException(
            status_code=404,
            detail="Company not found"
        )
    
    # Update the API key
    company_record.callrail_api_key = api_key
    company_record.updated_at = datetime.utcnow()
    db.commit()
    
    return {
        "success": True,
        "message": "CallRail API key updated successfully"
    }

@router.post("/set-callrail-account-id/{company_id}")
@require_role("exec")
@require_tenant_ownership("company_id")
async def set_callrail_account_id(
    request: Request,
    company_id: str,
    account_id: str,
    db: Session = Depends(get_db)
):
    """
    Manually set the CallRail account ID for a company.
    """
    # Get the company
    company_record = db.query(company.Company).filter_by(id=company_id).first()
    if not company_record:
        raise HTTPException(
            status_code=404,
            detail="Company not found"
        )
    
    # Update the account ID
    company_record.callrail_account_id = account_id
    company_record.updated_at = datetime.utcnow()
    db.commit()
    
    return {
        "success": True,
        "message": "CallRail account ID updated successfully"
    }

@router.get("/by-phone/{phone_number}")
async def get_company_by_phone(phone_number: str, db: Session = Depends(get_db)):
    """
    Lookup a company by phone number and return its name.
    
    Args:
        phone_number: The phone number to search for
        
    Returns:
        Company name if found, 404 error if not found
    """
    # Query the database for a company with this phone number
    company_record = db.query(company.Company).filter_by(phone_number=phone_number).first()
    
    if not company_record:
        raise HTTPException(status_code=404, detail="No company found with this phone number")
    
    # Return only the company name
    return {
        "company_name": company_record.name
    }
