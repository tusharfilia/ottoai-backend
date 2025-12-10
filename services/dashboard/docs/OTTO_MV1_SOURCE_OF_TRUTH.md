You, Cursor, Shunya, and the FE agency can all treat this as the canonical contract. It's written to be:

- Backend-first (DB + APIs)
- Shunya-aligned (using the integration docs you shared )
- Consistent with your existing CSR + Sales Rep integration docs
- Executable as a checklist for audits later

# OTTO MV1 – Source of Truth (v1.0)

## Surfaces in MV1

- CSR Web App (Next.js – "CSR dashboard")
- Executive Web App (same codebase, different RBAC)
- Sales Rep Mobile App (React Native / Expo)
- Shunya-backed AI stack (ASR + analysis + insights)
- Otto backend (FastAPI + Postgres + Celery)

## 1. Core Domain Model & IDs

### 1.1 Tenancy & Users

**company / tenant**
- `company_id` (string, canonical tenant ID; mirrors Clerk org_id)
- Used everywhere as primary tenant scope.

**user**
- `user_id` (string; mirrors Clerk user_id)
- `role ∈ {csr, manager, exec, sales_rep, admin}`
- Optional: `permissions: string[]` for finer-grained access in future.

**RBAC enforcement**
- Done via middleware that pulls `company_id`, `user_id`, `role` from JWT and attaches a `TenantContext` to each request.

### 1.2 Universal Contact Card (canonical entity)

Single canonical entity, reused across all flows (CSR, Exec, Rep, Ask Otto):

**contact_card**
- `id` (UUID) ← canonical person/entity ID
- `company_id`
- `primary_phone`
- `secondary_phones[]` (optional)
- `email` (optional)
- `first_name`, `last_name`
- `full_name` (denormalized)
- `address_line_1`, `address_line_2`, `city`, `state`, `zip`, `country`
- `created_at`, `updated_at`
- `source ∈ {callrail, manual, auto_ai, import, otto, shunya}` (aligned with enums doc)

**Property intel** (from Otto property scraper):
- `property_type`, `roof_type`, `square_feet`, `valuation`, `hoa`, `bedrooms`, `bathrooms`, `year_built`, etc.

**AI summary fields:**
- `last_call_summary`
- `primary_intent`
- `risks[]` (deal risk signals; Otto computed from Shunya cues)
- `tags[]` (labels)

**Rules**
- EVERY call / lead / appointment / text / recording must point to a `contact_card_id`.
- No separate "lead_id vs customer_id vs user_id" for the same person.
- Derived concepts (lead, appointment, pending_action) reference `contact_card_id` and their own IDs.

### 1.3 Other key entities (linked to ContactCard)

**lead**
- `id`
- `company_id`
- `contact_card_id`
- `stage ∈ {new, qualified, booked, pending, dead}`
- `qualification_status ∈ {hot, warm, cold, unqualified}` (Shunya aligned)
- `source` (ad channel / campaign / referral)
- `last_activity_at`

**call**
- `id`
- `company_id`
- `contact_card_id`
- `csr_id` (nullable; may be AutoAI)
- `assigned_rep_id` (nullable; for pre-visit calls)
- `direction ∈ {inbound, outbound}`
- `call_type ∈ {csr_call, sales_call, visit_call}`
- `callrail_call_id` / `twilio_sid`
- `audio_url`
- `started_at`, `ended_at`
- `duration_seconds`
- `booking_status ∈ {booked, not_booked, service_not_offered}` (Shunya)

**call_transcript**
- `id`
- `company_id`
- `call_id`
- `transcript_text`
- `speaker_labels`
- `confidence_score`
- `uwc_task_id` / `uwc_transcript_id` (Shunya IDs)

**call_analysis**
- `id`
- `company_id`
- `call_id`
- `qualification_status` (hot/warm/cold/unqualified)
- `sentiment_score`
- `objections[]` (linked to canonical objection taxonomy)
- `objection_severity`
- `sop_compliance_score`
- `sop_stages_completed[]`
- `pending_actions[]`
- `summary`
- `missed_opportunities[]`

**appointment**
- `id`
- `company_id`
- `contact_card_id`
- `sales_rep_id`
- `csr_id` (who booked it)
- `service_type`
- `scheduled_start_at`, `scheduled_end_at`
- `status ∈ {scheduled, completed, no_show, cancelled}`
- `outcome ∈ {closed_won, closed_lost, open}` (aligned with outcome ENUM)
- `deal_value` (nullable)
- `source_call_id` (which CSR call generated this appointment)

**recording_session** (field visit / ride-along)
- `id`
- `company_id`
- `appointment_id`
- `sales_rep_id`
- `audio_url`
- `started_at`, `ended_at`
- `duration_seconds`
- Shunya IDs similar to call.

**pending_action**
- `id`
- `company_id`
- `contact_card_id`
- `linked_call_id` / `appointment_id` (optional)
- `assigned_to_type ∈ {csr, sales_rep, exec, system}`
- `assigned_to_user_id` (for CSR/rep owners)
- `category` (Enum from Otto if you choose to freeze; Shunya can align)
- `raw_text` (original Shunya text)
- `due_at`
- `status ∈ {open, in_progress, completed, cancelled}`

**task** (for UI to-do lists)
- Similar shape to `pending_action` but UI-friendly; may be a thin wrapper referencing it.

## 2. Shunya ↔ Otto Responsibilities (Line in the Sand)

### 2.1 Shunya does (per docs)

- ASR transcription (CSR calls, sales visits).
- NLU analysis:
  - Qualification (hot/warm/cold/unqualified).
  - Objection detection & classification (canonical objection categories).
  - Sentiment analysis.
  - SOP compliance scores & per-stage coverage (based on uploaded SOP).
  - Segmentation (Part1 / Part2 by discovery/inspection vs presentation/proposal/resolution).
  - Pending action detection (currently free-text but compatible with your ENUMs).
  - Missed opportunity tags (discovery/cross_sell/upsell/qualification/risk_signal/process_gap).
- Trend analytics & search APIs for Ask Otto / analytics queries.
- Webhook delivery with:
  - At-least-once semantics.
  - HMAC signatures.
  - Task-level IDs for idempotency.

### 2.2 Otto does (must be reflected in backend & DB)

- Owns all domain entities & schemas (ContactCard, Lead, Appointment, Call, etc.).
- Owns canonical ENUM values (objection categories, sentiment bands, outcome enums).
- Runs property scraping and enrichment.
- Computes:
  - Booking rate formulas (CSR/rep/company).
  - "Auto rescues" (missed calls recovered by AI vs by humans).
  - Win rates for reps.
  - Deal risk decision logic (Shunya provides signals; Otto decides low/med/high/critical).
- Defines what shows up on which dashboard for each role.
- Enforces multi-tenancy and RBAC.
- Exposes public APIs to frontend and internal AI APIs to Shunya (`/internal/ai/...`)

## 3. Ask Otto (RAG) – Contract

**High-level** (applies to CSR Ask Otto and Exec Ask Otto):

- **Backend API**: `/api/v1/ask-otto` (or equivalent)

**Inputs:**
- `question: string`
- `scope: "self" | "team" | "company"`
  - CSR: only "self"
  - Exec: "company" (and optionally "csr_team" | "sales_team")
- Optional: `call_id`, `contact_card_id`, `appointment_id`.

**Backend:**
- Uses Shunya search/analytics + Otto's own RAG/metrics to assemble answer.
- Never exposes Shunya directly; always via Otto API.

**Scope rules:**

**CSR Ask Otto:**
- Can see only:
  - Calls where `csr_id = user_id`.
  - Leads / appointments they touched.
  - Objections, coaching, stats limited to their own work.

**Exec Ask Otto:**
- Can see all calls/leads/appointments for `company_id`.

## 4. Metrics Definitions (What Backend Must Provide)

These are the numbers the UI is drawing; backend must compute them consistently from DB + Shunya analysis.

### 4.1 CSR-side metrics

**Per CSR** (scoped to `company_id` + `csr_id` and date range):

- **total_leads_spoken_to**
  - Count of calls with `call_type = csr_call` and associated leads.

- **qualified_leads**
  - Count where Shunya `qualification_status ∈ {hot, warm}`.

- **appointments_booked**
  - Appointments where `csr_id = this CSR` and `status = scheduled | completed`.

- **booking_rate**
  - `appointments_booked / qualified_leads`.

- **auto_rescues** (for missed-call recovery section)
  - Leads rescued where:
    - initial call was missed,
    - later booked after AI text/voice follow-up.

- **unbooked_appointments_list**
  - Calls where:
    - `call_type = csr_call`,
    - `booking_status = not_booked`,
    - Within date range.
  - Each row:
    - `contact_card_id`
    - `name`, `phone`
    - `reason_not_booked` (from Shunya objection/pending actions)
    - `last_spoken_at` (from call logs)

- **csr_objections**
  - Top objections for this CSR:
    - from `call_analysis.objections`.
    - Show `objection_category`, `occurrence_rate`.

### 4.2 Exec → CSR tab metrics

Same shapes as CSR, but:
- Aggregated over all CSRs (`call.csr_id IN company CSRs`).
- Objections: union across CSRs (with counts and rates).
- "Most coaching opportunity":
  - Derived from:
    - low SOP compliance scores,
    - high miss-rate on objection categories,
    - volume of calls.

### 4.3 Exec → Sales tab metrics

**Per Sales Rep:**
- **total_recorded_hours**
- **win_rate:**
  - `closed_won appointments / completed appointments`.
- **process_grade:**
  - Derived from Shunya's SOP compliance on visits.
- **auto_usage:**
  - of calls/visits processed by Otto + Shunya vs total possible.

**Also:**
- **pending_leads_by_rep**
  - Same concept as CSR pending-leads, but scoped to reps + post-appointment stage.

### 4.4 Missed Calls Recovery

For both CSR and Exec:
- **missed_calls_total**
- **calls_rescued_by_auto:**
  - Leads where AI text/voice engagement converted to booked.
- **calls_rescued_by_humans:**
  - Leads where CSR manually re-engaged after missed call.

All must be implemented as backend endpoints (e.g. `/api/v1/dashboard/csr-metrics`, `/api/v1/dashboard/exec-csr-metrics`, `/api/v1/dashboard/exec-sales-metrics`, `/api/v1/missed-calls/queue/*`), following your existing patterns.

## 5. RBAC – Role x Surface Matrix

**Roles**: `csr`, `manager`, `exec`, `sales_rep`.

### 5.1 General rules

- Tenant always enforced by `company_id` from JWT.
- Role-specific filtering:
  - **CSR:**
    - Only their own calls/leads/appointments/pending_actions.
  - **Sales Rep:**
    - Only appointments/recordings assigned to them.
    - Only leads assigned to them.
  - **Exec:**
    - Everything in `company_id` as read-only for analytics.
  - **Manager:**
    - Same as Exec, but may have more write capabilities.

### 5.2 Examples

- `/api/v1/missed-calls/queue/metrics`
  - Allowed roles: `csr`, `manager`, `exec`.
  - Data:
    - CSR: their slice.
    - Exec / manager: company-wide.

- `/api/v1/recording-sessions/*`
  - Sales rep: only own sessions.
  - Exec/manager: per company.
  - CSR: typically no access.

Your middleware and dependency injection must implement these checks once and reuse them across endpoints (as you already started).

## 6. Idempotency & Retry Safety

Given Shunya's at-least-once webhooks and Otto's own async jobs, the guarantees:

**Shunya → Otto webhooks:**
- Use `X-Shunya-Task-Id` as idempotency key.
- If the same `task_id` is processed twice, no double insert / double state transition.

**Otto → Shunya submissions:**
- Use deterministic natural keys:
  - e.g. `(company_id, call_id, "csr_analysis")`.
- Prevent resubmitting the same workload unless explicitly requested.

**DB side:**
- Unique constraints on:
  - `(company_id, call_id)` in analysis tables.
  - `(company_id, contact_card_id, category, due_at)` for `pending_actions` (if desired).

**Frontend:**
- Follows the behaviors already documented in CSR & Sales Rep integration docs (debounce submit, handle 409/429, etc.).

## 7. Exec & CSR Nested Frontend Structure (Single Repo)

**Given:**
- One FE repo: Exec + CSR nested.
- Role-based routing: same routes, different data scopes.

**Contract:**
- Backend never assumes "if path == /csr then role == csr".
- Backend trusts only JWT `role`.
- FE simply controls which components a user sees; all privilege enforcement remains backend-side.

## 8. Sales Rep Mobile App – Backend Expectations

The Sales Rep app will:
- List today's appointments (and optionally tomorrow/upcoming) for that rep.
- For each appointment card:
  - Pull ContactCard + Appointment + latest CallSummary + property intel.
- Start/stop field recording sessions:
  - Trigger recording (client-side).
  - Upload audio to Otto; Otto then sends to Shunya.
- After visit:
  - Rep sets outcome (`closed_won`, `closed_lost`, `open`),
  - Enters `deal_value` and simple reason codes,
  - Otto schedules AI follow-up as needed.

**Backend needs:**
- `/api/v1/reps/{rep_id}/appointments?date=YYYY-MM-DD`
- `/api/v1/appointments/{id}` with embedded contact card + AI insights.
- `/api/v1/recording-sessions` (POST start, POST stop+upload, GET by appointment).
- `/api/v1/reps/{rep_id}/stats` (for Exec's sales team stats, plus rep-self view).

Your `SALES_REP_APP_INTEGRATION.md` is already aligned with this; this Source of Truth just pins the domain semantics.

## 9. Known Gaps / TODO (from code + docs)

These are explicitly allowed to be "in-progress", but they must be tracked:

- Webhook polling vs pure webhook-driven:
  - Some flows still use `asyncio.sleep` rather than proper worker + webhook/callback.
- Transcript storage for recording sessions is incomplete.
- No RAG queries via Shunya search yet (Ask Otto still partially Otto-only).
- Trend windows: implement 7/30/90 day defaults consistently.
- Some dashboard endpoints mentioned in CSR docs are still TODO (e.g. `dashboard/metrics`, `top-objections`).

## 10. How to Use This Doc

This is now your north star spec. From here:

**Backend audit with Cursor**
- "Diff backend models + routes against Section 1–8 of `OTTO_MV1_SOURCE_OF_TRUTH.md` and list all mismatches (missing fields, wrong enums, missing endpoints, RBAC holes, idempotency gaps)."

**Shunya audit**
- "Check that Shunya integration (`uwc_client`, `shunya_integration_service`, webhook handler) fully matches Sections 2 & 6."

**Frontend audit (CSR + Exec + Sales Rep)**
- For each screen, verify:
  - It calls the right `/api/v1/*` endpoint.
  - It passes no extra IDs that break the universal ContactCard model.
  - Scope & role logic match Section 5.

