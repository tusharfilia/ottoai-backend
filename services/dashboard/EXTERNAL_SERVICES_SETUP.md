# External Services Setup Guide

This guide walks you through setting up Twilio and CallRail for the OttoAI missed call recovery system.

## 🔧 Prerequisites

1. **Twilio Account**: Sign up at https://www.twilio.com/
2. **CallRail Account**: Sign up at https://www.callrail.com/
3. **Domain**: You'll need a public domain for webhook endpoints

## 📞 Twilio Setup

### 1. Create Twilio Account
- Go to https://www.twilio.com/
- Sign up for a free account
- Verify your phone number

### 2. Get Credentials
- Go to Console Dashboard
- Copy your **Account SID** and **Auth Token**
- These are your `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN`

### 3. Purchase Phone Number
- Go to Phone Numbers > Buy a number
- Choose a number that supports SMS
- This will be your `TWILIO_FROM_NUMBER`

### 4. Configure Webhooks
- Go to Phone Numbers > Manage > Active Numbers
- Click on your purchased number
- Set **SMS webhook URL** to: `https://your-domain.com/sms/twilio-webhook`
- Set **Voice webhook URL** to: `https://your-domain.com/voice/twilio-webhook`

## 📊 CallRail Setup

### 1. Create CallRail Account
- Go to https://www.callrail.com/
- Sign up for a free account
- Complete the setup wizard

### 2. Get API Credentials
- Go to Settings > API
- Copy your **API Key** (this is your `CALLRAIL_API_KEY`)
- Go to Settings > Account
- Copy your **Account ID** (this is your `CALLRAIL_ACCOUNT_ID`)

### 3. Configure Webhooks
- Go to Settings > Webhooks
- Add the following webhook URLs:
  - **Call Events**: `https://your-domain.com/callrail/call.incoming`
  - **Call Events**: `https://your-domain.com/callrail/call.answered`
  - **Call Events**: `https://your-domain.com/callrail/call.missed`
  - **Call Events**: `https://your-domain.com/callrail/call.completed`
  - **SMS Events**: `https://your-domain.com/sms/callrail-webhook`

## 🔐 Environment Configuration

Create a `.env` file in the project root:

```bash
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
```

## 🧪 Testing Configuration

Run the configuration test:

```bash
python3 configure_external_services.py
```

This will:
- Check if credentials are configured
- Test Twilio connection
- Test CallRail connection
- Show webhook endpoints
- Create environment template

## 🚀 Production Deployment

### 1. Update Environment Variables
Set the following environment variables in your production environment:

```bash
export TWILIO_ACCOUNT_SID="your_production_sid"
export TWILIO_AUTH_TOKEN="your_production_token"
export TWILIO_FROM_NUMBER="+1234567890"
export CALLRAIL_API_KEY="your_production_key"
export CALLRAIL_ACCOUNT_ID="your_production_account"
export BASE_URL="https://your-production-domain.com"
```

### 2. Update Webhook URLs
Update the webhook URLs in both Twilio and CallRail to point to your production domain.

### 3. Test End-to-End Flow
1. Make a test call to your CallRail tracking number
2. Let it go to voicemail (missed call)
3. Check that SMS is sent via Twilio
4. Verify webhook data is received by your backend

## 🔍 Troubleshooting

### Twilio Issues
- **SMS not sending**: Check phone number format (+1234567890)
- **Webhook not receiving**: Verify URL is accessible and returns 200
- **Authentication failed**: Verify Account SID and Auth Token

### CallRail Issues
- **Webhooks not firing**: Check webhook URLs are correct
- **API errors**: Verify API key and Account ID
- **No call data**: Ensure tracking number is properly configured

### General Issues
- **Database errors**: Run migrations: `python3 run_migration.py --all`
- **Redis errors**: Check Redis connection: `python3 test_redis_connection.py`
- **Environment variables**: Use `python3 configure_external_services.py` to check

## 📋 Checklist

- [ ] Twilio account created and verified
- [ ] Twilio phone number purchased
- [ ] Twilio webhooks configured
- [ ] CallRail account created
- [ ] CallRail API credentials obtained
- [ ] CallRail webhooks configured
- [ ] Environment variables set
- [ ] Database migrations run
- [ ] Redis connection working
- [ ] End-to-end test completed

## 🆘 Support

If you encounter issues:

1. Check the logs: `tail -f logs/app.log`
2. Run configuration test: `python3 configure_external_services.py`
3. Test individual services:
   - Twilio: `python3 test_twilio_integration.py`
   - CallRail: `python3 test_callrail_integration.py`
   - Redis: `python3 test_redis_connection.py`

## 🔄 Next Steps

Once external services are configured:

1. **Test the complete flow**: Missed call → SMS → Customer response
2. **Configure UWC/Shunya**: Set up AI services for dynamic responses
3. **Monitor performance**: Use the built-in metrics and monitoring
4. **Scale up**: Configure for production load and reliability










