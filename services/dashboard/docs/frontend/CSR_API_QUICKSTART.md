# CSR API Quickstart

**Date**: 2025-12-10  
**Status**: ✅ **Ready for Frontend Development**

---

## 📋 Purpose

This is a short, practical guide to get the CSR frontend team started calling Otto backend APIs within minutes. For full endpoint-by-endpoint details, see [CSR_APP_INTEGRATION.md](./CSR_APP_INTEGRATION.md).

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

The CSR Next.js app uses Clerk for authentication. The JWT token from Clerk must be included in all API requests.

**RBAC (Role-Based Access Control)**:
- **CSR Role**: JWT contains `role: "csr"` claim
- **Data Scoping**: CSR can only see:
  - Own calls and leads (filtered by `csr_id` when available)
  - Company-wide missed calls (for recovery)
  - Company-wide leads (for booking)
- **Cannot Access**: Other CSRs' personal data, Sales Rep appointments, Manager-only endpoints
- **Ask Otto Context**: When CSR uses Ask Otto, backend forwards `X-Target-Role: customer_rep` (or `csr`) to Shunya to scope responses to CSR data

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

// Similar for PATCH, PUT, DELETE...
```

---

## 4. Quick Example: Fetch Contact Card

```typescript
import { apiGet } from '@/lib/api/client';

async function loadContactCard(contactCardId: string) {
  try {
    const contactCard = await apiGet<ContactCardDetail>(
      `/api/v1/contact-cards/${contactCardId}`
    );
    
    console.log('Contact name:', contactCard.first_name, contactCard.last_name);
    console.log('Lead status:', contactCard.lead_status);
    console.log('Open tasks:', contactCard.open_tasks);
    
    return contactCard;
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 404) {
        console.error('Contact card not found');
      } else if (error.status === 403) {
        console.error('Permission denied');
      } else {
        console.error('API error:', error.message);
      }
    } else {
      console.error('Network error:', error);
    }
    throw error;
  }
}
```

---

## 5. Error Handling

### Common Status Codes

- **200 OK** - Success
- **400 Bad Request** - Invalid input (check request body/params)
- **401 Unauthorized** - Missing/invalid JWT (re-authenticate)
- **403 Forbidden** - Insufficient permissions (check user role)
- **404 Not Found** - Resource doesn't exist or belongs to another company
- **409 Conflict** - Resource conflict (e.g., duplicate task)
- **429 Too Many Requests** - Rate limit exceeded (implement exponential backoff)
- **500 Internal Server Error** - Server error (retry or report)

### Example Error Handling

```typescript
try {
  const result = await apiGet('/api/v1/contact-cards/123');
} catch (error) {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 401:
        // Redirect to login or refresh token
        redirectToLogin();
        break;
      case 403:
        // Show permission denied message
        showError('You don\'t have permission to access this resource');
        break;
      case 404:
        // Show not found message
        showError('Resource not found');
        break;
      case 409:
        // Handle conflict (e.g., duplicate)
        showError('This action conflicts with existing data');
        break;
      case 429:
        // Rate limited - retry after delay
        await delay(1000);
        // Retry logic...
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

## 6. Response Format

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
    "id": "contact_123",
    "first_name": "John",
    "last_name": "Doe",
    "primary_phone": "+12025551234"
  }
}
```

**Extract Data**:

```typescript
const response = await apiGet('/api/v1/contact-cards/123');
// response is already the unwrapped data (T), not the full APIResponse
console.log(response.id); // "contact_123"
console.log(response.first_name); // "John"
```

---

## 7. CSR Dashboard Endpoints

This section covers all endpoints required for the CSR dashboard. All endpoints are scoped to the authenticated CSR user (except auto-queued leads which are company-wide).

---

## A. Ask Otto (CSR-Scoped)

### POST `/api/v1/rag/query`

**Roles**: `csr`, `manager`, `sales_rep`

**Description**: Natural language Q&A over company data. When called by a CSR, responses are automatically scoped to that CSR's calls, leads, and tasks only.

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
  query: "What are my top objections this month?",
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

**Important Notes**:
- **Target Role**: When called by a CSR, backend automatically sends `X-Target-Role: customer_rep` to Shunya
- **Scoping**: Only includes that CSR's calls/leads/tasks, not company-wide data
- **Shunya Fields**: All semantic analysis (objections, qualification, booking) comes from Shunya. Otto never overrides Shunya's semantics.
- **Nullable Fields**: If Shunya is still processing, `citations` may be empty and `confidence_score` may be 0.0

---

## B. CSR Overview + Booking Trend

### GET `/api/v1/metrics/csr/overview/self`

**Roles**: `csr` only

**Description**: Get comprehensive CSR overview metrics for the authenticated CSR user.

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date (defaults to 30 days ago)
- `date_to` (optional, ISO8601): End date (defaults to now)

**Response**:

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

**Example Request**:

```typescript
const overview = await apiGet<CSROverviewSelfResponse>(
  '/api/v1/metrics/csr/overview/self?date_from=2025-01-01&date_to=2025-01-31'
);
```

**Example Response**:

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

**Important Notes**:
- All booking/qualification fields come from Shunya (`CallAnalysis.*`). Otto never infers booking from appointments.
- Rates are null-safe (null if denominator is 0)

---

### GET `/api/v1/metrics/csr/booking-trend/self`

**Roles**: `csr` only

**Description**: Get booking rate trend over time with summary metrics.

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date
- `date_to` (optional, ISO8601): End date
- `granularity` (optional, default: "month"): Time bucket size - `"day"`, `"week"`, or `"month"`

**Response**:

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
    value: number | null;                           // Booking rate for this period
  }>;
}
```

**Example Request**:

```typescript
const trend = await apiGet<CSRBookingTrendSelfResponse>(
  '/api/v1/metrics/csr/booking-trend/self?granularity=month&date_from=2025-01-01&date_to=2025-01-31'
);
```

**Example Response**:

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

**Important Notes**:
- All booking/qualification derived ONLY from Shunya fields (`CallAnalysis.booking_status`, `CallAnalysis.lead_quality`)
- Never infer booking from appointments table

---

## C. CSR Unbooked Calls

### GET `/api/v1/calls/unbooked/self`

**Roles**: `csr` only

**Description**: Get paginated list of unbooked calls for the authenticated CSR. Unbooked = any call where Shunya's `booking_status` is not `"booked"`.

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date
- `date_to` (optional, ISO8601): End date
- `page` (optional, default: 1): Page number (1-indexed)
- `page_size` (optional, default: 50): Page size (1-200)

**Response**:

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

**Example Request**:

```typescript
const unbooked = await apiGet<UnbookedCallsSelfResponse>(
  '/api/v1/calls/unbooked/self?page=1&page_size=50&date_from=2025-01-01'
);
```

**Example Response**:

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
      }
    ],
    "page": 1,
    "page_size": 50,
    "total": 25
  }
}
```

---

## D. CSR Objections + Drilldown

### GET `/api/v1/metrics/csr/objections/self`

**Roles**: `csr` only

**Description**: Get top objections and all objections for the authenticated CSR.

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date
- `date_to` (optional, ISO8601): End date

**Response**:

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

**Example Request**:

```typescript
const objections = await apiGet<CSRObjectionsSelfResponse>(
  '/api/v1/metrics/csr/objections/self?date_from=2025-01-01'
);
```

**Example Response**:

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

**UI Mapping**:
- **"Top 5 objections" card** → Use `top_objections` list
- **Expanded "all objections" list** → Use `all_objections` list

---

### GET `/api/v1/calls/by-objection/self`

**Roles**: `csr` only

**Description**: Get paginated list of calls filtered by a specific objection. Used for drilldown when clicking an objection.

**Query Parameters**:
- `objection` (required, string): Objection key to filter by
- `date_from` (optional, ISO8601): Start date
- `date_to` (optional, ISO8601): End date
- `page` (optional, default: 1): Page number (1-indexed)
- `page_size` (optional, default: 50): Page size (1-200)

**Response**:

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

**Example Request**:

```typescript
const calls = await apiGet<CallsByObjectionSelfResponse>(
  '/api/v1/calls/by-objection/self?objection=price%20too%20high&page=1&page_size=50'
);
```

**Example Response**:

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

**UI Mapping**:
- **Clicking one objection** → Call this endpoint with `objection` param
- **Play recordings** → Use `audio_url` field if present

---

## E. Auto AI-Queued Leads (Company-Level, Visible to CSR)

### GET `/api/v1/metrics/csr/auto-queued-leads`

**Roles**: `csr`, `manager`

**Description**: Get auto-queued leads from AI recovery (missed calls/texts that Otto handled). This data is company-wide and visible to all CSRs, not scoped to individual CSR.

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date
- `date_to` (optional, ISO8601): End date

**Response**:

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

**Example Request**:

```typescript
const leads = await apiGet<AutoQueuedLeadsResponse>(
  '/api/v1/metrics/csr/auto-queued-leads?date_from=2025-01-01'
);
```

**Example Response**:

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

**Important Notes**:
- **Scoping**: Company-wide data, not CSR-specific
- **Source**: Pulled from missed calls/texts that Otto AI handled
- **Purpose**: Leads ready for booking that any CSR can pick up

---

## F. CSR Missed Call Recovery

### GET `/api/v1/metrics/csr/missed-calls/self`

**Roles**: `csr` only

**Description**: Get high-level missed call recovery metrics for the authenticated CSR.

**Query Parameters**:
- `date_from` (optional, ISO8601): Start date
- `date_to` (optional, ISO8601): End date

**Response**:

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

**Example Request**:

```typescript
const metrics = await apiGet<CSRMissedCallsSelfResponse>(
  '/api/v1/metrics/csr/missed-calls/self?date_from=2025-01-01'
);
```

**Example Response**:

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

**UI Mapping**: Use this for the high-level metrics card

---

### GET `/api/v1/leads/missed/self`

**Roles**: `csr` only

**Description**: Get paginated list of missed leads (booked, pending, or dead) for the authenticated CSR.

**Query Parameters**:
- `status` (optional): Filter by status - `"booked"`, `"pending"`, or `"dead"`
- `date_from` (optional, ISO8601): Start date
- `date_to` (optional, ISO8601): End date
- `page` (optional, default: 1): Page number (1-indexed)
- `page_size` (optional, default: 50): Page size (1-200)

**Response**:

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

**Example Request**:

```typescript
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

**Example Response**:

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

**UI Mapping**:
- **Three lists/columns (booked, pending, dead)** → Call this endpoint with `status` filter for each

**Data Source Notes**:
- **From Shunya**: `status` (booked/dead classification), booking/outcome
- **From CallRail/Twilio**: `attempt_count`, `last_contacted_at`

---

## G. RBAC & Scoping (CSR)

### CSR Role Scoping Rules

**CSR can see**:
- ✅ Own calls (filtered by `Call.owner_id == csr_user_id`)
- ✅ Own leads (filtered by CSR ownership)
- ✅ Own tasks (filtered by `Task.assignee_id == csr_user_id`)
- ✅ Company-wide auto-queued leads (shared pool for all CSRs)

**CSR cannot see**:
- ❌ Other CSRs' personal calls/leads/tasks
- ❌ Sales Rep appointments
- ❌ Manager-only endpoints (use Exec views instead)

### Manager Role

Managers may call some CSR endpoints (e.g., `/api/v1/metrics/csr/auto-queued-leads`) but are intended to use Exec dashboard views for company-wide metrics.

### Ask Otto Scoping

When a CSR calls Ask Otto:
- Backend automatically sends `X-Target-Role: customer_rep` to Shunya
- Context includes only that CSR's identity + data: `{"user_role": "csr", "csr_id": <current_user_id>}`
- Does NOT include other reps' metrics or company-level aggregates

---

## 8. Testing Your Setup

### 1. Test Authentication

```typescript
// Try fetching your company's data
const metrics = await apiGet('/api/v1/dashboard/metrics?company_id=YOUR_COMPANY_ID');
console.log('✅ Authentication working!', metrics);
```

### 2. Test Tenant Isolation

```typescript
// Try accessing another company's data (should fail with 403)
try {
  const otherCompanyData = await apiGet('/api/v1/dashboard/metrics?company_id=OTHER_COMPANY_ID');
} catch (error) {
  if (error.status === 403) {
    console.log('✅ Tenant isolation working!');
  }
}
```

### 3. Test Error Handling

```typescript
// Try accessing non-existent resource (should fail with 404)
try {
  const missing = await apiGet('/api/v1/contact-cards/non-existent-id');
} catch (error) {
  if (error.status === 404) {
    console.log('✅ Error handling working!');
  }
}
```

---

## 9. Next Steps

1. **Set up environment variables**:
   ```env
   NEXT_PUBLIC_API_BASE_URL=https://ottoai-backend-production.up.railway.app
   ```

2. **Implement API client** using the patterns above

3. **Start with a simple endpoint** (e.g., `GET /api/v1/dashboard/metrics`) to verify auth works

4. **Read the full integration spec**: [CSR_APP_INTEGRATION.md](./CSR_APP_INTEGRATION.md) for complete endpoint details

---

## 10. Quick Reference

| Item | Value |
|------|-------|
| **Base URL** | `process.env.NEXT_PUBLIC_API_BASE_URL` or Railway URL |
| **Auth Header** | `Authorization: Bearer <JWT_FROM_CLERK>` |
| **Content-Type** | `application/json` |
| **Response Format** | `{ success: boolean, data: T }` |
| **Error Format** | `{ error_code: string, message: string }` |

---

**For full endpoint-by-endpoint details, see [CSR_APP_INTEGRATION.md](./CSR_APP_INTEGRATION.md)**

---

## 11. Shunya Integration Notes

### Source of Truth

**All semantic analysis comes from Shunya**. Otto backend never overrides or infers Shunya's semantics. This includes:
- Booking status (`booking_status` from `CallAnalysis`)
- Qualification status (`lead_quality` from `CallAnalysis`)
- Objections (`objections` array from `CallAnalysis`)
- Compliance scores (`sop_compliance_score` from `CallAnalysis`)
- Sentiment scores (`sentiment_score` from `CallAnalysis`)

**Important**: Otto never infers booking from the `Appointment` table. All booking metrics are derived exclusively from Shunya's `CallAnalysis.booking_status` field.

### Enum Alignment

**BookingStatus** (from Shunya canonical enums):
- `booked` - Appointment scheduled
- `not_booked` - No appointment scheduled
- `service_not_offered` - Customer needs service we don't provide

**QualificationStatus** (from Shunya `lead_quality`):
- `hot` - High urgency, ready to close
- `warm` - Showing interest but not urgent
- `cold` - Low interest, informational stage
- `qualified` - Qualified (general)
- `unqualified` - Not a fit for our services

**CallOutcomeCategory** (from Shunya):
- `qualified_but_unbooked` - Qualified but no booking
- `qualified_service_not_offered` - Qualified but service not offered
- `unqualified` - Not qualified

### Shunya-Derived Fields (May Be Null)

When calling endpoints that return Shunya analysis data, the following fields may be `null` or empty if Shunya hasn't finished processing:
- `transcript` (from `CallTranscript`) - May be `null` if transcription in progress
- `objections` (from `CallAnalysis`) - May be empty array `[]` if analysis not complete
- `sop_compliance_score` - May be `null` if compliance check not run
- `sentiment_score` - May be `null` if analysis not complete
- `lead_quality` / `qualification_status` - May be `null` if qualification analysis not complete
- `booking_status` - May be `null` if booking analysis not complete

**Frontend Handling**: Always check for `null` values and empty arrays. Show appropriate loading/empty states when Shunya processing is incomplete.


