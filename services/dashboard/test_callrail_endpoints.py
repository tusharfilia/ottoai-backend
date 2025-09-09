"""
Script to test CallRail endpoints for manually setting API key and account ID.

Usage:
1. Make sure you have the company ID
2. Update the variables at the top of the script
3. Run this script with Python

python test_callrail_endpoints.py
"""

import requests
import json

# Update these variables
API_BASE_URL = "https://tv-mvp-test.fly.dev"
COMPANY_ID = "org_2vNbGs3yx3ZFNGrAeSiRSJh184F"
CALLRAIL_API_KEY = "24dc8d59e4de1ccc694961ae252fa257"
CALLRAIL_ACCOUNT_ID = "307-566-904"

# Headers for the request
headers = {
    "Content-Type": "application/json"
}

def test_set_callrail_api_key():
    """Test setting the CallRail API key for a company"""
    url = f"{API_BASE_URL}/company/set-callrail-api-key/{COMPANY_ID}"
    params = {
        "api_key": CALLRAIL_API_KEY
    }
    
    print(f"Sending request to: {url}")
    response = requests.post(url, params=params, headers=headers)
    
    if response.status_code == 200:
        print(f"Status code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return True
    else:
        print(f"Status code: {response.status_code}")
        print(f"Response text: {response.text}")
        return False

def test_set_callrail_account_id():
    """Test setting the CallRail account ID for a company"""
    url = f"{API_BASE_URL}/company/set-callrail-account-id/{COMPANY_ID}"
    params = {
        "account_id": CALLRAIL_ACCOUNT_ID
    }
    
    print(f"Sending request to: {url}")
    response = requests.post(url, params=params, headers=headers)
    
    if response.status_code == 200:
        print(f"Status code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return True
    else:
        print(f"Status code: {response.status_code}")
        print(f"Response text: {response.text}")
        return False

if __name__ == "__main__":
    print("Testing CallRail endpoints...\n")
    
    print("Setting CallRail API key...")
    if test_set_callrail_api_key():
        print("✅ Successfully set CallRail API key")
    else:
        print("❌ Failed to set CallRail API key")
    
    print("\nSetting CallRail account ID...")
    if test_set_callrail_account_id():
        print("✅ Successfully set CallRail account ID")
    else:
        print("❌ Failed to set CallRail account ID") 