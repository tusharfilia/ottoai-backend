#!/usr/bin/env python3
"""
Configure Twilio and CallRail for OttoAI
"""
import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.obs.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

def configure_twilio():
    """Configure Twilio credentials and webhooks"""
    print("🔧 Twilio Configuration")
    print("=" * 40)
    
    # Check current Twilio configuration
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_from = os.getenv("TWILIO_FROM_NUMBER", "")
    twilio_callback = os.getenv("TWILIO_CALLBACK_NUMBER", "")
    
    print(f"Current Twilio Account SID: {twilio_sid[:8]}..." if twilio_sid else "Not configured")
    print(f"Current Twilio Auth Token: {'*' * 20}" if twilio_token else "Not configured")
    print(f"Current From Number: {twilio_from}" if twilio_from else "Not configured")
    print(f"Current Callback Number: {twilio_callback}" if twilio_callback else "Not configured")
    
    if not all([twilio_sid, twilio_token, twilio_from]):
        print("\n❌ Twilio not fully configured")
        print("\nTo configure Twilio:")
        print("1. Sign up at https://www.twilio.com/")
        print("2. Get your Account SID and Auth Token from the console")
        print("3. Purchase a phone number for SMS")
        print("4. Set environment variables:")
        print("   export TWILIO_ACCOUNT_SID='your_account_sid'")
        print("   export TWILIO_AUTH_TOKEN='your_auth_token'")
        print("   export TWILIO_FROM_NUMBER='+1234567890'")
        print("   export TWILIO_CALLBACK_NUMBER='+1234567890'")
        return False
    else:
        print("\n✅ Twilio configuration looks good")
        return True

def configure_callrail():
    """Configure CallRail credentials and webhooks"""
    print("\n🔧 CallRail Configuration")
    print("=" * 40)
    
    # Check current CallRail configuration
    callrail_key = os.getenv("CALLRAIL_API_KEY", "")
    callrail_account = os.getenv("CALLRAIL_ACCOUNT_ID", "")
    
    print(f"Current CallRail API Key: {callrail_key[:8]}..." if callrail_key else "Not configured")
    print(f"Current CallRail Account ID: {callrail_account}" if callrail_account else "Not configured")
    
    if not all([callrail_key, callrail_account]):
        print("\n❌ CallRail not fully configured")
        print("\nTo configure CallRail:")
        print("1. Sign up at https://www.callrail.com/")
        print("2. Get your API Key from Settings > API")
        print("3. Get your Account ID from the dashboard")
        print("4. Set environment variables:")
        print("   export CALLRAIL_API_KEY='your_api_key'")
        print("   export CALLRAIL_ACCOUNT_ID='your_account_id'")
        return False
    else:
        print("\n✅ CallRail configuration looks good")
        return True

def test_twilio_connection():
    """Test Twilio connection"""
    print("\n🧪 Testing Twilio Connection")
    print("=" * 40)
    
    try:
        from app.services.twilio_service import TwilioService
        
        twilio_service = TwilioService()
        
        # Test connection by getting account info
        client = twilio_service._get_client()
        account = client.api.accounts(twilio_service.account_sid).fetch()
        
        print(f"✅ Twilio connection successful")
        print(f"   Account SID: {account.sid}")
        print(f"   Account Name: {account.friendly_name}")
        print(f"   Account Status: {account.status}")
        
        return True
        
    except Exception as e:
        print(f"❌ Twilio connection failed: {str(e)}")
        return False

def test_callrail_connection():
    """Test CallRail connection"""
    print("\n🧪 Testing CallRail Connection")
    print("=" * 40)
    
    try:
        import requests
        
        api_key = os.getenv("CALLRAIL_API_KEY", "")
        account_id = os.getenv("CALLRAIL_ACCOUNT_ID", "")
        
        if not api_key or not account_id:
            print("❌ CallRail credentials not configured")
            return False
        
        # Test API connection
        headers = {
            "Authorization": f"Token token={api_key}"
        }
        
        url = f"https://api.callrail.com/v3/accounts/{account_id}.json"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ CallRail connection successful")
            print(f"   Account ID: {data.get('id')}")
            print(f"   Account Name: {data.get('name')}")
            print(f"   Account Status: {data.get('status')}")
            return True
        else:
            print(f"❌ CallRail connection failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ CallRail connection failed: {str(e)}")
        return False

def show_webhook_endpoints():
    """Show webhook endpoints that need to be configured"""
    print("\n🔗 Webhook Endpoints Configuration")
    print("=" * 40)
    
    base_url = os.getenv("BASE_URL", "https://your-domain.com")
    
    print("Twilio Webhooks:")
    print(f"  SMS Status Callback: {base_url}/sms/twilio-webhook")
    print(f"  Voice Status Callback: {base_url}/voice/twilio-webhook")
    
    print("\nCallRail Webhooks:")
    print(f"  Call Events: {base_url}/callrail/call.incoming")
    print(f"  Call Events: {base_url}/callrail/call.answered")
    print(f"  Call Events: {base_url}/callrail/call.missed")
    print(f"  Call Events: {base_url}/callrail/call.completed")
    print(f"  SMS Events: {base_url}/sms/callrail-webhook")
    
    print("\nTo configure webhooks:")
    print("1. Update BASE_URL environment variable to your production domain")
    print("2. Configure webhooks in Twilio Console:")
    print("   - Go to Phone Numbers > Manage > Active Numbers")
    print("   - Click on your phone number")
    print("   - Set SMS webhook URL to the SMS Status Callback URL above")
    print("3. Configure webhooks in CallRail:")
    print("   - Go to Settings > Webhooks")
    print("   - Add webhook URLs for each event type")

def create_environment_template():
    """Create environment template file"""
    print("\n📝 Creating Environment Template")
    print("=" * 40)
    
    env_template = """# OttoAI Environment Configuration
# Copy this file to .env and fill in your values

# Database
DATABASE_URL=sqlite:///./otto_dev.db

# Redis
REDIS_URL=redis://localhost:6379

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_FROM_NUMBER=+1234567890
TWILIO_CALLBACK_NUMBER=+1234567890

# CallRail Configuration
CALLRAIL_API_KEY=your_callrail_api_key
CALLRAIL_ACCOUNT_ID=your_callrail_account_id

# UWC/Shunya Configuration
UWC_BASE_URL=https://otto.shunyalabs.ai
UWC_API_KEY=your_uwc_api_key
UWC_HMAC_SECRET=your_uwc_hmac_secret

# Clerk Authentication
CLERK_SECRET_KEY=your_clerk_secret_key
CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key

# AWS S3 (for file storage)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
S3_BUCKET=otto-documents-staging

# Application
BASE_URL=https://your-domain.com
ENVIRONMENT=development
LOG_LEVEL=INFO
"""
    
    template_path = Path(__file__).parent / "env.template"
    with open(template_path, "w") as f:
        f.write(env_template)
    
    print(f"✅ Environment template created: {template_path}")
    print("Copy this file to .env and fill in your values")

def main():
    """Main configuration function"""
    print("🚀 OttoAI External Services Configuration")
    print("=" * 50)
    
    # Configure services
    twilio_configured = configure_twilio()
    callrail_configured = configure_callrail()
    
    # Test connections
    twilio_working = False
    callrail_working = False
    
    if twilio_configured:
        twilio_working = test_twilio_connection()
    
    if callrail_configured:
        callrail_working = test_callrail_connection()
    
    # Show webhook endpoints
    show_webhook_endpoints()
    
    # Create environment template
    create_environment_template()
    
    # Summary
    print("\n📊 Configuration Summary")
    print("=" * 40)
    print(f"Twilio: {'✅ Configured & Working' if twilio_working else '❌ Not configured or not working'}")
    print(f"CallRail: {'✅ Configured & Working' if callrail_working else '❌ Not configured or not working'}")
    
    if twilio_working and callrail_working:
        print("\n🎉 All external services are configured and working!")
        return True
    else:
        print("\n⚠️  Some services need configuration")
        print("Please configure the missing services and run this script again")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)















