# Otto ↔ Shunya Responsibility Matrix

This document defines, stage by stage, **who owns what** between:

- **Otto** (core product, data, workflows, UI)
- **Shunya / Ask Otto** (ASR, analysis, coaching, LLM layer)

Property intelligence (roof/sqft/equity) is explicitly **Otto-owned**.

---

## Stage 1 – Inbound CSR Call (Phone rings → call handled or missed)

**Shunya / Ask Otto**

- ASR transcription of CSR call audio
- Call-level analysis:
  - Summary
  - Intent / reason for call
  - Qualification status
  - Outcome classification:
    - qualified_and_booked
    - qualified_not_booked
    - qualified_service_not_offered
    - not_qualified
  - Objections & objection labels
  - SOP compliance scoring + gaps
  - Sentiment
  - Pending actions / tasks
  - Missed opportunities (upsell / cross-sell)
- Entity extraction:
  - Customer name (if spoken)
  - Address (for property intelligence trigger)
  - Service category
- Returns analysis + segmentation to Otto via ShunyaJob pipeline + webhook

**Otto**

- Receives CallRail webhooks and creates/updates:
  - `Call`
  - `ContactCard`
  - `Lead`
- Triggers Shunya jobs (CSR call analysis)
- Stores:
  - Transcript
  - Analysis (CallAnalysis)
  - Tasks from pending actions
  - KeySignals from missed opportunities
- Updates:
  - Lead status (new → qualified_*)
  - Lead status history
- Emits domain events:
  - `call.created`
  - `call.transcribed`
  - `lead.status_changed`
- Triggers property intelligence (scraper) when address is known
  - Uses Otto-owned ChatGPT scraper, not Shunya

---

## Stage 2 – Missed Calls & Lead Nurture

**Shunya / Ask Otto**

- Conversation intelligence for nurture flows (when used):
  - Drafting SMS follow-ups
  - Understanding replies
  - Suggesting next steps or re-booking attempts
- Classifying inbound SMS replies (e.g., “not interested”, “call later”, “already booked”)

**Otto**

- Owns missed-call queue and SLA logic
- Sends Twilio SMS messages and records:
  - `MessageThread`
  - SMS attempts/outcomes
- Persists all messages under the ContactCard timeline
- Creates Tasks for:
  - Manual callbacks
  - Escalations
- Updates Lead status based on nurture outcome
- Exposes nurture history to UI and Ask Otto via:
  - `/internal/ai/calls/{id}`
  - `/internal/ai/leads/{id}`
  - `/api/v1/message-threads/{contact_card_id}`

---

## Stage 3 – Lead Routing & Lead Pool (Manager View)

**Shunya / Ask Otto**

- (Optional, later) Provide recommendations:
  - Which reps should run which leads
  - Which zones or time windows perform best
- Answer manager questions via `/internal/ai/search`:
  - Leads at risk
  - Leads stuck in certain stages
  - Rep performance patterns

**Otto**

- Owns Lead Pool:
  - `Lead.pool_status` (in_pool / assigned / closed / archived)
  - Rep requests & manager assignments
  - `RepAssignmentHistory`
- Exposes Lead Pool APIs:
  - `GET /api/v1/lead-pool`
  - `POST /api/v1/lead-pool/{lead_id}/request`
  - `POST /api/v1/lead-pool/{lead_id}/assign`
- Updates:
  - Lead status
  - Rep assignment
- Emits:
  - `lead.requested_by_rep`
  - `lead.assigned_to_rep`
- Surfaces Lead Pool state in Contact Card Top Section

---

## Stage 4 – Sales Rep Workflow & Geofenced Recording

**Shunya / Ask Otto**

- ASR & analysis of **in-person sales visits**
- Meeting segmentation:
  - Greeting / rapport
  - Discovery
  - Proposal / close
  - Objection handling
  - Wrap-up / next steps
- Visit-level analysis:
  - Outcome classification:
    - won
    - lost
    - pending_decision
    - no_show
    - rescheduled
  - Objections & their handling
  - SOP compliance score
  - Sentiment
  - Recommended next actions

**Otto**

- Manages rep app and geofencing:
  - Rep clock-in / clock-out
  - Location tracking while on shift
  - Auto-start/stop recording:
    - Start when entering geofence (~200 ft)
    - Stop when leaving (~500 ft)
- Creates and manages:
  - `RecordingSession` records
  - Ghost mode settings per rep:
    - Analysis allowed
    - Raw audio not stored / not shared with org
- Upload flow:
  - After visit audio upload, trigger Shunya visit analysis via async job pipeline
- Persists:
  - Transcript
  - Visit analysis
  - Appointment outcome & Lead status
  - Tasks (pending actions)
  - KeySignals (missed opportunities)
- Emits:
  - `appointment.created`
  - `appointment.outcome_updated`
  - `recording_session.analyzed`

---

## Stage 5 – Post-Visit, Deal Flow & Wins Feed

**Shunya / Ask Otto**

- Helps answer questions:
  - “Why did we win this deal?”
  - “Why did we lose it?”
  - “What should we do next on this undecided proposal?”
- Provides explanations of:
  - Objections
  - Customer concerns
  - Sales behavior patterns

**Otto**

- Owns:
  - Appointment outcomes (won, lost, pending, no_show, rescheduled)
  - Deal size capture
  - Wins feed:
    - `GET /api/v1/wins-feed`
  - Tasks for follow-ups (pending actions)
- Triggers review flows:
  - `POST /api/v1/reviews/request` to initiate Google review / other platforms
- Updates:
  - Lead.deal_status
  - Lead.closed_at
- Surfaces full deal context on Contact Card bottom section

---

## Stage 6 – Ask Otto (Internal GPT) & Analytics

**Shunya / Ask Otto**

- LLM engine for:
  - Natural-language questions about calls, reps, performance, trends
  - Explanations and coaching
  - “Top objections”, “Stage-wise performance”, “Rep trends”
- Uses Otto APIs:
  - `/internal/ai/calls/{id}`
  - `/internal/ai/leads/{id}`
  - `/internal/ai/appointments/{id}`
  - `/internal/ai/companies/{id}`
  - `/internal/ai/services/{company_id}`
  - `/internal/ai/search` (for calls + aggregates)

**Otto**

- Exposes read-only, tenant-scoped APIs under `/internal/ai/*`
- Enforces:
  - `Authorization: Bearer AI_INTERNAL_TOKEN`
  - `X-Company-Id` headers
  - RBAC when needed
- Implements `/internal/ai/search` to:
  - Filter calls by rep, date, outcomes, objections, sentiment, SOP scores
  - Return:
    - Calls list
    - Aggregates (per rep, per outcome, objections, etc.)
- Logs and monitors all Ask Otto queries for:
  - Security
  - Performance
  - Cost controls

---

## Stage 7 – Property Intelligence (Otto-Owned Only)

**Shunya / Ask Otto**

- Not responsible for property scraping or valuation.

**Otto**

- When an address is extracted (from CSR call or otherwise), Otto:
  - Feeds address into its own ChatGPT-based scraper using a custom prompt
  - Produces:
    - Roof type
    - Sqft
    - Year built
    - Stories
    - HOA
    - Subdivision
    - Est value range
    - Potential equity
    - For-sale flag
  - Stores output in `ContactCard.property_snapshot`
- Surfaces property intelligence in Contact Card Top/Middle sections
- Shunya may **read** this data via internal AI APIs, but does not generate it

---

This matrix is the **single source of truth** for what Otto vs Shunya own at each stage of the lifecycle and what each side can expect from the other.
