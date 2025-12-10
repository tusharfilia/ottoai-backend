# Otto Backend ↔ Shunya Integration TODO

**Date**: 2025-01-20  
**Status**: 📋 **Implementation Checklist**  
**Purpose**: Concrete backend code changes required to align Otto backend with Shunya contracts and MV1 product requirements

---

## Overview

This document lists **only** the concrete backend code changes needed to align Otto's backend with Shunya's current contracts (as documented in `Target_Role_Header.md`, `Integration-Status.md`, `webhook-and-other-payload-ask-otto.md`, and `enums-inventory-by-service.md`).

**Source of Truth**: Based on:
- `docs/frontend/OTTO_BACKEND_SHUNYA_AUDIT.md`
- `docs/integrations/shunya/Target_Role_Header.md`
- `docs/integrations/shunya/Integration-Status.md`
- `docs/integrations/shunya/webhook-and-other-payload-ask-otto.md`
- `docs/integrations/shunya/enums-inventory-by-service.md`

---

## A. Core Plumbing (target_role)

### A1. Add `target_role` parameter support to `UWCClient._get_headers()`

**Files to touch:**
- `app/services/uwc_client.py`

**Functions/classes to modify:**
- `UWCClient._get_headers()` - Add optional `target_role: Optional[str] = None` parameter
- `UWCClient._make_request()` - Add optional `target_role: Optional[str] = None` parameter and pass to `_get_headers()`
- `UWCClient._get_headers()` - Conditionally add `X-Target-Role` header if `target_role` is provided

**Behavior after change:**
- `_get_headers()` accepts optional `target_role` parameter
- If `target_role` is provided, adds `X-Target-Role: {target_role}` to headers dict
- All existing calls continue to work (backward compatible - parameter is optional)

**Backward compatibility:**
- ✅ **Fully backward compatible** - `target_role` parameter is optional
- Existing calls without `target_role` continue to work (no header added)
- No feature flag needed

---

### A2. Add `target_role` query parameter support to `UWCClient._make_request()`

**Files to touch:**
- `app/services/uwc_client.py`

**Functions/classes to modify:**
- `UWCClient._make_request()` - Add optional `target_role_query: Optional[str] = None` parameter
- `UWCClient._make_request()` - If `target_role_query` is provided, append `?target_role={target_role_query}` to endpoint URL

**Behavior after change:**
- `_make_request()` accepts optional `target_role_query` parameter
- If provided, appends `?target_role={target_role_query}` to endpoint URL before making request
- Works for GET and POST requests (query parameter approach per Shunya contract)

**Backward compatibility:**
- ✅ **Fully backward compatible** - `target_role_query` parameter is optional
- Existing calls without query param continue to work
- No feature flag needed

---

### A3. Create role extraction helper function

**Files to touch:**
- `app/services/uwc_client.py` (or `app/core/tenant.py` if shared utility)

**Functions/classes to create:**
- `UWCClient._extract_target_role_from_user_context(user_role: str) -> str` - Maps Otto roles to Shunya target roles
- Or: `get_shunya_target_role(user_role: str) -> str` in `app/core/tenant.py` if shared

**Behavior after change:**
- Maps Otto roles (`csr`, `sales_rep`, `manager`, `exec`) to Shunya target roles (`customer_rep`, `sales_rep`, `sales_manager`, `admin`)
- Defaults to `sales_rep` if role not recognized
- Used consistently across all Shunya API calls

**Backward compatibility:**
- ✅ **Fully backward compatible** - New helper function, doesn't break existing code
- No feature flag needed

**Mapping logic:**
```python
{
    "csr": "customer_rep",
    "sales_rep": "sales_rep",
    "rep": "sales_rep",  # Alias
    "manager": "sales_manager",
    "exec": "admin",
    # Default: "sales_rep"
}
```

---

## B. Ask Otto (endpoint + payload)

### B1. Create new `query_ask_otto()` method in `UWCClient`

**Files to touch:**
- `app/services/uwc_client.py`

**Functions/classes to create:**
- `UWCClient.query_ask_otto()` - New method that calls Shunya's canonical `/api/v1/ask-otto/query` endpoint

**Behavior after change:**
- New method `query_ask_otto()` calls `POST /api/v1/ask-otto/query` (not `/api/v1/search/`)
- Payload shape: `{ "question": str, "conversation_id": Optional[str], "context": dict, "scope": Optional[str] }`
- Automatically sets `X-Target-Role` header based on user role context
- Returns response with `answer`, `sources`, `confidence`, `suggested_follow_ups`, `metadata`

**Backward compatibility:**
- ⚠️ **Breaking change** - New method replaces `query_rag()` for Ask Otto
- Keep `query_rag()` method for backward compatibility (mark as deprecated)
- Feature flag: `ENABLE_ASK_OTTO_V2=true` to use new endpoint (default: `false` to use legacy)

**Migration path:**
- Phase 1: Add new method, keep old method working
- Phase 2: Update `routes/rag.py` to use new method when feature flag enabled
- Phase 3: Remove old method after migration complete

---

### B2. Update `routes/rag.py::query_ask_otto()` to use new Ask Otto endpoint

**Files to touch:**
- `app/routes/rag.py`

**Functions/classes to modify:**
- `query_ask_otto()` - Replace `uwc_client.query_rag()` call with `uwc_client.query_ask_otto()`
- Extract `target_role` from `user_role` using helper function
- Transform request payload from `{query, filters, max_results}` to `{question, conversation_id?, context, scope?}`

**Behavior after change:**
- Route handler calls `uwc_client.query_ask_otto()` instead of `uwc_client.query_rag()`
- Extracts `target_role` from `request.state.user_role` and passes to Shunya
- Transforms `RAGQueryRequest` to Shunya's expected payload shape
- Response shape remains the same (Otto's `RAGQueryResponse`), so frontend doesn't need changes

**Backward compatibility:**
- ⚠️ **Feature flag required** - Use `ENABLE_ASK_OTTO_V2=true` to enable new endpoint
- Default to `false` to keep using legacy `/api/v1/search/` endpoint
- Frontend API contract unchanged (still `POST /api/v1/rag/query`)

---

### B3. Add Ask Otto streaming support (optional, future)

**Files to touch:**
- `app/services/uwc_client.py`
- `app/routes/rag.py` (new endpoint)

**Functions/classes to create:**
- `UWCClient.query_ask_otto_stream()` - SSE streaming method
- `routes/rag.py::query_ask_otto_stream()` - New route handler for streaming

**Behavior after change:**
- New endpoint `POST /api/v1/rag/query-stream` (or `/api/v1/ask-otto/query-stream`)
- Returns Server-Sent Events (SSE) stream with token-by-token answer
- Handles SSE event types: `start`, `classification`, `data_fetched`, `answer_start`, `token`, `answer_complete`, `metadata`, `done`, `error`

**Backward compatibility:**
- ✅ **Fully backward compatible** - New endpoint, doesn't affect existing `/query` endpoint
- Feature flag: `ENABLE_ASK_OTTO_STREAMING=true` (default: `false`)

**Status:**
- ⚠️ **PLANNED, not yet implemented** - Mark as future enhancement

---

## C. Follow-up Recommendations

### C1. Add `get_followup_recommendations()` method to `UWCClient`

**Files to touch:**
- `app/services/uwc_client.py`

**Functions/classes to create:**
- `UWCClient.get_followup_recommendations()` - New method for follow-up recommendations

**Behavior after change:**
- New method calls `POST /api/v1/analysis/followup-recommendations/{call_id}`
- Accepts `target_role` parameter and sets `X-Target-Role` header
- Returns follow-up recommendations with action items, timing, and reasoning

**Backward compatibility:**
- ✅ **Fully backward compatible** - New method, doesn't affect existing code
- No feature flag needed (new feature)

**Status:**
- ⚠️ **PLANNED, not yet implemented** - Mark as future enhancement

---

### C2. Integrate follow-up recommendations into call analysis flow

**Files to touch:**
- `app/services/shunya_integration_service.py` (or similar)
- `app/routes/calls.py` (or appropriate route)

**Functions/classes to modify/create:**
- Add call to `uwc_client.get_followup_recommendations()` after call analysis completes
- Store recommendations in database (new field or table)
- Expose via API endpoint (e.g., `GET /api/v1/calls/{call_id}/followup-recommendations`)

**Behavior after change:**
- After Shunya completes call analysis, automatically fetch follow-up recommendations
- Store recommendations in database for later retrieval
- Expose via API endpoint for frontend consumption

**Backward compatibility:**
- ✅ **Fully backward compatible** - New feature, doesn't break existing analysis flow
- Feature flag: `ENABLE_FOLLOWUP_RECOMMENDATIONS=true` (default: `false`)

**Status:**
- ⚠️ **PLANNED, not yet implemented** - Mark as future enhancement

---

## D. SOP/Compliance Actions

### D1. Update `ingest_document()` to include `target_role` query parameter

**Files to touch:**
- `app/services/uwc_client.py`

**Functions/classes to modify:**
- `UWCClient.ingest_document()` - Add `target_role: Optional[str] = None` parameter
- Append `?target_role={target_role}` to endpoint URL if provided

**Behavior after change:**
- `ingest_document()` accepts optional `target_role` parameter
- If provided, appends `?target_role={target_role}` to `/api/v1/ingestion/documents/upload` endpoint
- Shunya contract requires `target_role` for SOP/document ingestion

**Backward compatibility:**
- ⚠️ **Breaking change** - Shunya requires `target_role` for document ingestion
- Make parameter required (not optional) to match Shunya contract
- Update all callers to pass `target_role` (from `document.role_target` or user context)

**Callers to update:**
- `app/tasks/onboarding_tasks.py::ingest_document_with_shunya()` - Extract `target_role` from `document.role_target`
- `app/routes/rag.py::upload_document()` - Extract `target_role` from user role context

---

### D2. Add `check_compliance_post()` method for initiating compliance checks

**Files to touch:**
- `app/services/uwc_client.py`

**Functions/classes to create:**
- `UWCClient.check_compliance_post()` - New method for POST compliance checks

**Behavior after change:**
- New method calls `POST /api/v1/sop/compliance/check?target_role={role}`
- Accepts `call_id` and `target_role` parameters
- Initiates fresh compliance check (vs. GET which retrieves existing results)

**Backward compatibility:**
- ✅ **Fully backward compatible** - New method, doesn't affect existing `check_compliance()` GET method
- No feature flag needed

**Status:**
- ⚠️ **PLANNED, not yet implemented** - Currently only GET endpoint is used

---

### D3. Update document ingestion callers to pass `target_role`

**Files to touch:**
- `app/tasks/onboarding_tasks.py`
- `app/routes/rag.py`

**Functions/classes to modify:**
- `ingest_document_with_shunya()` - Extract `target_role` from `document.role_target` and pass to `uwc_client.ingest_document()`
- `routes/rag.py::upload_document()` - Extract `target_role` from user role context and pass to `uwc_client.ingest_document()`

**Behavior after change:**
- Document ingestion tasks extract `target_role` from document metadata or user context
- Pass `target_role` to `uwc_client.ingest_document()` to satisfy Shunya contract requirement

**Backward compatibility:**
- ⚠️ **Breaking change** - Shunya requires `target_role` for document ingestion
- Must update all callers to provide `target_role`
- Documents without `role_target` should default to user's role or `sales_rep`

---

## E. Personal Otto (Planned)

### E1. Add Personal Otto methods to `UWCClient`

**Files to touch:**
- `app/services/uwc_client.py`

**Functions/classes to create:**
- `UWCClient.ingest_training_documents()` - `POST /api/v1/personal-otto/ingest/training-documents`
- `UWCClient.train_personal_otto()` - `POST /api/v1/personal-otto/train`
- `UWCClient.get_personal_otto_profile_status()` - `GET /api/v1/personal-otto/profile/status`
- `UWCClient.get_personal_otto_profile()` - `GET /api/v1/personal-otto/profile`

**Behavior after change:**
- All methods **require** `X-Target-Role` header (per Shunya contract)
- Methods accept `target_role` parameter and set header automatically
- Returns Personal Otto profile, training status, and recommendations

**Backward compatibility:**
- ✅ **Fully backward compatible** - New methods, doesn't affect existing code
- Feature flag: `ENABLE_PERSONAL_OTTO=true` (default: `false`)

**Status:**
- ⚠️ **PLANNED, not yet implemented** - Mark as future enhancement

---

### E2. Create Personal Otto backend routes

**Files to touch:**
- `app/routes/personal_otto.py` (new file)

**Functions/classes to create:**
- `POST /api/v1/personal-otto/ingest` - Upload training documents
- `POST /api/v1/personal-otto/train` - Trigger training job
- `GET /api/v1/personal-otto/profile/status` - Get training status
- `GET /api/v1/personal-otto/profile` - Get Personal Otto profile

**Behavior after change:**
- New routes expose Personal Otto functionality to frontend
- Routes extract `target_role` from user context and pass to Shunya
- Store training job status in database for tracking

**Backward compatibility:**
- ✅ **Fully backward compatible** - New routes, doesn't affect existing endpoints
- Feature flag: `ENABLE_PERSONAL_OTTO=true` (default: `false`)

**Status:**
- ⚠️ **PLANNED, not yet implemented** - Mark as future enhancement

---

## F. Enum/Schema Alignment

### F1. Add `service_not_offered` to `BookingStatus` enum

**Files to touch:**
- `app/models/call.py` (or wherever `BookingStatus` is defined)
- `app/schemas/call.py` (Pydantic schemas)

**Functions/classes to modify:**
- `BookingStatus` enum - Add `SERVICE_NOT_OFFERED = "service_not_offered"` value
- Update Pydantic schemas to include new value

**Behavior after change:**
- `BookingStatus` enum includes `booked`, `not_booked`, `service_not_offered` (per Shunya canonical enum)
- Database migration may be needed if enum is stored as PostgreSQL enum type
- API responses can return `service_not_offered` value

**Backward compatibility:**
- ⚠️ **Database migration required** - If using PostgreSQL enum type, need migration
- Existing `booked`/`not_booked` values continue to work
- Feature flag: Not needed (enum addition is backward compatible)

---

### F2. Create `ActionType` enum from Shunya canonical values

**Files to touch:**
- `app/models/task.py` (or new `app/models/enums.py`)
- `app/schemas/task.py` (Pydantic schemas)

**Functions/classes to create/modify:**
- `ActionType` enum - Create enum with 30 canonical values from Shunya
- Update `Task` model to use enum (currently free-form string)
- Update Pydantic schemas

**Behavior after change:**
- `ActionType` enum includes all 30 Shunya canonical values (e.g., `call_back`, `send_quote`, `schedule_appointment`, etc.)
- `Task.action_type` field uses enum instead of free-form string
- API validation ensures only canonical values are accepted

**Backward compatibility:**
- ⚠️ **Breaking change** - Migration from free-form string to enum
- Database migration required to map existing string values to enum
- Feature flag: `ENABLE_ACTION_TYPE_ENUM=true` (default: `false`) for gradual migration

**Migration strategy:**
- Phase 1: Add enum, keep accepting strings (coerce strings to enum)
- Phase 2: Validate enum values, reject invalid strings
- Phase 3: Remove string support, require enum only

---

### F3. Add `AppointmentType` enum

**Files to touch:**
- `app/models/appointment.py`
- `app/schemas/appointment.py`

**Functions/classes to create/modify:**
- `AppointmentType` enum - Create enum with values: `in_person`, `virtual`, `phone`
- Update `Appointment` model to use enum (if currently free-form string)

**Behavior after change:**
- `AppointmentType` enum includes `in_person`, `virtual`, `phone` (per Shunya canonical enum)
- API validation ensures only canonical values are accepted

**Backward compatibility:**
- ⚠️ **Breaking change** - If currently free-form string, migration required
- Feature flag: `ENABLE_APPOINTMENT_TYPE_ENUM=true` (default: `false`)

---

### F4. Add `CallOutcomeCategory` enum

**Files to touch:**
- `app/models/call.py` (or `app/models/analysis.py`)
- `app/schemas/call.py`

**Functions/classes to create/modify:**
- `CallOutcomeCategory` enum - Create enum with values: `qualified_and_booked`, `qualified_service_not_offered`, `qualified_but_unbooked`
- Add field to `CallAnalysis` or `Call` model

**Behavior after change:**
- `CallOutcomeCategory` enum computed from `qualification_status` + `booking_status`
- Stored in call analysis results
- Exposed via API responses

**Backward compatibility:**
- ✅ **Fully backward compatible** - New computed field, doesn't break existing code
- No feature flag needed

---

### F5. Add `MeetingPhase` enum

**Files to touch:**
- `app/models/recording_session.py` (or `app/models/analysis.py`)
- `app/schemas/recording_session.py`

**Functions/classes to create/modify:**
- `MeetingPhase` enum - Create enum with values: `rapport_agenda`, `proposal_close`
- Update `MeetingSegmentation` model to use enum

**Behavior after change:**
- `MeetingPhase` enum used in meeting segmentation results
- Stored in `meeting_segments` array in analysis results

**Backward compatibility:**
- ✅ **Fully backward compatible** - New enum for existing feature
- No feature flag needed

---

### F6. Add `MissedOpportunityType` enum

**Files to touch:**
- `app/models/call.py` (or `app/models/analysis.py`)
- `app/schemas/call.py`

**Functions/classes to create/modify:**
- `MissedOpportunityType` enum - Create enum with values: `discovery`, `cross_sell`, `upsell`, `qualification`
- Add field to `OpportunityAnalysis` or `CallAnalysis` model

**Behavior after change:**
- `MissedOpportunityType` enum used in opportunity analysis results
- Stored in `missed_opportunities` array in analysis results

**Backward compatibility:**
- ✅ **Fully backward compatible** - New enum for existing feature
- No feature flag needed

---

### F7. Enforce `CallType` enum (currently free-form string)

**Files to touch:**
- `app/models/call.py`
- `app/schemas/call.py`

**Functions/classes to modify:**
- `CallType` enum - Create enum with values: `sales_call`, `csr_call`
- Update `Call.call_type` field to use enum instead of free-form string

**Behavior after change:**
- `CallType` enum enforced in database and API
- Only `sales_call` and `csr_call` values accepted

**Backward compatibility:**
- ⚠️ **Breaking change** - Migration from free-form string to enum
- Database migration required
- Feature flag: `ENABLE_CALL_TYPE_ENUM=true` (default: `false`)

---

## Implementation Priority

### Critical (Must fix before production)
1. **A1-A3**: Core `target_role` plumbing (required for Personal Otto, SOP ingestion)
2. **B1-B2**: Ask Otto endpoint alignment (currently using wrong endpoint)
3. **D1, D3**: Document ingestion `target_role` (Shunya requires it)

### Important (Should fix soon)
4. **F1**: `BookingStatus.service_not_offered` (enum alignment)
5. **F2**: `ActionType` enum (migration from free-form string)

### Nice to have (Future enhancements)
6. **B3**: Ask Otto streaming support
7. **C1-C2**: Follow-up recommendations
8. **D2**: POST compliance check endpoint
9. **E1-E2**: Personal Otto support
10. **F3-F7**: Remaining enum alignments

---

## Feature Flags Summary

| Feature Flag | Default | Purpose |
|--------------|---------|---------|
| `ENABLE_ASK_OTTO_V2` | `false` | Use canonical `/api/v1/ask-otto/query` endpoint |
| `ENABLE_ASK_OTTO_STREAMING` | `false` | Enable SSE streaming for Ask Otto |
| `ENABLE_FOLLOWUP_RECOMMENDATIONS` | `false` | Enable follow-up recommendations feature |
| `ENABLE_PERSONAL_OTTO` | `false` | Enable Personal Otto features |
| `ENABLE_ACTION_TYPE_ENUM` | `false` | Enforce ActionType enum (vs. free-form string) |
| `ENABLE_APPOINTMENT_TYPE_ENUM` | `false` | Enforce AppointmentType enum |
| `ENABLE_CALL_TYPE_ENUM` | `false` | Enforce CallType enum |

---

## Testing Checklist

After implementing changes, test:

- [ ] Ask Otto with `sales_rep` role → `X-Target-Role: sales_rep` header sent
- [ ] Ask Otto with `csr` role → `X-Target-Role: customer_rep` header sent
- [ ] Document ingestion with `target_role` query parameter → Shunya accepts request
- [ ] Personal Otto training with `X-Target-Role` header → No 400 errors
- [ ] Compliance POST check with `target_role` query parameter → Shunya accepts request
- [ ] Follow-up recommendations with `X-Target-Role` header → Returns recommendations
- [ ] Enum values match Shunya canonical values in API responses
- [ ] Backward compatibility: Existing endpoints still work without `target_role`
- [ ] Feature flags: Can toggle new features on/off

---

**Last Updated**: 2025-01-20  
**Next Review**: After implementation begins

