# Tasks and Message Threads Explained

## 📋 What Are Tasks?

**Tasks** are **action items/to-do items** that track things CSRs, Reps, and Managers need to do.

### Examples:
- "Follow up at 5pm"
- "Customer deciding with spouse - check back in 2 days"
- "Send contract to customer"
- "Request photos from customer"
- "Call back about pricing objections"

### Key Features:
- **Linked to entities**: Can be linked to a ContactCard, Lead, Appointment, or Call
- **Assigned to roles**: Can be assigned to CSR, Rep, Manager, or AI
- **Created by**: Can be created by:
  - **Otto AI** (automatic, based on call analysis)
  - **Shunya/UWC AI** (automatic, based on recording analysis)
  - **Manual** (human-created)
- **Status**: Can be `open`, `completed`, `overdue`, or `cancelled`
- **Due dates**: Can have scheduled due dates/times
- **Priority**: Can be marked as `high`, `medium`, or `low`

### Where They're Used:
- **CSR Dashboard**: Shows tasks assigned to the CSR (follow-ups, callbacks, etc.)
- **Sales Rep Mobile**: Shows tasks assigned to the rep (follow-ups, appointment prep, etc.)
- **Executive Dashboard**: Shows all tasks across the company (for managers to oversee)

---

## 💬 What Are Message Threads?

**Message Threads** are **SMS/text message history** between customers and your company.

### Examples:
- Customer texts: "What time is my appointment?"
- CSR replies: "Your appointment is tomorrow at 10 AM"
- Otto automated: "Reminder: Your appointment is in 1 hour"
- Customer texts: "Can we reschedule?"
- Rep texts: "On my way! ETA 15 minutes"

### Key Features:
- **Stored per contact**: All messages linked to a ContactCard
- **Sender tracking**: Records who sent it:
  - `customer`
  - `csr`
  - `rep`
  - `manager`
  - `otto` (Otto automation)
  - `shunya` (Shunya/UWC automation)
- **Message types**:
  - `manual` (human-sent)
  - `automated` (AI/automation sent)
- **Direction**: `inbound` (customer → company) or `outbound` (company → customer)
- **Delivery tracking**: Tracks if message was delivered, read, etc.
- **Provider integration**: Integrates with Twilio, CallRail, etc.

### Where They're Used:
- **CSR Dashboard**: Shows SMS conversation history with customers
- **Sales Rep Mobile**: Shows SMS conversations with their leads
- **Contact Details**: Shows all SMS history for a specific contact

### What Gets Stored:
- All messages (Otto auto, CSR→customer, customer→Otto AI)
- Appointment confirmations
- Reminders
- Voicemail transcripts (if converted to text)
- Missed call recovery messages

---

## ⚠️ Why Were They Skipped?

The seed script output showed:
```
ℹ️ 'tasks' table not found in this database; skipping task seeding.
ℹ️ 'message_threads' table not found in this database; skipping SMS thread seeding.
```

**Reason**: These database tables haven't been created yet in your Railway database. They need to be migrated first.

### What This Means:

1. **The models exist** - The code for Tasks and MessageThreads is already written
2. **The tables don't exist** - The database migrations haven't been run yet
3. **The script gracefully skips them** - This is fine for now! The core demo data (contacts, leads, calls, appointments) is more important

### Are They Critical?

- **Tasks**: Nice-to-have for demo, but not critical. You can still demo the platform without them.
- **Message Threads**: Nice-to-have for demo, but not critical. The core call/appointment data is more important for initial frontend development.

---

## 🚀 If You Want to Add Them Later

If you want to create these tables and seed task/message data:

1. **Check if migrations exist** for these tables:
   ```bash
   ls migrations/versions/ | grep -E "(task|message)"
   ```

2. **Run migrations** if they exist:
   ```bash
   alembic upgrade head
   ```

3. **Re-run the seed script** - it will automatically create task/message data once the tables exist

---

## 📊 Current Demo Data Status

✅ **What's Working** (seeded successfully):
- 15 contact cards
- 15 leads
- 69 calls (31 CSR + 15 Sales Rep + 23 generic reps)
- 11 call transcripts
- 12 call analyses
- 15 appointments
- 10 rep shifts
- 5 recording sessions

⏭️ **What's Skipped** (tables don't exist yet):
- Tasks (0 tasks)
- Message threads (0 messages)

**Bottom Line**: You have plenty of demo data to test with! Tasks and messages are bonus features that can be added later when those tables are migrated.



