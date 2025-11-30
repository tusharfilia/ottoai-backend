# ngrok Setup for Local CallRail Webhook Testing

## Quick Start

### Step 1: Start ngrok in a separate terminal

```bash
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard
./start-ngrok.sh
```

Or manually:
```bash
ngrok http 8000
```

### Step 2: Copy the ngrok URL

ngrok will display something like:
```
Forwarding   https://abc123-def456.ngrok-free.app -> http://localhost:8000
```

Copy the `https://abc123-def456.ngrok-free.app` URL.

### Step 3: Update CallRail Webhook

1. Go to CallRail Dashboard: https://app.callrail.com/
2. Navigate to: **Settings → Integrations → Webhooks**
3. Find the "Call Completed" webhook
4. Update the URL to: `https://<your-ngrok-url>/callrail/call.completed`
   - Example: `https://abc123-def456.ngrok-free.app/callrail/call.completed`
5. Save the webhook

### Step 4: Test the Flow

1. **Make sure your local backend is running:**
   ```bash
   cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard
   # Backend should already be running on port 8000
   ```

2. **Call your CallRail number:** `+1 (202) 831-3219`
3. **Don't answer** (let it go to missed)
4. **Check your local backend logs** - you should see:
   ```
   INFO: CallRail call.completed webhook: {...}
   ```

5. **Check the database:**
   ```bash
   sqlite3 otto_dev.db "SELECT call_id, phone_number, missed_call, created_at FROM calls ORDER BY created_at DESC LIMIT 1;"
   ```

6. **Check the frontend:**
   - Open `http://localhost:3000`
   - Navigate to "Missed Leads" section
   - The missed call should appear

## Troubleshooting

### ngrok URL not working?

1. **Check ngrok is running:**
   ```bash
   curl http://localhost:4040/api/tunnels
   ```

2. **Check backend is running:**
   ```bash
   curl http://localhost:8000/health
   ```

3. **Test webhook manually:**
   ```bash
   curl -X POST "https://<your-ngrok-url>/callrail/call.completed" \
     -H "Content-Type: application/json" \
     -d '{
       "resource_id": "CAL_TEST",
       "customer_phone_number": "+15551234567",
       "tracking_phone_number": "+12028313219",
       "answered": false,
       "created_at": "2025-11-24T06:00:00Z"
     }'
   ```

### CallRail webhook not reaching ngrok?

1. **Verify webhook URL in CallRail dashboard** - must match ngrok URL exactly
2. **Check ngrok web interface:** Open `http://localhost:4040` in browser to see incoming requests
3. **Check CallRail webhook logs** in CallRail dashboard

### After testing, restore production webhook

When done testing, **restore the production webhook URL** in CallRail:
```
https://ottoai-backend-production.up.railway.app/callrail/call.completed
```

## Alternative: Test with Production Backend

If you prefer not to use ngrok, you can:
1. Check Railway production logs to see if the webhook was received
2. Query the production database to see if the call was created
3. Test the frontend against production backend (update `NEXT_PUBLIC_API_URL`)

