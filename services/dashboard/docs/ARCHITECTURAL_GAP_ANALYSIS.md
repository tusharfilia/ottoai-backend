# Otto Backend - Architectural Gap Analysis

**Date**: 2025-01-XX  
**Auditor**: Principal Systems Architect  
**Scope**: Complete backend codebase analysis for Shunya integration correctness, semantic inference violations, and production readiness  
**Purpose**: Identify gaps, violations, and risks before implementation phase

---

## Executive Summary

This analysis examines the Otto backend codebase against the core architectural constraint: **Shunya is the single source of truth for all semantic interpretation**. The analysis identifies:

- ✅ **Correctly Implemented**: Core Shunya integration pipeline, idempotency, multi-tenant isolation
- ⚠️ **Partially Implemented**: Target role headers, Ask Otto endpoint alignment, SMS/text analysis
- ❌ **Missing**: Personal Otto, follow-up recommendations, dead lead intent detection from Shunya
- 🔁 **Violations**: Outcome inference in AI search, potential dead lead heuristics

**Critical Finding**: Otto correctly uses Shunya for call analysis but has several places where it infers semantics instead of relying on Shunya data.

---

## A. Architecture Map

### What Exists Today

#### ✅ Core Services (Correctly Implemented)
1. **Shunya Integration Service** (`app/services/shunya_integration_service.py`)
   - CSR call processing pipeline
   - Sales visit processing pipeline
   - Properly stores Shunya outputs in domain models
   - Updates Lead status from Shunya qualification (correct)

2. **UWC Client** (`app/services/uwc_client.py`)
   - JWT authentication
   - Retry logic with exponential backoff
   - Circuit breaker pattern
   - Error handling
   - ⚠️ **Gap**: Missing `X-Target-Role` header support in many calls

3. **Shunya Job Service** (`app/services/shunya_job_service.py`)
   - Idempotency via `ShunyaJob` table
   - Output hash checking
   - Retry management
   - Status tracking

4. **Webhook Handler** (`app/routes/shunya_webhook.py`)
   - HMAC signature verification
   - Tenant isolation verification
   - Idempotency checks

5. **Response Normalizer** (`app/services/shunya_response_normalizer.py`)
   - Defensive parsing
   - Enum normalization
   - Handles format variations

#### ✅ Data Models (Correctly Structured)
- `CallAnalysis` - Stores Shunya outputs (objections, sentiment, compliance, booking_status)
- `CallTranscript` - Stores Shunya ASR results
- `RecordingAnalysis` - Stores Shunya visit analysis
- `ShunyaJob` - Tracks async jobs with idempotency

#### ✅ Multi-Tenant Isolation
- All queries filter by `company_id` / `tenant_id`
- Middleware enforces tenant context
- Webhook verification checks tenant match

### What's Missing or Incorrect

#### ❌ Missing Shunya Features
1. **Personal Otto** - Not implemented (requires `X-Target-Role` header)
2. **Follow-up Recommendations** - Endpoint exists in client but not called
3. **SMS/Text Analysis** - Unclear if Shunya is used for text thread interpretation
4. **Dead Lead Intent Detection** - No evidence of Shunya intent detection for dead/abandoned leads

#### ⚠️ Partially Implemented
1. **Ask Otto** - Using legacy endpoint `/api/v1/search/` instead of canonical `/api/v1/ask-otto/query`
2. **Target Role Headers** - Client has mapping function but not consistently used
3. **SOP Compliance** - Only GET endpoint used, POST with `target_role` missing
4. **Meeting Segmentation** - Client methods exist but end-to-end flow not fully verified

---

## B. Gap Analysis Table

| Area | Status | Issue | Recommendation |
|------|--------|-------|----------------|
| **Semantic Inference** | | | |
| Outcome derivation in AI search | ❌ **VIOLATION** | `_derive_outcome()` in `ai_search.py` infers outcomes from appointments/leads instead of using Shunya `CallAnalysis.call_outcome_category` | Replace with Shunya data. If Shunya data missing, return `null`, don't infer. |
| Dead lead detection | ⚠️ **UNCLEAR** | Uses `Lead.status` (ABANDONED, DORMANT) but unclear if these are set by Shunya intent or Otto heuristics | Verify: If Shunya provides dead lead intent, use it. Otherwise, document Otto rule clearly. |
| No-show detection | ⚠️ **UNCLEAR** | `AppointmentOutcome.NO_SHOW` exists but unclear if set by geofence (Otto) or Shunya analysis | Document: No-show should be Otto-owned (geofence-based), not Shunya. |
| **Shunya Integration** | | | |
| Target role headers | ⚠️ **PARTIAL** | `UWCClient` has `_map_otto_role_to_shunya_target_role()` but not used in all calls | Add `target_role` parameter to all Shunya calls that require it (Ask Otto, Personal Otto, SOP/compliance). |
| Ask Otto endpoint | ⚠️ **MISMATCH** | Using legacy `/api/v1/search/` instead of canonical `/api/v1/ask-otto/query` | Switch to canonical endpoint with correct payload format. |
| Ask Otto payload | ⚠️ **MISMATCH** | Sending `{query, limit, filters}` instead of `{question, conversation_id?, context, scope?}` | Update payload to match Shunya contract. |
| Personal Otto | ❌ **MISSING** | No calls to `/api/v1/personal-otto/*` endpoints | Implement Personal Otto endpoints with required `X-Target-Role` header. |
| Follow-up recommendations | ❌ **MISSING** | Client method exists but not called in integration flow | Call `/api/v1/analysis/followup-recommendations/{call_id}` after analysis completes. |
| SOP compliance POST | ⚠️ **PARTIAL** | Only GET endpoint used; POST with `?target_role=` missing | Add POST compliance check with required `target_role` query param. |
| Document ingestion | ⚠️ **PARTIAL** | `ingest_document()` exists but missing `?target_role=` query param | Add `target_role` query param to document ingestion calls. |
| SMS/Text analysis | ❌ **UNCLEAR** | SMS handling exists but no evidence of Shunya text thread analysis | Verify: If Shunya provides SMS analysis, integrate it. Otherwise, document as Otto-owned. |
| **Idempotency** | | | |
| Webhook idempotency | ✅ **OK** | `ShunyaJob` + output hash checking | No changes needed. |
| Race conditions | ⚠️ **RISK** | Webhook + polling both can process same job | Add distributed lock (Redis) to prevent concurrent processing. |
| **Multi-Tenant** | | | |
| Tenant isolation | ✅ **OK** | All queries filter by `company_id` | No changes needed. |
| Webhook tenant verification | ✅ **OK** | Verifies `company_id` matches | No changes needed. |
| **Scalability** | | | |
| Idempotency queries | ⚠️ **BOTTLENECK** | Database query on every webhook (~10-50ms) | Add Redis cache layer for fast-path idempotency checks. |
| No caching layer | ⚠️ **MISSING** | All data read directly from PostgreSQL | Consider Redis caching for frequently accessed analysis results. |

---

## C. Shunya Dependency Checklist

### What Otto Expects from Shunya (Must Be Delivered)

#### ✅ Already Delivered (Verified in Code)
- [x] Call transcription (ASR) - `POST /api/v1/transcription/transcribe`
- [x] Complete analysis - `GET /api/v1/analysis/complete/{call_id}`
- [x] Qualification status - From complete analysis
- [x] Booking status - From complete analysis (`booking_status` enum)
- [x] Objections - From complete analysis
- [x] SOP compliance score - From complete analysis
- [x] Sentiment score - From complete analysis
- [x] Meeting segmentation - `POST /api/v1/meeting-segmentation/analyze`
- [x] Webhook notifications - `POST /api/v1/shunya/webhook`

#### ⚠️ Partially Delivered (Otto Not Using Correctly)
- [ ] Ask Otto canonical endpoint - Otto using legacy endpoint
- [ ] Target role support - Shunya supports it, Otto not sending headers
- [ ] Follow-up recommendations - Shunya provides endpoint, Otto not calling
- [ ] Personal Otto - Shunya provides endpoints, Otto not implemented

#### ❌ Not Yet Delivered (Otto Expects But Shunya May Not Provide)
- [ ] **Dead lead intent detection** - Otto uses `Lead.status` (ABANDONED, DORMANT) but unclear if Shunya provides explicit intent
- [ ] **SMS/Text thread analysis** - Otto handles SMS but unclear if Shunya analyzes text threads
- [ ] **Reschedule intent detection** - Otto has reschedule logic but unclear if Shunya provides intent
- [ ] **Cancellation intent detection** - Otto has cancellation logic but unclear if Shunya provides intent

**Action Required**: Verify with Shunya team:
1. Does Shunya provide explicit dead lead intent detection?
2. Does Shunya analyze SMS/text threads?
3. Does Shunya detect reschedule/cancellation intent?

---

## D. Otto Work Remaining

### Backend

#### Critical (Must Fix Before Production)
1. **Fix `_derive_outcome()` in `ai_search.py`**
   - **File**: `app/routes/ai_search.py:33-53`
   - **Issue**: Infers outcomes from appointments/leads instead of Shunya
   - **Fix**: Use `CallAnalysis.call_outcome_category` from Shunya. If null, return null.
   - **Impact**: High - Violates core constraint

2. **Add target_role header support to UWC client**
   - **File**: `app/services/uwc_client.py`
   - **Issue**: `_get_headers()` doesn't accept `target_role` parameter
   - **Fix**: Add `target_role` parameter and set `X-Target-Role` header when provided
   - **Impact**: High - Required for Personal Otto, proper Ask Otto scoping

3. **Switch Ask Otto to canonical endpoint**
   - **File**: `app/routes/rag.py:171-179`
   - **Issue**: Using legacy `/api/v1/search/` instead of `/api/v1/ask-otto/query`
   - **Fix**: Use `query_ask_otto()` method with canonical endpoint and payload
   - **Impact**: High - Ask Otto mis-scoped (defaults to sales_rep)

4. **Fix Ask Otto payload format**
   - **File**: `app/routes/rag.py:157-179`
   - **Issue**: Sending wrong payload format
   - **Fix**: Send `{question, conversation_id?, context, scope?}` instead of `{query, limit, filters}`
   - **Impact**: High - Payload mismatch

5. **Implement Personal Otto**
   - **Files**: New service + routes
   - **Issue**: Not implemented
   - **Fix**: Create endpoints for Personal Otto training/profile with required `X-Target-Role` header
   - **Impact**: Medium - Feature not available

6. **Add follow-up recommendations call**
   - **File**: `app/services/shunya_integration_service.py:567`
   - **Issue**: Client method exists but not called
   - **Fix**: Call `/api/v1/analysis/followup-recommendations/{call_id}` after analysis completes
   - **Impact**: Medium - Feature not available

7. **Add POST compliance check with target_role**
   - **File**: `app/services/uwc_client.py`
   - **Issue**: Only GET endpoint used
   - **Fix**: Add POST `/api/v1/sop/compliance/check?target_role=` method
   - **Impact**: Medium - Compliance checks not role-scoped

8. **Add target_role to document ingestion**
   - **File**: `app/routes/rag.py:686`
   - **Issue**: Missing `?target_role=` query param
   - **Fix**: Add `target_role` query param to `ingest_document()` call
   - **Impact**: Medium - Document ingestion not role-scoped

#### Important (Should Fix Soon)
9. **Verify dead lead detection logic**
   - **Files**: `app/services/metrics_service.py:1550`, `app/models/lead.py:21-22`
   - **Issue**: Uses `Lead.status` (ABANDONED, DORMANT) but unclear if set by Shunya or Otto
   - **Fix**: Document clearly: If Shunya provides dead lead intent, use it. Otherwise, document Otto rule.
   - **Impact**: Medium - Unclear ownership

10. **Add distributed lock for webhook + polling race condition**
    - **Files**: `app/routes/shunya_webhook.py`, `app/tasks/shunya_job_polling_tasks.py`
    - **Issue**: Both webhook and polling can process same job concurrently
    - **Fix**: Add Redis distributed lock before processing
    - **Impact**: Medium - Potential duplicate processing

11. **Verify SMS/text analysis integration**
    - **Files**: `app/routes/sms_handler.py`, `app/models/message_thread.py`
    - **Issue**: SMS handling exists but no Shunya integration
    - **Fix**: If Shunya provides SMS analysis, integrate it. Otherwise, document as Otto-owned.
    - **Impact**: Low - Feature may not be needed

12. **Verify no-show detection logic**
    - **Files**: `app/models/appointment.py:17`, `app/services/shunya_integration_service.py:997`
    - **Issue**: Unclear if no-show is Otto-owned (geofence) or Shunya-owned
    - **Fix**: Document: No-show should be Otto-owned (geofence-based), not Shunya.
    - **Impact**: Low - Clarification needed

### Infra

13. **Add Redis cache for idempotency**
    - **File**: `app/services/idempotency.py`
    - **Issue**: Database query on every webhook (~10-50ms)
    - **Fix**: Add Redis cache layer for fast-path idempotency checks
    - **Impact**: Medium - Performance improvement

14. **Add Redis caching for analysis results**
    - **Files**: Various API routes
    - **Issue**: All data read directly from PostgreSQL
    - **Fix**: Add Redis caching for frequently accessed analysis results
    - **Impact**: Low - Performance optimization

### Integrations

15. **Verify meeting segmentation end-to-end**
    - **Files**: `app/services/shunya_integration_service.py:872-1068`
    - **Issue**: Client methods exist but end-to-end flow not fully verified
    - **Fix**: Test full pipeline: recording → Shunya → persisted → exposed
    - **Impact**: Low - Verification needed

### Observability

16. **Add metrics for Shunya call failures**
    - **Files**: `app/services/uwc_client.py`
    - **Issue**: Errors logged but not tracked in metrics
    - **Fix**: Add Prometheus metrics for Shunya API failures
    - **Impact**: Low - Monitoring improvement

### Tests

17. **Add integration tests for Shunya violations**
    - **Files**: New test files
    - **Issue**: No tests verify Otto doesn't infer semantics
    - **Fix**: Add tests that verify Otto returns null when Shunya data missing
    - **Impact**: High - Prevents regressions

---

## E. Risk Register

### Top Risks If This Shipped Today

| Risk | Severity | Likelihood | Impact | Mitigation |
|------|----------|------------|--------|------------|
| **Outcome inference in AI search** | 🔴 **CRITICAL** | High | High | Users see incorrect outcomes. Fix `_derive_outcome()` immediately. |
| **Ask Otto mis-scoped** | 🔴 **CRITICAL** | High | High | CSR/Exec queries default to sales_rep context. Fix endpoint + headers. |
| **Dead lead heuristics override Shunya** | 🟡 **HIGH** | Medium | Medium | If Shunya provides dead lead intent, Otto may override it. Verify ownership. |
| **Webhook + polling race condition** | 🟡 **HIGH** | Medium | Medium | Duplicate processing possible. Add distributed lock. |
| **No target_role headers** | 🟡 **HIGH** | High | Medium | Personal Otto won't work. SOP/compliance not role-scoped. |
| **Idempotency database bottleneck** | 🟠 **MEDIUM** | High | Low | High webhook volume may slow down. Add Redis cache. |
| **SMS analysis missing** | 🟠 **MEDIUM** | Low | Low | If Shunya provides SMS analysis, Otto not using it. Verify requirement. |
| **No-show detection unclear** | 🟠 **MEDIUM** | Low | Low | Unclear if Otto or Shunya owns no-show. Document clearly. |

---

## F. Explicit Violations of Core Constraint

### ❌ Violation 1: Outcome Inference in AI Search

**Location**: `app/routes/ai_search.py:33-53`

**Code**:
```python
def _derive_outcome(call: Call, lead: Optional[Lead], appointment: Optional[Appointment]) -> Optional[str]:
    """Derive outcome string from call/lead/appointment state."""
    if appointment and appointment.outcome:
        return appointment.outcome.value
    if lead and lead.status:
        status_value = lead.status.value
        if "won" in status_value:
            return "won"
        # ... more inference logic
```

**Issue**: Infers outcomes from appointments/leads instead of using Shunya `CallAnalysis.call_outcome_category`.

**Fix**: Use `CallAnalysis.call_outcome_category` from Shunya. If null, return null.

**Impact**: High - Violates core constraint that Shunya is source of truth.

---

### ⚠️ Violation 2: Dead Lead Detection (Unclear Ownership)

**Location**: `app/services/metrics_service.py:1550`

**Code**:
```python
# Check if dead (using Lead.status for lead lifecycle, not booking semantics)
is_dead = lead.status in [LeadStatus.ABANDONED.value, LeadStatus.CLOSED_LOST.value, LeadStatus.DORMANT.value]
```

**Issue**: Uses `Lead.status` but unclear if these statuses are set by Shunya intent or Otto heuristics.

**Fix**: 
- If Shunya provides dead lead intent → Use Shunya data
- If Otto owns dead lead logic → Document clearly: "Otto rule: no response after N attempts + time window"

**Impact**: Medium - Unclear ownership violates clarity principle.

---

## G. What Should Explicitly Remain Shunya-Owned

Per the Responsibility Matrix, Shunya owns:

1. ✅ **Call transcription analysis** - Correctly implemented
2. ✅ **Text/SMS analysis** - ⚠️ Unclear if implemented
3. ✅ **Lead qualification (hot/warm/cold)** - Correctly implemented
4. ✅ **Booking status classification** - Correctly implemented
5. ✅ **Objections extraction** - Correctly implemented
6. ✅ **SOP compliance scoring** - Correctly implemented
7. ✅ **Sentiment analysis** - Correctly implemented
8. ✅ **Meeting outcome (won/lost/pending)** - Correctly implemented for sales visits
9. ⚠️ **Pending nurture** - Unclear if Shunya provides
10. ⚠️ **Reschedule intent** - Unclear if Shunya provides
11. ⚠️ **Cancellation intent** - Unclear if Shunya provides
12. ⚠️ **Dead lead intent** - Unclear if Shunya provides

**Action Required**: Verify with Shunya team which of the unclear items (9-12) Shunya provides.

---

## H. What Should Explicitly Remain Otto-Owned

Per the Responsibility Matrix, Otto owns:

1. ✅ **Multi-tenant isolation** - Correctly implemented
2. ✅ **User authentication & RBAC** - Correctly implemented
3. ✅ **Contact cards** - Correctly implemented
4. ✅ **Property intelligence scraping** - Correctly implemented (ChatGPT-based)
5. ✅ **CallRail + Twilio integrations** - Correctly implemented
6. ✅ **Webhooks ingestion** - Correctly implemented
7. ✅ **Task generation** - Correctly implemented
8. ✅ **Notifications** - Correctly implemented
9. ✅ **CSR-led manual appointment dispatching** - Correctly implemented
10. ✅ **Sales rep scheduling** - Correctly implemented
11. ✅ **Geofenced recording** - Correctly implemented
12. ✅ **Recording session lifecycle** - Correctly implemented
13. ✅ **Metrics aggregation** - Correctly implemented (Shunya-first)
14. ✅ **UI-facing APIs** - Correctly implemented
15. ✅ **Idempotency** - Correctly implemented
16. ✅ **Audit logs** - Correctly implemented
17. ✅ **Observability** - Correctly implemented
18. ⚠️ **No-show detection** - Should be Otto-owned (geofence-based) but needs documentation
19. ⚠️ **Dead lead logic** - Should be Otto-owned if Shunya doesn't provide intent, but needs documentation

---

## I. Recommendations Summary

### Immediate Actions (Before Any Code Changes)

1. **Verify with Shunya team**:
   - Does Shunya provide dead lead intent detection?
   - Does Shunya analyze SMS/text threads?
   - Does Shunya detect reschedule/cancellation intent?
   - Does Shunya provide pending nurture signals?

2. **Document ownership clearly**:
   - No-show detection: Otto-owned (geofence-based)
   - Dead lead logic: If Shunya provides intent → Shunya-owned, else Otto-owned with documented rule

### Critical Fixes (Before Production)

1. Fix `_derive_outcome()` to use Shunya data
2. Add target_role header support
3. Switch Ask Otto to canonical endpoint
4. Fix Ask Otto payload format

### Important Fixes (Soon)

5. Implement Personal Otto
6. Add follow-up recommendations call
7. Add POST compliance check with target_role
8. Add target_role to document ingestion
9. Add distributed lock for race condition

### Nice to Have (Later)

10. Add Redis cache for idempotency
11. Add Redis caching for analysis results
12. Add metrics for Shunya failures
13. Add integration tests for violations

---

## J. Conclusion

The Otto backend demonstrates **strong foundational architecture** with proper Shunya integration for core call analysis. However, there are **critical violations** where Otto infers semantics instead of relying on Shunya data, particularly in the AI search endpoint.

**Key Findings**:
- ✅ Core Shunya integration is correct
- ❌ Outcome inference violates core constraint
- ⚠️ Several Shunya features not fully utilized (target_role, Personal Otto, follow-up recommendations)
- ⚠️ Unclear ownership for dead lead detection and SMS analysis

**Production Readiness**: **NOT READY** - Critical violations must be fixed before production.

**Next Steps**:
1. Fix critical violations (outcome inference, Ask Otto endpoint)
2. Verify unclear ownership with Shunya team
3. Implement missing Shunya features (Personal Otto, follow-up recommendations)
4. Add tests to prevent regressions

---

**End of Analysis**



