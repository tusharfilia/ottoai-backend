# Executive Web App Integration Specification

**Date**: 2025-12-10  
**Status**: ✅ **Implementation-Ready**

---

## 📋 Document Purpose

This document provides a complete, production-grade integration specification for the Executive Next.js frontend to integrate with the Otto FastAPI backend. It defines exactly how Executive screens should communicate with backend APIs, including authentication, data mapping, user actions, and error handling.

**Target Audience**: Frontend development agency implementing Executive web app  
**Scope**: Executive dashboard only (not CSR webapp or Rep mobile app)

---

## 0. Global Integration Rules

### 0.1 Authentication & Tenant Scoping

**Every Executive frontend API call MUST:**

1. **Include JWT in Authorization header**:
   ```
   Authorization: Bearer <JWT>
   ```
   - JWT is supplied by the auth layer (Clerk or equivalent)
   - JWT contains `user_id`, `company_id`, and `role: "manager"` claims
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
const response = await fetch(`${API_BASE_URL}/api/v1/metrics/exec/company-overview`, {
  headers: {
    'Authorization': `Bearer ${jwtToken}`,
    'Content-Type': 'application/json',
  },
});
```

---

### 0.2 RBAC (Role-Based Access Control)

**Manager Role**:
- JWT contains `role: "manager"` claim
- Backend enforces role-based access via `@require_role("manager")` decorators
- Manager can see company-wide data (all CSRs, all sales reps)

**Manager Data Scoping**:
- ✅ **Can Access**:
  - Company-wide data (all CSRs, all sales reps)
  - Aggregated metrics across all teams
  - Individual agent/rep performance breakdowns
  - All executive dashboard endpoints
- ❌ **Cannot Access**:
  - CSR-specific self-scoped endpoints (use Exec endpoints instead)
  - Sales rep-specific self-scoped endpoints (use Exec endpoints instead)

**Ask Otto RBAC**:
- When manager uses Ask Otto, backend automatically sends `X-Target-Role: sales_manager` to Shunya
- Shunya scopes responses to company-wide data (all CSRs, all sales reps, all tasks)
- Context includes entire company for comprehensive insights

**403 Forbidden Handling**:
- If backend returns `403`, treat as "insufficient permissions"
- Show user-friendly message: "You don't have permission to perform this action"
- Never force through 403 errors in UI
- Log 403 errors for security monitoring

---

## 1. Executive Frontend Screens

The Executive dashboard consists of the following main screens:

### 1.1 Exec Home / Ask Otto
**Purpose**: Company-wide Q&A interface for executives to ask questions about company performance, teams, and metrics.

### 1.2 Company Overview Screen
**Purpose**: High-level company-wide metrics showing funnel, win/loss breakdown, attribution, and "who is dropping the ball".

### 1.3 Exec – CSR Tab
**Purpose**: Executive view of CSR team performance, including aggregated metrics, objections, unbooked appointments, and coaching opportunities.

### 1.4 Exec – Missed Calls / Auto AIQ
**Purpose**: Company-wide missed call recovery metrics and auto-queued leads ready for booking.

### 1.5 Exec – Sales Rep Tab
**Purpose**: Executive view of sales team performance, including ride-along appointments, opportunities, team stats, and objections.

---

## 2. Screen-by-Screen Integration Specs

---

## Screen: Exec Home / Ask Otto

**File(s)**: `src/app/(exec)/page.tsx` (HeroSection, FocusedPromptView)

### Purpose

Company-wide Q&A interface for executives. Manager can ask natural language questions about company performance, all CSRs, all sales reps, and all company tasks. Responses include entire company data.

### Data Source

**Endpoint**: `POST /api/v1/rag/query`

**Method**: POST

**Auth**: Requires manager role (JWT with `role: "manager"`)

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

- **Company-Wide Scope**: When called by a manager, backend automatically sends `X-Target-Role: sales_manager` to Shunya
- **Data Included**: Entire company (all CSRs, all sales reps, all tasks)
- **Context Passed**: Full company context for comprehensive insights
- **Shunya Fields**: All semantic analysis comes from Shunya. Otto never overrides Shunya's semantics.

### Example Request

```typescript
const response = await apiPost<RAGQueryResponse>('/api/v1/rag/query', {
  query: "What are the top objections across all CSRs and sales reps?",
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
    "query": "What are the top objections across all CSRs and sales reps?",
    "answer": "Across all teams, the top objections are: 'price too high' (35%), 'need to think about it' (22%), and 'not the right time' (18%)...",
    "citations": [
      {
        "doc_id": "call_456",
        "chunk_text": "Customer mentioned price concerns...",
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
- **403 Forbidden**: Show "You don't have permission" message (should not occur for manager role)
- **500 Internal Server Error**: Show generic error, allow retry

---

## Screen: Company Overview

**File(s)**: `src/app/(exec)/overview/page.tsx`

### Purpose

Display high-level company-wide metrics including funnel ratios, win/loss breakdown, attribution of where deals stall, and "who is dropping the ball" (worst CSR and worst sales rep).

### Data Source

**Endpoint**: `GET /api/v1/metrics/exec/company-overview`

**Method**: GET

**Auth**: Requires manager role only

**When Called**: On page load, and when date range changes

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date (defaults to 30 days ago)
- `date_to` (optional, ISO8601): End date (defaults to now)

### Response Schema

```typescript
interface ExecCompanyOverviewMetrics {
  // High-level funnel
  total_leads: number | null;
  qualified_leads: number | null;                  // From Shunya lead_quality
  total_appointments: number | null;
  total_closed_deals: number | null;                // From Shunya booking_status at sales outcome
  
  // Ratios
  lead_to_sale_ratio: number | null;                // closed_deals / total_leads
  close_rate: number | null;                        // closed_deals / qualified_leads
  sales_output_amount: number | null;               // Revenue (placeholder)
  
  // Win/loss breakdown
  win_rate: number | null;                         // Same as close_rate
  pending_rate: number | null;                     // pending / qualified
  lost_rate: number | null;                        // lost / qualified
  
  // Attribution
  win_loss_attribution: ExecCompanyWinLossAttribution | null;
  
  // Who is dropping the ball
  who_dropping_ball: ExecWhoDroppingBall | null;
}

interface ExecCompanyWinLossAttribution {
  pending_from_csr_initial_call: number | null;
  lost_from_csr_initial_call: number | null;
  pending_from_csr_followup: number | null;
  lost_from_csr_followup: number | null;
  pending_from_sales_followup: number | null;
  lost_from_sales_followup: number | null;
  pending_from_sales_appointment: number | null;
  lost_from_sales_appointment: number | null;
}

interface ExecWhoDroppingBall {
  worst_csr_id: string | null;
  worst_csr_name: string | null;
  worst_csr_booking_rate: number | null;
  worst_rep_id: string | null;
  worst_rep_name: string | null;
  worst_rep_win_rate: number | null;
}
```

### Fields Used by UI

**Funnel Metrics Cards**:
- **"Lead-to-Sale Ratio"** → `lead_to_sale_ratio` (format as percentage: `(lead_to_sale_ratio * 100).toFixed(1) + '%'`)
- **"Close Rate"** → `close_rate` (format as percentage)
- **"Sales Output"** → `sales_output_amount` (format as currency, show "N/A" if null)

**Win vs Lose Breakdown**:
- **"Win Rate"** → `win_rate` (format as percentage)
- **"Pending Rate"** → `pending_rate` (format as percentage)
- **"Lost Rate"** → `lost_rate` (format as percentage)

**Attribution Section** ("Where Deals Stall"):
- **"Lost at CSR Initial Call"** → `win_loss_attribution.lost_from_csr_initial_call` (format as percentage)
- **"Lost at CSR Follow-up"** → `win_loss_attribution.lost_from_csr_followup` (format as percentage)
- **"Lost at Sales Follow-up"** → `win_loss_attribution.lost_from_sales_followup` (format as percentage)
- **"Lost at Sales Appointment"** → `win_loss_attribution.lost_from_sales_appointment` (format as percentage)
- **"Pending at CSR Initial Call"** → `win_loss_attribution.pending_from_csr_initial_call` (format as percentage)
- **"Pending at CSR Follow-up"** → `win_loss_attribution.pending_from_csr_followup` (format as percentage)
- **"Pending at Sales Follow-up"** → `win_loss_attribution.pending_from_sales_followup` (format as percentage)
- **"Pending at Sales Appointment"** → `win_loss_attribution.pending_from_sales_appointment` (format as percentage)

**"Who is Dropping the Ball" Section**:
- **Worst CSR Card**:
  - Name → `who_dropping_ball.worst_csr_name` (show "Unknown" if null)
  - ID → `who_dropping_ball.worst_csr_id` (for navigation to CSR detail)
  - Booking Rate → `who_dropping_ball.worst_csr_booking_rate` (format as percentage)
- **Worst Sales Rep Card**:
  - Name → `who_dropping_ball.worst_rep_name` (show "Unknown" if null)
  - ID → `who_dropping_ball.worst_rep_id` (for navigation to rep detail)
  - Win Rate → `who_dropping_ball.worst_rep_win_rate` (format as percentage)

### Role Scoping Notes

- **Company-Wide**: All metrics aggregated across all CSRs and all sales reps
- **Shunya Source of Truth**: All booking/qualification/outcome fields come from Shunya

### Example Request

```typescript
const overview = await apiGet<ExecCompanyOverviewMetrics>(
  '/api/v1/metrics/exec/company-overview?date_from=2025-01-01&date_to=2025-01-31'
);
```

### Example Response

```json
{
  "success": true,
  "data": {
    "total_leads": 500,
    "qualified_leads": 400,
    "total_appointments": 300,
    "total_closed_deals": 240,
    "lead_to_sale_ratio": 0.48,
    "close_rate": 0.6,
    "sales_output_amount": null,
    "win_rate": 0.6,
    "pending_rate": 0.25,
    "lost_rate": 0.15,
    "win_loss_attribution": {
      "pending_from_csr_initial_call": 0.1,
      "lost_from_csr_initial_call": 0.05,
      "pending_from_csr_followup": 0.08,
      "lost_from_csr_followup": 0.04,
      "pending_from_sales_followup": 0.05,
      "lost_from_sales_followup": 0.03,
      "pending_from_sales_appointment": 0.02,
      "lost_from_sales_appointment": 0.03
    },
    "who_dropping_ball": {
      "worst_csr_id": "csr_123",
      "worst_csr_name": "John Doe",
      "worst_csr_booking_rate": 0.45,
      "worst_rep_id": "rep_456",
      "worst_rep_name": "Jane Smith",
      "worst_rep_win_rate": 0.35
    }
  }
}
```

### Edge Cases & Error Handling

- **Null rates**: Show "N/A" or "—" if any rate is null
- **Null `who_dropping_ball`**: Show "No data available" for worst performer cards
- **Empty attribution**: Show zeros for all attribution fields
- **403 Forbidden**: Should not occur for manager role, but show permission error if it does
- **500 Error**: Show retry button, allow manual refresh

---

## Screen: Exec – CSR Tab

**File(s)**: `src/app/(exec)/csr/page.tsx`

### Purpose

Executive view of CSR team performance, showing aggregated metrics across all CSRs, top objections, unbooked appointments list, and coaching opportunities per CSR.

### Data Source

**Endpoint**: `GET /api/v1/metrics/exec/csr/dashboard`

**Method**: GET

**Auth**: Requires manager role only

**When Called**: On page load, and when date range changes

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date (defaults to 30 days ago)
- `date_to` (optional, ISO8601): End date (defaults to now)

### Response Schema

```typescript
interface ExecCSRDashboardMetrics {
  overview: ExecCSRMetrics;                         // Company-wide CSR metrics
  booking_rate_trend: TimeSeriesPoint[] | null;     // Booking rate trend over time
  unbooked_calls_count: number | null;             // Total unbooked calls (CSR-wide)
  top_objections: ObjectionSummary[];               // Top objections across all CSRs
  coaching_opportunities: CSRAgentCoachingSummary[]; // Per-CSR coaching summaries
}

interface ExecCSRMetrics {
  total_calls: number;
  qualified_calls: number;
  qualified_rate: number | null;
  booked_calls: number;
  booking_rate: number | null;
  avg_objections_per_call: number | null;
  avg_compliance_score: number | null;              // 0-10 scale
  avg_sentiment_score: number | null;               // 0.0-1.0
  open_followups: number;
  overdue_followups: number;
}

interface TimeSeriesPoint {
  bucket_start: string;                             // ISO8601 datetime
  bucket_end: string;                               // ISO8601 datetime
  value: number | null;                             // Booking rate for this period
}

interface ObjectionSummary {
  objection_key: string;
  objection_label: string | null;
  occurrence_count: number;
  occurrence_rate: number | null;                    // 0.0-1.0
  occurrence_rate_over_qualified_unbooked: number | null;
}

interface CSRAgentCoachingSummary {
  csr_id: string;                                   // CSR user ID
  csr_name: string | null;
  total_calls: number;
  qualified_calls: number;
  booked_calls: number;
  booking_rate: number | null;
  sop_compliance_score: number | null;              // 0-10 scale
  top_objections: ObjectionSummary[];               // Top objections for this CSR
}
```

### Fields Used by UI

**Top Metrics Cards** (CSR-Level Aggregated):
- **"Booking Rate"** → `overview.booking_rate` (format as percentage)
- **"Total Leads"** → `overview.total_calls` (format with commas)
- **"Total Qualified"** → `overview.qualified_calls` (format with commas)
- **"Total Booked"** → `overview.booked_calls` (format with commas)

**Unbooked Appointments List**:
- **Count** → `unbooked_calls_count` (display as "X unbooked calls")
- **Note**: For detailed unbooked calls list, use CSR endpoint `GET /api/v1/calls/unbooked/self` aggregated across all CSRs (requires additional endpoint or aggregation logic)

**Objections Section**:
- **Top Objections List** → `top_objections` array
  - Objection Text → `objection_label` or `objection_key` (fallback)
  - Occurrence Count → `occurrence_count`
  - Occurrence Rate → `occurrence_rate` (format as percentage)
- **Drilldown**: When clicking an objection, use CSR objection drilldown endpoint with company-wide scope (may require additional endpoint or aggregation)

**Coaching Opportunities Section**:
- **List of CSRs** → `coaching_opportunities` array
  - **CSR Name** → `csr_name` (show "Unknown" if null)
  - **CSR ID** → `csr_id` (for navigation to CSR detail)
  - **Success Rate** → `booking_rate` (format as percentage)
  - **Total Calls** → `total_calls`
  - **Booking** → `booked_calls`
  - **SOP/Playbook Score** → `sop_compliance_score` (format as "X/10")
  - **Top Coaching Needs** → `top_objections` array (show top 3 objections)

**Click CSR → Show CSR Detail**:
- When clicking a CSR in coaching opportunities:
  - Navigate to CSR detail view
  - Show all objections for that CSR: `coaching_opportunities[].top_objections`
  - Show % of appointments unbooked due to each objection: `occurrence_rate_over_qualified_unbooked` (format as percentage)
  - Show recordings list (requires additional endpoint or use CSR-specific endpoints)

### Role Scoping Notes

- **Company-Wide**: All metrics aggregated across all CSRs
- **Shunya Source of Truth**: All booking/qualification fields come from Shunya

### Example Request

```typescript
const dashboard = await apiGet<ExecCSRDashboardMetrics>(
  '/api/v1/metrics/exec/csr/dashboard?date_from=2025-01-01&date_to=2025-01-31'
);
```

### Example Response

```json
{
  "success": true,
  "data": {
    "overview": {
      "total_calls": 1500,
      "qualified_calls": 1200,
      "qualified_rate": 0.8,
      "booked_calls": 900,
      "booking_rate": 0.75,
      "avg_objections_per_call": 1.2,
      "avg_compliance_score": 8.3,
      "avg_sentiment_score": 0.72,
      "open_followups": 150,
      "overdue_followups": 30
    },
    "booking_rate_trend": [
      {
        "bucket_start": "2025-01-01T00:00:00Z",
        "bucket_end": "2025-01-08T00:00:00Z",
        "value": 0.72
      }
    ],
    "unbooked_calls_count": 300,
    "top_objections": [
      {
        "objection_key": "price too high",
        "objection_label": "Price too high",
        "occurrence_count": 400,
        "occurrence_rate": 0.27,
        "occurrence_rate_over_qualified_unbooked": 0.35
      }
    ],
    "coaching_opportunities": [
      {
        "csr_id": "csr_123",
        "csr_name": "John Doe",
        "total_calls": 150,
        "qualified_calls": 120,
        "booked_calls": 80,
        "booking_rate": 0.67,
        "sop_compliance_score": 7.5,
        "top_objections": [
          {
            "objection_key": "price too high",
            "objection_label": "Price too high",
            "occurrence_count": 40,
            "occurrence_rate": 0.27,
            "occurrence_rate_over_qualified_unbooked": 0.35
          }
        ]
      }
    ]
  }
}
```

### Edge Cases & Error Handling

- **Null rates**: Show "N/A" or "—" if any rate is null
- **Empty `coaching_opportunities` array**: Show "No coaching opportunities" message
- **Empty `top_objections` array**: Show "No objections found" message
- **Null `booking_rate_trend`**: Show "No trend data available"

---

## Screen: Exec – Missed Calls / Auto AIQ

**File(s)**: `src/app/(exec)/missed-calls/page.tsx`

### Purpose

Display company-wide missed call recovery metrics and auto-queued leads ready for booking. Shows high-level metrics and three lists/columns (booked, pending, dead) for missed leads.

### Data Sources

**Metrics Endpoint**: `GET /api/v1/metrics/exec/missed-calls`

**Auto-Queued Leads Endpoint**: `GET /api/v1/metrics/csr/auto-queued-leads` (company-wide, visible to manager)

### High-Level Metrics

**Endpoint**: `GET /api/v1/metrics/exec/missed-calls`

**Method**: GET

**Auth**: Requires manager role only

**When Called**: On page load, and when date range changes

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date (defaults to 30 days ago)
- `date_to` (optional, ISO8601): End date (defaults to now)

**Response Schema**:

```typescript
interface ExecMissedCallRecoveryMetrics {
  total_missed_calls: number | null;
  total_saved_calls: number | null;                  // From Shunya booking_status
  total_saved_by_otto: number | null;               // Saved via Otto AI
  booked_leads_count: number | null;                 // From Shunya
  pending_leads_count: number | null;
  dead_leads_count: number | null;
}
```

**Fields Used by UI** (High-Level Metrics Cards):
- **"Total Missed Calls"** → `total_missed_calls`
- **"Total Saved Calls"** → `total_saved_calls`
- **"Total Saved by Otto"** → `total_saved_by_otto`
- **"Booked Leads"** → `booked_leads_count`
- **"Pending Leads"** → `pending_leads_count`
- **"Dead Leads"** → `dead_leads_count`

### Auto AI-Queued Leads

**Endpoint**: `GET /api/v1/metrics/csr/auto-queued-leads`

**Method**: GET

**Auth**: Requires manager or CSR role

**When Called**: On page load, and when date range changes

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date
- `date_to` (optional, ISO8601): End date

**Response Schema**:

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

**Fields Used by UI**:
- **List of Prospects** → `items` array
  - Customer Name → `customer_name` (show "Unknown" if null)
  - Phone → `phone` (format: `(XXX) XXX-XXXX`)
  - Status → `status` (display as badge: "Pending", "Scheduled", etc.)
  - Last Contacted → `last_contacted_at` (format: "Jan 15, 2:30 PM")
- **Click Lead** → Navigate to contact card using `lead_id`

### Missed Leads Lists (Booked/Pending/Dead)

**Note**: For viewing booked/pending/dead leads lists at company level, use the CSR auto-queued leads endpoint or aggregate CSR-specific missed leads endpoints. The exec missed-calls endpoint provides counts only.

**Alternative**: Use company-wide aggregation of CSR missed leads endpoints if available, or use the auto-queued leads endpoint which is company-wide.

### Role Scoping Notes

- **Company-Wide**: All metrics aggregated across all CSRs
- **Data Sources**:
  - **From Shunya**: `total_saved_calls`, `booked_leads_count` (derived from Shunya booking_status)
  - **From CallRail/Twilio**: `total_missed_calls` (call tracking), `total_saved_by_otto` (AI recovery tracking)

### Example Requests

```typescript
// Get high-level metrics
const metrics = await apiGet<ExecMissedCallRecoveryMetrics>(
  '/api/v1/metrics/exec/missed-calls?date_from=2025-01-01&date_to=2025-01-31'
);

// Get auto-queued leads
const leads = await apiGet<AutoQueuedLeadsResponse>(
  '/api/v1/metrics/csr/auto-queued-leads?date_from=2025-01-01'
);
```

### Example Responses

**Metrics**:
```json
{
  "success": true,
  "data": {
    "total_missed_calls": 200,
    "total_saved_calls": 150,
    "total_saved_by_otto": 100,
    "booked_leads_count": 120,
    "pending_leads_count": 30,
    "dead_leads_count": 50
  }
}
```

**Auto-Queued Leads**:
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

- **Null counts**: Show "0" or "—" if any count is null
- **Empty `items` array**: Show "No auto-queued leads available" empty state
- **403 Forbidden**: Should not occur for manager role

---

## Screen: Exec – Sales Rep Tab

**File(s)**: `src/app/(exec)/sales/page.tsx`

### Purpose

Executive view of sales team performance, including ride-along appointments for today, opportunities table, sales team stats, objections, and sales team overview KPIs.

### Data Sources

**Main Dashboard Endpoint**: `GET /api/v1/metrics/exec/sales/dashboard`

**Ride-Along Endpoint**: `GET /api/v1/metrics/exec/ride-along`

**Sales Opportunities Endpoint**: `GET /api/v1/metrics/sales/opportunities`

### Sales Team Dashboard

**Endpoint**: `GET /api/v1/metrics/exec/sales/dashboard`

**Method**: GET

**Auth**: Requires manager role only

**When Called**: On page load, and when date range changes

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date (defaults to 30 days ago)
- `date_to` (optional, ISO8601): End date (defaults to now)

**Response Schema**:

```typescript
interface ExecSalesTeamDashboardMetrics {
  overview: ExecSalesMetrics;                      // Company-wide sales metrics
  team_stats: SalesTeamStatsMetrics;               // Team statistics
  reps: SalesRepRecordingSummary[];                // Per-rep summaries
  top_objections: ObjectionSummary[];              // Top objections across all sales reps
}

interface ExecSalesMetrics {
  total_appointments: number;
  completed_appointments: number;
  won_appointments: number;
  lost_appointments: number;
  pending_appointments: number;
  team_win_rate: number | null;                    // won / completed
  avg_objections_per_appointment: number | null;
  avg_compliance_score: number | null;              // 0-10 scale
  avg_meeting_structure_score: number | null;      // 0.0-1.0
  avg_sentiment_score: number | null;              // 0.0-1.0
}

interface SalesTeamStatsMetrics {
  total_conversations: number | null;              // Total conversations/recordings
  avg_recording_duration_seconds: number | null;   // Average recording duration
  followup_rate: number | null;                    // Fraction of leads with >=1 followup
  followup_win_rate: number | null;               // Win rate for leads with followups
  first_touch_win_rate: number | null;             // Win rate for first appointment
  team_win_rate: number | null;                    // Overall team win rate
}

interface SalesRepRecordingSummary {
  rep_id: string;                                  // Sales rep user ID
  rep_name: string | null;
  total_recordings: number;
  total_recording_hours: number;
  win_rate: number | null;
  auto_usage_hours: number | null;                 // Placeholder
  sop_compliance_score: number | null;              // 0-10 scale
  sales_compliance_score: number | null;            // 0-10 scale
}

interface ObjectionSummary {
  objection_key: string;
  objection_label: string | null;
  occurrence_count: number;
  occurrence_rate: number | null;                   // 0.0-1.0
  occurrence_rate_over_qualified_unbooked: number | null;
}
```

**Fields Used by UI**:

**High-Level Overview Cards**:
- **"Total Appointments"** → `overview.total_appointments`
- **"Completed Appointments"** → `overview.completed_appointments`
- **"Won Appointments"** → `overview.won_appointments`
- **"Lost Appointments"** → `overview.lost_appointments`
- **"Pending Appointments"** → `overview.pending_appointments`
- **"Team Win Rate"** → `overview.team_win_rate` (format as percentage)
- **"Avg Objections per Appointment"** → `overview.avg_objections_per_appointment`
- **"Avg Compliance Score"** → `overview.avg_compliance_score` (format as "X/10")
- **"Avg Meeting Structure Score"** → `overview.avg_meeting_structure_score` (format as percentage)
- **"Avg Sentiment Score"** → `overview.avg_sentiment_score` (format as percentage)

**Sales Team Overview KPIs**:
- **"Total Conversations"** → `team_stats.total_conversations`
- **"Avg Recording Duration"** → `team_stats.avg_recording_duration_seconds` (format as "Xm Ys" or "X hours")
- **"Follow-up Rate %"** → `team_stats.followup_rate` (format as percentage)
- **"Follow-up Win Rate %"** → `team_stats.followup_win_rate` (format as percentage)
- **"First-Touch Win Rate"** → `team_stats.first_touch_win_rate` (format as percentage)
- **"Overall Team Win Rate"** → `team_stats.team_win_rate` (format as percentage)

**Team Stats List Per Rep**:
- **Rep List** → `reps` array
  - Rep Name → `rep_name` (show "Unknown" if null)
  - Rep ID → `rep_id` (for navigation to rep detail)
  - Total Appointments → `total_recordings` (note: this is recordings, not appointments)
  - Completed Appointments → Derived from recordings with outcomes
  - Won Appointments → Derived from recordings with "won" outcome
  - Win Rate → `win_rate` (format as percentage)
  - Avg Compliance Score → `sop_compliance_score` (format as "X/10")
  - Auto Usage Rate → `auto_usage_hours` (format as "X hours", show "N/A" if null)

**Top Objections Section**:
- **Top Objections List** → `top_objections` array
  - Objection Text → `objection_label` or `objection_key` (fallback)
  - Occurrence Count → `occurrence_count`
  - Occurrence Rate → `occurrence_rate` (format as percentage)
- **Drilldown**: When clicking an objection, use sales rep objection drilldown endpoint (may require additional endpoint or aggregation)

### Ride-Along List

**Endpoint**: `GET /api/v1/metrics/exec/ride-along`

**Method**: GET

**Auth**: Requires manager role only

**When Called**: On page load, and when date changes

**Query Parameters**:
- `date` (optional, ISO8601): Date to filter by (defaults to today)
- `page` (optional, default: 1): Page number (1-indexed)
- `page_size` (optional, default: 50): Page size (1-200)

**Response Schema**:

```typescript
interface RideAlongAppointmentsResponse {
  items: RideAlongAppointmentItem[];
  page: number;
  page_size: number;
  total: number;
}

interface RideAlongAppointmentItem {
  appointment_id: number;
  customer_name: string | null;
  scheduled_at: string;                            // ISO8601 timestamp
  rep_id: string | null;                           // Sales rep user ID
  rep_name: string | null;
  status: "won" | "in_progress" | "not_started" | "rejected"; // From Shunya + appointment state
  outcome: "won" | "lost" | "pending" | null;      // From Shunya RecordingAnalysis
  sop_compliance_scores: Record<string, number>;    // SOP compliance scores by phase
  booking_path: string[];                          // e.g., ['inbound_call_csr', 'csr_followup_call', 'appointment_booked']
}
```

**Fields Used by UI** (Ride-Along Table):
- **Customer Name** → `customer_name` (show "Unknown" if null)
- **Scheduled At** → `scheduled_at` (format: "Jan 15, 10:00 AM")
- **Rep Name** → `rep_name` (show "Unassigned" if null)
- **Status** → `status` (display as badge: "Won", "In Progress", "Not Started", "Rejected")
- **Outcome** → `outcome` (display as badge, show "—" if null)
- **SOP Compliance Scores** → `sop_compliance_scores` (display as "Opening: 9.0, Discovery: 8.5, ..." or as a scorecard)
- **Booking Path** → `booking_path` (display as breadcrumb: "Inbound Call CSR → CSR Follow-up → Appointment Booked")

### Sales Opportunities Table

**Endpoint**: `GET /api/v1/metrics/sales/opportunities`

**Method**: GET

**Auth**: Requires manager role only

**When Called**: On page load

**Query Parameters**: None

**Response Schema**:

```typescript
interface SalesOpportunitiesResponse {
  items: SalesOpportunityItem[];
}

interface SalesOpportunityItem {
  rep_id: string;                                   // Sales rep user ID
  rep_name: string | null;
  pending_leads_count: number;                      // From Shunya + Task
  tasks: string[];                                  // Short task descriptions
}
```

**Fields Used by UI** (Opportunities Table):
- **Rep Name** → `rep_name` (show "Unknown" if null)
- **Rep ID** → `rep_id` (for navigation to rep detail)
- **Pending Leads** → `pending_leads_count`
- **Tasks Summary** → `tasks` array (display as comma-separated list or bullet list)

### Role Scoping Notes

- **Company-Wide**: All metrics aggregated across all sales reps
- **Shunya Source of Truth**: All outcomes, compliance scores, and objections come from Shunya

### Example Requests

```typescript
// Get sales team dashboard
const dashboard = await apiGet<ExecSalesTeamDashboardMetrics>(
  '/api/v1/metrics/exec/sales/dashboard?date_from=2025-01-01&date_to=2025-01-31'
);

// Get ride-along appointments for today
const appointments = await apiGet<RideAlongAppointmentsResponse>(
  '/api/v1/metrics/exec/ride-along?date=2025-01-15&page=1&page_size=50'
);

// Get sales opportunities
const opportunities = await apiGet<SalesOpportunitiesResponse>(
  '/api/v1/metrics/sales/opportunities'
);
```

### Example Responses

**Sales Team Dashboard**:
```json
{
  "success": true,
  "data": {
    "overview": {
      "total_appointments": 300,
      "completed_appointments": 270,
      "won_appointments": 180,
      "lost_appointments": 70,
      "pending_appointments": 30,
      "team_win_rate": 0.667,
      "avg_objections_per_appointment": 1.3,
      "avg_compliance_score": 8.2,
      "avg_meeting_structure_score": 0.82,
      "avg_sentiment_score": 0.73
    },
    "team_stats": {
      "total_conversations": 270,
      "avg_recording_duration_seconds": 1800,
      "followup_rate": 0.65,
      "followup_win_rate": 0.72,
      "first_touch_win_rate": 0.60,
      "team_win_rate": 0.667
    },
    "reps": [
      {
        "rep_id": "rep_123",
        "rep_name": "John Doe",
        "total_recordings": 50,
        "total_recording_hours": 25.0,
        "win_rate": 0.70,
        "auto_usage_hours": null,
        "sop_compliance_score": 8.5,
        "sales_compliance_score": 8.3
      }
    ],
    "top_objections": [
      {
        "objection_key": "price too high",
        "objection_label": "Price too high",
        "occurrence_count": 100,
        "occurrence_rate": 0.37,
        "occurrence_rate_over_qualified_unbooked": null
      }
    ]
  }
}
```

**Ride-Along Appointments**:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "appointment_id": 123,
        "customer_name": "John Doe",
        "scheduled_at": "2025-01-15T10:00:00Z",
        "rep_id": "rep_456",
        "rep_name": "Jane Smith",
        "status": "won",
        "outcome": "won",
        "sop_compliance_scores": {
          "opening": 9.0,
          "discovery": 8.5,
          "presentation": 9.2,
          "closing": 8.8
        },
        "booking_path": [
          "inbound_call_csr",
          "csr_followup_call",
          "appointment_booked"
        ]
      }
    ],
    "page": 1,
    "page_size": 50,
    "total": 25
  }
}
```

**Sales Opportunities**:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "rep_id": "rep_123",
        "rep_name": "John Doe",
        "pending_leads_count": 15,
        "tasks": [
          "Follow up with lead_456",
          "Send quote to lead_789"
        ]
      }
    ]
  }
}
```

### Edge Cases & Error Handling

- **Null rates**: Show "N/A" or "—" if any rate is null
- **Empty `reps` array**: Show "No sales reps found" message
- **Empty `top_objections` array**: Show "No objections found" message
- **Empty `items` array (ride-along)**: Show "No appointments scheduled for this date" message
- **Null `sop_compliance_scores`**: Show "No compliance data" or empty scorecard
- **Pagination**: Show page controls if `total > page_size`

---

## 3. Shunya Integration Notes

### Source of Truth

**All semantic analysis comes from Shunya**. Otto backend never overrides or infers Shunya's semantics. This includes:
- Booking status (`booking_status` from `CallAnalysis`)
- Qualification status (`lead_quality` from `CallAnalysis`)
- Objections (`objections` array from `CallAnalysis`)
- Compliance scores (`sop_compliance_score` from `CallAnalysis`)
- Sentiment scores (`sentiment_score` from `CallAnalysis`)
- Meeting structure scores (derived from `meeting_segments`)
- Sales outcomes (`outcome` from `RecordingAnalysis`)

**Important**: Otto never infers booking from the `Appointment` table. All booking metrics are derived exclusively from Shunya's `CallAnalysis.booking_status` field.

### Shunya-Derived Fields (May Be Null)

When calling endpoints that return Shunya analysis data, the following fields may be `null` or empty if Shunya hasn't finished processing:
- `sop_compliance_scores` - May be empty dict if compliance check not run
- `sentiment_score` - May be `null` if analysis not complete
- `outcome` - May be `null` if recording analysis not complete
- `booking_status` - May be `null` if booking analysis not complete

**Frontend Handling**: Always check for `null` values and empty arrays. Show appropriate loading/empty states when Shunya processing is incomplete.

---

## 4. Error Handling

### Common Status Codes

- **200 OK** - Success
- **400 Bad Request** - Invalid input (check request body/params)
- **401 Unauthorized** - Missing/invalid JWT (re-authenticate)
- **403 Forbidden** - Insufficient permissions (check user role - must be `manager`)
- **404 Not Found** - Resource doesn't exist or belongs to another company
- **500 Internal Server Error** - Server error (retry or report)

### Example Error Handling

```typescript
try {
  const result = await apiGet('/api/v1/metrics/exec/company-overview');
} catch (error) {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 401:
        // Redirect to login or refresh token
        redirectToLogin();
        break;
      case 403:
        // Show permission denied message
        showError('You don\'t have permission to access this resource. Manager role required.');
        break;
      case 404:
        // Show not found message
        showError('Resource not found');
        break;
      case 500:
        // Server error - show retry option
        showError('Server error. Please try again.');
        break;
      default:
        showError('An unexpected error occurred');
    }
  }
}
```

---

**For quick reference, see [EXEC_API_QUICKSTART.md](./EXEC_API_QUICKSTART.md)**

