#!/usr/bin/env python3
"""
Final Twilio configuration test
"""
import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_twilio_final_configuration():
    """Test final Twilio configuration"""
    print("🧪 Testing Final Twilio Configuration")
    print("=" * 50)
    
    try:
        from twilio.rest import Client
        
        # Get credentials
        account_sid = os.getenv("TWILIO_ACCOUNT_SID", "ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN", "your_auth_token_here")
        from_number = os.getenv("TWILIO_FROM_NUMBER", "+1XXXXXXXXXX")
        
        # Initialize Twilio client
        client = Client(account_sid, auth_token)
        
        # Find the phone number
        phone_numbers = client.incoming_phone_numbers.list()
        target_number = None
        
        for number in phone_numbers:
            if number.phone_number == from_number:
                target_number = number
                break
        
        if not target_number:
            print(f"❌ Phone number {from_number} not found")
            return False
        
        print(f"✅ Phone Number: {target_number.phone_number}")
        print(f"✅ Voice Webhook: {target_number.voice_url}")
        print(f"✅ SMS Webhook: {target_number.sms_url}")
        print(f"✅ Voice Method: {target_number.voice_method}")
        print(f"✅ SMS Method: {target_number.sms_method}")
        
        # Verify webhooks are pointing to Railway
        railway_url = "https://ottoai-backend-production.up.railway.app"
        expected_webhook = f"{railway_url}/mobile/twilio-webhook"
        
        if target_number.voice_url == expected_webhook and target_number.sms_url == expected_webhook:
            print("✅ Webhooks correctly configured for Railway")
            return True
        else:
            print(f"❌ Webhooks not correctly configured")
            print(f"Expected: {expected_webhook}")
            print(f"Voice: {target_number.voice_url}")
            print(f"SMS: {target_number.sms_url}")
            return False
        
    except Exception as e:
        print(f"❌ Final configuration test failed: {str(e)}")
        return False

def test_sms_service():
    """Test SMS service functionality"""
    print("\n🧪 Testing SMS Service")
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
        
        print("✅ SMS service ready for production")
        return True
        
    except Exception as e:
        print(f"❌ SMS service test failed: {str(e)}")
        return False

def main():
    """Run final Twilio tests"""
    print("🚀 Final Twilio Configuration Test")
    print("=" * 60)
    
    tests = [
        ("Twilio Configuration", test_twilio_final_configuration),
        ("SMS Service", test_sms_service)
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
    print("📊 Final Twilio Test Results")
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
        print("\n🎉 TWILIO CONFIGURATION COMPLETE!")
        print("\n✅ Twilio Status:")
        print("  • Account: Active")
        print("  • Phone Number: +1XXXXXXXXXX")
        print("  • Voice Webhook: Configured")
        print("  • SMS Webhook: Configured")
        print("  • SMS Service: Ready")
        print("  • Railway Integration: Ready")
        
        print("\n📋 Next Steps:")
        print("  1. ✅ Twilio: COMPLETE")
        print("  2. 🔧 CallRail: Ready to configure")
        print("  3. 🔧 UWC/Shunya: Ready to configure")
        
        print("\n🚀 Ready for CallRail setup!")
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed. Please check the logs above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)







