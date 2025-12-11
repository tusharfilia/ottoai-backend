# Sales Rep Mobile App Integration Specification

**Date**: 2025-12-10  
**Status**: ✅ **Implementation-Ready**

---

## 📋 Document Purpose

This document provides a complete, production-grade integration specification for the Sales Rep React Native mobile app to integrate with the Otto FastAPI backend. It defines exactly how Sales Rep screens should communicate with backend APIs, including authentication, data mapping, user actions, and error handling.

**Target Audience**: Frontend development agency implementing Sales Rep mobile app  
**Scope**: Sales Rep mobile app only (not CSR webapp or Executive webapp)

---

## 0. Global Integration Rules

### 0.1 Platform & Role

**Platform**: Sales Rep mobile app (React Native)

**Role**: `sales_rep` for all screens in this doc

**Auth**: Same as CSR/Exec (JWT from Clerk or equivalent auth provider)

### 0.2 Authentication & Tenant Scoping

**Every Sales Rep frontend API call MUST:**

1. **Include JWT in Authorization header**:
   ```
   Authorization: Bearer <JWT>
   ```
   - JWT is supplied by the auth layer (Clerk or equivalent)
   - JWT contains `user_id`, `company_id`, and `role: "sales_rep"` claims
   - Frontend should extract JWT from auth provider (Clerk session)

2. **Include tenant scoping via header** (if required by endpoint):
   ```
   X-Company-Id: <company_id>
   ```
   - `company_id` is extracted from JWT claims (not manually set)
   - Frontend must NOT try to override `company_id` for other tenants
   - Multi-tenancy is enforced backend-side using `company_id` and role claims from JWT

3. **Never call internal/Shunya endpoints directly**:
   - ❌ Do NOT call `/internal/ai/*` endpoints
   - ❌ Do NOT call Shunya/UWC URLs directly
   - ✅ All AI/analysis/Ask Otto behavior flows through Otto's own APIs
   - ✅ Frontend only calls `/api/v1/*` public endpoints

**Backend Enforcement**:
- `TenantContextMiddleware` extracts `tenant_id`, `user_id`, and `user_role` from JWT
- All database queries are automatically scoped by `company_id`
- Cross-tenant access attempts return `403 Forbidden`

**Example Request**:
```typescript
const response = await fetch(`${API_BASE_URL}/api/v1/metrics/sales/rep/overview/self`, {
  headers: {
    'Authorization': `Bearer ${jwtToken}`,
    'Content-Type': 'application/json',
  },
});
```

### 0.3 Shunya-First Semantics

**All semantic analysis comes from Shunya via Otto's backend:**

- **Booking / Qualified**: From `CallAnalysis.booking_status` and `CallAnalysis.lead_quality` (not inferred from appointments)
- **Outcome (won/lost/pending)**: From `RecordingAnalysis.outcome` (not `Appointment.outcome`)
- **Objections**: From `RecordingAnalysis.objections` (JSON list)
- **SOP Compliance**: From `RecordingAnalysis.sop_compliance_score` (0-10 scale)
- **Sentiment**: From `RecordingAnalysis.sentiment_score` (0.0-1.0)
- **Meeting Structure**: Derived from `RecordingAnalysis.meeting_segments`

**Important**:
- ✅ All data fetched via Otto backend; frontend never calls Shunya directly
- ✅ Otto never overrides Shunya's semantics
- ✅ All win rates, scores, and KPIs are derived from Shunya fields stored in `CallAnalysis` and `RecordingAnalysis`

### 0.4 Self-Scoping

**All endpoints in this doc are self-scoped:**

- Use current user context (authenticated `sales_rep` user)
- No explicit `rep_id` needed on "self" endpoints
- Backend automatically extracts `user_id` from JWT and filters data accordingly
- All metrics, appointments, tasks, and meeting details are automatically scoped to the authenticated sales rep

**Example**:
- `GET /api/v1/metrics/sales/rep/overview/self` → Returns metrics for the authenticated rep only
- `GET /api/v1/appointments/today/self` → Returns today's appointments for the authenticated rep only
- `GET /api/v1/tasks/sales-rep/self` → Returns follow-up tasks for the authenticated rep only

### 0.5 RBAC (Role-Based Access Control)

**Sales Rep Role**:
- JWT contains `role: "sales_rep"` claim
- Backend enforces role-based access via `@require_role("sales_rep")` decorators
- Sales rep may only see/modify resources they own

**Sales Rep Data Scoping**:
- ✅ **Can Access**:
  - Own metrics (self-scoped)
  - Own appointments (assigned to their `rep_id`)
  - Own follow-up tasks (assigned to their `rep_id`)
  - Own meeting details (appointments they own)
  - Ask Otto scoped to own data
- ❌ **Cannot Access**:
  - Other reps' metrics or appointments
  - CSR-specific endpoints
  - Manager-only endpoints (use Exec endpoints instead)

**Ask Otto RBAC**:
- When sales rep uses Ask Otto, backend automatically sends `X-Target-Role: sales_rep` to Shunya
- Shunya scopes responses to sales rep-accessible data (own appointments, leads, tasks, recordings)
- Context includes only that sales rep's identity: `{"user_role": "sales_rep", "rep_id": <current_user_id>}`

**403 Forbidden Handling**:
- If backend returns `403`, treat as "insufficient permissions"
- Show user-friendly message: "You don't have permission to perform this action"
- Never force through 403 errors in UI
- Log 403 errors for security monitoring

---

## 1. Sales Rep Frontend Screens

The Sales Rep mobile app consists of the following main screens:

### 1.1 Sales Rep Home / Ask Otto
**Purpose**: Chat-like Q&A about their own pipeline, customers, appointments, performance.

### 1.2 Recording Tab
**Purpose**: Auto-record appointments via geofence + mic. Mostly automatic with no manual interaction required.

### 1.3 Main Dashboard Tab / KPIs & Stats
**Purpose**: Show per-rep performance metrics for a date range.

### 1.4 Main Dashboard Tab / Today's Appointments
**Purpose**: Show today's appointment list sorted by time.

### 1.5 Main Dashboard Tab / Follow-Ups
**Purpose**: List follow-up tasks with "call" or "message" actions.

### 1.6 Meeting Detail / Customer Card
**Purpose**: Show AI meeting summary, transcript, objections, SOP scores, sentiment, outcome, and follow-up recommendations.

---

## 2. Screen-by-Screen Integration Specs

---

## Screen: Sales Rep Home / Ask Otto

**File(s)**: `src/screens/AskOttoScreen.tsx` (or equivalent)

### Purpose

Chat-like Q&A interface for sales reps. Sales rep can ask natural language questions about their own pipeline, customers, appointments, performance, follow-ups, and recordings. All answers are Shunya-backed RAG responses but role-scoped to the authenticated sales rep's data.

### Data Source

**Endpoint**: `POST /api/v1/rag/query`

**Method**: POST

**Auth**: Requires `sales_rep` role (JWT with `role: "sales_rep"`)

**When Called**: On prompt submit (user types question and clicks submit)

### Request Schema

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

### Response Schema

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

### Frontend spec: fields + endpoint + example JSON

**Endpoint**: `POST /api/v1/rag/query`

**Used by UI**:
- **Input**: `query.question` → User's typed question
- **Output**:
  - `answer` → Chat bubble text (display as message)
  - `citations[]` → "Sources" list (show as expandable section or inline links)
  - `confidence_score` → Optional confidence indicator (show as badge or progress bar)

**Example Request**:
```json
{
  "query": "What's my win rate this month?",
  "filters": {
    "date_range": "last_30_days"
  },
  "max_results": 10
}
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
- **Target Role**: Backend automatically sets `X-Target-Role: sales_rep` when calling Shunya, so context is sales-rep scoped
- **Scoping**: Only includes that sales rep's appointments, leads, tasks, and recordings, not company-wide data
- **Shunya Fields**: All semantic analysis (outcomes, objections, compliance, sentiment) comes from Shunya. Otto never overrides Shunya's semantics.
- **Nullable Fields**: If Shunya is still processing, `citations` may be empty and `confidence_score` may be 0.0

**Example Questions Sales Rep Can Ask**:
- "Show me my pending follow-ups"
- "What happened in my last 3 appointments with John Doe?"
- "What's my win rate this month?"
- "What are my top objections this quarter?"
- "Which appointments did I win this week?"

---

## Screen: Recording Tab

**File(s)**: `src/screens/RecordingTab.tsx` (or equivalent)

### Purpose

Auto-record appointments via geofence + mic (Otto mobile). Recording is triggered automatically when the sales rep enters a geofence around an appointment location. The recording tab may display a list of recordings or show recording status.

### Data Source

**No dedicated public API for recording list yet**

**Current State**: Recordings are managed by Otto backend + Shunya and surfaced only through the Meeting Detail view (`GET /api/v1/meetings/{appointment_id}/analysis`).

**Recording Pipeline**:
- Recording is automatic (geofence + mic trigger)
- No explicit API calls required beyond the existing recording ingestion pipeline
- Recordings are processed by Shunya and stored in `RecordingSession`, `RecordingAnalysis`, and `RecordingTranscript` tables
- Analysis results are available via the Meeting Detail endpoint

### Frontend spec: fields + endpoint + example JSON

**Endpoint**: N/A (no dedicated recording list endpoint)

**Used by UI**:
- If the recording tab shows a list of recordings, use `GET /api/v1/appointments/today/self` to get appointments, then call `GET /api/v1/meetings/{appointment_id}/analysis` for each appointment to check if recording/analysis exists
- If the recording tab is just a status indicator, no API calls needed (recording happens automatically)

**Note**: If a dedicated recording list endpoint is needed in the future, it will be documented separately. For now, recordings are accessed through the Meeting Detail view.

---

## Screen: Main Dashboard Tab / KPIs & Stats

**File(s)**: `src/screens/DashboardScreen.tsx` (or equivalent, KPIs section)

### Purpose

Show per-rep performance metrics for a date range. Displays key performance indicators including win rates, attendance, follow-up rates, compliance scores, and sentiment scores. All metrics are derived from Shunya fields.

### Data Source

**Endpoint**: `GET /api/v1/metrics/sales/rep/overview/self`

**Method**: GET

**Auth**: Requires `sales_rep` role (JWT with `role: "sales_rep"`)

**When Called**: On screen load, and when date range is changed

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date (defaults to 30 days ago)
- `date_to` (optional, ISO8601): End date (defaults to now)

### Response Schema

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
  pending_followups_count: number;             // Count of open follow-up tasks
  avg_objections_per_appointment: number | null;  // From RecordingAnalysis.objections
  avg_compliance_score: number | null;        // From RecordingAnalysis.sop_compliance_score (0-10 scale)
  avg_meeting_structure_score: number | null; // Derived from RecordingAnalysis.meeting_segments
  avg_sentiment_score: number | null;         // From RecordingAnalysis.sentiment_score (0.0-1.0)
  open_followups: number;                     // Open/pending tasks with due_at >= now
  overdue_followups: number;                   // Open/pending tasks with due_at < now
}
```

### Frontend spec: fields + endpoint + example JSON

**Endpoint**: `GET /api/v1/metrics/sales/rep/overview/self?date_from=2025-01-01&date_to=2025-01-31`

**Fields used**:
- `win_rate` → Main KPI card (display as percentage, e.g., "65%")
- `first_touch_win_rate` vs `followup_win_rate` → Two side-by-side stats (display as percentages, e.g., "50%" and "75%")
- `auto_usage_hours` → Total Otto hours used (display as hours, e.g., "12.5 hours")
- `attendance_rate` → Appointments attended % (display as percentage, e.g., "90%")
- `followup_rate` → Follow-up completion rate (display as percentage, e.g., "60%")
- `pending_followups_count` → Count badge (display as number, e.g., "8")
- `avg_compliance_score` → Compliance score (display as score out of 10, e.g., "8.5/10")
- `avg_meeting_structure_score` → Meeting structure score (display as percentage, e.g., "85%")
- `avg_sentiment_score` → Sentiment score (display as percentage, e.g., "75%")
- `open_followups` → Open tasks count (display as number, e.g., "5")
- `overdue_followups` → Overdue tasks count (display as number, e.g., "2")

**Example Request**:
```typescript
const metrics = await apiGet<SalesRepMetrics>(
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

**UI Mapping**:
- **Main KPI Card**: Display `win_rate` as large percentage (e.g., "66.7%")
- **Side-by-Side Stats**: Display `first_touch_win_rate` (e.g., "50%") and `followup_win_rate` (e.g., "75%") in two columns
- **Otto Hours**: Display `auto_usage_hours` as "12.5 hours" with icon
- **Attendance**: Display `attendance_rate` as "90%" with progress bar
- **Follow-up Rate**: Display `followup_rate` as "60%" with progress bar
- **Pending Follow-ups**: Display `pending_followups_count` as badge with number "8"
- **Scores Section**: Display `avg_compliance_score` (8.5/10), `avg_meeting_structure_score` (85%), and `avg_sentiment_score` (75%) in a scores card
- **Tasks Summary**: Display `open_followups` (5) and `overdue_followups` (2) in a tasks summary card

**Important Notes**:
- **Shunya-First**: All win/loss decisions come from Shunya's `RecordingAnalysis.outcome`, not `Appointment.outcome`. Otto never overrides Shunya's semantics.
- **Scores from Shunya**: `avg_compliance_score`, `avg_sentiment_score`, `avg_meeting_structure_score` all come from Shunya's `RecordingAnalysis` fields.
- **Rates are null-safe**: All rate fields return `null` if denominator is 0 or if insufficient data exists. Display "N/A" or "-" when null.
- **First-touch vs Follow-up**: `first_touch_win_rate` and `followup_win_rate` may be `null` if there's insufficient appointment history. Display "N/A" when null.

---

## Screen: Main Dashboard Tab / Today's Appointments

**File(s)**: `src/screens/DashboardScreen.tsx` (or equivalent, Today's Appointments section)

### Purpose

Show today's appointment list sorted by time. Sales rep can see all appointments scheduled for today, sorted chronologically. Each appointment shows customer name, scheduled time, address, status, and outcome (if analysis exists).

### Data Source

**Endpoint**: `GET /api/v1/appointments/today/self`

**Method**: GET

**Auth**: Requires `sales_rep` role (JWT with `role: "sales_rep"`)

**When Called**: On screen load, and when date is changed

**Query Parameters**:
- `date` (optional, ISO date YYYY-MM-DD): Date to filter by (defaults to "today" if omitted)

### Response Schema

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

### Frontend spec: fields + endpoint + example JSON

**Endpoint**: `GET /api/v1/appointments/today/self?date=2025-01-15` (optional date param)

**Fields used**:
- `appointment_id` → Used for navigation to Meeting Detail (on tap)
- `customer_name` → Display as primary text in list item
- `scheduled_time` → Display as time (e.g., "10:00 AM") and date if needed
- `address_line` → Display as secondary text or in detail view
- `status` → Display as status badge (e.g., "Scheduled", "Completed", "Cancelled")
- `outcome` → Display as outcome badge if not null (e.g., "Won", "Lost", "Pending")

**Click Behavior**:
- On tap → Navigate to customer/meeting detail screen, calling:
  - `GET /api/v1/meetings/{appointment_id}/analysis` (see Meeting Detail screen)

**Example Request**:
```typescript
const appointments = await apiGet<SalesRepTodayAppointment[]>(
  '/api/v1/appointments/today/self?date=2025-01-15'
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

**UI Mapping**:
- **List Item**: Display `customer_name` as primary text, `scheduled_time` as secondary text (formatted as "10:00 AM"), `status` as badge
- **Outcome Badge**: If `outcome` is not null, display as colored badge (e.g., green for "won", red for "lost", yellow for "pending")
- **Address**: Display `address_line` in detail view or as tertiary text if space allows
- **Tap Action**: Navigate to Meeting Detail screen with `appointment_id`

**Important Notes**:
- **Self-Scoped**: Only returns appointments where `Appointment.assigned_rep_id == authenticated_rep_id`
- **Sorted by Time**: Appointments are sorted by `scheduled_time` (ascending)
- **Outcome from Shunya**: The `outcome` field comes from `RecordingAnalysis.outcome` if analysis exists, otherwise `null`
- **Status vs Outcome**: `status` is the appointment status (scheduled/completed/etc.), while `outcome` is the Shunya-derived result (won/lost/pending)

---

## Screen: Main Dashboard Tab / Follow-Ups

**File(s)**: `src/screens/DashboardScreen.tsx` (or equivalent, Follow-Ups section)

### Purpose

List follow-up tasks with "call" or "message" actions. Sales rep can see all follow-up tasks assigned to them, sorted by due date. Each task shows customer name, task description, type, due date, status, and whether it's overdue.

### Data Source

**Endpoint**: `GET /api/v1/tasks/sales-rep/self`

**Method**: GET

**Auth**: Requires `sales_rep` role (JWT with `role: "sales_rep"`)

**When Called**: On screen load, and when filters are changed

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date for `due_date` range filter
- `date_to` (optional, ISO8601): End date for `due_date` range filter
- `status` (optional): Filter by status - `"open"`, `"pending"`, `"completed"`, `"overdue"`, `"cancelled"`

### Response Schema

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

### Frontend spec: fields + endpoint + example JSON

**Endpoint**: `GET /api/v1/tasks/sales-rep/self?date_from=2025-01-01&date_to=2025-01-31&status=pending`

**Fields used**:
- `task_id` → Used for task actions (complete, cancel, etc.)
- `customer_name` → Display as primary text in list item
- `title` → Display as task description
- `type` → Display as task type badge (e.g., "Call Back", "Send Quote")
- `due_date` → Display as due date/time (formatted, e.g., "Jan 16, 10:00 AM")
- `status` → Display as status badge
- `overdue` → Display as visual indicator (red border, warning icon, etc.)
- `last_contact_time` → Display as "Last contacted X days ago" if not null

**Actions**:
- **Call Button**: Use Twilio / phone integration on the client side (no special API documented here yet)
- **Message Button**: Use Twilio SMS integration on the client side (no special API documented here yet)
- **Tap Row**: Navigate to customer/meeting detail:
  - If task has `appointment_id` (not in schema but may be linked), call `GET /api/v1/meetings/{appointment_id}/analysis`
  - Otherwise, navigate to customer details endpoint (if available, reference `/api/v1/leads/{lead_id}` from other docs)

**Example Request**:
```typescript
const tasks = await apiGet<SalesRepFollowupTask[]>(
  '/api/v1/tasks/sales-rep/self?date_from=2025-01-01&date_to=2025-01-31&status=pending'
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

**UI Mapping**:
- **List Item**: Display `customer_name` as primary text, `title` as secondary text, `due_date` as tertiary text (formatted)
- **Type Badge**: Display `type` as badge (e.g., "Call Back", "Send Quote")
- **Status Badge**: Display `status` as colored badge
- **Overdue Indicator**: If `overdue` is `true`, display red border, warning icon, or "OVERDUE" label
- **Last Contact**: If `last_contact_time` is not null, display as "Last contacted 2 days ago" (calculate days from now)
- **Next Step**: If `next_step` is not null, display as hint text or in detail view
- **Call/Message Buttons**: Display action buttons (Twilio integration handled client-side)
- **Tap Action**: Navigate to customer/meeting detail based on task linkage

**Important Notes**:
- **Self-Scoped**: Only returns tasks where `Task.assignee_id == authenticated_rep_id` (or `Task.assigned_to == "rep"` if `assignee_id` is not available)
- **ActionType Enum**: The `type` field uses canonical `ActionType` enum values (30 total values: `call_back`, `send_quote`, `schedule_appointment`, `follow_up_call`, etc.)
- **Follow-up Semantics**: Tasks are aligned with Shunya's canonical action types for consistency
- **Last Contact Time**: Currently `null` - will be populated from Twilio/CallRail integration in the future
- **Next Step**: Currently `null` - will be populated from Shunya follow-up recommendations in the future
- **Sorted by Due Date**: Tasks are sorted by `due_date` (ascending)

---

## Screen: Meeting Detail / Customer Card

**File(s)**: `src/screens/MeetingDetailScreen.tsx` (or equivalent)

### Purpose

Show AI meeting summary, transcript, objections, SOP scores, sentiment, outcome, and follow-up recommendations. This is the detailed view when a sales rep taps on an appointment or follow-up task. All data is Shunya-derived but normalized by Otto.

### Data Source

**Endpoint**: `GET /api/v1/meetings/{appointment_id}/analysis`

**Method**: GET

**Auth**: Requires `sales_rep` role (JWT with `role: "sales_rep"`)

**When Called**: When user taps on an appointment or follow-up task linked to an appointment

**Path Parameters**:
- `appointment_id` (required): Appointment ID

### Response Schema

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

### Frontend spec: fields + endpoint + example JSON

**Endpoint**: `GET /api/v1/meetings/{appointment_id}/analysis`

**Fields used**:
- `summary` → Top section text (display as meeting summary card)
- `transcript` → Transcript view (scrollable text area)
- `objections[]` → List of objections with timestamps or metadata (display as objections card with list)
- `sop_compliance_score` → Display as score out of 10 (e.g., "8.5/10") with progress bar
- `sentiment_score` → Display as percentage (e.g., "75%") with sentiment indicator (positive/neutral/negative)
- `outcome` → Display as outcome badge (e.g., "Won", "Lost", "Pending")
- `followup_recommendations` → Next-step UI (display as recommendations card with action items)

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

**UI Mapping**:
- **Summary Card**: Display `summary` as text in a card at the top
- **Transcript Section**: Display `transcript` in a scrollable text area with formatting (speaker labels if available)
- **Objections Card**: Display `objections[]` as a list with:
  - Objection type as primary text (e.g., "Price")
  - Timestamp as secondary text (e.g., "4:05")
  - Severity/metadata as badge or indicator
- **Scores Section**: Display `sop_compliance_score` (8.5/10) and `sentiment_score` (75%) in a scores card with progress bars
- **Outcome Badge**: Display `outcome` as colored badge (green for "won", red for "lost", yellow for "pending")
- **Follow-up Recommendations**: Display `followup_recommendations` as a recommendations card with:
  - `next_steps[]` as bullet list
  - `recommended_actions[]` as action items with priority indicators

**Important Notes**:
- **RBAC**: The sales rep must own the appointment (`Appointment.assigned_rep_id == authenticated_rep_id`). Returns `403 Forbidden` if not owned.
- **Shunya-First**: All fields (`objections`, `sop_compliance_score`, `sentiment_score`, `outcome`) come from Shunya's `RecordingAnalysis`. Otto never overrides Shunya's semantics.
- **Transcript Source**: Transcript comes from `RecordingTranscript.transcript` if available, otherwise `null`.
- **Summary Source**: Summary comes from `RecordingTranscript` (first 500 chars) or `RecordingAnalysis.coaching_tips` as fallback.
- **Follow-up Recommendations**: Structure reused from the follow-up recommendations integration. May be `null` if not available.
- **Data Normalization**: This data is largely Shunya-derived, but normalized by Otto for consistent structure.

---

## 3. RBAC & Self-Scoping

### All Endpoints in This Doc

**Require `sales_rep` role**:
- All endpoints documented in this spec require JWT with `role: "sales_rep"` claim
- Backend enforces role-based access via `@require_role("sales_rep")` decorators
- Returns `403 Forbidden` if role is not `sales_rep`

**Are self-scoped using the authenticated user**:
- All endpoints automatically extract `user_id` from JWT
- Data is filtered by `rep_id == authenticated_user_id`
- No explicit `rep_id` parameter needed on "self" endpoints
- Sales rep can only see their own metrics, appointments, tasks, and meeting details

### Manager/Exec Endpoints

**Any manager/exec endpoints for sales are documented in**:
- [EXEC_APP_INTEGRATION.md](./EXEC_APP_INTEGRATION.md)
- [EXEC_API_QUICKSTART.md](./EXEC_API_QUICKSTART.md)

Sales reps should not call manager-only endpoints. If a sales rep needs company-wide data, they should use the Exec dashboard instead.

---

## 4. Error Handling

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
- `403 Forbidden`: Role does not have permission (e.g., CSR trying to access sales rep endpoint, or sales rep trying to access another rep's appointment)
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

**Frontend Error Handling**:
- Show user-friendly error messages
- Handle `403` as "insufficient permissions" (should not happen for self-scoped endpoints)
- Handle `404` as "resource not found" (appointment may have been deleted or not owned by rep)
- Allow retry for `500` errors
- Log errors for debugging

---

## 5. Next Steps

1. **Review [SALES_REP_API_QUICKSTART.md](./SALES_REP_API_QUICKSTART.md)** for detailed API reference
2. **Set up API client** with JWT authentication
3. **Implement Ask Otto screen** with chat interface
4. **Build dashboard** with KPIs and stats
5. **Implement today's appointments** list
6. **Add follow-ups** list with task management
7. **Wire up meeting detail** view for appointment drill-down
8. **Handle recording tab** (mostly automatic, no API calls needed)

---

**Questions?** Contact the backend team or refer to the full API quickstart docs.
