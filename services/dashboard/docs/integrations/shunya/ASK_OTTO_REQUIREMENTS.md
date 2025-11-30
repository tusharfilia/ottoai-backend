# Ask Otto – Requirements & Expectations

## 1. Overview

Ask Otto is the AI “brain” that sits on top of Otto’s data and workflows for home-services companies.  
It needs to:

- Answer **per-call questions** (“What happened on this call?”, “Why did we lose it?”)
- Provide **coaching & SOP feedback** to reps and managers
- Surface **trends & analytics** (top objections, sentiment trends, stage performance)
- Help managers decide **next best actions** for leads and deals

To do this safely and at scale, Ask Otto **never talks directly to Otto’s database**.  
It only talks to **read-only, tenant-scoped APIs** exposed under `/internal/ai/*` and `/internal/ai/search`.

---

## 2. Otto → Ask Otto: Data Surfaces

Ask Otto relies on the following Otto endpoints:

### 2.1 Per-call / Per-lead metadata

- `GET /internal/ai/calls/{call_id}`
  - For a single call: call metadata, rep, company, booking outcome

- `GET /internal/ai/leads/{lead_id}`
  - Lead state, contact info, associated appointments

- `GET /internal/ai/appointments/{appointment_id}`
  - Appointment timing, rep assignment, outcome, deal size, service type

- `GET /internal/ai/companies/{company_id}`
  - Company profile, timezone, services offered

- `GET /internal/ai/services/{company_id}`
  - Service catalog for upsell/cross-sell suggestions

All are:

- Read-only
- Multi-tenant scoped via `X-Company-Id`
- Protected via `Authorization: Bearer <AI_INTERNAL_TOKEN>`

---

## 3. Ask Otto Modes & Required Data

### 3.1 Per-Call Mode (“Explain this call”)

Triggered when Ask Otto is opened **from a specific call** in the UI.

Frontend will pass:

- `call_id`
- `company_id`
- (optionally) `rep_id`

Ask Otto must:

1. Fetch structured call context:
   - `GET /internal/ai/calls/{call_id}`
   - Possibly `GET /internal/ai/leads/{lead_id}`, `GET /internal/ai/appointments/{appointment_id}` if IDs are present

2. Combine with Shunya analysis:
   - Transcript
   - Summary
   - Objections
   - SOP compliance
   - Sentiment
   - Pending actions
   - Missed opportunities

3. Answer questions like:
   - “Why didn’t this call book?”
   - “What did the customer care most about?”
   - “What should we do next for this lead?”

### 3.2 Free-Form Rep Mode (“What happened on my last 5 calls?”)

Triggered when Ask Otto is opened **without a specific call**.

Required Otto capability:

- `GET /internal/ai/search` with filters such as:
  - `rep_ids`
  - `date_from` / `date_to`
  - `lead_statuses`
  - `appointment_outcomes`
  - `has_objections`, `objection_labels`
  - sentiment / SOP ranges

Ask Otto uses this to:

- Get a list of recent calls for a rep
- Drill into selected calls via `/internal/ai/calls/{id}` etc.
- Answer questions like:
  - “Where am I losing deals?”
  - “What objections do I struggle with?”

### 3.3 Manager / Analytics Mode

Ask Otto answers manager-level questions like:

- “What are the **top objections** in the last 30 days?”
- “Which reps have the lowest SOP compliance?”
- “How has sentiment changed this month vs last?”

Otto requirements:

- `/internal/ai/search` supports:
  - Aggregates:
    - `total_calls`
    - `calls_by_outcome`
    - `calls_by_rep`
    - `calls_with_objections`
    - `objection_label_counts`
    - `avg_sentiment`
    - `avg_sop_score`
  - Default date window: **last 30 days**
  - Optional quick windows: **7 days** and **90 days**

Ask Otto can:

- Use `/internal/ai/search` for analytics + samples
- Pull individual calls via `/internal/ai/calls/{call_id}` when drilling down

---

## 4. Default Date Ranges & Windows

- **Default** window for trends: **last 30 days**
- Supporting windows:
  - 7 days – short-term shifts
  - 90 days – long-term patterns

Ask Otto should:

- Assume 30 days if caller does not specify a range
- Allow explicit boundaries when provided in the question

---

## 5. Multi-Tenancy & Security Expectations

Every Ask Otto API call into Otto must:

- Include `Authorization: Bearer <AI_INTERNAL_TOKEN>`
- Include `X-Company-Id: <company_id>`

Otto guarantees:

- All `/internal/ai/*` and `/internal/ai/search` endpoints are **tenant-scoped** by `company_id`
- A given `AI_INTERNAL_TOKEN` can be scoped to one or more tenants (configurable)
- No direct DB or raw table access is ever provided to Ask Otto

---

## 6. Out-of-Scope for Ask Otto

Ask Otto does **not**:

- Create or update Otto records directly
- Manage Twilio, CallRail, or any telephony
- Own property intelligence (roofing scraper is Otto-owned)
- Own lead pool or routing logic

Ask Otto **reads**, explains, and recommends; Otto **stores**, **routes**, and **executes**.

This document is the authoritative reference for how Ask Otto should consume Otto’s internal AI APIs and what responsibilities live on each side.
