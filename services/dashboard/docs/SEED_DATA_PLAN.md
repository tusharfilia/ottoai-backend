# Demo Data Seed Plan for Sales Rep & Executive Platforms

## 📋 What I Need From You

### 1. **Clerk User IDs & Emails**

Please provide the following Clerk demo user credentials:

#### **Sales Rep Demo User:**
- Clerk User ID: `?`
- Email: `?`
- Username: `?`
- Name: `?`

#### **Executive/Manager Demo User:**
- Clerk User ID: `?`
- Email: `?`
- Username: `?`
- Name: `?`

### 2. **Company Setup**

- **Option A**: Use the same company (`org_36EW2DYBw4gpJaL4ASL2ZxFZPO9`) for all three roles
  - ✅ Pros: Shows multi-tenant separation, all users see same company data
  - ✅ Cons: Data scoping becomes more important
  
- **Option B**: Create separate demo companies for each role
  - ✅ Pros: Complete isolation
  - ✅ Cons: More complex setup

**Recommendation**: Use the **same company** (Option A) - this is more realistic and tests multi-tenant security properly.

### 3. **Any Specific Data Scenarios?**

Do you want any specific scenarios like:
- High-performing rep vs. struggling rep?
- Recent wins vs. long sales cycles?
- Specific objection patterns?
- Different appointment statuses?

---

## 🎯 What I'll Create

### **Sales Rep Platform Demo Data**

#### **User Setup:**
- Sales Rep user with `role="sales_rep"`
- Linked to SalesRep profile
- Same company as CSR (`org_36EW2DYBw4gpJaL4ASL2ZxFZPO9`)

#### **Data Created:**
1. **Appointments** (assigned to this rep):
   - 8-10 appointments (mix of upcoming/past)
   - Some with recording sessions
   - Mix of statuses: scheduled, completed, no_show, cancelled
   - Realistic locations with geo coordinates

2. **Rep Shifts**:
   - 10-15 shift records (past 2 weeks)
   - Mix of statuses: completed, active, planned
   - Clock-in/out times
   - Some shifts with notes

3. **Recording Sessions**:
   - 3-5 recording sessions linked to appointments
   - Some with transcripts
   - Some with analyses (coaching tips)

4. **Calls** (assigned to rep):
   - 10-15 calls (inbound/outbound)
   - Linked to appointments/contacts
   - Mix of outcomes (booked, bought, lost)

5. **Leads** (assigned to rep):
   - 5-8 leads in various stages
   - Linked to contacts

6. **Performance Data**:
   - Call analyses with coaching tips
   - Objection data
   - Sentiment scores

---

### **Executive/Manager Platform Demo Data**

#### **User Setup:**
- Executive user with `role="manager"`
- Linked to SalesManager profile (if needed)
- Same company as CSR/Rep

#### **Data Created:**
1. **Company-Wide Metrics Data**:
   - All calls across all reps (already have ~30 from CSR seed)
   - All appointments across all reps (already have 5)
   - All leads across company (already have 15)

2. **Additional Rep Data**:
   - 1-2 more sales reps (in addition to existing 2)
   - Rep performance metrics
   - Manager-rep assignments

3. **Revenue Intelligence Data**:
   - Won deals with deal sizes
   - Lost deals with reasons
   - Pipeline stages

4. **Team Performance Data**:
   - Rep leaderboard data
   - Coaching opportunities across all reps
   - Objection trends

5. **Executive-Specific Metrics**:
   - Booking rates over time
   - Top objections
   - Revenue forecasts
   - Growth metrics

---

## 📊 Data Relationships

```
Company (org_36EW2DYBw4gpJaL4ASL2ZxFZPO9)
├── CSR User (user_36EWfrANnNFNL2dN3wdAo9z2FK2) ✅ Already created
├── Sales Rep User (?) ⏳ To create
│   ├── SalesRep Profile
│   ├── Appointments (assigned to rep)
│   ├── Rep Shifts
│   ├── Recording Sessions
│   └── Calls (assigned to rep)
├── Executive User (?) ⏳ To create
│   └── SalesManager Profile (if needed)
└── Existing Data (from CSR seed):
    ├── 15 Contact Cards
    ├── 15 Leads
    ├── 36 Calls
    ├── 2 Sales Reps
    └── 5 Appointments
```

---

## 🚀 Implementation Plan

1. **Extend existing seed script** (`scripts/seed_demo_data.py`)
   - Add functions for Sales Rep data
   - Add functions for Executive data
   - Make it modular (can seed individual roles)

2. **Create separate seed scripts** (alternative approach):
   - `scripts/seed_sales_rep_data.py`
   - `scripts/seed_executive_data.py`
   - `scripts/seed_all_demo_data.py` (runs all three)

3. **Ensure data relationships**:
   - Sales Rep appointments link to existing contacts
   - Executive sees all company data
   - Proper role-based data scoping

---

## ❓ Questions for You

1. **Clerk User IDs**: Can you provide the Clerk User IDs and emails for:
   - Sales Rep demo user
   - Executive demo user

2. **Company**: Same company for all, or separate?

3. **Data Volume**: 
   - How many appointments for the rep? (8-10?)
   - How many shifts? (10-15 over 2 weeks?)
   - Any specific scenarios you want to showcase?

4. **Timeline**: When do you need this ready?

Once you provide the Clerk IDs, I can start building the seed scripts! 🚀





