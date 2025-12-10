# CSR Web App Integration Specification

**Date**: 2025-12-10  
**Status**: ✅ **Implementation-Ready**

---

## 📋 Document Purpose

This document provides a complete, production-grade integration specification for the CSR (Customer Service Representative) Next.js frontend to integrate with the Otto FastAPI backend. It defines exactly how CSR screens should communicate with backend APIs, including authentication, data mapping, user actions, and error handling.

**Target Audience**: Frontend development agency implementing CSR web app  
**Scope**: CSR surface only (not Executive webapp or Rep mobile app)

---

## 0. Global Integration Rules

### 0.1 Authentication & Tenant Scoping

**Every CSR frontend API call MUST:**

1. **Include JWT in Authorization header**:
   ```
   Authorization: Bearer <JWT>
   ```
   - JWT is supplied by the auth layer (Clerk or equivalent)
   - JWT contains `user_id`, `company_id`, and `role` claims
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
const response = await fetch(`${API_BASE_URL}/api/v1/contact-cards/${contactId}`, {
  headers: {
    'Authorization': `Bearer ${jwtToken}`,
    'Content-Type': 'application/json',
  },
});
```

---

### 0.2 Idempotency & Client Behavior

**Backend Idempotency Mechanisms**:
- `Idempotency-Key` headers in Otto → Shunya calls (handled backend-side)
- Natural keys for Tasks and KeySignals (prevent duplicates)
- `ShunyaJob` output hashing (prevents duplicate processing)
- State checks (Lead status/appointment outcome only update if changed)

**Frontend Requirements**:

1. **Avoid Double-Submission**:
   - Disable submit buttons while request is in-flight
   - Show loading states during mutations
   - Prevent rapid clicks (debounce or disable button)

2. **Handle Error Responses Gracefully**:
   - `409 Conflict`: Resource conflict (e.g., duplicate task) → Show user-friendly message
   - `429 Too Many Requests`: Rate limit exceeded → Show retry message, implement exponential backoff
   - `500 Internal Server Error`: Server error → Show generic error, allow retry
   - `400 Bad Request`: Invalid input → Show validation errors from response

3. **Optimistic Updates**:
   - Only update UI optimistically when safe (e.g., marking task complete)
   - If request fails, revert optimistic update and show error
   - For critical mutations (create appointment, update lead status), wait for server confirmation

4. **No Idempotency Headers Required**:
   - Frontend does NOT need to send `Idempotency-Key` headers
   - Backend handles all idempotency internally
   - Frontend should assume backend may deduplicate repeated requests

**Example**:
```typescript
const [isSubmitting, setIsSubmitting] = useState(false);

const handleCompleteTask = async (taskId: string) => {
  if (isSubmitting) return; // Prevent double-submission
  
  setIsSubmitting(true);
  try {
    await apiPost(`/api/v1/tasks/${taskId}/complete`);
    // Optimistically update UI
    setTasks(tasks.map(t => t.id === taskId ? { ...t, status: 'completed' } : t));
  } catch (error) {
    if (error.status === 409) {
      // Task already completed - refresh from server
      await refetchTasks();
    } else {
      // Show error message
      showError('Failed to complete task');
    }
  } finally {
    setIsSubmitting(false);
  }
};
```

---

### 0.3 RBAC (Role-Based Access Control)

**CSR Role**:
- JWT contains `role: "csr"` claim
- Backend enforces role-based access via `@require_role("csr", ...)` decorators
- CSR may only see/modify resources they are permitted to by backend

**CSR Data Scoping**:
- ✅ **Can Access**:
  - Own calls (filtered by `Call.owner_id == csr_user_id`)
  - Own leads (filtered by CSR ownership)
  - Own tasks (filtered by `Task.assignee_id == csr_user_id`)
  - Company-wide auto-queued leads (shared pool for all CSRs)
- ❌ **Cannot Access**:
  - Other CSRs' personal calls/leads/tasks
  - Sales Rep appointments
  - Manager-only endpoints (use Exec views instead)

**Ask Otto RBAC**:
- When CSR uses Ask Otto, backend automatically sends `X-Target-Role: customer_rep` to Shunya
- Shunya scopes responses to CSR-accessible data (calls, leads, not rep appointments)
- Context includes only that CSR's identity: `{"user_role": "csr", "csr_id": <current_user_id>}`
- Does NOT include other reps' metrics or company-level aggregates

**403 Forbidden Handling**:
- If backend returns `403`, treat as "insufficient permissions"
- Show user-friendly message: "You don't have permission to perform this action"
- Never force through 403 errors in UI
- Log 403 errors for security monitoring

**CSR Permissions**:
- ✅ Can view own calls, leads, appointments
- ✅ Can view company-wide missed calls (for recovery)
- ✅ Can create/update tasks assigned to CSR
- ✅ Can acknowledge key signals
- ✅ Can view contact cards and lead details
- ✅ Can view message threads
- ❌ Cannot assign leads to reps (manager-only)
- ❌ Cannot access manager-only endpoints
- ❌ Cannot modify other CSRs' data

**Example**:
```typescript
try {
  const response = await apiGet('/api/v1/lead-pool');
} catch (error) {
  if (error.status === 403) {
    // Show permission denied message
    showError('You do not have permission to view the lead pool');
  }
}
```

---

## 1. CSR Frontend Screens Identified

Based on exploration of `/Users/tusharmehrotra/otto`, the following CSR-focused screens have been identified:

### 1.1 CSR Home / Dashboard
**File(s)**: `src/app/(receptionsit)/page.tsx`

**Components**:
- `HeaderSection` - Header with navigation
- `HeroSection` - Ask Otto prompt input
- `OverviewSection` - Overview metrics/charts
- `DeliverablesSection` - Call back list, emergencies, coaching tips
- `FocusedPromptView` - Chat interface for Ask Otto queries
- `CollapsibleSidebar` - Recent chats sidebar

**Purpose**: Main landing page for CSR with Ask Otto chat interface and overview metrics.

---

### 1.2 Receptionist Dashboard / Performance View
**File(s)**: `src/app/(receptionsit)/receptionist/page.tsx`

**Components**:
- `InsightCard` - Coaching insights and recommendations
- `CallStats` - Dashboard metrics (booking rate, total leads, etc.)
- `BookingRateChart` - Booking rate improvement chart
- `TopObjections` - Top objections component
- `MissedCallsRecovery` - Missed calls recovery overview
- `MissedLeadsDashboard` - Missed leads dashboard (kanban/list view)
- `LeadsTableCard` - Queued leads ready for booking
- `ExpandedTableCard` - Unbooked leads table
- `ArchivedLeadsPanel` - Archived leads drawer
- `LeadDetailsDialog` - Lead details drawer

**Purpose**: CSR performance dashboard showing personal stats, company leads, missed calls, and coaching insights.

---

### 1.3 Missed Calls Recovery
**File(s)**: 
- `src/components/missed-calls-recovery.tsx`
- `src/components/sections/MissedLeadsDashboard.tsx`

**Components**:
- `MissedCallsRecovery` - Recovery metrics (missed calls, saved calls, Otto rescues, success rate)
- `MissedLeadsDashboard` - Kanban/list view of missed leads (booked/pending/dead)

**Purpose**: Surface missed calls for recovery and track recovery metrics.

---

### 1.4 Lead Details Dialog
**File(s)**: `src/components/LeadDetailsDialog.tsx`

**Components**:
- Lead info section (name, phone, status badges)
- Overall engagement section
- Text messaging section (key highlights, conversation thread)
- Previous/Next navigation

**Purpose**: Detailed view of a single lead with engagement metrics and message history.

---

### 1.5 Top Objections
**File(s)**: `src/components/top-objections.tsx`

**Components**:
- Objections list with percentages
- `ObjectionsDetailDialog` - Detailed objections view

**Purpose**: Display most common objections encountered during calls.

---

### 1.6 Archived Leads Panel
**File(s)**: `src/components/sections/ArchivedLeadsPanel.tsx`

**Components**:
- Search input
- Archived lead cards
- `LeadDetailsDialog` integration

**Purpose**: View and search archived/closed leads.

---

## 2. Screen-by-Screen Integration Specs

---

## Screen: CSR Home / Ask Otto

**File(s)**: `src/app/(receptionsit)/page.tsx` (HeroSection, FocusedPromptView)

### Purpose

Main landing page for CSR with Ask Otto chat interface. CSR can ask natural language questions about their performance, calls, leads, and tasks. Responses are automatically scoped to that CSR's data only.

### Data Source

**Endpoint**: `POST /api/v1/rag/query`

**Method**: POST

**Auth**: Requires CSR role (JWT with `role: "csr"`)

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
  query_id: string;                 // Unique query ID (guaranteed non-null)
  query: string;                    // Original query
  answer: string;                   // Answer text (guaranteed non-null)
  citations: Citation[];            // Source citations (may be empty if processing)
  confidence_score: number;         // 0.0-1.0 (may be 0.0 if processing incomplete)
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

### Fields Used by UI

- **`answer`** (string) → Display in chat message bubble
- **`citations`** (array) → Show as expandable "Sources" section below answer
- **`confidence_score`** (number) → Display confidence indicator (e.g., "High confidence" if > 0.8)
- **`query_id`** (string) → Store for query history/analytics

### Role Scoping Notes

- **CSR Scope Only**: When called by a CSR, backend automatically sends `X-Target-Role: customer_rep` to Shunya
- **Data Included**: Only that CSR's calls, leads, and tasks (not company-wide or other CSRs' data)
- **Context Passed**: `{"user_role": "csr", "csr_id": <current_user_id>}`
- **Shunya Fields**: All semantic analysis (objections, qualification, booking) comes from Shunya. Otto never overrides Shunya's semantics.

### Example Request

```typescript
const response = await apiPost<RAGQueryResponse>('/api/v1/rag/query', {
  query: "What are my top objections this month?",
  filters: { date_range: "last_30_days" },
  max_results: 10
});
```

### Example Response

```json
{
  "success": true,
  "data": {
    "query_id": "query_abc123",
    "query": "What are my top objections this month?",
    "answer": "Your top objections this month are: 'price too high' (40%), 'need to think about it' (28%), and 'not the right time' (15%)...",
    "citations": [
      {
        "doc_id": "call_456",
        "chunk_text": "Customer mentioned price concerns during call...",
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

### Edge Cases & Error Handling

- **Empty `citations` array**: Show answer without sources section (Shunya may still be processing)
- **`confidence_score` is 0.0**: Show "Processing..." indicator (Shunya analysis incomplete)
- **Network timeout**: Show "Query taking longer than expected" message, allow retry
- **403 Forbidden**: Show "You don't have permission" message (should not occur for CSR role)
- **500 Internal Server Error**: Show generic error, allow retry

---

## Screen: CSR Home / Overview Card

**File(s)**: `src/app/(receptionsit)/page.tsx` (OverviewSection)

### Purpose

Display CSR overview metrics card showing key performance indicators: booking rate, qualified leads, booked appointments, top reason for missed bookings, and pending leads.

### Data Source

**Endpoint**: `GET /api/v1/metrics/csr/overview/self`

**Method**: GET

**Auth**: Requires CSR role only

**When Called**: On page load, and optionally on date range change

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date (defaults to 30 days ago)
- `date_to` (optional, ISO8601): End date (defaults to now)

### Response Schema

```typescript
interface CSROverviewSelfResponse {
  total_calls: number;
  qualified_calls: number;
  qualified_rate: number | null;                    // qualified_calls / total_calls
  booked_calls: number;
  booking_rate: number | null;                      // booked_calls / qualified_calls
  service_not_offered_calls: number;
  service_not_offered_rate: number | null;          // service_not_offered_calls / qualified_calls
  avg_objections_per_qualified_call: number | null;
  qualified_but_unbooked_calls: number;
  avg_compliance_score: number | null;              // 0-10 scale
  open_followups: number;
  overdue_followups: number;
  top_reason_for_missed_bookings: string | null;
  pending_leads_count: number | null;
  top_missed_booking_reason: string | null;        // Top objection for missed bookings
}
```

### Fields Used by UI

| UI Element | API Field | Notes |
|------------|-----------|-------|
| "Top reason for missed bookings" | `top_missed_booking_reason` | Display as text (e.g., "Price too high") |
| "Booked appointments count" | `booked_calls` | Display as number (e.g., "90") |
| "Booking rate" | `booking_rate` | Display as percentage (e.g., "75%") - format `(booking_rate * 100).toFixed(1) + '%'` |
| "Qualified leads" | `qualified_calls` | Display as number |
| "Total leads" | `total_calls` | Display as number |
| "Pending leads" | `qualified_but_unbooked_calls` | Alternative: use `pending_leads_count` if available |

### Role Scoping Notes

- **CSR Self-Scoped**: Automatically filtered to authenticated CSR user (`Call.owner_id == csr_user_id`)
- **No `csr_id` Parameter**: CSR identity is extracted from JWT token
- **Shunya Source of Truth**: All booking/qualification fields come from Shunya (`CallAnalysis.*`). Otto never infers booking from appointments table.

### Example Request

```typescript
const overview = await apiGet<CSROverviewSelfResponse>(
  '/api/v1/metrics/csr/overview/self?date_from=2025-01-01&date_to=2025-01-31'
);
```

### Example Response

```json
{
  "success": true,
  "data": {
    "total_calls": 150,
    "qualified_calls": 120,
    "qualified_rate": 0.8,
    "booked_calls": 90,
    "booking_rate": 0.75,
    "service_not_offered_calls": 10,
    "service_not_offered_rate": 0.083,
    "avg_objections_per_qualified_call": 1.5,
    "qualified_but_unbooked_calls": 20,
    "avg_compliance_score": 8.5,
    "open_followups": 15,
    "overdue_followups": 3,
    "top_reason_for_missed_bookings": "price too high",
    "pending_leads_count": 25,
    "top_missed_booking_reason": "price too high"
  }
}
```

### Edge Cases & Error Handling

- **Null rates** (`qualified_rate`, `booking_rate`): Show "N/A" or "—" if denominator is 0
- **Empty data**: Show zeros for all counts, "No data" for text fields
- **403 Forbidden**: Should not occur for CSR role, but show permission error if it does
- **500 Error**: Show retry button, allow manual refresh

---

## Screen: CSR Dashboard / Booking Trend

**File(s)**: `src/app/(receptionsit)/receptionist/page.tsx` (BookingRateChart)

### Purpose

Display booking rate trend over time (e.g., "32% last month → 78% this month") as a line chart showing improvement over time periods.

### Data Source

**Endpoint**: `GET /api/v1/metrics/csr/booking-trend/self`

**Method**: GET

**Auth**: Requires CSR role only

**When Called**: On page load, and when date range or granularity changes

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date
- `date_to` (optional, ISO8601): End date
- `granularity` (optional, default: "month"): Time bucket size - `"day"`, `"week"`, or `"month"`

### Response Schema

```typescript
interface CSRBookingTrendSelfResponse {
  summary: {
    total_leads: number;
    total_qualified_leads: number;                  // From Shunya lead_quality
    total_booked_calls: number;                    // From Shunya booking_status
    current_booking_rate: number | null;            // booked / qualified
  };
  booking_rate_trend: Array<{
    timestamp: string;                               // YYYY-MM-DD format
    value: number | null;                           // Booking rate for this period (0.0-1.0)
  }>;
}
```

### Fields Used by UI

**Summary Section** (optional, can show above chart):
- `summary.total_leads` → "Total Leads" stat
- `summary.total_qualified_leads` → "Qualified Leads" stat
- `summary.total_booked_calls` → "Booked Calls" stat
- `summary.current_booking_rate` → "Current Booking Rate" stat (format as percentage)

**Chart Data**:
- `booking_rate_trend[].timestamp` → X-axis labels (format: "Jan 1", "Jan 8", etc.)
- `booking_rate_trend[].value` → Y-axis values (convert to percentage: `value * 100`)

**Trend Comparison** (e.g., "32% last month → 78% this month"):
- Compare first and last `value` in `booking_rate_trend` array
- Format: `"${firstValue * 100}% last ${granularity} → ${lastValue * 100}% this ${granularity}"`

### Role Scoping Notes

- **CSR Self-Scoped**: Automatically filtered to authenticated CSR user
- **Shunya Source of Truth**: All booking/qualification derived ONLY from Shunya fields (`CallAnalysis.booking_status`, `CallAnalysis.lead_quality`)
- **Never Infer from Appointments**: Otto never infers booking from appointments table

### Example Request

```typescript
const trend = await apiGet<CSRBookingTrendSelfResponse>(
  '/api/v1/metrics/csr/booking-trend/self?granularity=month&date_from=2025-01-01&date_to=2025-01-31'
);
```

### Example Response

```json
{
  "success": true,
  "data": {
    "summary": {
      "total_leads": 150,
      "total_qualified_leads": 120,
      "total_booked_calls": 90,
      "current_booking_rate": 0.75
    },
    "booking_rate_trend": [
      {
        "timestamp": "2025-01-01",
        "value": 0.72
      },
      {
        "timestamp": "2025-01-08",
        "value": 0.78
      },
      {
        "timestamp": "2025-01-15",
        "value": 0.75
      }
    ]
  }
}
```

### Edge Cases & Error Handling

- **Null `value` in trend points**: Skip that point or show as "No data" on chart
- **Empty `booking_rate_trend` array**: Show "No data available" message
- **Invalid `granularity`**: Backend returns 400, show error message
- **403 Forbidden**: Should not occur for CSR role

---

## Screen: CSR Dashboard / Unbooked Appointments Card

**File(s)**: `src/app/(receptionsit)/receptionist/page.tsx` (ExpandedTableCard, UnbookedLeadsTable)

### Purpose

Display table/list of unbooked calls for the CSR. Each row represents a call that did not result in a booking. Clicking a row navigates to the customer/contact card.

### Data Source

**Endpoint**: `GET /api/v1/calls/unbooked/self`

**Method**: GET

**Auth**: Requires CSR role only

**When Called**: On page load, and on pagination/date filter changes

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date
- `date_to` (optional, ISO8601): End date
- `page` (optional, default: 1): Page number (1-indexed)
- `page_size` (optional, default: 50): Page size (1-200)

### Response Schema

```typescript
interface UnbookedCallsSelfResponse {
  items: Array<{
    call_id: number;
    customer_name: string | null;
    phone: string | null;
    booking_status: string;                         // From Shunya enum (e.g., "not_booked", "service_not_offered")
    qualified: boolean | null;                      // Derived from Shunya lead_quality
    status: "pending";                              // Always "pending" for unbooked
    last_contacted_at: string | null;               // ISO8601 timestamp
  }>;
  page: number;
  page_size: number;
  total: number;
}
```

### Fields Used by UI

**Table Columns**:
- **Customer Name** → `customer_name` (show "Unknown" if null)
- **Phone** → `phone` (format: `(XXX) XXX-XXXX` if US number)
- **Booking Status** → `booking_status` (display as badge: "Not Booked", "Service Not Offered", etc.)
- **Qualified** → `qualified` (show checkmark if `true`, "—" if `null`)
- **Last Contacted** → `last_contacted_at` (format: "Jan 15, 2:30 PM" or relative time "2 hours ago")

**Row Click Action**:
- Navigate to contact card using `call_id` or `lead_id` (if available)
- **Recommended**: Use `call_id` to fetch call details, then extract `contact_card_id` from call record
- **Alternative**: If `lead_id` is available in response, use that to fetch contact card

### Role Scoping Notes

- **CSR Self-Scoped**: Automatically filtered to authenticated CSR user (`Call.owner_id == csr_user_id`)
- **Unbooked Definition**: Any call where Shunya's `booking_status` is NOT `"booked"` (includes `"not_booked"`, `"service_not_offered"`, etc.)

### Example Request

```typescript
const unbooked = await apiGet<UnbookedCallsSelfResponse>(
  '/api/v1/calls/unbooked/self?page=1&page_size=50&date_from=2025-01-01'
);
```

### Example Response

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "call_id": 123,
        "customer_name": "John Doe",
        "phone": "+1234567890",
        "booking_status": "not_booked",
        "qualified": true,
        "status": "pending",
        "last_contacted_at": "2025-01-15T10:30:00Z"
      },
      {
        "call_id": 124,
        "customer_name": "Jane Smith",
        "phone": "+1987654321",
        "booking_status": "service_not_offered",
        "qualified": true,
        "status": "pending",
        "last_contacted_at": "2025-01-14T14:20:00Z"
      }
    ],
    "page": 1,
    "page_size": 50,
    "total": 25
  }
}
```

### Edge Cases & Error Handling

- **Null `customer_name`**: Show "Unknown Customer"
- **Null `phone`**: Show "No phone" or "—"
- **Null `last_contacted_at`**: Show "Never" or "—"
- **Empty `items` array**: Show "No unbooked calls" empty state
- **Pagination**: Show page controls if `total > page_size`

---

## Screen: CSR Dashboard / Top Objections + Drilldown

**File(s)**: `src/app/(receptionsit)/receptionist/page.tsx` (TopObjections, ObjectionsDetailDialog)

### Purpose

Display top objections encountered by the CSR. Show top 5 by default, with ability to expand to see all. Clicking an objection shows a drilldown list of calls where that objection occurred, with ability to play recordings.

### Data Sources

**Top List Endpoint**: `GET /api/v1/metrics/csr/objections/self`

**Drilldown Endpoint**: `GET /api/v1/calls/by-objection/self`

### Top Objections List

**Endpoint**: `GET /api/v1/metrics/csr/objections/self`

**Method**: GET

**Auth**: Requires CSR role only

**When Called**: On page load, and when date range changes

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date
- `date_to` (optional, ISO8601): End date

**Response Schema**:

```typescript
interface CSRObjectionsSelfResponse {
  top_objections: Array<{                           // Top 5 objections
    objection: string;                               // Objection key/text
    occurrence_count: number;
    occurrence_rate: number;                          // 0.0-1.0
    qualified_unbooked_occurrence_rate: number | null; // Rate over qualified but unbooked calls
  }>;
  all_objections: Array<{                            // All objections
    objection: string;
    occurrence_count: number;
    occurrence_rate: number;
    qualified_unbooked_occurrence_rate: number | null;
  }>;
}
```

**Fields Used by UI**:
- **Top 5 List** → Use `top_objections` array
- **Expanded All List** → Use `all_objections` array
- **Objection Text** → `objection` (display as label)
- **Occurrence Count** → `occurrence_count` (display as number)
- **Occurrence Rate** → `occurrence_rate` (display as percentage: `(occurrence_rate * 100).toFixed(1) + '%'`)

### Objection Drilldown

**Endpoint**: `GET /api/v1/calls/by-objection/self`

**Method**: GET

**Auth**: Requires CSR role only

**When Called**: When user clicks an objection from the top list

**Query Parameters**:
- `objection` (required, string): Objection key to filter by (URL-encode if contains spaces)
- `date_from` (optional, ISO8601): Start date
- `date_to` (optional, ISO8601): End date
- `page` (optional, default: 1): Page number (1-indexed)
- `page_size` (optional, default: 50): Page size (1-200)

**Response Schema**:

```typescript
interface CallsByObjectionSelfResponse {
  items: Array<{
    call_id: number;
    customer_name: string | null;
    started_at: string;                             // ISO8601 timestamp
    duration_seconds: number | null;
    booking_status: string | null;                  // From Shunya
    audio_url: string | null;                        // Audio URL if available (for playback)
  }>;
  page: number;
  page_size: number;
  total: number;
}
```

**Fields Used by UI**:
- **Call List** → `items` array (display in table/list)
- **Customer Name** → `customer_name` (show "Unknown" if null)
- **Call Date/Time** → `started_at` (format: "Jan 15, 2:30 PM")
- **Duration** → `duration_seconds` (format: "3m 45s")
- **Booking Status** → `booking_status` (display as badge)
- **Play Recording** → `audio_url` (if present, show play button; if null, disable play button)

### Role Scoping Notes

- **CSR Self-Scoped**: Both endpoints automatically filtered to authenticated CSR user
- **Shunya Source**: Objections come from Shunya `CallAnalysis.objections` array

### Example Requests

```typescript
// Get top objections
const objections = await apiGet<CSRObjectionsSelfResponse>(
  '/api/v1/metrics/csr/objections/self?date_from=2025-01-01'
);

// Get calls for specific objection (when user clicks "price too high")
const calls = await apiGet<CallsByObjectionSelfResponse>(
  '/api/v1/calls/by-objection/self?objection=price%20too%20high&page=1&page_size=50'
);
```

### Example Responses

**Top Objections**:
```json
{
  "success": true,
  "data": {
    "top_objections": [
      {
        "objection": "price too high",
        "occurrence_count": 40,
        "occurrence_rate": 0.27,
        "qualified_unbooked_occurrence_rate": 0.35
      },
      {
        "objection": "need to think about it",
        "occurrence_count": 28,
        "occurrence_rate": 0.19,
        "qualified_unbooked_occurrence_rate": 0.25
      }
    ],
    "all_objections": [
      // ... all objections
    ]
  }
}
```

**Calls by Objection**:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "call_id": 123,
        "customer_name": "John Doe",
        "started_at": "2025-01-15T10:30:00Z",
        "duration_seconds": 180,
        "booking_status": "not_booked",
        "audio_url": "https://storage.example.com/audio/call_123.mp3"
      }
    ],
    "page": 1,
    "page_size": 50,
    "total": 40
  }
}
```

### Edge Cases & Error Handling

- **Empty `top_objections` array**: Show "No objections found" message
- **Null `audio_url`**: Disable play button, show "Recording not available"
- **Invalid `objection` parameter**: Backend returns 400, show error message
- **Pagination**: Show page controls if `total > page_size`

---

## Screen: CSR Dashboard / Auto AI-Queued Leads Ready for Booking

**File(s)**: `src/app/(receptionsit)/receptionist/page.tsx` (LeadsTableCard)

### Purpose

Display list of prospects that Otto AI recovered from missed calls/texts and queued as "ready for booking". This is a company-wide shared pool visible to all CSRs (not CSR-specific).

### Data Source

**Endpoint**: `GET /api/v1/metrics/csr/auto-queued-leads`

**Method**: GET

**Auth**: Requires CSR or manager role

**When Called**: On page load, and when date range changes

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date
- `date_to` (optional, ISO8601): End date

### Response Schema

```typescript
interface AutoQueuedLeadsResponse {
  items: Array<{
    lead_id: string;
    customer_name: string | null;
    phone: string | null;
    last_contacted_at: string | null;                // ISO8601 timestamp
    status: string;                                 // e.g., "pending", "scheduled"
  }>;
}
```

### Fields Used by UI

**Table/List Columns**:
- **Customer Name** → `customer_name` (show "Unknown" if null)
- **Phone** → `phone` (format: `(XXX) XXX-XXXX`)
- **Status** → `status` (display as badge: "Pending", "Scheduled", etc.)
- **Last Contacted** → `last_contacted_at` (format: "Jan 15, 2:30 PM" or relative time)

**Row Click Action**:
- Navigate to contact card using `lead_id`
- Call `GET /api/v1/contact-cards/{contact_card_id}` (extract from lead record)

### Role Scoping Notes

- **Company-Wide**: Data is shared across all CSRs in the company (not filtered to individual CSR)
- **Source**: Pulled from missed calls/texts that Otto AI handled
- **Purpose**: Leads ready for booking that any CSR can pick up

### Example Request

```typescript
const leads = await apiGet<AutoQueuedLeadsResponse>(
  '/api/v1/metrics/csr/auto-queued-leads?date_from=2025-01-01'
);
```

### Example Response

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "lead_id": "lead_123",
        "customer_name": "Jane Smith",
        "phone": "+1987654321",
        "last_contacted_at": "2025-01-15T14:20:00Z",
        "status": "pending"
      }
    ]
  }
}
```

### Edge Cases & Error Handling

- **Empty `items` array**: Show "No auto-queued leads available" empty state
- **Null `customer_name`**: Show "Unknown Customer"
- **Null `last_contacted_at`**: Show "Never" or "—"

---

## Screen: CSR Dashboard / Missed Call Recovery Overview

**File(s)**: `src/app/(receptionsit)/receptionist/page.tsx` (MissedCallsRecovery, MissedLeadsDashboard)

### Purpose

Display high-level missed call recovery metrics and three lists/columns showing booked, pending, and dead leads from missed calls.

### Data Sources

**Metrics Endpoint**: `GET /api/v1/metrics/csr/missed-calls/self`

**Leads List Endpoint**: `GET /api/v1/leads/missed/self`

### High-Level Metrics

**Endpoint**: `GET /api/v1/metrics/csr/missed-calls/self`

**Method**: GET

**Auth**: Requires CSR role only

**When Called**: On page load, and when date range changes

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date
- `date_to` (optional, ISO8601): End date

**Response Schema**:

```typescript
interface CSRMissedCallsSelfResponse {
  total_missed_calls: number;
  total_saved_calls: number;                        // From Shunya booking_status (eventually booked)
  total_saved_by_otto: number;                     // Saved via Otto AI auto-rescue
  booked_leads_count: number;                       // From Shunya
  pending_leads_count: number;
  dead_leads_count: number;
}
```

**Fields Used by UI** (High-Level Metrics Cards):
- **"Total Missed Calls"** → `total_missed_calls`
- **"Total Saved Calls"** → `total_saved_calls`
- **"Total Saved by Otto"** → `total_saved_by_otto`
- **"Booked Leads"** → `booked_leads_count`
- **"Pending Leads"** → `pending_leads_count`
- **"Dead Leads"** → `dead_leads_count`

### Leads Lists (Booked/Pending/Dead)

**Endpoint**: `GET /api/v1/leads/missed/self`

**Method**: GET

**Auth**: Requires CSR role only

**When Called**: On page load, and when status filter or pagination changes

**Query Parameters**:
- `status` (optional): Filter by status - `"booked"`, `"pending"`, or `"dead"` (call three times, once for each status)
- `date_from` (optional, ISO8601): Start date
- `date_to` (optional, ISO8601): End date
- `page` (optional, default: 1): Page number (1-indexed)
- `page_size` (optional, default: 50): Page size (1-200)

**Response Schema**:

```typescript
interface MissedLeadsSelfResponse {
  items: Array<{
    lead_id: string;
    customer_name: string | null;
    status: "booked" | "pending" | "dead";         // From Shunya booking/outcome
    source: "missed_call" | "missed_text";
    last_contacted_at: string | null;              // ISO8601 timestamp
    next_action: string | null;
    next_action_due_at: string | null;            // ISO8601 timestamp
    attempt_count: number;                          // From CallRail/Twilio (non-Shunya)
  }>;
  page: number;
  page_size: number;
  total: number;
}
```

**Fields Used by UI** (Per Lead Item):
- **Customer Name** → `customer_name` (show "Unknown" if null)
- **Status** → `status` (display as badge: "Booked", "Pending", "Dead")
- **Source** → `source` (display as icon/badge: "Missed Call" or "Missed Text")
- **Last Contacted** → `last_contacted_at` (format: "Jan 15, 2:30 PM")
- **Next Action** → `next_action` (display as text, e.g., "Follow up call")
- **Next Action Due** → `next_action_due_at` (format: "Jan 20, 9:00 AM" or relative time)
- **Attempt Count** → `attempt_count` (display as "X attempts")

**UI Mapping**:
- **"Booked" Column** → Call endpoint with `status=booked`
- **"Pending" Column** → Call endpoint with `status=pending`
- **"Dead" Column** → Call endpoint with `status=dead`

### Role Scoping Notes

- **CSR Self-Scoped**: Both endpoints automatically filtered to authenticated CSR user
- **Data Sources**:
  - **From Shunya**: `status` (booked/dead classification), booking/outcome
  - **From CallRail/Twilio**: `attempt_count`, `last_contacted_at` (non-Shunya fields)

### Example Requests

```typescript
// Get high-level metrics
const metrics = await apiGet<CSRMissedCallsSelfResponse>(
  '/api/v1/metrics/csr/missed-calls/self?date_from=2025-01-01'
);

// Get booked leads
const booked = await apiGet<MissedLeadsSelfResponse>(
  '/api/v1/leads/missed/self?status=booked&page=1&page_size=50'
);

// Get pending leads
const pending = await apiGet<MissedLeadsSelfResponse>(
  '/api/v1/leads/missed/self?status=pending&page=1&page_size=50'
);

// Get dead leads
const dead = await apiGet<MissedLeadsSelfResponse>(
  '/api/v1/leads/missed/self?status=dead&page=1&page_size=50'
);
```

### Example Responses

**Metrics**:
```json
{
  "success": true,
  "data": {
    "total_missed_calls": 50,
    "total_saved_calls": 35,
    "total_saved_by_otto": 20,
    "booked_leads_count": 25,
    "pending_leads_count": 10,
    "dead_leads_count": 15
  }
}
```

**Leads List**:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "lead_id": "lead_123",
        "customer_name": "John Doe",
        "status": "pending",
        "source": "missed_call",
        "last_contacted_at": "2025-01-15T10:30:00Z",
        "next_action": "Follow up call",
        "next_action_due_at": "2025-01-20T09:00:00Z",
        "attempt_count": 2
      }
    ],
    "page": 1,
    "page_size": 50,
    "total": 25
  }
}
```

### Edge Cases & Error Handling

- **Empty `items` array for a status**: Show empty state for that column (e.g., "No pending leads")
- **Null `customer_name`**: Show "Unknown Customer"
- **Null `next_action`**: Show "—" or "No action"
- **Invalid `status` parameter**: Backend returns 400, show error message
- **Pagination**: Show page controls if `total > page_size`

---

## Screen: Receptionist Dashboard / Performance View

**File(s)**: `src/app/(receptionsit)/receptionist/page.tsx`

### Purpose

CSR performance dashboard showing personal stats, company-wide leads, missed calls recovery, coaching insights, and actionable lead lists.

### Backend Endpoints Used

| Purpose / Action                         | Method | Endpoint                                      | When Called                  | Notes |
|------------------------------------------|--------|-----------------------------------------------|------------------------------|-------|
| Load dashboard metrics                   | GET    | `/api/v1/dashboard/metrics`                   | On page load                 | Personal + company metrics |
| Load booking rate chart                  | GET    | `/api/v1/dashboard/booking-rate`              | On page load                 | Time series data |
| Load top objections                      | GET    | `/api/v1/dashboard/top-objections`             | On page load                 | Company-wide objections |
| Load missed calls recovery               | GET    | `/api/v1/missed-calls/queue/metrics`          | On page load                 | Recovery metrics |
| Load missed calls queue                  | GET    | `/api/v1/missed-calls/queue/entries`          | On page load                 | Missed calls list |
| Load unbooked leads                      | GET    | `/api/v1/leads?status=qualified_unbooked`     | On page load                 | Unbooked qualified leads |
| Load queued leads (Otto AI)               | GET    | `/api/v1/leads?status=qualified_unbooked&priority=high` | On page load | High-priority leads |
| Load leads by priority                    | GET    | `/api/v1/leads?status=qualified_unbooked`     | On page load + sort          | Priority-sorted leads |
| Load contact card detail                 | GET    | `/api/v1/contact-cards/{contact_card_id}`     | On lead name click           | Full contact card |
| Load archived leads                      | GET    | `/api/v1/leads?status=closed_lost,closed_won` | On archive panel open        | Archived leads |

### Data Mapping (Backend → UI)

**Dashboard Metrics** (`GET /api/v1/dashboard/metrics`):
- `data.booking_rate` → "Booking rate" stat (format as percentage)
- `data.total_leads` → "Total Leads" stat (format with commas)
- `data.qualified_leads` → "Qualified Leads" stat (format with commas)
- `data.booked_appointments` → "Booked Appointments" stat (format with commas)

**Booking Rate Chart** (`GET /api/v1/dashboard/booking-rate`):
- `data[]` → Chart data points
  - `date` → X-axis label (format: "Sep 1", "Sep 5", etc.)
  - `rate` → Y-axis value (percentage)

**Top Objections** (`GET /api/v1/dashboard/top-objections`):
- `data[]` → Objections list
  - `label` → Objection text (display in list)
  - `percentage` → Progress bar value (0-100)

**Missed Calls Recovery** (`GET /api/v1/missed-calls/queue/metrics`):
- `data.metrics.missed_calls` → "Missed Calls" stat card
- `data.metrics.saved_calls` → "Saved Calls" stat card (with info tooltip)
- `data.metrics.otto_rescues` → "Otto Rescues" stat card (with info tooltip)
- `data.metrics.success_rate` → Progress bar value and text ("X% of Otto-assisted missed calls booked")

**Unbooked Leads Table** (`GET /api/v1/leads?status=qualified_unbooked`):
- `data[]` → Table rows
  - `contact_card.first_name + last_name` → "Name" column
  - `contact_card.primary_phone` → "Phone Number" column
  - `lead.source` → "Reason for not booking" (derived from lead metadata)
  - `lead.last_contacted_at` → "Last Spoken with" (format: "2:00 PM, Sep 8")
  - `contact_card.address` → "Details" column (truncated)

**Queued Leads (Otto AI)** (`GET /api/v1/leads?status=qualified_unbooked&priority=high`):
- `data[]` → Table rows
  - `contact_card.first_name + last_name` → "Name" (clickable, opens LeadDetailsDialog)
  - `contact_card.primary_phone` → "Phone Number"
  - Lead metadata → "Service Requested"
  - Appointment metadata → "Availability"
  - `contact_card.address` → "Address"
  - `lead.tags` or AI summary → "Details (Captured by Otto AI)"

**Leads by Priority** (`GET /api/v1/leads?status=qualified_unbooked`):
- `data[]` → Table rows (sorted by priority/urgency)
  - `contact_card.first_name + last_name` → "Name" (clickable)
  - `contact_card.primary_phone` → "Phone Number"
  - `lead.source` → "Lead Source"
  - Lead metadata → "Reason Not Booked"
  - `lead.created_at` → "Date"
  - `lead.last_contacted_at` → "Last Touched"
  - Assigned rep info → "Agent"
  - `lead.priority` → "Urgency" badge (High/Medium/Low)
  - Objections data → "Objection & Response"

**Contact Card Detail** (`GET /api/v1/contact-cards/{contact_card_id}`):
- See "Contact Card / Customer Detail" screen section below

### User Actions → API Calls

- **When CSR clicks lead name**:
  - Call `GET /api/v1/contact-cards/{contact_card_id}` (from `lead.contact_card_id`)
  - Open `LeadDetailsDialog` with contact card data

- **When CSR clicks "View Archived Leads"**:
  - Call `GET /api/v1/leads?status=closed_lost,closed_won`
  - Open `ArchivedLeadsPanel` drawer

- **When CSR clicks "View Details" on objection**:
  - Open `ObjectionsDetailDialog` (uses same top objections data)

- **When CSR clicks "Expand to see all" in Missed Leads Dashboard**:
  - Call `GET /api/v1/missed-calls/queue/entries?page_size=100` (increase limit)
  - Update kanban/list view with expanded data

### Edge Cases & Error Handling

- **404 on metrics**: Show empty state, allow manual refresh
- **403 (permission denied)**: Show "You don't have permission" message
- **500 or network error**: Show retry button, log error
- **Empty leads list**: Show "No unbooked leads" message
- **Empty missed calls**: Show "No missed calls" message

---

## Screen: Missed Calls Recovery

**File(s)**: 
- `src/components/missed-calls-recovery.tsx`
- `src/components/sections/MissedLeadsDashboard.tsx`

### Purpose

Surface missed calls for recovery, track recovery metrics, and manage missed leads in kanban/list view.

### Backend Endpoints Used

| Purpose / Action                         | Method | Endpoint                                      | When Called                  | Notes |
|------------------------------------------|--------|-----------------------------------------------|------------------------------|-------|
| Load missed calls recovery metrics       | GET    | `/api/v1/missed-calls/queue/metrics`          | On component mount           | Recovery stats |
| Load missed calls queue entries          | GET    | `/api/v1/missed-calls/queue/entries`          | On component mount + refresh | Missed calls list |
| Load missed calls (alternative)          | GET    | `/api/v1/dashboard/calls?status=missed&company_id={id}` | On component mount | Alternative endpoint |
| Load contact card for missed call        | GET    | `/api/v1/contact-cards/{contact_card_id}`     | On lead card click           | Full contact details |

### Data Mapping (Backend → UI)

**Missed Calls Recovery Metrics** (`GET /api/v1/missed-calls/queue/metrics`):
- `data.metrics.missed_calls` → "Missed Calls" stat card
- `data.metrics.saved_calls` → "Saved Calls" stat card
- `data.metrics.otto_rescues` → "Otto Rescues" stat card
- `data.metrics.success_rate` → Progress bar value and text

**Missed Calls Queue** (`GET /api/v1/missed-calls/queue/entries`):
- `data.items[]` → Kanban/list items
  - `customer_phone` → Lead phone number
  - `status` → Determine kanban column (booked/pending/dead)
  - `priority` → Urgency indicator
  - `sla_deadline` → Callback reminder time
  - `retry_count` → "Calls Attempted" count

**Alternative: Dashboard Calls** (`GET /api/v1/dashboard/calls?status=missed`):
- `data.calls[]` → Missed calls list
  - `phone_number` → Lead phone number
  - `missed_call` → Boolean flag
  - `booked` → Status (booked/pending/dead)
  - `contact_card_id` → Used to fetch contact details

**Contact Card Detail** (when lead clicked):
- See "Contact Card / Customer Detail" section below

### User Actions → API Calls

- **When CSR clicks missed call card**:
  - If `contact_card_id` exists: Call `GET /api/v1/contact-cards/{contact_card_id}`
  - Open `LeadDetailsDialog` with contact card data

- **When CSR switches view mode (Kanban/List)**:
  - Re-fetch `GET /api/v1/missed-calls/queue/entries` (no API change, just UI toggle)

- **When CSR changes sort order**:
  - Re-fetch with updated query params (if backend supports sorting)

- **When CSR clicks "Expand to see all"**:
  - Call `GET /api/v1/missed-calls/queue/entries?page_size=100` (increase limit)

### Edge Cases & Error Handling

- **404 on metrics**: Show zeros for all stats
- **403 (permission denied)**: Show "You don't have permission" message
- **500 or network error**: Show retry button, allow manual refresh
- **Empty missed calls**: Show "No missed calls" empty state
- **Missing contact_card_id**: Show phone number only, disable click action

---

## Screen: Contact Card / Customer Detail

**File(s)**: `src/components/LeadDetailsDialog.tsx`

### Purpose

Detailed view of a single contact/lead showing engagement metrics, message history, tasks, key signals, and timeline.

### Backend Endpoints Used

| Purpose / Action                         | Method | Endpoint                                      | When Called                  | Notes |
|------------------------------------------|--------|-----------------------------------------------|------------------------------|-------|
| Load contact card detail                 | GET    | `/api/v1/contact-cards/{contact_card_id}`     | On dialog open               | Full contact card with all sections |
| Load message thread                     | GET    | `/api/v1/message-threads/{contact_card_id}`   | On dialog open               | SMS/nurture messages |
| Load tasks for contact                  | GET    | `/api/v1/tasks?contact_card_id={id}`          | On dialog open               | Open tasks |
| Load key signals for contact            | GET    | `/api/v1/key-signals?contact_card_id={id}`    | On dialog open               | Unacknowledged signals |
| Send SMS message                        | POST   | `/api/v1/sms/send?call_id={call_id}&message={text}` | On "Send" button click       | Send new message (requires call_id) |
| Complete task                           | POST   | `/api/v1/tasks/{task_id}/complete`             | On "Complete" button click   | Mark task complete |
| Acknowledge key signal                  | POST   | `/api/v1/key-signals/{signal_id}/acknowledge` | On "Acknowledge" click       | Mark signal acknowledged |
| Update lead status                      | PATCH  | `/api/v1/leads/{lead_id}`                     | On status change             | Update lead status |

### Data Mapping (Backend → UI)

**Contact Card Detail** (`GET /api/v1/contact-cards/{contact_card_id}`):

**Top Section**:
- `data.lead_status` → Lead status badge (qualified_booked, qualified_unbooked, etc.)
- `data.lead_status_history[]` → Status change timeline
- `data.key_signals[]` → Insight cards
  - `signal_type` → Signal category
  - `title` → Signal title
  - `severity` → Severity indicator (low/medium/high/critical)
- `data.open_tasks[]` → Open tasks list
  - `description` → Task description
  - `due_at` → Due date/time
  - `status` → Task status

**Middle Section**:
- `data.sop_compliance[]` → SOP compliance stages
  - `stage_name` → Stage name
  - `followed` → Boolean (completed/missed)
  - `score` → Compliance score
- `data.objections[]` → Objections list
  - `category` → Objection category
  - `objection_text` → Objection text
  - `overcome` → Boolean (overcome/not overcome)
- `data.missed_opportunities[]` → Missed opportunities
- `data.pending_actions[]` → Pending actions
- `data.appointment_outcome` → Appointment outcome (if applicable)
- `data.ai_summary` → AI-generated summary
- `data.recording_sessions[]` → Recording sessions (for visits)

**Bottom Section**:
- `data.booking_timeline[]` → Timeline events
  - `type` → Event type (call, text, appointment, task)
  - `timestamp` → Event time
  - `description` → Event description
- `data.call_recordings[]` → Call recordings
  - `call_id` → Call ID
  - `transcript` → Call transcript
  - `recording_url` → Audio recording URL
- `data.text_threads[]` → Text message threads
- `data.nurture_threads[]` → Nurture automation threads

**Contact Info**:
- `data.first_name + last_name` → Lead name header
- `data.primary_phone` → Primary phone label
- `data.address` → Address (if available)
- `data.property_snapshot` → Property intelligence data
  - `est_value_range` → Property value chip
  - `roof_type` → Roof type
  - `square_feet` → Square footage

**Message Thread** (`GET /api/v1/message-threads/{contact_card_id}`):
- `data.messages[]` → Message list (chronological)
  - `sender` → Sender name/phone
  - `sender_role` → Sender role (csr, otto, customer)
  - `body` → Message text
  - `direction` → inbound/outbound
  - `created_at` → Message time (format: "6:50 PM")
  - `isOtto` → Derived from `sender_role === "otto"` or `sender_role === "ai"`

**Tasks** (`GET /api/v1/tasks?contact_card_id={id}`):
- `data.tasks[]` → Tasks list
  - `description` → Task description
  - `due_at` → Due date
  - `status` → Task status (open/completed/overdue)

**Key Signals** (`GET /api/v1/key-signals?contact_card_id={id}`):
- `data.signals[]` → Signals list
  - `title` → Signal title
  - `description` → Signal description
  - `severity` → Severity level
  - `acknowledged` → Acknowledged status

### User Actions → API Calls

- **When CSR clicks "Message" button**:
  - If SMS sending endpoint exists: Call `POST /api/v1/message-threads/{contact_card_id}` with message body
  - Otherwise: Open SMS compose UI (implementation depends on Twilio integration)

- **When CSR marks task complete**:
  - Call `POST /api/v1/tasks/{task_id}/complete`
  - Optimistically update UI (mark task as completed)
  - Refetch tasks list to get updated state

- **When CSR acknowledges key signal**:
  - Call `POST /api/v1/key-signals/{signal_id}/acknowledge`
  - Optimistically update UI (mark signal as acknowledged)

- **When CSR updates lead status**:
  - Call `PATCH /api/v1/leads/{lead_id}` with `{ "status": newStatus }`
  - Wait for server confirmation before updating UI

- **When CSR clicks "Previous" or "Next"**:
  - Navigate to previous/next lead in list (no API call, uses local state)

### Edge Cases & Error Handling

- **404 on contact card**: Show "Contact not found" message, close dialog
- **403 (permission denied)**: Show "You don't have permission" message
- **500 or network error**: Show retry button, allow manual refresh
- **Empty message thread**: Show "No messages yet" empty state
- **Empty tasks**: Show "No open tasks" message
- **Empty key signals**: Show "No signals" message
- **Missing property snapshot**: Hide property intelligence section

---

## Screen: Tasks View

**File(s)**: (Component may be embedded in other screens)

### Purpose

View and manage tasks assigned to CSR or related to specific leads/contacts.

### Backend Endpoints Used

| Purpose / Action                         | Method | Endpoint                                      | When Called                  | Notes |
|------------------------------------------|--------|-----------------------------------------------|------------------------------|-------|
| Load tasks                               | GET    | `/api/v1/tasks?contact_card_id={id}&status=open` | On screen open / refresh | Filter by contact, lead, or assignee |
| Create new task                          | POST   | `/api/v1/tasks`                               | On "Create Task" click      | Create task |
| Update task                              | PATCH  | `/api/v1/tasks/{task_id}`                     | On task edit                 | Update task fields |
| Complete task                            | POST   | `/api/v1/tasks/{task_id}/complete`             | On "Complete" button click   | Mark task complete |
| Delete task                              | DELETE | `/api/v1/tasks/{task_id}`                     | On "Delete" button click     | Remove task |

### Data Mapping (Backend → UI)

**Tasks List** (`GET /api/v1/tasks`):
- `data.tasks[]` → Tasks list
  - `description` → Task description text
  - `due_at` → Due date/time (format: "Due: Sep 25, 2:00 PM")
  - `status` → Task status badge (open/completed/overdue/cancelled)
  - `assigned_to` → Assignee badge (CSR, Rep, Manager, AI)
  - `priority` → Priority indicator (high/medium/low)
  - `contact_card_id` → Link to contact card
  - `lead_id` → Link to lead
- `data.overdue_count` → Overdue tasks count badge

### User Actions → API Calls

- **When CSR creates new task**:
  - Call `POST /api/v1/tasks` with:
    ```json
    {
      "description": "Task description",
      "assigned_to": "csr",
      "contact_card_id": "...",
      "lead_id": "...",
      "due_at": "2025-11-25T10:00:00Z",
      "priority": "high"
    }
    ```
  - Refetch tasks list after creation

- **When CSR marks task complete**:
  - Call `POST /api/v1/tasks/{task_id}/complete`
  - Optimistically update UI
  - Refetch tasks list

- **When CSR edits task**:
  - Call `PATCH /api/v1/tasks/{task_id}` with updated fields
  - Refetch tasks list

- **When CSR deletes task**:
  - Call `DELETE /api/v1/tasks/{task_id}`
  - Optimistically remove from UI
  - Refetch tasks list

- **When CSR filters tasks**:
  - Call `GET /api/v1/tasks?status=open&overdue=true` (with filters)
  - Update tasks list

### Edge Cases & Error Handling

- **404 on task**: Show "Task not found" message
- **403 (permission denied)**: Show "You don't have permission" message
- **409 (duplicate task)**: Show "Task already exists" message, refresh list
- **500 or network error**: Show retry button
- **Empty tasks list**: Show "No tasks" empty state
- **Overdue tasks**: Highlight in red, show overdue badge

---

## Screen: Message / SMS View

**File(s)**: (Component embedded in LeadDetailsDialog)

### Purpose

View SMS/nurture message threads for a contact and send new messages.

### Backend Endpoints Used

| Purpose / Action                         | Method | Endpoint                                      | When Called                  | Notes |
|------------------------------------------|--------|-----------------------------------------------|------------------------------|-------|
| Load message thread                      | GET    | `/api/v1/message-threads/{contact_card_id}`   | On dialog open / refresh     | Full message history |
| Send SMS message                         | POST   | `/api/v1/sms/send?call_id={call_id}&message={text}` | On "Send" button click       | Send new message (requires call_id) |

**Note**: SMS sending requires a `call_id` (not `contact_card_id`). See SMS Sending Flow below.

### Data Mapping (Backend → UI)

**Message Thread** (`GET /api/v1/message-threads/{contact_card_id}`):
- `data.messages[]` → Message list (chronological order)
  - `id` → Message ID
  - `sender` → Sender phone number or user ID
  - `sender_role` → Sender role (csr, otto, customer)
  - `body` → Message text
  - `direction` → inbound/outbound
  - `created_at` → Message timestamp (format: "6:50 PM")
  - `delivered` → Delivery status
  - `read` → Read status
- `data.total` → Total message count

**Message Display**:
- `sender_role === "otto" || sender_role === "ai"` → Show "Otto" badge, dark avatar
- `sender_role === "csr"` → Show CSR name, light avatar
- `direction === "inbound"` → Customer message
- `direction === "outbound"` → CSR/Otto message
- `body` → Message text content
- `created_at` → Time display (format: "6:50 PM")

**Key Message Highlights** (derived from messages):
- Extract key phrases from messages (may be provided by backend or computed frontend-side)
- Display as bullet list in "Key Message Highlights" section

### User Actions → API Calls

- **When CSR sends SMS message**:
  - Follow the SMS Sending Flow (see pseudocode below)
  - After send: Refetch message thread `GET /api/v1/message-threads/{contact_card_id}` to show new message

**SMS Sending Flow (Short-term Solution)**:

**Current Behavior**: The SMS sending endpoint requires a `call_id`, not a `contact_card_id`. This is a temporary pattern that will be simplified later with a helper endpoint.

**Frontend Implementation Steps**:

1. Fetch calls for the contact card to get the most recent call ID
2. Use that `call_id` to send the SMS
3. Refresh the message thread to show the new message

**Pseudocode**:

```typescript
// Step 1: Get contact card (if not already loaded)
const contactCard = await apiGet(`/api/v1/contact-cards/${contactCardId}`);

// Step 2: Find the most recent call for this contact
// Option A: Use call_recordings from contact card if available
let latestCallId: number | null = null;
if (contactCard.data.call_recordings && contactCard.data.call_recordings.length > 0) {
  // Sort by started_at descending, get the most recent
  const sortedCalls = contactCard.data.call_recordings.sort(
    (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
  );
  latestCallId = sortedCalls[0]?.call_id;
}

// Option B: If call_recordings not available, query calls endpoint
if (!latestCallId) {
  const companyId = getCompanyIdFromJWT(); // Extract from JWT
  const callsResponse = await apiGet(
    `/api/v1/dashboard/calls?status=all&company_id=${companyId}`
  );
  const contactCalls = callsResponse.calls.filter(
    (call) => call.contact_card_id === contactCardId
  );
  if (contactCalls.length > 0) {
    const sortedCalls = contactCalls.sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
    latestCallId = sortedCalls[0].call_id;
  }
}

// Step 3: Send SMS using the call_id
if (!latestCallId) {
  throw new Error('No call found for this contact. Cannot send SMS.');
}

await apiPost(
  `/api/v1/sms/send?call_id=${latestCallId}&message=${encodeURIComponent(messageText)}`
);

// Step 4: Refresh message thread to show new message
const updatedThread = await apiGet(`/api/v1/message-threads/${contactCardId}`);
```

**Future Improvement**: A simplified endpoint `POST /api/v1/contact-cards/{contact_card_id}/send-sms` may be added later that handles finding the call_id internally, eliminating the need for this multi-step frontend flow.

- **When CSR refreshes message thread**:
  - Call `GET /api/v1/message-threads/{contact_card_id}`
  - Update message list

### Edge Cases & Error Handling

- **404 on contact card**: Show "Contact not found" message
- **403 (permission denied)**: Show "You don't have permission" message
- **500 or network error**: Show retry button
- **Empty message thread**: Show "No messages yet" empty state
- **Message send failure**: Show error message, allow retry
- **Undelivered message**: Show delivery status indicator

---

## Screen: Lead Pool (if CSR has access)

**File(s)**: (May be embedded in other screens)

### Purpose

View and request leads from the shared lead pool (if CSR has access to this feature).

### Backend Endpoints Used

| Purpose / Action                         | Method | Endpoint                                      | When Called                  | Notes |
|------------------------------------------|--------|-----------------------------------------------|------------------------------|-------|
| Load lead pool                           | GET    | `/api/v1/lead-pool`                           | On screen open               | List of pool leads |
| Request lead from pool                   | POST   | `/api/v1/lead-pool/{lead_id}/request`          | On "Request" button click    | Request lead assignment |

### Data Mapping (Backend → UI)

**Lead Pool** (`GET /api/v1/lead-pool`):
- `data.leads[]` → Pool leads list
  - `contact_name` → Lead name
  - `primary_phone` → Phone number
  - `address` → Address
  - `lead_status` → Lead status
  - `signals[]` → Key signal titles
  - `last_activity` → Last activity timestamp
  - `requested_by_rep_ids[]` → List of rep IDs who requested (CSR may not see this)
- `data.in_pool_count` → Count of leads in pool
- `data.assigned_count` → Count of assigned leads

### User Actions → API Calls

- **When CSR requests a lead**:
  - Call `POST /api/v1/lead-pool/{lead_id}/request`
  - Show success message
  - Refetch lead pool to update status

**Note**: CSR may not have access to lead pool. Check RBAC permissions. If CSR cannot access, this screen should not be shown.

### Edge Cases & Error Handling

- **403 (permission denied)**: Hide lead pool screen entirely (CSR may not have access)
- **404 on lead**: Show "Lead not found" message
- **500 or network error**: Show retry button
- **Empty lead pool**: Show "No leads in pool" empty state

---

## 3. Special CSR Features

### 3.1 Dynamic Contact Card

**Endpoint**: `GET /api/v1/contact-cards/{contact_card_id}`

**Required Sections**:

**Top Section**:
- `data.lead_status` → Lead status badge
- `data.lead_status_history[]` → Status change history
- `data.key_signals[]` → Key signals (insights)
- `data.open_tasks[]` → Open tasks list

**Middle Section**:
- `data.sop_compliance[]` → SOP compliance stages
- `data.objections[]` → Objections raised
- `data.missed_opportunities[]` → Missed opportunities
- `data.pending_actions[]` → Pending actions
- `data.appointment_outcome` → Appointment outcome (if applicable)
- `data.ai_summary` → AI-generated summary
- `data.recording_sessions[]` → Recording sessions (for visits)

**Bottom Section**:
- `data.booking_timeline[]` → Timeline of events (calls, SMS, appointments, tasks)
- `data.call_recordings[]` → Call recordings with transcripts
- `data.text_threads[]` → SMS message threads
- `data.nurture_threads[]` → Nurture automation threads

**Property Intelligence**:
- `data.property_snapshot` → Property data (roof type, square feet, value, etc.)
- Display in middle section as property intelligence card

---

### 3.2 Missed Calls & Nurture

**Endpoints**:
- `GET /api/v1/dashboard/calls?status=missed&company_id={id}` - Missed calls list
- `GET /api/v1/missed-calls/queue/metrics` - Recovery metrics
- `GET /api/v1/missed-calls/queue/entries` - Missed calls queue

**Nurture Actions**:
- All nurture actions (follow-ups, SMS) should call Otto APIs, not Shunya directly
- Use `GET /api/v1/message-threads/{contact_card_id}` for message threads
- Use `POST /api/v1/sms/send?call_id={call_id}&message={text}` for sending SMS (see SMS Sending Flow in Message / SMS View section)

---

### 3.3 Tasks & Key Signals

**Tasks Endpoints**:
- `GET /api/v1/tasks?contact_card_id={id}&status=open` - List tasks
- `POST /api/v1/tasks` - Create task
- `PATCH /api/v1/tasks/{task_id}` - Update task
- `POST /api/v1/tasks/{task_id}/complete` - Complete task
- `DELETE /api/v1/tasks/{task_id}` - Delete task

**Key Signals Endpoints**:
- `GET /api/v1/key-signals?contact_card_id={id}` - List signals
- `POST /api/v1/key-signals/{signal_id}/acknowledge` - Acknowledge signal

---

### 3.4 SMS / Message Threads

**Read**:
- `GET /api/v1/message-threads/{contact_card_id}` → Load full conversation

**Send**:
  - `POST /api/v1/sms/send?call_id={call_id}&message={message}` → Send SMS message
  - **Note**: Requires `call_id`, not `contact_card_id`. See SMS Sending Flow pseudocode in "Screen: Message / SMS View" section above for implementation details.
  - This is a temporary frontend pattern; a simplified helper endpoint may be added later.

---

## 4. Backend Endpoint Reference

### 4.1 Contact Cards

- `GET /api/v1/contact-cards/{contact_id}` - Get contact card detail
- `GET /api/v1/contact-cards/by-phone?phone_number={phone}&company_id={id}` - Get by phone
- `POST /api/v1/contact-cards/{contact_id}/refresh-property` - Refresh property intelligence

### 4.2 Leads

- `GET /api/v1/leads/{lead_id}` - Get lead detail
- `GET /api/v1/leads?status={status}&source={source}&priority={priority}` - List leads
- `POST /api/v1/leads` - Create lead
- `PATCH /api/v1/leads/{lead_id}` - Update lead

### 4.3 Appointments

- `GET /api/v1/appointments/{appointment_id}` - Get appointment detail
- `GET /api/v1/appointments?rep_id={id}&date={date}&status={status}` - List appointments
- `POST /api/v1/appointments` - Create appointment
- `PATCH /api/v1/appointments/{appointment_id}` - Update appointment

### 4.4 Calls

- `GET /api/v1/calls/{call_id}` - Get call detail
- `GET /api/v1/dashboard/calls?status={status}&company_id={id}` - List calls (by status)

### 4.5 Tasks

- `GET /api/v1/tasks?contact_card_id={id}&lead_id={id}&status={status}&overdue={bool}` - List tasks
- `POST /api/v1/tasks` - Create task
- `PATCH /api/v1/tasks/{task_id}` - Update task
- `POST /api/v1/tasks/{task_id}/complete` - Complete task
- `DELETE /api/v1/tasks/{task_id}` - Delete task

### 4.6 Key Signals

- `GET /api/v1/key-signals?contact_card_id={id}&signal_type={type}&acknowledged={bool}` - List signals
- `POST /api/v1/key-signals/{signal_id}/acknowledge` - Acknowledge signal

### 4.7 Message Threads

- `GET /api/v1/message-threads/{contact_card_id}` - Get message thread
- `POST /api/v1/sms/send?call_id={call_id}&message={text}` - Send SMS message (requires call_id)

### 4.8 Lead Pool

- `GET /api/v1/lead-pool` - List pool leads
- `POST /api/v1/lead-pool/{lead_id}/request` - Request lead
- `POST /api/v1/lead-pool/{lead_id}/assign` - Assign lead (manager only)

### 4.9 Missed Calls Queue

- `GET /api/v1/missed-calls/queue/metrics` - Get recovery metrics
- `GET /api/v1/missed-calls/queue/entries` - Get queue entries
- `GET /api/v1/missed-calls/queue/status` - Get queue status

### 4.10 Dashboard Metrics

- `GET /api/v1/dashboard/metrics` - Get dashboard metrics
- `GET /api/v1/dashboard/booking-rate` - Get booking rate chart data
- `GET /api/v1/dashboard/top-objections` - Get top objections
- `GET /api/v1/dashboard/calls?status={status}&company_id={id}` - Get calls by status

### 4.11 RAG / Ask Otto

- `POST /api/v1/rag/query` - Ask Otto query

---

## 5. Response Schema Reference

All endpoints return responses wrapped in `APIResponse<T>`:

```typescript
interface APIResponse<T> {
  data: T;
  success?: boolean;
  message?: string;
}
```

**Error Response**:
```typescript
interface ErrorResponse {
  error_code: string;
  message: string;
  details?: any;
  request_id?: string;
}
```

**Common Status Codes**:
- `200 OK` - Success
- `400 Bad Request` - Invalid input
- `401 Unauthorized` - Missing/invalid JWT
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict (e.g., duplicate)
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

---

## 6. Open Questions / Ambiguities

### 6.1 SMS Sending

**Answer**: SMS sending uses `POST /api/v1/sms/send?call_id={call_id}&message={text}`, which requires a `call_id` parameter, not `contact_card_id`.

**Current State**: 
- `GET /api/v1/message-threads/{contact_card_id}` exists for reading messages
- `POST /api/v1/sms/send` exists in `app/routes/sms_handler.py` and requires `call_id` as query parameter

**Recommendation**: Frontend must find the most recent call for a contact card to get `call_id` before sending SMS. Alternatively, use `contact_card.call_recordings[]` from contact card detail to get a `call_id`.

---

### 6.2 Dashboard Metrics Endpoints

**Answer**: `GET /api/v1/dashboard/metrics` exists in `app/routes/backend.py`, but it returns a different structure than frontend expects.

**Current State**: 
- `GET /api/v1/dashboard/metrics?company_id={id}` exists but returns:
  - `still_deciding`, `awaiting_quote`, `purchased_service`, `missed_calls`, `cancelled_appointments`, `discrepancies`, `lost_quotes`, `still_deciding_count`
  - Frontend expects: `booking_rate`, `total_leads`, `qualified_leads`, `booked_appointments`

**Status**: 
- ✅ `GET /api/v1/dashboard/booking-rate` - **IMPLEMENTED** (returns time series booking rate data)
- ✅ `GET /api/v1/dashboard/top-objections` - **IMPLEMENTED** (returns objection labels + percentages)

Both endpoints are now available and return data scoped by company_id from JWT tenant context.

---

### 6.3 Ask Otto / RAG Endpoint

**Status**: ✅ **Implemented** - `POST /api/v1/rag/query` exists in `app/routes/rag.py`

**Current Implementation**:
- Backend uses `/api/v1/search/` endpoint (legacy) when calling Shunya
- No `X-Target-Role` header sent (defaults to `sales_rep` in Shunya)
- Payload shape: `{ query, document_types, limit, score_threshold, filters }`

**Target Implementation** (per Shunya contract):
- Backend will migrate to `/api/v1/ask-otto/query` endpoint
- Payload shape: `{ question, conversation_id?, context, scope? }`
- Header: `X-Target-Role: customer_rep` (or `csr`) for CSR queries
- Streaming support: `/api/v1/ask-otto/query-stream` (optional, not yet implemented)

**CSR Scoping**: Endpoint supports CSR role and scopes queries to CSR data (calls, leads, not rep appointments). Backend sets appropriate context when calling Shunya.

---

### 6.4 Lead Pool Access for CSR

**Question**: Do CSRs have access to lead pool, or is it manager/rep only?

**Current State**: `GET /api/v1/lead-pool` has `@require_role("manager", "sales_rep", "csr")`, so CSR has access.

**Recommendation**: CSR can view lead pool but may not be able to request leads (check `POST /api/v1/lead-pool/{lead_id}/request` permissions).

---

### 6.5 Archived Leads Endpoint

**Question**: What endpoint should be used for archived leads (closed_lost, closed_won)?

**Current State**: Frontend shows archived leads panel, but endpoint is unclear.

**Recommendation**: Use `GET /api/v1/leads?status=closed_lost,closed_won` or create dedicated archived leads endpoint.

---

### 6.6 Property Intelligence Refresh

**Question**: Does `POST /api/v1/contact-cards/{contact_id}/refresh-property` trigger property intelligence scraping?

**Current State**: Endpoint exists in `app/routes/contact_cards.py`.

**Recommendation**: Verify endpoint triggers property intelligence task and returns updated property snapshot.

---

## 7. Implementation Checklist

### Frontend Agency Checklist

- [ ] Set up API client with JWT authentication
- [ ] Implement tenant scoping (extract `company_id` from JWT)
- [ ] Implement error handling (403, 404, 409, 429, 500)
- [ ] Implement optimistic updates for safe mutations
- [ ] Implement double-submission prevention
- [ ] Implement loading states for all API calls
- [ ] Implement empty states for all lists
- [ ] Implement retry logic for failed requests
- [ ] Implement real-time refresh (polling or WebSocket)
- [ ] Test all endpoints with real backend
- [ ] Verify RBAC permissions (CSR role)
- [ ] Verify multi-tenancy isolation
- [ ] Test error scenarios (network failures, timeouts)

---

## 8. Testing Recommendations

### Manual Testing

1. **Authentication**: Verify JWT is included in all requests
2. **Tenant Isolation**: Verify CSR can only see their company's data
3. **RBAC**: Verify CSR cannot access manager-only endpoints
4. **Idempotency**: Test double-submission scenarios
5. **Error Handling**: Test all error codes (403, 404, 409, 429, 500)
6. **Empty States**: Test with no data (empty lists, no metrics)
7. **Real-time Updates**: Test auto-refresh mechanisms

### Integration Testing

1. **End-to-End Flows**:
   - Missed call → Contact card → Task creation → Task completion
   - Lead detail → Message thread → Send SMS → Refresh thread
   - Dashboard load → Metrics display → Chart rendering

2. **Error Scenarios**:
   - Network failure during API call
   - 403 permission denied
   - 404 resource not found
   - 409 conflict (duplicate task)

---

## 9. Summary

### Screens Discovered

1. **CSR Home / Dashboard** (`src/app/(receptionsit)/page.tsx`)
2. **Receptionist Dashboard / Performance View** (`src/app/(receptionsit)/receptionist/page.tsx`)
3. **Missed Calls Recovery** (`src/components/missed-calls-recovery.tsx`, `src/components/sections/MissedLeadsDashboard.tsx`)
4. **Lead Details Dialog** (`src/components/LeadDetailsDialog.tsx`)
5. **Top Objections** (`src/components/top-objections.tsx`)
6. **Archived Leads Panel** (`src/components/sections/ArchivedLeadsPanel.tsx`)

### Total Backend Endpoints Referenced

**Approximately 25+ endpoints** across:
- Contact Cards (3 endpoints)
- Leads (4 endpoints)
- Appointments (4 endpoints)
- Calls (2 endpoints)
- Tasks (5 endpoints)
- Key Signals (2 endpoints)
- Message Threads (2 endpoints)
- Lead Pool (3 endpoints)
- Missed Calls Queue (3 endpoints)
- Dashboard Metrics (4 endpoints)
- RAG / Ask Otto (1 endpoint)

### Notable Ambiguities / TODOs

1. **SMS Sending**: Verify if `POST /api/v1/message-threads/{contact_card_id}` exists for sending messages
2. **Dashboard Metrics**: Verify if `GET /api/v1/dashboard/metrics`, `GET /api/v1/dashboard/booking-rate`, and `GET /api/v1/dashboard/top-objections` exist
3. **Archived Leads**: Clarify endpoint for archived leads (closed_lost, closed_won)
4. **Property Intelligence Refresh**: Verify `POST /api/v1/contact-cards/{contact_id}/refresh-property` triggers scraping
5. **Lead Pool Request**: Verify if CSR can request leads from pool (may be rep-only)

---

**Last Updated**: 2025-01-20  
**Status**: ✅ **Ready for Frontend Implementation**

---

## 10. Shunya Integration & Enum Alignment

### 10.1 Shunya-Derived Fields (Nullable States)

**Call Analysis Fields** (from `CallAnalysis` model):
- `transcript` (from `CallTranscript.transcript_text`) - ⚠️ **May be `null`** if transcription in progress or failed
- `objections` (array) - ⚠️ **May be empty array** if analysis not complete
- `objection_details` (array) - ⚠️ **May be `null`** if objections not yet analyzed
- `sop_compliance_score` (number) - ⚠️ **May be `null`** if compliance check not run
- `sop_stages_completed` (array) - ⚠️ **May be empty** if analysis incomplete
- `sop_stages_missed` (array) - ⚠️ **May be empty** if analysis incomplete
- `sentiment_score` (number) - ⚠️ **May be `null`** if sentiment analysis not complete
- `lead_quality` (string) - ⚠️ **May be `null`** if qualification analysis not complete
- `qualification` (object) - ⚠️ **May be `null`** if qualification analysis not complete
  - `qualification_status` - ⚠️ **May be `null`**
  - `bant_scores` - ⚠️ **May be `null`**

**Frontend Handling**: Always check for `null`/empty values and show appropriate loading/empty states. Poll `GET /api/v1/calls/{call_id}/analysis` to check `status` field (`"complete" | "not_analyzed" | "processing"`).

### 10.2 Enum Alignment (Shunya Canonical Values)

**BookingStatus** (from Shunya `enums-inventory-by-service.md`):
- `booked` - Appointment scheduled ✅ **Implemented**
- `not_booked` - No appointment scheduled ✅ **Implemented**
- `service_not_offered` - Customer needs service we don't provide ⚠️ **May not be consistently surfaced in all endpoints yet**

**QualificationStatus**:
- `hot` - High urgency, ready to close ✅ **Implemented**
- `warm` - Showing interest but not urgent ✅ **Implemented**
- `cold` - Low interest, informational stage ✅ **Implemented**
- `unqualified` - Not a fit for our services ✅ **Implemented**

**ActionType** (Pending Actions):
- **Current State**: Free-form string in Otto
- **Target**: Will be migrated to Shunya's canonical 30-value enum (see `OTTO_BACKEND_SHUNYA_AUDIT.md` for full list)
- Common values: `call_back`, `send_quote`, `schedule_appointment`, `follow_up_call`, `send_estimate`, `send_contract`, `verify_insurance`, etc.

**CallType**:
- `csr_call` - CSR call ✅ **Used in code**
- `sales_call` - Sales rep call ✅ **Used in code**
- **Note**: Currently stored as free-form string; will be enforced as enum

**MeetingPhase** (for sales visits, not CSR):
- `rapport_agenda` - Part 1: Rapport building and agenda setting
- `proposal_close` - Part 2: Proposal presentation and closing
- **Note**: Not applicable to CSR calls; used for sales visit recordings

**MissedOpportunityType**:
- `discovery`, `cross_sell`, `upsell`, `qualification`
- **Note**: Currently not consistently modeled in Otto; will be aligned with Shunya canonical values

### 10.3 Ask Otto Payload & Headers

**Current Backend → Shunya Payload** (legacy):
```json
{
  "query": "What are the most common objections?",
  "document_types": null,
  "limit": 10,
  "score_threshold": 0,
  "filters": { "date_range": "last_30_days" }
}
```
- Endpoint: `POST /api/v1/search/` (legacy)
- No `X-Target-Role` header (defaults to `sales_rep` in Shunya)

**Target Backend → Shunya Payload** (per Shunya contract):
```json
{
  "question": "What are the most common objections?",
  "conversation_id": "optional_conversation_id",
  "context": { "tenant_id": "...", "user_role": "csr" },
  "scope": "csr_data_only"
}
```
- Endpoint: `POST /api/v1/ask-otto/query`
- Header: `X-Target-Role: customer_rep` (or `csr`)

**Frontend Impact**: No changes required - frontend continues to call `/api/v1/rag/query`; backend handles Shunya communication internally.



