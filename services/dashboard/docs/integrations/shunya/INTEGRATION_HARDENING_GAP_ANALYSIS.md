# Shunya Integration Hardening - Gap Analysis

**Date**: 2025-11-24  
**Status**: ✅ **Phase 1 & Phase 2 Complete** - Ready for Shunya Confirmations

---

## 📋 Executive Summary

This document identifies gaps between Otto's current Shunya integration implementation and the requirements defined in:
- `RESPONSIBILITY_MATRIX.md` (canonical responsibilities)
- `ASK_OTTO_REQUIREMENTS.md` (Ask Otto API needs)
- Shunya OpenAPI contract (endpoint contracts)

**Overall Status**: Most infrastructure exists, but several hardening opportunities identified.

---

## 🔍 Analysis Methodology

1. ✅ Codebase audit of `UWCClient` endpoints vs OpenAPI paths
2. ✅ Multi-tenancy enforcement verification
3. ✅ Idempotency guard coverage analysis
4. ✅ Security hardening (HTTPS, JWT, HMAC, tenant isolation)
5. ✅ Async job orchestration alignment with Responsibility Matrix
6. ✅ `/internal/ai/*` endpoint completeness vs Ask Otto requirements

---

## 📊 Gap Categories

### A. API Contract Alignment (Otto → Shunya)

#### A1. Endpoint Path Verification

**Current UWCClient Methods**:
- `submit_asr_batch()` → `POST /uwc/v1/asr/batch`
- `transcribe_audio()` → `POST /api/v1/transcription/transcribe` ✅
- `get_transcription_status()` → `GET /api/v1/transcription/status/{call_id}` ✅
- `get_transcript()` → `GET /api/v1/transcription/transcript/{call_id}` ✅
- `query_rag()` → `POST /api/v1/search/` ✅
- `summarize_call()` → `POST /api/v1/summarization/summarize` ✅
- `get_summarization_status()` → `GET /api/v1/summarization/status/{call_id}` ✅
- `detect_objections()` → `GET /api/v1/analysis/objections/{call_id}` ✅
- `qualify_lead()` → `GET /api/v1/analysis/qualification/{call_id}` ✅
- `get_complete_analysis()` → `GET /api/v1/analysis/complete/{call_id}` ✅
- `analyze_meeting_segmentation()` → `POST /api/v1/meeting-segmentation/analyze` ✅
- `get_meeting_segmentation_status()` → `GET /api/v1/meeting-segmentation/status/{call_id}` ✅
- `get_meeting_segmentation_analysis()` → `GET /api/v1/meeting-segmentation/analysis/{call_id}` ✅

**Findings**:
- ⚠️ **Gap**: `submit_asr_batch()` uses `/uwc/v1/asr/batch` but OpenAPI shows `/api/v1/transcription/transcribe` for transcription
- ✅ Most endpoints align with OpenAPI spec
- ✅ JWT + `X-Company-ID` headers are set correctly

**Action Required**:
- Verify if Shunya supports batch ASR vs single transcription endpoint
- Document assumption: `/uwc/v1/asr/batch` is Shunya-internal, `/api/v1/transcription/transcribe` is Otto-facing

#### A2. Request/Response Schema Alignment

**Findings**:
- ✅ `TranscriptionRequest` matches OpenAPI (`call_id`, `audio_url`, `call_type`)
- ✅ Response handling extracts `task_id` / `transcript_id` correctly
- ⚠️ **Gap**: OpenAPI shows `TranscriptionResponse` has `transcript_id` (integer) and `task_id` (string), but response parsing may not handle all variants

**Action Required**:
- Add defensive parsing for job ID extraction
- Handle both `job_id`, `task_id`, `transcript_id` response variants

#### A3. Enum Value Alignment

**OpenAPI Enum Values**:
- `CallType`: `["sales_call", "csr_call"]` ✅
- Outcome classifications: Need to verify against Responsibility Matrix

**Responsibility Matrix Outcomes**:
- CSR calls: `qualified_and_booked`, `qualified_not_booked`, `qualified_service_not_offered`, `not_qualified`
- Sales visits: `won`, `lost`, `pending_decision`, `no_show`, `rescheduled`

**Findings**:
- ✅ Call types align
- ⚠️ **Gap**: Outcome enum values in `AppointmentOutcome` may not match Responsibility Matrix exactly
- Need to verify outcome mapping in `ShunyaResponseNormalizer`

**Action Required**:
- Audit outcome mapping in normalizer
- Create adapter for outcome value translation if needed

---

### B. Multi-Tenancy Hardening

#### B1. X-Company-ID Header Enforcement

**Current State**:
- ✅ `UWCClient._get_headers()` always includes `X-Company-ID: {company_id}`
- ✅ All `_make_request()` calls require `company_id` parameter
- ✅ JWT includes `company_id` in claims

**Verification**:
```python
# In UWCClient._get_headers():
headers = {
    "Authorization": auth_header,
    "X-Company-ID": company_id,  # ✅ Always set
    "X-Request-ID": request_id,
    ...
}
```

**Status**: ✅ **COMPLIANT**

#### B2. Tenant-Scoped Database Queries

**Current State**:
- ✅ `ShunyaJob` queries filter by `company_id`
- ✅ `get_job_by_shunya_id(company_id, shunya_job_id)` scopes by tenant
- ✅ Webhook handler verifies `payload.company_id == job.company_id`

**Verification Points**:
- ✅ Webhook tenant check: Line 149-166 in `shunya_webhook.py`
- ✅ Job lookup: Line 140 in `shunya_webhook.py` uses tenant-scoped method

**Status**: ✅ **COMPLIANT**

#### B3. Cross-Tenant Attack Prevention

**Current State**:
- ✅ Webhook handler checks `job.company_id != company_id` → returns 403
- ✅ All DB queries filter by `company_id`

**Status**: ✅ **COMPLIANT**

---

### C. Idempotency Hardening

#### C1. ShunyaJob Idempotency

**Current State**:
- ✅ `ShunyaJob.processed_output_hash` field exists
- ✅ `ShunyaJobService.should_process()` checks hash
- ✅ Webhook handler checks idempotency before processing

**Verification**:
```python
# In shunya_webhook.py:
if not shunya_job_service.should_process(db, job, normalized_result):
    return APIResponse(data={"status": "already_processed", ...})
```

**Status**: ✅ **COMPLIANT**

#### C2. Task Creation Idempotency

**Current State**:
- ✅ `Task.unique_key` field exists (from migration)
- ✅ `generate_task_unique_key()` helper exists
- ✅ `_process_shunya_analysis_for_call()` checks for existing tasks

**Gap Analysis**:
- ⚠️ **Gap**: Need to verify all task creation paths use `unique_key` check
- ⚠️ **Gap**: Need to verify `task_exists_by_unique_key()` is called before every task creation

**Action Required**:
- Audit `_create_tasks_from_pending_actions()` methods
- Ensure natural key generation for all Shunya-driven tasks

#### C3. KeySignal Creation Idempotency

**Current State**:
- ✅ `KeySignal.unique_key` field exists
- ✅ `generate_signal_unique_key()` helper exists
- ⚠️ **Gap**: Need to verify all signal creation uses `unique_key` check

**Action Required**:
- Audit signal creation in `_process_shunya_analysis_for_visit()` and `_process_shunya_analysis_for_call()`

#### C4. Lead Status Update Idempotency

**Current State**:
- ✅ `LeadStatusHistory` tracks status changes
- ⚠️ **Gap**: Need to verify we only write history when status actually changes

**Action Required**:
- Add check: `if old_status != new_status: write_history()`

#### C5. Appointment Outcome Update Idempotency

**Current State**:
- ✅ `Appointment.last_outcome_update` timestamp field (if exists)
- ⚠️ **Gap**: Need to verify we only update outcome if it actually changes
- ⚠️ **Gap**: Need to verify `appointment.outcome_updated` event only emits on actual change

**Action Required**:
- Add check: `if appointment.outcome != new_outcome: update()`

---

### D. Security Hardening

#### D1. HTTPS Enforcement

**Current State**:
- ✅ `UWC_BASE_URL` from settings (should be HTTPS)
- ⚠️ **Gap**: No explicit validation that `base_url` starts with `https://`

**Action Required**:
- Add validation: warn/error if `UWC_BASE_URL` is not HTTPS in production

#### D2. JWT Generation

**Current State**:
- ✅ `_generate_jwt()` uses HS256 algorithm
- ✅ Includes `company_id`, `iat`, `exp`, `iss`, `aud`
- ✅ 5-minute TTL
- ⚠️ **Gap**: Need to verify JWT secret is set in production

**Action Required**:
- Add validation check on startup

#### D3. HMAC Signature Generation

**Current State**:
- ✅ `_generate_signature()` uses HMAC-SHA256
- ✅ Webhook signature verification implemented
- ✅ Constant-time comparison

**Status**: ✅ **COMPLIANT**

#### D4. Webhook Security

**Current State**:
- ✅ HMAC signature verification with X-Shunya-* headers
- ✅ Timestamp validation (epoch milliseconds, 5-minute window)
- ✅ Tenant isolation check
- ✅ Raw body access before JSON parsing
- ✅ Signature formula: `HMAC_SHA256(secret, "{timestamp}.{raw_body_bytes}")`

**Status**: ✅ **HARDENED** (Updated 2025-01-28)

**Implementation**:
- Headers: `X-Shunya-Signature`, `X-Shunya-Timestamp`, `X-Shunya-Task-Id`
- Timestamp format: Epoch milliseconds (not ISO 8601)
- See `app/utils/shunya_webhook_security.py` and `docs/integrations/shunya/CHANGELOG_ASK_OTTO_ALIGNMENT.md`

---

### E. Async Job Orchestration

#### E1. CSR Call Pipeline

**Responsibility Matrix Requirement**:
> Otto triggers Shunya jobs (CSR call analysis)

**Current State**:
- ✅ `process_csr_call()` creates `ShunyaJob`
- ✅ Submits to Shunya via async job pipeline
- ✅ Polling + webhook paths exist
- ✅ Idempotency guards in place

**Status**: ✅ **COMPLIANT**

#### E2. Sales Visit Pipeline

**Responsibility Matrix Requirement**:
> After visit audio upload, trigger Shunya visit analysis via async job pipeline

**Current State**:
- ✅ `process_sales_visit()` method exists
- ✅ Creates `ShunyaJob` with type `SALES_VISIT`
- ✅ Polling + webhook support

**Status**: ✅ **COMPLIANT**

#### E3. Segmentation Chaining

**Responsibility Matrix Requirement**:
> Meeting segmentation segments appointment into parts

**Current State**:
- ✅ `analyze_meeting_segmentation()` endpoint exists
- ⚠️ **Gap**: Need to verify segmentation jobs are chained after visit analysis completes

**Action Required**:
- Verify segmentation is triggered automatically after visit analysis

---

### F. Ask Otto API Completeness

#### F1. `/internal/ai/calls/{call_id}`

**Ask Otto Requirements**:
- ✅ Returns: `call_id`, `company_id`, `lead_id`, `contact_card_id`, `rep_id`, `phone_number`
- ✅ Returns: `booking_outcome`, `appointment_id`
- ⚠️ **Gap**: `started_at`, `ended_at` may be null (using `created_at` as proxy)
- ⚠️ **Gap**: `direction` is always `None`

**Action Required**:
- Map `Call` model fields to `started_at`/`ended_at` if available
- Extract `direction` from CallRail metadata if available

#### F2. `/internal/ai/leads/{lead_id}`

**Ask Otto Requirements**:
- ✅ Returns: `lead` fields, `contact` fields, `appointments`
- ✅ Status, source, priority, score included

**Status**: ✅ **COMPLIANT**

#### F3. `/internal/ai/appointments/{appointment_id}`

**Ask Otto Requirements**:
- ✅ Returns: `appointment`, `lead`, `contact`
- ✅ Includes: `scheduled_start`, `scheduled_end`, `status`, `outcome`, `service_type`, `location`

**Status**: ✅ **COMPLIANT**

#### F4. `/internal/ai/companies/{company_id}`

**Ask Otto Requirements**:
- ✅ Returns: `company_id`, `name`
- ⚠️ **Gap**: `timezone`, `service_areas` are `None` (not stored in Company model)

**Action Required**:
- Document that `timezone` and `service_areas` require schema additions

#### F5. `/internal/ai/services/{company_id}`

**Ask Otto Requirements**:
- ✅ Returns service catalog
- ✅ Handles missing Services table gracefully

**Status**: ✅ **COMPLIANT**

#### F6. `/internal/ai/search`

**Ask Otto Requirements**:
- ✅ Supports filters: `rep_ids`, `date_from/date_to`, `lead_statuses`, `appointment_outcomes`
- ✅ Supports: `has_objections`, `objection_labels`, `sentiment_min/max`, `sop_score` ranges
- ✅ Returns aggregates: `total_calls`, `calls_by_outcome`, `calls_by_rep`, `objection_label_counts`, `avg_sentiment`, `avg_sop_score`
- ✅ Default date window: last 30 days

**Status**: ✅ **COMPLIANT**

---

### G. Pending Shunya Confirmations

**Items Waiting on Shunya Team**:

1. **Outcome Enum Values**: Exact strings for `qualified_and_booked`, etc. ⏸️ **PENDING**
2. **Objection Label Taxonomy**: Complete list of objection categories ⏸️ **PENDING**
3. ✅ **Webhook Payload & Security**: **RESOLVED** (2025-01-28) - Headers, signature formula, delivery guarantees confirmed
4. ✅ **Segmentation Output Shape**: **RESOLVED** (2025-01-28) - Part1/Part2 structure with content, key_points confirmed
5. ✅ **Error Envelope Format**: **RESOLVED** (2025-01-28) - Canonical error envelope structure confirmed
6. ✅ **Pending Actions Free-String**: **RESOLVED** (2025-01-28) - Free-string action types confirmed, mapping implemented

**Action Required**:
- Outcome enum and objection taxonomy still pending (items 1-2)
- Adapter layer created for outcome/enum translations
- See `docs/integrations/shunya/CHANGELOG_ASK_OTTO_ALIGNMENT.md` for resolved items

---

## 📝 Proposed Patch List

### **Category 1: Safe to Patch Immediately**

1. ✅ **Add HTTPS validation warning** in `UWCClient.__init__()` for production
2. ✅ **Audit and fix task creation idempotency** - ensure all paths check `unique_key`
3. ✅ **Audit and fix signal creation idempotency** - ensure all paths check `unique_key`
4. ✅ **Add lead status change check** - only write history if status actually changed
5. ✅ **Add appointment outcome change check** - only update if outcome actually changed
6. ✅ **Improve job ID extraction** - handle `job_id`, `task_id`, `transcript_id` variants defensively
7. ✅ **Document outcome enum mapping** - create clear mapping document
8. ✅ **Add missing field documentation** - document why `timezone`, `service_areas` are None

### **Category 2: Requires Shunya Confirmation**

1. ⏸️ **Outcome enum value alignment** - wait for Shunya to confirm exact strings
2. ⏸️ **Objection label taxonomy** - wait for Shunya taxonomy document
3. ⏸️ **Webhook payload structure** - wait for final webhook schema
4. ⏸️ **Segmentation additional fields** - wait for Shunya enhancement details

### **Category 3: Schema Changes Needed**

1. 📋 **Add `timezone` to Company model** (if needed for Ask Otto)
2. 📋 **Add `service_areas` to Company model** (if needed for Ask Otto)
3. 📋 **Add `direction` to Call model** (if available from CallRail)

---

## 🎯 Implementation Priority

**Phase 1 (Immediate - Safe to Patch)**:
1. Idempotency hardening (tasks, signals, status changes)
2. HTTPS validation
3. Job ID extraction improvements
4. Documentation updates

**Phase 2 (Adapter Layer - COMPLETE ✅)**:
1. ✅ Contract stubs created for all expected structures
2. ✅ Mapping tables created for all enum translations
3. ✅ Enhanced adapter layer implemented (contract + mapping integration)
4. ✅ Simulation tests created with synthetic payloads
5. ✅ All documentation updated

**Phase 3 (After Shunya Confirmation)**:
1. Update contracts with final field names/types
2. Update mappings with final enum values
3. Enable simulation tests
4. Test with real Shunya responses

**Phase 4 (Future Enhancements)**:
1. Schema additions for missing Ask Otto fields (timezone, service_areas)
2. Enhanced error handling based on Shunya error envelope

---

**Status**: ✅ **Phase 1 & Phase 2 Complete** - Ready for Shunya confirmations.

