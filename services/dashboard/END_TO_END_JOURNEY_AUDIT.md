# Otto Backend - End-to-End Journey Audit

**Date**: 2025-11-24  
**Purpose**: Audit backend readiness for frontend integration + Shunya Ask Otto  
**Canonical Flow**: AZ Roof Co Example (6 phases)

---

## Executive Summary

**Overall Status**: 🟧 **PARTIAL** - Core infrastructure exists, but several critical gaps remain for full frontend integration.

**Key Findings**:
- ✅ **Phase 1 (Inbound CSR Call)**: 90% ready - Webhooks, Shunya pipeline, Contact Card assembly all functional
- ✅ **Phase 2 (Call Outcomes)**: 85% ready - Appointment creation works, missed call queue exists
- ✅ **Phase 3 (Lead Pool)**: 95% ready - All endpoints exist, assignment history tracked
- 🟧 **Phase 4 (Rep Workflow)**: 70% ready - Geofencing/recording exists, but missing "today's appointments" endpoint for reps
- 🟧 **Phase 5 (Post-Visit)**: 60% ready - Visit analysis works, but missing deal size input endpoint and wins feed
- ✅ **Phase 6 (Ask Otto)**: 95% ready - Internal AI endpoints exist, RBAC enforced

**Critical Gaps**:
1. **No endpoint for reps to get "today's appointments"** (only `/sales-rep/{rep_id}/appointments` which uses old Call model)
2. **No endpoint to mark appointment outcome + deal size** (PATCH exists but doesn't handle deal_size properly)
3. **No wins feed endpoint** for closed-won deals
4. **No review follow-up trigger** endpoint
5. **No Tasks CRUD endpoints** (tasks created by Shunya but no API to list/update)
6. **No KeySignals read endpoints** (signals created but not queryable)
7. **No SMS/nurture thread read API** for Contact Card

---

## Phase-by-Phase Audit

### **Phase 1: Inbound CSR Call** ✅ 90% Ready

#### 1.1 CallRail Webhook → Call/ContactCard/Lead Creation

**Status**: ✅ **READY**

**Endpoints**:
- `POST /callrail/call.incoming` - Creates Call, ContactCard, Lead
- `POST /callrail/call.answered` - Updates call status
- `POST /callrail/call.missed` - Routes to missed call queue
- `POST /callrail/call.completed` - Triggers Shunya analysis

**Models/Schemas**:
- `Call` model ✅
- `ContactCard` model ✅
- `Lead` model ✅
- `ensure_contact_card_and_lead()` service ✅

**Events Emitted**:
- `call.incoming` ✅
- `call.answered` ✅
- `call.missed` ✅

**Gaps**: None

---

#### 1.2 Shunya Async Job Pipeline

**Status**: ✅ **READY**

**Endpoints**:
- `POST /api/v1/shunya/webhook` - Shunya job completion webhook ✅
- Celery tasks: `process_call_recording` ✅

**Models/Schemas**:
- `ShunyaJob` model ✅
- `ShunyaJobService` ✅
- Async polling with exponential backoff ✅
- Idempotency guards ✅

**Processing**:
- ASR (transcript) ✅
- Call analysis (qualification, outcome, objections, SOP, missed opportunities, pending actions, address extraction) ✅
- Persists `CallTranscript`, `CallAnalysis` ✅
- Updates `Lead.status` + `LeadStatusHistory` ✅
- Creates `Tasks` from pending actions ✅
- Creates `KeySignals` from missed opportunities ✅
- Triggers property intelligence when address extracted ✅

**Events Emitted**:
- `call.transcribed` ✅
- `lead.updated` ✅
- `task.created` ✅
- `property_snapshot.updated` ✅

**Gaps**: None

---

#### 1.3 Dynamic Contact Card Display

**Status**: ✅ **READY**

**Endpoints**:
- `GET /api/v1/contact-cards/{contact_id}` ✅
- `GET /api/v1/contact-cards/by-phone?phone={number}` ✅

**Schema**: `ContactCardDetail` ✅

**Includes**:
- Top Section: `lead_status`, `LeadStatusHistory`, `key_signals`, `open_tasks` ✅
- Middle Section: `SOP compliance`, `objections`, `missed_opportunities`, `pending_actions`, `appointment_outcome`, `AI summary`, `recording_sessions` ✅
- Bottom Section: `booking_timeline`, `call_recordings`, `text/nurture_threads` ✅

**Service**: `ContactCardAssembler` ✅

**Gaps**: 
- 🟧 **SMS/nurture thread read API missing** - Contact Card assembler includes `text_threads` and `nurture_threads`, but there's no dedicated endpoint to fetch message threads separately. The data is embedded in ContactCardDetail, but if frontend needs to refresh just the thread, it must fetch entire Contact Card.

---

### **Phase 2: Call Outcomes** ✅ 85% Ready

#### 2.1 Qualified & Booked → Appointment Creation

**Status**: ✅ **READY**

**Endpoints**:
- `POST /api/v1/appointments` ✅
- Auto-geocodes address ✅
- Links to Lead + ContactCard ✅

**Models/Schemas**:
- `Appointment` model ✅
- `AppointmentCreateBody` schema ✅

**Events Emitted**:
- `appointment.created` ✅

**Lead Pool Integration**:
- Lead enters pool as `in_pool` ✅
- `Lead.pool_status` updated ✅

**Gaps**: None

---

#### 2.2 Qualified but Unbooked (Pending Action)

**Status**: ✅ **READY**

**Processing**:
- Tasks created by Shunya ✅
- Lead in nurturing state ✅

**Gaps**: None

---

#### 2.3 Qualified Service Not Offered

**Status**: ✅ **READY**

**Processing**:
- Lead marked appropriately ✅
- Missed opportunities logged as `KeySignals` ✅

**Gaps**: None

---

#### 2.4 Missed Call → Queue + SMS Nurture

**Status**: 🟧 **PARTIAL**

**Endpoints**:
- `POST /api/v1/missed-calls/queue/{call_id}` ✅
- `GET /api/v1/missed-calls/queue/entries` ✅
- `GET /api/v1/missed-calls/queue/entries/{queue_id}` ✅
- `POST /api/v1/missed-calls/queue/entries/{queue_id}/process` ✅
- `POST /api/v1/missed-calls/processor/start` ✅

**Service**: `MissedCallQueueService` ✅

**Events Emitted**:
- `call.missed` ✅

**Gaps**:
- 🟧 **SMS nurture thread read API missing** - Frontend can see SMS threads in Contact Card, but no dedicated endpoint to fetch nurture conversation history separately. See Phase 1.3 gap.

---

### **Phase 3: Lead Pool & Assignment** ✅ 95% Ready

#### 3.1 Manager Views Lead Pool

**Status**: ✅ **READY**

**Endpoints**:
- `GET /api/v1/lead-pool?status={status}` ✅
- Returns: `PoolLeadSummary[]` with location, property info, lead value, risk, signals ✅

**Schema**: `LeadPoolListResponse` ✅

**Includes**:
- Contact name, phone, address ✅
- Lead status, deal status ✅
- Key signals (titles) ✅
- Last activity timestamp ✅
- Assigned rep ID ✅
- Requested by rep IDs ✅

**Gaps**: None

---

#### 3.2 Rep Requests Lead

**Status**: ✅ **READY**

**Endpoints**:
- `POST /api/v1/lead-pool/{lead_id}/request` ✅

**Processing**:
- Creates `RepAssignmentHistory` with `status="requested"` ✅
- Updates `Lead.requested_by_rep_ids` ✅

**Events Emitted**:
- `lead.requested_by_rep` ✅

**Gaps**: None

---

#### 3.3 Manager Assigns Lead

**Status**: ✅ **READY**

**Endpoints**:
- `POST /api/v1/lead-pool/{lead_id}/assign` ✅

**Processing**:
- Updates `Lead.pool_status` to `assigned` ✅
- Updates `Appointment.assigned_rep_id` if appointment exists ✅
- Creates/updates `RepAssignmentHistory` with `status="assigned"` ✅

**Events Emitted**:
- `lead.assigned_to_rep` ✅

**Gaps**: None

---

### **Phase 4: Rep Workflow** 🟧 70% Ready

#### 4.1 Rep Clock-In

**Status**: ✅ **READY**

**Endpoints**:
- `POST /api/v1/reps/{rep_id}/shifts/clock-in` ✅
- `GET /api/v1/reps/{rep_id}/shifts/today` ✅

**Models/Schemas**:
- `RepShift` model ✅
- `ShiftStatus` enum ✅

**Processing**:
- Creates active shift ✅
- Location tracking enabled ✅

**Gaps**: None

---

#### 4.2 Rep Sees Today's Appointments

**Status**: 🟥 **MISSING**

**Current Endpoints**:
- `GET /sales-rep/{rep_id}/appointments` - **USES OLD CALL MODEL** ❌
- `GET /mobile/appointments` - **USES OLD CALL MODEL** ❌

**Gap**: 
- 🟥 **No endpoint for reps to get today's appointments from Appointment model**
- Current endpoints query `Call` model with `booked=True`, but appointments should come from `Appointment` model
- Need: `GET /api/v1/reps/{rep_id}/appointments/today` or `GET /api/v1/appointments?assigned_rep_id={rep_id}&date={today}`

**Workaround**: Frontend could query `GET /api/v1/appointments/{appointment_id}` for each appointment, but no list endpoint exists.

---

#### 4.3 Rep Sees Contact Card Per Appointment

**Status**: ✅ **READY**

**Endpoints**:
- `GET /api/v1/appointments/{appointment_id}` - Returns appointment with lead + contact ✅
- `GET /api/v1/contact-cards/{contact_id}` - Full contact card ✅

**Gaps**: None

---

#### 4.4 Geofenced Auto-Recording

**Status**: ✅ **READY**

**Endpoints**:
- `POST /api/v1/recording-sessions/start` ✅
- `POST /api/v1/recording-sessions/{session_id}/stop` ✅
- `POST /api/v1/recording-sessions/{session_id}/upload-audio` ✅
- `GET /api/v1/recording-sessions/{session_id}` ✅

**Models/Schemas**:
- `RecordingSession` model ✅
- `RecordingMode` enum (normal, ghost, off) ✅
- `AudioStorageMode` enum (persistent, ephemeral, not_stored) ✅

**Processing**:
- Geofence validation ✅
- Audio upload ✅
- Shunya visit analysis job created ✅

**Events Emitted**:
- `recording_session.started` ✅
- `recording_session.stopped` ✅

**Gaps**: None

---

#### 4.5 Ghost Mode

**Status**: ✅ **READY**

**Configuration**:
- `SalesRep.recording_mode` field ✅
- `Company.ghost_mode_storage` config ✅
- `Company.ghost_mode_retention` config ✅

**Processing**:
- `RecordingSessionService.get_audio_storage_mode()` ✅
- `RecordingSessionService.apply_ghost_mode_restrictions()` ✅
- Audio URL hidden in API responses ✅

**Gaps**: 
- 🟧 **No rep API to toggle ghost mode per user or per visit** - Ghost mode is set at rep level (`SalesRep.recording_mode`), but there's no endpoint for reps to toggle it themselves. Managers can update it via `PUT /sales-rep/{rep_id}`, but no self-service toggle exists.

---

### **Phase 5: Post-Visit Analysis & Closing the Loop** 🟧 60% Ready

#### 5.1 Shunya Visit + Segmentation Analysis

**Status**: ✅ **READY**

**Processing**:
- Visit transcript + segmentation stored ✅
- `RecordingAnalysis` model ✅
- `RecordingTranscript` model ✅

**Events Emitted**:
- `recording_session.transcription.completed` ✅
- `recording_session.analysis.completed` ✅

**Gaps**: None

---

#### 5.2 Appointment Outcome Updates

**Status**: 🟧 **PARTIAL**

**Endpoints**:
- `PATCH /api/v1/appointments/{appointment_id}` ✅
- Accepts `outcome` field ✅

**Models/Schemas**:
- `AppointmentOutcome` enum (won, lost, pending, no_show, rescheduled) ✅
- `AppointmentUpdateBody` schema ✅

**Processing**:
- Updates `Appointment.outcome` ✅
- Updates `Appointment.status` to `completed` when outcome set ✅
- Updates `Lead.status` based on outcome ✅

**Events Emitted**:
- `appointment.updated` ✅
- `appointment.outcome_updated` ✅ (emitted by Shunya integration service)

**Gaps**:
- 🟧 **Deal size input not properly handled** - `Appointment.deal_size` field exists, but `AppointmentUpdateBody` doesn't explicitly include it. Frontend can pass it in `PATCH`, but schema doesn't document it. Also, `Lead.deal_size` should be synced when appointment outcome = won.

---

#### 5.3 Tasks from Pending Actions

**Status**: ✅ **READY** (Creation), 🟥 **MISSING** (Read/Update)

**Creation**:
- Tasks created by Shunya ✅
- `Task` model with `unique_key` for idempotency ✅

**Endpoints**:
- 🟥 **No GET /api/v1/tasks endpoint** - Tasks are created but not queryable
- 🟥 **No PATCH /api/v1/tasks/{task_id} endpoint** - Can't mark tasks as completed
- 🟥 **No GET /api/v1/tasks?contact_card_id={id} endpoint** - Can't list tasks for a contact

**Gaps**:
- 🟥 **Tasks CRUD endpoints missing** - Frontend needs to list, update, and complete tasks. Currently tasks are only visible in Contact Card `open_tasks` array, but no dedicated API exists.

---

#### 5.4 KeySignals from Missed Opportunities

**Status**: ✅ **READY** (Creation), 🟥 **MISSING** (Read/Acknowledge)

**Creation**:
- KeySignals created by Shunya ✅
- `KeySignal` model with `unique_key` for idempotency ✅

**Endpoints**:
- 🟥 **No GET /api/v1/key-signals endpoint** - Signals are created but not queryable
- 🟥 **No PATCH /api/v1/key-signals/{signal_id}/acknowledge endpoint** - Can't acknowledge signals

**Gaps**:
- 🟥 **KeySignals read/acknowledge endpoints missing** - Frontend needs to list and acknowledge signals. Currently signals are only visible in Contact Card `key_signals` array, but no dedicated API exists.

---

#### 5.5 Closed-Won: Deal Size Input

**Status**: 🟧 **PARTIAL**

**Models/Schemas**:
- `Appointment.deal_size` field ✅
- `Lead.deal_size` field ✅

**Endpoints**:
- `PATCH /api/v1/appointments/{appointment_id}` - Can update `deal_size` via schema extension, but not documented ✅

**Gaps**:
- 🟧 **Deal size input endpoint not explicit** - Frontend needs a clear endpoint to mark appointment as won + provide deal size. Current `PATCH` endpoint works but schema doesn't document `deal_size` field explicitly.
- 🟧 **Lead.deal_size not synced** - When appointment outcome = won and deal_size is set, `Lead.deal_size` should be updated automatically.

---

#### 5.6 Wins Feed

**Status**: 🟥 **MISSING**

**Endpoints**:
- 🟥 **No GET /api/v1/wins or GET /api/v1/appointments?outcome=won endpoint** - No endpoint to list closed-won deals

**Gaps**:
- 🟥 **Wins feed endpoint missing** - Frontend needs to display a feed of closed-won deals. Could be implemented as `GET /api/v1/appointments?outcome=won&status=completed&limit=50` or a dedicated `/api/v1/wins` endpoint.

---

#### 5.7 Review Follow-Up Trigger

**Status**: 🟥 **MISSING**

**Endpoints**:
- 🟥 **No POST /api/v1/appointments/{appointment_id}/trigger-review endpoint** - No endpoint to trigger review follow-up

**Gaps**:
- 🟥 **Review follow-up trigger missing** - When appointment outcome = won, frontend should be able to trigger a review follow-up (e.g., Google review request). No endpoint exists for this.

---

### **Phase 6: Ask Otto + Analytics** ✅ 95% Ready

#### 6.1 Ask Otto Integration

**Status**: ✅ **READY**

**Endpoints**:
- `POST /api/v1/rag/query` ✅
- `GET /api/v1/rag/queries` ✅
- `POST /api/v1/rag/queries/{query_id}/feedback` ✅

**Internal AI Endpoints** (for Shunya):
- `GET /internal/ai/calls/{call_id}` ✅
- `GET /internal/ai/leads/{lead_id}` ✅
- `GET /internal/ai/appointments/{appointment_id}` ✅
- `GET /internal/ai/companies/{company_id}` ✅
- `GET /internal/ai/reps/{rep_id}` ✅
- `GET /internal/ai/services/{company_id}` ✅

**Authentication**:
- Internal token auth ✅
- `X-Company-Id` header validation ✅
- Tenant isolation ✅

**Gaps**: None

---

#### 6.2 RBAC Enforcement

**Status**: ✅ **READY**

**Middleware**:
- `@require_role()` decorator ✅
- Role hierarchy enforced ✅
- Tenant context middleware ✅

**Permissions**:
- Reps see their own calls ✅
- Managers see org-wide ✅

**Gaps**: None

---

## Frontend Integration Checklist

### **CSR UI Needs**

| Feature | Endpoint | Status |
|---------|----------|--------|
| List calls | `GET /api/v1/dashboard/calls?status={status}` | ✅ Ready |
| Filter leads by status | `GET /api/v1/leads?status={status}` | 🟥 Missing |
| Open Contact Card | `GET /api/v1/contact-cards/{contact_id}` | ✅ Ready |
| View call history | Embedded in Contact Card | ✅ Ready |
| View SMS/nurture threads | Embedded in Contact Card | 🟧 Partial (no separate endpoint) |
| View Shunya analysis | Embedded in Contact Card | ✅ Ready |
| View property intelligence | Embedded in Contact Card | ✅ Ready |
| View tasks | Embedded in Contact Card | 🟧 Partial (no CRUD endpoints) |
| View key signals | Embedded in Contact Card | 🟧 Partial (no acknowledge endpoint) |

**Gaps**:
- 🟥 **No GET /api/v1/leads endpoint with filtering** - Frontend can't list leads by status
- 🟧 **No SMS thread refresh endpoint** - Must fetch entire Contact Card to refresh threads
- 🟧 **No Tasks CRUD** - Can't mark tasks complete or create new tasks
- 🟧 **No KeySignals acknowledge** - Can't acknowledge signals

---

### **Lead Pool UI Needs**

| Feature | Endpoint | Status |
|---------|----------|--------|
| List pool leads | `GET /api/v1/lead-pool` | ✅ Ready |
| Request lead (rep) | `POST /api/v1/lead-pool/{lead_id}/request` | ✅ Ready |
| Assign lead (manager) | `POST /api/v1/lead-pool/{lead_id}/assign` | ✅ Ready |
| See rep interest | Embedded in `PoolLeadSummary.requested_by_rep_ids` | ✅ Ready |
| See assignment history | `RepAssignmentHistory` model exists, but no endpoint | 🟥 Missing |

**Gaps**:
- 🟥 **No GET /api/v1/lead-pool/{lead_id}/assignment-history endpoint** - Frontend can't see full assignment history for a lead

---

### **Rep App Needs**

| Feature | Endpoint | Status |
|---------|----------|--------|
| Get today's appointments | `GET /api/v1/appointments?assigned_rep_id={id}&date={today}` | 🟥 Missing |
| Get contact card per appointment | `GET /api/v1/appointments/{appointment_id}` | ✅ Ready |
| Clock in/out | `POST /api/v1/reps/{rep_id}/shifts/clock-in` | ✅ Ready |
| Get shift status | `GET /api/v1/reps/{rep_id}/shifts/today` | ✅ Ready |
| Start recording | `POST /api/v1/recording-sessions/start` | ✅ Ready |
| Check recording state | `GET /api/v1/recording-sessions/{session_id}` | ✅ Ready |
| Mark appointment outcome | `PATCH /api/v1/appointments/{appointment_id}` | 🟧 Partial (deal_size not documented) |
| Provide deal size | `PATCH /api/v1/appointments/{appointment_id}` | 🟧 Partial (not explicit) |
| Toggle ghost mode | No endpoint | 🟥 Missing |

**Gaps**:
- 🟥 **No today's appointments endpoint** - Reps can't get their appointments for today
- 🟧 **Deal size input not explicit** - Schema doesn't document `deal_size` field
- 🟥 **No ghost mode toggle** - Reps can't toggle ghost mode themselves

---

### **Ask Otto Needs**

| Feature | Endpoint | Status |
|---------|----------|--------|
| Query Ask Otto | `POST /api/v1/rag/query` | ✅ Ready |
| Get query history | `GET /api/v1/rag/queries` | ✅ Ready |
| Internal AI endpoints | `/internal/ai/*` | ✅ Ready |
| RBAC enforcement | Middleware | ✅ Ready |

**Gaps**: None

---

## Backend TODO List (Prioritized)

### **🔴 Critical (Blocking Frontend Integration)**

1. **Add GET /api/v1/appointments endpoint with filtering**
   - Support `assigned_rep_id`, `date`, `status`, `outcome` query params
   - Returns `AppointmentResponse[]`
   - Used by: Rep app to see today's appointments

2. **Add Tasks CRUD endpoints**
   - `GET /api/v1/tasks?contact_card_id={id}` - List tasks for a contact
   - `GET /api/v1/tasks/{task_id}` - Get task details
   - `PATCH /api/v1/tasks/{task_id}` - Update task (mark complete, change due date, etc.)
   - `POST /api/v1/tasks` - Create manual task
   - Used by: CSR UI, Rep app

3. **Add KeySignals read/acknowledge endpoints**
   - `GET /api/v1/key-signals?contact_card_id={id}` - List signals for a contact
   - `PATCH /api/v1/key-signals/{signal_id}/acknowledge` - Acknowledge signal
   - Used by: CSR UI, Manager dashboard

4. **Extend AppointmentUpdateBody schema to explicitly include deal_size**
   - Add `deal_size: Optional[float]` field
   - Sync `Lead.deal_size` when appointment outcome = won
   - Used by: Rep app to input deal size

5. **Add GET /api/v1/leads endpoint with filtering**
   - Support `status`, `source`, `priority`, `assigned_rep_id` query params
   - Returns `LeadResponse[]`
   - Used by: CSR UI to filter leads

---

### **🟡 High Priority (Important for UX)**

6. **Add wins feed endpoint**
   - `GET /api/v1/wins?company_id={id}&limit=50` or
   - `GET /api/v1/appointments?outcome=won&status=completed&limit=50`
   - Returns closed-won appointments with deal sizes
   - Used by: Manager dashboard, wins feed

7. **Add review follow-up trigger endpoint**
   - `POST /api/v1/appointments/{appointment_id}/trigger-review`
   - Creates follow-up task or sends review request
   - Used by: Rep app, Manager dashboard

8. **Add assignment history endpoint**
   - `GET /api/v1/lead-pool/{lead_id}/assignment-history`
   - Returns `RepAssignmentHistory[]` for a lead
   - Used by: Lead Pool UI to show rep interest history

9. **Add SMS/nurture thread read endpoint**
   - `GET /api/v1/contact-cards/{contact_id}/messages`
   - Returns message thread (SMS + nurture messages)
   - Used by: CSR UI to refresh threads without fetching entire Contact Card

10. **Add ghost mode toggle endpoint for reps**
    - `PATCH /api/v1/reps/{rep_id}/recording-mode`
    - Allows reps to toggle `recording_mode` (normal/ghost/off)
    - Used by: Rep app settings

---

### **🟢 Medium Priority (Nice to Have)**

11. **Add appointment outcome update endpoint (explicit)**
    - `POST /api/v1/appointments/{appointment_id}/outcome`
    - Explicit endpoint for marking outcome + deal size
    - Used by: Rep app (clearer than PATCH)

12. **Add Contact Card refresh endpoint**
    - `POST /api/v1/contact-cards/{contact_id}/refresh`
    - Forces Contact Card assembler to rebuild (useful for testing)
    - Used by: Frontend debugging

13. **Add appointment geofence status endpoint**
    - `GET /api/v1/appointments/{appointment_id}/geofence-status`
    - Returns whether rep is within geofence, distance, etc.
    - Used by: Rep app to show geofence status

---

## Summary Table

| Phase | Feature | Endpoint(s) | Status |
|-------|---------|-------------|--------|
| **Phase 1** | CallRail webhook | `POST /callrail/call.*` | ✅ Ready |
| **Phase 1** | Shunya async pipeline | `POST /api/v1/shunya/webhook` | ✅ Ready |
| **Phase 1** | Contact Card display | `GET /api/v1/contact-cards/{id}` | ✅ Ready |
| **Phase 1** | SMS thread read | Embedded only | 🟧 Partial |
| **Phase 2** | Appointment creation | `POST /api/v1/appointments` | ✅ Ready |
| **Phase 2** | Missed call queue | `GET /api/v1/missed-calls/queue/*` | ✅ Ready |
| **Phase 3** | Lead pool list | `GET /api/v1/lead-pool` | ✅ Ready |
| **Phase 3** | Request lead | `POST /api/v1/lead-pool/{id}/request` | ✅ Ready |
| **Phase 3** | Assign lead | `POST /api/v1/lead-pool/{id}/assign` | ✅ Ready |
| **Phase 3** | Assignment history | No endpoint | 🟥 Missing |
| **Phase 4** | Clock in/out | `POST /api/v1/reps/{id}/shifts/clock-in` | ✅ Ready |
| **Phase 4** | Today's appointments | No endpoint | 🟥 Missing |
| **Phase 4** | Geofenced recording | `POST /api/v1/recording-sessions/start` | ✅ Ready |
| **Phase 4** | Ghost mode toggle | No endpoint | 🟥 Missing |
| **Phase 5** | Visit analysis | Shunya webhook | ✅ Ready |
| **Phase 5** | Appointment outcome | `PATCH /api/v1/appointments/{id}` | 🟧 Partial |
| **Phase 5** | Deal size input | Not explicit | 🟧 Partial |
| **Phase 5** | Tasks CRUD | No endpoints | 🟥 Missing |
| **Phase 5** | KeySignals acknowledge | No endpoint | 🟥 Missing |
| **Phase 5** | Wins feed | No endpoint | 🟥 Missing |
| **Phase 5** | Review follow-up | No endpoint | 🟥 Missing |
| **Phase 6** | Ask Otto query | `POST /api/v1/rag/query` | ✅ Ready |
| **Phase 6** | Internal AI endpoints | `GET /internal/ai/*` | ✅ Ready |
| **Phase 6** | RBAC enforcement | Middleware | ✅ Ready |

---

## Next Steps

1. **Immediate**: Implement critical TODOs (#1-5) to unblock frontend integration
2. **Short-term**: Implement high-priority TODOs (#6-10) for better UX
3. **Long-term**: Implement medium-priority TODOs (#11-13) for polish

**Estimated Effort**:
- Critical: 2-3 days
- High Priority: 2-3 days
- Medium Priority: 1-2 days
- **Total**: ~1 week to fully support end-to-end journey

---

**End of Audit**

