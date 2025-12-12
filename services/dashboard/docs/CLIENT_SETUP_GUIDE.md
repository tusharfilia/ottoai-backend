# Client Setup Guide: CallRail & Twilio Configuration

## Overview

This guide explains how **clients** (companies using Otto) configure CallRail and Twilio for real call tracking and analysis.

## Backend URL

**Production Backend:**
```
https://ottoai-backend-production.up.railway.app
```

All webhook URLs should point to this domain.

---

## Option 1: Via Onboarding API (Recommended)

If you're using Otto's onboarding flow, use these endpoints:

### CallRail Setup

**Endpoint:** `POST /api/v1/onboarding/callrail/connect`

**Request:**
```json
{
  "api_key": "your-callrail-api-key",
  "account_id": "your-callrail-account-id",
  "primary_tracking_number": "+15551234567"
}
```

**What it does:**
- Stores CallRail credentials in your company record
- Sets `call_provider = "callrail"`
- Returns webhook URL you need to configure in CallRail

**Response:**
```json
{
  "success": true,
  "provider": "callrail",
  "webhook_url": "https://ottoai-backend-production.up.railway.app/api/v1/callrail/call.completed",
  "onboarding_step": "document_ingestion"
}
```

### Twilio Setup

**Endpoint:** `POST /api/v1/onboarding/twilio/connect`

**Request:**
```json
{
  "account_sid": "your-twilio-account-sid",
  "auth_token": "your-twilio-auth-token",
  "primary_tracking_number": "+15551234567"
}
```

**What it does:**
- Stores Twilio credentials in your company record
- Sets `call_provider = "twilio"`
- Returns webhook URL you need to configure in Twilio

---

## Option 2: Manual Configuration (Via Company API)

If you need to configure manually or update existing settings:

### Set CallRail API Key

**Endpoint:** `POST /company/set-callrail-api-key/{company_id}`

**Query Parameters:**
- `api_key`: Your CallRail API key

**Example:**
```bash
curl -X POST \
  "https://ottoai-backend-production.up.railway.app/company/set-callrail-api-key/org_123" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d "api_key=your-callrail-api-key"
```

### Set CallRail Account ID

**Endpoint:** `POST /company/set-callrail-account-id/{company_id}`

**Query Parameters:**
- `account_id`: Your CallRail account ID

### Update Company Phone Number

**Endpoint:** `PUT /company/{company_id}`

**Query Parameters:**
- `phone_number`: Your CallRail tracking number (must match exactly)

**Important:** The `phone_number` field in your company record **must match** your CallRail tracking number. The system uses this to identify which company a call belongs to.

---

## Step-by-Step: Complete Setup

### Step 1: Get Your CallRail Credentials

1. **Log into CallRail Dashboard**
   - Go to https://app.callrail.com/

2. **Get API Key**
   - Go to **Settings** → **Integrations** → **API**
   - Click **Generate New Token** (or copy existing)
   - This is your `api_key`

3. **Get Account ID**
   - Go to **Settings** → **Account**
   - Copy your **Account ID**
   - This is your `account_id`

4. **Get Tracking Number**
   - Go to **Numbers** → **Tracking Numbers**
   - Copy the phone number you want to use (e.g., `+1 520-523-2772`)
   - **Format it consistently**: `+15205232772` or `15205232772`

### Step 2: Configure Company in Otto

**Option A: Via Onboarding API**
```bash
curl -X POST \
  "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/callrail/connect" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "your-callrail-api-key",
    "account_id": "your-callrail-account-id",
    "primary_tracking_number": "+15205232772"
  }'
```

**Option B: Manual Configuration**
```bash
# 1. Set API key
curl -X POST \
  "https://ottoai-backend-production.up.railway.app/company/set-callrail-api-key/YOUR_COMPANY_ID?api_key=your-key" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 2. Set account ID
curl -X POST \
  "https://ottoai-backend-production.up.railway.app/company/set-callrail-account-id/YOUR_COMPANY_ID?account_id=your-account-id" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 3. Update phone number (CRITICAL - must match tracking number)
curl -X PUT \
  "https://ottoai-backend-production.up.railway.app/company/YOUR_COMPANY_ID?phone_number=+15205232772" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Step 3: Configure CallRail Webhooks

1. **Go to CallRail Dashboard**
   - Settings → Integrations → Webhooks

2. **Add Webhook URLs:**
   ```
   https://ottoai-backend-production.up.railway.app/api/v1/callrail/call.incoming
   https://ottoai-backend-production.up.railway.app/api/v1/callrail/call.answered
   https://ottoai-backend-production.up.railway.app/api/v1/callrail/call.completed
   https://ottoai-backend-production.up.railway.app/api/v1/callrail/call.missed
   ```

3. **Enable Events:**
   - ✅ `call.incoming` - Call starts ringing
   - ✅ `call.answered` - Call is answered
   - ✅ `call.completed` - Call ends (with recording URL)
   - ✅ `call.missed` - Call was missed

### Step 4: Configure Shunya Webhook (If Not Already Done)

Shunya needs to send analysis results back to Otto:

1. **In Shunya Dashboard:**
   - Add webhook URL: `https://ottoai-backend-production.up.railway.app/api/v1/shunya/webhook`
   - Configure HMAC secret (must match backend config)
   - Enable events: `job.completed`, `job.failed`

### Step 5: Verify Configuration

**Check Company Record:**
```bash
curl -X GET \
  "https://ottoai-backend-production.up.railway.app/company/YOUR_COMPANY_ID" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Verify fields are set:**
- ✅ `callrail_api_key` - Not null
- ✅ `callrail_account_id` - Not null
- ✅ `phone_number` - Matches your CallRail tracking number exactly

**Test with Real Call:**
1. Call your CallRail tracking number
2. Have a conversation
3. End the call
4. Check Railway logs:
   ```bash
   railway logs --filter "callrail"
   ```
5. Check database:
   ```sql
   SELECT * FROM calls ORDER BY created_at DESC LIMIT 1;
   SELECT * FROM call_analyses ORDER BY created_at DESC LIMIT 1;
   ```

---

## Twilio Setup (If Using Twilio Instead)

### Step 1: Get Twilio Credentials

1. **Log into Twilio Console**
   - Go to https://console.twilio.com/

2. **Get Account SID and Auth Token**
   - Dashboard → Copy **Account SID** and **Auth Token**

3. **Get Phone Number**
   - Phone Numbers → Manage → Active Numbers
   - Copy your Twilio number

### Step 2: Configure in Otto

**Via Onboarding API:**
```bash
curl -X POST \
  "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/twilio/connect" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "account_sid": "your-twilio-account-sid",
    "auth_token": "your-twilio-auth-token",
    "primary_tracking_number": "+15551234567"
  }'
```

### Step 3: Configure Twilio Webhooks

1. **Go to Twilio Console**
   - Phone Numbers → Manage → Active Numbers
   - Click on your number

2. **Set Webhook URLs:**
   - **SMS Webhook:** `https://ottoai-backend-production.up.railway.app/api/v1/twilio-webhook`
   - **Voice Webhook:** `https://ottoai-backend-production.up.railway.app/api/v1/twilio-webhook`

---

## Critical Configuration Points

### 1. Phone Number Matching

**The `phone_number` field in your company record MUST match your CallRail tracking number exactly.**

The system uses `find_company_by_tracking_number()` to identify which company a call belongs to. It tries multiple formats:
- Exact match: `+15205232772`
- Without `+`: `15205232772`
- Normalized comparison (removes dashes, spaces)

**Best Practice:** Store it in one format consistently (e.g., `+15205232772`).

### 2. Company ID = Clerk Org ID

Your `company_id` is the same as your Clerk organization ID (starts with `org_`).

When configuring, use your Clerk org ID as the company ID.

### 3. Webhook URLs Must Be Public

All webhook URLs must be:
- ✅ Publicly accessible (no VPN/firewall blocking)
- ✅ HTTPS (not HTTP)
- ✅ Returning 200 status codes

### 4. Shunya Integration

Shunya webhook must be configured separately:
- Webhook URL: `https://ottoai-backend-production.up.railway.app/api/v1/shunya/webhook`
- HMAC secret must match backend configuration
- This is typically configured by Otto team, not clients

---

## Troubleshooting

### "No company found for tracking number"

**Problem:** CallRail webhook received but company not found.

**Solution:**
1. Check `phone_number` in company record matches tracking number exactly
2. Try different formats: `+15205232772`, `15205232772`, `520-523-2772`
3. Check database:
   ```sql
   SELECT id, name, phone_number FROM companies WHERE id = 'YOUR_COMPANY_ID';
   ```

### "Webhook not receiving calls"

**Problem:** Calls happening but webhooks not firing.

**Solution:**
1. Verify webhook URLs in CallRail dashboard
2. Check Railway logs: `railway logs --filter "callrail"`
3. Test webhook manually:
   ```bash
   curl -X POST https://ottoai-backend-production.up.railway.app/api/v1/callrail/call.completed \
     -H "Content-Type: application/json" \
     -d '{"call_id": "test", "caller_number": "+15551234567", "tracking_number": "YOUR_TRACKING_NUMBER"}'
   ```

### "Shunya analysis not completing"

**Problem:** Calls created but no analysis.

**Solution:**
1. Check Shunya webhook is configured
2. Check Shunya jobs table:
   ```sql
   SELECT * FROM shunya_jobs ORDER BY created_at DESC LIMIT 10;
   ```
3. Check Railway logs: `railway logs --filter "shunya"`

---

## Quick Checklist

- [ ] CallRail account created
- [ ] CallRail API key obtained
- [ ] CallRail account ID obtained
- [ ] Tracking number identified
- [ ] Company `phone_number` set to match tracking number
- [ ] CallRail API key stored in company record
- [ ] CallRail account ID stored in company record
- [ ] CallRail webhooks configured (4 endpoints)
- [ ] Shunya webhook configured (if not done by Otto team)
- [ ] Test call made and verified in database
- [ ] Shunya analysis completing successfully

---

## Next Steps

Once configured:
1. **Make a test call** to your tracking number
2. **Verify call appears** in database
3. **Check Shunya analysis** completes
4. **Monitor logs** for any errors
5. **Start using frontend** - data will populate automatically

---

## Support

If you encounter issues:
1. Check Railway logs: `railway logs --tail`
2. Verify company configuration: `GET /company/{company_id}`
3. Test webhook manually (see troubleshooting above)
4. Contact Otto support with:
   - Company ID
   - Tracking number
   - Error messages from logs
   - Timestamp of test call

