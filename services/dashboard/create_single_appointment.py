import requests
import random
import logging
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
BASE_URL = "https://tv-mvp-test.fly.dev"

# Configure retry strategy
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504],
)

# Create a session with retry strategy
session = requests.Session()
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

# Sample data for the appointment
SAMPLE_ADDRESSES = [
    "123 Main St, Springfield, IL 62701",
    "456 Oak Ave, Riverdale, NY 10471",
    "789 Pine Blvd, Portland, OR 97201",
    "101 Maple Dr, Austin, TX 78701",
    "202 Cedar Ln, Miami, FL 33101"
]

SAMPLE_NAMES = [
    "John Smith",
    "Emma Johnson",
    "Michael Williams",
    "Sophia Brown",
    "William Jones"
]

def generate_phone_number():
    """Generate a random US phone number"""
    area_code = random.randint(200, 999)
    prefix = random.randint(200, 999)
    line = random.randint(1000, 9999)
    return f"+1{area_code}{prefix}{line}"

def create_single_appointment():
    """Create a single appointment for current time + 1 minute"""
    # Fixed company ID
    company_id = "org_2wICtXwbvjSCtXHHkFZk13s2nMn"
    
    # Generate appointment time (current time + 1 minute)
    quote_date = (datetime.now() + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    
    # Prepare parameters for the appointment
    params = {
        "company_id": company_id,
        "name": random.choice(SAMPLE_NAMES),
        "phone_number": generate_phone_number(),
        "address": random.choice(SAMPLE_ADDRESSES),
        "quote_date": quote_date,
        "booked": "true",
        "missed_call": "false"
    }
    
    # Send the request to create the appointment
    url = f"{BASE_URL}/add-call"
    
    try:
        logger.info(f"Creating appointment with params: {params}")
        response = session.post(url, params=params)
        logger.info(f"Response status code: {response.status_code}")
        
        if response.status_code >= 400:
            logger.error(f"Error creating appointment: {response.text}")
            return None
            
        call_data = response.json()
        logger.info(f"Appointment created successfully for {quote_date}: {call_data}")
        return call_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating appointment: {str(e)}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            logger.error(f"Response text: {e.response.text}")
        return None

if __name__ == "__main__":
    logger.info("Creating a single booked appointment for current time + 1 minute")
    result = create_single_appointment()
    if result:
        logger.info(f"Successfully created appointment with ID: {result.get('call_id')}")
    else:
        logger.error("Failed to create appointment") 