# Target Role Implementation - Breaking Changes Analysis

**Date**: 2025-12-08  

---

## Executive Summary

Analysis of how Otto Backend calls Shunya APIs reveals **potential breaking changes** due to the `target_role` migration. Some endpoints require `target_role` but Otto Backend is not passing it, while others have endpoint mismatches.

---

## Findings

### ✅ **No Issues Found** (Endpoints Not Using target_role)

These endpoints are called correctly and don't require `target_role`:

1. **Transcription APIs** ✅
   - `POST /api/v1/transcription/transcribe` - No target_role needed
   - `GET /api/v1/transcription/transcript/{call_id}` - No target_role needed
   - **Status**: ✅ Working

2. **Summarization APIs** ✅
   - `POST /api/v1/summarization/summarize` - No target_role needed
   - `GET /api/v1/analysis/summary/{call_id}` - No target_role needed
   - **Status**: ✅ Working

3. **Lead Qualification APIs** ✅
   - `GET /api/v1/analysis/qualification/{call_id}` - No target_role needed
   - **Status**: ✅ Working

4. **Objection Detection APIs** ✅
   - `GET /api/v1/analysis/objections/{call_id}` - No target_role needed
   - **Status**: ✅ Working

5. **Meeting Segmentation APIs** ✅
   - `POST /api/v1/meeting-segmentation/analyze` - No target_role needed
   - `GET /api/v1/analysis/meeting-segmentation/{call_id}` - No target_role needed
   - **Status**: ✅ Working

6. **Complete Analysis API** ✅
   - `GET /api/v1/analysis/complete/{call_id}` - No target_role needed
   - **Status**: ✅ Working

---

### ⚠️ **POTENTIAL ISSUES** (Endpoints Requiring target_role)

#### Issue 1: Compliance Check Endpoint Mismatch

**Otto Backend Code** (`uwc_client.py:967-989`):
```python
async def check_compliance(
    self,
    company_id: str,
    request_id: str,
    call_id: int
) -> Dict[str, Any]:
    return await self._make_request(
        "GET",
        f"/api/v1/analysis/compliance/{call_id}",  # ❌ GET endpoint
        company_id,
        request_id
    )
```

**Shunya Endpoints**:
1. **GET** `/api/v1/analysis/compliance/{call_id}` - ✅ EXISTS
   - **Purpose**: Retrieve existing compliance check results
   - **target_role**: ❌ NOT REQUIRED (reads from stored `CallComplianceCheck.target_role`)
   - **Status**: ✅ **WORKING** - No breaking change

2. **POST** `/api/v1/sop/compliance/check?target_role={role}` - ✅ EXISTS
   - **Purpose**: RUN a new compliance check
   - **target_role**: ✅ **REQUIRED** (query parameter)
   - **Status**: ⚠️ **NOT CALLED BY OTTO BACKEND**

**Analysis**:
- Otto Backend calls the **GET** endpoint to retrieve compliance results
- This endpoint doesn't require `target_role` because it reads from the database
- **However**, if Otto Backend needs to **RUN** a new compliance check, it should call the **POST** endpoint with `target_role`
- **Current behavior**: Otto Backend likely runs compliance checks via the analysis pipeline, not directly via this endpoint

**Recommendation**:
- ✅ **No immediate fix needed** - GET endpoint works correctly
- ⚠️ **If Otto Backend needs to trigger compliance checks**, add a method that calls `POST /api/v1/sop/compliance/check?target_role={role}`

---

#### Issue 2: Ask Otto Endpoints - Missing X-Target-Role Header

**Otto Backend Code**: No direct calls found in `uwc_client.py`

**Shunya Endpoints** (require `X-Target-Role` header):
- `POST /api/v1/ask-otto/query` - Header optional (defaults to `sales_rep`)
- `POST /api/v1/ask-otto/query-stream` - Header optional (defaults to `sales_rep`)
- `GET /api/v1/ask-otto/conversations` - Header optional (defaults to `sales_rep`)
- `GET /api/v1/ask-otto/conversations/{conversation_id}` - Header optional (defaults to `sales_rep`)
- `GET /api/v1/ask-otto/suggested-questions` - Header optional (defaults to `sales_rep`)

**Analysis**:
- Ask Otto endpoints have `target_role` as **optional** with default `sales_rep`
- If Otto Backend doesn't pass `X-Target-Role` header, it will default to `sales_rep`
- **This may be incorrect** if the user is a `customer_rep` or has a different role

**Impact**:
- ⚠️ **Low-Medium**: Defaults to `sales_rep` which may be wrong for `customer_rep` users
- ⚠️ **RBAC**: Queries may be denied or return incorrect data if role context is wrong

**Recommendation**:
- ✅ **Add `X-Target-Role` header** to all Ask Otto API calls in Otto Backend
- Extract role from JWT token or user context
- Pass as header: `X-Target-Role: {user_role}`

**Example Fix**:
```python
# In uwc_client.py, add method:
async def query_ask_otto(
    self,
    company_id: str,
    request_id: str,
    question: str,
    target_role: str = "sales_rep",  # Extract from user context
    conversation_id: Optional[str] = None
) -> Dict[str, Any]:
    payload = {"question": question}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    
    headers = self._get_headers(company_id, request_id, payload)
    headers["X-Target-Role"] = target_role  # ✅ Add target_role header
    
    return await self._make_request(
        "POST",
        "/api/v1/ask-otto/query",
        company_id,
        request_id,
        payload,
        custom_headers=headers  # Need to modify _make_request to accept custom headers
    )
```

---

#### Issue 3: Personal Otto Endpoints - Missing X-Target-Role Header (REQUIRED)

**Otto Backend Code**: No direct calls found in `uwc_client.py`

**Shunya Endpoints** (require `X-Target-Role` header - **REQUIRED**):
- `POST /api/v1/personal-otto/ingest/training-documents` - ✅ **REQUIRED**
- `POST /api/v1/personal-otto/train` - ✅ **REQUIRED**
- `GET /api/v1/personal-otto/profile/status` - ✅ **REQUIRED**
- `GET /api/v1/personal-otto/profile` - ✅ **REQUIRED**

**Analysis**:
- Personal Otto endpoints **require** `X-Target-Role` header
- If Otto Backend calls these without the header, **requests will fail with 400 Bad Request**

**Impact**:
- 🔴 **HIGH**: Requests will **fail** if header is missing
- **Error**: `400 Bad Request - Missing required header: X-Target-Role`

**Recommendation**:
- 🔴 **CRITICAL FIX NEEDED**: Add `X-Target-Role` header to all Personal Otto API calls
- Extract role from user context (likely `sales_rep` or `customer_rep`)

**Example Fix**:
```python
# In uwc_client.py, add method:
async def train_personal_otto(
    self,
    company_id: str,
    request_id: str,
    user_id: str,
    target_role: str,  # REQUIRED: sales_rep or customer_rep
    training_examples: List[Dict[str, Any]],
    force_retrain: bool = False
) -> Dict[str, Any]:
    payload = {
        "training_examples": training_examples,
        "force_retrain": force_retrain
    }
    
    headers = self._get_headers(company_id, request_id, payload)
    headers["X-Target-Role"] = target_role  # ✅ REQUIRED
    
    return await self._make_request(
        "POST",
        "/api/v1/personal-otto/train",
        company_id,
        request_id,
        payload,
        custom_headers=headers
    )
```

---

#### Issue 4: SOP Management Endpoints - Missing target_role Query Parameter

**Otto Backend Code**: No direct calls found in `uwc_client.py`

**Shunya Endpoints** (require `target_role` query parameter):
- `GET /api/v1/sop/stages?target_role={role}` - ✅ **REQUIRED**
- `GET /api/v1/sop/stages/{stage_id}?target_role={role}` - ✅ **REQUIRED**
- `POST /api/v1/sop/actions/?target_role={role}` - ✅ **REQUIRED**
- `POST /api/v1/ingestion/documents?target_role={role}` - ✅ **REQUIRED**

**Analysis**:
- SOP endpoints **require** `target_role` as query parameter
- If Otto Backend calls these without the parameter, **requests will fail with 400 Bad Request**

**Impact**:
- 🔴 **HIGH**: Requests will **fail** if query parameter is missing
- **Error**: `400 Bad Request - Missing required query parameter: target_role`

**Recommendation**:
- 🔴 **CRITICAL FIX NEEDED**: Add `target_role` query parameter to all SOP API calls
- Extract role from user context

**Example Fix**:
```python
# In uwc_client.py, modify _make_request to support query params:
async def get_sop_stages(
    self,
    company_id: str,
    request_id: str,
    target_role: str,  # REQUIRED: sales_rep or customer_rep
    approval_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    # Build query string
    query_params = f"target_role={target_role}"
    if approval_status:
        query_params += f"&approval_status={approval_status}"
    query_params += f"&limit={limit}&offset={offset}"
    
    return await self._make_request(
        "GET",
        f"/api/v1/sop/stages?{query_params}",  # ✅ Include target_role
        company_id,
        request_id
    )
```

---

#### Issue 5: Follow-up Recommendations - Missing X-Target-Role Header

**Otto Backend Code**: No direct calls found in `uwc_client.py`

**Shunya Endpoint**:
- `POST /api/v1/analysis/followup-recommendations/{call_id}` - Header optional (defaults to `sales_rep`)

**Analysis**:
- Follow-up recommendations endpoint has `target_role` as **optional** with default `sales_rep`
- Similar to Ask Otto, defaults may be incorrect for `customer_rep` users

**Impact**:
- ⚠️ **Low-Medium**: Defaults to `sales_rep` which may be wrong

**Recommendation**:
- ✅ **Add `X-Target-Role` header** to follow-up recommendations calls
- Extract role from user context

---

## Summary of Breaking Changes

| Endpoint Category | Endpoint | Issue | Severity | Status |
|------------------|----------|-------|----------|--------|
| **Compliance** | `GET /api/v1/analysis/compliance/{call_id}` | ✅ No issue | ✅ Safe | Working |
| **Compliance** | `POST /api/v1/sop/compliance/check` | ⚠️ Not called | 🟡 Medium | Not used |
| **Ask Otto** | All Ask Otto endpoints | ⚠️ Missing header | 🟡 Medium | Defaults to sales_rep |
| **Personal Otto** | All Personal Otto endpoints | 🔴 Missing header | 🔴 **HIGH** | **Will fail** |
| **SOP Management** | All SOP endpoints | 🔴 Missing query param | 🔴 **HIGH** | **Will fail** |
| **Follow-up** | Follow-up recommendations | ⚠️ Missing header | 🟡 Medium | Defaults to sales_rep |

---

## Recommended Actions

### Immediate (Critical)

1. **Add `X-Target-Role` header to Personal Otto calls**
   - Extract role from user context
   - Pass as header: `X-Target-Role: {user_role}`
   - **Impact**: Prevents 400 errors

2. **Add `target_role` query parameter to SOP calls**
   - Extract role from user context
   - Pass as query param: `?target_role={user_role}`
   - **Impact**: Prevents 400 errors

### Short-term (Important)

3. **Add `X-Target-Role` header to Ask Otto calls**
   - Extract role from user context
   - Pass as header: `X-Target-Role: {user_role}`
   - **Impact**: Ensures correct RBAC and data filtering

4. **Add `X-Target-Role` header to Follow-up Recommendations**
   - Extract role from user context
   - Pass as header: `X-Target-Role: {user_role}`
   - **Impact**: Ensures correct role context

### Long-term (Nice to have)

5. **Standardize target_role handling**
   - Consider migrating all endpoints to use `X-Target-Role` header
   - Remove query parameter approach for consistency

6. **Add role extraction helper**
   - Create utility function to extract role from JWT or user context
   - Use consistently across all API calls

---

## Testing Checklist

After implementing fixes, test:

- [ ] Personal Otto training with `sales_rep` role
- [ ] Personal Otto training with `customer_rep` role
- [ ] SOP stages retrieval with `sales_rep` role
- [ ] SOP stages retrieval with `customer_rep` role
- [ ] Ask Otto queries with `sales_rep` role
- [ ] Ask Otto queries with `customer_rep` role
- [ ] Follow-up recommendations with different roles
- [ ] Error handling for invalid roles
- [ ] Error handling for missing roles

---

## Code Changes Required in Otto Backend

### 1. Modify `uwc_client.py` to support custom headers

```python
async def _make_request(
    self,
    method: str,
    endpoint: str,
    company_id: str,
    request_id: str,
    payload: Optional[dict] = None,
    retry_count: int = 0,
    custom_headers: Optional[Dict[str, str]] = None  # ✅ NEW
) -> Dict[str, Any]:
    # ... existing code ...
    headers = self._get_headers(company_id, request_id, payload)
    if custom_headers:
        headers.update(custom_headers)  # ✅ Merge custom headers
    # ... rest of method ...
```

### 2. Add role extraction helper

```python
def _extract_role_from_context(self, user_context: Optional[Dict[str, Any]] = None) -> str:
    """Extract role from user context or default to sales_rep"""
    if user_context and "role" in user_context:
        role = user_context["role"]
        if role in ["sales_rep", "customer_rep", "sales_manager", "admin"]:
            return role
    return "sales_rep"  # Default
```

### 3. Update all API methods to accept and pass target_role



**Document Maintained By**: Shunya Team (ottoai-rag)  
**Last Updated**: 2025-12-08  
**Next Review**: After Otto Backend team feedback

