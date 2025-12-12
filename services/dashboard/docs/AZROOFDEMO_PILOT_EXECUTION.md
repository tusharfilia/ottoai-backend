# AZ Roof Demo Pilot Execution Guide
## Real Production Deployment - End-to-End Pilot

**Backend URL**: `https://ottoai-backend-production.up.railway.app`  
**Clerk Org**: `azroofdemo` (org_id: `org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs`)  
**CallRail Number**: `12028313219` (for inbound calls)  
**Twilio Number**: `15205232772` (for SMS texting)

---

## 1. Tenant Routing Design Confirmation

### 1.1 CallRail Webhook → Company Routing

**Routing Logic**: `find_company_by_tracking_number()` in `app/routes/enhanced_callrail.py:54-85`

**Flow**:
1. CallRail sends webhook with `tracking_number` (or `tracking_phone_number`, `trackingnum`)
2. Backend extracts tracking number from webhook payload
3. Matches against `Company.phone_number` using:
   - **Exact match** first
   - **Normalized comparison** (strips non-digits, handles +1 prefix)
   - **Without + sign** if starts with +
4. Returns `Company` record → uses `company_id` for all subsequent operations

**Critical**: `Company.phone_number` **MUST** match CallRail tracking number exactly (or normalized equivalent).

**File Reference**: `ottoai-backend/services/dashboard/app/routes/enhanced_callrail.py:54-85, 112-115`

### 1.2 Twilio SMS Webhook → Company Routing

**Routing Logic**: `process_inbound_sms()` in `app/routes/sms_handler.py:182-202`

**Flow**:
1. Twilio sends SMS webhook with `To` number (the Twilio number that received SMS)
2. Backend queries: `Company.phone_number = to_number`
3. Returns `Company` record → uses `company_id` for all subsequent operations

**Critical**: For SMS routing, `Company.phone_number` should match the Twilio number that receives SMS.

**File Reference**: `ottoai-backend/services/dashboard/app/routes/sms_handler.py:194-202`

### 1.3 Phone Number Normalization

**Function**: `normalize_phone_number()` in `app/routes/enhanced_callrail.py:30-52`

**Behavior**:
- Removes all non-digit characters
- If 10 digits → prepends `1` (US/Canada)
- If 11 digits starting with `1` → keeps as-is
- Examples:
  - `+1 (202) 831-3219` → `12028313219`
  - `+12028313219` → `12028313219`
  - `12028313219` → `12028313219`

**Implication**: You can store phone numbers in various formats, but matching is normalized.

### 1.4 Current Design Limitation

**Issue**: Both CallRail (calls) and Twilio (SMS) use `Company.phone_number` for routing.

**For Your Pilot**:
- **CallRail number** (`12028313219`) → Should be in `Company.phone_number`
- **Twilio number** (`15205232772`) → Currently also needs to match `Company.phone_number` for SMS routing

**Workaround Options**:
1. **Option A**: Use same number for both (if CallRail and Twilio share a number)
2. **Option B**: Store CallRail number in `phone_number`, Twilio in `primary_tracking_number` (but SMS routing won't work without code change)
3. **Option C**: Use CallRail number for both, configure Twilio to forward SMS to CallRail number

**Recommendation**: Check if your Twilio number can receive calls routed to CallRail, or if you need separate numbers. For pilot, use CallRail number (`12028313219`) in `Company.phone_number` and ensure Twilio SMS webhooks route to the same number.

---

## 2. Manual Onboarding Steps

### 2.1 Verify Company Record Exists

**Check if company already exists**:

```bash
# Get manager JWT token from Clerk dashboard
# Then query company
curl -X GET "https://ottoai-backend-production.up.railway.app/api/v1/company/org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs" \
  -H "Authorization: Bearer YOUR_MANAGER_JWT_TOKEN"
```

**If company doesn't exist**, create it:

```bash
curl -X POST "https://ottoai-backend-production.up.railway.app/api/v1/company/?name=AZ%20Roof%20Demo&phone_number=%2B12028313219&address=123%20Main%20St" \
  -H "Authorization: Bearer YOUR_MANAGER_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response**:
```json
{
  "status": "success",
  "company_id": "org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs",
  "clerk_org_id": "org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs"
}
```

**File Reference**: `ottoai-backend/services/dashboard/app/routes/company.py:224-305`

---

### 2.2 Update Company Phone Number (Critical)

**Ensure `phone_number` matches CallRail tracking number**:

```bash
# Option 1: Via PUT endpoint (if exists)
curl -X PUT "https://ottoai-backend-production.up.railway.app/api/v1/company/org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs?phone_number=%2B12028313219" \
  -H "Authorization: Bearer YOUR_MANAGER_JWT_TOKEN"

# Option 2: Direct DB update (if API doesn't exist)
# Connect to Railway Postgres and run:
# UPDATE companies SET phone_number = '+12028313219' WHERE id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
```

**Verify**:
```sql
SELECT id, name, phone_number, primary_tracking_number 
FROM companies 
WHERE id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
```

**Expected**: `phone_number = '+12028313219'` or `'12028313219'`

**File Reference**: `ottoai-backend/services/dashboard/app/routes/company.py:439-443`

---

### 2.3 Configure CallRail Integration (Optional - if using CallRail API)

**If you want to use CallRail API features** (not required for webhooks):

```bash
curl -X POST "https://ottoai-backend-production.up.railway.app/api/v1/company/set-callrail-api-key/org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs?api_key=YOUR_CALLRAIL_API_KEY" \
  -H "Authorization: Bearer YOUR_MANAGER_JWT_TOKEN"

curl -X POST "https://ottoai-backend-production.up.railway.app/api/v1/company/set-callrail-account-id/org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs?account_id=YOUR_CALLRAIL_ACCOUNT_ID" \
  -H "Authorization: Bearer YOUR_MANAGER_JWT_TOKEN"
```

**File Reference**: `ottoai-backend/services/dashboard/app/routes/company.py:650-727`

---

### 2.4 Verify Users Exist in Otto DB

**Check if users are linked**:

```bash
# Get list of users for company
curl -X GET "https://ottoai-backend-production.up.railway.app/api/v1/users" \
  -H "Authorization: Bearer YOUR_MANAGER_JWT_TOKEN"
```

**If users don't exist in Otto DB**, they may need to be created via Clerk webhook or manually. Users should already exist since you mentioned they're created in Clerk.

**File Reference**: `ottoai-backend/services/dashboard/app/routes/user.py:101-189`

---

### 2.5 Configure CallRail Webhooks

**In CallRail Dashboard**:

1. Go to **Settings** → **Integrations** → **Webhooks**
2. Add webhook URLs:
   - **Call Incoming**: `https://ottoai-backend-production.up.railway.app/api/v1/callrail/call.incoming`
   - **Call Answered**: `https://ottoai-backend-production.up.railway.app/api/v1/callrail/call.answered`
   - **Call Missed**: `https://ottoai-backend-production.up.railway.app/api/v1/callrail/call.missed`
   - **Call Completed**: `https://ottoai-backend-production.up.railway.app/api/v1/callrail/call.completed`
   - **SMS Events**: `https://ottoai-backend-production.up.railway.app/sms/callrail-webhook`

3. **Link tracking number** (`12028313219`) to your CallRail account

**Test webhook receipt**:
```bash
# Make a test call to 12028313219
# Check Railway logs:
railway logs --filter "callrail" --tail 50
```

**Expected**: Log shows "CallRail call.incoming webhook: {...}"

**File Reference**: `ottoai-backend/services/dashboard/app/routes/enhanced_callrail.py:87-340`

---

### 2.6 Configure Twilio SMS Webhooks

**In Twilio Dashboard**:

1. Go to **Phone Numbers** → **Manage** → **Active Numbers**
2. Click on your number (`15205232772`)
3. Set **SMS webhook URL**: `https://ottoai-backend-production.up.railway.app/sms/twilio-webhook`
4. HTTP Method: `POST`
5. Save

**Test SMS webhook**:
```bash
# Send test SMS to 15205232772
# Check Railway logs:
railway logs --filter "twilio" --tail 50
```

**Expected**: Log shows "Twilio SMS webhook received from +1..."

**File Reference**: `ottoai-backend/services/dashboard/app/routes/sms_handler.py:115-180`

**Note**: If Twilio SMS routing doesn't work because `Company.phone_number` is set to CallRail number, you may need to:
- Use same number for both CallRail and Twilio, OR
- Store Twilio number in a separate field and update SMS routing logic (requires code change - not recommended for pilot)

---

### 2.7 Document Ingestion (Optional - for Ask Otto)

**Note**: This endpoint uploads documents to Otto's S3, then Otto calls **Shunya's ingestion API** (`POST /api/v1/ingestion/documents/upload`). Shunya is the one that actually ingests and processes documents for use in Ask Otto, analysis, etc.

**Flow**:
1. Otto receives file upload → stores in S3
2. Otto creates Document record in DB
3. Otto triggers Celery task → calls Shunya's ingestion API
4. Shunya processes document → uses for Ask Otto, analysis, etc.

**Upload SOP documents**:

```bash
# Upload CSR SOP
curl -X POST "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/documents/upload" \
  -H "Authorization: Bearer YOUR_MANAGER_JWT_TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/csr_sop.pdf" \
  -F "category=sop" \
  -F "role_target=csr" \
  -F "metadata={\"document_type\":\"sop\",\"target_role\":\"customer_rep\"}"

# Upload Sales Rep SOP
curl -X POST "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/documents/upload" \
  -H "Authorization: Bearer YOUR_MANAGER_JWT_TOKEN" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/sales_sop.pdf" \
  -F "category=sop" \
  -F "role_target=sales_rep" \
  -F "metadata={\"document_type\":\"sop\",\"target_role\":\"sales_rep\"}"
```

**Verify ingestion status**:
```bash
curl -X GET "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/documents/status/{document_id}" \
  -H "Authorization: Bearer YOUR_MANAGER_JWT_TOKEN"
```

**File References**: 
- `ottoai-backend/services/dashboard/app/routes/onboarding/onboarding_routes.py:249-309` (Otto endpoint)
- `ottoai-backend/services/dashboard/app/tasks/onboarding_tasks.py:17-122` (Calls Shunya API)
- `ottoai-backend/services/dashboard/app/services/uwc_client.py:1001-1044` (Shunya API client - `POST /api/v1/ingestion/documents/upload`)

---

## 3. Reusing Existing CallRail + Twilio Setup

### 3.1 CallRail Setup Reuse

**Current Design**: CallRail webhooks route by `tracking_number` → `Company.phone_number` match.

**For Multi-Tenant**:
- ✅ **Supported**: Each company can have different tracking numbers
- ✅ **Webhook routing**: Automatic via phone number matching
- ⚠️ **Limitation**: If multiple companies share same tracking number, first match wins (shouldn't happen in production)

**Your Pilot**:
- Use existing CallRail account
- Configure webhook URLs (same for all tenants - routing is automatic)
- Link tracking number `12028313219` to your CallRail account
- Ensure `Company.phone_number = '+12028313219'` for this tenant

**No per-tenant CallRail configuration needed** - webhook routing handles it.

---

### 3.2 Twilio Setup Reuse

**Current Design**: Twilio SMS webhooks route by `To` number → `Company.phone_number` match.

**For Multi-Tenant**:
- ⚠️ **Limitation**: Each company needs unique Twilio number OR shared number with routing logic
- ⚠️ **Current Implementation**: Simple `Company.phone_number = to_number` match

**Your Pilot Options**:

**Option A: Use Same Number for Both** (Recommended)
- Use `12028313219` for both CallRail calls and Twilio SMS
- Set `Company.phone_number = '+12028313219'`
- Configure Twilio to use same number (if possible)

**Option B: Separate Numbers** (Requires Code Change)
- CallRail: `12028313219` → `Company.phone_number`
- Twilio: `15205232772` → Would need separate field or routing logic
- **Not supported without code change**

**Option C: Use CallRail Number for SMS Routing**
- Set `Company.phone_number = '+12028313219'`
- Configure Twilio to forward SMS to CallRail number
- **May not work if Twilio and CallRail are separate**

**Recommendation**: For pilot, use Option A if possible. If not, test SMS separately and note the limitation.

---

## 4. Pilot Execution Checklist

### 4.1 Pre-Flight Checks

- [ ] Company record exists: `org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs`
- [ ] `Company.phone_number = '+12028313219'` (matches CallRail tracking number)
- [ ] CallRail webhooks configured and pointing to Railway backend
- [ ] Twilio SMS webhook configured (if using separate number, note limitation)
- [ ] Users exist in Otto DB (csr, sales_rep, manager)
- [ ] Test webhook receipt (make test call, check logs)

---

### 4.2 Scenario 1: Inbound Call → Booked Immediately

#### 4.2.1 Execute Call

1. **Make call** to `12028313219` (CallRail tracking number)
2. **Answer call** and have conversation that results in booking
3. **End call** (CallRail sends `call.completed` webhook)

#### 4.2.2 Verification Checklist

**Immediate (within 30 seconds)**:

- [ ] **CallRail webhook received**:
  ```bash
  railway logs --filter "callrail" --tail 20
  ```
  ✅ Should see: "CallRail call.completed webhook: {...}"

- [ ] **Call record created**:
  ```sql
  SELECT call_id, phone_number, company_id, recording_url, duration, created_at 
  FROM calls 
  WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs' 
  ORDER BY created_at DESC 
  LIMIT 1;
  ```
  ✅ `call_id` exists, `phone_number` matches caller, `company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs'`

- [ ] **ContactCard created**:
  ```sql
  SELECT id, primary_phone, company_id 
  FROM contact_cards 
  WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs' 
  AND primary_phone = '<caller_phone>';
  ```
  ✅ ContactCard exists

- [ ] **Lead created**:
  ```sql
  SELECT id, contact_card_id, status, company_id 
  FROM leads 
  WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs' 
  ORDER BY created_at DESC 
  LIMIT 1;
  ```
  ✅ Lead exists

**Within 2-5 minutes** (Shunya processing):

- [ ] **Shunya job created**:
  ```sql
  SELECT id, job_type, job_status, shunya_job_id, call_id 
  FROM shunya_jobs 
  WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs' 
  AND call_id = <call_id_from_above>
  ORDER BY created_at DESC 
  LIMIT 1;
  ```
  ✅ Job exists with `job_type = 'csr_call'`

- [ ] **Shunya job completed**:
  ```sql
  SELECT job_status, processed_output_hash 
  FROM shunya_jobs 
  WHERE id = <job_id_from_above>;
  ```
  ✅ `job_status = 'succeeded'` (may take 2-5 minutes)

- [ ] **Call transcript created**:
  ```sql
  SELECT call_id, transcript_text 
  FROM call_transcripts 
  WHERE call_id = <call_id_from_above>;
  ```
  ✅ `transcript_text` populated

- [ ] **Call analysis created**:
  ```sql
  SELECT call_id, booking_status, lead_quality, call_outcome_category, 
         objections, sop_compliance_score 
  FROM call_analyses 
  WHERE call_id = <call_id_from_above>;
  ```
  ✅ `booking_status = 'booked'` (from Shunya, not inferred)
  ✅ `lead_quality` populated (hot/warm/cold from Shunya)
  ✅ `call_outcome_category` populated (from Shunya)

- [ ] **Lead status updated**:
  ```sql
  SELECT id, status, last_qualified_at 
  FROM leads 
  WHERE id = <lead_id_from_above>;
  ```
  ✅ `status = 'qualified_booked'` (updated from Shunya analysis)

- [ ] **Appointment created**:
  ```sql
  SELECT id, lead_id, scheduled_start, scheduled_end, status, location_address 
  FROM appointments 
  WHERE lead_id = <lead_id_from_above> 
  AND company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
  ```
  ✅ Appointment exists
  ✅ `scheduled_start` populated (if Shunya extracted time)
  ✅ `status = 'scheduled'` or `'confirmed'`

**Via API**:

- [ ] **Get call details**:
  ```bash
  curl -X GET "https://ottoai-backend-production.up.railway.app/api/v1/calls/<call_id>" \
    -H "Authorization: Bearer CSR_TOKEN"
  ```
  ✅ Returns call with analysis

- [ ] **Get call analysis**:
  ```bash
  curl -X GET "https://ottoai-backend-production.up.railway.app/api/v1/calls/<call_id>/analysis" \
    -H "Authorization: Bearer CSR_TOKEN"
  ```
  ✅ Returns analysis with `booking_status = 'booked'`

- [ ] **Get appointments**:
  ```bash
  curl -X GET "https://ottoai-backend-production.up.railway.app/api/v1/appointments?lead_id=<lead_id>" \
    -H "Authorization: Bearer CSR_TOKEN"
  ```
  ✅ Returns appointment list

**Frontend**:

- [ ] CSR Dashboard shows call with booking status
- [ ] Contact Card shows appointment
- [ ] Sales Rep can see appointment in "Today's Appointments"

---

### 4.3 Scenario 2: Inbound Call → Qualified But Not Booked

#### 4.3.1 Execute Call

1. **Make call** to `12028313219`
2. **Answer call** and have conversation that qualifies but doesn't book
3. **End call**

#### 4.3.2 Verification Checklist

**Immediate (within 30 seconds)**:

- [ ] CallRail webhook received
- [ ] Call record created
- [ ] ContactCard created
- [ ] Lead created

**Within 2-5 minutes** (Shunya processing):

- [ ] **Call analysis created**:
  ```sql
  SELECT call_id, booking_status, call_outcome_category, lead_quality 
  FROM call_analyses 
  WHERE call_id = <call_id>;
  ```
  ✅ `booking_status = 'not_booked'` (from Shunya)
  ✅ `call_outcome_category = 'qualified_but_unbooked'` (from Shunya)
  ✅ `lead_quality = 'hot'` or `'warm'` or `'cold'` (from Shunya)

- [ ] **Lead status updated**:
  ```sql
  SELECT id, status 
  FROM leads 
  WHERE id = <lead_id>;
  ```
  ✅ `status = 'qualified_unbooked'` or `'warm'` or `'hot'`

- [ ] **Tasks created** (if Shunya returns pending actions):
  ```sql
  SELECT id, description, assigned_to, source, status 
  FROM tasks 
  WHERE contact_card_id = <contact_card_id> 
  AND company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
  ```
  ✅ Tasks exist with `source = 'shunya'` (if Shunya provided pending actions)

**Via API**:

- [ ] **Get CSR metrics**:
  ```bash
  curl -X GET "https://ottoai-backend-production.up.railway.app/api/v1/metrics/csr/overview/self" \
    -H "Authorization: Bearer CSR_TOKEN"
  ```
  ✅ Returns `qualified_but_unbooked_calls: 1`

- [ ] **Get pending leads**:
  ```bash
  curl -X GET "https://ottoai-backend-production.up.railway.app/api/v1/leads?status=qualified_unbooked,warm,hot" \
    -H "Authorization: Bearer CSR_TOKEN"
  ```
  ✅ Returns lead in list

**Follow-Up Action (SMS)**:

- [ ] **Send SMS** via Twilio to customer
- [ ] **Verify SMS webhook received**:
  ```bash
  railway logs --filter "twilio" --tail 20
  ```
  ✅ Log shows SMS received

- [ ] **Verify SMS linked to contact**:
  ```sql
  -- Check if SMS thread exists (if SMS model exists)
  -- Or check contact_card for SMS history
  ```

**Frontend**:

- [ ] CSR Dashboard shows qualified but unbooked lead
- [ ] Contact Card shows follow-up tasks
- [ ] SMS thread visible in Contact Card

---

## 5. Troubleshooting

### 5.1 "No company found for tracking number"

**Symptom**: Webhook logs show "No company found for tracking number"

**Fix**:
1. Verify `Company.phone_number` matches tracking number:
   ```sql
   SELECT id, phone_number FROM companies WHERE id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
   ```
2. Try different formats: `+12028313219`, `12028313219`, `+1-202-831-3219`
3. Check normalization: `12028313219` should normalize to `12028313219`

### 5.2 Shunya Job Not Completing

**Symptom**: `shunya_jobs.job_status = 'pending'` or `'running'` for > 5 minutes

**Check**:
1. Shunya webhook configured: `POST /api/v1/shunya/webhook`
2. HMAC secret matches
3. Check Shunya job logs:
   ```sql
   SELECT id, job_status, error_message, retry_count 
   FROM shunya_jobs 
   WHERE call_id = <call_id>;
   ```

### 5.3 Appointment Not Created

**Symptom**: Call analysis shows `booking_status = 'booked'` but no appointment

**Check**:
1. Verify Shunya returned appointment time in `entities`:
   ```sql
   SELECT entities FROM call_analyses WHERE call_id = <call_id>;
   ```
2. Check appointment creation logic logs
3. Manually create appointment if needed (for testing)

### 5.4 SMS Not Routing to Company

**Symptom**: SMS webhook received but "No company found for tracking number"

**Fix**:
1. Verify `Company.phone_number` matches Twilio `To` number
2. If using separate Twilio number, note limitation (requires code change)
3. Use same number for both CallRail and Twilio if possible

---

## 6. Success Criteria Summary

### Scenario 1 (Booked Call):
- ✅ Call ingested → Call record created
- ✅ Shunya processed → Analysis with `booking_status = 'booked'`
- ✅ Appointment created → Sales rep can see in "Today's Appointments"
- ✅ All data from Shunya (no inference)

### Scenario 2 (Qualified Unbooked):
- ✅ Call ingested → Call record created
- ✅ Shunya processed → Analysis with `booking_status = 'not_booked'`, `call_outcome_category = 'qualified_but_unbooked'`
- ✅ Lead in CSR shared pool → Visible in pending leads
- ✅ Tasks created (if Shunya provided pending actions)
- ✅ SMS follow-up captured → Visible in contact card

### Overall:
- ✅ Tenant isolation: Only `org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs` data visible
- ✅ Role scoping: CSR sees shared leads, sales rep sees own appointments
- ✅ Shunya source of truth: All semantics from Shunya, no inference

---

## 7. Quick Reference

**Backend URL**: `https://ottoai-backend-production.up.railway.app`  
**Company ID**: `org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs`  
**CallRail Number**: `+12028313219`  
**Twilio Number**: `+15205232772`  

**Key Endpoints**:
- CallRail webhooks: `/api/v1/callrail/*`
- Twilio SMS: `/sms/twilio-webhook`
- Company: `/api/v1/company/{company_id}`
- Calls: `/api/v1/calls/{call_id}`
- Appointments: `/api/v1/appointments`
- Metrics: `/api/v1/metrics/*`

**DB Tables to Monitor**:
- `calls` - Call records
- `call_analyses` - Shunya analysis results
- `contact_cards` - Customer contacts
- `leads` - Sales leads
- `appointments` - Scheduled appointments
- `shunya_jobs` - Shunya processing jobs
- `tasks` - Follow-up tasks

---

**Ready to execute!** Start with Section 2 (Manual Onboarding), then proceed to Section 4 (Pilot Execution Checklist).

