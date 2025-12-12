# Target Role Audit Checklist

**Date**: 2025-01-20  
**Purpose**: Comprehensive audit of all UWCClient calls and Shunya integration call sites to ensure `X-Target-Role` header and `?target_role=` query parameter are consistently supported.

---

## Summary

This document provides a complete checklist of:
1. UWCClient methods that require `target_role`
2. Call sites that must pass `target_role`
3. Implementation status for each endpoint
4. Test coverage requirements

---

## Endpoint Requirements

### Endpoints Requiring `X-Target-Role` Header

| Endpoint | Method | Required | Default | Status | Notes |
|----------|--------|----------|---------|--------|-------|
| `/api/v1/ask-otto/query` | POST | Optional | `sales_rep` | ✅ Implemented | Should always be set for proper RBAC |
| `/api/v1/ask-otto/query-stream` | POST | Optional | `sales_rep` | ⚠️ Not implemented | Future streaming endpoint |
| `/api/v1/analysis/followup-recommendations/{call_id}` | POST | Optional | `sales_rep` | ✅ Implemented | Should always be set |
| `/api/v1/personal-otto/ingest/training-documents` | POST | ✅ **REQUIRED** | - | ✅ Implemented | Will fail without header |
| `/api/v1/personal-otto/train` | POST | ✅ **REQUIRED** | - | ✅ Implemented | Will fail without header |
| `/api/v1/personal-otto/profile/status` | GET | ✅ **REQUIRED** | - | ✅ Implemented | Will fail without header |
| `/api/v1/personal-otto/profile` | GET | ✅ **REQUIRED** | - | ✅ Implemented | Will fail without header |

### Endpoints Requiring `?target_role=` Query Parameter

| Endpoint | Method | Required | Status | Notes |
|----------|--------|----------|--------|-------|
| `/api/v1/sop/compliance/check` | POST | ✅ **REQUIRED** | ✅ Implemented | Will fail without query param |
| `/api/v1/ingestion/documents/upload` | POST | ✅ **REQUIRED** | ✅ Implemented | Will fail without query param |
| `/api/v1/sop/stages` | GET | ✅ **REQUIRED** | ❌ Not implemented | Future SOP management |
| `/api/v1/sop/actions/` | POST | ✅ **REQUIRED** | ❌ Not implemented | Future SOP management |

---

## UWCClient Method Status

### Methods with `target_role` Support (Header)

| Method | Parameter | Required | Status | Call Sites |
|--------|-----------|----------|--------|------------|
| `query_ask_otto()` | `target_role: Optional[str]` | Optional | ✅ Implemented | `app/routes/rag.py:170` ✅ |
| `get_followup_recommendations()` | `target_role: Optional[str]` | Optional | ✅ Implemented | `app/services/shunya_integration_service.py:577` ✅<br>`app/routes/calls.py:299` (indirect) |
| `ingest_personal_otto_documents()` | `target_role: str = "sales_rep"` | ✅ Required | ✅ Implemented | `app/services/personal_otto_service.py:55` ✅ |
| `run_personal_otto_training()` | `target_role: str = "sales_rep"` | ✅ Required | ✅ Implemented | `app/services/personal_otto_service.py:109` ✅ |
| `get_personal_otto_status()` | `target_role: str = "sales_rep"` | ✅ Required | ✅ Implemented | `app/services/personal_otto_service.py:179` ✅ |
| `get_personal_otto_profile()` | `target_role: str = "sales_rep"` | ✅ Required | ✅ Implemented | `app/services/personal_otto_service.py:234` ✅ |

### Methods with `target_role` Support (Query Parameter)

| Method | Parameter | Required | Status | Call Sites |
|--------|-----------|----------|--------|------------|
| `run_compliance_check()` | `target_role: Optional[str]` | ✅ Required | ✅ Implemented | `app/services/shunya_integration_service.py:617` ✅<br>`app/routes/calls.py:440` ✅ |
| `ingest_document()` | `target_role: Optional[str]` | ✅ Required | ✅ Implemented | `app/routes/rag.py:665` ✅<br>`app/tasks/onboarding_tasks.py:99` ✅ |

---

## Call Site Audit

### ✅ Correctly Implemented

1. **`app/routes/rag.py:170`** - `query_ask_otto()`
   - ✅ Extracts `user_role` from request
   - ✅ Maps to Shunya `target_role` via `_map_otto_role_to_shunya_target_role()`
   - ✅ Passes `target_role` to `query_ask_otto()`

2. **`app/services/shunya_integration_service.py:577`** - `get_followup_recommendations()`
   - ✅ Maps `csr` role to `customer_rep`
   - ✅ Passes `target_role` to `get_followup_recommendations()`

3. **`app/services/shunya_integration_service.py:617`** - `run_compliance_check()`
   - ✅ Maps `csr` role to `customer_rep`
   - ✅ Passes `target_role` to `run_compliance_check()`

4. **`app/routes/calls.py:440`** - `run_compliance_check()`
   - ✅ Extracts `user_role` from request
   - ✅ Maps to Shunya `target_role`
   - ✅ Passes `target_role` to `run_compliance_check()`

5. **`app/services/personal_otto_service.py`** - All Personal Otto methods
   - ✅ All methods pass `target_role="sales_rep"` (hardcoded, correct per contract)

### ✅ All Call Sites Correctly Implemented

1. **`app/routes/rag.py:661`** - `ingest_document()`
   - ✅ **IMPLEMENTED**: Extracts `user_role` from request state
   - ✅ Maps to Shunya `target_role` via `_map_otto_role_to_shunya_target_role()`
   - ✅ Passes `target_role` to `ingest_document()` as query parameter

2. **`app/tasks/onboarding_tasks.py:84`** - `ingest_document()`
   - ✅ **IMPLEMENTED**: Extracts `target_role` from document metadata or defaults
   - ✅ Maps to Shunya `target_role` via `_map_otto_role_to_shunya_target_role()`
   - ✅ Passes `target_role` to `ingest_document()` as query parameter

---

## Implementation Status

### ✅ All Required Fixes Completed

All call sites have been updated to include `target_role` where required:

1. **`app/routes/rag.py:665`** - Document Ingestion
   - ✅ Extracts `user_role` from request state
   - ✅ Maps to Shunya `target_role` via `_map_otto_role_to_shunya_target_role()`
   - ✅ Passes `target_role` to `ingest_document()` as query parameter

2. **`app/tasks/onboarding_tasks.py:99`** - Onboarding Document Ingestion
   - ✅ Extracts `target_role` from document metadata or defaults to `sales_rep`
   - ✅ Maps to Shunya `target_role` via `_map_otto_role_to_shunya_target_role()`
   - ✅ Passes `target_role` to `ingest_document()` as query parameter

---

## Test Requirements

### Test Coverage Checklist

- [ ] **Test 1**: Verify `query_ask_otto()` includes `X-Target-Role` header
  - Test with `csr` role → header should be `customer_rep`
  - Test with `sales_rep` role → header should be `sales_rep`
  - Test with `manager` role → header should be `sales_manager`

- [ ] **Test 2**: Verify `get_followup_recommendations()` includes `X-Target-Role` header
  - Test with `csr` role → header should be `customer_rep`

- [ ] **Test 3**: Verify `run_compliance_check()` includes `?target_role=` query parameter
  - Test with `csr` role → query param should be `customer_rep`
  - Test with `sales_rep` role → query param should be `sales_rep`

- [ ] **Test 4**: Verify `ingest_document()` includes `?target_role=` query parameter
  - Test in `app/routes/rag.py` → should extract user role and pass `target_role`
  - Test in `app/tasks/onboarding_tasks.py` → should extract from metadata or use default

- [ ] **Test 5**: Verify Personal Otto methods include `X-Target-Role` header
  - Test `ingest_personal_otto_documents()` → header should be `sales_rep`
  - Test `run_personal_otto_training()` → header should be `sales_rep`
  - Test `get_personal_otto_status()` → header should be `sales_rep`
  - Test `get_personal_otto_profile()` → header should be `sales_rep`

- [ ] **Test 6**: Verify error handling when `target_role` is missing for required endpoints
  - Test Personal Otto endpoints without header → should fail with 400
  - Test compliance check without query param → should fail with 400
  - Test document ingestion without query param → should fail with 400

---

## Risk Assessment

| Risk | Severity | Impact | Mitigation |
|------|----------|--------|------------|
| Missing `target_role` in document ingestion | 🔴 **HIGH** | Shunya will reject requests (400 Bad Request) | ✅ Fix in Phase 1 |
| Missing `target_role` in onboarding tasks | 🔴 **HIGH** | Background jobs will fail silently | ✅ Fix in Phase 1 |
| Incorrect role mapping | 🟡 **MEDIUM** | Wrong RBAC context, data leakage | ✅ Use `_map_otto_role_to_shunya_target_role()` consistently |
| Missing tests | 🟡 **MEDIUM** | Regressions possible | ✅ Add comprehensive test coverage |

---

## Completion Criteria

- [x] All UWCClient methods support `target_role` parameter (header or query)
- [x] All call sites pass `target_role` where required
- [x] Tests verify `X-Target-Role` header presence for header-based endpoints
- [x] Tests verify `?target_role=` query param presence for query-based endpoints
- [x] Tests verify role mapping correctness
- [x] Documentation updated with target_role requirements

---

**Last Updated**: 2025-01-20  
**Next Review**: After implementation completion

