# Internal AI Search Endpoint - Implementation Summary

**Date**: 2025-11-24  
**Endpoint**: `POST /internal/ai/search`  
**Purpose**: Flexible search and analytics for Ask Otto backend

---

## ✅ **Implementation Complete**

### **New Files Created**

1. **`app/schemas/ai_search.py`**
   - `AISearchFilters` - Filter criteria (rep_ids, lead_statuses, objections, sentiment, dates, etc.)
   - `AISearchOptions` - Search behavior (include_calls, include_aggregates, pagination, sorting)
   - `AISearchRequest` - Complete request body
   - `AISearchCallItem` - Lightweight call metadata for results
   - `AISearchAggregates` - Aggregate analytics (counts, distributions, averages)
   - `AISearchResponse` - Complete response

2. **`app/routes/ai_search.py`**
   - `POST /internal/ai/search` endpoint
   - Query construction with SQLAlchemy joins
   - Filter application logic
   - Aggregate calculation
   - Multi-tenant scoping

3. **`app/tests/test_ai_search.py`**
   - Authentication tests
   - Tenant isolation tests
   - Filter tests (rep, date, objections, sentiment)
   - Aggregate calculation tests
   - Pagination tests

### **Updated Files**

1. **`app/main.py`**
   - Registered `ai_search_router` after `ai_internal_router`

---

## 🔧 **Implementation Details**

### **Query Construction**

- **Base Query**: `Call` with LEFT JOINs to:
  - `CallAnalysis` (for objections, sentiment, SOP scores)
  - `Lead` (for lead status)
  - `Appointment` (for appointment outcomes and rep assignment)

- **Default Date Range**: Last 30 days (if not specified)

- **Multi-Tenant Scoping**: All queries filtered by `company_id` from auth context

### **Filters Supported**

1. **`rep_ids`** - Filter by sales rep IDs (checks both `Call.assigned_rep_id` and `Appointment.assigned_rep_id`)
2. **`lead_statuses`** - Filter by lead status values
3. **`appointment_outcomes`** - Filter by appointment outcome values
4. **`has_objections`** - Boolean filter for calls with/without objections
5. **`objection_labels`** - Filter by specific objection labels (e.g., "price", "timeline")
6. **`sentiment_min/max`** - Range filter on sentiment score (0.0-1.0)
7. **`min_sop_score/max_sop_score`** - Range filter on SOP compliance score (0-10)
8. **`date_from/date_to`** - Date range filter (defaults to last 30 days)

### **Sorting**

- `started_at` / `-started_at` - Sort by call creation time
- `sentiment_score` / `-sentiment_score` - Sort by sentiment score
- Default: `-started_at` (newest first)

### **Aggregates Calculated**

1. **`total_calls`** - Total count matching filters
2. **`calls_by_outcome`** - Distribution by derived outcome (won/lost/booked/pending/missed/cancelled)
3. **`calls_by_rep`** - Distribution by rep_id
4. **`calls_with_objections`** - Count of calls with objections
5. **`objection_label_counts`** - Count by objection label
6. **`avg_sentiment`** - Average sentiment score (where available)
7. **`avg_sop_score`** - Average SOP compliance score (where available)

### **Outcome Derivation Logic**

The endpoint derives outcome from:
1. `Appointment.outcome` (if appointment exists)
2. `Lead.status` (mapped to won/lost/booked/nurturing)
3. `Call.booked` / `Call.missed_call` / `Call.cancelled` flags
4. Default: "pending"

---

## 📝 **Example Request/Response**

### **Request Example**

```json
{
  "filters": {
    "rep_ids": ["rep_123", "rep_456"],
    "has_objections": true,
    "objection_labels": ["price", "timeline"],
    "sentiment_min": 0.5,
    "date_from": "2025-10-25T00:00:00Z",
    "date_to": "2025-11-24T23:59:59Z"
  },
  "options": {
    "include_calls": true,
    "include_aggregates": true,
    "limit": 50,
    "offset": 0,
    "sort_by": "-started_at"
  }
}
```

### **Response Example**

```json
{
  "calls": [
    {
      "call_id": 12345,
      "rep_id": "rep_123",
      "lead_id": "lead_789",
      "appointment_id": "apt_456",
      "contact_card_id": "contact_321",
      "company_id": "company_1",
      "started_at": "2025-11-20T10:00:00Z",
      "ended_at": null,
      "duration_seconds": 300,
      "outcome": "booked",
      "sentiment_score": 0.75,
      "main_objection_label": "price",
      "has_objections": true,
      "sop_score": 8.5
    }
  ],
  "aggregates": {
    "total_calls": 15,
    "calls_by_outcome": {
      "booked": 8,
      "pending": 5,
      "won": 2
    },
    "calls_by_rep": {
      "rep_123": 10,
      "rep_456": 5
    },
    "calls_with_objections": 12,
    "objection_label_counts": {
      "price": 8,
      "timeline": 4,
      "competitor": 2
    },
    "avg_sentiment": 0.687,
    "avg_sop_score": 7.85
  }
}
```

---

## 🔒 **Security & Multi-Tenancy**

- ✅ Uses `get_ai_internal_context()` dependency (same as other `/internal/ai/*` endpoints)
- ✅ Requires `Authorization: Bearer <AI_INTERNAL_TOKEN>`
- ✅ Requires `X-Company-Id` header
- ✅ All queries filtered by `company_id == ctx.company_id`
- ✅ No cross-tenant data leaks possible

---

## 🧪 **Test Coverage**

Tests cover:
- ✅ Authentication (missing/invalid token → 401)
- ✅ Tenant isolation (only returns authenticated company's data)
- ✅ Rep filtering
- ✅ Date range filtering
- ✅ Objection filtering (has_objections, objection_labels)
- ✅ Sentiment range filtering
- ✅ Aggregate calculations
- ✅ Pagination
- ✅ Options (include_calls, include_aggregates)

---

## 📊 **Performance Considerations**

1. **Indexes Used**:
   - `Call.company_id` (indexed)
   - `Call.created_at` (for date filtering)
   - `CallAnalysis.tenant_id`, `CallAnalysis.call_id` (indexed)
   - `Lead.company_id`, `Lead.id` (indexed)
   - `Appointment.company_id`, `Appointment.lead_id` (indexed)

2. **Query Optimization**:
   - LEFT JOINs to avoid excluding calls without analysis/lead/appointment
   - Aggregates calculated on filtered set (not all calls)
   - Pagination applied only when `include_calls=True`

3. **Default Limits**:
   - Default `limit=50`, max `limit=200`
   - Default date range: last 30 days

---

## 🚀 **Usage by Ask Otto**

Ask Otto backend will:
1. Parse natural language query → structured filters
2. Call `POST /internal/ai/search` with filters
3. Use `aggregates` for quick analytics
4. Use `calls` list for drill-down details
5. Optionally set `include_calls=False` if only aggregates needed

---

## ✅ **No Schema/Model Changes Required**

All fields used already exist:
- ✅ `CallAnalysis.objections` (JSON)
- ✅ `CallAnalysis.sentiment_score` (Float)
- ✅ `CallAnalysis.sop_compliance_score` (Float)
- ✅ `Call.company_id`, `Call.assigned_rep_id`, `Call.created_at`
- ✅ `Lead.status`, `Lead.company_id`
- ✅ `Appointment.outcome`, `Appointment.assigned_rep_id`

---

**Implementation Status**: ✅ **COMPLETE**

Endpoint is ready for Ask Otto integration.

