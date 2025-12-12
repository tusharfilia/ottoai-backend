# Pilot Onboarding & QA Runbook
## 2-Customer Pilot Execution Guide

**Last Updated**: 2025-01-XX  
**Purpose**: Manual onboarding and controlled call scenario testing for 2-customer pilot  
**Constraints**: No backend code changes, no schema edits, no demo mode, no special casing

---

## Table of Contents

1. [A) Manual Onboarding Runbook](#a-manual-onboarding-runbook)
2. [B) Scenario 1 - Inbound Call Booked Immediately](#b-scenario-1---inbound-call-booked-immediately)
3. [C) Scenario 2 - Qualified But Not Booked, Requires Follow-Up](#c-scenario-2---qualified-but-not-booked-requires-follow-up)
4. [D) Pilot Readiness Checklist](#d-pilot-readiness-checklist)
5. [E) Pilot Blockers](#e-pilot-blockers)

---

## A) Manual Onboarding Runbook

### A.1 Create/Configure Tenant/Company in Backend

**Location**: `app/routes/company.py::create_company`

**Endpoint**: `POST /api/v1/company/?name={name}&phone_number={phone}&address={address}`

**Method**: Via API (requires manager role)

**Steps**:

1. **Get Clerk JWT token** (as manager/exec user):
   ```bash
   # Use Clerk dashboard or API to get JWT token for a manager user
   # Token must include org_id claim matching the company you're creating
   ```

2. **Create company via API**:
   ```bash
   curl -X POST "https://your-railway-url.com/api/v1/company/?name=Test%20Company&phone_number=%2B15551234567&address=123%20Main%20St" \
     -H "Authorization: Bearer YOUR_CLERK_JWT_TOKEN" \
     -H "Content-Type: application/json"
   ```

   **Expected Response**:
   ```json
   {
     "status": "success",
     "company_id": "org_2a1b3c4d5e6f7g8h",
     "clerk_org_id": "org_2a1b3c4d5e6f7g8h"
   }
   ```

3. **Verify in Database**:
   ```sql
   SELECT id, name, phone_number, address, created_at 
   FROM companies 
   WHERE id = 'org_2a1b3c4d5e6f7g8h';
   ```

   **Success Signals**:
   - Row exists in `companies` table
   - `id` matches Clerk org ID
   - `phone_number` matches tracking number you'll use in CallRail

**File Reference**: `ottoai-backend/services/dashboard/app/routes/company.py:224-305`

---

### A.2 Create Clerk Users Manually (CSR + Sales Rep + Exec)

**Location**: Clerk Dashboard or `app/routes/user.py::create_user`

**Method**: Via Clerk Dashboard (recommended) or API

**Steps**:

1. **Create CSR User**:
   - Go to Clerk Dashboard → Users → Create User
   - Email: `csr@testcompany.com`
   - Password: Set temporary password
   - **Add to Organization**: Select the company org (created in A.1)
   - **Assign Role**: `org:csr` (maps to Otto `csr` role)
   - **Verify Role Mapping**: `app/middleware/tenant.py:220-259`
     - Clerk `org:csr` → Otto `csr`
     - Clerk `org:sales_rep` → Otto `sales_rep`
     - Clerk `org:admin` → Otto `manager`

2. **Create Sales Rep User**:
   - Email: `salesrep@testcompany.com`
   - **Assign Role**: `org:sales_rep` (maps to Otto `sales_rep` role)
   - Add to same organization

3. **Create Exec/Manager User**:
   - Email: `manager@testcompany.com`
   - **Assign Role**: `org:admin` or `org:manager` (maps to Otto `manager` role)
   - Add to same organization

4. **Verify Claims/Role Mapping**:
   ```bash
   # Test JWT token extraction (use Clerk API or decode JWT)
   # Verify JWT contains:
   # - org_id: matches company_id from A.1
   # - org_role: "org:csr", "org:sales_rep", or "org:admin"
   ```

5. **Create Otto User Records** (if not auto-created via webhook):
   ```bash
   # Option 1: Via API (if user creation endpoint exists)
   curl -X POST "https://your-railway-url.com/api/v1/user/" \
     -H "Authorization: Bearer MANAGER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "csr@testcompany.com",
       "username": "csr",
       "name": "CSR User",
       "role": "csr",
       "company_id": "org_2a1b3c4d5e6f7g8h"
     }'
   
   # Option 2: Direct DB insert (if needed)
   # INSERT INTO users (id, email, username, name, role, company_id, clerk_id)
   # VALUES ('user_csr_123', 'csr@testcompany.com', 'csr', 'CSR User', 'csr', 'org_2a1b3c4d5e6f7g8h', 'user_clerk_csr_123');
   ```

6. **Verify User Records**:
   ```sql
   SELECT id, email, role, company_id, clerk_id 
   FROM users 
   WHERE company_id = 'org_2a1b3c4d5e6f7g8h';
   ```

   **Success Signals**:
   - 3 users exist (csr, sales_rep, manager)
   - `role` field matches: `csr`, `sales_rep`, `manager`
   - `company_id` matches company from A.1
   - `clerk_id` matches Clerk user ID

**File Reference**: 
- `ottoai-backend/services/dashboard/app/middleware/tenant.py:220-259` (role mapping)
- `ottoai-backend/services/dashboard/app/routes/user.py:101-189` (user creation)

---

### A.3 Configure CallRail Webhooks to Otto

**Location**: CallRail Dashboard → Settings → Webhooks

**Endpoints** (exact URLs):

1. **Call Incoming**: `POST https://your-railway-url.com/api/v1/callrail/call.incoming`
2. **Call Answered**: `POST https://your-railway-url.com/api/v1/callrail/call.answered`
3. **Call Missed**: `POST https://your-railway-url.com/api/v1/callrail/call.missed`
4. **Call Completed**: `POST https://your-railway-url.com/api/v1/callrail/call.completed`
5. **SMS Events**: `POST https://your-railway-url.com/sms/callrail-webhook`

**Steps**:

1. **In CallRail Dashboard**:
   - Go to Settings → Integrations → Webhooks
   - Add webhook URL for each event type above
   - Enable events: `call.incoming`, `call.answered`, `call.missed`, `call.completed`, `sms.received`

2. **Configure Tracking Number**:
   - In CallRail, add tracking number (must match `phone_number` from A.1)
   - Link tracking number to CallRail account

3. **Test Webhook Receipt**:
   ```bash
   # Make a test call to tracking number
   # Check Railway logs:
   railway logs --filter "callrail"
   
   # Expected log entry:
   # "CallRail call.incoming webhook: {...}"
   ```

4. **Verify Webhook Processing**:
   ```sql
   -- Check if call record was created
   SELECT call_id, phone_number, company_id, created_at 
   FROM calls 
   WHERE company_id = 'org_2a1b3c4d5e6f7g8h' 
   ORDER BY created_at DESC 
   LIMIT 1;
   ```

   **Success Signals**:
   - Log shows webhook received
   - `Call` record created in DB
   - `ContactCard` created/updated
   - `Lead` created/updated

**File Reference**: 
- `ottoai-backend/services/dashboard/app/routes/enhanced_callrail.py:87-340`
- `ottoai-backend/services/dashboard/docs/EXTERNAL_SERVICES_SETUP.md:47-55`

---

### A.4 Configure Twilio Webhooks for SMS

**Location**: Twilio Dashboard → Phone Numbers → Active Numbers

**Endpoints**:

1. **SMS Webhook**: `POST https://your-railway-url.com/sms/twilio-webhook`
2. **Alternative Route**: `POST https://your-railway-url.com/api/v1/sms/twilio-webhook` (if exists)

**Steps**:

1. **In Twilio Dashboard**:
   - Go to Phone Numbers → Manage → Active Numbers
   - Click on your purchased number
   - Set **SMS webhook URL**: `https://your-railway-url.com/sms/twilio-webhook`
   - HTTP Method: `POST`
   - Save configuration

2. **Test SMS Webhook**:
   ```bash
   # Send test SMS to Twilio number
   # Check Railway logs:
   railway logs --filter "twilio"
   
   # Expected log entry:
   # "Twilio SMS webhook received from +15551234567: <message>"
   ```

3. **Verify SMS Processing**:
   ```sql
   -- Check if SMS thread was created (if SMS model exists)
   -- Or check contact_card for SMS history
   SELECT * FROM contact_cards 
   WHERE company_id = 'org_2a1b3c4d5e6f7g8h' 
   ORDER BY updated_at DESC 
   LIMIT 1;
   ```

   **Success Signals**:
   - Log shows SMS webhook received
   - SMS processed and linked to contact

**File Reference**: 
- `ottoai-backend/services/dashboard/app/routes/sms_handler.py:115-180`
- `ottoai-backend/services/dashboard/docs/EXTERNAL_SERVICES_SETUP.md:28-33`

---

### A.5 Perform Document Ingestion to Shunya

**Location**: `app/routes/onboarding/onboarding_routes.py::upload_document`

**Endpoint**: `POST /api/v1/onboarding/documents/upload`

**Steps**:

1. **Upload SOP Document** (for CSR):
   ```bash
   curl -X POST "https://your-railway-url.com/api/v1/onboarding/documents/upload" \
     -H "Authorization: Bearer MANAGER_TOKEN" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@/path/to/sop.pdf" \
     -F "category=sop" \
     -F "role_target=csr" \
     -F "metadata={\"document_type\":\"sop\",\"target_role\":\"customer_rep\"}"
   ```

   **Expected Response**:
   ```json
   {
     "success": true,
     "data": {
       "document_id": "doc_123",
       "status": "pending",
       "s3_url": "https://s3.../sop.pdf"
     }
   }
   ```

2. **Upload SOP Document** (for Sales Rep):
   ```bash
   curl -X POST "https://your-railway-url.com/api/v1/onboarding/documents/upload" \
     -H "Authorization: Bearer MANAGER_TOKEN" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@/path/to/sales_sop.pdf" \
     -F "category=sop" \
     -F "role_target=sales_rep" \
     -F "metadata={\"document_type\":\"sop\",\"target_role\":\"sales_rep\"}"
   ```

3. **Check Ingestion Status**:
   ```bash
   curl -X GET "https://your-railway-url.com/api/v1/onboarding/documents/status/doc_123" \
     -H "Authorization: Bearer MANAGER_TOKEN"
   ```

4. **Verify Shunya Ingestion**:
   ```sql
   -- Check document record
   SELECT id, filename, category, role_target, ingestion_status, shunya_job_id 
   FROM documents 
   WHERE company_id = 'org_2a1b3c4d5e6f7g8h';
   
   -- Check Shunya job
   SELECT id, job_type, job_status, shunya_job_id, input_payload 
   FROM shunya_jobs 
   WHERE company_id = 'org_2a1b3c4d5e6f7g8h' 
   AND job_type = 'document_ingestion';
   ```

   **Success Signals**:
   - Document record created with `ingestion_status = 'completed'`
   - Shunya job created with `job_status = 'succeeded'`
   - Shunya received document with correct `target_role` query param

**File Reference**: 
- `ottoai-backend/services/dashboard/app/routes/onboarding/onboarding_routes.py:249-309`
- `ottoai-backend/services/dashboard/app/tasks/onboarding_tasks.py:17-122`
- `ottoai-backend/services/dashboard/app/services/uwc_client.py:1001-1044`

**Critical**: `target_role` must be set correctly:
- `csr` → `customer_rep` (Shunya target role)
- `sales_rep` → `sales_rep` (Shunya target role)
- `manager` → `sales_manager` (Shunya target role)

---

### A.6 Verify Ask Otto Works Per Role

**Location**: `app/routes/rag.py::query_ask_otto`

**Endpoint**: `POST /api/v1/rag/query`

**Steps**:

1. **Test as CSR** (should scope to CSR-only data):
   ```bash
   curl -X POST "https://your-railway-url.com/api/v1/rag/query" \
     -H "Authorization: Bearer CSR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "What are the most common objections?",
       "filters": {}
     }'
   ```

   **Expected Behavior**:
   - Request includes `X-Target-Role: customer_rep` header (set by backend)
   - Response scoped to CSR-only data (no sales rep data)
   - Citations from CSR SOPs only

2. **Test as Sales Rep** (should scope to self-only data):
   ```bash
   curl -X POST "https://your-railway-url.com/api/v1/rag/query" \
     -H "Authorization: Bearer SALES_REP_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "What are my upcoming appointments?",
       "filters": {}
     }'
   ```

   **Expected Behavior**:
   - Request includes `X-Target-Role: sales_rep` header
   - Response scoped to this rep's data only
   - Citations from sales rep SOPs

3. **Test as Manager** (should scope to company-wide data):
   ```bash
   curl -X POST "https://your-railway-url.com/api/v1/rag/query" \
     -H "Authorization: Bearer MANAGER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "What are the company-wide booking rates?",
       "filters": {}
     }'
   ```

   **Expected Behavior**:
   - Request includes `X-Target-Role: sales_manager` header
   - Response scoped to company-wide data
   - Citations from all SOPs

4. **Verify Target Role Mapping**:
   ```sql
   -- Check RAG query logs (if stored)
   SELECT query_text, user_role, uwc_request_id 
   FROM rag_queries 
   WHERE company_id = 'org_2a1b3c4d5e6f7g8h' 
   ORDER BY created_at DESC 
   LIMIT 3;
   ```

   **Success Signals**:
   - Each query has correct `user_role` stored
   - Shunya receives correct `X-Target-Role` header (check Shunya logs)
   - Responses are correctly scoped per role

**File Reference**: 
- `ottoai-backend/services/dashboard/app/routes/rag.py:95-170`
- `ottoai-backend/services/dashboard/app/services/uwc_client.py::_map_otto_role_to_shunya_target_role`

**Role Mapping**:
- Otto `csr` → Shunya `customer_rep`
- Otto `sales_rep` → Shunya `sales_rep`
- Otto `manager` → Shunya `sales_manager`

---

## B) Scenario 1 — Inbound Call Booked Immediately

### B.1 Trigger Inbound Call via CallRail Number

**Steps**:

1. **Make test call** to CallRail tracking number (configured in A.3)
2. **Answer call** and have conversation that results in booking
3. **End call** (CallRail will send `call.completed` webhook)

**Expected Webhook Flow**:
- `POST /api/v1/callrail/call.incoming` → Call starts
- `POST /api/v1/callrail/call.answered` → Call answered
- `POST /api/v1/callrail/call.completed` → Call ends with recording

---

### B.2 Confirm Otto Ingests Call + Stores Transcript/Analysis

**Verification Steps**:

1. **Check Call Record**:
   ```sql
   SELECT call_id, phone_number, company_id, recording_url, duration, created_at 
   FROM calls 
   WHERE company_id = 'org_2a1b3c4d5e6f7g8h' 
   ORDER BY created_at DESC 
   LIMIT 1;
   ```

   **Expected**:
   - `call_id` exists
   - `phone_number` matches caller
   - `recording_url` populated (from CallRail)
   - `duration` > 0

2. **Check Shunya Job Created**:
   ```sql
   SELECT id, job_type, job_status, shunya_job_id, call_id, company_id 
   FROM shunya_jobs 
   WHERE call_id = '<call_id_from_above>' 
   AND company_id = 'org_2a1b3c4d5e6f7g8h';
   ```

   **Expected**:
   - Job exists with `job_type = 'csr_call'`
   - `job_status` = `'succeeded'` (after processing)
   - `shunya_job_id` populated

3. **Check Call Transcript**:
   ```sql
   SELECT call_id, transcript_text, created_at 
   FROM call_transcripts 
   WHERE call_id = '<call_id_from_above>';
   ```

   **Expected**:
   - `transcript_text` populated (from Shunya transcription)

4. **Check Call Analysis**:
   ```sql
   SELECT call_id, lead_quality, booking_status, call_outcome_category, 
          objections, sop_compliance_score, sentiment_score 
   FROM call_analyses 
   WHERE call_id = '<call_id_from_above>';
   ```

   **Expected**:
   - `booking_status = 'booked'` (from Shunya)
   - `lead_quality` populated (hot/warm/cold from Shunya)
   - `call_outcome_category` populated (from Shunya)
   - **CRITICAL**: All fields come from Shunya, not inferred by Otto

**File Reference**: 
- `ottoai-backend/services/dashboard/app/routes/enhanced_callrail.py:312-340`
- `ottoai-backend/services/dashboard/app/services/shunya_integration_service.py:473-849`

---

### B.3 Confirm Lead/Contact Card Created/Updated

**Verification Steps**:

1. **Check ContactCard**:
   ```sql
   SELECT id, primary_phone, first_name, last_name, address, company_id 
   FROM contact_cards 
   WHERE company_id = 'org_2a1b3c4d5e6f7g8h' 
   AND primary_phone = '<caller_phone_number>';
   ```

   **Expected**:
   - ContactCard exists (created or updated)
   - `primary_phone` matches caller
   - Name fields populated (if extracted from call)

2. **Check Lead**:
   ```sql
   SELECT id, contact_card_id, status, source, company_id, created_at 
   FROM leads 
   WHERE contact_card_id = '<contact_card_id_from_above>' 
   AND company_id = 'org_2a1b3c4d5e6f7g8h';
   ```

   **Expected**:
   - Lead exists
   - `status` updated based on Shunya classification
   - `source` = `'inbound_call'` or similar

**File Reference**: 
- `ottoai-backend/services/dashboard/app/services/domain_entities.py::ensure_contact_card_and_lead`

---

### B.4 Confirm Shunya booking_status Reflects "booked" and Otto Surfaces It

**Verification Steps**:

1. **Check CallAnalysis.booking_status**:
   ```sql
   SELECT call_id, booking_status, lead_quality, call_outcome_category 
   FROM call_analyses 
   WHERE call_id = '<call_id>' 
   AND booking_status = 'booked';
   ```

   **Expected**:
   - `booking_status = 'booked'` (from Shunya, not inferred)

2. **Check Lead Status**:
   ```sql
   SELECT id, status, last_qualified_at 
   FROM leads 
   WHERE id = '<lead_id>' 
   AND status = 'qualified_booked';
   ```

   **Expected**:
   - `status = 'qualified_booked'` (updated from Shunya analysis)

3. **Verify via API**:
   ```bash
   curl -X GET "https://your-railway-url.com/api/v1/calls/<call_id>/analysis" \
     -H "Authorization: Bearer CSR_TOKEN"
   ```

   **Expected Response**:
   ```json
   {
     "success": true,
     "data": {
       "booking_status": "booked",
       "lead_quality": "hot",
       "call_outcome_category": "booked"
     }
   }
   ```

**File Reference**: 
- `ottoai-backend/services/dashboard/app/models/call_analysis.py:118-122`
- `ottoai-backend/services/dashboard/app/services/shunya_integration_service.py:692-727`

---

### B.5 Confirm Appointment Exists (with Scheduled Time/Date)

**Verification Steps**:

1. **Check Appointment Record**:
   ```sql
   SELECT id, lead_id, contact_card_id, scheduled_start, scheduled_end, 
          status, location_address, company_id 
   FROM appointments 
   WHERE lead_id = '<lead_id>' 
   AND company_id = 'org_2a1b3c4d5e6f7g8h';
   ```

   **Expected**:
   - Appointment exists
   - `scheduled_start` populated (from Shunya entities or manual)
   - `scheduled_end` populated (if provided)
   - `status = 'scheduled'` or `'confirmed'`
   - `location_address` populated (if extracted from call)

2. **Verify Appointment Creation Logic**:
   ```sql
   -- Check if appointment was auto-created from Shunya analysis
   SELECT id, booking_status, entities 
   FROM call_analyses 
   WHERE call_id = '<call_id>' 
   AND booking_status = 'booked';
   
   -- entities JSON should contain appointment time/date if Shunya extracted it
   ```

3. **Verify via API**:
   ```bash
   curl -X GET "https://your-railway-url.com/api/v1/appointments?lead_id=<lead_id>" \
     -H "Authorization: Bearer CSR_TOKEN"
   ```

   **Expected Response**:
   ```json
   {
     "success": true,
     "data": {
       "items": [
         {
           "id": "apt_123",
           "scheduled_start": "2025-01-20T14:00:00Z",
           "scheduled_end": "2025-01-20T15:00:00Z",
           "status": "scheduled",
           "location_address": "123 Main St, City, State"
         }
       ]
     }
   }
   ```

**File Reference**: 
- `ottoai-backend/services/dashboard/app/services/shunya_integration_service.py:728-850`
- `ottoai-backend/services/dashboard/app/models/appointment.py`

**Note**: If Shunya doesn't extract appointment time/address, you can manually set `ContactCard.address` (see B.6)

---

### B.6 Manual Address Setting (if Shunya Doesn't Extract)

**Location**: `app/routes/contact_cards.py` or direct DB update

**Option 1: Via API** (if endpoint exists):
```bash
# Check if PUT /api/v1/contact-cards/{contact_id} exists
curl -X PUT "https://your-railway-url.com/api/v1/contact-cards/<contact_id>" \
  -H "Authorization: Bearer MANAGER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Main St, City, State 12345",
    "city": "City",
    "state": "State",
    "postal_code": "12345"
  }'
```

**Option 2: Direct DB Update** (for testing only):
```sql
UPDATE contact_cards 
SET address = '123 Main St, City, State 12345',
    city = 'City',
    state = 'State',
    postal_code = '12345'
WHERE id = '<contact_card_id>' 
AND company_id = 'org_2a1b3c4d5e6f7g8h';
```

**Option 3: Trigger Property Intelligence**:
```bash
curl -X POST "https://your-railway-url.com/api/v1/contact-cards/<contact_id>/refresh-property" \
  -H "Authorization: Bearer MANAGER_TOKEN"
```

**Expected**: Property intelligence service triggers geofence/property snapshot update

**File Reference**: 
- `ottoai-backend/services/dashboard/app/routes/contact_cards.py:126-174`
- `ottoai-backend/services/dashboard/app/services/property_intelligence_service.py:85-122`

---

### B.7 CSR Dispatches to Sales Rep (Manual Dispatch)

**Location**: `app/routes/appointments.py::assign_appointment_to_rep`

**Endpoint**: `POST /api/v1/appointments/{appointment_id}/assign`

**Steps**:

1. **Get Sales Rep ID**:
   ```bash
   curl -X GET "https://your-railway-url.com/api/v1/sales-reps" \
     -H "Authorization: Bearer CSR_TOKEN"
   ```

2. **Assign Appointment**:
   ```bash
   curl -X POST "https://your-railway-url.com/api/v1/appointments/<appointment_id>/assign" \
     -H "Authorization: Bearer CSR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "rep_id": "user_sales_rep_123",
       "allow_double_booking": false
     }'
   ```

   **Expected Response**:
   ```json
   {
     "success": true,
     "data": {
       "id": "apt_123",
       "assigned_rep_id": "user_sales_rep_123",
       "status": "scheduled"
     }
   }
   ```

3. **Verify Double-Booking Prevention**:
   ```sql
   -- Try to assign overlapping appointment to same rep
   -- Should fail with error: "Double-booking conflict"
   ```

4. **Check Appointment Assignment**:
   ```sql
   SELECT id, assigned_rep_id, status, scheduled_start, scheduled_end 
   FROM appointments 
   WHERE id = '<appointment_id>' 
   AND assigned_rep_id = 'user_sales_rep_123';
   ```

   **Expected**:
   - `assigned_rep_id` populated
   - Status remains `'scheduled'` or `'confirmed'`

**File Reference**: 
- `ottoai-backend/services/dashboard/app/routes/appointments.py:922-996`
- `ottoai-backend/services/dashboard/app/services/appointment_dispatch_service.py:33-142`

---

### B.8 Sales Rep Sees Appointment in Today/Upcoming Endpoints

**Verification Steps**:

1. **Get Today's Appointments** (as Sales Rep):
   ```bash
   curl -X GET "https://your-railway-url.com/api/v1/metrics/appointments/today/self" \
     -H "Authorization: Bearer SALES_REP_TOKEN"
   ```

   **Expected Response**:
   ```json
   {
     "success": true,
     "data": [
       {
         "appointment_id": "apt_123",
         "scheduled_time": "2025-01-20T14:00:00Z",
         "customer_name": "John Doe",
         "address": "123 Main St, City, State",
         "status": "scheduled"
       }
     ]
   }
   ```

2. **Get Upcoming Appointments**:
   ```bash
   curl -X GET "https://your-railway-url.com/api/v1/appointments?date=2025-01-20" \
     -H "Authorization: Bearer SALES_REP_TOKEN"
   ```

3. **Verify Self-Scoping**:
   ```sql
   -- Sales rep should ONLY see their own appointments
   SELECT id, assigned_rep_id, scheduled_start 
   FROM appointments 
   WHERE company_id = 'org_2a1b3c4d5e6f7g8h' 
   AND assigned_rep_id = 'user_sales_rep_123'
   AND scheduled_start >= CURRENT_DATE;
   ```

   **Expected**:
   - Only appointments assigned to this rep are returned
   - No other rep's appointments visible

**File Reference**: 
- `ottoai-backend/services/dashboard/app/routes/metrics_kpis.py:1291-1324`
- `ottoai-backend/services/dashboard/app/services/metrics_service.py:3752-3801`

---

### B.9 Verification Checklist Summary

**API Endpoints to Check**:
- ✅ `GET /api/v1/calls/{call_id}` - Call details
- ✅ `GET /api/v1/calls/{call_id}/analysis` - Shunya analysis results
- ✅ `GET /api/v1/contact-cards/{contact_id}` - Contact card with property intelligence
- ✅ `GET /api/v1/appointments/{appointment_id}` - Appointment details
- ✅ `GET /api/v1/metrics/appointments/today/self` - Sales rep today's appointments

**DB Models to Verify**:
- ✅ `Call` - Call record with `recording_url`
- ✅ `CallTranscript` - Transcript from Shunya
- ✅ `CallAnalysis` - Analysis with `booking_status = 'booked'`, `lead_quality`, `call_outcome_category`
- ✅ `ContactCard` - Contact with address (triggers property intelligence)
- ✅ `Lead` - Lead with `status = 'qualified_booked'`
- ✅ `Appointment` - Appointment with `scheduled_start`, `assigned_rep_id`
- ✅ `ShunyaJob` - Job with `job_status = 'succeeded'`

**Frontend Screens to Check**:
- ✅ CSR Dashboard - Shows call with booking status
- ✅ Contact Card View - Shows appointment, property intelligence
- ✅ Sales Rep App - Shows today's appointments
- ✅ Appointment Dispatch UI - Shows assignment confirmation

---

## C) Scenario 2 — Qualified But Not Booked, Requires Follow-Up

### C.1 Trigger Inbound Call via CallRail Number

**Steps**: Same as B.1, but steer conversation to be qualified but not booked

---

### C.2 Confirm Shunya lead_quality Reflects Qualified Status

**Verification Steps**:

1. **Check CallAnalysis.lead_quality**:
   ```sql
   SELECT call_id, lead_quality, booking_status, call_outcome_category 
   FROM call_analyses 
   WHERE call_id = '<call_id>' 
   AND company_id = 'org_2a1b3c4d5e6f7g8h';
   ```

   **Expected**:
   - `lead_quality` = `'hot'`, `'warm'`, or `'cold'` (from Shunya)
   - `booking_status` = `'not_booked'` (from Shunya)
   - `call_outcome_category` = `'qualified_but_unbooked'` (from Shunya)

2. **Verify Lead Status**:
   ```sql
   SELECT id, status, last_qualified_at 
   FROM leads 
   WHERE id = '<lead_id>' 
   AND status IN ('qualified_unbooked', 'warm', 'hot');
   ```

   **Expected**:
   - `status` updated based on Shunya classification
   - `last_qualified_at` populated

**File Reference**: 
- `ottoai-backend/services/dashboard/app/services/shunya_integration_service.py:692-727`

---

### C.3 Confirm booking_status is NOT booked and Outcome Category Indicates Qualified-But-Unbooked

**Verification Steps**:

1. **Check CallAnalysis**:
   ```sql
   SELECT call_id, booking_status, call_outcome_category, lead_quality 
   FROM call_analyses 
   WHERE call_id = '<call_id>' 
   AND booking_status = 'not_booked'
   AND call_outcome_category = 'qualified_but_unbooked';
   ```

   **Expected**:
   - `booking_status = 'not_booked'` (from Shunya)
   - `call_outcome_category = 'qualified_but_unbooked'` (from Shunya)
   - **CRITICAL**: These values come from Shunya, not inferred

2. **Verify via API**:
   ```bash
   curl -X GET "https://your-railway-url.com/api/v1/calls/<call_id>/analysis" \
     -H "Authorization: Bearer CSR_TOKEN"
   ```

   **Expected Response**:
   ```json
   {
     "success": true,
     "data": {
       "booking_status": "not_booked",
       "call_outcome_category": "qualified_but_unbooked",
       "lead_quality": "warm"
     }
   }
   ```

---

### C.4 Confirm Lead Appears in CSR Shared Boards/Lists for Pending/Nurture

**Verification Steps**:

1. **Get CSR Pending Leads**:
   ```bash
   curl -X GET "https://your-railway-url.com/api/v1/leads?status=qualified_unbooked,warm,hot" \
     -H "Authorization: Bearer CSR_TOKEN"
   ```

   **Expected Response**:
   ```json
   {
     "success": true,
     "data": {
       "items": [
         {
           "id": "lead_123",
           "status": "qualified_unbooked",
           "contact_card_id": "contact_123",
           "last_qualified_at": "2025-01-20T10:00:00Z"
         }
       ]
     }
   }
   ```

2. **Get CSR Metrics** (should show qualified but unbooked):
   ```bash
   curl -X GET "https://your-railway-url.com/api/v1/metrics/csr/overview/self" \
     -H "Authorization: Bearer CSR_TOKEN"
   ```

   **Expected Response**:
   ```json
   {
     "success": true,
     "data": {
       "qualified_but_unbooked_calls": 1,
       "qualified_calls": 1,
       "booking_rate": 0.0
     }
   }
   ```

3. **Verify CSR Scoping**:
   ```sql
   -- CSR should see ALL leads in company (shared pool)
   SELECT id, status, company_id 
   FROM leads 
   WHERE company_id = 'org_2a1b3c4d5e6f7g8h' 
   AND status IN ('qualified_unbooked', 'warm', 'hot');
   ```

   **Expected**:
   - All qualified but unbooked leads visible to CSR
   - Not scoped to specific CSR user

**File Reference**: 
- `ottoai-backend/services/dashboard/app/routes/metrics_kpis.py:83-129`
- `ottoai-backend/services/dashboard/app/services/metrics_service.py`

---

### C.5 CSR Performs Follow-Up Action (SMS via Twilio from Contact Card)

**Location**: Contact Card UI or SMS API

**Steps**:

1. **Get Contact Card**:
   ```bash
   curl -X GET "https://your-railway-url.com/api/v1/contact-cards/<contact_id>" \
     -H "Authorization: Bearer CSR_TOKEN"
   ```

2. **Send SMS via Twilio** (if SMS sending endpoint exists):
   ```bash
   # Check if POST /api/v1/sms/send exists
   curl -X POST "https://your-railway-url.com/api/v1/sms/send" \
     -H "Authorization: Bearer CSR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "to_number": "+15551234567",
       "message": "Hi, this is a follow-up regarding your inquiry. When would be a good time to connect?",
       "contact_card_id": "contact_123"
     }'
   ```

   **Alternative**: Use Twilio directly (if no endpoint exists):
   - Send SMS via Twilio Dashboard or API
   - SMS will be received via webhook (configured in A.4)

3. **Verify SMS Sent**:
   ```sql
   -- Check if SMS records exist (if SMS model exists)
   -- Or check contact_card for SMS thread
   ```

**File Reference**: 
- `ottoai-backend/services/dashboard/app/routes/sms_handler.py`
- `ottoai-backend/services/dashboard/app/services/twilio_service.py`

---

### C.6 Confirm New SMS Thread Entries Are Captured and Visible

**Verification Steps**:

1. **Check SMS Webhook Received**:
   ```bash
   # Check Railway logs
   railway logs --filter "sms"
   
   # Expected: "Twilio SMS webhook received from +15551234567: <message>"
   ```

2. **Verify SMS Linked to Contact**:
   ```sql
   -- Check if SMS thread model exists
   -- Or check contact_card.custom_metadata for SMS history
   SELECT id, custom_metadata 
   FROM contact_cards 
   WHERE id = '<contact_id>';
   ```

3. **Check Contact Card UI**:
   - Navigate to Contact Card in frontend
   - Verify SMS thread visible in "Messages" or "SMS History" section

**File Reference**: 
- `ottoai-backend/services/dashboard/app/routes/sms_handler.py:115-180`
- `ottoai-backend/services/dashboard/app/services/contact_card_assembler.py::_build_global_blocks`

---

### C.7 Confirm Status Transitions After Follow-Up (Only if Shunya Returns Them)

**Verification Steps**:

1. **Check if Shunya Updates Status**:
   - If customer responds to SMS, Shunya may analyze response
   - Check for new `CallAnalysis` or `Lead` status update

2. **Verify Status Update** (if Shunya provides):
   ```sql
   SELECT id, status, last_qualified_at, updated_at 
   FROM leads 
   WHERE id = '<lead_id>' 
   ORDER BY updated_at DESC;
   ```

   **Expected**:
   - Status updated ONLY if Shunya returns new classification
   - **CRITICAL**: Otto does NOT infer status changes

3. **Check Task Creation** (if Shunya returns pending actions):
   ```sql
   SELECT id, description, assigned_to, source, status, due_at 
   FROM tasks 
   WHERE contact_card_id = '<contact_id>' 
   AND company_id = 'org_2a1b3c4d5e6f7g8h';
   ```

   **Expected**:
   - Tasks created from Shunya `pending_actions` (if any)
   - `source = 'shunya'`
   - `assigned_to = 'csr'` (default)

**File Reference**: 
- `ottoai-backend/services/dashboard/app/services/shunya_integration_service.py:807-844`
- `ottoai-backend/services/dashboard/app/models/task.py:39-88`

---

### C.8 Verification Checklist Summary

**API Endpoints to Check**:
- ✅ `GET /api/v1/leads?status=qualified_unbooked` - Pending leads
- ✅ `GET /api/v1/metrics/csr/overview/self` - CSR metrics with qualified_but_unbooked_calls
- ✅ `GET /api/v1/contact-cards/{contact_id}` - Contact card with SMS thread
- ✅ `GET /api/v1/tasks?contact_card_id={id}` - Follow-up tasks

**DB Models to Verify**:
- ✅ `CallAnalysis` - `booking_status = 'not_booked'`, `call_outcome_category = 'qualified_but_unbooked'`
- ✅ `Lead` - `status = 'qualified_unbooked'` or `'warm'`/`'hot'`
- ✅ `Task` - Tasks created from Shunya `pending_actions` (if any)
- ✅ `ContactCard` - SMS thread entries (if SMS model exists)

**Frontend Screens to Check**:
- ✅ CSR Dashboard - Shows qualified but unbooked leads
- ✅ Contact Card View - Shows SMS thread, follow-up tasks
- ✅ CSR Metrics - Shows `qualified_but_unbooked_calls` count

**What is Shunya-Owned vs Otto-Owned**:
- **Shunya-Owned**: `lead_quality`, `booking_status`, `call_outcome_category`, `objections`, `sop_compliance`, `sentiment`, `pending_actions`
- **Otto-Owned**: `Lead.status` (derived from Shunya), `Task` creation (from Shunya `pending_actions`), `ContactCard` address (if extracted), SMS thread storage

---

## D) Pilot Readiness Checklist

### D.1 Auth/RBAC for All Roles (< 10 minutes)

**Test Steps**:

1. **CSR Role**:
   ```bash
   # Get CSR token, test CSR endpoint
   curl -X GET "https://your-railway-url.com/api/v1/metrics/csr/overview/self" \
     -H "Authorization: Bearer CSR_TOKEN"
   ```
   ✅ Should return 200 (not 403)

2. **Sales Rep Role**:
   ```bash
   # Get sales rep token, test rep endpoint
   curl -X GET "https://your-railway-url.com/api/v1/metrics/appointments/today/self" \
     -H "Authorization: Bearer SALES_REP_TOKEN"
   ```
   ✅ Should return 200 (not 403)

3. **Manager Role**:
   ```bash
   # Get manager token, test manager endpoint
   curl -X GET "https://your-railway-url.com/api/v1/metrics/exec/csr" \
     -H "Authorization: Bearer MANAGER_TOKEN"
   ```
   ✅ Should return 200 (not 403)

4. **Cross-Role Access Denial**:
   ```bash
   # CSR trying to access manager endpoint
   curl -X GET "https://your-railway-url.com/api/v1/metrics/exec/csr" \
     -H "Authorization: Bearer CSR_TOKEN"
   ```
   ✅ Should return 403 Forbidden

**File Reference**: 
- `ottoai-backend/services/dashboard/app/middleware/rbac.py`
- `ottoai-backend/services/dashboard/app/middleware/tenant.py:220-259`

---

### D.2 Tenant Isolation Sanity Check (< 5 minutes)

**Test Steps**:

1. **Create Two Companies** (A and B):
   - Company A: `org_company_a`
   - Company B: `org_company_b`

2. **Create Call in Company A**:
   ```sql
   -- Insert test call for company A
   INSERT INTO calls (call_id, phone_number, company_id, created_at)
   VALUES (1001, '+15551234567', 'org_company_a', NOW());
   ```

3. **Query as Company A User**:
   ```bash
   curl -X GET "https://your-railway-url.com/api/v1/calls" \
     -H "Authorization: Bearer COMPANY_A_TOKEN"
   ```
   ✅ Should return call 1001

4. **Query as Company B User**:
   ```bash
   curl -X GET "https://your-railway-url.com/api/v1/calls" \
     -H "Authorization: Bearer COMPANY_B_TOKEN"
   ```
   ✅ Should return empty array (no calls from company A)

5. **Direct DB Query** (verify isolation):
   ```sql
   -- Company A user should only see company A data
   SELECT call_id, company_id 
   FROM calls 
   WHERE company_id = 'org_company_a';
   ```

**File Reference**: 
- `ottoai-backend/services/dashboard/app/middleware/tenant.py:19-262`
- `ottoai-backend/services/dashboard/app/core/tenant.py`

---

### D.3 Call Ingestion Reliability (< 10 minutes)

**Test Steps**:

1. **Send Test CallRail Webhook**:
   ```bash
   curl -X POST "https://your-railway-url.com/api/v1/callrail/call.completed" \
     -H "Content-Type: application/json" \
     -d '{
       "resource_id": "CAL_test123",
       "customer_phone_number": "+15551234567",
       "tracking_phone_number": "+15559876543",
       "recording": "https://callrail.com/recordings/test.mp3",
       "duration": 180,
       "answered": true
     }'
   ```

2. **Verify Call Record Created**:
   ```sql
   SELECT call_id, phone_number, company_id, recording_url 
   FROM calls 
   WHERE call_id = 1001 
   OR phone_number = '+15551234567';
   ```
   ✅ Call record exists

3. **Verify Shunya Job Created**:
   ```sql
   SELECT id, job_type, job_status, call_id 
   FROM shunya_jobs 
   WHERE call_id = 1001;
   ```
   ✅ Shunya job created with `job_type = 'csr_call'`

4. **Check Idempotency** (send same webhook twice):
   ```bash
   # Send same webhook again
   curl -X POST "https://your-railway-url.com/api/v1/callrail/call.completed" \
     -H "Content-Type: application/json" \
     -d '{...same payload...}'
   ```
   ✅ Should not create duplicate call record

**File Reference**: 
- `ottoai-backend/services/dashboard/app/routes/enhanced_callrail.py:312-340`
- `ottoai-backend/services/dashboard/app/services/idempotency.py`

---

### D.4 Shunya Pipeline Health (< 10 minutes)

**Test Steps**:

1. **Check Shunya Webhook Receipt**:
   ```bash
   # Check Railway logs for Shunya webhook
   railway logs --filter "shunya"
   ```
   ✅ Logs show webhook received

2. **Check Shunya Job Status**:
   ```sql
   SELECT id, job_type, job_status, shunya_job_id, retry_count, error_message 
   FROM shunya_jobs 
   WHERE company_id = 'org_2a1b3c4d5e6f7g8h' 
   ORDER BY created_at DESC 
   LIMIT 10;
   ```
   ✅ Jobs have `job_status = 'succeeded'` (not `'failed'` or `'timeout'`)

3. **Check Idempotency Signals**:
   ```sql
   SELECT id, processed_output_hash, job_status 
   FROM shunya_jobs 
   WHERE processed_output_hash IS NOT NULL;
   ```
   ✅ `processed_output_hash` populated (indicates idempotency working)

4. **Check Error Counters**:
   ```sql
   SELECT COUNT(*) as failed_jobs 
   FROM shunya_jobs 
   WHERE job_status = 'failed' 
   AND created_at > NOW() - INTERVAL '24 hours';
   ```
   ✅ Failed jobs < 5% of total (or acceptable threshold)

5. **Check Polling vs Webhook Race Condition**:
   ```sql
   -- Check for duplicate processing (should not exist)
   SELECT call_id, COUNT(*) as job_count 
   FROM shunya_jobs 
   WHERE call_id IS NOT NULL 
   GROUP BY call_id 
   HAVING COUNT(*) > 1;
   ```
   ✅ No duplicate jobs for same call_id

**File Reference**: 
- `ottoai-backend/services/dashboard/app/routes/shunya_webhook.py:38-268`
- `ottoai-backend/services/dashboard/app/tasks/shunya_job_polling_tasks.py:29-773`
- `ottoai-backend/services/dashboard/app/services/shunya_job_service.py`

---

### D.5 Dispatching Safety (No Double Booking) (< 5 minutes)

**Test Steps**:

1. **Create Two Overlapping Appointments**:
   ```sql
   -- Appointment 1: 2pm-3pm
   INSERT INTO appointments (id, lead_id, scheduled_start, scheduled_end, 
                            status, company_id, assigned_rep_id)
   VALUES ('apt_1', 'lead_1', '2025-01-20 14:00:00', '2025-01-20 15:00:00',
          'scheduled', 'org_2a1b3c4d5e6f7g8h', 'user_rep_1');
   
   -- Appointment 2: 2:30pm-3:30pm (overlaps)
   INSERT INTO appointments (id, lead_id, scheduled_start, scheduled_end,
                            status, company_id)
   VALUES ('apt_2', 'lead_2', '2025-01-20 14:30:00', '2025-01-20 15:30:00',
          'scheduled', 'org_2a1b3c4d5e6f7g8h');
   ```

2. **Try to Assign Overlapping Appointment**:
   ```bash
   curl -X POST "https://your-railway-url.com/api/v1/appointments/apt_2/assign" \
     -H "Authorization: Bearer CSR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "rep_id": "user_rep_1",
       "allow_double_booking": false
     }'
   ```
   ✅ Should return 400 error: "Double-booking conflict"

3. **Verify Double-Booking Check Logic**:
   ```sql
   -- Check for overlapping appointments
   SELECT a1.id as apt1, a2.id as apt2, a1.scheduled_start, a2.scheduled_start
   FROM appointments a1, appointments a2
   WHERE a1.assigned_rep_id = a2.assigned_rep_id
   AND a1.id != a2.id
   AND a1.scheduled_start < a2.scheduled_end
   AND (a1.scheduled_end IS NULL OR a1.scheduled_end > a2.scheduled_start)
   AND a1.company_id = 'org_2a1b3c4d5e6f7g8h';
   ```
   ✅ No overlapping appointments assigned to same rep

**File Reference**: 
- `ottoai-backend/services/dashboard/app/services/appointment_dispatch_service.py:115-139`

---

### D.6 Core Dashboards Not 500'ing (< 5 minutes)

**Test Steps**:

1. **CSR Dashboard**:
   ```bash
   curl -X GET "https://your-railway-url.com/api/v1/metrics/csr/overview/self" \
     -H "Authorization: Bearer CSR_TOKEN"
   ```
   ✅ Returns 200 (not 500)

2. **Sales Rep Dashboard**:
   ```bash
   curl -X GET "https://your-railway-url.com/api/v1/metrics/sales/rep/overview/self" \
     -H "Authorization: Bearer SALES_REP_TOKEN"
   ```
   ✅ Returns 200 (not 500)

3. **Executive Dashboard**:
   ```bash
   curl -X GET "https://your-railway-url.com/api/v1/metrics/exec/csr" \
     -H "Authorization: Bearer MANAGER_TOKEN"
   ```
   ✅ Returns 200 (not 500)

4. **Contact Card Detail**:
   ```bash
   curl -X GET "https://your-railway-url.com/api/v1/contact-cards/<contact_id>" \
     -H "Authorization: Bearer CSR_TOKEN"
   ```
   ✅ Returns 200 (not 500)

**File Reference**: 
- `ottoai-backend/services/dashboard/app/routes/metrics_kpis.py`
- `ottoai-backend/services/dashboard/app/routes/contact_cards.py`

---

### D.7 Observability Checks (< 5 minutes)

**Test Steps**:

1. **Check trace_id Propagation**:
   ```bash
   # Make API call, check logs for trace_id
   curl -X GET "https://your-railway-url.com/api/v1/calls" \
     -H "Authorization: Bearer CSR_TOKEN" \
     -H "X-Request-ID: test-trace-123"
   
   # Check Railway logs
   railway logs --filter "test-trace-123"
   ```
   ✅ Logs contain `trace_id: test-trace-123`

2. **Check Key Metrics Counters**:
   ```sql
   -- Check if metrics tables exist and have data
   SELECT COUNT(*) as call_count FROM calls WHERE company_id = 'org_2a1b3c4d5e6f7g8h';
   SELECT COUNT(*) as lead_count FROM leads WHERE company_id = 'org_2a1b3c4d5e6f7g8h';
   SELECT COUNT(*) as appointment_count FROM appointments WHERE company_id = 'org_2a1b3c4d5e6f7g8h';
   ```
   ✅ Counters exist and have reasonable values

3. **Check Error Logging**:
   ```bash
   # Check Railway logs for errors
   railway logs --filter "ERROR" --tail 50
   ```
   ✅ No critical errors (warnings acceptable)

**File Reference**: 
- `ottoai-backend/services/dashboard/app/obs/logging.py`
- `ottoai-backend/services/dashboard/app/middleware/trace.py`

---

## E) Pilot Blockers

### E.1 Missing Endpoints/Features

**If ContactCard Address Update Endpoint Missing**:
- **File**: `app/routes/contact_cards.py`
- **Fix**: Add `PUT /api/v1/contact-cards/{contact_id}` endpoint
- **Smallest Fix**: Use direct DB update for testing (see B.6)

**If SMS Sending Endpoint Missing**:
- **File**: `app/routes/sms_handler.py`
- **Fix**: Add `POST /api/v1/sms/send` endpoint
- **Smallest Fix**: Use Twilio directly for testing

**If Ask Otto Target Role Not Set**:
- **File**: `app/routes/rag.py:150`
- **Fix**: Ensure `X-Target-Role` header is set based on user role
- **Status**: Should already be implemented per `app/routes/rag.py:143-150`

---

### E.2 Configuration Issues

**If CallRail Webhook Not Receiving**:
- Check Railway URL is accessible
- Verify webhook URL in CallRail matches exactly
- Check Railway logs for 404/500 errors

**If Shunya Webhook Not Receiving**:
- Verify `UWC_HMAC_SECRET` matches Shunya config
- Check webhook URL: `POST /api/v1/shunya/webhook`
- Verify HMAC signature validation

**If Clerk Role Mapping Incorrect**:
- Check `app/middleware/tenant.py:220-259` for role mapping
- Verify Clerk org roles match expected values
- Test JWT token extraction

---

### E.3 Data Issues

**If Shunya Data Missing**:
- **Correct Behavior**: Fields should be `null`/`unknown`, not inferred
- **Check**: `app/services/shunya_integration_service.py` - ensure no inference logic
- **Verify**: `CallAnalysis` fields are only set from Shunya response

**If Appointment Time Not Extracted**:
- **Correct Behavior**: Appointment created with `scheduled_start = null` if Shunya doesn't provide
- **Workaround**: Manually set via API or DB (see B.6)

---

## Summary

This runbook provides step-by-step instructions for:
1. **Manual onboarding** of a single tenant (company, users, webhooks, documents)
2. **Scenario 1 testing** (inbound call → booked → dispatch → sales rep view)
3. **Scenario 2 testing** (inbound call → qualified but unbooked → follow-up)
4. **Pilot readiness** checklist (auth, tenant isolation, ingestion, Shunya health, dispatching, dashboards, observability)
5. **Pilot blockers** identification (missing endpoints, configuration issues, data issues)

**Key Principles**:
- ✅ Shunya is single source of truth (no inference)
- ✅ Role-based scoping enforced (CSR shared, sales rep self-scoped, manager company-wide)
- ✅ No backend code changes required
- ✅ Use existing endpoints and models only

**Estimated Time**: 
- Onboarding: ~30-45 minutes
- Scenario 1: ~20-30 minutes
- Scenario 2: ~20-30 minutes
- Pilot Readiness: ~60 minutes
- **Total**: ~2-3 hours for complete pilot setup and testing


