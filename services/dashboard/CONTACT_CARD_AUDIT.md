# Contact Card Implementation Audit

## What Exists (Already Implemented)

### ✅ Models
- **ContactCard** - Basic customer identity fields
- **Lead** - Status, source, campaign, priority, score, tags
- **Appointment** - Basic appointment fields with geofence config
- **Call** - Full call model with text_messages JSON field
- **RecordingSession** - Geofenced recording with Ghost Mode support
- **RecordingTranscript** - ASR results from recording sessions
- **RecordingAnalysis** - Analysis results from recording sessions
- **CallTranscript** - ASR results from calls
- **CallAnalysis** - Analysis results from calls (objections, SOP, coaching)
- **FollowUpDraft** - AI-generated follow-ups
- **MissedCallQueue** - Automation tracking

### ✅ Features
- Property intelligence scraper (OpenAI Chat API)
- Property snapshot storage (property_snapshot, property_snapshot_raw)
- Basic ContactCardDetail schema
- Recent calls aggregation
- Leads and appointments linked to ContactCard

### ✅ Shunya/UWC Integration
- Transcript storage (CallTranscript, RecordingTranscript)
- Analysis storage (CallAnalysis, RecordingAnalysis)
- Objection detection
- SOP compliance tracking
- Coaching tips
- Sentiment scores

## What's Missing (Per Spec)

### ❌ Top Section - Missing Fields
1. **Customer Snapshot:**
   - `lead_age` (computed from lead.created_at)
   - `last_activity_at` (computed from max of all activities)

2. **Deal Status:**
   - `deal_status` enum (new/nurturing/booked/no-show/rescheduled/in-progress/won/lost)
   - `deal_size`, `deal_summary`, `closed_at` on Lead or Appointment

3. **Rep Assignment:**
   - `assigned_rep_name` (join to SalesRep)
   - `assigned_at` timestamp
   - `claimed` boolean flag
   - `route_position`, `route_group`, `distance_from_previous_stop`

4. **Adaptive Lead Status Engine:**
   - Additional statuses: warm, hot, dormant, abandoned
   - **LeadStatusHistory** model (new)
   - Auto-adjustment logic

5. **Tasks:**
   - **Task** model (separate from FollowUpDraft)
   - Task assignment (csr/rep/manager/ai)
   - Task source (otto/shunya/manual)
   - Due dates, completion tracking

6. **Key Signals:**
   - **KeySignal** model (new)
   - Risk/opportunity/coaching/operational alerts
   - Auto-generation triggers

### ❌ Middle Section - Missing Fields
1. **Appointment Deal Info:**
   - `deal_size_estimate` (Float)
   - `material_type` (String)
   - `financing_type` (String)

2. **SOP Compliance Checklist:**
   - Separate **SopComplianceResult** model (new)
   - Individual checklist items with status (completed/missed/warning)
   - Link to Appointment

3. **Visit Activity Timeline:**
   - **EventLog** model (new) with event_type enum
   - Rep en route, arrived, recording started, milestones, etc.

4. **Geofence Events:**
   - `arrival_at`, `departure_at` on Appointment
   - `on_site_duration` (computed)

5. **Rep Interest:**
   - Reps who requested the lead
   - **RepAssignmentHistory** model (new)

6. **Escalation Warnings:**
   - Flags on Appointment or separate model

### ❌ Bottom Section - Missing Models
1. **Narrative Summary:**
   - Generated text field (computed or stored)

2. **Booking Risk/Context Chips:**
   - **BookingContextChip** model (new) or JSON on Lead

3. **Booking Timeline:**
   - **EventLog** model (shared with Visit Timeline)
   - Chronological log of all events

### ❌ Global Blocks - Missing Models
1. **MessageThread:**
   - Separate model for SMS history (or enhance Call.text_messages)
   - Message-level metadata (sender role, type, direction)

2. **AutomationThread:**
   - Track automation events (missed call nurture, follow-ups, etc.)
   - Link to ContactCard/Lead

3. **ObjectionTag:**
   - Separate model or use existing CallAnalysis.objections

4. **KeyMoment:**
   - Timestamps for key events (objection, decision, etc.)
   - Link to transcripts

5. **AI Insights:**
   - Aggregated insights across all calls/recordings
   - Missed opportunities, buying signals, deal risk

## Implementation Plan

### Phase 1: Extend Existing Models (Backwards Compatible)
1. Add missing fields to Lead model
2. Add missing fields to Appointment model
3. Add computed fields to ContactCard (lead_age, last_activity_at)

### Phase 2: Create New Models
1. Task model
2. KeySignal model
3. LeadStatusHistory model
4. RepAssignmentHistory model
5. EventLog model
6. SopComplianceResult model
7. BookingContextChip model (or JSON on Lead)
8. MessageThread model (or enhance Call.text_messages)

### Phase 3: Update ContactCard Assembler
1. Build Top Section (status, deal health, rep assignment, signals, tasks)
2. Build Middle Section (appointment details, property, recording, SOP, timeline)
3. Build Bottom Section (how booked, call/SMS history, timeline)
4. Include Global Blocks (all calls, messages, automation, insights)

### Phase 4: Map Shunya/UWC Outputs
1. Ensure all transcripts map to ContactCard
2. Ensure all analyses map to ContactCard
3. Extract objections, SOP compliance, coaching tips
4. Generate narrative summaries

### Phase 5: Event Emission
1. Emit events for all ContactCard updates
2. Ensure real-time updates trigger







