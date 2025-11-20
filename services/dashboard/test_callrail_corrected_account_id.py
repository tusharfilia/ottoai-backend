#!/usr/bin/env python3
"""
Test CallRail v3 API with corrected account ID format
"""
import os
import sys
import requests
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_callrail_api_with_corrected_account_id():
    """Test CallRail v3 API with corrected account ID"""
    print("🧪 Testing CallRail v3 API with Corrected Account ID")
    print("=" * 60)
    
    try:
        api_key = os.getenv("CALLRAIL_API_KEY", "5723c50ca185204e80920d82b5688e5d")
        account_id = "307566904"  # Corrected format without dashes
        
        print(f"✅ API Key: {api_key[:10]}...")
        print(f"✅ Account ID: {account_id} (corrected format)")
        
        # Test API connection with corrected account ID
        url = f"https://api.callrail.com/v3/accounts/{account_id}.json"
        headers = {
            "Authorization": f"Token token={api_key}",
            "Content-Type": "application/json"
        }
        
        print(f"🔍 Testing URL: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Account Name: {data.get('name', 'N/A')}")
            print(f"✅ Account Status: {data.get('status', 'N/A')}")
            print(f"✅ Account Type: {data.get('account_type', 'N/A')}")
            print(f"✅ Account ID: {data.get('id', 'N/A')}")
            return True
        else:
            print(f"❌ API connection failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ CallRail API test failed: {str(e)}")
        return False

def test_callrail_tracking_numbers_corrected():
    """Test CallRail tracking numbers with corrected account ID"""
    print("\n🧪 Testing CallRail Tracking Numbers (Corrected Account ID)")
    print("=" * 60)
    
    try:
        api_key = os.getenv("CALLRAIL_API_KEY", "5723c50ca185204e80920d82b5688e5d")
        account_id = "307566904"  # Corrected format without dashes
        
        print(f"✅ API Key: {api_key[:10]}...")
        print(f"✅ Account ID: {account_id} (corrected format)")
        
        # Get tracking numbers
        url = f"https://api.callrail.com/v3/accounts/{account_id}/tracking_numbers.json"
        headers = {
            "Authorization": f"Token token={api_key}",
            "Content-Type": "application/json"
        }
        
        print(f"🔍 Testing URL: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            tracking_numbers = data.get('tracking_numbers', [])
            
            print(f"✅ Found {len(tracking_numbers)} tracking numbers:")
            for number in tracking_numbers:
                print(f"  • {number.get('number', 'N/A')} - {number.get('name', 'N/A')}")
                print(f"    Status: {number.get('status', 'N/A')}")
                print(f"    Call Recording: {number.get('call_recording', 'N/A')}")
                print(f"    Webhook URL: {number.get('webhook_url', 'N/A')}")
                print()
            
            return True
        else:
            print(f"❌ Tracking numbers request failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Tracking numbers test failed: {str(e)}")
        return False

def test_callrail_calls_endpoint():
    """Test CallRail calls endpoint"""
    print("\n🧪 Testing CallRail Calls Endpoint")
    print("=" * 60)
    
    try:
        api_key = os.getenv("CALLRAIL_API_KEY", "5723c50ca185204e80920d82b5688e5d")
        account_id = "307566904"  # Corrected format without dashes
        
        # Get recent calls
        url = f"https://api.callrail.com/v3/accounts/{account_id}/calls.json"
        headers = {
            "Authorization": f"Token token={api_key}",
            "Content-Type": "application/json"
        }
        
        print(f"🔍 Testing URL: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            calls = data.get('calls', [])
            
            print(f"✅ Found {len(calls)} recent calls:")
            for call in calls[:3]:  # Show first 3 calls
                print(f"  • Call ID: {call.get('id', 'N/A')}")
                print(f"    Phone: {call.get('phone_number', 'N/A')}")
                print(f"    Status: {call.get('status', 'N/A')}")
                print(f"    Duration: {call.get('duration', 'N/A')} seconds")
                print(f"    Recording: {call.get('recording_url', 'N/A')}")
                print()
            
            return True
        else:
            print(f"❌ Calls request failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Calls endpoint test failed: {str(e)}")
        return False

def main():
    """Run CallRail tests with corrected account ID"""
    print("🚀 CallRail v3 API Test (Corrected Account ID)")
    print("=" * 70)
    
    tests = [
        ("CallRail API Connection", test_callrail_api_with_corrected_account_id),
        ("Tracking Numbers", test_callrail_tracking_numbers_corrected),
        ("Calls Endpoint", test_callrail_calls_endpoint)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test {test_name} failed with exception: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*70}")
    print("📊 CallRail Test Results (Corrected Account ID)")
    print("=" * 70)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 CallRail API working with corrected account ID!")
        print(f"\n✅ Correct Account ID: 307566904")
        print("✅ API Connection: Active")
        print("✅ Tracking Numbers: Available")
        print("✅ Calls Endpoint: Working")
        
        print("\n📋 Next Steps:")
        print("  1. ✅ Twilio: COMPLETE")
        print("  2. ✅ CallRail: COMPLETE (with corrected account ID)")
        print("  3. 🔧 UWC/Shunya: Ready to configure")
        print("  4. 🧪 End-to-End Testing: Ready")
        
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed. Please check the logs above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)







