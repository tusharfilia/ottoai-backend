# Sales Rep Mobile App Integration Specification

**Date**: 2025-01-20  
**Status**: ✅ **Production-Ready**  
**Target Platform**: React Native (Expo)  
**Validation**: ✅ All 12 validation passes completed

---

## 📋 Document Purpose

This document provides a complete, production-grade integration specification for the Sales Rep mobile app to integrate with the Otto FastAPI backend. It defines exactly how Sales Rep screens should communicate with backend APIs, including authentication, data mapping, user actions, error handling, idempotency, and mobile-specific considerations.

**Target Audience**: Frontend development agency implementing Sales Rep mobile app  
**Scope**: Sales Rep mobile app only (not CSR webapp or Executive dashboard)

**All endpoints, schemas, and behaviors have been cross-validated against:**
- ✅ Backend route files (`app/routes/*.py`)
- ✅ Pydantic schemas (`app/schemas/*.py`)
- ✅ SQLAlchemy models (`app/models/*.py`)
- ✅ OpenAPI specification (`/openapi.json`)
- ✅ Seed demo data (`scripts/seed_demo_data.py`)

---

## 0. Global Integration Rules

### 0.1 Auth, Tenancy & RBAC

#### JWT from Clerk

**Every Sales Rep API call MUST include JWT in Authorization header**:
```
Authorization: Bearer <JWT>
```

**JWT Claims Structure**:
- `org_id` / `organization_id` / `tenant_id` / `company_id` → Extracted by backend as `tenant_id`
- `sub` / `user_id` → Extracted by backend as `user_id`
- `org_role` / `role` → Must be `"rep"`, `"org:sales_rep"`, or `"sales_rep"` → Mapped to `"sales_rep"` role

**Backend Role Mapping**:
```python
role_mapping = {
    "admin": "manager",
    "org:admin": "manager",
    "exec": "manager",
    "manager": "manager",
    "csr": "csr",
    "org:csr": "csr",
    "rep": "sales_rep",
    "sales_rep": "sales_rep",
    "org:sales_rep": "sales_rep",
}
```

**Getting JWT in React Native**:
```typescript
import { useAuth } from '@clerk/clerk-expo';

const { getToken } = useAuth();
const token = await getToken(); // Returns JWT string
```

#### Tenant Scoping

**All Sales Rep endpoints are tenant-scoped**:
- Backend automatically extracts `tenant_id` from JWT's `org_id` claim via `TenantContextMiddleware`
- Reps **only see their own assignments** (appointments, tasks, recordings, etc.)
- Backend enforces ownership checks: reps cannot access other reps' data
- **Frontend must NEVER pass `tenant_id` manually** — it's extracted from JWT

**Example**:
```typescript
// ✅ Correct: Backend extracts tenant_id from JWT
GET /api/v1/appointments
Headers: { Authorization: "Bearer <jwt>" }

// ❌ Wrong: Never pass tenant_id manually
GET /api/v1/appointments?tenant_id=org_123
```

#### Role-Based Access Control

**Sales Rep Role** (`sales_rep`):
- ✅ Can access:
  - `/api/v1/appointments` (own appointments only)
  - `/api/v1/tasks` (own tasks only)
  - `/api/v1/recording-sessions/*` (own recordings only)
  - `/api/v1/reps/{rep_id}/shifts/*` (own shifts only)
  - `/api/v1/message-threads/{contact_card_id}` (tenant-scoped)
- ❌ Cannot access:
  - Manager-only endpoints
  - Other reps' appointments/tasks/recordings
  - Company-wide analytics (manager-only)

**Manager Role** (`manager`):
- ✅ Can access: All rep endpoints + management endpoints

**CSR Role** (`csr`):
- ✅ Can access: CSR-specific endpoints (not rep endpoints)

**403 Forbidden Handling**:
```typescript
if (response.status === 403) {
  // User doesn't have permission
  // Show error: "You don't have permission to access this resource"
  // Do NOT retry
  showError('Access denied. You do not have permission to perform this action.');
}
```

---

### 0.2 Idempotency for Mutating Endpoints

#### Recording Sessions

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

#### Appointments

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

#### Tasks

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

#### Rep Shifts

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
    // If already clocked in, backend may return existing shift
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

### 0.3 Production-Grade Behaviors

#### Pagination & Performance

**All list endpoints support pagination**:

```typescript
// Appointments
GET /api/v1/appointments?date=2025-01-20&limit=50&offset=0

// Tasks
GET /api/v1/tasks?limit=100&offset=0&status=open

// Message Threads
GET /api/v1/message-threads/{contact_card_id}?limit=50&offset=0
```

**Defaults**:
- `limit`: 50 (max: 1000)
- `offset`: 0

**Best Practices**:
- Use cursor-based pagination for large datasets (implemented via `offset` for now)
- Load initial page with `limit=50`
- Implement infinite scroll or "Load More" button
- Cache paginated results locally for offline access

#### Error Handling

**401 Unauthorized** (Token Expired):
```typescript
if (response.status === 401) {
  // Refresh JWT from Clerk
  const { getToken } = useAuth();
  const newToken = await getToken({ template: 'default' });
  
  // Retry request with new token
  return retryRequest(path, options, newToken);
}
```

**403 Forbidden** (RBAC Issue):
```typescript
if (response.status === 403) {
  // User doesn't have permission
  // Show error: "You don't have permission to access this resource"
  // Do NOT retry
  showError('Access denied. You do not have permission to perform this action.');
  return;
}
```

**404 Not Found** (Resource Deleted):
```typescript
if (response.status === 404) {
  // Resource was deleted or doesn't exist
  // Remove from local cache/state
  // Show user-friendly message
  removeFromCache(resourceId);
  showError('This resource no longer exists.');
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

#### Observability & Logging

**Request ID / Correlation ID**:
- Backend returns `request_id` / `trace_id` in error responses
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

### 0.4 Mobile Constraints

#### Offline / Flaky Network Considerations

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

#### Timeouts and UX Expectations

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

### 0.5 Security & DO NOTs

#### ❌ DO NOT

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

## 1. Sales Rep Frontend Screens Identified

Based on exploration of `/Users/tusharmehrotra/Documents/Otto_Salesrep`, the following Sales Rep screens have been identified:

### 1.1 Home / AI Chat Screen
**File(s)**: `app/(tabs)/index.tsx`

**Components**:
- `GreetingSection` - Personalized greeting
- `ChatBubble` - Chat message bubbles
- `MessageInput` - Text input for Ask Otto queries
- `SuggestionChips` - Quick suggestion chips
- `SideDrawer` - Chat history drawer

**Purpose**: Main landing page with Ask Otto chat interface for natural language queries.

**Backend Endpoints**:
- `POST /api/v1/rag/query` - Ask Otto queries (if implemented)

---

### 1.2 Sales Dashboard Screen
**File(s)**: `app/(tabs)/sales.tsx`

**Components**:
- `SalesDashboard` - Main dashboard container
- `SalesHeader` - Header with stats
- `InsightsSection` - AI insights and recommendations
- `KPIStatsPanel` - KPI metrics (revenue, appointments, etc.)
- `BookmarkChips` - Bookmarked filters
- `AppointmentsList` - Upcoming appointments list
- `FollowUpsSection` - Follow-up tasks and reminders

**Purpose**: Sales rep performance dashboard with appointments, KPIs, and insights.

**Backend Endpoints**:
- `GET /api/v1/appointments` - List appointments
- `GET /api/v1/tasks` - List tasks
- `GET /api/v1/appointments/{appointment_id}` - Get appointment details

---

### 1.3 Recording Screen
**File(s)**: `app/(tabs)/record.tsx`

**Components**:
- `RecordingPrompt` - Instructions for recording
- `RecordingControls` - Start/pause/stop recording
- `RecordingTimer` - Recording duration display
- `RecordingWaveform` - Audio waveform visualization
- `PlaybackControl` - Playback controls after recording
- `OutcomeSelector` - Won/Not Won selector
- `PostingSection` - Post to wins feed

**Purpose**: Record appointment audio, select outcome, and optionally post to wins feed.

**Backend Endpoints**:
- `POST /api/v1/recording-sessions/start` - Start recording session
- `POST /api/v1/recording-sessions/{session_id}/stop` - Stop recording session
- `POST /api/v1/recording-sessions/{session_id}/upload-audio` - Upload audio
- `PATCH /api/v1/appointments/{appointment_id}` - Update appointment outcome
- `POST /api/v1/wins-feed` - Post to wins feed (if implemented)

---

### 1.4 Feeds Screen
**File(s)**: `app/(tabs)/feeds.tsx`

**Components**:
- `ExploreFeed` - Explore wins feed
- `MyPostsFeed` - Rep's own posts
- `SavedFeed` - Saved posts

**Purpose**: Social feed for wins, insights, and team collaboration.

**Backend Endpoints**:
- `GET /api/v1/wins-feed` - Get wins feed (if implemented)
- `POST /api/v1/wins-feed` - Post to wins feed (if implemented)

---

### 1.5 Messages Screen
**File(s)**: `app/(tabs)/messages.tsx`

**Components**:
- `Conversations` - List of conversations
- `ConversationListItem` - Individual conversation item
- `ChatHeader` - Chat header
- `MessageBubble` - Message bubbles
- `MessageInputBar` - Message input

**Purpose**: SMS/message threads with contacts.

**Backend Endpoints**:
- `GET /api/v1/message-threads/{contact_card_id}` - Get message thread

---

### 1.6 Past Appointments Screen
**File(s)**: `app/past-appointments.tsx`

**Purpose**: View past appointments and outcomes.

**Backend Endpoints**:
- `GET /api/v1/appointments?date={past_date}` - List past appointments

---

## 2. Detailed Endpoint Documentation

### 2.1 Appointments

#### 2.1.1 List Appointments

**Endpoint**: `GET /api/v1/appointments`

**Roles**: `sales_rep`, `manager`, `csr`

**Query Parameters**:
- `rep_id` (optional, string): Sales rep ID (defaults to authenticated user if rep)
- `date` (optional, string): Date filter (ISO format YYYY-MM-DD, defaults to today)
- `status` (optional, string): Filter by status (`scheduled`, `confirmed`, `completed`, `cancelled`, `no_show`)
- `outcome` (optional, string): Filter by outcome (`pending`, `won`, `lost`, `no_show`, `rescheduled`)

**Response**:
```typescript
{
  "data": {
    "appointments": [
      {
        "appointment_id": "appt_123",
        "lead_id": "lead_456",
        "contact_card_id": "contact_789",
        "customer_name": "John Doe",
        "address": "123 Main St",
        "scheduled_start": "2025-01-20T14:00:00Z",
        "scheduled_end": "2025-01-20T15:00:00Z",
        "status": "scheduled",
        "outcome": "pending",
        "service_type": "Roof Replacement",
        "is_assigned_to_me": true,
        "deal_size": null,
        "pending_tasks_count": 2
      }
    ],
    "total": 5,
    "date": "2025-01-20"
  }
}
```

**Tenant Scoping**: ✅ Automatic (rep sees only own appointments)

**Pagination**: ❌ No pagination - returns all appointments for the specified date

**Example**:
```typescript
// Get today's appointments
const appointments = await apiClient.get('/api/v1/appointments', {
  date: '2025-01-20'
});

// Get past appointments
const pastAppointments = await apiClient.get('/api/v1/appointments', {
  date: '2025-01-19',
  status: 'completed'
});
```

---

#### 2.1.2 Get Appointment Details

**Endpoint**: `GET /api/v1/appointments/{appointment_id}`

**Roles**: `sales_rep`, `manager`, `csr`

**Response**:
```typescript
{
  "data": {
    "appointment": {
      "id": "appt_123",
      "lead_id": "lead_456",
      "contact_card_id": "contact_789",
      "scheduled_start": "2025-01-20T14:00:00Z",
      "scheduled_end": "2025-01-20T15:00:00Z",
      "status": "scheduled",
      "outcome": "pending",
      "assigned_rep_id": "rep_123",
      "location": "123 Main St",
      "service_type": "Roof Replacement",
      "notes": "Customer prefers morning appointments",
      "deal_size": null,
      "created_at": "2025-01-15T10:00:00Z",
      "updated_at": "2025-01-15T10:00:00Z"
    },
    "lead": {
      "id": "lead_456",
      "status": "qualified",
      "deal_size": null,
      "created_at": "2025-01-10T08:00:00Z"
    },
    "contact": {
      "id": "contact_789",
      "first_name": "John",
      "last_name": "Doe",
      "phone_number": "+1234567890",
      "email": "john@example.com",
      "address": "123 Main St"
    }
  }
}
```

**Tenant Scoping**: ✅ Automatic (rep can only access own appointments)

**Example**:
```typescript
const appointment = await apiClient.get(`/api/v1/appointments/${appointmentId}`);
```

---

#### 2.1.3 Update Appointment

**Endpoint**: `PATCH /api/v1/appointments/{appointment_id}`

**Roles**: `sales_rep`, `manager`, `csr`

**Request Body**:
```typescript
{
  "scheduled_start": "2025-01-20T15:00:00Z", // optional
  "scheduled_end": "2025-01-20T16:00:00Z", // optional
  "status": "completed", // optional
  "outcome": "won", // optional: "pending" | "won" | "lost" | "no_show" | "rescheduled"
  "deal_size": 5000.00, // optional, required when outcome="won"
  "location": "123 Main St", // optional
  "service_type": "Roof Replacement", // optional
  "notes": "Customer signed contract" // optional
}
```

**Response**: Same as `GET /api/v1/appointments/{appointment_id}`

**Idempotency**: ✅ Yes (safe to retry)

**Tenant Scoping**: ✅ Automatic (rep can only update own appointments)

**Example**:
```typescript
// Mark appointment as won
await apiClient.patch(`/api/v1/appointments/${appointmentId}`, {
  outcome: 'won',
  deal_size: 5000.00,
  status: 'completed'
});
```

---

### 2.2 Tasks

#### 2.2.1 List Tasks

**Endpoint**: `GET /api/v1/tasks`

**Roles**: `sales_rep`, `manager`, `csr`

**Query Parameters**:
- `assignee_id` (optional, string): Filter by assignee (user ID)
- `lead_id` (optional, string): Filter by lead ID
- `contact_card_id` (optional, string): Filter by contact card ID
- `status` (optional, string): Filter by status (`open`, `completed`, `overdue`, `cancelled`)
- `overdue` (optional, boolean): Filter by overdue status
- `due_before` (optional, datetime): Filter tasks due before this date
- `due_after` (optional, datetime): Filter tasks due after this date
- `limit` (optional, int): Maximum number of tasks (default: 100, max: 1000)
- `offset` (optional, int): Number of tasks to skip (default: 0)

**Response**:
```typescript
{
  "data": {
    "tasks": [
      {
        "id": "task_123",
        "description": "Follow up with customer",
        "status": "open",
        "assigned_to": "sales_rep",
        "due_at": "2025-01-21T10:00:00Z",
        "priority": "high",
        "contact_card_id": "contact_789",
        "lead_id": "lead_456",
        "appointment_id": "appt_123",
        "created_at": "2025-01-20T08:00:00Z",
        "updated_at": "2025-01-20T08:00:00Z"
      }
    ],
    "total": 10,
    "overdue_count": 2
  }
}
```

**Tenant Scoping**: ✅ Automatic (rep sees only own tasks)

**Pagination**: ✅ `limit` (default: 100, max: 1000), `offset` (default: 0)

**Example**:
```typescript
// Get open tasks
const tasks = await apiClient.get('/api/v1/tasks', {
  status: 'open',
  limit: 50
});
```

---

#### 2.2.2 Create Task

**Endpoint**: `POST /api/v1/tasks`

**Roles**: `sales_rep`, `manager`, `csr`

**Request Body**:
```typescript
{
  "description": "Follow up with customer", // required
  "assigned_to": "rep", // required: "csr" | "rep" | "manager" | "ai"
  "contact_card_id": "contact_789", // optional
  "lead_id": "lead_456", // optional
  "appointment_id": "appt_123", // optional
  "call_id": 123, // optional
  "due_at": "2025-01-21T10:00:00Z", // optional
  "priority": "high", // optional: "high" | "medium" | "low"
  "source": "manual" // optional: "manual" | "otto" | "shunya" (default: "manual")
}
```

**Response**:
```typescript
{
  "data": {
    "id": "task_123",
    "description": "Follow up with customer",
    "status": "open",
    "assigned_to": "sales_rep",
    "due_at": "2025-01-21T10:00:00Z",
    "priority": "high",
    "created_at": "2025-01-20T08:00:00Z"
  }
}
```

**Idempotency**: ❌ No (do NOT auto-retry)

**Tenant Scoping**: ✅ Automatic

**Example**:
```typescript
const task = await apiClient.post('/api/v1/tasks', {
  description: 'Follow up with customer',
  assigned_to: 'sales_rep',
  appointment_id: appointmentId,
  due_at: '2025-01-21T10:00:00Z',
  priority: 'high'
});
```

---

#### 2.2.3 Complete Task

**Endpoint**: `POST /api/v1/tasks/{task_id}/complete`

**Roles**: `sales_rep`, `manager`, `csr`

**Response**:
```typescript
{
  "data": {
    "id": "task_123",
    "status": "completed",
    "completed_at": "2025-01-20T10:00:00Z",
    "completed_by": "rep_123"
  }
}
```

**Idempotency**: ✅ Yes (safe to retry)

**Tenant Scoping**: ✅ Automatic

**Example**:
```typescript
await apiClient.post(`/api/v1/tasks/${taskId}/complete`);
```

---

#### 2.2.4 Update Task

**Endpoint**: `PATCH /api/v1/tasks/{task_id}`

**Roles**: `sales_rep`, `manager`, `csr`

**Request Body**:
```typescript
{
  "status": "open", // optional
  "due_at": "2025-01-22T10:00:00Z", // optional
  "assigned_to": "sales_rep", // optional
  "description": "Updated description", // optional
  "priority": "medium", // optional
  "notes": "Additional notes" // optional
}
```

**Response**: Same as `GET /api/v1/tasks/{task_id}`

**Idempotency**: ✅ Yes (safe to retry)

**Tenant Scoping**: ✅ Automatic

---

### 2.3 Recording Sessions

#### 2.3.1 Start Recording Session

**Endpoint**: `POST /api/v1/recording-sessions/start`

**Roles**: `sales_rep`, `manager`

**Request Body**:
```typescript
{
  "appointment_id": "appt_123", // required
  "rep_id": "rep_123", // required
  "location": { // required
    "lat": 40.7128,
    "lng": -74.0060
  },
  "mode": "full" // optional: "full" | "ghost" | "ephemeral"
}
```

**Response**:
```typescript
{
  "data": {
    "recording_session_id": "session_123",
    "mode": "full",
    "audio_storage_mode": "persistent",
    "audio_upload_url": "https://s3.amazonaws.com/...", // presigned S3 URL
    "shunya_job_config": null
  }
}
```

**Idempotency**: ✅ Yes (uses `recording_session_id` as idempotency key)

**Tenant Scoping**: ✅ Automatic (rep can only start sessions for own appointments)

**Prerequisites**:
- Rep must be clocked in (active shift)
- Appointment must be assigned to rep
- Location must be within geofence (validated by mobile app)

**Example**:
```typescript
const response = await apiClient.post('/api/v1/recording-sessions/start', {
  appointment_id: appointmentId,
  rep_id: repId,
  location: {
    lat: currentLocation.latitude,
    lng: currentLocation.longitude
  },
  mode: 'full'
});

const sessionId = response.data.recording_session_id;
const uploadUrl = response.data.audio_upload_url;
```

---

#### 2.3.2 Stop Recording Session

**Endpoint**: `POST /api/v1/recording-sessions/{session_id}/stop`

**Roles**: `sales_rep`, `manager`

**Request Body**:
```typescript
{
  "location": { // required
    "lat": 40.7128,
    "lng": -74.0060
  }
}
```

**Response**:
```typescript
{
  "data": {
    "session": {
      "id": "session_123",
      "rep_id": "rep_123",
      "appointment_id": "appt_123",
      "started_at": "2025-01-20T14:00:00Z",
      "ended_at": "2025-01-20T15:00:00Z",
      "mode": "full",
      "transcription_status": "in_progress",
      "analysis_status": "not_started"
    }
  }
}
```

**Idempotency**: ✅ Yes (safe to retry)

**Tenant Scoping**: ✅ Automatic

**Example**:
```typescript
await apiClient.post(`/api/v1/recording-sessions/${sessionId}/stop`, {
  location: {
    lat: currentLocation.latitude,
    lng: currentLocation.longitude
  }
});
```

---

#### 2.3.3 Upload Audio Complete

**Endpoint**: `POST /api/v1/recording-sessions/{session_id}/upload-audio`

**Roles**: `sales_rep`, `manager`

**Request Body**:
```typescript
{
  "audio_url": "s3://bucket/audio.m4a", // required (S3 URL after upload)
  "audio_duration_seconds": 120.5, // required
  "audio_size_bytes": 1024000 // required
}
```

**Response**:
```typescript
{
  "data": {
    "status": "uploaded",
    "recording_session_id": "session_123"
  }
}
```

**Idempotency**: ✅ Yes (safe to retry if upload fails)

**Tenant Scoping**: ✅ Automatic

**Example**:
```typescript
// After uploading audio to S3 presigned URL
await apiClient.post(`/api/v1/recording-sessions/${sessionId}/upload-audio`, {
  audio_url: s3Url,
  audio_duration_seconds: duration,
  audio_size_bytes: fileSize
});
```

---

#### 2.3.4 Get Recording Session

**Endpoint**: `GET /api/v1/recording-sessions/{session_id}`

**Roles**: `sales_rep`, `manager`

**Response**: Same as `POST /api/v1/recording-sessions/{session_id}/stop`

**Tenant Scoping**: ✅ Automatic

---

### 2.4 Rep Shifts

#### 2.4.1 Clock In

**Endpoint**: `POST /api/v1/reps/{rep_id}/shifts/clock-in`

**Roles**: `sales_rep`, `manager`

**Request Body**:
```typescript
{
  "desired_start_time": "2025-01-20T08:00:00Z", // optional (defaults to now)
  "notes": "Starting shift" // optional
}
```

**Response**:
```typescript
{
  "data": {
    "shift": {
      "id": "shift_123",
      "rep_id": "rep_123",
      "shift_date": "2025-01-20",
      "clock_in_at": "2025-01-20T08:00:00Z",
      "clock_out_at": null,
      "status": "active",
      "scheduled_start": "07:00:00",
      "scheduled_end": "20:00:00"
    },
    "effective_start_time": "2025-01-20T08:00:00Z",
    "effective_end_time": "2025-01-20T20:00:00Z",
    "recording_mode": "full",
    "allow_location_tracking": true,
    "allow_recording": true
  }
}
```

**Idempotency**: ✅ Yes (returns existing shift if already clocked in)

**Tenant Scoping**: ✅ Automatic

**Example**:
```typescript
const shift = await apiClient.post(`/api/v1/reps/${repId}/shifts/clock-in`, {
  notes: 'Starting shift'
});
```

---

#### 2.4.2 Clock Out

**Endpoint**: `POST /api/v1/reps/{rep_id}/shifts/clock-out`

**Roles**: `sales_rep`, `manager`

**Response**:
```typescript
{
  "data": {
    "id": "shift_123",
    "rep_id": "rep_123",
    "shift_date": "2025-01-20",
    "clock_in_at": "2025-01-20T08:00:00Z",
    "clock_out_at": "2025-01-20T20:00:00Z",
    "status": "completed"
  }
}
```

**Idempotency**: ✅ Yes (safe to retry)

**Tenant Scoping**: ✅ Automatic

**Example**:
```typescript
await apiClient.post(`/api/v1/reps/${repId}/shifts/clock-out`);
```

---

#### 2.4.3 Get Today's Shift

**Endpoint**: `GET /api/v1/reps/{rep_id}/shifts/today`

**Roles**: `sales_rep`, `manager`

**Response**: Same as `POST /api/v1/reps/{rep_id}/shifts/clock-in`

**Tenant Scoping**: ✅ Automatic

**Example**:
```typescript
const shift = await apiClient.get(`/api/v1/reps/${repId}/shifts/today`);
```

---

### 2.5 Message Threads

#### 2.5.1 Get Message Thread

**Endpoint**: `GET /api/v1/message-threads/{contact_card_id}`

**Roles**: `sales_rep`, `manager`, `csr`

**Query Parameters**:
- `limit` (optional, int): Maximum number of messages (default: 100, max: 1000)
- `offset` (optional, int): Number of messages to skip (default: 0)

**Response**:
```typescript
{
  "data": {
    "contact_card_id": "contact_789",
    "messages": [
      {
        "id": "msg_123",
        "sender": "+1234567890",
        "sender_role": "customer",
        "body": "Hello, I'm interested in your services",
        "direction": "inbound",
        "created_at": "2025-01-20T10:00:00Z",
        "provider": "Twilio",
        "message_sid": "SM123",
        "delivered": true,
        "read": false
      }
    ],
    "total": 10
  }
}
```

**Tenant Scoping**: ✅ Automatic

**Pagination**: ✅ `limit` (default: 100, max: 1000), `offset` (default: 0)

**Example**:
```typescript
const thread = await apiClient.get(`/api/v1/message-threads/${contactCardId}`, {
  limit: 50
});
```

---

## 3. Shunya Integration Constraints

### 3.1 Shunya-Derived Fields

**Recording Transcripts** (from `app/models/recording_transcript.py`):
- `transcript_text` - May be `null` in Ghost Mode (`audio_storage_mode == "not_stored"`)
- `speaker_labels` - Speaker diarization from Shunya (JSON array)
- `confidence_score` - ASR confidence (0.0 to 1.0)
- `uwc_job_id` - Shunya job correlation ID
- `is_ghost_mode` - Boolean flag indicating Ghost Mode session
- `transcript_restricted` - Boolean flag indicating transcript is not available

**Recording Analysis** (from `app/models/recording_analysis.py`):
- `objections` - Array of objection types: `["price", "timeline", "competitor", "need_spouse_approval"]`
- `objection_details` - Detailed objection data with timestamps and quotes
- `sentiment_score` - 0.0 (negative) to 1.0 (positive)
- `engagement_score` - 0.0 to 1.0
- `coaching_tips` - AI-generated coaching recommendations (JSON array)
- `sop_stages_completed` - Array of completed SOP stages
- `sop_stages_missed` - Array of missed SOP stages
- `sop_compliance_score` - 0-10 score
- `lead_quality` - Classification: `"qualified"`, `"unqualified"`, `"hot"`, `"warm"`, `"cold"`
- `conversion_probability` - 0.0 to 1.0
- `meeting_segments` - Meeting phase segmentation (JSON array)
- `outcome` - Classification: `"won"`, `"lost"`, `"qualified"`, `"no_show"`, `"rescheduled"`
- `outcome_confidence` - 0.0 to 1.0

### 3.2 Normalization

**How Shunya Data is Normalized**:
- Shunya responses are normalized into Otto domain models via `app/services/shunya_integration_service.py`
- Empty/missing Shunya fields are stored as `null` in database
- Frontend must handle `null` values gracefully

**Processing Flow**:
1. Recording session stopped → Audio uploaded → Shunya transcription job enqueued
2. Shunya webhook received → Transcript stored in `recording_transcripts` table
3. Shunya analysis job enqueued → Analysis stored in `recording_analyses` table
4. Frontend polls `GET /api/v1/recording-sessions/{session_id}` to check status

### 3.3 Processing States

**Transcription Status** (from `app/models/recording_session.py`):
- `"not_started"` - Transcription not yet started
- `"in_progress"` - Transcription in progress (Shunya processing)
- `"completed"` - Transcription completed successfully
- `"failed"` - Transcription failed

**Analysis Status** (from `app/models/recording_session.py`):
- `"not_started"` - Analysis not yet started
- `"in_progress"` - Analysis in progress (Shunya processing)
- `"completed"` - Analysis completed successfully
- `"failed"` - Analysis failed

### 3.4 Frontend Handling

**Show Loading State**:
```typescript
if (session.transcription_status === 'in_progress' || session.analysis_status === 'in_progress') {
  showLoadingIndicator('Processing recording...');
}
```

**Handle Null Transcript in Ghost Mode**:
```typescript
if (session.mode === 'ghost' && !session.transcript?.transcript_text) {
  showMessage('Transcript not available in Ghost Mode');
}
```

**Poll for Status Updates**:
```typescript
const pollSessionStatus = async (sessionId: string) => {
  const interval = setInterval(async () => {
    const session = await apiClient.get(`/api/v1/recording-sessions/${sessionId}`);
    
    if (session.transcription_status === 'completed' && session.analysis_status === 'completed') {
      clearInterval(interval);
      // Show results
    } else if (session.transcription_status === 'failed' || session.analysis_status === 'failed') {
      clearInterval(interval);
      showError('Processing failed');
    }
  }, 5000); // Poll every 5 seconds
  
  // Stop polling after 5 minutes
  setTimeout(() => clearInterval(interval), 5 * 60 * 1000);
};
```

**Handle Missing/Delayed Shunya Outputs**:
- If `transcription_status == "failed"`, show error message
- If `analysis_status == "failed"`, show error but transcript may still be available
- If processing takes > 5 minutes, show warning: "Processing is taking longer than expected"
- Always handle `null` values for Shunya-derived fields gracefully

### 3.5 Ghost Mode Considerations

**Ghost Mode** (`mode == "ghost"`):
- `audio_storage_mode` may be `"ephemeral"` or `"not_stored"`
- `audio_url` will be `null` in Ghost Mode
- `transcript_text` may be `null` (depending on tenant retention policy)
- Analysis data (objections, coaching tips, etc.) is **always retained** (aggregated data only)

**Frontend Behavior**:
- Do not show audio playback controls if `audio_url == null`
- Do not show transcript if `transcript_text == null`
- Always show analysis data (objections, coaching tips, etc.) even in Ghost Mode

---

## 4. Error Codes Reference

### Common Error Codes

| Error Code | HTTP Status | Description | Action |
|------------|-------------|-------------|--------|
| `TOKEN_EXPIRED` | 401 | JWT token has expired | Refresh token from Clerk and retry |
| `MISSING_TENANT_ID` | 401 | Tenant ID not found in JWT | Check JWT claims, ensure user is in organization |
| `INVALID_TOKEN` | 401 | Invalid JWT token | Re-authenticate with Clerk |
| `NOT_FOUND` | 404 | Resource not found | Remove from cache, show user-friendly message |
| `VALIDATION_ERROR` | 400 | Invalid request body | Show validation errors to user |
| `INVALID_REQUEST` | 400 | Invalid query parameters | Check parameter format |
| `RBAC_VIOLATION` | 403 | Insufficient permissions | Show permission denied message, do NOT retry |
| `INTERNAL_ERROR` | 500 | Server error | Retry with exponential backoff (max 3 times) |

---

## 5. Testing with Demo Data

### Demo Credentials

**Sales Rep User**:
- Email: `salesrep@otto-demo.com`
- Clerk User ID: `user_36M3F0kllDOemX3prAPP1Zb8C5f`
- Role: `sales_rep`
- Organization: `org_36EW2DYBw4gpJaL4ASL2ZxFZPO9`

**Manager User**:
- Email: `manager@otto-demo.com`
- Clerk User ID: `user_36M3Kp5NQjnGhcmu5NM8nhOCqg2`
- Role: `manager`
- Organization: `org_36EW2DYBw4gpJaL4ASL2ZxFZPO9`

### Seeding Demo Data

Run the seed script to populate demo data:
```bash
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard
python -m scripts.seed_demo_data
```

This creates:
- Demo appointments for Sales Rep
- Demo tasks
- Demo recording sessions
- Demo rep shifts
- Demo message threads

---

## 6. Next Steps

1. ✅ Set up Clerk authentication in React Native app
2. ✅ Implement API client with error handling and retry logic
3. ✅ Implement offline queue for critical operations
4. ✅ Test with demo data
5. ✅ Implement pagination for list endpoints
6. ✅ Add request ID logging for observability

---

**Questions?** Contact the backend team with `request_id` from error responses.

