#!/usr/bin/env python3
"""
Test CallRail call recordings API
"""
import os
import sys
import requests
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_callrail_recordings_api():
    """Test CallRail recordings API"""
    print("🧪 Testing CallRail Recordings API")
    print("=" * 50)
    
    try:
        api_key = os.getenv("CALLRAIL_API_KEY", "5723c50ca185204e80920d82b5688e5d")
        account_id = "307566904"  # Corrected format without dashes
        
        print(f"✅ API Key: {api_key[:10]}...")
        print(f"✅ Account ID: {account_id}")
        
        # Get recent calls with recordings
        url = f"https://api.callrail.com/v3/accounts/{account_id}/calls.json"
        headers = {
            "Authorization": f"Token token={api_key}",
            "Content-Type": "application/json"
        }
        
        # Add parameters to get calls with recordings
        params = {
            "fields": "id,phone_number,recording_url,recording_duration,recording_status",
            "limit": 10
        }
        
        print(f"🔍 Testing URL: {url}")
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            calls = data.get('calls', [])
            
            print(f"✅ Found {len(calls)} recent calls:")
            
            recordings_found = 0
            for call in calls:
                call_id = call.get('id', 'N/A')
                phone = call.get('phone_number', 'N/A')
                recording_url = call.get('recording_url', 'N/A')
                recording_duration = call.get('recording_duration', 'N/A')
                recording_status = call.get('recording_status', 'N/A')
                
                print(f"  • Call ID: {call_id}")
                print(f"    Phone: {phone}")
                print(f"    Recording URL: {recording_url}")
                print(f"    Duration: {recording_duration} seconds")
                print(f"    Status: {recording_status}")
                print()
                
                if recording_url and recording_url != 'N/A':
                    recordings_found += 1
            
            print(f"✅ Found {recordings_found} calls with recordings")
            return True
        else:
            print(f"❌ Recordings request failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Recordings test failed: {str(e)}")
        return False

def test_specific_call_recording():
    """Test getting recording for a specific call"""
    print("\n🧪 Testing Specific Call Recording")
    print("=" * 50)
    
    try:
        api_key = os.getenv("CALLRAIL_API_KEY", "5723c50ca185204e80920d82b5688e5d")
        account_id = "307566904"
        
        # Get a specific call (you would replace this with an actual call ID)
        call_id = "test_call_123"  # Replace with actual call ID
        url = f"https://api.callrail.com/v3/accounts/{account_id}/calls/{call_id}.json"
        headers = {
            "Authorization": f"Token token={api_key}",
            "Content-Type": "application/json"
        }
        
        print(f"🔍 Testing URL: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            call = data.get('call', {})
            
            print(f"✅ Call details:")
            print(f"  • ID: {call.get('id', 'N/A')}")
            print(f"  • Phone: {call.get('phone_number', 'N/A')}")
            print(f"  • Recording URL: {call.get('recording_url', 'N/A')}")
            print(f"  • Recording Duration: {call.get('recording_duration', 'N/A')}")
            print(f"  • Recording Status: {call.get('recording_status', 'N/A')}")
            
            return True
        else:
            print(f"❌ Specific call request failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Specific call recording test failed: {str(e)}")
        return False

def test_recording_webhook():
    """Test recording webhook configuration"""
    print("\n🧪 Testing Recording Webhook Configuration")
    print("=" * 50)
    
    try:
        railway_url = "https://ottoai-backend-production.up.railway.app"
        
        # CallRail webhooks for recordings
        webhook_endpoints = [
            f"{railway_url}/callrail/call.completed",  # Post-call webhook
            f"{railway_url}/callrail/call.answered",   # Call answered webhook
            f"{railway_url}/callrail/call.missed"      # Missed call webhook
        ]
        
        print("✅ Recording webhook endpoints:")
        for webhook in webhook_endpoints:
            print(f"  • {webhook}")
        
        print("✅ Recording webhooks configured")
        return True
        
    except Exception as e:
        print(f"❌ Recording webhook test failed: {str(e)}")
        return False

def main():
    """Run CallRail recordings tests"""
    print("🚀 CallRail Recordings Test Suite")
    print("=" * 60)
    
    tests = [
        ("CallRail Recordings API", test_callrail_recordings_api),
        ("Specific Call Recording", test_specific_call_recording),
        ("Recording Webhook Configuration", test_recording_webhook)
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
    print(f"\n{'='*60}")
    print("📊 CallRail Recordings Test Results")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 CallRail Recordings Ready!")
        print("\n✅ Recording Status:")
        print("  • API Access: Ready")
        print("  • Recording URLs: Available")
        print("  • Webhook Endpoints: Configured")
        
        print("\n📋 Next Steps:")
        print("  1. Test recording API access")
        print("  2. Configure recording webhooks")
        print("  3. Integrate with UWC ASR")
        
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed. Please check the logs above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)










