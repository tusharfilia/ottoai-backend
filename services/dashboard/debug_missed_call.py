#!/usr/bin/env python3
"""
Debug script for missed call flow
"""
import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

def debug_missed_call_setup():
    """Debug the missed call setup"""
    print("🔍 Debugging Missed Call Flow")
    print("=" * 60)
    
    # Check environment variables
    print("\n1️⃣  Checking Environment Variables:")
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_from = os.getenv("TWILIO_FROM_NUMBER")
    
    if twilio_sid:
        print(f"   ✅ TWILIO_ACCOUNT_SID: {twilio_sid[:10]}...")
    else:
        print("   ❌ TWILIO_ACCOUNT_SID: NOT SET")
    
    if twilio_token:
        print(f"   ✅ TWILIO_AUTH_TOKEN: {twilio_token[:10]}...")
    else:
        print("   ❌ TWILIO_AUTH_TOKEN: NOT SET")
    
    if twilio_from:
        print(f"   ✅ TWILIO_FROM_NUMBER: {twilio_from}")
    else:
        print("   ❌ TWILIO_FROM_NUMBER: NOT SET")
    
    # Check database
    print("\n2️⃣  Checking Database:")
    try:
        from app.database import SessionLocal
        from app.models import company, call
        
        db = SessionLocal()
        
        # Check companies
        companies = db.query(company.Company).all()
        print(f"   Found {len(companies)} companies:")
        for c in companies:
            print(f"      - ID: {c.id}, Name: {c.name}, Phone: {c.phone_number}")
        
        # Check recent calls
        recent_calls = db.query(call.Call).order_by(call.Call.created_at.desc()).limit(5).all()
        print(f"\n   Recent {len(recent_calls)} calls:")
        for c in recent_calls:
            print(f"      - Call ID: {c.call_id}, Phone: {c.phone_number}, Missed: {c.missed_call}, Status: {c.status}")
        
        db.close()
        print("   ✅ Database connection working")
    except Exception as e:
        print(f"   ❌ Database error: {str(e)}")
    
    # Check Twilio service
    print("\n3️⃣  Testing Twilio Service:")
    try:
        from app.services.twilio_service import TwilioService
        twilio_service = TwilioService()
        print("   ✅ TwilioService initialized")
        
        # Try to get account info
        if twilio_sid and twilio_token:
            from twilio.rest import Client
            client = Client(twilio_sid, twilio_token)
            account = client.api.accounts(twilio_sid).fetch()
            print(f"   ✅ Twilio account connected: {account.friendly_name}")
        else:
            print("   ⚠️  Cannot test Twilio connection - credentials missing")
    except Exception as e:
        print(f"   ❌ Twilio service error: {str(e)}")
    
    # Check missed call queue service
    print("\n4️⃣  Testing Missed Call Queue Service:")
    try:
        from app.services.missed_call_queue_service import MissedCallQueueService
        service = MissedCallQueueService()
        print("   ✅ MissedCallQueueService initialized")
    except Exception as e:
        print(f"   ❌ Missed call queue service error: {str(e)}")
    
    # Check webhook endpoints
    print("\n5️⃣  Webhook Endpoints:")
    railway_url = os.getenv("BASE_URL", "https://ottoai-backend-production.up.railway.app")
    print(f"   Expected CallRail Post-Call webhook: {railway_url}/callrail/call.completed")
    print(f"   Alternative endpoint: {railway_url}/call-complete")
    
    print("\n" + "=" * 60)
    print("✅ Debug complete!")
    print("\n💡 Next Steps:")
    print("   1. Ensure company.phone_number matches CallRail tracking number")
    print("   2. Verify CallRail webhook is configured correctly")
    print("   3. Check Railway logs for webhook requests")
    print("   4. Test by calling the CallRail number and missing the call")

if __name__ == "__main__":
    debug_missed_call_setup()












