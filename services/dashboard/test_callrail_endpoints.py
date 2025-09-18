"""
Script to test CallRail endpoints for manually setting API key and account ID.

Usage:
1. Set environment variables: CALLRAIL_API_KEY_TEST, CALLRAIL_ACCOUNT_ID_TEST
2. Make sure you have the company ID
3. Run this script with Python

python test_callrail_endpoints.py
"""

import requests
import json
import os
import sys

# Load test credentials from environment
API_BASE_URL = "https://tv-mvp-test.fly.dev"
COMPANY_ID = "org_2vNbGs3yx3ZFNGrAeSiRSJh184F"
CALLRAIL_API_KEY = os.getenv("CALLRAIL_API_KEY_TEST")
CALLRAIL_ACCOUNT_ID = os.getenv("CALLRAIL_ACCOUNT_ID_TEST")

# Check if test credentials are available
if not CALLRAIL_API_KEY or not CALLRAIL_ACCOUNT_ID:
    print("❌ Test credentials not found in environment variables.")
    print("Please set CALLRAIL_API_KEY_TEST and CALLRAIL_ACCOUNT_ID_TEST environment variables.")
    print("Skipping test...")
    sys.exit(0)

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