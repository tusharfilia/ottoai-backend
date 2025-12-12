# Testing CallRail Missed Call Flow

## 🎯 Quick Test Guide

### Step 1: Find Your CallRail Tracking Number

**Option A: Check Your Database**
```sql
-- Connect to your database and run:
SELECT id, name, phone_number, callrail_account_id 
FROM companies 
WHERE phone_number IS NOT NULL;
```

**Option B: Check CallRail Dashboard**
1. Log into CallRail dashboard
2. Go to **Numbers** → **Tracking Numbers**
3. Note the number you want to test (e.g., `+1 520-523-2772`)

### Step 2: Ensure Company Record Exists

**The company's `phone_number` field MUST match the CallRail tracking number exactly.**

Format examples:
- `+15205232772` (no dashes, with country code)
- `15205232772` (no dashes, no plus)
- `520-523-2772` (with dashes)

**Check/Update Company:**
```sql
-- Find company
SELECT * FROM companies WHERE id = 'your_company_id';

-- Update phone_number to match CallRail tracking number
UPDATE companies 
SET phone_number = '+15205232772'  -- Replace with your CallRail number
WHERE id = 'your_company_id';
```

### Step 3: Ensure CallRail Webhook is Configured

**Webhook URL in CallRail Dashboard:**
```
POST https://ottoai-backend-production.up.railway.app/callrail/call.missed
```

**Required Webhook Events in CallRail:**
- ✅ `call.missed` - **REQUIRED** for missed call flow
- ✅ `call.incoming` - Creates call record
- ✅ `call.completed` - Updates call with transcript

### Step 4: Test the Flow

**Method 1: Real Call Test (Recommended)**

1. **Call your CallRail tracking number** from your phone
2. **Let it ring** - Don't answer!
3. **Hang up** after a few rings OR let it go to voicemail
4. **Wait 30-60 seconds** for webhook processing
5. **Check your phone** for SMS from your Twilio number

**Method 2: Simulate Webhook (Quick Test)**

```bash
# Set your Railway URL
RAILWAY_URL="https://ottoai-backend-production.up.railway.app"

# Replace these with your actual values:
TRACKING_NUMBER="+15205232772"  # Your CallRail number
CALLER_NUMBER="+1YOUR_PHONE"    # Your phone number
CALLRAIL_CALL_ID="test_$(date +%s)"

# Simulate call.missed webhook
curl -X POST "${RAILWAY_URL}/callrail/call.missed" \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "'${CALLRAIL_CALL_ID}'",
    "caller_number": "'${CALLER_NUMBER}'",
    "tracking_number": "'${TRACKING_NUMBER}'",
    "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'",
    "answered": false
  }'
```

### Step 5: Verify the Flow Worked

**Check Database:**
```sql
-- Check if call was created
SELECT call_id, phone_number, missed_call, status, created_at 
FROM calls 
WHERE phone_number = 'YOUR_CALLER_NUMBER'
ORDER BY created_at DESC 
LIMIT 5;

-- Check if queue entry was created
SELECT id, call_id, customer_phone, status, priority, created_at 
FROM missed_call_queue 
WHERE customer_phone = 'YOUR_CALLER_NUMBER'
ORDER BY created_at DESC 
LIMIT 5;

-- Check if SMS was sent (via Twilio logs or check your phone)
```

**Check Logs (Railway):**
```bash
# View recent logs
railway logs --tail

# Look for:
# - "CallRail call.missed webhook"
# - "Added missed call to queue"
# - "AI rescue SMS sent"
```

**Check Your Phone:**
- You should receive an SMS from your Twilio number
- Message should say: "Hi! We just missed your call to {company_name}..."

---

## 🔧 Troubleshooting

### Issue: No SMS Received

**Check 1: Company Phone Number Match**
```sql
-- Verify company phone_number matches CallRail tracking number
SELECT id, name, phone_number FROM companies;
```
- **Fix**: Update `companies.phone_number` to match CallRail tracking number exactly

**Check 2: Twilio Configuration**
```bash
# Check if Twilio is configured
echo $TWILIO_ACCOUNT_SID
echo $TWILIO_AUTH_TOKEN
echo $TWILIO_FROM_NUMBER
```
- **Fix**: Ensure Twilio credentials are set in Railway environment variables

**Check 3: Webhook URL**
- Go to CallRail Dashboard → Integrations → Webhooks
- Verify webhook URL is: `https://ottoai-backend-production.up.railway.app/callrail/call.missed`
- Verify webhook is enabled for `call.missed` event

**Check 4: CallRail Number Configuration**
- In CallRail, ensure the tracking number is configured to:
  - **Forward to**: Voicemail (not AI, not another number)
  - OR: **Hang Up** option (if available)
- **NOT**: Forward to AI or another service (this prevents missed call detection)

### Issue: Webhook Not Received

**Check Railway Logs:**
```bash
railway logs --tail | grep -i "callrail\|missed"
```

**Test Webhook Endpoint:**
```bash
curl -X POST "https://ottoai-backend-production.up.railway.app/callrail/call.missed" \
  -H "Content-Type: application/json" \
  -d '{"test": "true"}'
```

**Check CallRail Webhook Logs:**
- CallRail Dashboard → Integrations → Webhooks → View Logs
- Look for delivery failures or 404 errors

### Issue: Queue Entry Not Created

**Check Database Connection:**
- Ensure PostgreSQL is accessible
- Check Railway database connection string

**Check Service Status:**
```bash
# Check if queue processor is running
curl https://ottoai-backend-production.up.railway.app/health
```

---

## 📋 Pre-Test Checklist

- [ ] CallRail tracking number identified
- [ ] Company record exists with `phone_number` matching CallRail number
- [ ] CallRail webhook configured: `POST /callrail/call.missed`
- [ ] Twilio credentials configured in Railway
- [ ] Twilio `from_number` matches company phone number
- [ ] CallRail number configured to go to voicemail/hang up (not AI)
- [ ] Queue processor is running (check `/health` endpoint)

---

## 🧪 Quick Test Script

Save this as `test_missed_call.sh`:

```bash
#!/bin/bash

# Configuration
RAILWAY_URL="https://ottoai-backend-production.up.railway.app"
TRACKING_NUMBER="+15205232772"  # Replace with your CallRail number
CALLER_NUMBER="+1YOUR_PHONE"    # Replace with your phone number
CALL_ID="test_$(date +%s)"

echo "🧪 Testing CallRail Missed Call Flow"
echo "====================================="
echo "Tracking Number: $TRACKING_NUMBER"
echo "Caller Number: $CALLER_NUMBER"
echo ""

# Step 1: Simulate call.incoming
echo "1️⃣  Simulating call.incoming..."
curl -X POST "${RAILWAY_URL}/callrail/call.incoming" \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "'${CALL_ID}'",
    "caller_number": "'${CALLER_NUMBER}'",
    "tracking_number": "'${TRACKING_NUMBER}'",
    "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"
  }' | jq .

sleep 2

# Step 2: Simulate call.missed
echo ""
echo "2️⃣  Simulating call.missed..."
curl -X POST "${RAILWAY_URL}/callrail/call.missed" \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "'${CALL_ID}'",
    "caller_number": "'${CALLER_NUMBER}'",
    "tracking_number": "'${TRACKING_NUMBER}'",
    "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'",
    "answered": false
  }' | jq .

echo ""
echo "✅ Test complete! Check your phone for SMS in 30-60 seconds."
echo ""
echo "📋 Next Steps:"
echo "   1. Check your phone for SMS from Twilio"
echo "   2. Reply to the SMS to test response handling"
echo "   3. Check database for queue entry status"
```

---

## 🎯 Expected Flow

1. **Call placed** → CallRail tracking number
2. **Call not answered** → Goes to voicemail/hangs up
3. **CallRail webhook** → `POST /callrail/call.missed` to Railway
4. **Otto creates call record** → `calls` table
5. **Otto adds to queue** → `missed_call_queue` table
6. **Queue processor** → Sends SMS via Twilio
7. **SMS delivered** → Customer receives follow-up message
8. **Customer responds** → Response tracked, queue status updated

---

## 📞 Need Help?

If the flow isn't working:
1. Check Railway logs: `railway logs --tail`
2. Check database for call/queue records
3. Verify CallRail webhook is firing (check CallRail dashboard)
4. Verify Twilio SMS is being sent (check Twilio dashboard)














