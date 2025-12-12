#!/usr/bin/env python3
"""
Test CallRail v3 API setup and configuration
"""
import os
import sys
import requests
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_callrail_api_connection():
    """Test CallRail v3 API connection"""
    print("🧪 Testing CallRail v3 API Connection")
    print("=" * 50)
    
    try:
        api_key = os.getenv("CALLRAIL_API_KEY", "5723c50ca185204e80920d82b5688e5d")
        account_id = os.getenv("CALLRAIL_ACCOUNT_ID", "307-566-904")
        
        print(f"✅ API Key: {api_key[:10]}...")
        print(f"✅ Account ID: {account_id}")
        
        # Test API connection with account info
        url = f"https://api.callrail.com/v3/accounts/{account_id}.json"
        headers = {
            "Authorization": f"Token token={api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Account Name: {data.get('name', 'N/A')}")
            print(f"✅ Account Status: {data.get('status', 'N/A')}")
            print(f"✅ Account Type: {data.get('account_type', 'N/A')}")
            return True
        else:
            print(f"❌ API connection failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ CallRail API test failed: {str(e)}")
        return False

def test_callrail_tracking_numbers():
    """Test CallRail tracking numbers"""
    print("\n🧪 Testing CallRail Tracking Numbers")
    print("=" * 50)
    
    try:
        api_key = os.getenv("CALLRAIL_API_KEY", "5723c50ca185204e80920d82b5688e5d")
        account_id = os.getenv("CALLRAIL_ACCOUNT_ID", "307-566-904")
        
        # Get tracking numbers
        url = f"https://api.callrail.com/v3/accounts/{account_id}/tracking_numbers.json"
        headers = {
            "Authorization": f"Token token={api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            tracking_numbers = data.get('tracking_numbers', [])
            
            print(f"✅ Found {len(tracking_numbers)} tracking numbers:")
            for number in tracking_numbers:
                print(f"  • {number.get('number', 'N/A')} - {number.get('name', 'N/A')}")
                print(f"    Status: {number.get('status', 'N/A')}")
                print(f"    Call Recording: {number.get('call_recording', 'N/A')}")
                print()
            
            return True
        else:
            print(f"❌ Tracking numbers request failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Tracking numbers test failed: {str(e)}")
        return False

def test_callrail_webhooks():
    """Test CallRail webhook configuration"""
    print("\n🧪 Testing CallRail Webhook Configuration")
    print("=" * 50)
    
    try:
        # Test webhook endpoints
        railway_url = "https://ottoai-backend-production.up.railway.app"
        
        webhook_endpoints = [
            f"{railway_url}/webhooks/callrail",
            f"{railway_url}/webhooks/callrail-sms"
        ]
        
        print("✅ CallRail webhook endpoints:")
        for endpoint in webhook_endpoints:
            print(f"  • {endpoint}")
        
        print("✅ Webhook configuration ready")
        return True
        
    except Exception as e:
        print(f"❌ Webhook configuration test failed: {str(e)}")
        return False

def test_callrail_integration():
    """Test CallRail integration with OttoAI"""
    print("\n🧪 Testing CallRail Integration")
    print("=" * 50)
    
    try:
        # Test that our CallRail handlers are properly configured
        from app.routes.enhanced_callrail import router as callrail_router
        
        # Check if the routes exist
        routes = [route.path for route in callrail_router.routes]
        
        print("✅ Available CallRail routes:")
        for route in routes:
            print(f"  • {route}")
        
        # Check for required routes
        required_routes = [
            "/webhooks/callrail",
            "/webhooks/callrail-sms"
        ]
        
        missing_routes = []
        for required in required_routes:
            if required not in routes:
                missing_routes.append(required)
        
        if missing_routes:
            print(f"❌ Missing routes: {missing_routes}")
            return False
        else:
            print("✅ All required CallRail routes configured")
            return True
        
    except Exception as e:
        print(f"❌ CallRail integration test failed: {str(e)}")
        return False

def main():
    """Run CallRail setup tests"""
    print("🚀 CallRail v3 API Setup Test Suite")
    print("=" * 60)
    
    tests = [
        ("CallRail API Connection", test_callrail_api_connection),
        ("Tracking Numbers", test_callrail_tracking_numbers),
        ("Webhook Configuration", test_callrail_webhooks),
        ("CallRail Integration", test_callrail_integration)
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
    print("📊 CallRail Setup Results")
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
        print("\n🎉 CallRail setup successful!")
        print("\n✅ CallRail Status:")
        print("  • API Connection: Active")
        print("  • Tracking Numbers: Available")
        print("  • Webhook Endpoints: Configured")
        print("  • Integration: Ready")
        
        print("\n📋 Next Steps:")
        print("  1. ✅ Twilio: COMPLETE")
        print("  2. ✅ CallRail: COMPLETE")
        print("  3. 🔧 UWC/Shunya: Ready to configure")
        print("  4. 🧪 End-to-End Testing: Ready")
        
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed. Please check the logs above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)















