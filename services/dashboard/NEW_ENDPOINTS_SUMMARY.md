# New Endpoints Implementation Summary

**Date**: 2025-11-24  
**Purpose**: Summary of all new endpoints implemented for frontend integration

---

## 📋 **Overview**

Implemented **9 new endpoint groups** with **20+ endpoints** total to support the end-to-end user journey:

1. ✅ Appointments listing (Today's Appointments for Reps)
2. ✅ Tasks CRUD (4 endpoints)
3. ✅ KeySignals list + acknowledge (2 endpoints)
4. ✅ Appointment deal_size extension
5. ✅ Lead listing with filters
6. ✅ SMS thread read
7. ✅ Ghost mode toggle & status (2 endpoints)
8. ✅ Wins feed
9. ✅ Review follow-up trigger

---

## 🆕 **New Endpoints**

### **1. Appointments - Today's Appointments**

**Endpoint**: `GET /api/v1/appointments`

**Query Parameters**:
- `rep_id` (optional) - Sales rep ID (defaults to authenticated user if rep)
- `date` (optional) - Date filter (YYYY-MM-DD, defaults to today)
- `status` (optional) - Filter by status (scheduled, confirmed, completed, cancelled, no_show)
- `outcome` (optional) - Filter by outcome (pending, won, lost, no_show, rescheduled)

**Response**:
```json
{
  "success": true,
  "data": {
    "appointments": [
      {
        "appointment_id": "uuid",
        "lead_id": "uuid",
        "contact_card_id": "uuid",
        "customer_name": "John Doe",
        "address": "123 Main St",
        "scheduled_start": "2025-11-24T10:00:00Z",
        "scheduled_end": "2025-11-24T11:00:00Z",
        "status": "scheduled",
        "outcome": "pending",
        "service_type": "roofing",
        "is_assigned_to_me": true,
        "deal_size": null,
        "pending_tasks_count": 2
      }
    ],
    "total": 5,
    "date": "2025-11-24"
  }
}
```

**Features**:
- Auto-detects rep_id from auth context for sales_rep role
- Filters by date (defaults to today in UTC)
- Includes pending tasks count
- Multi-tenant scoped

---

### **2. Tasks CRUD**

#### **GET /api/v1/tasks**

**Query Parameters**:
- `assignee_id` (optional) - Filter by assignee user ID
- `lead_id` (optional) - Filter by lead ID
- `contact_card_id` (optional) - Filter by contact card ID
- `status` (optional) - Filter by status (open, completed, overdue, cancelled)
- `overdue` (optional boolean) - Filter by overdue status
- `due_before` (optional datetime) - Filter tasks due before this date
- `due_after` (optional datetime) - Filter tasks due after this date

**Response**:
```json
{
  "success": true,
  "data": {
    "tasks": [
      {
        "id": "uuid",
        "description": "Follow up at 5pm",
        "assigned_to": "csr",
        "source": "shunya",
        "due_at": "2025-11-24T17:00:00Z",
        "status": "open",
        "priority": "high",
        "contact_card_id": "uuid",
        "lead_id": "uuid"
      }
    ],
    "total": 10,
    "overdue_count": 2
  }
}
```

#### **PATCH /api/v1/tasks/{task_id}**

**Request Body**:
```json
{
  "status": "completed",
  "due_at": "2025-11-25T17:00:00Z",
  "assigned_to": "rep",
  "description": "Updated description",
  "priority": "medium",
  "notes": "Additional notes"
}
```

**Response**: Updated `TaskSummary`

**Events**: `task.updated`

#### **POST /api/v1/tasks/{task_id}/complete**

**Response**: Completed `TaskSummary`

**Events**: `task.completed`

#### **DELETE /api/v1/tasks/{task_id}**

**Response**: `{"status": "deleted", "task_id": "uuid"}`

**Events**: `task.deleted`

#### **POST /api/v1/tasks**

**Request Body**:
```json
{
  "description": "Follow up with customer",
  "assigned_to": "csr",
  "contact_card_id": "uuid",
  "lead_id": "uuid",
  "appointment_id": "uuid",
  "call_id": 123,
  "due_at": "2025-11-25T17:00:00Z",
  "priority": "high",
  "source": "manual"
}
```

**Response**: Created `TaskSummary`

**Events**: `task.created`

**Features**:
- Auto-marks tasks as OVERDUE if due_at < now and status not completed/cancelled
- Soft delete (marks as cancelled)
- Stores notes in task_metadata JSON field

---

### **3. KeySignals List + Acknowledge**

#### **GET /api/v1/key-signals**

**Query Parameters**:
- `lead_id` (optional) - Filter by lead ID
- `appointment_id` (optional) - Filter by appointment ID
- `contact_card_id` (optional) - Filter by contact card ID
- `signal_type` (optional) - Filter by type (risk, opportunity, coaching, operational)
- `acknowledged` (optional boolean) - Filter by acknowledged status
- `created_after` (optional datetime) - Filter signals created after this date
- `created_before` (optional datetime) - Filter signals created before this date

**Response**:
```json
{
  "success": true,
  "data": {
    "signals": [
      {
        "id": "uuid",
        "signal_type": "risk",
        "title": "Rep late to appointment",
        "description": "Rep arrived 15 minutes late",
        "severity": "high",
        "acknowledged": false,
        "contact_card_id": "uuid",
        "lead_id": "uuid",
        "created_at": "2025-11-24T10:00:00Z"
      }
    ],
    "total": 5,
    "unacknowledged_count": 3
  }
}
```

#### **POST /api/v1/key-signals/{signal_id}/acknowledge**

**Response**: Acknowledged `KeySignalSummary`

**Events**: `key_signal.acknowledged`

**Features**:
- Idempotent (can call multiple times safely)
- Sets `acknowledged_at` and `acknowledged_by` from auth context
- Ordered by severity (critical first), then created_at (newest first)

---

### **4. Appointment Deal Size Extension**

**Updated Endpoint**: `PATCH /api/v1/appointments/{appointment_id}`

**New Field in Request Body**:
```json
{
  "outcome": "won",
  "deal_size": 35000.0
}
```

**Behavior**:
- When `outcome = "won"` and `deal_size` is provided:
  - Updates `Appointment.deal_size`
  - Syncs `Lead.deal_size`
  - Updates `Lead.deal_status = "won"`
  - Updates `Lead.status = CLOSED_WON` (if not already)
  - Sets `Lead.closed_at = now`
  - Updates `Appointment.status = COMPLETED`

**Response**: Updated `AppointmentResponse` with `deal_size` field

---

### **5. Lead Listing**

**Endpoint**: `GET /api/v1/leads`

**Query Parameters**:
- `status` (optional) - Filter by status (comma-separated for multiple: `new,qualified_booked`)
- `rep_id` (optional) - Filter by assigned rep ID
- `source` (optional) - Filter by source (inbound_call, web_form, referral, etc.)
- `date_from` (optional datetime) - Filter leads created after this date
- `date_to` (optional datetime) - Filter leads created before this date
- `search` (optional string) - Search by name or phone number
- `limit` (optional, default 50, max 200) - Maximum results
- `offset` (optional, default 0) - Pagination offset

**Response**:
```json
{
  "success": true,
  "data": {
    "leads": [
      {
        "lead_id": "uuid",
        "status": "qualified_booked",
        "source": "inbound_call",
        "priority": "high",
        "score": 85,
        "last_contacted_at": "2025-11-24T10:00:00Z",
        "contact": {
          "name": "John Doe",
          "primary_phone": "+12025551234",
          "city": "Phoenix",
          "state": "AZ"
        },
        "created_at": "2025-11-20T08:00:00Z"
      }
    ],
    "total": 25,
    "limit": 50,
    "offset": 0
  }
}
```

**Features**:
- Supports comma-separated status list for multiple filters
- Full-text search on contact name and phone
- Pagination support
- Multi-tenant scoped

---

### **6. SMS Thread Read**

**Endpoint**: `GET /api/v1/message-threads/{contact_card_id}`

**Response**:
```json
{
  "success": true,
  "data": {
    "contact_card_id": "uuid",
    "messages": [
      {
        "id": "uuid",
        "sender": "+12025551234",
        "sender_role": "customer",
        "body": "Hi, I'm interested in your services",
        "direction": "inbound",
        "created_at": "2025-11-24T10:00:00Z",
        "provider": "Twilio",
        "message_sid": "SM123456",
        "delivered": true,
        "read": false
      }
    ],
    "total": 5
  }
}
```

**Features**:
- Returns messages in chronological order
- Falls back to `Call.text_messages` if no `MessageThread` records exist
- Multi-tenant scoped

---

### **7. Ghost Mode Toggle & Status**

#### **GET /api/v1/reps/{rep_id}/ghost-mode**

**Response**:
```json
{
  "success": true,
  "data": {
    "rep_id": "rep_123",
    "ghost_mode_enabled": true,
    "recording_mode": "ghost",
    "updated_at": "2025-11-24T12:00:00Z"
  }
}
```

#### **POST /api/v1/reps/{rep_id}/ghost-mode/toggle**

**Request Body**:
```json
{
  "enabled": true
}
```
OR omit `enabled` to toggle current state.

**Response**: Updated `GhostModeStatus`

**Events**: `rep.ghost_mode_changed`

**Features**:
- Reps can only view/toggle their own mode
- Managers can view/toggle any rep's mode
- Updates `SalesRep.recording_mode` field

---

### **8. Wins Feed**

**Endpoint**: `GET /api/v1/wins-feed`

**Query Parameters**:
- `date_from` (optional) - Filter wins from this date (defaults to 30 days ago)
- `date_to` (optional) - Filter wins until this date (defaults to now)
- `rep_id` (optional) - Filter by sales rep ID
- `limit` (optional, default 100, max 200) - Maximum results

**Response**:
```json
{
  "success": true,
  "data": {
    "wins": [
      {
        "appointment_id": "uuid",
        "lead_id": "uuid",
        "contact_name": "John Doe",
        "address": "123 Main St",
        "rep_name": "Jane Smith",
        "rep_id": "rep_123",
        "deal_size": 35000.0,
        "closed_at": "2025-11-24T15:00:00Z",
        "service_type": "roofing",
        "scheduled_start": "2025-11-24T10:00:00Z"
      }
    ],
    "total": 15,
    "date_from": "2025-10-25T00:00:00Z",
    "date_to": "2025-11-24T23:59:59Z"
  }
}
```

**Features**:
- Only returns appointments with `outcome = won` and `deal_size > 0`
- Ordered by `closed_at` (newest first)
- Includes rep name and contact name
- Defaults to last 30 days

---

### **9. Review Follow-Up Trigger**

**Endpoint**: `POST /api/v1/reviews/request`

**Request Body**:
```json
{
  "appointment_id": "uuid",
  "channel": "sms",
  "template_id": "review_template_1"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "review_request_id": "uuid",
    "appointment_id": "uuid",
    "contact_card_id": "uuid",
    "channel": "sms",
    "status": "queued",
    "created_at": "2025-11-24T16:00:00Z"
  }
}
```

**Events**: `review.requested`

**Features**:
- Only works for appointments with `outcome = won`
- Emits event for background worker to process SMS/email
- Validates appointment belongs to tenant
- Returns immediately (async processing)

---

## 📦 **New/Updated Files**

### **New Route Files**:
1. `app/routes/tasks.py` - Tasks CRUD endpoints
2. `app/routes/key_signals.py` - KeySignals list + acknowledge
3. `app/routes/message_threads.py` - SMS thread read
4. `app/routes/rep_settings.py` - Ghost mode toggle & status
5. `app/routes/wins_feed.py` - Wins feed endpoint
6. `app/routes/reviews.py` - Review follow-up trigger

### **Updated Route Files**:
1. `app/routes/appointments.py` - Added listing endpoint + deal_size support
2. `app/routes/leads.py` - Added listing endpoint with filters

### **New Schema Files**:
1. `app/schemas/appointments.py` - Appointment listing schemas

### **Updated Files**:
1. `app/main.py` - Registered all new routers

---

## 🔧 **Models Used**

All endpoints use existing models:
- `Appointment` (already has `deal_size` field ✅)
- `Task` (already has all required fields ✅)
- `KeySignal` (already has `acknowledged`, `acknowledged_at`, `acknowledged_by` ✅)
- `MessageThread` (already exists ✅)
- `SalesRep` (already has `recording_mode` field ✅)
- `Lead` (already has `deal_size`, `deal_status`, `closed_at` fields ✅)
- `ContactCard` (already exists ✅)

**No new migrations required** - all fields already exist in models.

---

## 🎯 **Event Emissions**

All endpoints emit appropriate domain events:

- `task.created` - When task is created
- `task.updated` - When task is updated
- `task.completed` - When task is marked complete
- `task.deleted` - When task is soft-deleted
- `key_signal.acknowledged` - When signal is acknowledged
- `rep.ghost_mode_changed` - When ghost mode is toggled
- `review.requested` - When review follow-up is triggered

---

## ✅ **Testing Checklist**

### **Appointments Listing**
- [ ] No appointments for rep → empty list
- [ ] Multiple appointments across dates → date filtering works
- [ ] Multi-tenant isolation → rep from another company cannot see appointments
- [ ] Auto-detects rep_id from auth context

### **Tasks CRUD**
- [ ] List tasks by assignee
- [ ] Overdue filter works correctly
- [ ] Complete task → status + timestamps + event emission
- [ ] Create task → validation and event emission
- [ ] Update task → change log and event emission

### **KeySignals**
- [ ] List all signals for company
- [ ] Filter by lead/appointment
- [ ] Acknowledge signal → idempotent (can't double acknowledge)
- [ ] Multi-tenant isolation

### **Appointment Deal Size**
- [ ] Update with outcome="won" + deal_size → persists correctly
- [ ] Updates Lead.deal_size and Lead.status
- [ ] Update without deal_size → keeps existing value

### **Lead Listing**
- [ ] Filter by status (single and comma-separated)
- [ ] Filter by rep
- [ ] Search by name/phone
- [ ] Pagination works
- [ ] Multi-tenant isolation

### **SMS Thread**
- [ ] Contact with no messages → empty array
- [ ] Multiple messages → sorted by time
- [ ] Falls back to Call.text_messages if no MessageThread
- [ ] Multi-tenant isolation

### **Ghost Mode**
- [ ] Rep can read & toggle their own mode
- [ ] Manager can toggle for any rep
- [ ] Tenant isolation
- [ ] Event emission

### **Wins Feed**
- [ ] No wins → empty list
- [ ] Multiple wins across dates → date filters correct
- [ ] Filter by rep_id
- [ ] Only returns won appointments with deal_size

### **Review Follow-Up**
- [ ] Request review for won appointment → success
- [ ] Request for appointment from another company → 403/404
- [ ] Request for non-won appointment → 400 error
- [ ] Event emission

---

## 📝 **Example Request/Response Payloads**

### **1. Get Today's Appointments (Rep)**

**Request**:
```bash
GET /api/v1/appointments?date=2025-11-24
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "appointments": [
      {
        "appointment_id": "apt_123",
        "lead_id": "lead_456",
        "contact_card_id": "contact_789",
        "customer_name": "John Doe",
        "address": "123 Main St, Phoenix, AZ",
        "scheduled_start": "2025-11-24T10:00:00Z",
        "scheduled_end": "2025-11-24T11:00:00Z",
        "status": "scheduled",
        "outcome": "pending",
        "service_type": "roofing",
        "is_assigned_to_me": true,
        "deal_size": null,
        "pending_tasks_count": 2
      }
    ],
    "total": 1,
    "date": "2025-11-24"
  }
}
```

---

### **2. List Tasks**

**Request**:
```bash
GET /api/v1/tasks?contact_card_id=contact_789&status=open&overdue=true
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "tasks": [
      {
        "id": "task_123",
        "description": "Follow up at 5pm",
        "assigned_to": "csr",
        "source": "shunya",
        "due_at": "2025-11-24T17:00:00Z",
        "status": "overdue",
        "priority": "high",
        "contact_card_id": "contact_789",
        "lead_id": "lead_456"
      }
    ],
    "total": 1,
    "overdue_count": 1
  }
}
```

---

### **3. Complete Task**

**Request**:
```bash
POST /api/v1/tasks/task_123/complete
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "id": "task_123",
    "description": "Follow up at 5pm",
    "assigned_to": "csr",
    "source": "shunya",
    "due_at": "2025-11-24T17:00:00Z",
    "status": "completed",
    "completed_at": "2025-11-24T16:30:00Z",
    "completed_by": "user_789"
  }
}
```

---

### **4. Acknowledge Key Signal**

**Request**:
```bash
POST /api/v1/key-signals/signal_123/acknowledge
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "id": "signal_123",
    "signal_type": "risk",
    "title": "Rep late to appointment",
    "severity": "high",
    "acknowledged": true,
    "acknowledged_at": "2025-11-24T16:30:00Z",
    "acknowledged_by": "user_789"
  }
}
```

---

### **5. Update Appointment with Deal Size**

**Request**:
```bash
PATCH /api/v1/appointments/apt_123
Authorization: Bearer <token>
Content-Type: application/json

{
  "outcome": "won",
  "deal_size": 35000.0
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "appointment": {
      "id": "apt_123",
      "outcome": "won",
      "status": "completed",
      "deal_size": 35000.0,
      ...
    },
    "lead": {
      "id": "lead_456",
      "status": "closed_won",
      "deal_size": 35000.0,
      "deal_status": "won",
      "closed_at": "2025-11-24T16:30:00Z"
    }
  }
}
```

---

### **6. List Leads**

**Request**:
```bash
GET /api/v1/leads?status=qualified_booked,qualified_unbooked&rep_id=rep_123&limit=20
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "leads": [
      {
        "lead_id": "lead_456",
        "status": "qualified_booked",
        "source": "inbound_call",
        "priority": "high",
        "score": 85,
        "last_contacted_at": "2025-11-24T10:00:00Z",
        "contact": {
          "name": "John Doe",
          "primary_phone": "+12025551234",
          "city": "Phoenix",
          "state": "AZ"
        },
        "created_at": "2025-11-20T08:00:00Z"
      }
    ],
    "total": 15,
    "limit": 20,
    "offset": 0
  }
}
```

---

### **7. Get SMS Thread**

**Request**:
```bash
GET /api/v1/message-threads/contact_789
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "contact_card_id": "contact_789",
    "messages": [
      {
        "id": "msg_123",
        "sender": "+12025551234",
        "sender_role": "customer",
        "body": "Hi, I'm interested in your services",
        "direction": "inbound",
        "created_at": "2025-11-24T10:00:00Z",
        "provider": "Twilio",
        "message_sid": "SM123456",
        "delivered": true,
        "read": false
      },
      {
        "id": "msg_124",
        "sender": "+12025559999",
        "sender_role": "csr",
        "body": "Thanks for reaching out! Let me schedule a consultation.",
        "direction": "outbound",
        "created_at": "2025-11-24T10:05:00Z",
        "provider": "Twilio",
        "message_sid": "SM123457",
        "delivered": true,
        "read": true
      }
    ],
    "total": 2
  }
}
```

---

### **8. Get Ghost Mode Status**

**Request**:
```bash
GET /api/v1/reps/rep_123/ghost-mode
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "rep_id": "rep_123",
    "ghost_mode_enabled": true,
    "recording_mode": "ghost",
    "updated_at": "2025-11-24T12:00:00Z"
  }
}
```

---

### **9. Toggle Ghost Mode**

**Request**:
```bash
POST /api/v1/reps/rep_123/ghost-mode/toggle
Authorization: Bearer <token>
Content-Type: application/json

{
  "enabled": false
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "rep_id": "rep_123",
    "ghost_mode_enabled": false,
    "recording_mode": "normal",
    "updated_at": "2025-11-24T16:30:00Z"
  }
}
```

---

### **10. Get Wins Feed**

**Request**:
```bash
GET /api/v1/wins-feed?date_from=2025-10-25T00:00:00Z&rep_id=rep_123&limit=50
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "wins": [
      {
        "appointment_id": "apt_123",
        "lead_id": "lead_456",
        "contact_name": "John Doe",
        "address": "123 Main St",
        "rep_name": "Jane Smith",
        "rep_id": "rep_123",
        "deal_size": 35000.0,
        "closed_at": "2025-11-24T15:00:00Z",
        "service_type": "roofing",
        "scheduled_start": "2025-11-24T10:00:00Z"
      }
    ],
    "total": 15,
    "date_from": "2025-10-25T00:00:00Z",
    "date_to": "2025-11-24T23:59:59Z"
  }
}
```

---

### **11. Request Review Follow-Up**

**Request**:
```bash
POST /api/v1/reviews/request
Authorization: Bearer <token>
Content-Type: application/json

{
  "appointment_id": "apt_123",
  "channel": "sms",
  "template_id": "review_template_1"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "review_request_id": "review_req_789",
    "appointment_id": "apt_123",
    "contact_card_id": "contact_789",
    "channel": "sms",
    "status": "queued",
    "created_at": "2025-11-24T16:30:00Z"
  }
}
```

---

## 🔒 **Security & Multi-Tenancy**

All endpoints:
- ✅ Enforce RBAC via `@require_role()` decorator
- ✅ Scope by `company_id` from auth context
- ✅ Validate tenant isolation (404 if entity belongs to another company)
- ✅ Use existing error response patterns

---

## 📊 **Event Bus Integration**

All endpoints emit events via `emit_domain_event()`:
- Events follow standard envelope format
- Include tenant_id, lead_id, payload
- Non-blocking emission

---

## 🧪 **Next Steps**

1. **Run Tests**: Create test files under `app/tests/` for each endpoint group
2. **Verify Imports**: Ensure all imports resolve correctly
3. **Check Linter**: Run linter on all new files
4. **Update OpenAPI**: Verify all endpoints appear in `/docs`
5. **Integration Testing**: Test with frontend client

---

## ✅ **Completion Status**

- ✅ All 9 endpoint groups implemented
- ✅ All routers registered in `main.py`
- ✅ All schemas created
- ✅ Event emissions added
- ✅ Multi-tenant scoping enforced
- ✅ RBAC enforced
- ⏳ Tests pending (to be created)

---

**End of Summary**



**Date**: 2025-11-24  
**Purpose**: Summary of all new endpoints implemented for frontend integration

---

## 📋 **Overview**

Implemented **9 new endpoint groups** with **20+ endpoints** total to support the end-to-end user journey:

1. ✅ Appointments listing (Today's Appointments for Reps)
2. ✅ Tasks CRUD (4 endpoints)
3. ✅ KeySignals list + acknowledge (2 endpoints)
4. ✅ Appointment deal_size extension
5. ✅ Lead listing with filters
6. ✅ SMS thread read
7. ✅ Ghost mode toggle & status (2 endpoints)
8. ✅ Wins feed
9. ✅ Review follow-up trigger

---

## 🆕 **New Endpoints**

### **1. Appointments - Today's Appointments**

**Endpoint**: `GET /api/v1/appointments`

**Query Parameters**:
- `rep_id` (optional) - Sales rep ID (defaults to authenticated user if rep)
- `date` (optional) - Date filter (YYYY-MM-DD, defaults to today)
- `status` (optional) - Filter by status (scheduled, confirmed, completed, cancelled, no_show)
- `outcome` (optional) - Filter by outcome (pending, won, lost, no_show, rescheduled)

**Response**:
```json
{
  "success": true,
  "data": {
    "appointments": [
      {
        "appointment_id": "uuid",
        "lead_id": "uuid",
        "contact_card_id": "uuid",
        "customer_name": "John Doe",
        "address": "123 Main St",
        "scheduled_start": "2025-11-24T10:00:00Z",
        "scheduled_end": "2025-11-24T11:00:00Z",
        "status": "scheduled",
        "outcome": "pending",
        "service_type": "roofing",
        "is_assigned_to_me": true,
        "deal_size": null,
        "pending_tasks_count": 2
      }
    ],
    "total": 5,
    "date": "2025-11-24"
  }
}
```

**Features**:
- Auto-detects rep_id from auth context for sales_rep role
- Filters by date (defaults to today in UTC)
- Includes pending tasks count
- Multi-tenant scoped

---

### **2. Tasks CRUD**

#### **GET /api/v1/tasks**

**Query Parameters**:
- `assignee_id` (optional) - Filter by assignee user ID
- `lead_id` (optional) - Filter by lead ID
- `contact_card_id` (optional) - Filter by contact card ID
- `status` (optional) - Filter by status (open, completed, overdue, cancelled)
- `overdue` (optional boolean) - Filter by overdue status
- `due_before` (optional datetime) - Filter tasks due before this date
- `due_after` (optional datetime) - Filter tasks due after this date

**Response**:
```json
{
  "success": true,
  "data": {
    "tasks": [
      {
        "id": "uuid",
        "description": "Follow up at 5pm",
        "assigned_to": "csr",
        "source": "shunya",
        "due_at": "2025-11-24T17:00:00Z",
        "status": "open",
        "priority": "high",
        "contact_card_id": "uuid",
        "lead_id": "uuid"
      }
    ],
    "total": 10,
    "overdue_count": 2
  }
}
```

#### **PATCH /api/v1/tasks/{task_id}**

**Request Body**:
```json
{
  "status": "completed",
  "due_at": "2025-11-25T17:00:00Z",
  "assigned_to": "rep",
  "description": "Updated description",
  "priority": "medium",
  "notes": "Additional notes"
}
```

**Response**: Updated `TaskSummary`

**Events**: `task.updated`

#### **POST /api/v1/tasks/{task_id}/complete**

**Response**: Completed `TaskSummary`

**Events**: `task.completed`

#### **DELETE /api/v1/tasks/{task_id}**

**Response**: `{"status": "deleted", "task_id": "uuid"}`

**Events**: `task.deleted`

#### **POST /api/v1/tasks**

**Request Body**:
```json
{
  "description": "Follow up with customer",
  "assigned_to": "csr",
  "contact_card_id": "uuid",
  "lead_id": "uuid",
  "appointment_id": "uuid",
  "call_id": 123,
  "due_at": "2025-11-25T17:00:00Z",
  "priority": "high",
  "source": "manual"
}
```

**Response**: Created `TaskSummary`

**Events**: `task.created`

**Features**:
- Auto-marks tasks as OVERDUE if due_at < now and status not completed/cancelled
- Soft delete (marks as cancelled)
- Stores notes in task_metadata JSON field

---

### **3. KeySignals List + Acknowledge**

#### **GET /api/v1/key-signals**

**Query Parameters**:
- `lead_id` (optional) - Filter by lead ID
- `appointment_id` (optional) - Filter by appointment ID
- `contact_card_id` (optional) - Filter by contact card ID
- `signal_type` (optional) - Filter by type (risk, opportunity, coaching, operational)
- `acknowledged` (optional boolean) - Filter by acknowledged status
- `created_after` (optional datetime) - Filter signals created after this date
- `created_before` (optional datetime) - Filter signals created before this date

**Response**:
```json
{
  "success": true,
  "data": {
    "signals": [
      {
        "id": "uuid",
        "signal_type": "risk",
        "title": "Rep late to appointment",
        "description": "Rep arrived 15 minutes late",
        "severity": "high",
        "acknowledged": false,
        "contact_card_id": "uuid",
        "lead_id": "uuid",
        "created_at": "2025-11-24T10:00:00Z"
      }
    ],
    "total": 5,
    "unacknowledged_count": 3
  }
}
```

#### **POST /api/v1/key-signals/{signal_id}/acknowledge**

**Response**: Acknowledged `KeySignalSummary`

**Events**: `key_signal.acknowledged`

**Features**:
- Idempotent (can call multiple times safely)
- Sets `acknowledged_at` and `acknowledged_by` from auth context
- Ordered by severity (critical first), then created_at (newest first)

---

### **4. Appointment Deal Size Extension**

**Updated Endpoint**: `PATCH /api/v1/appointments/{appointment_id}`

**New Field in Request Body**:
```json
{
  "outcome": "won",
  "deal_size": 35000.0
}
```

**Behavior**:
- When `outcome = "won"` and `deal_size` is provided:
  - Updates `Appointment.deal_size`
  - Syncs `Lead.deal_size`
  - Updates `Lead.deal_status = "won"`
  - Updates `Lead.status = CLOSED_WON` (if not already)
  - Sets `Lead.closed_at = now`
  - Updates `Appointment.status = COMPLETED`

**Response**: Updated `AppointmentResponse` with `deal_size` field

---

### **5. Lead Listing**

**Endpoint**: `GET /api/v1/leads`

**Query Parameters**:
- `status` (optional) - Filter by status (comma-separated for multiple: `new,qualified_booked`)
- `rep_id` (optional) - Filter by assigned rep ID
- `source` (optional) - Filter by source (inbound_call, web_form, referral, etc.)
- `date_from` (optional datetime) - Filter leads created after this date
- `date_to` (optional datetime) - Filter leads created before this date
- `search` (optional string) - Search by name or phone number
- `limit` (optional, default 50, max 200) - Maximum results
- `offset` (optional, default 0) - Pagination offset

**Response**:
```json
{
  "success": true,
  "data": {
    "leads": [
      {
        "lead_id": "uuid",
        "status": "qualified_booked",
        "source": "inbound_call",
        "priority": "high",
        "score": 85,
        "last_contacted_at": "2025-11-24T10:00:00Z",
        "contact": {
          "name": "John Doe",
          "primary_phone": "+12025551234",
          "city": "Phoenix",
          "state": "AZ"
        },
        "created_at": "2025-11-20T08:00:00Z"
      }
    ],
    "total": 25,
    "limit": 50,
    "offset": 0
  }
}
```

**Features**:
- Supports comma-separated status list for multiple filters
- Full-text search on contact name and phone
- Pagination support
- Multi-tenant scoped

---

### **6. SMS Thread Read**

**Endpoint**: `GET /api/v1/message-threads/{contact_card_id}`

**Response**:
```json
{
  "success": true,
  "data": {
    "contact_card_id": "uuid",
    "messages": [
      {
        "id": "uuid",
        "sender": "+12025551234",
        "sender_role": "customer",
        "body": "Hi, I'm interested in your services",
        "direction": "inbound",
        "created_at": "2025-11-24T10:00:00Z",
        "provider": "Twilio",
        "message_sid": "SM123456",
        "delivered": true,
        "read": false
      }
    ],
    "total": 5
  }
}
```

**Features**:
- Returns messages in chronological order
- Falls back to `Call.text_messages` if no `MessageThread` records exist
- Multi-tenant scoped

---

### **7. Ghost Mode Toggle & Status**

#### **GET /api/v1/reps/{rep_id}/ghost-mode**

**Response**:
```json
{
  "success": true,
  "data": {
    "rep_id": "rep_123",
    "ghost_mode_enabled": true,
    "recording_mode": "ghost",
    "updated_at": "2025-11-24T12:00:00Z"
  }
}
```

#### **POST /api/v1/reps/{rep_id}/ghost-mode/toggle**

**Request Body**:
```json
{
  "enabled": true
}
```
OR omit `enabled` to toggle current state.

**Response**: Updated `GhostModeStatus`

**Events**: `rep.ghost_mode_changed`

**Features**:
- Reps can only view/toggle their own mode
- Managers can view/toggle any rep's mode
- Updates `SalesRep.recording_mode` field

---

### **8. Wins Feed**

**Endpoint**: `GET /api/v1/wins-feed`

**Query Parameters**:
- `date_from` (optional) - Filter wins from this date (defaults to 30 days ago)
- `date_to` (optional) - Filter wins until this date (defaults to now)
- `rep_id` (optional) - Filter by sales rep ID
- `limit` (optional, default 100, max 200) - Maximum results

**Response**:
```json
{
  "success": true,
  "data": {
    "wins": [
      {
        "appointment_id": "uuid",
        "lead_id": "uuid",
        "contact_name": "John Doe",
        "address": "123 Main St",
        "rep_name": "Jane Smith",
        "rep_id": "rep_123",
        "deal_size": 35000.0,
        "closed_at": "2025-11-24T15:00:00Z",
        "service_type": "roofing",
        "scheduled_start": "2025-11-24T10:00:00Z"
      }
    ],
    "total": 15,
    "date_from": "2025-10-25T00:00:00Z",
    "date_to": "2025-11-24T23:59:59Z"
  }
}
```

**Features**:
- Only returns appointments with `outcome = won` and `deal_size > 0`
- Ordered by `closed_at` (newest first)
- Includes rep name and contact name
- Defaults to last 30 days

---

### **9. Review Follow-Up Trigger**

**Endpoint**: `POST /api/v1/reviews/request`

**Request Body**:
```json
{
  "appointment_id": "uuid",
  "channel": "sms",
  "template_id": "review_template_1"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "review_request_id": "uuid",
    "appointment_id": "uuid",
    "contact_card_id": "uuid",
    "channel": "sms",
    "status": "queued",
    "created_at": "2025-11-24T16:00:00Z"
  }
}
```

**Events**: `review.requested`

**Features**:
- Only works for appointments with `outcome = won`
- Emits event for background worker to process SMS/email
- Validates appointment belongs to tenant
- Returns immediately (async processing)

---

## 📦 **New/Updated Files**

### **New Route Files**:
1. `app/routes/tasks.py` - Tasks CRUD endpoints
2. `app/routes/key_signals.py` - KeySignals list + acknowledge
3. `app/routes/message_threads.py` - SMS thread read
4. `app/routes/rep_settings.py` - Ghost mode toggle & status
5. `app/routes/wins_feed.py` - Wins feed endpoint
6. `app/routes/reviews.py` - Review follow-up trigger

### **Updated Route Files**:
1. `app/routes/appointments.py` - Added listing endpoint + deal_size support
2. `app/routes/leads.py` - Added listing endpoint with filters

### **New Schema Files**:
1. `app/schemas/appointments.py` - Appointment listing schemas

### **Updated Files**:
1. `app/main.py` - Registered all new routers

---

## 🔧 **Models Used**

All endpoints use existing models:
- `Appointment` (already has `deal_size` field ✅)
- `Task` (already has all required fields ✅)
- `KeySignal` (already has `acknowledged`, `acknowledged_at`, `acknowledged_by` ✅)
- `MessageThread` (already exists ✅)
- `SalesRep` (already has `recording_mode` field ✅)
- `Lead` (already has `deal_size`, `deal_status`, `closed_at` fields ✅)
- `ContactCard` (already exists ✅)

**No new migrations required** - all fields already exist in models.

---

## 🎯 **Event Emissions**

All endpoints emit appropriate domain events:

- `task.created` - When task is created
- `task.updated` - When task is updated
- `task.completed` - When task is marked complete
- `task.deleted` - When task is soft-deleted
- `key_signal.acknowledged` - When signal is acknowledged
- `rep.ghost_mode_changed` - When ghost mode is toggled
- `review.requested` - When review follow-up is triggered

---

## ✅ **Testing Checklist**

### **Appointments Listing**
- [ ] No appointments for rep → empty list
- [ ] Multiple appointments across dates → date filtering works
- [ ] Multi-tenant isolation → rep from another company cannot see appointments
- [ ] Auto-detects rep_id from auth context

### **Tasks CRUD**
- [ ] List tasks by assignee
- [ ] Overdue filter works correctly
- [ ] Complete task → status + timestamps + event emission
- [ ] Create task → validation and event emission
- [ ] Update task → change log and event emission

### **KeySignals**
- [ ] List all signals for company
- [ ] Filter by lead/appointment
- [ ] Acknowledge signal → idempotent (can't double acknowledge)
- [ ] Multi-tenant isolation

### **Appointment Deal Size**
- [ ] Update with outcome="won" + deal_size → persists correctly
- [ ] Updates Lead.deal_size and Lead.status
- [ ] Update without deal_size → keeps existing value

### **Lead Listing**
- [ ] Filter by status (single and comma-separated)
- [ ] Filter by rep
- [ ] Search by name/phone
- [ ] Pagination works
- [ ] Multi-tenant isolation

### **SMS Thread**
- [ ] Contact with no messages → empty array
- [ ] Multiple messages → sorted by time
- [ ] Falls back to Call.text_messages if no MessageThread
- [ ] Multi-tenant isolation

### **Ghost Mode**
- [ ] Rep can read & toggle their own mode
- [ ] Manager can toggle for any rep
- [ ] Tenant isolation
- [ ] Event emission

### **Wins Feed**
- [ ] No wins → empty list
- [ ] Multiple wins across dates → date filters correct
- [ ] Filter by rep_id
- [ ] Only returns won appointments with deal_size

### **Review Follow-Up**
- [ ] Request review for won appointment → success
- [ ] Request for appointment from another company → 403/404
- [ ] Request for non-won appointment → 400 error
- [ ] Event emission

---

## 📝 **Example Request/Response Payloads**

### **1. Get Today's Appointments (Rep)**

**Request**:
```bash
GET /api/v1/appointments?date=2025-11-24
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "appointments": [
      {
        "appointment_id": "apt_123",
        "lead_id": "lead_456",
        "contact_card_id": "contact_789",
        "customer_name": "John Doe",
        "address": "123 Main St, Phoenix, AZ",
        "scheduled_start": "2025-11-24T10:00:00Z",
        "scheduled_end": "2025-11-24T11:00:00Z",
        "status": "scheduled",
        "outcome": "pending",
        "service_type": "roofing",
        "is_assigned_to_me": true,
        "deal_size": null,
        "pending_tasks_count": 2
      }
    ],
    "total": 1,
    "date": "2025-11-24"
  }
}
```

---

### **2. List Tasks**

**Request**:
```bash
GET /api/v1/tasks?contact_card_id=contact_789&status=open&overdue=true
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "tasks": [
      {
        "id": "task_123",
        "description": "Follow up at 5pm",
        "assigned_to": "csr",
        "source": "shunya",
        "due_at": "2025-11-24T17:00:00Z",
        "status": "overdue",
        "priority": "high",
        "contact_card_id": "contact_789",
        "lead_id": "lead_456"
      }
    ],
    "total": 1,
    "overdue_count": 1
  }
}
```

---

### **3. Complete Task**

**Request**:
```bash
POST /api/v1/tasks/task_123/complete
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "id": "task_123",
    "description": "Follow up at 5pm",
    "assigned_to": "csr",
    "source": "shunya",
    "due_at": "2025-11-24T17:00:00Z",
    "status": "completed",
    "completed_at": "2025-11-24T16:30:00Z",
    "completed_by": "user_789"
  }
}
```

---

### **4. Acknowledge Key Signal**

**Request**:
```bash
POST /api/v1/key-signals/signal_123/acknowledge
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "id": "signal_123",
    "signal_type": "risk",
    "title": "Rep late to appointment",
    "severity": "high",
    "acknowledged": true,
    "acknowledged_at": "2025-11-24T16:30:00Z",
    "acknowledged_by": "user_789"
  }
}
```

---

### **5. Update Appointment with Deal Size**

**Request**:
```bash
PATCH /api/v1/appointments/apt_123
Authorization: Bearer <token>
Content-Type: application/json

{
  "outcome": "won",
  "deal_size": 35000.0
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "appointment": {
      "id": "apt_123",
      "outcome": "won",
      "status": "completed",
      "deal_size": 35000.0,
      ...
    },
    "lead": {
      "id": "lead_456",
      "status": "closed_won",
      "deal_size": 35000.0,
      "deal_status": "won",
      "closed_at": "2025-11-24T16:30:00Z"
    }
  }
}
```

---

### **6. List Leads**

**Request**:
```bash
GET /api/v1/leads?status=qualified_booked,qualified_unbooked&rep_id=rep_123&limit=20
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "leads": [
      {
        "lead_id": "lead_456",
        "status": "qualified_booked",
        "source": "inbound_call",
        "priority": "high",
        "score": 85,
        "last_contacted_at": "2025-11-24T10:00:00Z",
        "contact": {
          "name": "John Doe",
          "primary_phone": "+12025551234",
          "city": "Phoenix",
          "state": "AZ"
        },
        "created_at": "2025-11-20T08:00:00Z"
      }
    ],
    "total": 15,
    "limit": 20,
    "offset": 0
  }
}
```

---

### **7. Get SMS Thread**

**Request**:
```bash
GET /api/v1/message-threads/contact_789
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "contact_card_id": "contact_789",
    "messages": [
      {
        "id": "msg_123",
        "sender": "+12025551234",
        "sender_role": "customer",
        "body": "Hi, I'm interested in your services",
        "direction": "inbound",
        "created_at": "2025-11-24T10:00:00Z",
        "provider": "Twilio",
        "message_sid": "SM123456",
        "delivered": true,
        "read": false
      },
      {
        "id": "msg_124",
        "sender": "+12025559999",
        "sender_role": "csr",
        "body": "Thanks for reaching out! Let me schedule a consultation.",
        "direction": "outbound",
        "created_at": "2025-11-24T10:05:00Z",
        "provider": "Twilio",
        "message_sid": "SM123457",
        "delivered": true,
        "read": true
      }
    ],
    "total": 2
  }
}
```

---

### **8. Get Ghost Mode Status**

**Request**:
```bash
GET /api/v1/reps/rep_123/ghost-mode
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "rep_id": "rep_123",
    "ghost_mode_enabled": true,
    "recording_mode": "ghost",
    "updated_at": "2025-11-24T12:00:00Z"
  }
}
```

---

### **9. Toggle Ghost Mode**

**Request**:
```bash
POST /api/v1/reps/rep_123/ghost-mode/toggle
Authorization: Bearer <token>
Content-Type: application/json

{
  "enabled": false
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "rep_id": "rep_123",
    "ghost_mode_enabled": false,
    "recording_mode": "normal",
    "updated_at": "2025-11-24T16:30:00Z"
  }
}
```

---

### **10. Get Wins Feed**

**Request**:
```bash
GET /api/v1/wins-feed?date_from=2025-10-25T00:00:00Z&rep_id=rep_123&limit=50
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "wins": [
      {
        "appointment_id": "apt_123",
        "lead_id": "lead_456",
        "contact_name": "John Doe",
        "address": "123 Main St",
        "rep_name": "Jane Smith",
        "rep_id": "rep_123",
        "deal_size": 35000.0,
        "closed_at": "2025-11-24T15:00:00Z",
        "service_type": "roofing",
        "scheduled_start": "2025-11-24T10:00:00Z"
      }
    ],
    "total": 15,
    "date_from": "2025-10-25T00:00:00Z",
    "date_to": "2025-11-24T23:59:59Z"
  }
}
```

---

### **11. Request Review Follow-Up**

**Request**:
```bash
POST /api/v1/reviews/request
Authorization: Bearer <token>
Content-Type: application/json

{
  "appointment_id": "apt_123",
  "channel": "sms",
  "template_id": "review_template_1"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "review_request_id": "review_req_789",
    "appointment_id": "apt_123",
    "contact_card_id": "contact_789",
    "channel": "sms",
    "status": "queued",
    "created_at": "2025-11-24T16:30:00Z"
  }
}
```

---

## 🔒 **Security & Multi-Tenancy**

All endpoints:
- ✅ Enforce RBAC via `@require_role()` decorator
- ✅ Scope by `company_id` from auth context
- ✅ Validate tenant isolation (404 if entity belongs to another company)
- ✅ Use existing error response patterns

---

## 📊 **Event Bus Integration**

All endpoints emit events via `emit_domain_event()`:
- Events follow standard envelope format
- Include tenant_id, lead_id, payload
- Non-blocking emission

---

## 🧪 **Next Steps**

1. **Run Tests**: Create test files under `app/tests/` for each endpoint group
2. **Verify Imports**: Ensure all imports resolve correctly
3. **Check Linter**: Run linter on all new files
4. **Update OpenAPI**: Verify all endpoints appear in `/docs`
5. **Integration Testing**: Test with frontend client

---

## ✅ **Completion Status**

- ✅ All 9 endpoint groups implemented
- ✅ All routers registered in `main.py`
- ✅ All schemas created
- ✅ Event emissions added
- ✅ Multi-tenant scoping enforced
- ✅ RBAC enforced
- ⏳ Tests pending (to be created)

---

**End of Summary**



**Date**: 2025-11-24  
**Purpose**: Summary of all new endpoints implemented for frontend integration

---

## 📋 **Overview**

Implemented **9 new endpoint groups** with **20+ endpoints** total to support the end-to-end user journey:

1. ✅ Appointments listing (Today's Appointments for Reps)
2. ✅ Tasks CRUD (4 endpoints)
3. ✅ KeySignals list + acknowledge (2 endpoints)
4. ✅ Appointment deal_size extension
5. ✅ Lead listing with filters
6. ✅ SMS thread read
7. ✅ Ghost mode toggle & status (2 endpoints)
8. ✅ Wins feed
9. ✅ Review follow-up trigger

---

## 🆕 **New Endpoints**

### **1. Appointments - Today's Appointments**

**Endpoint**: `GET /api/v1/appointments`

**Query Parameters**:
- `rep_id` (optional) - Sales rep ID (defaults to authenticated user if rep)
- `date` (optional) - Date filter (YYYY-MM-DD, defaults to today)
- `status` (optional) - Filter by status (scheduled, confirmed, completed, cancelled, no_show)
- `outcome` (optional) - Filter by outcome (pending, won, lost, no_show, rescheduled)

**Response**:
```json
{
  "success": true,
  "data": {
    "appointments": [
      {
        "appointment_id": "uuid",
        "lead_id": "uuid",
        "contact_card_id": "uuid",
        "customer_name": "John Doe",
        "address": "123 Main St",
        "scheduled_start": "2025-11-24T10:00:00Z",
        "scheduled_end": "2025-11-24T11:00:00Z",
        "status": "scheduled",
        "outcome": "pending",
        "service_type": "roofing",
        "is_assigned_to_me": true,
        "deal_size": null,
        "pending_tasks_count": 2
      }
    ],
    "total": 5,
    "date": "2025-11-24"
  }
}
```

**Features**:
- Auto-detects rep_id from auth context for sales_rep role
- Filters by date (defaults to today in UTC)
- Includes pending tasks count
- Multi-tenant scoped

---

### **2. Tasks CRUD**

#### **GET /api/v1/tasks**

**Query Parameters**:
- `assignee_id` (optional) - Filter by assignee user ID
- `lead_id` (optional) - Filter by lead ID
- `contact_card_id` (optional) - Filter by contact card ID
- `status` (optional) - Filter by status (open, completed, overdue, cancelled)
- `overdue` (optional boolean) - Filter by overdue status
- `due_before` (optional datetime) - Filter tasks due before this date
- `due_after` (optional datetime) - Filter tasks due after this date

**Response**:
```json
{
  "success": true,
  "data": {
    "tasks": [
      {
        "id": "uuid",
        "description": "Follow up at 5pm",
        "assigned_to": "csr",
        "source": "shunya",
        "due_at": "2025-11-24T17:00:00Z",
        "status": "open",
        "priority": "high",
        "contact_card_id": "uuid",
        "lead_id": "uuid"
      }
    ],
    "total": 10,
    "overdue_count": 2
  }
}
```

#### **PATCH /api/v1/tasks/{task_id}**

**Request Body**:
```json
{
  "status": "completed",
  "due_at": "2025-11-25T17:00:00Z",
  "assigned_to": "rep",
  "description": "Updated description",
  "priority": "medium",
  "notes": "Additional notes"
}
```

**Response**: Updated `TaskSummary`

**Events**: `task.updated`

#### **POST /api/v1/tasks/{task_id}/complete**

**Response**: Completed `TaskSummary`

**Events**: `task.completed`

#### **DELETE /api/v1/tasks/{task_id}**

**Response**: `{"status": "deleted", "task_id": "uuid"}`

**Events**: `task.deleted`

#### **POST /api/v1/tasks**

**Request Body**:
```json
{
  "description": "Follow up with customer",
  "assigned_to": "csr",
  "contact_card_id": "uuid",
  "lead_id": "uuid",
  "appointment_id": "uuid",
  "call_id": 123,
  "due_at": "2025-11-25T17:00:00Z",
  "priority": "high",
  "source": "manual"
}
```

**Response**: Created `TaskSummary`

**Events**: `task.created`

**Features**:
- Auto-marks tasks as OVERDUE if due_at < now and status not completed/cancelled
- Soft delete (marks as cancelled)
- Stores notes in task_metadata JSON field

---

### **3. KeySignals List + Acknowledge**

#### **GET /api/v1/key-signals**

**Query Parameters**:
- `lead_id` (optional) - Filter by lead ID
- `appointment_id` (optional) - Filter by appointment ID
- `contact_card_id` (optional) - Filter by contact card ID
- `signal_type` (optional) - Filter by type (risk, opportunity, coaching, operational)
- `acknowledged` (optional boolean) - Filter by acknowledged status
- `created_after` (optional datetime) - Filter signals created after this date
- `created_before` (optional datetime) - Filter signals created before this date

**Response**:
```json
{
  "success": true,
  "data": {
    "signals": [
      {
        "id": "uuid",
        "signal_type": "risk",
        "title": "Rep late to appointment",
        "description": "Rep arrived 15 minutes late",
        "severity": "high",
        "acknowledged": false,
        "contact_card_id": "uuid",
        "lead_id": "uuid",
        "created_at": "2025-11-24T10:00:00Z"
      }
    ],
    "total": 5,
    "unacknowledged_count": 3
  }
}
```

#### **POST /api/v1/key-signals/{signal_id}/acknowledge**

**Response**: Acknowledged `KeySignalSummary`

**Events**: `key_signal.acknowledged`

**Features**:
- Idempotent (can call multiple times safely)
- Sets `acknowledged_at` and `acknowledged_by` from auth context
- Ordered by severity (critical first), then created_at (newest first)

---

### **4. Appointment Deal Size Extension**

**Updated Endpoint**: `PATCH /api/v1/appointments/{appointment_id}`

**New Field in Request Body**:
```json
{
  "outcome": "won",
  "deal_size": 35000.0
}
```

**Behavior**:
- When `outcome = "won"` and `deal_size` is provided:
  - Updates `Appointment.deal_size`
  - Syncs `Lead.deal_size`
  - Updates `Lead.deal_status = "won"`
  - Updates `Lead.status = CLOSED_WON` (if not already)
  - Sets `Lead.closed_at = now`
  - Updates `Appointment.status = COMPLETED`

**Response**: Updated `AppointmentResponse` with `deal_size` field

---

### **5. Lead Listing**

**Endpoint**: `GET /api/v1/leads`

**Query Parameters**:
- `status` (optional) - Filter by status (comma-separated for multiple: `new,qualified_booked`)
- `rep_id` (optional) - Filter by assigned rep ID
- `source` (optional) - Filter by source (inbound_call, web_form, referral, etc.)
- `date_from` (optional datetime) - Filter leads created after this date
- `date_to` (optional datetime) - Filter leads created before this date
- `search` (optional string) - Search by name or phone number
- `limit` (optional, default 50, max 200) - Maximum results
- `offset` (optional, default 0) - Pagination offset

**Response**:
```json
{
  "success": true,
  "data": {
    "leads": [
      {
        "lead_id": "uuid",
        "status": "qualified_booked",
        "source": "inbound_call",
        "priority": "high",
        "score": 85,
        "last_contacted_at": "2025-11-24T10:00:00Z",
        "contact": {
          "name": "John Doe",
          "primary_phone": "+12025551234",
          "city": "Phoenix",
          "state": "AZ"
        },
        "created_at": "2025-11-20T08:00:00Z"
      }
    ],
    "total": 25,
    "limit": 50,
    "offset": 0
  }
}
```

**Features**:
- Supports comma-separated status list for multiple filters
- Full-text search on contact name and phone
- Pagination support
- Multi-tenant scoped

---

### **6. SMS Thread Read**

**Endpoint**: `GET /api/v1/message-threads/{contact_card_id}`

**Response**:
```json
{
  "success": true,
  "data": {
    "contact_card_id": "uuid",
    "messages": [
      {
        "id": "uuid",
        "sender": "+12025551234",
        "sender_role": "customer",
        "body": "Hi, I'm interested in your services",
        "direction": "inbound",
        "created_at": "2025-11-24T10:00:00Z",
        "provider": "Twilio",
        "message_sid": "SM123456",
        "delivered": true,
        "read": false
      }
    ],
    "total": 5
  }
}
```

**Features**:
- Returns messages in chronological order
- Falls back to `Call.text_messages` if no `MessageThread` records exist
- Multi-tenant scoped

---

### **7. Ghost Mode Toggle & Status**

#### **GET /api/v1/reps/{rep_id}/ghost-mode**

**Response**:
```json
{
  "success": true,
  "data": {
    "rep_id": "rep_123",
    "ghost_mode_enabled": true,
    "recording_mode": "ghost",
    "updated_at": "2025-11-24T12:00:00Z"
  }
}
```

#### **POST /api/v1/reps/{rep_id}/ghost-mode/toggle**

**Request Body**:
```json
{
  "enabled": true
}
```
OR omit `enabled` to toggle current state.

**Response**: Updated `GhostModeStatus`

**Events**: `rep.ghost_mode_changed`

**Features**:
- Reps can only view/toggle their own mode
- Managers can view/toggle any rep's mode
- Updates `SalesRep.recording_mode` field

---

### **8. Wins Feed**

**Endpoint**: `GET /api/v1/wins-feed`

**Query Parameters**:
- `date_from` (optional) - Filter wins from this date (defaults to 30 days ago)
- `date_to` (optional) - Filter wins until this date (defaults to now)
- `rep_id` (optional) - Filter by sales rep ID
- `limit` (optional, default 100, max 200) - Maximum results

**Response**:
```json
{
  "success": true,
  "data": {
    "wins": [
      {
        "appointment_id": "uuid",
        "lead_id": "uuid",
        "contact_name": "John Doe",
        "address": "123 Main St",
        "rep_name": "Jane Smith",
        "rep_id": "rep_123",
        "deal_size": 35000.0,
        "closed_at": "2025-11-24T15:00:00Z",
        "service_type": "roofing",
        "scheduled_start": "2025-11-24T10:00:00Z"
      }
    ],
    "total": 15,
    "date_from": "2025-10-25T00:00:00Z",
    "date_to": "2025-11-24T23:59:59Z"
  }
}
```

**Features**:
- Only returns appointments with `outcome = won` and `deal_size > 0`
- Ordered by `closed_at` (newest first)
- Includes rep name and contact name
- Defaults to last 30 days

---

### **9. Review Follow-Up Trigger**

**Endpoint**: `POST /api/v1/reviews/request`

**Request Body**:
```json
{
  "appointment_id": "uuid",
  "channel": "sms",
  "template_id": "review_template_1"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "review_request_id": "uuid",
    "appointment_id": "uuid",
    "contact_card_id": "uuid",
    "channel": "sms",
    "status": "queued",
    "created_at": "2025-11-24T16:00:00Z"
  }
}
```

**Events**: `review.requested`

**Features**:
- Only works for appointments with `outcome = won`
- Emits event for background worker to process SMS/email
- Validates appointment belongs to tenant
- Returns immediately (async processing)

---

## 📦 **New/Updated Files**

### **New Route Files**:
1. `app/routes/tasks.py` - Tasks CRUD endpoints
2. `app/routes/key_signals.py` - KeySignals list + acknowledge
3. `app/routes/message_threads.py` - SMS thread read
4. `app/routes/rep_settings.py` - Ghost mode toggle & status
5. `app/routes/wins_feed.py` - Wins feed endpoint
6. `app/routes/reviews.py` - Review follow-up trigger

### **Updated Route Files**:
1. `app/routes/appointments.py` - Added listing endpoint + deal_size support
2. `app/routes/leads.py` - Added listing endpoint with filters

### **New Schema Files**:
1. `app/schemas/appointments.py` - Appointment listing schemas

### **Updated Files**:
1. `app/main.py` - Registered all new routers

---

## 🔧 **Models Used**

All endpoints use existing models:
- `Appointment` (already has `deal_size` field ✅)
- `Task` (already has all required fields ✅)
- `KeySignal` (already has `acknowledged`, `acknowledged_at`, `acknowledged_by` ✅)
- `MessageThread` (already exists ✅)
- `SalesRep` (already has `recording_mode` field ✅)
- `Lead` (already has `deal_size`, `deal_status`, `closed_at` fields ✅)
- `ContactCard` (already exists ✅)

**No new migrations required** - all fields already exist in models.

---

## 🎯 **Event Emissions**

All endpoints emit appropriate domain events:

- `task.created` - When task is created
- `task.updated` - When task is updated
- `task.completed` - When task is marked complete
- `task.deleted` - When task is soft-deleted
- `key_signal.acknowledged` - When signal is acknowledged
- `rep.ghost_mode_changed` - When ghost mode is toggled
- `review.requested` - When review follow-up is triggered

---

## ✅ **Testing Checklist**

### **Appointments Listing**
- [ ] No appointments for rep → empty list
- [ ] Multiple appointments across dates → date filtering works
- [ ] Multi-tenant isolation → rep from another company cannot see appointments
- [ ] Auto-detects rep_id from auth context

### **Tasks CRUD**
- [ ] List tasks by assignee
- [ ] Overdue filter works correctly
- [ ] Complete task → status + timestamps + event emission
- [ ] Create task → validation and event emission
- [ ] Update task → change log and event emission

### **KeySignals**
- [ ] List all signals for company
- [ ] Filter by lead/appointment
- [ ] Acknowledge signal → idempotent (can't double acknowledge)
- [ ] Multi-tenant isolation

### **Appointment Deal Size**
- [ ] Update with outcome="won" + deal_size → persists correctly
- [ ] Updates Lead.deal_size and Lead.status
- [ ] Update without deal_size → keeps existing value

### **Lead Listing**
- [ ] Filter by status (single and comma-separated)
- [ ] Filter by rep
- [ ] Search by name/phone
- [ ] Pagination works
- [ ] Multi-tenant isolation

### **SMS Thread**
- [ ] Contact with no messages → empty array
- [ ] Multiple messages → sorted by time
- [ ] Falls back to Call.text_messages if no MessageThread
- [ ] Multi-tenant isolation

### **Ghost Mode**
- [ ] Rep can read & toggle their own mode
- [ ] Manager can toggle for any rep
- [ ] Tenant isolation
- [ ] Event emission

### **Wins Feed**
- [ ] No wins → empty list
- [ ] Multiple wins across dates → date filters correct
- [ ] Filter by rep_id
- [ ] Only returns won appointments with deal_size

### **Review Follow-Up**
- [ ] Request review for won appointment → success
- [ ] Request for appointment from another company → 403/404
- [ ] Request for non-won appointment → 400 error
- [ ] Event emission

---

## 📝 **Example Request/Response Payloads**

### **1. Get Today's Appointments (Rep)**

**Request**:
```bash
GET /api/v1/appointments?date=2025-11-24
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "appointments": [
      {
        "appointment_id": "apt_123",
        "lead_id": "lead_456",
        "contact_card_id": "contact_789",
        "customer_name": "John Doe",
        "address": "123 Main St, Phoenix, AZ",
        "scheduled_start": "2025-11-24T10:00:00Z",
        "scheduled_end": "2025-11-24T11:00:00Z",
        "status": "scheduled",
        "outcome": "pending",
        "service_type": "roofing",
        "is_assigned_to_me": true,
        "deal_size": null,
        "pending_tasks_count": 2
      }
    ],
    "total": 1,
    "date": "2025-11-24"
  }
}
```

---

### **2. List Tasks**

**Request**:
```bash
GET /api/v1/tasks?contact_card_id=contact_789&status=open&overdue=true
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "tasks": [
      {
        "id": "task_123",
        "description": "Follow up at 5pm",
        "assigned_to": "csr",
        "source": "shunya",
        "due_at": "2025-11-24T17:00:00Z",
        "status": "overdue",
        "priority": "high",
        "contact_card_id": "contact_789",
        "lead_id": "lead_456"
      }
    ],
    "total": 1,
    "overdue_count": 1
  }
}
```

---

### **3. Complete Task**

**Request**:
```bash
POST /api/v1/tasks/task_123/complete
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "id": "task_123",
    "description": "Follow up at 5pm",
    "assigned_to": "csr",
    "source": "shunya",
    "due_at": "2025-11-24T17:00:00Z",
    "status": "completed",
    "completed_at": "2025-11-24T16:30:00Z",
    "completed_by": "user_789"
  }
}
```

---

### **4. Acknowledge Key Signal**

**Request**:
```bash
POST /api/v1/key-signals/signal_123/acknowledge
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "id": "signal_123",
    "signal_type": "risk",
    "title": "Rep late to appointment",
    "severity": "high",
    "acknowledged": true,
    "acknowledged_at": "2025-11-24T16:30:00Z",
    "acknowledged_by": "user_789"
  }
}
```

---

### **5. Update Appointment with Deal Size**

**Request**:
```bash
PATCH /api/v1/appointments/apt_123
Authorization: Bearer <token>
Content-Type: application/json

{
  "outcome": "won",
  "deal_size": 35000.0
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "appointment": {
      "id": "apt_123",
      "outcome": "won",
      "status": "completed",
      "deal_size": 35000.0,
      ...
    },
    "lead": {
      "id": "lead_456",
      "status": "closed_won",
      "deal_size": 35000.0,
      "deal_status": "won",
      "closed_at": "2025-11-24T16:30:00Z"
    }
  }
}
```

---

### **6. List Leads**

**Request**:
```bash
GET /api/v1/leads?status=qualified_booked,qualified_unbooked&rep_id=rep_123&limit=20
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "leads": [
      {
        "lead_id": "lead_456",
        "status": "qualified_booked",
        "source": "inbound_call",
        "priority": "high",
        "score": 85,
        "last_contacted_at": "2025-11-24T10:00:00Z",
        "contact": {
          "name": "John Doe",
          "primary_phone": "+12025551234",
          "city": "Phoenix",
          "state": "AZ"
        },
        "created_at": "2025-11-20T08:00:00Z"
      }
    ],
    "total": 15,
    "limit": 20,
    "offset": 0
  }
}
```

---

### **7. Get SMS Thread**

**Request**:
```bash
GET /api/v1/message-threads/contact_789
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "contact_card_id": "contact_789",
    "messages": [
      {
        "id": "msg_123",
        "sender": "+12025551234",
        "sender_role": "customer",
        "body": "Hi, I'm interested in your services",
        "direction": "inbound",
        "created_at": "2025-11-24T10:00:00Z",
        "provider": "Twilio",
        "message_sid": "SM123456",
        "delivered": true,
        "read": false
      },
      {
        "id": "msg_124",
        "sender": "+12025559999",
        "sender_role": "csr",
        "body": "Thanks for reaching out! Let me schedule a consultation.",
        "direction": "outbound",
        "created_at": "2025-11-24T10:05:00Z",
        "provider": "Twilio",
        "message_sid": "SM123457",
        "delivered": true,
        "read": true
      }
    ],
    "total": 2
  }
}
```

---

### **8. Get Ghost Mode Status**

**Request**:
```bash
GET /api/v1/reps/rep_123/ghost-mode
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "rep_id": "rep_123",
    "ghost_mode_enabled": true,
    "recording_mode": "ghost",
    "updated_at": "2025-11-24T12:00:00Z"
  }
}
```

---

### **9. Toggle Ghost Mode**

**Request**:
```bash
POST /api/v1/reps/rep_123/ghost-mode/toggle
Authorization: Bearer <token>
Content-Type: application/json

{
  "enabled": false
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "rep_id": "rep_123",
    "ghost_mode_enabled": false,
    "recording_mode": "normal",
    "updated_at": "2025-11-24T16:30:00Z"
  }
}
```

---

### **10. Get Wins Feed**

**Request**:
```bash
GET /api/v1/wins-feed?date_from=2025-10-25T00:00:00Z&rep_id=rep_123&limit=50
Authorization: Bearer <token>
```

**Response**:
```json
{
  "success": true,
  "data": {
    "wins": [
      {
        "appointment_id": "apt_123",
        "lead_id": "lead_456",
        "contact_name": "John Doe",
        "address": "123 Main St",
        "rep_name": "Jane Smith",
        "rep_id": "rep_123",
        "deal_size": 35000.0,
        "closed_at": "2025-11-24T15:00:00Z",
        "service_type": "roofing",
        "scheduled_start": "2025-11-24T10:00:00Z"
      }
    ],
    "total": 15,
    "date_from": "2025-10-25T00:00:00Z",
    "date_to": "2025-11-24T23:59:59Z"
  }
}
```

---

### **11. Request Review Follow-Up**

**Request**:
```bash
POST /api/v1/reviews/request
Authorization: Bearer <token>
Content-Type: application/json

{
  "appointment_id": "apt_123",
  "channel": "sms",
  "template_id": "review_template_1"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "review_request_id": "review_req_789",
    "appointment_id": "apt_123",
    "contact_card_id": "contact_789",
    "channel": "sms",
    "status": "queued",
    "created_at": "2025-11-24T16:30:00Z"
  }
}
```

---

## 🔒 **Security & Multi-Tenancy**

All endpoints:
- ✅ Enforce RBAC via `@require_role()` decorator
- ✅ Scope by `company_id` from auth context
- ✅ Validate tenant isolation (404 if entity belongs to another company)
- ✅ Use existing error response patterns

---

## 📊 **Event Bus Integration**

All endpoints emit events via `emit_domain_event()`:
- Events follow standard envelope format
- Include tenant_id, lead_id, payload
- Non-blocking emission

---

## 🧪 **Next Steps**

1. **Run Tests**: Create test files under `app/tests/` for each endpoint group
2. **Verify Imports**: Ensure all imports resolve correctly
3. **Check Linter**: Run linter on all new files
4. **Update OpenAPI**: Verify all endpoints appear in `/docs`
5. **Integration Testing**: Test with frontend client

---

## ✅ **Completion Status**

- ✅ All 9 endpoint groups implemented
- ✅ All routers registered in `main.py`
- ✅ All schemas created
- ✅ Event emissions added
- ✅ Multi-tenant scoping enforced
- ✅ RBAC enforced
- ⏳ Tests pending (to be created)

---

**End of Summary**


