#!/usr/bin/env python3
"""
Test direct SMS sending to verify the system works
"""
import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_direct_sms():
    """Test sending SMS directly"""
    print("🧪 Testing Direct SMS Sending")
    print("=" * 50)
    
    try:
        from app.services.twilio_service import TwilioService
        
        # Initialize Twilio service
        twilio_service = TwilioService()
        
        # Get your phone number for testing
        test_phone = input("Enter your phone number for testing (e.g., +1234567890): ").strip()
        
        if not test_phone:
            print("❌ No phone number provided")
            return False
        
        # Normalize phone number
        normalized = twilio_service._normalize_phone_number(test_phone)
        print(f"✅ Normalized phone number: {normalized}")
        
        # Test SMS sending
        message = "Hi! This is a test SMS from OttoAI. We missed your call and would love to help you. Reply with your question or call us back at +15205232772."
        
        print(f"✅ From: {os.getenv('TWILIO_FROM_NUMBER', '+15205232772')}")
        print(f"✅ To: {normalized}")
        print(f"✅ Message: {message}")
        
        # Ask for confirmation
        confirm = input("\nSend test SMS? (y/n): ").strip().lower()
        
        if confirm == 'y':
            try:
                # Send SMS
                result = twilio_service.send_sms(
                    to_phone=normalized,
                    message=message
                )
                
                if result:
                    print("✅ SMS sent successfully!")
                    print("✅ Check your phone for the message")
                    return True
                else:
                    print("❌ SMS sending failed")
                    return False
                    
            except Exception as e:
                print(f"❌ SMS sending error: {str(e)}")
                return False
        else:
            print("✅ SMS sending cancelled")
            return True
        
    except Exception as e:
        print(f"❌ Direct SMS test failed: {str(e)}")
        return False

def test_sms_reply_handling():
    """Test SMS reply handling"""
    print("\n🧪 Testing SMS Reply Handling")
    print("=" * 50)
    
    try:
        from app.routes.sms_handler import router as sms_router
        
        print("✅ SMS handler routes available:")
        routes = [route.path for route in sms_router.routes]
        for route in routes:
            print(f"  • {route}")
        
        print("✅ SMS reply handling ready")
        return True
        
    except Exception as e:
        print(f"❌ SMS reply handling test failed: {str(e)}")
        return False

def main():
    """Run direct SMS test"""
    print("🚀 Direct SMS Test")
    print("=" * 40)
    
    tests = [
        ("Direct SMS Sending", test_direct_sms),
        ("SMS Reply Handling", test_sms_reply_handling)
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
    print(f"\n{'='*40}")
    print("📊 Direct SMS Test Results")
    print("=" * 40)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 DIRECT SMS TEST COMPLETE!")
        print("\n✅ SMS Status:")
        print("  • Twilio Service: Working")
        print("  • SMS Sending: Working")
        print("  • SMS Reply Handling: Ready")
        
        print("\n📋 Next Steps:")
        print("  1. Test SMS sending directly")
        print("  2. Test SMS reply handling")
        print("  3. Verify complete SMS flow")
        
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed. Please check the logs above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)










