import requests
import json
import logging
import time
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
BASE_URL = "https://tv-mvp-test.fly.dev"
# OR "https://tv-mvp-dev.fly.dev"
# also maybe need in services/dashboard

# Configure retry strategy
retry_strategy = Retry(
    total=3,  # number of retries
    backoff_factor=1,  # wait 1, 2, 4 seconds between retries
    status_forcelist=[500, 502, 503, 504],  # HTTP status codes to retry on
)

# Create a session with retry strategy
session = requests.Session()
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

def create_company(name, phone_number, address=None):
    """Create a new company"""
    # Add trailing slash to prevent redirect
    url = f"{BASE_URL}/webhook/company/"
    
    # Generate a unique timestamp to avoid conflicts
    timestamp = int(time.time())
    
    params = {
        "name": name,
        "phone_number": phone_number,
        "address": address or f"Default Address {timestamp}"
    }
    
    try:
        # Send parameters in query string
        logger.info(f"Attempting to create company with params: {params}")
        response = session.post(url, params=params)
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {response.headers}")
        logger.info(f"Response body: {response.text}")
        response.raise_for_status()
        logger.info(f"Company created successfully: {response.json()}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating company: {str(e)}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response text: {e.response.text}")
        return None

def add_user_to_organization(org_id, user_id, role):
    """Add a user to a Clerk organization"""
    url = f"{BASE_URL}/company/organizations/{org_id}/memberships"
    data = {
        "user_id": user_id,
        "role": "org:member"  # All users will be members
    }
    
    try:
        logger.info(f"Adding user {user_id} to organization {org_id} as member")
        response = session.post(url, json=data)
        response.raise_for_status()
        logger.info(f"Successfully added user to organization: {response.json()}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error adding user to organization: {str(e)}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response text: {e.response.text}")
        return None

def set_user_metadata(user_id, role, company_id):
    """Set public metadata for a user (sales_rep or sales_manager)"""
    url = f"{BASE_URL}/user/metadata/{user_id}"
    
    # Map backend roles to mobile app roles
    role_mapping = {
        "manager": "sales_manager",
        "rep": "sales_rep",
        "admin": "admin"
    }
    
    # Prepare metadata payload
    data = {
        "publicMetadata": {
            "role": role_mapping.get(role, "sales_rep"),
            "company": company_id  # Using "company" instead of "company_id"
        }
    }
    
    try:
        logger.info(f"Setting metadata for user {user_id} with role: {role_mapping.get(role, 'sales_rep')} and company: {company_id}")
        response = session.patch(url, json=data)
        response.raise_for_status()
        logger.info(f"Successfully set user metadata: {response.json()}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error setting user metadata: {str(e)}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response text: {e.response.text}")
        return None

def create_manager(name, email, phone_number, company_id, password=None, username=None):
    """Create a new sales manager"""
    # Add trailing slash to prevent redirect
    url = f"{BASE_URL}/webhook/sales-manager/"
    if not username:
        username = name.lower().replace(" ", "")
    if not password:
        timestamp = int(time.time())
        password = f"SecureP@ssw0rd_{timestamp}"
    
    params = {
        "name": name,
        "email": email,
        "phone_number": phone_number,
        "company_id": company_id,  # Now expects Clerk org ID
        "password": password,
        "username": username
    }
    
    try:
        # Send parameters in query string
        logger.info(f"Attempting to create manager with params: {params}")
        response = session.post(url, params=params)
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {response.headers}")
        logger.info(f"Response body: {response.text}")
        response.raise_for_status()
        logger.info(f"Manager created successfully: {response.json()}")
        
        # Add manager to organization
        response_data = response.json()
        if response_data.get("clerk_user_id") and response_data.get("clerk_org_id"):
            add_user_to_organization(
                response_data["clerk_org_id"],
                response_data["clerk_user_id"],
                "manager"
            )
            
            # Set user metadata for the mobile app
            set_user_metadata(
                response_data["clerk_user_id"],
                "manager",
                response_data["clerk_org_id"]  # Use the org_id as company_id
            )
        
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating manager: {str(e)}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response text: {e.response.text}")
        return None

def create_rep(name, email, phone_number, company_id, manager_id, password=None, username=None):
    """Create a new sales rep"""
    # Add trailing slash to prevent redirect
    url = f"{BASE_URL}/webhook/sales-rep/"
    if not username:
        username = name.lower().replace(" ", "")
    if not password:
        timestamp = int(time.time())
        password = f"SecureP@ssw0rd_{timestamp}"
    
    params = {
        "name": name,
        "email": email,
        "phone_number": phone_number,
        "company_id": company_id,  # Now expects Clerk org ID
        "manager_id": manager_id,  # Now expects Clerk user ID
        "password": password,
        "username": username
    }
    
    try:
        # Send parameters in query string
        logger.info(f"Attempting to create rep with params: {params}")
        response = session.post(url, params=params)
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {response.headers}")
        logger.info(f"Response body: {response.text}")
        response.raise_for_status()
        logger.info(f"Rep created successfully: {response.json()}")
        
        # Add rep to organization
        response_data = response.json()
        if response_data.get("clerk_user_id") and response_data.get("clerk_org_id"):
            add_user_to_organization(
                response_data["clerk_org_id"],
                response_data["clerk_user_id"],
                "rep"
            )
            
            # Set user metadata for the mobile app
            set_user_metadata(
                response_data["clerk_user_id"],
                "rep",
                response_data["clerk_org_id"]  # Use the org_id as company_id
            )
        
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating rep: {str(e)}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response text: {e.response.text}")
        return None

def update_existing_users_metadata(company_id):
    """Update the public metadata for existing users in a company to add the company_id field"""
    try:
        # Get all users for this company
        url = f"{BASE_URL}/company/{company_id}/users"
        logger.info(f"Fetching users for company {company_id}")
        response = session.get(url)
        response.raise_for_status()
        
        users = response.json().get("users", [])
        logger.info(f"Found {len(users)} users to update")
        
        # Update each user's metadata
        for user in users:
            user_id = user.get("id")
            role = "manager" if user.get("role") == "manager" else "rep"
            
            if user_id:
                set_user_metadata(user_id, role, company_id)
                logger.info(f"Updated metadata for user {user_id}")
            
        return {"success": True, "users_updated": len(users)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating user metadata: {str(e)}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response text: {e.response.text}")
        return {"success": False, "error": str(e)}

def main():
    import sys
    
    # Check if we're just updating existing users
    if len(sys.argv) > 1 and sys.argv[1] == "--update-metadata":
        if len(sys.argv) < 3:
            logger.error("Please provide a company_id")
            logger.error("Usage: python create_full_org.py --update-metadata <company_id>")
            return
            
        company_id = sys.argv[2]
        result = update_existing_users_metadata(company_id)
        logger.info(f"Metadata update result: {result}")
        return
    
    # Create a company with CallRail tracking number
    timestamp = int(time.time())
    company_data = create_company(
        name=f"Test Company {timestamp}",
        phone_number="+13019457791",  # Using CallRail tracking number
        address="123 Test St, Test City, TS 12345"
    )
    
    if not company_data:
        logger.error("Failed to create company. Exiting.")
        return
    
    # Get company ID (which is now a string)
    company_id = company_data.get("company_id") or company_data.get("clerk_org_id")
    
    if not company_id:
        logger.error("No company ID returned. Exiting.")
        return

    logger.info(f"Successfully created company with ID: {company_id}")
    
    # Create a manager with unique email, username, and phone number
    manager_data = create_manager(
        name="John Smith",
        email=f"john.smith.{timestamp}@testcompany18.com",
        phone_number=f"555-123-{(timestamp + 1) % 10000:04d}",
        company_id=company_id,
        username=f"johnsmith18_{timestamp}"
    )
    
    if not manager_data or manager_data.get("status") == "error":
        logger.error("Failed to create manager. Exiting.")
        if manager_data:
            logger.error(f"Error details: {manager_data.get('message')} - {manager_data.get('details', '')}")
        return
    
    manager_id = manager_data.get("manager_id")  # This is now the Clerk user ID
    
    if not manager_id:
        logger.error("No manager_id returned. Cannot create sales reps without a manager.")
        return
    
    logger.info(f"Successfully created manager with ID: {manager_id}")
    
    # Create two reps with unique emails and phone numbers
    rep1_data = create_rep(
        name="Alice Johnson",
        email=f"alice.johnson.{timestamp}@testcompany18.com",
        phone_number=f"555-123-{(timestamp + 2) % 10000:04d}",
        company_id=company_id,
        manager_id=manager_id,
        username=f"alicejohnson18_{timestamp}"
    )
    
    rep2_data = create_rep(
        name="Bob Wilson",
        email=f"bob.wilson.{timestamp}@testcompany18.com",
        phone_number=f"555-123-{(timestamp + 3) % 10000:04d}",
        company_id=company_id,
        manager_id=manager_id,
        username=f"bobwilson18_{timestamp}"
    )

if __name__ == "__main__":
    main() 