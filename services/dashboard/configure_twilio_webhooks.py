#!/usr/bin/env python3
"""
Configure Twilio webhooks for OttoAI
"""
import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

def configure_twilio_webhooks():
    """Configure Twilio webhooks"""
    print("🔧 Configuring Twilio Webhooks")
    print("=" * 50)
    
    try:
        from twilio.rest import Client
        
        # Get credentials
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_number = os.getenv("TWILIO_FROM_NUMBER", "+15205232772")
        
        if not account_sid or not auth_token:
            print("❌ Twilio credentials not found")
            return False
        
        # Railway app URL
        railway_url = "https://ottoai-backend-production.up.railway.app"
        
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
        
        print(f"✅ Found phone number: {target_number.phone_number}")
        print(f"✅ Current Voice URL: {target_number.voice_url}")
        print(f"✅ Current SMS URL: {target_number.sms_url}")
        
        # Configure webhooks
        voice_webhook = f"{railway_url}/mobile/twilio-voice-webhook"
        sms_webhook = f"{railway_url}/mobile/twilio-sms-webhook"
        
        print(f"\n🔧 Setting Voice Webhook: {voice_webhook}")
        print(f"🔧 Setting SMS Webhook: {sms_webhook}")
        
        # Update the phone number configuration
        updated_number = client.incoming_phone_numbers(target_number.sid).update(
            voice_url=voice_webhook,
            voice_method='POST',
            sms_url=sms_webhook,
            sms_method='POST'
        )
        
        print(f"\n✅ Voice Webhook Updated: {updated_number.voice_url}")
        print(f"✅ SMS Webhook Updated: {updated_number.sms_url}")
        print(f"✅ Voice Method: {updated_number.voice_method}")
        print(f"✅ SMS Method: {updated_number.sms_method}")
        
        return True
        
    except Exception as e:
        print(f"❌ Webhook configuration failed: {str(e)}")
        return False

def test_webhook_endpoints():
    """Test that webhook endpoints are accessible"""
    print("\n🧪 Testing Webhook Endpoints")
    print("=" * 50)
    
    import requests
    
    railway_url = "https://ottoai-backend-production.up.railway.app"
    
    endpoints = [
        f"{railway_url}/health",
        f"{railway_url}/mobile/twilio-voice-webhook",
        f"{railway_url}/mobile/twilio-sms-webhook"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, timeout=10)
            if response.status_code == 200:
                print(f"✅ {endpoint} - OK")
            else:
                print(f"⚠️  {endpoint} - Status: {response.status_code}")
        except Exception as e:
            print(f"❌ {endpoint} - Error: {str(e)}")
    
    return True

def main():
    """Configure Twilio webhooks"""
    print("🚀 Twilio Webhook Configuration")
    print("=" * 60)
    
    # Configure webhooks
    webhook_success = configure_twilio_webhooks()
    
    if webhook_success:
        print("\n🎉 Twilio webhooks configured successfully!")
        print("\n✅ Configuration Summary:")
        print(f"  • Phone Number: {os.getenv('TWILIO_FROM_NUMBER', '+15205232772')}")
        print(f"  • Voice Webhook: https://ottoai-backend-production.up.railway.app/mobile/twilio-voice-webhook")
        print(f"  • SMS Webhook: https://ottoai-backend-production.up.railway.app/mobile/twilio-sms-webhook")
        print(f"  • Method: POST")
        
        print("\n📋 Next Steps:")
        print("  1. Test SMS sending")
        print("  2. Test webhook receiving")
        print("  3. Configure CallRail")
        
        # Test endpoints
        test_webhook_endpoints()
        
        return True
    else:
        print("\n❌ Webhook configuration failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)













