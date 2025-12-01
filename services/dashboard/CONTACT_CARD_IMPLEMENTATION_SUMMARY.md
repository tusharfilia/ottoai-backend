# Contact Card Implementation Summary

## What Was Already in Place

### ✅ Existing Models
- **ContactCard** - Basic customer identity (name, phone, email, address, metadata)
- **Lead** - Sales opportunities (status, source, priority, score, tags)
- **Appointment** - Scheduled interactions (basic fields, geofence config)
- **Call** - Call records with `text_messages` JSON field for SMS history
- **RecordingSession** - Geofenced recording with Ghost Mode support
- **RecordingTranscript** - ASR results from recording sessions
- **RecordingAnalysis** - Analysis results from recording sessions
- **CallTranscript** - ASR results from calls
- **CallAnalysis** - Analysis results from calls (objections, SOP, coaching)

### ✅ Existing Features
- Property intelligence scraper (OpenAI Chat API)
- Property snapshot storage (`property_snapshot`, `property_snapshot_raw`, `property_snapshot_updated_at`)
- Basic `ContactCardDetail` schema
- Recent calls aggregation
- Leads and appointments linked to `ContactCard`

### ✅ Shunya/UWC Integration (Data Models)
- Transcript storage (CallTranscript, RecordingTranscript)
- Analysis storage (CallAnalysis, RecordingAnalysis)
- Objection detection fields
- SOP compliance tracking fields
- Coaching tips fields
- Sentiment/engagement scores

---

## What Was Added/Extended

### 📦 New Models Created

1. **Task** (`app/models/task.py`)
   - Action items linked to ContactCard/Lead/Appointment/Call
   - Assignee (csr/rep/manager/ai)
   - Source (otto/shunya/manual)
   - Status (open/completed/overdue/cancelled)
   - Due dates, completion tracking

2. **KeySignal** (`app/models/key_signal.py`)
   - Automatic alerts/signals
   - Types: risk/opportunity/coaching/operational
   - Severity levels (low/medium/high/critical)
   - Acknowledgment tracking

3. **LeadStatusHistory** (`app/models/lead_status_history.py`)
   - Tracks adaptive lead status transitions (new → warm → hot → booked → won)
   - Records transitions: new → dormant → abandoned
   - Reason and trigger tracking

4. **RepAssignmentHistory** (`app/models/rep_assignment_history.py`)
   - Tracks rep assignment/unassignment/claims
   - Routing information (position, group, distance)
   - Assignment metadata

5. **EventLog** (`app/models/event_log.py`)
   - Chronological log of all events
   - Powers Booking Timeline (Section 5.3) and Visit Activity Timeline (Section 4.6)
   - Event types: calls, SMS, automation, appointments, rep assignments, visit/recording events

6. **SopComplianceResult** (`app/models/sop_compliance_result.py`)
   - Sales Process Checklist items
   - Individual SOP items with status (completed/missed/warning)
   - Linked to Appointment/Call/RecordingSession

### 🔧 Extended Models

1. **Lead** (`app/models/lead.py`)
   - Added `deal_status`, `deal_size`, `deal_summary`, `closed_at`
   - Added `assigned_rep_id`, `assigned_at`, `assigned_by`, `rep_claimed`
   - Added new statuses: `WARM`, `HOT`, `DORMANT`, `ABANDONED`
   - Added relationships to Task, KeySignal, LeadStatusHistory, RepAssignmentHistory, EventLog

2. **Appointment** (`app/models/appointment.py`)
   - Added `deal_size`, `material_type`, `financing_type`
   - Added `assigned_by`, `assigned_at`, `rep_claimed`
   - Added `route_position`, `route_group`, `distance_from_previous_stop`
   - Added `arrival_at`, `departure_at`, `on_site_duration`, `gps_confidence`
   - Added relationships to Task, KeySignal, SopComplianceResult, RepAssignmentHistory, EventLog

3. **ContactCard** (`app/models/contact_card.py`)
   - Added relationships to Task, KeySignal, EventLog

4. **Company** (`app/models/company.py`)
   - Added relationships to Task, KeySignal, EventLog, SopComplianceResult

### 📝 Schema Extensions

1. **Extended Schemas** (`app/schemas/domain.py`)
   - `TaskSummary`, `KeySignalSummary`, `EventLogSummary`
   - `CallSummary`, `CallTranscriptSummary`, `CallAnalysisSummary`
   - `MessageSummary`, `RecordingSessionSummary`
   - `SopComplianceItem`, `AppointmentDetailExtended`, `LeadDetailExtended`
   - `ContactCardTopSection`, `ContactCardMiddleSection`, `ContactCardBottomSection`
   - `ContactCardGlobalBlocks`
   - Extended `ContactCardDetail` with sectioned structure

2. **Contact Card Assembler** (`app/services/contact_card_assembler.py`)
   - Complete service to assemble Contact Card from all related entities
   - Builds Top Section (status, deal health, rep assignment, signals, tasks)
   - Builds Middle Section (appointment details, property, recording, SOP, timeline)
   - Builds Bottom Section (how booked, call/SMS history, timeline)
   - Builds Global Blocks (all calls, messages, automation, insights)
   - Maps Shunya/UWC outputs (transcripts, objections, SOP compliance)

3. **Route Updates** (`app/routes/contact_cards.py`)
   - Updated `get_contact_card` to use `ContactCardAssembler`
   - Updated `get_contact_card_by_phone` to use `ContactCardAssembler`

### 🗄️ Database Updates

1. **Database Registration** (`app/database.py`)
   - Added new models to `init_db` imports
   - Added new models to table creation loop

---

## Final ContactCardDetail JSON Shape

### Structure Overview

```json
{
  // ContactCardBase fields (Section 1)
  "id": "uuid",
  "company_id": "string",
  "primary_phone": "string",
  "secondary_phone": "string | null",
  "email": "string | null",
  "first_name": "string | null",
  "last_name": "string | null",
  "address": "string | null",
  "city": "string | null",
  "state": "string | null",
  "postal_code": "string | null",
  "metadata": "object | null",
  "property_snapshot": "object | null",
  "created_at": "datetime",
  "updated_at": "datetime",
  "full_name": "string | null",
  
  // TOP SECTION - Current Status & Priority (Section 3)
  "top_section": {
    // Customer Snapshot (3.1)
    "lead_source": "string | null",
    "lead_age_days": "number | null",
    "last_activity_at": "datetime | null",
    
    // Deal Status (3.2)
    "deal_status": "string | null",
    "deal_size": "number | null",
    "deal_summary": "string | null",
    "closed_at": "datetime | null",
    
    // Rep Assignment (3.3)
    "assigned_rep_id": "string | null",
    "assigned_rep_name": "string | null",
    "assigned_at": "datetime | null",
    "rep_claimed": "boolean",
    "route_position": "number | null",
    "route_group": "string | null",
    "distance_from_previous_stop": "number | null",
    
    // Tasks (3.5)
    "tasks": [
      {
        "id": "uuid",
        "description": "string",
        "assigned_to": "csr|rep|manager|ai",
        "source": "otto|shunya|manual",
        "due_at": "datetime | null",
        "status": "open|completed|overdue|cancelled",
        "completed_at": "datetime | null",
        "priority": "string | null",
        "created_at": "datetime"
      }
    ],
    
    // Key Signals (3.6)
    "key_signals": [
      {
        "id": "uuid",
        "signal_type": "risk|opportunity|coaching|operational",
        "severity": "low|medium|high|critical",
        "title": "string",
        "description": "string | null",
        "acknowledged": "boolean",
        "created_at": "datetime"
      }
    ]
  },
  
  // MIDDLE SECTION - Sales Appointment & Performance (Section 4)
  // Only appears after booking
  "middle_section": {
    // Appointment Header (4.1)
    "active_appointment": {
      "id": "uuid",
      "lead_id": "uuid",
      "contact_card_id": "uuid",
      "company_id": "string",
      "assigned_rep_id": "string | null",
      "assigned_rep_name": "string | null",
      "scheduled_start": "datetime",
      "scheduled_end": "datetime | null",
      "status": "scheduled|confirmed|completed|cancelled|no_show",
      "outcome": "pending|won|lost|no_show|rescheduled",
      "location": "string | null",
      "service_type": "string | null",
      "notes": "string | null",
      "external_id": "string | null",
      "deal_size": "number | null",
      "material_type": "string | null",
      "financing_type": "string | null",
      "assigned_at": "datetime | null",
      "rep_claimed": "boolean",
      "route_position": "number | null",
      "route_group": "string | null",
      "arrival_at": "datetime | null",
      "departure_at": "datetime | null",
      "on_site_duration": "number | null",
      "recording_sessions": [...],
      "sop_compliance": [...],
      "created_at": "datetime",
      "updated_at": "datetime"
    },
    
    // Property Intelligence (4.2)
    "property_intelligence": {
      "roof_type": "string | null",
      "square_feet": "number | null",
      "stories": "number | null",
      "year_built": "number | null",
      "access_notes": "string | null",
      "solar": "string | null",
      "hoa": "string | null",
      "subdivision": "string | null",
      "last_sale_date": "string | null",
      "last_sale_price": "string | null",
      "est_value_range": "string | null",
      "potential_equity": "string | null",
      "is_for_sale": "string | null",
      "sources": ["string"],
      "google_earth_url": "string | null",
      "updated_at": "datetime | null"
    },
    
    // SOP Compliance (4.5)
    "sop_compliance": [
      {
        "checklist_item": "greeting|building_rapport|understanding_needs|...",
        "status": "completed|missed|warning",
        "notes": "string | null",
        "timestamp": "datetime | null"
      }
    ],
    
    // Visit Activity Timeline (4.6)
    "visit_timeline": [
      {
        "id": "uuid",
        "event_type": "rep_en_route|rep_arrived|recording_started|...",
        "timestamp": "datetime",
        "description": "string | null",
        "actor_role": "string | null",
        "metadata": "object | null"
      }
    ],
    
    // Recording Sessions (4.8)
    "recording_sessions": [
      {
        "id": "uuid",
        "appointment_id": "uuid",
        "started_at": "datetime",
        "ended_at": "datetime | null",
        "duration_seconds": "number | null",
        "mode": "normal|ghost",
        "audio_url": "string | null",  // Null in Ghost Mode
        "transcription_status": "not_started|in_progress|completed|failed",
        "analysis_status": "not_started|in_progress|completed|failed",
        "outcome_classification": "string | null",
        "sentiment_score": "number | null"
      }
    ],
    
    // Tasks (4.9)
    "appointment_tasks": [...],  // Same as tasks in top_section
    
    // Escalation Warnings (4.10)
    "escalation_warnings": ["string"],
    
    // Transcript Intelligence (4.11)
    "transcript_intelligence": {
      "id": "uuid",
      "objections": ["string"],
      "objection_details": [{"type": "string", "timestamp": "number", "quote": "string", "resolved": "boolean"}],
      "sentiment_score": "number | null",
      "engagement_score": "number | null",
      "coaching_tips": [{"tip": "string", "priority": "string", "category": "string"}],
      "sop_stages_completed": ["string"],
      "sop_stages_missed": ["string"],
      "sop_compliance_score": "number | null",
      "rehash_score": "number | null",
      "lead_quality": "string | null",
      "conversion_probability": "number | null",
      "analyzed_at": "datetime | null"
    }
  },
  
  // BOTTOM SECTION - How Customer Was Booked (Section 5)
  "bottom_section": {
    // Narrative Summary (5.1)
    "narrative_summary": "string | null",
    
    // Booking Risk/Context Chips (5.2)
    "booking_chips": [
      {
        "label": "string",
        "severity": "low|medium|high",
        "metadata": "object"
      }
    ],
    
    // Call Recordings (5.3 Tab 1)
    "call_recordings": [
      {
        "call_id": "number",
        "phone_number": "string",
        "direction": "string",
        "missed_call": "boolean",
        "booked": "boolean",
        "bought": "boolean",
        "created_at": "datetime",
        "duration_seconds": "number | null",
        "transcript": {
          "id": "uuid",
          "transcript_text": "string | null",
          "confidence_score": "number | null",
          "word_count": "number | null",
          "created_at": "datetime"
        } | null,
        "analysis": {
          "id": "uuid",
          "objections": ["string"],
          "objection_details": [...],
          "sentiment_score": "number | null",
          "coaching_tips": [...],
          "sop_stages_completed": ["string"],
          "sop_stages_missed": ["string"],
          "sop_compliance_score": "number | null",
          "analyzed_at": "datetime | null"
        } | null,
        "recording_url": "string | null"
      }
    ],
    
    // Text Messages (5.3 Tab 2)
    "text_messages": [
      {
        "timestamp": "datetime",
        "sender": "string",
        "role": "customer|csr|otto|rep",
        "body": "string",
        "direction": "inbound|outbound",
        "type": "manual|automated",
        "message_sid": "string | null"
      }
    ],
    
    // Booking Timeline (5.3 Tab 3)
    "booking_timeline": [
      {
        "id": "uuid",
        "event_type": "call_received|sms_sent|automation_nurture|appointment_created|...",
        "timestamp": "datetime",
        "description": "string | null",
        "actor_role": "string | null",
        "metadata": "object | null"
      }
    ]
  },
  
  // GLOBAL BLOCKS - Shared Across All Sections (Section 6)
  "global_blocks": {
    // Calls (6.1)
    "all_calls": [...],  // Simplified call summaries (limit 20)
    
    // Messages (6.2)
    "all_messages": [...],  // All SMS messages (limit 50)
    
    // Automation Events (6.3)
    "automation_events": [
      {
        "id": "uuid",
        "event_type": "automation_nurture|automation_followup|automation_scheduled|...",
        "timestamp": "datetime",
        "description": "string | null",
        "actor_role": "string | null",
        "metadata": "object | null"
      }
    ],
    
    // Pending Action Items (6.5)
    "pending_actions": [...],  // Tasks with status=open
    
    // AI Insights (6.6)
    "ai_insights": {
      "missed_opportunities": [],
      "sop_compliance_score": "number | null",
      "objection_clusters": {"objection_type": "count"},
      "buying_signals": ["string"],
      "deal_risk_score": "low|medium|high",
      "suggested_next_actions": []
    }
  },
  
  // Backward compatibility fields
  "property_intelligence": {...},  // Also in middle_section
  "leads": [...],
  "appointments": [...],
  "recent_call_ids": [1, 2, 3, ...]
}
```

---

## Example Payloads

### Example 1: New, Qualified, Not-Yet-Booked Contact

```json
{
  "id": "contact-123",
  "company_id": "company-456",
  "primary_phone": "+1234567890",
  "first_name": "John",
  "last_name": "Doe",
  "email": "john.doe@example.com",
  "address": "123 Main St, Austin, TX 78701",
  "full_name": "John Doe",
  
  "top_section": {
    "lead_source": "inbound_call",
    "lead_age_days": 2,
    "last_activity_at": "2025-11-15T10:30:00Z",
    "deal_status": "nurturing",
    "deal_size": null,
    "assigned_rep_id": null,
    "rep_claimed": false,
    "tasks": [
      {
        "id": "task-789",
        "description": "Follow up at 5pm",
        "assigned_to": "rep",
        "source": "shunya",
        "due_at": "2025-11-15T17:00:00Z",
        "status": "open",
        "priority": "high"
      }
    ],
    "key_signals": [
      {
        "id": "signal-101",
        "signal_type": "opportunity",
        "severity": "medium",
        "title": "High likelihood of closing",
        "acknowledged": false
      }
    ]
  },
  
  "middle_section": null,  // No appointment yet
  
  "bottom_section": {
    "narrative_summary": "Customer reached out via phone call. Initial call was missed. Otto automation initiated nurture sequence.",
    "booking_chips": [
      {"label": "Missed initial call", "severity": "medium"},
      {"label": "Otto booked majority", "severity": "low", "metadata": {"automation_count": 3}}
    ],
    "call_recordings": [
      {
        "call_id": 1001,
        "phone_number": "+1234567890",
        "missed_call": true,
        "booked": false,
        "created_at": "2025-11-13T08:15:00Z",
        "analysis": {
          "objections": [],
          "sentiment_score": null
        }
      }
    ],
    "text_messages": [
      {
        "timestamp": "2025-11-13T08:20:00Z",
        "sender": "+1234567890",
        "role": "customer",
        "body": "I need a roof quote",
        "direction": "inbound",
        "type": "manual"
      },
      {
        "timestamp": "2025-11-13T08:21:00Z",
        "sender": "otto",
        "role": "otto",
        "body": "Thanks for reaching out! We'll connect you with a specialist.",
        "direction": "outbound",
        "type": "automated"
      }
    ],
    "booking_timeline": [
      {
        "event_type": "call_missed",
        "timestamp": "2025-11-13T08:15:00Z",
        "actor_role": "system"
      },
      {
        "event_type": "sms_received",
        "timestamp": "2025-11-13T08:20:00Z",
        "actor_role": "customer"
      },
      {
        "event_type": "automation_nurture",
        "timestamp": "2025-11-13T08:21:00Z",
        "actor_role": "ai"
      }
    ]
  },
  
  "global_blocks": {
    "all_calls": [...],
    "all_messages": [...],
    "automation_events": [...],
    "pending_actions": [...],
    "ai_insights": {
      "sop_compliance_score": null,
      "objection_clusters": {},
      "buying_signals": [],
      "deal_risk_score": "low"
    }
  },
  
  "property_intelligence": null,
  "leads": [...],
  "appointments": [],
  "recent_call_ids": [1001]
}
```

### Example 2: Active Appointment with Recording + Property Intelligence

```json
{
  "id": "contact-123",
  "company_id": "company-456",
  "primary_phone": "+1234567890",
  "first_name": "John",
  "last_name": "Doe",
  "address": "123 Main St, Austin, TX 78701",
  "full_name": "John Doe",
  
  "top_section": {
    "lead_source": "inbound_call",
    "lead_age_days": 5,
    "last_activity_at": "2025-11-16T14:30:00Z",
    "deal_status": "booked",
    "deal_size": 15000.0,
    "assigned_rep_id": "rep-789",
    "assigned_rep_name": "Jane Smith",
    "assigned_at": "2025-11-14T10:00:00Z",
    "rep_claimed": true,
    "route_position": 2,
    "route_group": "north_route",
    "distance_from_previous_stop": 1.5,
    "tasks": [...],
    "key_signals": [...]
  },
  
  "middle_section": {
    "active_appointment": {
      "id": "apt-456",
      "scheduled_start": "2025-11-17T10:00:00Z",
      "scheduled_end": "2025-11-17T11:30:00Z",
      "status": "confirmed",
      "outcome": "pending",
      "location": "123 Main St, Austin, TX 78701",
      "assigned_rep_name": "Jane Smith",
      "deal_size": 15000.0,
      "material_type": "Asphalt Shingle",
      "financing_type": "Cash",
      "arrival_at": null,
      "departure_at": null,
      "recording_sessions": [],
      "sop_compliance": []
    },
    
    "property_intelligence": {
      "roof_type": "Asphalt Shingle",
      "square_feet": 2100,
      "stories": 2,
      "year_built": 1998,
      "hoa": "Yes",
      "subdivision": "Cedar Ridge",
      "last_sale_date": "2021-06-15",
      "last_sale_price": "$310,000",
      "est_value_range": "$520,000 – $570,000",
      "potential_equity": "$210,000 – $260,000",
      "is_for_sale": "No",
      "sources": ["Zillow", "Redfin"],
      "google_earth_url": "https://earth.google.com/web/...",
      "updated_at": "2025-11-15T09:00:00Z"
    },
    
    "sop_compliance": [],
    "visit_timeline": [],
    "recording_sessions": [],
    "appointment_tasks": [],
    "escalation_warnings": [],
    "transcript_intelligence": null
  },
  
  "bottom_section": {
    "narrative_summary": "Customer reached out via phone call. Appointment scheduled for November 17, 2025 at 10:00 AM. Assigned to sales rep.",
    "booking_chips": [
      {"label": "High responsiveness", "severity": "low"},
      {"label": "Otto booked majority", "severity": "low"}
    ],
    "call_recordings": [...],
    "text_messages": [...],
    "booking_timeline": [
      {
        "event_type": "call_completed",
        "timestamp": "2025-11-14T09:00:00Z",
        "actor_role": "customer"
      },
      {
        "event_type": "appointment_created",
        "timestamp": "2025-11-14T09:05:00Z",
        "actor_role": "csr"
      },
      {
        "event_type": "rep_assigned",
        "timestamp": "2025-11-14T10:00:00Z",
        "actor_role": "manager"
      },
      {
        "event_type": "rep_claimed",
        "timestamp": "2025-11-14T10:15:00Z",
        "actor_role": "rep"
      }
    ]
  },
  
  "global_blocks": {...}
}
```

### Example 3: Closed-Won Deal with Full Booking + Appointment + Review Data

```json
{
  "id": "contact-123",
  "company_id": "company-456",
  "primary_phone": "+1234567890",
  "first_name": "John",
  "last_name": "Doe",
  "address": "123 Main St, Austin, TX 78701",
  "full_name": "John Doe",
  
  "top_section": {
    "lead_source": "inbound_call",
    "lead_age_days": 30,
    "last_activity_at": "2025-11-20T16:00:00Z",
    "deal_status": "won",
    "deal_size": 18000.0,
    "deal_summary": "Roof replacement - Asphalt shingle, 2100 sq ft",
    "closed_at": "2025-11-18T15:30:00Z",
    "assigned_rep_id": "rep-789",
    "assigned_rep_name": "Jane Smith",
    "assigned_at": "2025-11-14T10:00:00Z",
    "rep_claimed": true,
    "tasks": [],
    "key_signals": []
  },
  
  "middle_section": {
    "active_appointment": {
      "id": "apt-456",
      "scheduled_start": "2025-11-17T10:00:00Z",
      "scheduled_end": "2025-11-17T11:30:00Z",
      "status": "completed",
      "outcome": "won",
      "location": "123 Main St, Austin, TX 78701",
      "assigned_rep_name": "Jane Smith",
      "deal_size": 18000.0,
      "material_type": "Asphalt Shingle",
      "financing_type": "Cash",
      "arrival_at": "2025-11-17T09:58:00Z",
      "departure_at": "2025-11-17T12:05:00Z",
      "on_site_duration": 127,
      "recording_sessions": [
        {
          "id": "session-789",
          "appointment_id": "apt-456",
          "started_at": "2025-11-17T09:58:00Z",
          "ended_at": "2025-11-17T12:05:00Z",
          "duration_seconds": 7620,
          "mode": "normal",
          "audio_url": "https://s3.amazonaws.com/...",
          "transcription_status": "completed",
          "analysis_status": "completed",
          "outcome_classification": "won",
          "sentiment_score": 0.85
        }
      ],
      "sop_compliance": [
        {"checklist_item": "greeting", "status": "completed", "timestamp": "2025-11-17T10:00:00Z"},
        {"checklist_item": "building_rapport", "status": "completed", "timestamp": "2025-11-17T10:05:00Z"},
        {"checklist_item": "understanding_needs", "status": "completed", "timestamp": "2025-11-17T10:15:00Z"},
        {"checklist_item": "inspecting_roof", "status": "completed", "timestamp": "2025-11-17T10:30:00Z"},
        {"checklist_item": "taking_photos", "status": "completed", "timestamp": "2025-11-17T10:45:00Z"},
        {"checklist_item": "presenting_estimate", "status": "completed", "timestamp": "2025-11-17T11:00:00Z"},
        {"checklist_item": "explaining_warranty", "status": "completed", "timestamp": "2025-11-17T11:10:00Z"},
        {"checklist_item": "reviewing_price", "status": "completed", "timestamp": "2025-11-17T11:15:00Z"},
        {"checklist_item": "discussing_financing", "status": "completed", "timestamp": "2025-11-17T11:20:00Z"},
        {"checklist_item": "closing_attempt", "status": "completed", "timestamp": "2025-11-17T11:25:00Z"},
        {"checklist_item": "next_steps_given", "status": "completed", "timestamp": "2025-11-17T11:30:00Z"}
      ]
    },
    
    "property_intelligence": {
      "roof_type": "Asphalt Shingle",
      "square_feet": 2100,
      "stories": 2,
      "year_built": 1998,
      "hoa": "Yes",
      "subdivision": "Cedar Ridge",
      "last_sale_price": "$310,000",
      "est_value_range": "$520,000 – $570,000",
      "potential_equity": "$210,000 – $260,000",
      "sources": ["Zillow", "Redfin"],
      "updated_at": "2025-11-15T09:00:00Z"
    },
    
    "visit_timeline": [
      {
        "event_type": "rep_en_route",
        "timestamp": "2025-11-17T09:30:00Z",
        "actor_role": "rep"
      },
      {
        "event_type": "rep_arrived",
        "timestamp": "2025-11-17T09:58:00Z",
        "actor_role": "system"
      },
      {
        "event_type": "recording_started",
        "timestamp": "2025-11-17T09:58:15Z",
        "actor_role": "system"
      },
      {
        "event_type": "inspection_milestone",
        "timestamp": "2025-11-17T10:30:00Z",
        "actor_role": "rep",
        "metadata": {"milestone": "roof_inspection_complete"}
      },
      {
        "event_type": "decision_moment",
        "timestamp": "2025-11-17T11:25:00Z",
        "actor_role": "customer",
        "metadata": {"decision": "accepted_estimate"}
      },
      {
        "event_type": "recording_ended",
        "timestamp": "2025-11-17T12:05:00Z",
        "actor_role": "system"
      },
      {
        "event_type": "rep_departed",
        "timestamp": "2025-11-17T12:05:30Z",
        "actor_role": "system"
      },
      {
        "event_type": "appointment_outcome",
        "timestamp": "2025-11-17T12:10:00Z",
        "actor_role": "rep",
        "metadata": {"outcome": "won", "deal_size": 18000.0}
      }
    ],
    
    "transcript_intelligence": {
      "objections": ["price"],
      "objection_details": [
        {
          "type": "price",
          "timestamp": 3420.5,
          "quote": "That's a bit high for me",
          "resolved": true
        }
      ],
      "sentiment_score": 0.85,
      "engagement_score": 0.92,
      "coaching_tips": [
        {
          "tip": "Excellent job addressing price objection with value proposition",
          "priority": "low",
          "category": "objection_handling"
        }
      ],
      "sop_stages_completed": ["connect", "agenda", "assess", "report", "present", "close"],
      "sop_stages_missed": [],
      "sop_compliance_score": 9.5,
      "lead_quality": "hot",
      "conversion_probability": 0.95
    },
    
    "escalation_warnings": []
  },
  
  "bottom_section": {
    "narrative_summary": "Customer reached out via phone call. Initial call was missed. Otto automation initiated nurture sequence. Appointment scheduled for November 17, 2025 at 10:00 AM. Assigned to sales rep. Rep completed full SOP checklist and closed deal successfully.",
    "booking_chips": [
      {"label": "Missed initial call", "severity": "medium"},
      {"label": "High responsiveness", "severity": "low"},
      {"label": "Otto booked majority", "severity": "low"}
    ],
    "call_recordings": [
      {
        "call_id": 1001,
        "missed_call": true,
        "booked": true,
        "analysis": {
          "objections": [],
          "sentiment_score": 0.7
        }
      }
    ],
    "text_messages": [...],
    "booking_timeline": [
      {"event_type": "call_missed", "timestamp": "2025-11-13T08:15:00Z"},
      {"event_type": "sms_received", "timestamp": "2025-11-13T08:20:00Z"},
      {"event_type": "automation_nurture", "timestamp": "2025-11-13T08:21:00Z"},
      {"event_type": "appointment_created", "timestamp": "2025-11-14T09:05:00Z"},
      {"event_type": "rep_assigned", "timestamp": "2025-11-14T10:00:00Z"},
      {"event_type": "appointment_confirmed", "timestamp": "2025-11-15T14:00:00Z"},
      {"event_type": "rep_arrived", "timestamp": "2025-11-17T09:58:00Z"},
      {"event_type": "recording_started", "timestamp": "2025-11-17T09:58:15Z"},
      {"event_type": "appointment_outcome", "timestamp": "2025-11-17T12:10:00Z"},
      {"event_type": "deal_won", "timestamp": "2025-11-18T15:30:00Z"}
    ]
  },
  
  "global_blocks": {
    "ai_insights": {
      "sop_compliance_score": 9.5,
      "objection_clusters": {"price": 1},
      "buying_signals": ["High conversion probability", "High engagement"],
      "deal_risk_score": "low"
    }
  }
}
```

---

## Files Created/Modified

### New Files Created
1. `app/models/task.py`
2. `app/models/key_signal.py`
3. `app/models/lead_status_history.py`
4. `app/models/rep_assignment_history.py`
5. `app/models/event_log.py`
6. `app/models/sop_compliance_result.py`
7. `app/services/contact_card_assembler.py`
8. `CONTACT_CARD_AUDIT.md`
9. `CONTACT_CARD_IMPLEMENTATION_SUMMARY.md` (this file)

### Modified Files
1. `app/models/lead.py` - Added deal fields, rep assignment, new statuses, relationships
2. `app/models/appointment.py` - Added deal info, rep assignment, geofence events, relationships
3. `app/models/contact_card.py` - Added relationships
4. `app/models/company.py` - Added relationships
5. `app/schemas/domain.py` - Extended with new schemas and sectioned ContactCardDetail
6. `app/routes/contact_cards.py` - Updated to use ContactCardAssembler
7. `app/database.py` - Added new models to init_db

---

## Next Steps

### Immediate (Critical)
1. ✅ Create Alembic migration for all new models and extended fields
2. ✅ Test ContactCard assembler with real data
3. ✅ Add event emission for new entities (Task, KeySignal, EventLog creation)
4. ✅ Update @ottoai/types package with extended ContactCardDetail schema

### Important (High Priority)
1. Implement adaptive lead status engine (auto-adjust status based on behavior)
2. Generate narrative summaries using AI (currently basic text generation)
3. Populate KeySignals automatically from business rules
4. Add rep interest tracking (reps who requested the lead)
5. Complete Shunya/UWC integration (map all outputs to ContactCard)

### Nice-to-Have
1. Add caching layer for ContactCard responses
2. Optimize queries (reduce N+1 queries)
3. Add pagination for large lists (calls, messages, events)
4. Generate AI insights using aggregated analysis
5. Add review workflow tracking

---

## Notes

- All changes are **backwards-compatible** - existing flat fields are preserved
- Frontend can consume either sectioned structure (`top_section`, `middle_section`, `bottom_section`) or flat fields
- Middle section is only populated after an appointment is booked
- Shunya/UWC outputs are mapped from existing CallAnalysis and RecordingAnalysis models
- SMS history is extracted from `Call.text_messages` JSON field (already exists)
- Property intelligence is already implemented and working
- All new models follow existing patterns and include proper indexes



