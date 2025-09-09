import requests
import json
import logging
import time
import os
import random
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
BASE_URL = "https://tv-mvp-test.fly.dev"
# OR "https://tv-mvp-dev.fly.dev"

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

# Sample addresses for more realistic data
SAMPLE_ADDRESSES = [
    "123 Main St, Springfield, IL 62701",
    "456 Oak Ave, Riverdale, NY 10471",
    "789 Pine Blvd, Portland, OR 97201",
    "101 Maple Dr, Austin, TX 78701",
    "202 Cedar Ln, Miami, FL 33101",
    "303 Elm St, Chicago, IL 60601",
    "404 Birch Rd, Seattle, WA 98101",
    "505 Willow Way, Denver, CO 80201",
    "606 Spruce Circle, Boston, MA 02101",
    "707 Redwood Ct, San Francisco, CA 94101"
]

# Sample names for more realistic data
SAMPLE_NAMES = [
    "John Smith",
    "Emma Johnson",
    "Michael Williams",
    "Sophia Brown",
    "William Jones",
    "Olivia Garcia",
    "James Miller",
    "Ava Davis",
    "Robert Wilson",
    "Isabella Martinez"
]

def generate_phone_number():
    """Generate a random US phone number"""
    area_code = random.randint(200, 999)
    prefix = random.randint(200, 999)
    line = random.randint(1000, 9999)
    return f"+1{area_code}{prefix}{line}"

def create_test_call(company_id, stage="booked_quote"):
    """
    Create a test call/appointment at different stages
    
    Stages:
    - booked_quote: Call is booked but not assigned to a rep
    - assigned: Call is assigned to a rep but not yet completed
    - completed: Call has been completed, but no purchase decision
    - bought: Customer has made a purchase
    - lost_sale: Sale was lost
    """
    # Add trailing slash to prevent redirect
    url = f"{BASE_URL}/add-call"
    
    # Generate a random future date for the quote (1-14 days in the future)
    days_in_future = random.randint(1, 14)
    quote_date = (datetime.now() + timedelta(days=days_in_future)).strftime("%Y-%m-%d %H:%M:%S")
    
    # Basic parameters for all call types
    params = {
        "company_id": company_id,
        "name": random.choice(SAMPLE_NAMES),
        "phone_number": generate_phone_number(),
        "address": random.choice(SAMPLE_ADDRESSES),
        "quote_date": quote_date,
        "booked": "true",  # All test calls are booked
        "missed_call": "false"
    }
    
    try:
        # Create the initial call record
        logger.info(f"Creating test call with params: {params}")
        response = session.post(url, params=params)
        logger.info(f"Response status code: {response.status_code}")
        
        if response.status_code >= 400:
            logger.error(f"Error creating call: {response.text}")
            return None
            
        call_data = response.json()
        logger.info(f"Call created successfully: {call_data}")
        
        # If we need to modify the call based on stage
        if stage != "booked_quote":
            call_id = call_data.get("call_id")
            if call_id:
                update_call_for_stage(call_id, company_id, stage)
            else:
                logger.error("No call_id in response, cannot update call stage")
        
        return call_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating test call: {str(e)}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            logger.error(f"Response text: {e.response.text}")
        return None

def update_call_for_stage(call_id, company_id, stage):
    """Update a call based on the desired stage"""
    url = f"{BASE_URL}/update-call-status"
    
    # Prepare update data based on stage
    update_data = {"call_id": call_id}
    
    if stage == "assigned":
        # For this we need to first get available reps for the company
        reps = get_sales_reps(company_id)
        if reps and len(reps) > 0:
            rep_id = reps[0].get("user_id")  # Get first rep's ID
            update_data["assigned_rep_id"] = rep_id
        else:
            logger.warning(f"No sales reps found for company {company_id}, cannot assign call")
            return None
    
    elif stage == "completed":
        # Call is completed but customer hasn't made a decision yet
        reps = get_sales_reps(company_id)
        if reps and len(reps) > 0:
            rep_id = reps[0].get("user_id")
            update_data["assigned_rep_id"] = rep_id
        # No additional status needed - this represents a call that happened but no purchase decision
    
    elif stage == "bought":
        # Customer has purchased
        reps = get_sales_reps(company_id)
        if reps and len(reps) > 0:
            rep_id = reps[0].get("user_id")
            update_data["assigned_rep_id"] = rep_id
        update_data["bought"] = True
        update_data["price_if_bought"] = round(random.uniform(1000, 10000), 2)
    
    elif stage == "lost_sale":
        # Sale was lost
        reps = get_sales_reps(company_id)
        if reps and len(reps) > 0:
            rep_id = reps[0].get("user_id")
            update_data["assigned_rep_id"] = rep_id
        update_data["bought"] = False
        
        # Possible reasons for lost sales
        lost_reasons = [
            "Price too high",
            "Chose competitor",
            "Changed mind",
            "No longer interested",
            "Budget constraints",
            "Timeline changed"
        ]
        update_data["reason_not_bought_homeowner"] = random.choice(lost_reasons)
    
    try:
        logger.info(f"Updating call {call_id} to stage '{stage}' with data: {update_data}")
        response = session.post(url, json=update_data)
        
        if response.status_code >= 400:
            logger.error(f"Error updating call: {response.text}")
            return None
            
        update_result = response.json()
        logger.info(f"Call updated successfully: {update_result}")
        return update_result
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating call: {str(e)}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            logger.error(f"Response text: {e.response.text}")
        return None

def get_sales_reps(company_id):
    """Get available sales reps for a company"""
    # Based on the endpoint in routes/sales_rep.py: @router.get("")
    url = f"{BASE_URL}/sales-rep"
    headers = {"Clerk-Organization": company_id}
    
    try:
        # Need to include the organization in headers for authentication
        response = session.get(url, headers=headers)
        if response.status_code >= 400:
            logger.error(f"Error getting sales reps: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return []
            
        result = response.json()
        logger.info(f"Found {len(result.get('reps', []))} sales reps")
        return result.get("reps", [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting sales reps: {str(e)}")
        return []

def create_bulk_test_calls(company_id, count=5, stage="booked_quote"):
    """Create multiple test calls at once"""
    logger.info(f"Creating {count} test calls at stage '{stage}' for company {company_id}")
    
    created_calls = []
    for i in range(count):
        call_data = create_test_call(company_id, stage)
        if call_data:
            created_calls.append(call_data)
    
    logger.info(f"Successfully created {len(created_calls)} out of {count} requested calls")
    return created_calls

def main():
    # Get company ID from environment or use a default if provided
    company_id = "org_2vQmaIXJvWrMGzWJbzB9Lysjlxg"
    # os.environ.get("COMPANY_ID")
    
    if not company_id:
        logger.error("No company ID provided. Set the COMPANY_ID environment variable.")
        logger.info("You can create a company first using create_full_org.py")
        return
    
    # Create a variety of test calls
    logger.info(f"Creating test calls for company ID: {company_id}")
    
    # Create 10 booked quote calls (not assigned to a rep yet)
    booked_calls = create_bulk_test_calls(company_id, 10, "booked_quote")
    logger.info(f"Created {len(booked_calls)} booked quote calls")
    
    # Create 3 assigned calls
    assigned_calls = create_bulk_test_calls(company_id, 3, "assigned")
    logger.info(f"Created {len(assigned_calls)} assigned calls")
    
    # Create 2 completed calls
    completed_calls = create_bulk_test_calls(company_id, 2, "completed")
    logger.info(f"Created {len(completed_calls)} completed calls")
    
    # Create 3 bought calls
    bought_calls = create_bulk_test_calls(company_id, 3, "bought")
    logger.info(f"Created {len(bought_calls)} bought calls")
    
    # Create 2 lost sale calls
    lost_calls = create_bulk_test_calls(company_id, 2, "lost_sale")
    logger.info(f"Created {len(lost_calls)} lost sale calls")
    
    # Summary
    total_calls = len(booked_calls) + len(assigned_calls) + len(completed_calls) + len(bought_calls) + len(lost_calls)
    logger.info(f"Successfully created {total_calls} test calls across all stages")

if __name__ == "__main__":
    main() 