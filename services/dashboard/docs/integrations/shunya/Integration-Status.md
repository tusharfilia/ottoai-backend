# Otto Backend ↔ Shunya (ottoai-rag) Integration State

**Document Version**: 2.0  
**Last Updated**: 2025-12-08  
**Intended Audience**: Otto Backend Team, Shunya Team, Integration Engineers  
**Purpose**: Comprehensive documentation of current integration state, API endpoints, authentication, and potential issues

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Authentication & Security](#authentication--security)
4. [API Endpoints](#api-endpoints)
5. [Headers & Request Context](#headers--request-context)
6. [Target Role Handling](#target-role-handling)
7. [Data Flow & Processing](#data-flow--processing)
8. [Known Issues & Migration Notes](#known-issues--migration-notes)
9. [Testing & Validation](#testing--validation)
10. [Future Considerations](#future-considerations)

---

## Executive Summary

**Otto Backend** (App Team) integrates with **Shunya** (ottoai-rag, AI Services Team) for:
- **ASR/NLU**: Transcription and natural language understanding
- **Call Analysis**: Lead qualification, objection detection, compliance checking
- **AI Services**: Ask Otto (Q&A), Personal Otto (AI clones), Meeting Segmentation

**Integration Status**: ✅ **Production Ready**
- All core APIs implemented
- Authentication via JWT (HS256)
- Header-based request context (X-Request-ID, X-Company-ID, etc.)
- Idempotency support
- Webhook delivery
- SSE streaming for Ask Otto

**Critical Change**: `target_role` parameter migration from JWT token to explicit URL/header parameters (see [Target Role Handling](#target-role-handling))

---

## Architecture Overview

### Service Roles

| Service | Repository | Team | Responsibility |
|---------|-----------|------|----------------|
| **Otto Backend** | `ottoai-backend` | App Team | Frontend API, business logic, job orchestration |
| **Shunya** | `ottoai-rag` | Shunya Team | AI services (ASR, NLU, LLM, analysis) |

### Integration Pattern

```
┌─────────────────┐         HTTP/REST          ┌─────────────────┐
│  Otto Backend   │ ──────────────────────────> │     Shunya      │
│  (App Team)     │ <────────────────────────── │ (AI Services)   │
└─────────────────┘      Webhooks/SSE          └─────────────────┘
```

**Communication Methods:**
1. **Synchronous**: Direct HTTP requests for immediate responses
2. **Asynchronous**: Background jobs with webhook callbacks
3. **Streaming**: Server-Sent Events (SSE) for real-time responses

---

## Authentication & Security

### JWT Authentication

**Method**: HS256 (HMAC-SHA256)  
**Token TTL**: 5 minutes  
**Claims Required**:
- `user_id` (or `sub`)
- `company_id` (or `org_id`)
- `role` (optional, legacy - see [Target Role Handling](#target-role-handling))

**Header Format**:
```http
Authorization: Bearer <JWT_TOKEN>
```

**Implementation**:
- **Otto Backend**: Generates JWT tokens with user/company context
- **Shunya**: Validates tokens using shared secret (`JWT_SECRET_KEY`)
- **No Database Dependency**: User context extracted directly from token

### Security Headers

| Header | Purpose | Required | Source |
|--------|---------|----------|--------|
| `Authorization` | JWT token | ✅ Yes | Otto Backend |
| `X-Company-ID` | Explicit tenant context | ✅ Yes | Otto Backend |
| `X-Request-ID` | Request tracing | ✅ Yes | Otto Backend |
| `X-UWC-Timestamp` | Replay attack prevention | ✅ Yes | Otto Backend |
| `X-Signature` | HMAC payload verification | ✅ Yes | Otto Backend |
| `Idempotency-Key` | Exactly-once processing | 🟡 Mutating requests | Otto Backend |
| `X-UWC-Version` | API versioning | 🟡 Optional | Otto Backend |
| `X-Target-Role` | Role context (see below) | 🟡 Varies by endpoint | Otto Backend |

**Development Mode**: Swagger-friendly mode relaxes header validation for testing

---

## API Endpoints

### Core Analysis APIs

#### 1. Transcription
- **POST** `/api/v1/transcription/transcribe`
- **GET** `/api/v1/transcription/transcript/{call_id}`
- **Purpose**: ASR (Automatic Speech Recognition)

#### 2. Summarization
- **POST** `/api/v1/summarization/summarize`
- **GET** `/api/v1/analysis/summary/{call_id}`
- **Purpose**: Generate call summaries with pending actions

#### 3. Lead Qualification
- **POST** `/api/v1/lead-qualification/qualify`
- **GET** `/api/v1/analysis/qualification/{call_id}`
- **Purpose**: BANT scoring, qualification status, booking status

#### 4. Objection Detection
- **GET** `/api/v1/analysis/objections/{call_id}`
- **Purpose**: Detect and categorize objections

#### 5. Compliance Checking
- **GET** `/api/v1/sop/compliance/status?target_role={role}`
- **POST** `/api/v1/sop/compliance/check?target_role={role}`
- **Purpose**: SOP compliance analysis
- **Note**: `target_role` via **query parameter**

#### 6. Meeting Segmentation
- **POST** `/api/v1/meeting-segmentation/analyze`
- **GET** `/api/v1/analysis/meeting-segmentation/{call_id}`
- **Purpose**: Segment sales visits into phases

#### 7. Complete Analysis
- **GET** `/api/v1/analysis/complete/{call_id}`
- **Purpose**: Aggregated analysis results

### AI Services APIs

#### 8. Ask Otto (Q&A)
- **POST** `/api/v1/ask-otto/query`
- **POST** `/api/v1/ask-otto/query-stream` (SSE streaming)
- **GET** `/api/v1/ask-otto/conversations`
- **GET** `/api/v1/ask-otto/conversations/{conversation_id}`
- **GET** `/api/v1/ask-otto/suggested-questions`
- **Purpose**: Natural language Q&A with RBAC
- **Note**: `target_role` via **X-Target-Role header** (optional, defaults to `sales_rep`)

#### 9. Personal Otto (AI Clones)
- **POST** `/api/v1/personal-otto/ingest/training-documents`
- **POST** `/api/v1/personal-otto/train`
- **GET** `/api/v1/personal-otto/profile/status`
- **GET** `/api/v1/personal-otto/profile`
- **Purpose**: User-specific AI profile training
- **Note**: `target_role` via **X-Target-Role header** (required)

### SOP Management APIs

#### 10. SOP Stages
- **GET** `/api/v1/sop/stages?target_role={role}`
- **GET** `/api/v1/sop/stages/{stage_id}?target_role={role}`
- **POST** `/api/v1/sop/stages`
- **PUT** `/api/v1/sop/stages/{stage_id}`
- **DELETE** `/api/v1/sop/stages/{stage_id}`
- **Purpose**: SOP stage CRUD operations
- **Note**: `target_role` via **query parameter**

#### 11. SOP Actions
- **POST** `/api/v1/sop/actions/?target_role={role}`
- **Purpose**: Bulk operations (approve, activate, deactivate, delete)
- **Note**: `target_role` via **query parameter**

### Document Ingestion

#### 12. Document Upload
- **POST** `/api/v1/ingestion/documents?target_role={role}`
- **Purpose**: Upload SOP documents
- **Note**: `target_role` via **query parameter**

### Follow-up Recommendations

#### 13. Follow-up Recommendations
- **POST** `/api/v1/analysis/followup-recommendations/{call_id}`
- **Purpose**: AI-generated follow-up recommendations
- **Note**: `target_role` via **X-Target-Role header** (optional)

---

## Headers & Request Context

### Headers Sent by Otto Backend

All requests from Otto Backend to Shunya include:

#### Required Headers
```http
Authorization: Bearer <JWT_TOKEN>
X-Company-ID: <company_id>
X-Request-ID: <uuid>
X-UWC-Timestamp: <iso8601_timestamp>
X-Signature: <hmac_sha256_signature>
Content-Type: application/json
```

#### Optional Headers
```http
X-Target-Role: sales_rep|customer_rep|sales_manager|admin
X-UWC-Version: v1
Idempotency-Key: <uuid>  # For mutating requests
```

### Header Implementation Status in Shunya

| Header | Status | Implementation |
|--------|--------|----------------|
| `Authorization` | ✅ Implemented | JWT validation via `jwt_auth.py` |
| `X-Company-ID` | ✅ Implemented | Extracted and validated |
| `X-Request-ID` | ✅ Implemented | Logging context filter |
| `X-UWC-Timestamp` | ✅ Implemented | Replay attack prevention |
| `X-Signature` | ✅ Implemented | HMAC verification |
| `Idempotency-Key` | ✅ Implemented | Database-backed idempotency |
| `X-UWC-Version` | ✅ Implemented | API versioning |
| `X-Target-Role` | ✅ Implemented | Role context (see below) |

### Request ID Tracing

**Implementation**: Context-based logging filter
- `X-Request-ID` automatically injected into all log records
- Enables request tracing across services
- Development mode auto-generates if missing

---

## Target Role Handling

### ⚠️ **CRITICAL CHANGE: Migration from JWT to Explicit Parameters**

**Previous Implementation** (Legacy):
- `target_role` extracted from JWT token `role` claim
- Single role per user
- No multi-role support

**Current Implementation** (Active):
- `target_role` passed explicitly via:
  - **Query Parameter** (`?target_role=sales_rep`) - for GET requests
  - **Header** (`X-Target-Role: sales_rep`) - for POST requests
- Supports multi-role users
- Allows role context switching without re-authentication

### Current Endpoint Patterns

#### Pattern 1: Query Parameter (GET requests)
```python
target_role: str = Query(..., description="Target role")
```
**Endpoints**:
- `/api/v1/sop/stages?target_role={role}`
- `/api/v1/sop/compliance/status?target_role={role}`
- `/api/v1/sop/compliance/check?target_role={role}`
- `/api/v1/sop/actions/?target_role={role}`
- `/api/v1/ingestion/documents?target_role={role}`

#### Pattern 2: Header (POST requests, optional)
```python
target_role: str = Depends(get_target_role_optional)  # Defaults to "sales_rep"
```
**Endpoints**:
- `/api/v1/ask-otto/query` (optional)
- `/api/v1/ask-otto/query-stream` (optional)
- `/api/v1/ask-otto/conversations` (optional)
- `/api/v1/ask-otto/conversations/{conversation_id}` (optional)
- `/api/v1/ask-otto/suggested-questions` (optional)
- `/api/v1/analysis/followup-recommendations/{call_id}` (optional)

#### Pattern 3: Header (POST requests, required)
```python
target_role: str = Depends(get_target_role_from_header)  # Required
```
**Endpoints**:
- `/api/v1/personal-otto/ingest/training-documents` (required)
- `/api/v1/personal-otto/train` (required)
- `/api/v1/personal-otto/profile/status` (required)
- `/api/v1/personal-otto/profile` (required)

### Helper Functions

**Location**: `app/core/jwt_auth.py`

1. **`get_target_role_from_header()`** - Required header
   ```python
   async def get_target_role_from_header(
       x_target_role: str = Header(..., alias="X-Target-Role")
   ) -> str
   ```

2. **`get_target_role_optional()`** - Optional header (default: `sales_rep`)
   ```python
   async def get_target_role_optional(
       x_target_role: Optional[str] = Header(None, alias="X-Target-Role")
   ) -> str
   ```

3. **`validate_user_role_access()`** - RBAC validation
   ```python
   async def validate_user_role_access(
       target_role: str = Depends(get_target_role_from_header),
       current_user: UserContext = Depends(get_current_user)
   ) -> str
   ```

### Valid Target Roles

```python
VALID_TARGET_ROLES = ["sales_rep", "customer_rep", "sales_manager", "admin"]
```

### Security Rules

- **Admins**: Can act as any role
- **Sales Managers**: Can act as `sales_rep` or `customer_rep`
- **Regular Users**: Can only act as their own role (validated against JWT `role` claim)

---

## Data Flow & Processing

### Typical Call Analysis Flow

```
1. Otto Backend receives call recording
   ↓
2. POST /api/v1/transcription/transcribe
   → Returns: {task_id, transcript_id}
   ↓
3. Poll for transcript (or webhook callback)
   GET /api/v1/transcription/transcript/{call_id}
   → Returns: {transcript_text, speaker_segments}
   ↓
4. Trigger analysis (parallel or sequential)
   - POST /api/v1/summarization/summarize
   - POST /api/v1/lead-qualification/qualify
   - POST /api/v1/sop/compliance/check?target_role={role}
   ↓
5. Webhook notification (optional)
   POST {otto_backend_webhook_url}
   → Payload: {call_id, status, results}
   ↓
6. Otto Backend stores results
```

### Ask Otto Query Flow

```
1. User submits question
   POST /api/v1/ask-otto/query
   Headers: X-Target-Role: sales_rep
   ↓
2. Shunya classifies query
   → Query type: analytical|knowledge|hybrid
   → Intent: performance_analysis|objection_handling|...
   ↓
3. RBAC permission check
   → Validates role can access requested data
   ↓
4. Fetch data sources
   → Analytics API (Otto Backend)
   → RAG search (transcripts, SOPs)
   ↓
5. Generate response
   → LLM synthesis with citations
   ↓
6. Return answer
   → {answer, sources, confidence, metadata}
```

---

## Migration Notes

#### Swagger UI Testing

**Problem**: Swagger UI doesn't easily support custom headers:
- `X-Target-Role` header must be manually added
- Query parameters are easier to test in Swagger

**Impact**:
- Developers prefer query parameter endpoints for testing
- Inconsistent testing approach

**Current Mitigation**:
- Development mode auto-generates missing headers
- Swagger-friendly mode relaxes validation

**Recommendation**:
- Keep query parameters for GET endpoints (easier testing)
- Use headers for POST endpoints (cleaner API design)
- Provide Swagger UI examples with headers


#### Webhook Delivery

**Status**: ✅ **Done**
- `WEBHOOK_ENABLED` flag controls webhook delivery
- Graceful skipping if credentials missing
- No repeated failures with incorrect API key

#### Idempotency

**Status**: ✅ **Done**
- Database-backed idempotency implemented
- TTL-based cleanup
- Supports mutating requests

#### Request ID Logging

**Status**: ✅ **Done**
- Context-based logging filter
- Automatic `X-Request-ID` injection
- Request tracing enabled

---

## Testing & Validation

### Development Mode

**Swagger-Friendly Mode**: Relaxes header validation for easier testing
- Auto-generates `X-Request-ID` if missing
- Auto-generates `X-UWC-Timestamp` if missing
- Skips HMAC verification
- Skips timestamp validation

**Configuration**:
```env
ENVIRONMENT=development
SWAGGER_FRIENDLY_MODE=true
```

### Testing Endpoints

#### With Query Parameters
```bash
curl -X GET "api/v1/sop/stages?target_role=sales_rep" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "X-Company-ID: test_company_1"
```

#### With Headers
```bash
curl -X POST "/api/v1/ask-otto/query" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "X-Company-ID: test_company_1" \
  -H "X-Target-Role: sales_rep" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are my top objections?"}'
```

### SSE Streaming Test

**HTML Test Page**: `/static/test-sse.html`
- Interactive UI for testing streaming endpoints
- Real-time token display
- Event log
- Metadata visualization

---

## Future Considerations

### Recommended Improvements

1. **Standardize Target Role Handling**
   - Migrate all endpoints to `X-Target-Role` header
   - Remove query parameter approach
   - Consistent validation across all endpoints

2. **Enhanced RBAC**
   - Add role hierarchy support
   - Implement team-based permissions
   - Support custom role definitions

3. **API Versioning**
   - Explicit versioning strategy
   - Deprecation policy
   - Migration paths

4. **Documentation**
   - OpenAPI/Swagger spec updates
   - Integration examples
   - Error handling guides

5. **Monitoring & Observability**
   - Request tracing across services
   - Performance metrics
   - Error rate tracking

---

## Appendix

### Endpoint Summary Table

| Endpoint | Method | Target Role Source | Required | Default |
|----------|--------|-------------------|----------|---------|
| `/api/v1/sop/stages` | GET | Query Parameter | ✅ Yes | - |
| `/api/v1/sop/compliance/status` | GET | Query Parameter | ✅ Yes | - |
| `/api/v1/sop/compliance/check` | POST | Query Parameter | ✅ Yes | - |
| `/api/v1/sop/actions/` | POST | Query Parameter | ✅ Yes | - |
| `/api/v1/ingestion/documents` | POST | Query Parameter | ✅ Yes | - |
| `/api/v1/ask-otto/query` | POST | Header (X-Target-Role) | 🟡 Optional | `sales_rep` |
| `/api/v1/ask-otto/query-stream` | POST | Header (X-Target-Role) | 🟡 Optional | `sales_rep` |
| `/api/v1/ask-otto/conversations` | GET | Header (X-Target-Role) | 🟡 Optional | `sales_rep` |
| `/api/v1/personal-otto/ingest/training-documents` | POST | Header (X-Target-Role) | ✅ Yes | - |
| `/api/v1/personal-otto/train` | POST | Header (X-Target-Role) | ✅ Yes | - |
| `/api/v1/analysis/followup-recommendations/{call_id}` | POST | Header (X-Target-Role) | 🟡 Optional | `sales_rep` |

### Migration Checklist for Frontend Teams

- [ ] Update API clients to send `X-Target-Role` header for Ask Otto endpoints
- [ ] Update API clients to send `target_role` query parameter for SOP/Compliance endpoints
- [ ] Remove dependency on JWT `role` claim for role context
- [ ] Add role switching UI for multi-role users
- [ ] Update error handling for missing/invalid `target_role`
- [ ] Test with different role contexts
- [ ] Update integration tests

---

**Document Maintained By**: Shunya Team (ottoai-rag)  
**Last Review Date**: 2025-12-08  
**Next Review Date**: 2026-01-08

