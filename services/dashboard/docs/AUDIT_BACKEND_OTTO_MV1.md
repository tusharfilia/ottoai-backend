# Backend Audit: OTTO MV1 Source of Truth Compliance

**Audit Date**: 2025-01-XX  
**Source of Truth**: `docs/OTTO_MV1_SOURCE_OF_TRUTH.md`  
**Scope**: Models, Routes, RBAC, Idempotency, Metrics

---

## Section 1: Models vs Spec

### 1.1 ContactCard

| Spec Field | Actual Field | Status | Notes |
|------------|--------------|--------|-------|
| `id` (UUID) | `id` (String, UUID) | ✅ OK | Matches |
| `company_id` | `company_id` | ✅ OK | Matches |
| `primary_phone` | `primary_phone` | ✅ OK | Matches |
| `secondary_phones[]` | `secondary_phone` (single) | ⚠️ MISMATCH | Spec wants array, model has single string |
| `email` | `email` | ✅ OK | Matches |
| `first_name`, `last_name` | `first_name`, `last_name` | ✅ OK | Matches |
| `full_name` (denormalized) | `full_name()` method | ✅ OK | Computed method, acceptable |
| `address_line_1`, `address_line_2` | `address` (single) | ⚠️ MISMATCH | Spec wants split, model has single field |
| `city`, `state`, `zip`, `country` | `city`, `state`, `postal_code` | ⚠️ PARTIAL | Missing `country` field |
| `source` enum | Not in model | ❌ MISSING | Should be `{callrail, manual, auto_ai, import, otto, shunya}` |
| Property intel fields | `property_snapshot` (JSON) | ✅ OK | Stored as JSON, acceptable |
| `last_call_summary` | Not in model | ❌ MISSING | AI summary field |
| `primary_intent` | Not in model | ❌ MISSING | AI summary field |
| `risks[]` | Not in model | ❌ MISSING | Deal risk signals |
| `tags[]` | In `custom_metadata` | ⚠️ PARTIAL | Stored in metadata, not direct field |

**Universal ContactCard Rule Compliance**: ✅ **COMPLIANT**
- All calls, leads, appointments reference `contact_card_id`
- No separate customer_id/lead_id confusion

---

### 1.2 Lead

| Spec Field | Actual Field | Status | Notes |
|------------|--------------|--------|-------|
| `id` | `id` (String, UUID) | ✅ OK | Matches |
| `company_id` | `company_id` | ✅ OK | Matches |
| `contact_card_id` | `contact_card_id` | ✅ OK | Matches |
| `stage ∈ {new, qualified, booked, pending, dead}` | `status` (LeadStatus enum) | ⚠️ MISMATCH | Enum values differ: `{new, warm, hot, qualified_booked, qualified_unbooked, nurturing, dormant, abandoned, closed_won, closed_lost}` |
| `qualification_status ∈ {hot, warm, cold, unqualified}` | Not direct field | ⚠️ PARTIAL | Stored in `CallAnalysis.lead_quality`, not on Lead model |
| `source` | `source` (LeadSource enum) | ✅ OK | Matches concept |
| `last_activity_at` | `last_contacted_at` | ⚠️ MISMATCH | Similar but not exact match |

**Issues**:
- Spec wants `qualification_status` on Lead, but it's in CallAnalysis
- Stage enum values don't align exactly

---

### 1.3 Call

| Spec Field | Actual Field | Status | Notes |
|------------|--------------|--------|-------|
| `id` | `call_id` (Integer) | ⚠️ MISMATCH | Spec wants `id`, model uses `call_id` |
| `company_id` | `company_id` | ✅ OK | Matches |
| `contact_card_id` | `contact_card_id` | ✅ OK | Matches |
| `csr_id` | Not in model | ❌ MISSING | Spec requires nullable `csr_id` |
| `assigned_rep_id` | `assigned_rep_id` | ✅ OK | Matches |
| `direction ∈ {inbound, outbound}` | Not in model | ❌ MISSING | Spec requires direction enum |
| `call_type ∈ {csr_call, sales_call, visit_call}` | Not in model | ❌ MISSING | Spec requires call_type enum |
| `callrail_call_id` / `twilio_sid` | `bland_call_id`, `call_sid` | ⚠️ PARTIAL | Has some IDs but naming differs |
| `audio_url` | Not in model | ❌ MISSING | Spec requires audio_url |
| `started_at`, `ended_at` | `created_at`, `last_call_timestamp` | ⚠️ MISMATCH | Has timestamps but not exact field names |
| `duration_seconds` | `last_call_duration` | ⚠️ MISMATCH | Similar but naming differs |
| `booking_status ∈ {booked, not_booked, service_not_offered}` | `booked` (Boolean) | ⚠️ MISMATCH | Spec wants enum, model has boolean |

**Critical Issues**:
- Missing `csr_id` field (required for CSR metrics)
- Missing `call_type` enum (required for filtering CSR calls)
- Missing `direction` enum (required for inbound/outbound distinction)
- `booking_status` should be enum, not boolean

---

### 1.4 CallTranscript

| Spec Field | Actual Field | Status | Notes |
|------------|--------------|--------|-------|
| `id` | `id` (String, UUID) | ✅ OK | Matches |
| `company_id` | `tenant_id` | ⚠️ MISMATCH | Field name differs (tenant_id vs company_id) |
| `call_id` | `call_id` | ✅ OK | Matches |
| `transcript_text` | `transcript_text` | ✅ OK | Matches |
| `speaker_labels` | `speaker_labels` (JSON) | ✅ OK | Matches |
| `confidence_score` | `confidence_score` | ✅ OK | Matches |
| `uwc_task_id` / `uwc_transcript_id` | `uwc_job_id` | ✅ OK | Matches concept |

**Issues**:
- Uses `tenant_id` instead of `company_id` (naming inconsistency)

---

### 1.5 CallAnalysis

| Spec Field | Actual Field | Status | Notes |
|------------|--------------|--------|-------|
| `id` | `id` (String, UUID) | ✅ OK | Matches |
| `company_id` | `tenant_id` | ⚠️ MISMATCH | Field name differs |
| `call_id` | `call_id` | ✅ OK | Matches |
| `qualification_status` | `lead_quality` (String) | ⚠️ MISMATCH | Field name differs, values should be enum |
| `sentiment_score` | `sentiment_score` | ✅ OK | Matches |
| `objections[]` | `objections` (JSON) | ✅ OK | Matches |
| `objection_severity` | Not in model | ❌ MISSING | Spec requires severity field |
| `sop_compliance_score` | `sop_compliance_score` | ✅ OK | Matches |
| `sop_stages_completed[]` | `sop_stages_completed` (JSON) | ✅ OK | Matches |
| `pending_actions[]` | Not in model | ❌ MISSING | Spec requires pending_actions array |
| `summary` | Not in model | ❌ MISSING | Spec requires summary field |
| `missed_opportunities[]` | Not in model | ❌ MISSING | Spec requires missed_opportunities array |

**Issues**:
- Uses `tenant_id` instead of `company_id`
- Missing several spec fields (pending_actions, summary, missed_opportunities, objection_severity)

---

### 1.6 Appointment

| Spec Field | Actual Field | Status | Notes |
|------------|--------------|--------|-------|
| `id` | `id` (String, UUID) | ✅ OK | Matches |
| `company_id` | `company_id` | ✅ OK | Matches |
| `contact_card_id` | `contact_card_id` | ✅ OK | Matches |
| `sales_rep_id` | `assigned_rep_id` | ⚠️ MISMATCH | Field name differs |
| `csr_id` | Not in model | ❌ MISSING | Spec requires `csr_id` (who booked it) |
| `service_type` | `service_type` | ✅ OK | Matches |
| `scheduled_start_at`, `scheduled_end_at` | `scheduled_start`, `scheduled_end` | ⚠️ MISMATCH | Field names differ slightly |
| `status ∈ {scheduled, completed, no_show, cancelled}` | `status` (AppointmentStatus enum) | ✅ OK | Matches |
| `outcome ∈ {closed_won, closed_lost, open}` | `outcome` (AppointmentOutcome enum) | ⚠️ MISMATCH | Enum has `{pending, won, lost, no_show, rescheduled}` - doesn't match spec |
| `deal_value` | `deal_size` | ⚠️ MISMATCH | Field name differs |
| `source_call_id` | Not in model | ❌ MISSING | Spec requires link to originating call |

**Critical Issues**:
- Missing `csr_id` field (required for CSR metrics)
- Missing `source_call_id` (required to track which call generated appointment)
- `outcome` enum values don't match spec

---

### 1.7 RecordingSession

| Spec Field | Actual Field | Status | Notes |
|------------|--------------|--------|-------|
| `id` | `id` (String, UUID) | ✅ OK | Matches |
| `company_id` | `company_id` | ✅ OK | Matches |
| `appointment_id` | `appointment_id` | ✅ OK | Matches |
| `sales_rep_id` | `rep_id` | ⚠️ MISMATCH | Field name differs |
| `audio_url` | `audio_url` | ✅ OK | Matches |
| `started_at`, `ended_at` | `started_at`, `ended_at` | ✅ OK | Matches |
| `duration_seconds` | `audio_duration_seconds` | ⚠️ MISMATCH | Field name differs |
| Shunya IDs | `shunya_asr_job_id`, `shunya_analysis_job_id` | ✅ OK | Matches |

**Issues**:
- Field naming inconsistencies (`rep_id` vs `sales_rep_id`, `audio_duration_seconds` vs `duration_seconds`)

---

### 1.8 PendingAction

| Spec Field | Actual Field | Status | Notes |
|------------|--------------|--------|-------|
| Model exists? | ❌ **NO MODEL** | ❌ MISSING | Spec requires `pending_action` model, but only `Task` exists |
| `id` | N/A | ❌ MISSING | No model |
| `company_id` | N/A | ❌ MISSING | No model |
| `contact_card_id` | N/A | ❌ MISSING | No model |
| `linked_call_id` / `appointment_id` | N/A | ❌ MISSING | No model |
| `assigned_to_type ∈ {csr, sales_rep, exec, system}` | N/A | ❌ MISSING | No model |
| `assigned_to_user_id` | N/A | ❌ MISSING | No model |
| `category` | N/A | ❌ MISSING | No model |
| `raw_text` | N/A | ❌ MISSING | No model |
| `due_at` | N/A | ❌ MISSING | No model |
| `status ∈ {open, in_progress, completed, cancelled}` | N/A | ❌ MISSING | No model |

**Critical Issue**: 
- **No `pending_action` model exists**. Only `Task` model exists, which may be a wrapper but doesn't match spec structure.

---

### 1.9 Task

| Spec Field | Actual Field | Status | Notes |
|------------|--------------|--------|-------|
| Spec says | "Similar shape to pending_action but UI-friendly; may be a thin wrapper" | ⚠️ UNCLEAR | Task exists but relationship to pending_action not defined |
| `id` | `id` (String, UUID) | ✅ OK | Has ID |
| `company_id` | `company_id` | ✅ OK | Matches |
| `contact_card_id` | `contact_card_id` | ✅ OK | Matches |
| `linked_call_id` / `appointment_id` | `call_id`, `appointment_id` | ✅ OK | Matches |
| `assigned_to_type` | `assigned_to` (TaskAssignee enum) | ⚠️ PARTIAL | Has enum but values: `{csr, rep, manager, ai}` vs spec `{csr, sales_rep, exec, system}` |
| `assigned_to_user_id` | Not in model | ❌ MISSING | Spec requires user_id for CSR/rep owners |
| `category` | Not in model | ❌ MISSING | Spec requires category field |
| `raw_text` | `description` | ⚠️ PARTIAL | Has description but spec wants raw_text (original Shunya text) |
| `due_at` | `due_at` | ✅ OK | Matches |
| `status` | `status` (TaskStatus enum) | ⚠️ MISMATCH | Enum has `{open, completed, overdue, cancelled}` vs spec `{open, in_progress, completed, cancelled}` |

**Issues**:
- Missing `assigned_to_user_id` (can't assign to specific CSR/rep)
- Missing `category` field
- Status enum missing `in_progress`
- `assigned_to_type` enum values don't match spec

---

## Section 2: Routes vs Spec

### 2.1 CSR Dashboard Endpoints

| Spec Endpoint | Actual Endpoint | Status | Notes |
|---------------|-----------------|--------|-------|
| `/api/v1/dashboard/csr-metrics` | `/api/v1/dashboard/metrics` | ⚠️ MISMATCH | Path differs, may not have CSR-specific scoping |
| `/api/v1/dashboard/booking-rate` | `/api/v1/dashboard/booking-rate` | ✅ OK | Exists and matches |
| `/api/v1/dashboard/top-objections` | `/api/v1/dashboard/top-objections` | ✅ OK | Exists and matches |
| `/api/v1/missed-calls/queue/metrics` | `/api/v1/missed-calls/queue/metrics` | ✅ OK | Exists and matches |
| `/api/v1/missed-calls/queue/entries` | `/api/v1/missed-calls/queue/entries` | ✅ OK | Exists and matches |
| Unbooked appointments list | Not found | ❌ MISSING | Spec requires endpoint for unbooked appointments list |

**Issues**:
- CSR metrics endpoint path may not match spec
- Missing unbooked appointments list endpoint

---

### 2.2 Exec Dashboard Endpoints

| Spec Endpoint | Actual Endpoint | Status | Notes |
|---------------|-----------------|--------|-------|
| `/api/v1/dashboard/exec-csr-metrics` | Not found | ❌ MISSING | Spec requires Exec → CSR tab metrics |
| `/api/v1/dashboard/exec-sales-metrics` | Not found | ❌ MISSING | Spec requires Exec → Sales tab metrics |
| `/api/v1/dashboard/metrics` | `/api/v1/dashboard/metrics` | ⚠️ PARTIAL | Exists but may not have Exec-specific aggregations |

**Critical Issues**:
- Missing Exec-specific CSR metrics endpoint (aggregated over all CSRs)
- Missing Exec-specific Sales metrics endpoint (per rep win rates, process grades, etc.)

---

### 2.3 Sales Rep Mobile App Endpoints

| Spec Endpoint | Actual Endpoint | Status | Notes |
|---------------|-----------------|--------|-------|
| `/api/v1/reps/{rep_id}/appointments?date=YYYY-MM-DD` | `/api/v1/sales-rep/{rep_id}/appointments` | ⚠️ MISMATCH | Path differs (`sales-rep` vs `reps`), may not support date query |
| `/api/v1/appointments/{id}` | `/api/v1/appointments/{appointment_id}` | ✅ OK | Exists, should check if it includes contact card + AI insights |
| `/api/v1/recording-sessions` (POST start) | `/api/v1/recording-sessions/start` | ✅ OK | Exists |
| `/api/v1/recording-sessions` (POST stop+upload) | `/api/v1/recording-sessions/{session_id}/stop` | ✅ OK | Exists |
| `/api/v1/recording-sessions` (GET by appointment) | `/api/v1/recording-sessions/{session_id}` | ⚠️ PARTIAL | Exists but may not support query by appointment_id |
| `/api/v1/reps/{rep_id}/stats` | Not found | ❌ MISSING | Spec requires rep stats endpoint |

**Issues**:
- Sales rep appointments endpoint path differs
- Missing rep stats endpoint

---

### 2.4 Ask Otto (RAG) Endpoint

| Spec Endpoint | Actual Endpoint | Status | Notes |
|---------------|-----------------|--------|-------|
| `/api/v1/ask-otto` | `/api/v1/rag/query` | ⚠️ MISMATCH | Path differs |
| Input: `question`, `scope`, optional `call_id`, `contact_card_id`, `appointment_id` | `RAGQueryRequest` | ⚠️ PARTIAL | Need to verify if scope parameter exists |
| CSR scope: only self | Implemented in code | ✅ OK | Code checks `user_role == "sales_rep"` for scoping |
| Exec scope: company-wide | Implemented in code | ✅ OK | Code allows company-wide for exec/manager |

**Issues**:
- Endpoint path doesn't match spec (`/rag/query` vs `/ask-otto`)
- Need to verify `scope` parameter exists in request model

---

## Section 3: RBAC & Tenancy

### 3.1 Tenant Context Middleware

**Status**: ✅ **COMPLIANT**
- `TenantContextMiddleware` extracts `company_id`, `user_id`, `role` from JWT
- Attaches to `request.state.tenant_id`, `request.state.user_id`, `request.state.user_role`
- Implementation in `app/middleware/tenant.py`

### 3.2 RBAC Enforcement

**Status**: ⚠️ **PARTIAL COMPLIANCE**

**Issues Found**:
1. **Role Enum Mismatch**: 
   - Spec: `{csr, manager, exec, sales_rep, admin}`
   - Code: Uses `{csr, manager, exec, sales_rep}` but also has aliases (`admin` → `manager`, `rep` → `sales_rep`)
   - **Issue**: `exec` role may not be properly distinguished from `manager`

2. **CSR Scoping**:
   - Spec: CSR should only see their own calls/leads/appointments
   - **Gap**: Need to verify all CSR endpoints filter by `csr_id = user_id`
   - **Example**: `/api/v1/dashboard/booking-rate` uses `tenant_id` but may not filter by CSR

3. **Sales Rep Scoping**:
   - Spec: Sales rep should only see their own appointments/recordings
   - **Status**: ✅ Appears implemented in recording_sessions routes (filters by `rep_id`)

4. **Exec/Manager Scoping**:
   - Spec: Should see company-wide data
   - **Status**: ✅ Most endpoints use `tenant_id` which gives company-wide access

### 3.3 Endpoint-Specific RBAC Issues

| Endpoint | Spec Allowed Roles | Actual Roles | Status | Notes |
|----------|-------------------|--------------|--------|-------|
| `/api/v1/missed-calls/queue/metrics` | `csr`, `manager`, `exec` | `manager`, `csr` | ⚠️ PARTIAL | Missing `exec` role |
| `/api/v1/recording-sessions/*` | Sales rep: own, Exec/manager: company, CSR: no access | Need to verify | ⚠️ NEEDS AUDIT | Must check actual implementation |
| `/api/v1/dashboard/booking-rate` | `csr`, `manager`, `exec`, `sales_rep` | `manager`, `csr`, `sales_rep` | ⚠️ PARTIAL | Missing `exec` role |

**Issues**:
- Some endpoints missing `exec` role in `@require_role()` decorator
- Need to verify CSR endpoints actually filter by `csr_id`

---

## Section 4: Idempotency & Shunya Flows

### 4.1 Shunya → Otto Webhook Idempotency

**Status**: ✅ **MOSTLY COMPLIANT**

**Implementation**:
- ✅ Webhook handler reads `X-Shunya-Task-Id` header
- ✅ Uses `ShunyaJob` model with `uwc_job_id` (unique constraint)
- ✅ Checks `job.job_status == SUCCEEDED` before processing (line 181 in shunya_webhook.py)
- ✅ Uses `processed_output_hash` to prevent duplicate processing
- ✅ `CallTranscript.uwc_job_id` has unique constraint (prevents duplicate transcripts)
- ✅ `CallAnalysis.uwc_job_id` has unique constraint (prevents duplicate analyses)

**Gaps**:
- ⚠️ **No unique constraint on `(company_id, call_id)` in analysis tables** as spec requires
- ⚠️ Need to verify `X-Shunya-Task-Id` is actually used for idempotency (currently uses `shunya_job_id` from payload)

### 4.2 Otto → Shunya Submission Idempotency

**Status**: ⚠️ **NEEDS VERIFICATION**

**Spec Requirement**: Use deterministic natural keys like `(company_id, call_id, "csr_analysis")`

**Current State**:
- Need to audit `ShunyaIntegrationService` and `UWCClient` to verify natural key usage
- Need to check if resubmissions are prevented

### 4.3 PendingAction Idempotency

**Status**: ❌ **NOT APPLICABLE** (No pending_action model exists)

**Spec Requirement**: Unique constraint on `(company_id, contact_card_id, category, due_at)`

**Current State**: Task model has `unique_key` field but no constraint as specified

---

## Section 5: Metrics Coverage

### 5.1 CSR-side Metrics

| Metric | Spec Definition | Implementation Status | Notes |
|--------|----------------|----------------------|-------|
| `total_leads_spoken_to` | Count calls with `call_type = csr_call` | ❌ NOT IMPLEMENTED | Missing `call_type` field on Call model |
| `qualified_leads` | Count where `qualification_status ∈ {hot, warm}` | ⚠️ PARTIAL | Qualification status in CallAnalysis, not Lead |
| `appointments_booked` | Appointments where `csr_id = this CSR` | ❌ NOT IMPLEMENTED | Missing `csr_id` on Appointment model |
| `booking_rate` | `appointments_booked / qualified_leads` | ⚠️ PARTIAL | Endpoint exists but uses different logic (appointments / qualified calls) |
| `auto_rescues` | Leads rescued after missed call + AI follow-up | ❌ NOT IMPLEMENTED | No endpoint found |
| `unbooked_appointments_list` | Calls with `call_type = csr_call`, `booking_status = not_booked` | ❌ NOT IMPLEMENTED | Missing `call_type` and `booking_status` enum |
| `csr_objections` | Top objections from `call_analysis.objections` | ✅ IMPLEMENTED | `/api/v1/dashboard/top-objections` exists |

### 5.2 Exec → CSR Tab Metrics

| Metric | Spec Definition | Implementation Status | Notes |
|--------|----------------|----------------------|-------|
| Aggregated CSR metrics | Same as CSR but over all CSRs | ❌ NOT IMPLEMENTED | No `/api/v1/dashboard/exec-csr-metrics` endpoint |
| "Most coaching opportunity" | Derived from low SOP, high miss-rate, volume | ❌ NOT IMPLEMENTED | No endpoint found |

### 5.3 Exec → Sales Tab Metrics

| Metric | Spec Definition | Implementation Status | Notes |
|--------|----------------|----------------------|-------|
| `total_recorded_hours` | Per Sales Rep | ❌ NOT IMPLEMENTED | No endpoint found |
| `win_rate` | `closed_won / completed appointments` | ❌ NOT IMPLEMENTED | No endpoint found |
| `process_grade` | Derived from Shunya SOP compliance | ❌ NOT IMPLEMENTED | No endpoint found |
| `auto_usage` | Calls/visits processed by Otto+Shunya vs total | ❌ NOT IMPLEMENTED | No endpoint found |
| `pending_leads_by_rep` | Post-appointment stage leads | ❌ NOT IMPLEMENTED | No endpoint found |

### 5.4 Missed Calls Recovery

| Metric | Spec Definition | Implementation Status | Notes |
|--------|----------------|----------------------|-------|
| `missed_calls_total` | Total missed calls | ✅ IMPLEMENTED | In `/api/v1/missed-calls/queue/metrics` |
| `calls_rescued_by_auto` | AI engagement → booked | ⚠️ PARTIAL | Metrics endpoint has `recovered_count` but may not distinguish auto vs human |
| `calls_rescued_by_humans` | CSR manual re-engagement | ⚠️ PARTIAL | Need to verify if metrics distinguish auto vs human |

---

## Section 6: Concrete TODO List

### 6.1 DB / Migration Changes (Must Fix Before Prod)

1. **Add `csr_id` to Call model**
   - Migration: Add `csr_id` column (nullable String, FK to users.id)
   - Purpose: Required for CSR metrics and filtering
   - Priority: **CRITICAL**

2. **Add `call_type` enum to Call model**
   - Migration: Add `call_type` column (Enum: `csr_call`, `sales_call`, `visit_call`)
   - Purpose: Required for filtering CSR calls vs sales calls
   - Priority: **CRITICAL**

3. **Add `direction` enum to Call model**
   - Migration: Add `direction` column (Enum: `inbound`, `outbound`)
   - Purpose: Required for call direction tracking
   - Priority: **HIGH**

4. **Change `booking_status` from Boolean to Enum**
   - Migration: Add `booking_status` column (Enum: `booked`, `not_booked`, `service_not_offered`)
   - Migration: Migrate data from `booked` boolean
   - Purpose: Aligns with spec
   - Priority: **HIGH**

5. **Add `csr_id` to Appointment model**
   - Migration: Add `csr_id` column (nullable String, FK to users.id)
   - Purpose: Track which CSR booked the appointment (required for CSR metrics)
   - Priority: **CRITICAL**

6. **Add `source_call_id` to Appointment model**
   - Migration: Add `source_call_id` column (nullable Integer, FK to calls.call_id)
   - Purpose: Track which call generated the appointment
   - Priority: **MEDIUM**

7. **Fix Appointment `outcome` enum**
   - Migration: Update enum values to match spec: `{closed_won, closed_lost, open}`
   - Current: `{pending, won, lost, no_show, rescheduled}`
   - Priority: **HIGH**

8. **Add `source` enum to ContactCard**
   - Migration: Add `source` column (Enum: `callrail`, `manual`, `auto_ai`, `import`, `otto`, `shunya`)
   - Purpose: Track contact card origin
   - Priority: **MEDIUM**

9. **Add AI summary fields to ContactCard**
   - Migration: Add `last_call_summary` (Text, nullable)
   - Migration: Add `primary_intent` (String, nullable)
   - Migration: Add `risks` (JSON array, nullable)
   - Purpose: AI-generated contact insights
   - Priority: **MEDIUM**

10. **Add `secondary_phones[]` array support to ContactCard**
    - Migration: Change `secondary_phone` (single) to `secondary_phones` (JSON array)
    - Purpose: Support multiple secondary phones
    - Priority: **LOW**

11. **Split `address` into `address_line_1`, `address_line_2` in ContactCard**
    - Migration: Add new columns, migrate data, deprecate old column
    - Priority: **LOW**

12. **Add `country` field to ContactCard**
    - Migration: Add `country` column (String, nullable)
    - Priority: **LOW**

13. **Create `pending_action` model**
    - Migration: Create new `pending_actions` table with all spec fields
    - Purpose: Separate from Task model as spec requires
    - Priority: **HIGH**

14. **Add unique constraint on `(company_id, call_id)` in call_analysis**
    - Migration: Add unique constraint
    - Purpose: Prevent duplicate analysis per call (idempotency)
    - Priority: **HIGH**

15. **Standardize field naming: `tenant_id` → `company_id`**
    - Migration: Rename `tenant_id` to `company_id` in CallTranscript and CallAnalysis
    - Purpose: Consistency with spec
    - Priority: **MEDIUM**

16. **Add missing CallAnalysis fields**
    - Migration: Add `objection_severity` (JSON or String)
    - Migration: Add `pending_actions[]` (JSON array)
    - Migration: Add `summary` (Text)
    - Migration: Add `missed_opportunities[]` (JSON array)
    - Priority: **MEDIUM**

17. **Add `qualification_status` to Lead model**
    - Migration: Add `qualification_status` column (Enum: `hot`, `warm`, `cold`, `unqualified`)
    - Purpose: Store Shunya qualification on Lead, not just in CallAnalysis
    - Priority: **HIGH**

### 6.2 API / Route Changes (Must Fix Before Prod)

1. **Create `/api/v1/dashboard/csr-metrics` endpoint**
   - Purpose: CSR-specific metrics (total_leads_spoken_to, qualified_leads, appointments_booked, booking_rate, auto_rescues)
   - Must filter by `csr_id = user_id` for CSR role
   - Priority: **CRITICAL**

2. **Create `/api/v1/dashboard/exec-csr-metrics` endpoint**
   - Purpose: Aggregated CSR metrics for Exec dashboard
   - Must aggregate over all CSRs in company
   - Priority: **CRITICAL**

3. **Create `/api/v1/dashboard/exec-sales-metrics` endpoint**
   - Purpose: Sales rep metrics (win_rate, process_grade, auto_usage, total_recorded_hours)
   - Must provide per-rep breakdown
   - Priority: **CRITICAL**

4. **Create unbooked appointments list endpoint**
   - Path: `/api/v1/dashboard/unbooked-appointments` or similar
   - Purpose: List calls where `call_type = csr_call`, `booking_status = not_booked`
   - Priority: **HIGH**

5. **Rename `/api/v1/rag/query` to `/api/v1/ask-otto`**
   - Purpose: Match spec naming
   - Priority: **LOW** (or keep both for backward compatibility)

6. **Add `scope` parameter to Ask Otto endpoint**
   - Purpose: Support `scope: "self" | "team" | "company"` as spec requires
   - Priority: **MEDIUM**

7. **Create `/api/v1/reps/{rep_id}/stats` endpoint**
   - Purpose: Sales rep stats for mobile app and Exec dashboard
   - Priority: **HIGH**

8. **Fix `/api/v1/sales-rep/{rep_id}/appointments` to match spec**
   - Current: `/api/v1/sales-rep/{rep_id}/appointments`
   - Spec: `/api/v1/reps/{rep_id}/appointments?date=YYYY-MM-DD`
   - Add date query parameter support
   - Priority: **MEDIUM**

9. **Verify `/api/v1/appointments/{id}` includes contact card + AI insights**
   - Purpose: Ensure response matches spec requirements
   - Priority: **MEDIUM**

10. **Add auto_rescues metric to missed-calls queue metrics**
    - Purpose: Distinguish auto-rescued vs human-rescued calls
    - Priority: **HIGH**

### 6.3 RBAC / Middleware Fixes (Must Fix Before Prod)

1. **Add `exec` role to all Exec-accessible endpoints**
   - Files: `app/routes/backend.py`, `app/routes/missed_call_queue.py`, etc.
   - Change: Add `"exec"` to `@require_role()` decorators
   - Priority: **HIGH**

2. **Verify CSR endpoints filter by `csr_id = user_id`**
   - Files: All CSR dashboard endpoints
   - Add filtering logic where missing
   - Priority: **CRITICAL**

3. **Standardize role enum values**
   - Ensure all code uses: `{csr, manager, exec, sales_rep, admin}`
   - Remove role aliases or document them clearly
   - Priority: **MEDIUM**

4. **Add RBAC checks to recording_sessions endpoints**
   - Verify CSR has no access (as spec requires)
   - Verify Sales rep only sees own sessions
   - Priority: **HIGH**

### 6.4 Shunya Flow Fixes (Must Fix Before Prod)

1. **Use `X-Shunya-Task-Id` header for idempotency**
   - Current: Uses `shunya_job_id` from payload
   - Change: Use `X-Shunya-Task-Id` header as primary idempotency key
   - File: `app/routes/shunya_webhook.py`
   - Priority: **HIGH**

2. **Add unique constraint on `(company_id, call_id)` in call_analysis**
   - Migration required (see DB changes)
   - Purpose: Prevent duplicate analysis per call
   - Priority: **HIGH**

3. **Verify Otto → Shunya submissions use natural keys**
   - Audit: `app/services/shunya_integration_service.py`
   - Verify: Uses `(company_id, call_id, "csr_analysis")` style keys
   - Priority: **MEDIUM**

4. **Add idempotency check for pending_action creation**
   - Once pending_action model exists, add unique constraint
   - Priority: **MEDIUM** (blocked by pending_action model creation)

### 6.5 Nice to Have (Post-MVP)

1. **Rename `tenant_id` to `company_id` in CallTranscript and CallAnalysis**
   - Consistency improvement
   - Priority: **LOW**

2. **Add `country` field to ContactCard**
   - Internationalization support
   - Priority: **LOW**

3. **Split address fields in ContactCard**
   - Better address parsing
   - Priority: **LOW**

4. **Support multiple secondary phones in ContactCard**
   - Enhanced contact management
   - Priority: **LOW**

5. **Add `audio_url` to Call model**
   - Direct audio access
   - Priority: **LOW**

---

## Summary Statistics

- **Models**: 8 entities audited
  - ✅ Fully compliant: 2 (ContactCard structure, RecordingSession)
  - ⚠️ Partial compliance: 5 (Lead, Call, CallTranscript, CallAnalysis, Appointment, Task)
  - ❌ Missing: 1 (PendingAction)

- **Routes**: ~15 endpoints audited
  - ✅ Matches spec: 6
  - ⚠️ Mismatch: 4
  - ❌ Missing: 5

- **RBAC**: Mostly compliant with minor gaps
  - ⚠️ Missing `exec` role in some endpoints
  - ⚠️ Need to verify CSR filtering

- **Idempotency**: Mostly compliant
  - ✅ Shunya webhook idempotency implemented
  - ⚠️ Missing unique constraint on `(company_id, call_id)`

- **Metrics**: Significant gaps
  - ✅ Implemented: 3 metrics
  - ⚠️ Partially implemented: 3 metrics
  - ❌ Not implemented: 10+ metrics

---

## Critical Path to Compliance

**Phase 1 (Must Fix Before Prod)**:
1. Add `csr_id` to Call and Appointment models
2. Add `call_type` enum to Call model
3. Create CSR metrics endpoint with proper filtering
4. Create Exec CSR and Sales metrics endpoints
5. Add `exec` role to all relevant endpoints
6. Verify CSR endpoints filter by `csr_id`

**Phase 2 (High Priority)**:
1. Create `pending_action` model
2. Add missing CallAnalysis fields
3. Fix Appointment outcome enum
4. Add unique constraint on `(company_id, call_id)` for call_analysis

**Phase 3 (Medium Priority)**:
1. Add `qualification_status` to Lead model
2. Standardize field naming (`tenant_id` → `company_id`)
3. Add `source` enum to ContactCard
4. Improve idempotency checks



