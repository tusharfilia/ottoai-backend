# CallRail Recording → Shunya Analysis Flow

## ✅ Yes, We Have It!

The system **automatically** receives CallRail recordings and sends them to Shunya for analysis. Here's how it works:

---

## Complete Flow

### 1. CallRail Sends Webhook with Recording URL

When a call completes, CallRail sends a `call.completed` webhook to:
```
POST https://ottoai-backend-production.up.railway.app/api/v1/callrail/call.completed
```

**Webhook Payload Includes:**
```json
{
  "call_id": "CAL019a4be69ef4764db2d8ac1d6b21ee00",
  "customer_phone_number": "+15551234567",
  "tracking_phone_number": "+15559876543",
  "recording": "https://app.callrail.com/recordings/abc123.mp3",  // ← Recording URL
  "recording_url": "https://app.callrail.com/recordings/abc123.mp3",  // Alternative field name
  "duration": 180,
  "answered": true
}
```

### 2. Backend Extracts Recording URL

**File:** `app/routes/enhanced_callrail.py::handle_call_completed()`

```python
# Extract recording URL from webhook
recording_url = data.get("recording") or data.get("recording_url")

# Find or create call record
call_record = db.query(Call).filter_by(
    phone_number=customer_phone,
    company_id=company_record.id
).order_by(Call.created_at.desc()).first()

# Trigger Shunya processing if recording URL is available
if recording_url and call_record:
    # Submit to Shunya async job system
    job = await shunya_async_job_service.submit_csr_call_job(
        db=db,
        call_id=call_record.call_id,
        audio_url=recording_url,  # ← CallRail recording URL sent to Shunya
        company_id=str(company_record.id),
        request_id=request_id
    )
```

### 3. Shunya Processes Recording

**File:** `app/services/shunya_integration_service.py::process_csr_call()`

The Shunya integration service:
1. **Transcribes audio:**
   ```python
   transcript_result = await uwc_client.transcribe_audio(
       company_id=company_id,
       request_id=request_id,
       audio_url=recording_url,  # CallRail recording URL
       language="en-US"
   )
   ```

2. **Stores transcript:**
   - Saves to `CallTranscript` table
   - Updates `Call.transcript` field

3. **Starts analysis:**
   ```python
   analysis_result = await uwc_client.start_analysis(
       company_id=company_id,
       request_id=request_id,
       call_id=call_id
   )
   ```

4. **Gets complete analysis:**
   - Qualification status (hot/warm/cold)
   - Booking status (booked/not_booked/service_not_offered)
   - Objections
   - SOP compliance
   - Sentiment score
   - Call outcome category

5. **Stores analysis:**
   - Saves to `CallAnalysis` table
   - Updates `Lead` status
   - Creates `Appointment` if booked
   - Creates `Task` from pending actions

### 4. Shunya Sends Results Back

Shunya sends webhook to:
```
POST https://ottoai-backend-production.up.railway.app/api/v1/shunya/webhook
```

Backend processes and stores final analysis results.

---

## Key Code Locations

### Webhook Handler
**File:** `app/routes/enhanced_callrail.py`
- **Function:** `handle_call_completed()`
- **Line:** ~377-408
- **What it does:** Extracts `recording_url` from CallRail webhook and triggers Shunya processing

### Shunya Integration
**File:** `app/services/shunya_integration_service.py`
- **Function:** `process_csr_call()`
- **What it does:** Sends recording URL to Shunya, gets transcript and analysis

### Async Job Service
**File:** `app/services/shunya_async_job_service.py`
- **Function:** `submit_csr_call_job()`
- **What it does:** Creates async job to process call with Shunya (non-blocking)

---

## Requirements for Recording Flow

### 1. CallRail Configuration

**Enable Recording in CallRail:**
1. Go to CallRail Dashboard
2. Settings → Recording
3. Enable **"Record all calls"** or **"Record based on rules"**
4. Ensure recordings are accessible via public URL

**Webhook Must Include Recording:**
- CallRail automatically includes `recording` or `recording_url` in `call.completed` webhook
- Recording URL must be publicly accessible (Shunya needs to download it)

### 2. Webhook Configuration

**Required Webhook:**
```
POST https://ottoai-backend-production.up.railway.app/api/v1/callrail/call.completed
```

**Enable Events:**
- ✅ `call.completed` - **REQUIRED** (includes recording URL)

### 3. Company Configuration

**Company record must have:**
- ✅ `phone_number` matching CallRail tracking number
- ✅ `callrail_api_key` (optional, for API calls)
- ✅ `callrail_account_id` (optional, for identification)

---

## Verification

### Check if Recording URL is Received

**Check Railway Logs:**
```bash
railway logs --filter "callrail" | grep "recording"
```

**Expected Log:**
```
CallRail call.completed webhook: {"recording": "https://...", ...}
CallRail recording URL available: https://app.callrail.com/recordings/abc123.mp3
Submitted CSR call 123 to async Shunya job job-uuid-here
```

### Check if Shunya Processing Started

**Check Database:**
```sql
-- Check Shunya jobs
SELECT * FROM shunya_jobs 
WHERE call_id = YOUR_CALL_ID 
ORDER BY created_at DESC 
LIMIT 1;

-- Check if transcript exists
SELECT * FROM call_transcripts 
WHERE call_id = YOUR_CALL_ID;

-- Check if analysis exists
SELECT * FROM call_analyses 
WHERE call_id = YOUR_CALL_ID;
```

### Check Shunya Logs

**Check Railway Logs:**
```bash
railway logs --filter "shunya" | grep "call_id"
```

**Expected Log:**
```
Transcribing call 123 via Shunya
Starting Shunya analysis for call 123
Shunya analysis completed for call 123
```

---

## Troubleshooting

### Recording URL Not Received

**Problem:** CallRail webhook doesn't include recording URL.

**Solutions:**
1. **Check CallRail Recording Settings:**
   - Ensure recording is enabled for your tracking number
   - Check if call was actually recorded (some calls may not be recorded)

2. **Check Webhook Payload:**
   ```bash
   # Add logging to see full payload
   railway logs --filter "callrail" | grep "call.completed"
   ```

3. **Verify Recording URL Format:**
   - CallRail may use `recording` or `recording_url` field
   - Code checks both: `data.get("recording") or data.get("recording_url")`

### Recording URL Not Accessible

**Problem:** Shunya can't download recording from CallRail URL.

**Solutions:**
1. **Check URL is Public:**
   - CallRail recording URLs should be publicly accessible
   - Test: `curl https://app.callrail.com/recordings/abc123.mp3`

2. **Check URL Expiration:**
   - Some CallRail URLs may expire
   - Ensure webhook is processed quickly (async job handles this)

3. **Check Shunya Logs:**
   ```bash
   railway logs --filter "shunya" | grep "transcribe"
   ```

### Shunya Processing Not Starting

**Problem:** Recording URL received but Shunya job not created.

**Solutions:**
1. **Check Call Record Exists:**
   ```sql
   SELECT * FROM calls WHERE call_id = YOUR_CALL_ID;
   ```
   - Call record must exist before Shunya processing starts

2. **Check Async Job Service:**
   ```sql
   SELECT * FROM shunya_jobs 
   WHERE call_id = YOUR_CALL_ID 
   ORDER BY created_at DESC;
   ```

3. **Check Error Logs:**
   ```bash
   railway logs --filter "shunya_async_job" | grep "error"
   ```

---

## Summary

✅ **Yes, the system fully supports CallRail recordings:**

1. ✅ CallRail sends recording URL in `call.completed` webhook
2. ✅ Backend extracts recording URL automatically
3. ✅ Recording URL sent to Shunya for transcription
4. ✅ Shunya transcribes and analyzes the call
5. ✅ Results stored in database (`CallTranscript`, `CallAnalysis`)
6. ✅ Lead status updated, appointments created, tasks generated

**No additional configuration needed** - it works automatically once:
- CallRail webhook is configured
- Recording is enabled in CallRail
- Company `phone_number` matches tracking number

---

## Next Steps

1. **Enable Recording in CallRail** (if not already enabled)
2. **Verify Webhook Includes Recording URL** (check logs)
3. **Test with Real Call** (make a call, check database)
4. **Monitor Shunya Processing** (check logs and database)

The flow is **fully automated** - just ensure CallRail is configured correctly!


