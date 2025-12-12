# Real-World Usage Guide

## Overview

After running `cleanup_seed_data.py`, your database is clean and ready for real data. This guide explains how real calls flow through the system and how to use it in production.

## End-to-End Flow

### 1. **Incoming Call (CallRail Webhook)**

When a real call comes in, CallRail sends webhooks to your backend:

**Webhook Endpoints:**
- `POST /api/v1/callrail/call.incoming` - Call starts ringing
- `POST /api/v1/callrail/call.answered` - Call is answered
- `POST /api/v1/callrail/call.completed` - Call ends (with recording)

**What Happens:**
1. CallRail sends webhook with:
   - `call_id` (CallRail's call ID)
   - `caller_number` (customer phone)
   - `tracking_number` (your tracking number)
   - `recording_url` (after call completes)
   - `duration`, `answered`, etc.

2. Backend automatically:
   - Creates/updates `ContactCard` (from phone number)
   - Creates/updates `Lead` (linked to contact)
   - Creates/updates `Call` record
   - Identifies company by tracking number

**Example CallRail Webhook:**
```json
{
  "call_id": "CAL019a4be69ef4764db2d8ac1d6b21ee00",
  "caller_number": "+15551234567",
  "tracking_number": "+15559876543",
  "recording_url": "https://callrail.com/recordings/abc123.mp3",
  "duration": 180,
  "answered": true,
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### 2. **Shunya Processing (Automatic)**

When a call completes with a recording, the backend automatically:

**Step 1: Transcription**
- Extracts `recording_url` from CallRail webhook
- Sends to Shunya: `POST /api/v1/transcription/transcribe`
- Shunya transcribes audio → returns `transcript_text`
- Stored in `CallTranscript` table

**Step 2: Analysis**
- Sends transcript to Shunya: `POST /api/v1/analysis/start/{call_id}`
- Shunya analyzes:
  - Lead qualification (hot/warm/cold)
  - Booking status (booked/not_booked/service_not_offered)
  - Objections (if any)
  - SOP compliance
  - Sentiment score
  - Call outcome category
- Results stored in `CallAnalysis` table

**Step 3: Webhook Notification**
- Shunya sends webhook to: `POST /api/v1/shunya/webhook`
- Backend processes and stores final analysis
- Updates `Call`, `Lead`, and creates `Appointment` if booked

### 3. **Frontend Display**

Your frontend can now fetch real data:

**CSR Dashboard:**
```bash
# Get all calls (with Shunya analysis)
GET /api/v1/calls?limit=50

# Get CSR metrics
GET /api/v1/metrics/csr/overview/self

# Get leads
GET /api/v1/leads?status=new,warm,hot

# Get appointments
GET /api/v1/appointments?date=2025-01-15
```

**Sales Rep App:**
```bash
# Get today's appointments
GET /api/v1/appointments/today/self

# Get sales rep metrics
GET /api/v1/metrics/sales/rep/overview/self

# Start recording session (when rep arrives at location)
POST /api/v1/recordings/sessions/start
{
  "appointment_id": "uuid-here"
}

# Stop recording session (after visit)
POST /api/v1/recordings/sessions/{session_id}/stop
{
  "audio_url": "https://s3.amazonaws.com/audio.mp3"
}
```

**Executive Dashboard:**
```bash
# Get company-wide metrics
GET /api/v1/metrics/exec/csr/overview
GET /api/v1/metrics/exec/sales/overview
```

### 4. **Creating Appointments (Manual or Automatic)**

**Automatic (from Shunya):**
- If Shunya detects `booking_status: "booked"` in call analysis
- Backend automatically creates `Appointment` record
- Linked to the `Call` and `Lead`
- Assigned to sales rep (if specified)

**Manual (via API):**
```bash
POST /api/v1/appointments
{
  "lead_id": "lead-uuid",
  "scheduled_start": "2025-01-20T14:00:00Z",
  "assigned_rep_id": "user_123",
  "location": "123 Main St, City, State",
  "service_type": "roofing_estimate"
}
```

### 5. **Sales Rep Visit Recording**

When a sales rep visits a customer:

**Step 1: Rep arrives at location**
- Frontend detects geofence entry
- Calls: `POST /api/v1/recordings/sessions/start`
- Backend creates `RecordingSession` with status="recording"

**Step 2: Rep completes visit**
- Frontend uploads audio to S3
- Calls: `POST /api/v1/recordings/sessions/{session_id}/stop`
- Backend:
  - Updates session status="completed"
  - Sends audio to Shunya for analysis
  - Shunya analyzes visit → stores in `RecordingAnalysis`
  - Updates `Appointment.outcome` (won/lost/pending)

## Setup Checklist

### 1. **Configure CallRail Webhooks**

In CallRail dashboard:
- Go to Settings → Integrations → Webhooks
- Add webhook URL: `https://your-backend.com/api/v1/callrail/call.completed`
- Enable events: `call.incoming`, `call.answered`, `call.completed`
- Add tracking numbers for each company

### 2. **Configure Shunya Webhook**

In Shunya dashboard:
- Add webhook URL: `https://your-backend.com/api/v1/shunya/webhook`
- Configure HMAC secret (must match backend config)
- Enable events: `job.completed`, `job.failed`

### 3. **Set Up Company Tracking Numbers**

For each company in your system:
- Add tracking numbers to `Company` model
- Map tracking numbers to companies in `enhanced_callrail.py::find_company_by_tracking_number()`

### 4. **Test with Real Call**

1. Make a test call to your tracking number
2. Answer the call and have a conversation
3. End the call
4. Check logs:
   ```bash
   # Railway logs
   railway logs
   
   # Or check database
   SELECT * FROM calls ORDER BY created_at DESC LIMIT 1;
   SELECT * FROM call_analyses ORDER BY created_at DESC LIMIT 1;
   ```

## What to Expect

### Empty State (Initially)
- All API endpoints return empty arrays: `{"data": {"items": [], "total": 0}}`
- Metrics return zeros: `{"total_calls": 0, "booked_calls": 0, ...}`
- This is normal! Data will populate as real calls come in.

### After First Call
- `GET /api/v1/calls` returns 1 call
- `GET /api/v1/leads` returns 1 lead
- `GET /api/v1/metrics/csr/overview/self` shows metrics for that call
- If booked, `GET /api/v1/appointments` returns 1 appointment

### After Multiple Calls
- Dashboard populates with real data
- Metrics calculate from actual Shunya analysis
- Trends show real booking rates, qualification rates, etc.

## Troubleshooting

### No Calls Appearing
1. Check CallRail webhook is configured correctly
2. Verify webhook URL is accessible (not blocked by firewall)
3. Check Railway logs for webhook errors:
   ```bash
   railway logs --filter "callrail"
   ```

### Shunya Analysis Not Completing
1. Check Shunya webhook is configured
2. Verify HMAC signature secret matches
3. Check Shunya job status:
   ```sql
   SELECT * FROM shunya_jobs ORDER BY created_at DESC LIMIT 10;
   ```
4. Check logs:
   ```bash
   railway logs --filter "shunya"
   ```

### Empty Metrics
- Normal if no calls yet
- If calls exist but metrics are zero, check:
  - `CallAnalysis` records exist (Shunya processed the calls)
  - `booking_status`, `call_outcome_category` are set correctly
  - Date range in metrics query includes call dates

## Next Steps

1. **Run cleanup script** (if not done):
   ```bash
   python3 -m scripts.cleanup_seed_data
   ```

2. **Configure webhooks** (CallRail + Shunya)

3. **Make test call** to verify end-to-end flow

4. **Monitor logs** to see data flowing:
   ```bash
   railway logs --tail
   ```

5. **Check frontend** - should show real data as calls come in

## API Examples

### Check if System is Ready
```bash
# Should return empty arrays (not errors)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-backend.com/api/v1/calls

# Should return zeros (not errors)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-backend.com/api/v1/metrics/csr/overview/self
```

### After First Call
```bash
# Should return 1 call
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-backend.com/api/v1/calls

# Should show metrics for that call
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-backend.com/api/v1/metrics/csr/overview/self
```

## Summary

**The system is now ready for real data:**
- ✅ Clean database (no seed data)
- ✅ Webhooks configured (CallRail → Backend → Shunya)
- ✅ Automatic processing (calls → transcription → analysis → storage)
- ✅ Frontend APIs return empty results gracefully
- ✅ Metrics calculate from real Shunya analysis

**Just start making real calls, and the system will populate automatically!**


