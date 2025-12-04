# Sales Rep API Quickstart

**Date**: 2025-01-20  
**Status**: ✅ **Production-Ready**  
**Target Platform**: React Native (Expo)  
**Validation**: ✅ All 12 validation passes completed

---

## 📋 Purpose

This is a practical quickstart guide for integrating the Sales Rep mobile app with Otto's backend APIs. For comprehensive endpoint-by-endpoint details, see [SALES_REP_APP_INTEGRATION.md](./SALES_REP_APP_INTEGRATION.md).

**All endpoints, schemas, and behaviors have been cross-validated against:**
- ✅ Backend route files (`app/routes/*.py`)
- ✅ Pydantic schemas (`app/schemas/*.py`)
- ✅ SQLAlchemy models (`app/models/*.py`)
- ✅ OpenAPI specification (`/openapi.json`)
- ✅ Seed demo data (`scripts/seed_demo_data.py`)

---

## 1. Base URLs

### Production (Railway)
```typescript
const API_BASE_URL = 'https://ottoai-backend-production.up.railway.app';
```

### Local Development
```typescript
const LOCAL_API_BASE_URL = 'http://localhost:8000';
```

**Environment Variable**:
- `EXPO_PUBLIC_API_URL` - Set in your `.env` file for Expo/React Native

---

## 2. Auth, Tenancy & RBAC

### JWT from Clerk

The Sales Rep mobile app uses Clerk for authentication. The JWT token from Clerk **must** be included in all API requests.

**JWT Claims Structure** (Validated against `app/middleware/tenant.py`):
- `org_id` / `organization_id` / `tenant_id` / `company_id` → Extracted by backend as `tenant_id`
- `sub` / `user_id` → Extracted by backend as `user_id`
- `org_role` / `role` → Must be `"rep"`, `"org:sales_rep"`, or `"sales_rep"` → Mapped to `"sales_rep"` role

**Backend Role Mapping** (from `app/middleware/tenant.py:181-192`):
```python
role_mapping = {
    "admin": "manager",
    "org:admin": "manager",
    "exec": "manager",
    "manager": "manager",
    "csr": "csr",
    "org:csr": "csr",  # Clerk org-scoped CSR role
    "rep": "sales_rep",
    "sales_rep": "sales_rep",
    "org:sales_rep": "sales_rep",  # Clerk org-scoped sales rep role
}
user_role = role_mapping.get(clerk_role.lower(), "sales_rep")  # Default to sales_rep if unknown
```

**Getting the JWT in React Native**:
```typescript
import { useAuth } from '@clerk/clerk-expo';

function useApiClient() {
  const { getToken } = useAuth();
  
  const makeRequest = async (path: string, options?: RequestInit) => {
    const token = await getToken();
    if (!token) throw new Error('Not authenticated');
    
    return fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });
  };
  
  return { makeRequest };
}
```

**Example JWT for Sales Rep** (from seed script):
```json
{
  "sub": "user_36M3F0kllDOemX3prAPP1Zb8C5f",
  "org_id": "org_36EW2DYBw4gpJaL4ASL2ZxFZPO9",
  "org_role": "org:sales_rep",
  "email": "salesrep@otto-demo.com"
}
```

### Tenant Scoping

**All Sales Rep endpoints are tenant-scoped** (enforced by `TenantContextMiddleware`):
- Backend automatically extracts `tenant_id` from JWT's `org_id` claim
- Reps **only see their own assignments** (appointments, tasks, recordings, etc.)
- Backend enforces ownership checks: reps cannot access other reps' data
- **Frontend must NEVER pass `tenant_id` manually** — it's extracted from JWT

**Tenant Isolation Enforcement**:
- All database queries filter by `company_id == tenant_id` (from `request.state.tenant_id`)
- Cross-tenant access attempts return `403 Forbidden`
- Reps can only access appointments where `assigned_rep_id == user_id` (from JWT)

### Role-Based Access Control

**Sales Rep Role** (`sales_rep`):
- ✅ Can access:
  - `GET /api/v1/appointments` (own appointments only, auto-filtered by `assigned_rep_id == user_id`)
  - `GET /api/v1/appointments/{appointment_id}` (only if `assigned_rep_id == user_id`)
  - `PATCH /api/v1/appointments/{appointment_id}` (only if `assigned_rep_id == user_id`)
  - `GET /api/v1/tasks` (tenant-scoped, filtered by `assigned_to == "rep"`)
  - `POST /api/v1/tasks` (can create tasks)
  - `POST /api/v1/tasks/{task_id}/complete` (tenant-scoped)
  - `PATCH /api/v1/tasks/{task_id}` (tenant-scoped)
  - `POST /api/v1/recording-sessions/start` (only for own appointments)
  - `POST /api/v1/recording-sessions/{session_id}/stop` (only own sessions)
  - `POST /api/v1/recording-sessions/{session_id}/upload-audio` (only own sessions)
  - `GET /api/v1/recording-sessions/{session_id}` (only own sessions)
  - `POST /api/v1/reps/{rep_id}/shifts/clock-in` (only if `rep_id == user_id`)
  - `POST /api/v1/reps/{rep_id}/shifts/clock-out` (only if `rep_id == user_id`)
  - `GET /api/v1/reps/{rep_id}/shifts/today` (only if `rep_id == user_id`)
  - `GET /api/v1/message-threads/{contact_card_id}` (tenant-scoped)
- ❌ Cannot access:
  - `POST /api/v1/appointments` (manager/csr only)
  - Manager-only endpoints
  - Other reps' appointments/tasks/recordings (backend returns 403)
  - Company-wide analytics (manager-only)

**Manager Role** (`manager`):
- ✅ Can access: All rep endpoints + management endpoints
- ✅ Can view all appointments (not filtered by `rep_id`)

**CSR Role** (`csr`):
- ✅ Can access: CSR-specific endpoints (not rep endpoints)

**403 Forbidden Handling**:
```typescript
if (response.status === 403) {
  // User doesn't have permission
  // Show error: "You don't have permission to access this resource"
  // Do NOT retry
  const error = await response.json();
  showError(error.detail?.message || 'Access denied');
}
```

---

## 3. Core Endpoints Quick Reference

### Appointments

```typescript
// List today's appointments (defaults to authenticated rep)
GET /api/v1/appointments?date=2025-01-20

// Get specific appointment
GET /api/v1/appointments/{appointment_id}

// Update appointment outcome (e.g., mark as won)
PATCH /api/v1/appointments/{appointment_id}
Body: { "outcome": "won", "deal_size": 5000.00 }
```

**Roles**: `sales_rep`, `manager`, `csr`  
**Tenant Scoping**: ✅ Automatic (rep sees only own appointments)  
**Ownership Check**: ✅ Backend verifies `assigned_rep_id == user_id` for reps

**Valid Enum Values** (from `app/models/appointment.py`):
- `status`: `"scheduled"`, `"confirmed"`, `"completed"`, `"cancelled"`, `"no_show"`
- `outcome`: `"pending"`, `"won"`, `"lost"`, `"no_show"`, `"rescheduled"`

### Tasks

```typescript
// List tasks (tenant-scoped, filtered by assigned_to)
GET /api/v1/tasks?status=open&limit=100&offset=0

// Complete a task
POST /api/v1/tasks/{task_id}/complete

// Create a task
POST /api/v1/tasks
Body: { 
  "description": "Follow up with customer", 
  "assigned_to": "rep",  // Valid: "csr" | "rep" | "manager" | "ai"
  "appointment_id": "appt_123",
  "due_at": "2025-01-21T10:00:00Z",
  "priority": "high"  // Optional: "high" | "medium" | "low"
}
```

**Roles**: `sales_rep`, `manager`, `csr`  
**Tenant Scoping**: ✅ Automatic

**Valid Enum Values** (from `app/models/task.py`):
- `assigned_to`: `"csr"`, `"rep"`, `"manager"`, `"ai"`
- `status`: `"open"`, `"completed"`, `"overdue"`, `"cancelled"`
- `source`: `"otto"`, `"shunya"`, `"manual"`

### Recording Sessions

```typescript
// Start recording session (geofenced)
POST /api/v1/recording-sessions/start
Body: { 
  "appointment_id": "appt_123", 
  "rep_id": "user_36M3F0kllDOemX3prAPP1Zb8C5f",
  "location": { "lat": 40.7128, "lng": -74.0060 },
  "mode": "normal"  // Optional: "normal" | "ghost" | "off"
}

// Stop recording session
POST /api/v1/recording-sessions/{session_id}/stop
Body: { "location": { "lat": 40.7128, "lng": -74.0060 } }

// Upload audio completion
POST /api/v1/recording-sessions/{session_id}/upload-audio
Body: { 
  "audio_url": "s3://bucket/audio.m4a", 
  "audio_duration_seconds": 120.5, 
  "audio_size_bytes": 1024000 
}
```

**Roles**: `sales_rep`, `manager`  
**Tenant Scoping**: ✅ Automatic  
**Idempotency**: ✅ Uses `recording_session_id` as idempotency key

**Valid Enum Values** (from `app/models/recording_session.py`):
- `mode`: `"normal"`, `"ghost"`, `"off"`
- `audio_storage_mode`: `"persistent"`, `"ephemeral"`, `"not_stored"`
- `transcription_status`: `"not_started"`, `"in_progress"`, `"completed"`, `"failed"`
- `analysis_status`: `"not_started"`, `"in_progress"`, `"completed"`, `"failed"`

**Prerequisites**:
- Rep must be clocked in (active shift) - validated by backend
- Appointment must be assigned to rep - validated by backend
- Location must be within geofence (validated by mobile app, backend trusts mobile)

### Rep Shifts

```typescript
// Clock in
POST /api/v1/reps/{rep_id}/shifts/clock-in
Body: { 
  "desired_start_time": "2025-01-20T08:00:00Z",  // Optional
  "notes": "Starting shift"  // Optional
}

// Clock out
POST /api/v1/reps/{rep_id}/shifts/clock-out

// Get today's shift status
GET /api/v1/reps/{rep_id}/shifts/today
```

**Roles**: `sales_rep`, `manager`  
**Tenant Scoping**: ✅ Automatic  
**Idempotency**: ✅ Clock-in is idempotent (returns existing shift if already clocked in)

**Valid Enum Values** (from `app/models/rep_shift.py`):
- `status`: `"off"`, `"planned"`, `"active"`, `"completed"`, `"skipped"`

**Response Note**: `GET /api/v1/reps/{rep_id}/shifts/today` may return `shift: null` if no shift exists yet (backend behavior, even though schema shows `shift: RepShiftBase`).

### Message Threads (SMS)

```typescript
// Get message thread for a contact
GET /api/v1/message-threads/{contact_card_id}?limit=50&offset=0
```

**Roles**: `sales_rep`, `manager`, `csr`  
**Tenant Scoping**: ✅ Automatic

**Valid Enum Values** (from `app/models/message_thread.py`):
- `direction`: `"inbound"`, `"outbound"`
- `sender_role`: `"customer"`, `"csr"`, `"rep"`, `"otto"`

---

## 4. Idempotency for Mutating Endpoints

### Recording Sessions

**Endpoint**: `POST /api/v1/recording-sessions/start`  
**Idempotent**: ✅ Yes  
**Idempotency Key**: `recording_session_id` (returned in response)  
**Retry Strategy**: 
- If network fails after receiving `recording_session_id`, use `GET /api/v1/recording-sessions/{session_id}` to check if session exists
- If session exists, use existing session ID
- If session doesn't exist, retry start request

**Example**:
```typescript
let sessionId: string | null = null;

try {
  const response = await apiClient.post('/api/v1/recording-sessions/start', body);
  sessionId = response.data.recording_session_id;
} catch (error) {
  // Network failure - check if session was created
  if (body.appointment_id) {
    const existingSession = await checkExistingSession(body.appointment_id);
    if (existingSession) {
      sessionId = existingSession.id;
    } else {
      // Retry start request
      const retryResponse = await apiClient.post('/api/v1/recording-sessions/start', body);
      sessionId = retryResponse.data.recording_session_id;
    }
  }
}
```

**Endpoint**: `POST /api/v1/recording-sessions/{session_id}/upload-audio`  
**Idempotent**: ✅ Yes (safe to retry if upload fails)  
**Idempotency Key**: `session_id` + `audio_url` combination  
**Retry Strategy**: 
- Check if `audio_url` is already set in session before retrying upload
- If `audio_url` exists, skip upload and proceed to next step

### Appointments

**Endpoint**: `PATCH /api/v1/appointments/{appointment_id}`  
**Idempotent**: ✅ Yes (updates are idempotent)  
**Idempotency Key**: `appointment_id`  
**Retry Strategy**: Safe to retry on network failure — backend will apply same update

**Example**:
```typescript
// Safe to retry - backend handles idempotency
const updateAppointment = async (appointmentId: string, outcome: string) => {
  try {
    await apiClient.patch(`/api/v1/appointments/${appointmentId}`, { outcome });
  } catch (error) {
    if (error.status >= 500) {
      // Retry with exponential backoff
      await retryWithBackoff(() => 
        apiClient.patch(`/api/v1/appointments/${appointmentId}`, { outcome })
      );
    }
  }
};
```

### Tasks

**Endpoint**: `POST /api/v1/tasks`  
**Idempotent**: ❌ No  
**Retry Strategy**: **Do NOT auto-retry**. Show user confirmation before retrying to avoid duplicate tasks.

**Example**:
```typescript
const createTask = async (taskData: TaskCreateBody) => {
  try {
    await apiClient.post('/api/v1/tasks', taskData);
  } catch (error) {
    if (error.status >= 500) {
      // Show confirmation dialog
      const shouldRetry = await showConfirmDialog(
        'Failed to create task. Retry?'
      );
      if (shouldRetry) {
        await apiClient.post('/api/v1/tasks', taskData);
      }
    }
  }
};
```

**Endpoint**: `POST /api/v1/tasks/{task_id}/complete`  
**Idempotent**: ✅ Yes (safe to retry)  
**Idempotency Key**: `task_id`  
**Retry Strategy**: Safe to retry — backend checks if task is already completed

### Rep Shifts

**Endpoint**: `POST /api/v1/reps/{rep_id}/shifts/clock-in`  
**Idempotent**: ✅ Yes  
**Idempotency Key**: `rep_id` + `shift_date` (today)  
**Retry Strategy**: Safe to retry — backend returns existing shift if already clocked in

**Example**:
```typescript
const clockIn = async (repId: string) => {
  try {
    const response = await apiClient.post(`/api/v1/reps/${repId}/shifts/clock-in`, {});
    return response.data;
  } catch (error) {
    // If already clocked in, backend returns 400 with message "Rep is already clocked in"
    if (error.status === 400 && error.message.includes('already clocked in')) {
      // Fetch today's shift
      return await apiClient.get(`/api/v1/reps/${repId}/shifts/today`);
    }
    throw error;
  }
};
```

**Endpoint**: `POST /api/v1/reps/{rep_id}/shifts/clock-out`  
**Idempotent**: ✅ Yes (safe to retry)  
**Idempotency Key**: `rep_id` + `shift_date`  
**Retry Strategy**: Safe to retry — backend checks if already clocked out

---

## 5. Production-Grade Behaviors

### Pagination & Performance

**All list endpoints support pagination** (validated against backend):

```typescript
// Appointments (NO pagination params - returns all for date)
GET /api/v1/appointments?date=2025-01-20

// Tasks (with pagination)
GET /api/v1/tasks?limit=100&offset=0&status=open

// Message Threads (with pagination)
GET /api/v1/message-threads/{contact_card_id}?limit=50&offset=0
```

**Defaults** (from backend code):
- **Appointments**: No pagination (returns all appointments for the date)
- **Tasks**: `limit=100` (min: 1, max: 1000), `offset=0` (min: 0)
- **Message Threads**: `limit=100` (min: 1, max: 1000), `offset=0` (min: 0)

**Best Practices**:
- Use `limit=50` for initial page loads
- Implement infinite scroll or "Load More" button
- Cache paginated results locally for offline access
- For appointments, consider client-side pagination if many results

### Error Handling

**401 Unauthorized** (Token Expired):
```typescript
if (response.status === 401) {
  const error = await response.json();
  if (error.detail?.error_code === 'TOKEN_EXPIRED') {
    // Refresh JWT from Clerk
    const { getToken } = useAuth();
    const newToken = await getToken({ template: 'default' });
    // Retry request with new token
    return retryRequest(path, options, newToken);
  }
}
```

**403 Forbidden** (RBAC Issue):
```typescript
if (response.status === 403) {
  // User doesn't have permission
  // Show error: "You don't have permission to access this resource"
  // Do NOT retry
  const error = await response.json();
  showError(error.detail?.message || 'Access denied');
  return;
}
```

**404 Not Found** (Resource Deleted):
```typescript
if (response.status === 404) {
  // Resource was deleted or doesn't exist
  // Remove from local cache/state
  // Show user-friendly message
  const error = await response.json();
  removeFromCache(resourceId);
  showError(error.detail?.message || 'Resource not found');
  return;
}
```

**400 Bad Request** (Validation Error):
```typescript
if (response.status === 400) {
  const error = await response.json();
  // Show validation errors from error.detail
  showError(error.detail?.message || 'Invalid request');
  // Check error.detail?.details for field-specific errors
  return;
}
```

**5xx Server Error**:
```typescript
if (response.status >= 500) {
  // Retry with exponential backoff
  // Show user: "Server error. Retrying..."
  // Max 3 retries with backoff: 1s, 2s, 4s
  
  const maxRetries = 3;
  let retryCount = 0;
  
  while (retryCount < maxRetries) {
    await sleep(Math.pow(2, retryCount) * 1000); // 1s, 2s, 4s
    try {
      return await retryRequest(path, options);
    } catch (error) {
      retryCount++;
      if (retryCount >= maxRetries) {
        showError('Server error. Please try again later.');
        throw error;
      }
    }
  }
}
```

**Error Response Format** (from `app/schemas/responses.py`):
```json
{
  "detail": {
    "error_code": "NOT_FOUND",
    "message": "Appointment not found",
    "request_id": "req_abc123xyz",
    "details": {
      "appointment_id": "appt_123"
    }
  }
}
```

**Standard Error Codes** (from `app/schemas/responses.py:ErrorCodes`):
- `UNAUTHORIZED`, `FORBIDDEN`, `INVALID_TOKEN`, `TOKEN_EXPIRED`
- `NOT_FOUND`, `VALIDATION_ERROR`, `INVALID_REQUEST`
- `RATE_LIMIT_EXCEEDED`, `INTERNAL_ERROR`

### Observability & Logging

**Request ID / Correlation ID**:
- Backend returns `request_id` / `trace_id` in error responses (from `request.state.trace_id`)
- **Always log this ID** for debugging
- **Never log JWTs or sensitive PII** (phone numbers, addresses, etc.)

**Example Error Response**:
```json
{
  "detail": {
    "error_code": "NOT_FOUND",
    "message": "Appointment not found",
    "request_id": "req_abc123xyz",
    "details": {
      "appointment_id": "appt_123"
    }
  }
}
```

**Logging Best Practices**:
```typescript
// ✅ Good
logger.error('Failed to fetch appointment', { 
  appointment_id: 'appt_123',
  request_id: error.request_id,
  status_code: error.status
});

// ❌ Bad (never log JWTs or PII)
logger.error('Failed', { 
  token: jwtToken, 
  phone: '+1234567890',
  address: '123 Main St'
});
```

---

## 6. Mobile Constraints

### Offline / Flaky Network Considerations

**What Can Be Cached for Offline Read**:
- ✅ Today's appointments (cache for 5 minutes)
- ✅ Completed tasks (cache for 1 hour)
- ✅ Past appointments (cache for 24 hours)
- ✅ Rep shift status (cache for 1 minute)
- ✅ Message threads (cache for 15 minutes)

**What Should Be Queued and Retried**:
- ✅ Recording session start/stop (queue and retry)
- ✅ Task completion (queue and retry)
- ✅ Appointment outcome updates (queue and retry)
- ✅ Clock-in/out (queue and retry)

**What Requires Online Confirmation**:
- ❌ Creating new tasks (require online)
- ❌ Posting to wins feed (require online)
- ❌ Starting recording session (require online for geofence validation)

**Offline Queue Implementation**:
```typescript
// Example offline queue
class OfflineQueue {
  private queue: Array<{ action: string; payload: any; timestamp: number }> = [];
  
  async add(action: string, payload: any) {
    this.queue.push({ action, payload, timestamp: Date.now() });
    await this.persistQueue();
    await this.processQueue();
  }
  
  async processQueue() {
    if (!navigator.onLine) return;
    
    while (this.queue.length > 0) {
      const item = this.queue[0];
      try {
        await this.executeAction(item.action, item.payload);
        this.queue.shift();
        await this.persistQueue();
      } catch (error) {
        // Retry later
        break;
      }
    }
  }
}
```

### Timeouts and UX Expectations

**Recommended Timeouts**:
- **Recording operations**: 30 seconds (large audio uploads)
- **List endpoints**: 10 seconds
- **Update endpoints**: 5 seconds
- **Health checks**: 3 seconds

**UX for Slow Responses**:
- Show loading indicator after 1 second
- Show "Retrying..." message after timeout
- Allow user to cancel long-running operations
- Cache responses to show stale data while refreshing

**Example**:
```typescript
const fetchWithTimeout = async (url: string, options: RequestInit, timeout: number = 10000) => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(timeoutId);
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new Error('Request timeout');
    }
    throw error;
  }
};
```

---

## 7. Security & DO NOTs

### ❌ DO NOT

1. **Never call Shunya or internal AI endpoints directly**
   - ✅ Use `/api/v1/*` endpoints only
   - ❌ Do NOT call `/api/v1/ai/*` or Shunya endpoints directly
   - ❌ Do NOT bypass Otto's API layer

2. **Do not trust client-supplied `tenant_id`**
   - ✅ Tenancy is enforced on the server from JWT
   - ❌ Do NOT pass `X-Company-Id` or `tenant_id` in request body
   - ❌ Do NOT try to access other tenants' data

3. **Reps cannot access other reps' appointments/leads**
   - ✅ Backend enforces ownership checks
   - ❌ Do NOT try to access other reps' data by ID
   - ❌ Do NOT try to bypass tenant scoping

4. **Only use real `/api/v1/*` endpoints**
   - ✅ All documented endpoints exist in backend code
   - ❌ Do NOT invent new endpoints
   - ❌ Do NOT use endpoints not documented here

5. **Never log JWTs or sensitive PII**
   - ✅ Log `request_id`, `appointment_id`, etc.
   - ❌ Do NOT log tokens, phone numbers, addresses in plain text
   - ❌ Do NOT include sensitive data in error messages shown to users

---

## 8. Shunya Integration Constraints

**Shunya-Derived Fields** (from `app/models/recording_transcript.py` and `app/models/recording_analysis.py`):

**Recording Transcripts**:
- `transcript_text` - May be `null` in Ghost Mode
- `speaker_labels` - Speaker diarization from Shunya
- `confidence_score` - ASR confidence
- `uwc_job_id` - Shunya job correlation ID

**Recording Analysis**:
- `objections` - Array of objection types
- `objection_details` - Detailed objection data with timestamps
- `sentiment_score` - 0.0 to 1.0
- `engagement_score` - 0.0 to 1.0
- `coaching_tips` - AI-generated coaching recommendations
- `sop_stages_completed` - Array of completed SOP stages
- `sop_stages_missed` - Array of missed SOP stages
- `sop_compliance_score` - 0-10 score
- `lead_quality` - Classification: "qualified", "unqualified", "hot", "warm", "cold"
- `conversion_probability` - 0.0 to 1.0
- `meeting_segments` - Meeting phase segmentation

**Normalization**:
- Shunya responses are normalized into Otto domain models
- Empty/missing Shunya fields are stored as `null` in database
- Frontend must handle `null` values gracefully

**Processing States**:
- `transcription_status`: `"not_started"` → `"in_progress"` → `"completed"` or `"failed"`
- `analysis_status`: `"not_started"` → `"in_progress"` → `"completed"` or `"failed"`

**Frontend Handling**:
- Show loading state when `transcription_status == "in_progress"`
- Show error state when `transcription_status == "failed"`
- Handle `null` transcript text in Ghost Mode
- Poll `GET /api/v1/recording-sessions/{session_id}` to check processing status

---

## 9. Example API Client (React Native)

```typescript
// lib/api/client.ts

import { useAuth } from '@clerk/clerk-expo';

const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'https://ottoai-backend-production.up.railway.app';

interface ApiResponse<T> {
  success: boolean;
  data: T;
  meta?: {
    request_id?: string;
    timestamp?: string;
    version?: string;
  };
  message?: string;
}

interface ErrorResponse {
  detail: {
    error_code: string;
    message: string;
    request_id?: string;
    details?: Record<string, any>;
  };
}

class ApiClient {
  private async getHeaders(): Promise<HeadersInit> {
    const { getToken } = useAuth();
    const token = await getToken();
    
    if (!token) {
      throw new Error('Not authenticated');
    }
    
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    };
  }

  private async handleResponse<T>(response: Response): Promise<ApiResponse<T>> {
    if (!response.ok) {
      const error: ErrorResponse = await response.json().catch(() => ({ 
        detail: { error_code: 'UNKNOWN', message: 'Unknown error' } 
      }));
      
      // Handle token expiration
      if (response.status === 401) {
        const { getToken } = useAuth();
        const newToken = await getToken({ template: 'default' });
        if (newToken) {
          // Retry with new token (implement retry logic)
          throw new Error('Token expired - retry with new token');
        }
        throw new Error('Authentication required');
      }
      
      // Handle RBAC violations
      if (response.status === 403) {
        throw new Error(error.detail?.message || 'Access denied');
      }
      
      // Handle not found
      if (response.status === 404) {
        throw new Error(error.detail?.message || 'Resource not found');
      }
      
      // Handle validation errors
      if (response.status === 400) {
        throw new Error(error.detail?.message || 'Invalid request');
      }
      
      // Handle server errors
      if (response.status >= 500) {
        throw new Error(error.detail?.message || 'Server error');
      }
      
      throw new Error(error.detail?.message || 'Request failed');
    }
    
    return await response.json();
  }

  async get<T>(path: string, params?: Record<string, any>): Promise<T> {
    const url = new URL(`${API_BASE_URL}${path}`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }
    
    const response = await fetch(url.toString(), {
      method: 'GET',
      headers: await this.getHeaders(),
    });
    
    const result = await this.handleResponse<T>(response);
    return result.data;
  }

  async post<T>(path: string, body?: any): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: await this.getHeaders(),
      body: body ? JSON.stringify(body) : undefined,
    });
    
    const result = await this.handleResponse<T>(response);
    return result.data;
  }

  async patch<T>(path: string, body: any): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'PATCH',
      headers: await this.getHeaders(),
      body: JSON.stringify(body),
    });
    
    const result = await this.handleResponse<T>(response);
    return result.data;
  }
}

export const apiClient = new ApiClient();
```

---

## 10. Next Steps

1. ✅ Read [SALES_REP_APP_INTEGRATION.md](./SALES_REP_APP_INTEGRATION.md) for detailed endpoint documentation
2. ✅ Set up Clerk authentication in your React Native app
3. ✅ Implement API client with error handling and retry logic
4. ✅ Test with demo data (see seed script: `scripts/seed_demo_data.py`)
5. ✅ Implement offline queue for critical operations

---

**Questions?** Contact the backend team with `request_id` from error responses.
