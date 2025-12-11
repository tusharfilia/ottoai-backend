# Sales Rep API Quickstart

**Date**: 2025-12-10  
**Status**: ✅ **Ready for Frontend Development**

---

## 📋 Purpose

This is a short, practical guide to get the Sales Rep frontend team started calling Otto backend APIs within minutes. For full endpoint-by-endpoint details, see [SALES_REP_APP_INTEGRATION.md](./SALES_REP_APP_INTEGRATION.md).

**Sales Rep App Context**:
- **Ask Otto Tab**: Chat-like Ask Otto, scoped to the `sales_rep` role. Questions about company data, leads/customers, appointments, calls/recordings, tasks/follow-ups. All answers are Shunya-backed RAG responses but role-scoped.
- **Recording Tab**: Auto-recording is triggered by geofence + mic (Otto mobile). Backend uses the same Shunya recording pipeline used elsewhere. This doc references existing recording endpoints, no new ones.
- **Main Dashboard Tab**: KPIs/stats (win_rate, first_touch_win_rate, followup_win_rate, auto_usage_hours, attendance_rate, followup_rate, pending_followups_count), today's appointments, follow-ups list, and meeting detail view.

---

## 1. Base URLs

### Staging / Production (Current)

```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://ottoai-backend-production.up.railway.app';
```

**Note**: The current backend is hosted on Railway. A dedicated staging environment URL will be provided later.

**Environment Variable**:
- `NEXT_PUBLIC_API_URL` - Set this in your `.env.local` file for local development or override the default Railway URL.

### Local Development

For local backend development:
```typescript
const LOCAL_API_BASE_URL = 'http://localhost:8000';
```

Set in `.env.local`:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 2. Authentication & RBAC

### JWT from Clerk

The Sales Rep Next.js app uses Clerk for authentication. The JWT token from Clerk must be included in all API requests.

**RBAC (Role-Based Access Control)**:
- **Sales Rep Role**: JWT contains `role: "sales_rep"` claim
- **Data Scoping**: Sales rep can only see:
  - Own metrics (self-scoped)
  - Own appointments (assigned to their `rep_id`)
  - Own follow-up tasks (assigned to their `rep_id`)
  - Own meeting details (appointments they own)
- **Cannot Access**: Other reps' data, CSR endpoints, Manager-only endpoints (use Exec endpoints instead)
- **Ask Otto Context**: When sales rep uses Ask Otto, backend automatically forwards `X-Target-Role: sales_rep` to Shunya to scope responses to sales rep data

**Getting the JWT**:

In your Next.js app, use Clerk's hooks to get the token:

```typescript
import { useAuth } from '@clerk/nextjs';

function MyComponent() {
  const { getToken } = useAuth();
  
  const fetchData = async () => {
    const token = await getToken();
    // Use token in API calls
  };
}
```

**Or in API routes/middleware**:

```typescript
import { auth } from '@clerk/nextjs';

export async function GET(request: Request) {
  const { getToken } = auth();
  const token = await getToken();
  // Use token in API calls
}
```

### Request Headers

All API requests must include:

```typescript
{
  'Authorization': `Bearer ${jwtToken}`,
  'Content-Type': 'application/json',
}
```

**Important**:
- The `company_id` and `role` are extracted from the JWT claims by the backend
- Frontend should **NOT** manually pass `X-Company-Id` header unless explicitly required by a specific endpoint
- The backend's `TenantContextMiddleware` automatically enforces tenant isolation using JWT claims
- The backend automatically sets `X-Target-Role: sales_rep` when calling Shunya APIs (frontend never calls Shunya directly)

---

## 3. Example API Client

Here's a minimal TypeScript example showing how to make authenticated API calls:

```typescript
// lib/api/client.ts

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://ottoai-backend-production.up.railway.app';

interface ApiError {
  status: number;
  message: string;
  error_code?: string;
}

class ApiError extends Error {
  constructor(message: string, public status: number, public error_code?: string) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Get JWT token from Clerk
 */
async function getAuthToken(): Promise<string | null> {
  // In client components, use useAuth hook
  // In server components/API routes, use auth() from @clerk/nextjs/server
  if (typeof window !== 'undefined') {
    // Client-side: use Clerk React hooks
    const { useAuth } = await import('@clerk/nextjs');
    // Implementation depends on your setup
    return null; // Replace with actual token retrieval
  } else {
    // Server-side: use Clerk server SDK
    const { auth } = await import('@clerk/nextjs/server');
    const { getToken } = auth();
    return await getToken();
  }
}

/**
 * Make an authenticated GET request
 */
export async function apiGet<T>(
  path: string,
  params?: Record<string, any>
): Promise<T> {
  const token = await getAuthToken();
  if (!token) {
    throw new ApiError('No authentication token', 401);
  }

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
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Unknown error' }));
    throw new ApiError(error.message || 'Request failed', response.status, error.error_code);
  }

  const data = await response.json();
  if (!data.success) {
    throw new ApiError(data.message || 'Request failed', response.status, data.error_code);
  }

  return data.data;
}

/**
 * Make an authenticated POST request
 */
export async function apiPost<T>(
  path: string,
  body: any
): Promise<T> {
  const token = await getAuthToken();
  if (!token) {
    throw new ApiError('No authentication token', 401);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Unknown error' }));
    throw new ApiError(error.message || 'Request failed', response.status, error.error_code);
  }

  const data = await response.json();
  if (!data.success) {
    throw new ApiError(data.message || 'Request failed', response.status, data.error_code);
  }

  return data.data;
}
```

---

## 4. Ask Otto (Sales Rep Scoped)

### POST `/api/v1/rag/query`

**Roles**: `sales_rep`, `manager`

**Description**: Natural language query interface for sales reps. Backend automatically scopes responses to the authenticated sales rep's data and forwards `X-Target-Role: sales_rep` to Shunya.

**Request**:

```typescript
interface RAGQueryRequest {
  query: string;                    // Natural language question (3-1000 chars)
  filters?: {                       // Optional filters
    date_range?: string;            // e.g., "last_30_days"
    [key: string]: any;
  };
  max_results?: number;             // Max results (1-50, default: 10)
}
```

**Response**:

```typescript
interface RAGQueryResponse {
  query_id: string;                 // Unique query ID
  query: string;                    // Original query
  answer: string;                    // Answer text (guaranteed non-null)
  citations: Citation[];            // Source citations (may be empty if processing)
  confidence_score: number;         // 0.0-1.0 (may be 0.0 if processing)
  latency_ms: number;               // Query latency in milliseconds
}

interface Citation {
  doc_id: string;
  filename?: string;
  chunk_text: string;
  similarity_score: number;
  call_id?: number;
  timestamp?: number;
}
```

**Example Request**:

```typescript
const response = await apiPost<RAGQueryResponse>('/api/v1/rag/query', {
  query: "What's my win rate this month?",
  filters: { date_range: "last_30_days" },
  max_results: 10
});
```

**Example Response**:

```json
{
  "success": true,
  "data": {
    "query_id": "query_abc123",
    "query": "What's my win rate this month?",
    "answer": "Your win rate this month is 65% (13 won out of 20 completed appointments). This is above your average of 60%.",
    "citations": [
      {
        "doc_id": "appointment_456",
        "chunk_text": "Appointment completed with outcome: won...",
        "similarity_score": 0.92,
        "call_id": 456,
        "timestamp": 1234567890
      }
    ],
    "confidence_score": 0.89,
    "latency_ms": 1250
  }
}
```

**Important Notes**:
- **Target Role**: When called by a sales rep, backend automatically sends `X-Target-Role: sales_rep` to Shunya
- **Scoping**: Only includes that sales rep's appointments, leads, tasks, and recordings, not company-wide data
- **Shunya Fields**: All semantic analysis (outcomes, objections, compliance, sentiment) comes from Shunya. Otto never overrides Shunya's semantics.
- **Nullable Fields**: If Shunya is still processing, `citations` may be empty and `confidence_score` may be 0.0
- **Frontend Never Calls Shunya**: The frontend only hits Otto APIs. All Shunya integration is handled by the backend.

**Sales Rep Can Ask**:
- "Show me my pending follow-ups"
- "What happened in my last 3 appointments with John Doe?"
- "What's my win rate this month?"
- "What are my top objections this quarter?"
- "Which appointments did I win this week?"

---

## 5. Sales Rep Overview Metrics (Self)

### GET `/api/v1/metrics/sales/rep/overview/self`

**Roles**: `sales_rep` only

**Description**: Get comprehensive sales rep overview metrics for the authenticated sales rep user. All metrics are computed from Shunya-derived fields (`RecordingAnalysis.outcome`, `sop_compliance_score`, `sentiment_score`, `meeting_segments`).

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date (defaults to 30 days ago)
- `date_to` (optional, ISO8601): End date (defaults to now)

**Response**:

```typescript
interface SalesRepMetrics {
  total_appointments: number;
  completed_appointments: number;
  won_appointments: number;                    // From Shunya RecordingAnalysis.outcome == "won"
  lost_appointments: number;                   // From Shunya RecordingAnalysis.outcome == "lost"
  pending_appointments: number;                // From Shunya RecordingAnalysis.outcome == "pending"
  win_rate: number | null;                    // won_appointments / completed_appointments
  first_touch_win_rate: number | null;         // Win rate for first appointment with a lead (may be null if insufficient history)
  followup_win_rate: number | null;            // Win rate where > 1 appointment happened before close (may be null)
  auto_usage_hours: number | null;            // Total hours of meetings recorded (RecordingSession.audio_duration_seconds / 3600)
  attendance_rate: number | null;             // Attended appointments / scheduled appointments
  followup_rate: number | null;               // Leads with ≥ 1 follow-up task completed / total leads owned by rep
  pending_followups_count: number;           // Count of open follow-up tasks
  avg_objections_per_appointment: number | null;  // From RecordingAnalysis.objections
  avg_compliance_score: number | null;        // From RecordingAnalysis.sop_compliance_score (0-10 scale)
  avg_meeting_structure_score: number | null; // Derived from RecordingAnalysis.meeting_segments
  avg_sentiment_score: number | null;        // From RecordingAnalysis.sentiment_score (0.0-1.0)
  open_followups: number;                     // Open/pending tasks with due_at >= now
  overdue_followups: number;                   // Open/pending tasks with due_at < now
}
```

**Example Request**:

```typescript
const overview = await apiGet<SalesRepMetrics>(
  '/api/v1/metrics/sales/rep/overview/self?date_from=2025-01-01&date_to=2025-01-31'
);
```

**Example Response**:

```json
{
  "success": true,
  "data": {
    "total_appointments": 50,
    "completed_appointments": 45,
    "won_appointments": 30,
    "lost_appointments": 10,
    "pending_appointments": 5,
    "win_rate": 0.6667,
    "first_touch_win_rate": 0.5,
    "followup_win_rate": 0.75,
    "auto_usage_hours": 12.5,
    "attendance_rate": 0.9,
    "followup_rate": 0.6,
    "pending_followups_count": 8,
    "avg_objections_per_appointment": 1.2,
    "avg_compliance_score": 8.5,
    "avg_meeting_structure_score": 0.85,
    "avg_sentiment_score": 0.75,
    "open_followups": 5,
    "overdue_followups": 2
  }
}
```

**Important Notes**:
- **Shunya-First**: All win/loss decisions come from Shunya's `RecordingAnalysis.outcome`, not `Appointment.outcome`. Otto never overrides Shunya's semantics.
- **Scores from Shunya**: `avg_compliance_score`, `avg_sentiment_score`, `avg_meeting_structure_score` all come from Shunya's `RecordingAnalysis` fields.
- **Rates are null-safe**: All rate fields return `null` if denominator is 0 or if insufficient data exists.
- **First-touch vs Follow-up**: `first_touch_win_rate` and `followup_win_rate` may be `null` if there's insufficient appointment history to accurately determine first-touch vs follow-up appointments.

---

## 6. Today's Appointments (Self)

### GET `/api/v1/appointments/today/self`

**Roles**: `sales_rep` only

**Description**: Get today's appointments for the authenticated sales rep. Only appointments assigned to the rep and scheduled for today (local or UTC date, following existing convention).

**Query Parameters**:
- `date` (optional, ISO date YYYY-MM-DD): Date to filter by (defaults to "today" if omitted)

**Response**:

```typescript
interface SalesRepTodayAppointment {
  appointment_id: string;
  customer_id: string | null;
  customer_name: string | null;
  scheduled_time: string;                    // ISO8601 datetime
  address_line: string | null;
  status: string;                             // "scheduled" | "in_progress" | "completed" | "cancelled"
  outcome: string | null;                      // From Shunya RecordingAnalysis.outcome: "won" | "lost" | "pending" (if analysis exists)
}
```

**Example Request**:

```typescript
const appointments = await apiGet<SalesRepTodayAppointment[]>(
  '/api/v1/appointments/today/self'
);
```

**Example Response**:

```json
{
  "success": true,
  "data": [
    {
      "appointment_id": "apt_001",
      "customer_id": "lead_123",
      "customer_name": "John Doe",
      "scheduled_time": "2025-01-15T10:00:00Z",
      "address_line": "123 Main St, City, State 12345",
      "status": "scheduled",
      "outcome": null
    },
    {
      "appointment_id": "apt_002",
      "customer_id": "lead_456",
      "customer_name": "Jane Smith",
      "scheduled_time": "2025-01-15T14:00:00Z",
      "address_line": "456 Oak Ave, City, State 12345",
      "status": "completed",
      "outcome": "won"
    },
    {
      "appointment_id": "apt_003",
      "customer_id": "lead_789",
      "customer_name": "Bob Johnson",
      "scheduled_time": "2025-01-15T16:00:00Z",
      "address_line": null,
      "status": "scheduled",
      "outcome": null
    }
  ]
}
```

**Important Notes**:
- **Self-Scoped**: Only returns appointments where `Appointment.assigned_rep_id == authenticated_rep_id`
- **Sorted by Time**: Appointments are sorted by `scheduled_time` (ascending)
- **Outcome from Shunya**: The `outcome` field comes from `RecordingAnalysis.outcome` if analysis exists, otherwise `null`
- **Status vs Outcome**: `status` is the appointment status (scheduled/completed/etc.), while `outcome` is the Shunya-derived result (won/lost/pending)

---

## 7. Follow-Ups List (Self)

### GET `/api/v1/tasks/sales-rep/self`

**Roles**: `sales_rep` only

**Description**: Get follow-up tasks assigned to the authenticated sales rep. Tasks come from Otto's `Task` table and are aligned with the canonical `ActionType` enum.

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date for `due_date` range filter
- `date_to` (optional, ISO8601): End date for `due_date` range filter
- `status` (optional): Filter by status - `"open"`, `"pending"`, `"completed"`, `"overdue"`, `"cancelled"`

**Response**:

```typescript
interface SalesRepFollowupTask {
  task_id: string;
  lead_id: string | null;
  customer_name: string | null;
  title: string | null;                        // Task description
  type: string | null;                         // Aligned with ActionType enum (e.g., "call_back", "send_quote", "schedule_appointment")
  due_date: string | null;                     // ISO8601 datetime
  status: string;                              // "open" | "pending" | "completed" | "overdue" | "cancelled"
  last_contact_time: string | null;            // ISO8601 datetime (currently may be null, TODO: Twilio/CallRail integration)
  next_step: string | null;                    // Next step recommendation (currently may be null, TODO: Shunya recommendations)
  overdue: boolean;                            // Whether task is overdue (due_date < now)
}
```

**Example Request**:

```typescript
const tasks = await apiGet<SalesRepFollowupTask[]>(
  '/api/v1/tasks/sales-rep/self?date_from=2025-01-01&date_to=2025-01-31'
);
```

**Example Response**:

```json
{
  "success": true,
  "data": [
    {
      "task_id": "task_001",
      "lead_id": "lead_123",
      "customer_name": "John Doe",
      "title": "Follow up on quote sent last week",
      "type": "follow_up_call",
      "due_date": "2025-01-16T10:00:00Z",
      "status": "open",
      "last_contact_time": null,
      "next_step": null,
      "overdue": false
    },
    {
      "task_id": "task_002",
      "lead_id": "lead_456",
      "customer_name": "Jane Smith",
      "title": "Send contract to customer",
      "type": "send_contract",
      "due_date": "2025-01-15T14:00:00Z",
      "status": "pending",
      "last_contact_time": "2025-01-14T16:30:00Z",
      "next_step": "Schedule signing appointment",
      "overdue": true
    }
  ]
}
```

**Important Notes**:
- **Self-Scoped**: Only returns tasks where `Task.assignee_id == authenticated_rep_id` (or `Task.assigned_to == "rep"` if `assignee_id` is not available)
- **ActionType Enum**: The `type` field uses canonical `ActionType` enum values (30 total values: `call_back`, `send_quote`, `schedule_appointment`, `follow_up_call`, etc.)
- **Follow-up Semantics**: Tasks are aligned with Shunya's canonical action types for consistency
- **Last Contact Time**: Currently `null` - will be populated from Twilio/CallRail integration in the future
- **Next Step**: Currently `null` - will be populated from Shunya follow-up recommendations in the future
- **Sorted by Due Date**: Tasks are sorted by `due_date` (ascending)

---

## 8. Meeting Detail (Self)

### GET `/api/v1/meetings/{appointment_id}/analysis`

**Roles**: `sales_rep` only

**Description**: Get detailed meeting analysis for a specific appointment. Includes AI summary, transcript, objections, SOP compliance, sentiment, outcome, and follow-up recommendations. The sales rep must own the appointment (RBAC enforced).

**Path Parameters**:
- `appointment_id` (required): Appointment ID

**Response**:

```typescript
interface SalesRepMeetingDetail {
  appointment_id: string;
  call_id: number | null;                      // Call ID if linked to a call
  summary: string | null;                       // AI meeting summary (from RecordingTranscript or RecordingAnalysis.coaching_tips)
  transcript: string | null;                   // Full transcript (from RecordingTranscript)
  objections: Array<{
    type: string;                               // Objection type (e.g., "price", "timeline", "competitor")
    timestamp?: number;                         // Timestamp in seconds
    [key: string]: any;
  }> | null;                                    // From RecordingAnalysis.objections
  sop_compliance_score: number | null;         // From RecordingAnalysis.sop_compliance_score (0-10 scale)
  sentiment_score: number | null;             // From RecordingAnalysis.sentiment_score (0.0-1.0)
  outcome: string | null;                      // From RecordingAnalysis.outcome: "won" | "lost" | "pending"
  followup_recommendations: {
    next_steps?: string[];
    recommended_actions?: Array<{
      action_type: string;
      priority: string;
      description: string;
    }>;
    [key: string]: any;
  } | null;                                    // From CallAnalysis.followup_recommendations (normalized structure)
}
```

**Example Request**:

```typescript
const detail = await apiGet<SalesRepMeetingDetail>(
  '/api/v1/meetings/apt_001/analysis'
);
```

**Example Response**:

```json
{
  "success": true,
  "data": {
    "appointment_id": "apt_001",
    "call_id": 12345,
    "summary": "Meeting with John Doe focused on pricing discussion. Customer expressed interest but needs to discuss with spouse. Key objections: price too high, timeline concerns. Sentiment was positive overall. Recommended follow-up: send detailed quote within 24 hours.",
    "transcript": "Rep: Hi John, thanks for meeting with me today. Let's discuss your roofing needs...\nCustomer: I'm interested but the price seems high...\nRep: I understand. Let me break down the value...",
    "objections": [
      {
        "type": "price",
        "timestamp": 245.5,
        "severity": "high"
      },
      {
        "type": "timeline",
        "timestamp": 312.8,
        "severity": "medium"
      }
    ],
    "sop_compliance_score": 8.5,
    "sentiment_score": 0.75,
    "outcome": "pending",
    "followup_recommendations": {
      "next_steps": [
        "Send detailed quote within 24 hours",
        "Follow up in 3 days to check on spouse discussion"
      ],
      "recommended_actions": [
        {
          "action_type": "send_quote",
          "priority": "high",
          "description": "Send comprehensive quote with breakdown of costs and value proposition"
        },
        {
          "action_type": "follow_up_call",
          "priority": "medium",
          "description": "Call in 3 days to follow up on spouse discussion"
        }
      ]
    }
  }
}
```

**Important Notes**:
- **RBAC**: The sales rep must own the appointment (`Appointment.assigned_rep_id == authenticated_rep_id`). Returns `403 Forbidden` if not owned.
- **Shunya-First**: All fields (`objections`, `sop_compliance_score`, `sentiment_score`, `outcome`) come from Shunya's `RecordingAnalysis`. Otto never overrides Shunya's semantics.
- **Transcript Source**: Transcript comes from `RecordingTranscript.transcript` if available, otherwise `null`.
- **Summary Source**: Summary comes from `RecordingTranscript` (first 500 chars) or `RecordingAnalysis.coaching_tips` as fallback.
- **Follow-up Recommendations**: Structure reused from the follow-up recommendations integration (Section C from backend TODO). May be `null` if not available.

---

## 9. RBAC & Scoping

### Sales Rep Permissions

**Sales Rep (`sales_rep` role) can access**:
- ✅ Own metrics (`/api/v1/metrics/sales/rep/overview/self`)
- ✅ Own appointments (`/api/v1/appointments/today/self`)
- ✅ Own follow-up tasks (`/api/v1/tasks/sales-rep/self`)
- ✅ Own meeting details (`/api/v1/meetings/{appointment_id}/analysis`)
- ✅ Ask Otto scoped to own data (`POST /api/v1/rag/query`)

**Sales Rep cannot access**:
- ❌ Other reps' metrics or appointments
- ❌ CSR-specific endpoints
- ❌ Manager-only endpoints (use Exec endpoints instead)

### Manager Permissions

**Manager (`manager` role) can access**:
- ✅ Company-wide sales metrics (see [EXEC_API_QUICKSTART.md](./EXEC_API_QUICKSTART.md))
- ✅ Individual rep metrics via `/api/v1/metrics/sales/rep/{rep_id}` (manager-only endpoint)
- ✅ Ask Otto with company-wide scope

**Manager cannot access**:
- ❌ Sales rep self-scoped endpoints (use manager endpoints instead)

---

## 10. Shunya Integration Notes

### Frontend Never Calls Shunya Directly

**Important**: The frontend **never** calls Shunya APIs directly. All Shunya integration is handled by the Otto backend.

### Shunya as Source of Truth

All semantic analysis comes from Shunya via Otto's `CallAnalysis` and `RecordingAnalysis` models:

- **Outcome (won/lost/pending)**: From `RecordingAnalysis.outcome` (not `Appointment.outcome`)
- **Objections**: From `RecordingAnalysis.objections` (JSON list)
- **SOP Compliance**: From `RecordingAnalysis.sop_compliance_score` (0-10 scale)
- **Sentiment**: From `RecordingAnalysis.sentiment_score` (0.0-1.0)
- **Meeting Structure**: Derived from `RecordingAnalysis.meeting_segments`
- **Follow-up Recommendations**: From `CallAnalysis.followup_recommendations` (normalized structure)

### Metrics Derivation

All win rates, scores, and KPIs are derived from Shunya fields:
- `win_rate` = `won_appointments / completed_appointments` where `won_appointments` comes from `RecordingAnalysis.outcome == "won"`
- `avg_compliance_score` = Average of `RecordingAnalysis.sop_compliance_score` across appointments
- `avg_sentiment_score` = Average of `RecordingAnalysis.sentiment_score` across appointments
- `avg_meeting_structure_score` = Derived from `RecordingAnalysis.meeting_segments` across appointments

**Otto never overrides Shunya's semantics**. All booking, qualification, outcome, objections, SOP, and sentiment decisions come from Shunya.

### Target Role Header

When a sales rep uses Ask Otto or other Shunya-integrated features, the backend automatically sets `X-Target-Role: sales_rep` when calling Shunya. The frontend does not need to (and should not) set this header.

---

## 11. Error Handling

All endpoints return standard error responses:

```typescript
interface ErrorResponse {
  success: false;
  error: {
    code: string;
    message: string;
    details?: any;
  };
}
```

**Common Error Codes**:
- `401 Unauthorized`: Missing or invalid JWT token
- `403 Forbidden`: Role does not have permission (e.g., CSR trying to access sales rep endpoint)
- `404 Not Found`: Resource not found (e.g., appointment not found or not owned by rep)
- `500 Internal Server Error`: Server error

**Example Error Response**:

```json
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Appointment not found or not assigned to this rep",
    "details": {
      "appointment_id": "apt_001"
    }
  }
}
```

---

## 12. Next Steps

1. **Review [SALES_REP_APP_INTEGRATION.md](./SALES_REP_APP_INTEGRATION.md)** for detailed UI → API integration mapping
2. **Set up API client** using the example code in Section 3
3. **Test authentication** with Clerk JWT tokens
4. **Start with Ask Otto** (`POST /api/v1/rag/query`) to verify Shunya integration
5. **Build dashboard** using overview metrics endpoint
6. **Implement today's appointments** list
7. **Add follow-ups** list with task management
8. **Wire up meeting detail** view for appointment drill-down

---

**Questions?** Contact the backend team or refer to the full integration docs.
