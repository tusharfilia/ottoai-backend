#!/usr/bin/env python3
"""
Test Twilio setup and configuration
"""
import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_twilio_credentials():
    """Test Twilio credentials and connection"""
    print("🧪 Testing Twilio Credentials")
    print("=" * 50)
    
    try:
        from twilio.rest import Client
        
        # Get credentials from environment
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        if not account_sid or not auth_token:
            print("❌ Twilio credentials not found in environment")
            return False
        
        print(f"✅ Account SID: {account_sid[:10]}...")
        print(f"✅ Auth Token: {auth_token[:10]}...")
        
        # Initialize Twilio client
        client = Client(account_sid, auth_token)
        
        # Test connection by fetching account info
        account = client.api.accounts(account_sid).fetch()
        
        print(f"✅ Account Status: {account.status}")
        print(f"✅ Account Name: {account.friendly_name}")
        print(f"✅ Account Type: {account.type}")
        
        return True
        
    except Exception as e:
        print(f"❌ Twilio connection failed: {str(e)}")
        return False

def test_twilio_phone_numbers():
    """Test Twilio phone numbers"""
    print("\n🧪 Testing Twilio Phone Numbers")
    print("=" * 50)
    
    try:
        from twilio.rest import Client
        
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        client = Client(account_sid, auth_token)
        
        # Fetch all phone numbers
        phone_numbers = client.incoming_phone_numbers.list()
        
        print(f"✅ Found {len(phone_numbers)} phone numbers:")
        
        for number in phone_numbers:
            print(f"  • {number.phone_number} ({number.friendly_name})")
            print(f"    - Voice URL: {number.voice_url}")
            print(f"    - SMS URL: {number.sms_url}")
            print(f"    - Capabilities: Voice={number.capabilities.get('voice', False)}, SMS={number.capabilities.get('sms', False)}")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ Phone numbers test failed: {str(e)}")
        return False

def test_twilio_sms_sending():
    """Test Twilio SMS sending (dry run)"""
    print("\n🧪 Testing Twilio SMS Configuration")
    print("=" * 50)
    
    try:
        from app.services.twilio_service import TwilioService
        
        # Initialize service
        service = TwilioService()
        
        # Test phone number normalization
        test_numbers = [
            "1234567890",
            "+1234567890", 
            "123-456-7890",
            "(123) 456-7890"
        ]
        
        print("✅ Phone number normalization tests:")
        for number in test_numbers:
            normalized = service._normalize_phone_number(number)
            print(f"  • {number} → {normalized}")
        
        print("\n✅ Twilio service initialized successfully")
        print("✅ SMS configuration ready")
        
        return True
        
    except Exception as e:
        print(f"❌ SMS configuration test failed: {str(e)}")
        return False

def main():
    """Run Twilio setup tests"""
    print("🚀 Twilio Setup Test Suite")
    print("=" * 60)
    
    tests = [
        ("Twilio Credentials", test_twilio_credentials),
        ("Phone Numbers", test_twilio_phone_numbers),
        ("SMS Configuration", test_twilio_sms_sending)
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
    print("📊 Twilio Setup Results")
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
        print("\n🎉 Twilio setup successful!")
        print("\n✅ Twilio Status:")
        print("  • Credentials: Valid")
        print("  • Phone Numbers: Available")
        print("  • SMS Service: Ready")
        print("\n📋 Next Steps:")
        print("  1. Choose which phone number to use as TWILIO_FROM_NUMBER")
        print("  2. Configure webhook URLs for voice and SMS")
        print("  3. Test end-to-end SMS flow")
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed. Please check the logs above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)









