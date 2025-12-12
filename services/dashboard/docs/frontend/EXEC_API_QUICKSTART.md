# Executive API Quickstart

**Date**: 2025-12-10  
**Status**: ✅ **Ready for Frontend Development**

---

## 📋 Purpose

This is a short, practical guide to get the Executive frontend team started calling Otto backend APIs within minutes. For full endpoint-by-endpoint details, see [EXEC_APP_INTEGRATION.md](./EXEC_APP_INTEGRATION.md).

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

The Executive Next.js app uses Clerk for authentication. The JWT token from Clerk must be included in all API requests.

**RBAC (Role-Based Access Control)**:
- **Manager/Exec Role**: JWT contains `role: "manager"` claim
- **Data Scoping**: Manager can see:
  - Company-wide data (all CSRs, all sales reps)
  - Aggregated metrics across all teams
  - Individual agent/rep performance breakdowns
- **Cannot Access**: CSR-specific self-scoped endpoints (use Exec endpoints instead)

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
    throw new ApiError('Authentication required', 401);
  }
  
  // Build URL with query params
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
    const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
    throw new ApiError(
      errorData.message || `Request failed: ${response.status}`,
      response.status,
      errorData.error_code
    );
  }
  
  const json = await response.json();
  // Handle APIResponse wrapper
  return json.data !== undefined ? json.data : json;
}

/**
 * Make an authenticated POST request
 */
export async function apiPost<T>(
  path: string,
  body?: any
): Promise<T> {
  const token = await getAuthToken();
  
  if (!token) {
    throw new ApiError('Authentication required', 401);
  }
  
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
    throw new ApiError(
      errorData.message || `Request failed: ${response.status}`,
      response.status,
      errorData.error_code
    );
  }
  
  const json = await response.json();
  return json.data !== undefined ? json.data : json;
}
```

---

## 4. Response Format

All endpoints return responses wrapped in `APIResponse<T>`:

```typescript
interface APIResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}
```

**Example Response**:

```json
{
  "success": true,
  "data": {
    "total_leads": 500,
    "qualified_leads": 400,
    "lead_to_sale_ratio": 0.6
  }
}
```

**Extract Data**:

```typescript
const response = await apiGet('/api/v1/metrics/exec/company-overview');
// response is already the unwrapped data (T), not the full APIResponse
console.log(response.total_leads); // 500
```

---

## 5. Executive Dashboard Endpoints

This section covers all endpoints required for the Executive dashboard. All endpoints are company-wide and require manager role.

---

## A. Ask Otto (Exec Scope)

### POST `/api/v1/rag/query`

**Roles**: `manager`, `csr`, `sales_rep`

**Description**: Natural language Q&A over company data. When called by a manager/exec, responses include entire company data (CSRs + sales reps + tasks).

**Request Body**:

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
  query: "What are the top objections across all CSRs and sales reps?",
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

**Important Notes**:
- **Target Role**: When called by a manager, backend automatically sends `X-Target-Role: sales_manager` to Shunya
- **Company-Wide Scope**: Includes all CSRs, all sales reps, and all company tasks
- **Shunya Fields**: All semantic analysis comes from Shunya. Otto never overrides Shunya's semantics.

---

## B. Company Overview

### GET `/api/v1/metrics/exec/company-overview`

**Roles**: `manager` only

**Description**: Get company-wide overview metrics including funnel ratios, win/loss breakdown, attribution, and "who is dropping the ball".

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date (defaults to 30 days ago)
- `date_to` (optional, ISO8601): End date (defaults to now)

**Response Schema**:

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
  pending_from_csr_initial_call: number | null;    // Fraction of qualified leads pending at CSR initial call
  lost_from_csr_initial_call: number | null;        // Fraction of qualified leads lost at CSR initial call
  pending_from_csr_followup: number | null;         // Fraction of qualified leads pending at CSR follow-up
  lost_from_csr_followup: number | null;            // Fraction of qualified leads lost at CSR follow-up
  pending_from_sales_followup: number | null;       // Fraction of qualified leads pending at sales follow-up
  lost_from_sales_followup: number | null;          // Fraction of qualified leads lost at sales follow-up
  pending_from_sales_appointment: number | null;    // Fraction of qualified leads pending at sales appointment
  lost_from_sales_appointment: number | null;       // Fraction of qualified leads lost at sales appointment
}

interface ExecWhoDroppingBall {
  worst_csr_id: string | null;                      // CSR with lowest booking rate
  worst_csr_name: string | null;
  worst_csr_booking_rate: number | null;
  
  worst_rep_id: string | null;                      // Sales rep with lowest win rate
  worst_rep_name: string | null;
  worst_rep_win_rate: number | null;
}
```

**Example Request**:

```typescript
const overview = await apiGet<ExecCompanyOverviewMetrics>(
  '/api/v1/metrics/exec/company-overview?date_from=2025-01-01&date_to=2025-01-31'
);
```

**Example Response**:

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

---

## C. Exec CSR Dashboard

### GET `/api/v1/metrics/exec/csr/dashboard`

**Roles**: `manager` only

**Description**: Get executive CSR dashboard metrics including company-wide CSR overview, booking trend, objections, and coaching opportunities per CSR.

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date (defaults to 30 days ago)
- `date_to` (optional, ISO8601): End date (defaults to now)

**Response Schema**:

```typescript
interface ExecCSRDashboardMetrics {
  overview: ExecCSRMetrics;                         // Company-wide CSR metrics
  booking_rate_trend: TimeSeriesPoint[] | null;     // Booking rate trend over time
  unbooked_calls_count: number | null;              // Total unbooked calls (CSR-wide)
  top_objections: ObjectionSummary[];               // Top objections across all CSRs
  coaching_opportunities: CSRAgentCoachingSummary[]; // Per-CSR coaching summaries
}

interface ExecCSRMetrics {
  total_calls: number;
  qualified_calls: number;
  qualified_rate: number | null;                   // qualified_calls / total_calls
  booked_calls: number;
  booking_rate: number | null;                      // booked_calls / qualified_calls
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
  objection_key: string;                            // Canonical objection key
  objection_label: string | null;                   // Display label
  occurrence_count: number;
  occurrence_rate: number | null;                   // 0.0-1.0
  occurrence_rate_over_qualified_unbooked: number | null; // Rate over qualified but unbooked calls
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

**Example Request**:

```typescript
const dashboard = await apiGet<ExecCSRDashboardMetrics>(
  '/api/v1/metrics/exec/csr/dashboard?date_from=2025-01-01&date_to=2025-01-31'
);
```

**Example Response**:

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

---

## D. Exec Missed Calls Recovery

### GET `/api/v1/metrics/exec/missed-calls`

**Roles**: `manager` only

**Description**: Get company-wide missed call recovery metrics.

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date (defaults to 30 days ago)
- `date_to` (optional, ISO8601): End date (defaults to now)

**Response Schema**:

```typescript
interface ExecMissedCallRecoveryMetrics {
  total_missed_calls: number | null;
  total_saved_calls: number | null;                  // From Shunya booking_status
  total_saved_by_otto: number | null;               // Saved via Otto AI
  booked_leads_count: number | null;                // From Shunya
  pending_leads_count: number | null;
  dead_leads_count: number | null;
}
```

**Example Request**:

```typescript
const metrics = await apiGet<ExecMissedCallRecoveryMetrics>(
  '/api/v1/metrics/exec/missed-calls?date_from=2025-01-01&date_to=2025-01-31'
);
```

**Example Response**:

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

**Data Source Notes**:
- **From Shunya**: `total_saved_calls`, `booked_leads_count` (derived from Shunya booking_status)
- **From CallRail/Twilio**: `total_missed_calls` (call tracking), `total_saved_by_otto` (AI recovery tracking)

**Note**: For viewing booked/pending/dead leads lists at company level, use the CSR auto-queued leads endpoint (`GET /api/v1/metrics/csr/auto-queued-leads`) which is company-wide and visible to managers.

---

## E. Exec Sales Team Dashboard

### GET `/api/v1/metrics/exec/sales/dashboard`

**Roles**: `manager` only

**Description**: Get executive sales team dashboard metrics including overview, team stats, per-rep summaries, and top objections.

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
  total_conversations: number | null;               // Total conversations/recordings
  avg_recording_duration_seconds: number | null;  // Average recording duration
  followup_rate: number | null;                    // Fraction of leads with >=1 followup
  followup_win_rate: number | null;                // Win rate for leads with followups
  first_touch_win_rate: number | null;             // Win rate for first appointment
  team_win_rate: number | null;                    // Overall team win rate
}

interface SalesRepRecordingSummary {
  rep_id: string;                                  // Sales rep user ID
  rep_name: string | null;
  total_recordings: number;
  total_recording_hours: number;
  win_rate: number | null;
  auto_usage_hours: number | null;                  // Placeholder
  sop_compliance_score: number | null;              // 0-10 scale
  sales_compliance_score: number | null;            // 0-10 scale
}
```

**Example Request**:

```typescript
const dashboard = await apiGet<ExecSalesTeamDashboardMetrics>(
  '/api/v1/metrics/exec/sales/dashboard?date_from=2025-01-01&date_to=2025-01-31'
);
```

**Example Response**:

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

---

## F. Ride-Along List

### GET `/api/v1/metrics/exec/ride-along`

**Roles**: `manager` only

**Description**: Get paginated list of ride-along appointments for executive view. Shows appointments with Shunya-driven outcomes and compliance scores.

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

**Example Request**:

```typescript
const appointments = await apiGet<RideAlongAppointmentsResponse>(
  '/api/v1/metrics/exec/ride-along?date=2025-01-15&page=1&page_size=50'
);
```

**Example Response**:

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

**Important Notes**:
- **Status/Outcome**: Derived from Shunya `RecordingAnalysis.outcome` + Otto local appointment state
- **SOP Compliance Scores**: Per-phase scores from Shunya compliance analysis

---

## G. Sales Opportunities / Pending Leads By Rep

### GET `/api/v1/metrics/sales/opportunities`

**Roles**: `manager` only

**Description**: Get sales opportunities per rep, showing pending leads and tasks summary for each sales rep.

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

**Example Request**:

```typescript
const opportunities = await apiGet<SalesOpportunitiesResponse>(
  '/api/v1/metrics/sales/opportunities'
);
```

**Example Response**:

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

**Important Notes**:
- **Data Source**: Uses Task + Shunya booking/outcome to identify pending leads per rep
- **Tasks**: Short descriptions of open tasks for each rep

---

## 6. RBAC & Scoping (Executive)

### Manager Role Scoping Rules

**Manager can see**:
- ✅ Company-wide data (all CSRs, all sales reps)
- ✅ Aggregated metrics across all teams
- ✅ Individual agent/rep performance breakdowns
- ✅ All executive dashboard endpoints

**Manager cannot see**:
- ❌ CSR-specific self-scoped endpoints (use Exec endpoints instead)
- ❌ Sales rep-specific self-scoped endpoints (use Exec endpoints instead)

### Ask Otto Scoping

When a manager calls Ask Otto:
- Backend automatically sends `X-Target-Role: sales_manager` to Shunya
- Context includes entire company: all CSRs, all sales reps, all tasks
- Full company-wide scope for comprehensive insights

### Endpoint Access

All executive endpoints require `@require_role("manager")`:
- Returns `403 Forbidden` if user role is not `manager`
- JWT must contain `role: "manager"` claim

---

## 7. Shunya Integration Notes

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

## 8. Quick Reference

| Item | Value |
|------|-------|
| **Base URL** | `process.env.NEXT_PUBLIC_API_BASE_URL` or Railway URL |
| **Auth Header** | `Authorization: Bearer <JWT_FROM_CLERK>` |
| **Content-Type** | `application/json` |
| **Response Format** | `{ success: boolean, data: T }` |
| **Error Format** | `{ error_code: string, message: string }` |
| **Required Role** | `manager` for all exec endpoints |

---

**For full endpoint-by-endpoint details, see [EXEC_APP_INTEGRATION.md](./EXEC_APP_INTEGRATION.md)**



