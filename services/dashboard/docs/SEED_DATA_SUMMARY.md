# Demo Data Seed Summary

## ✅ What Was Created

The `seed_demo_data.py` script now seeds demo data for **all three platforms**:

### 👤 **CSR Platform** (`csr@otto-demo.com`)
- **User ID**: `user_36EWfrANnNFNL2dN3wdAo9z2FK2`
- **Role**: `csr` (Clerk role: `org:csr`)
- **Data Created**:
  - 15 contact cards
  - 15 leads (various statuses)
  - 36 calls (company-wide, not assigned to reps)
  - 14 call transcripts
  - 17 call analyses
  - 5 appointments (CSR dashboard view)
  - 8 tasks
  - SMS message threads

### 📱 **Sales Rep Platform** (`salesrep@otto-demo.com`)
- **User ID**: `user_36M3F0kllDOemX3prAPP1Zb8C5f`
- **Role**: `sales_rep` (Clerk role: `org:rep`)
- **Performance Profile**: **High-Performing**
- **Data Created**:
  - 10 appointments (assigned to this rep)
    - 70% completed with wins
    - 20% upcoming
    - 10% no-show/cancelled
    - 75% win rate on completed appointments
  - 10-15 rep shifts (past 2 weeks, workdays only)
    - Mix of active, completed, and skipped
    - Realistic clock-in/out times
  - 5 recording sessions (linked to completed appointments)
    - With geofence data
    - Transcription and analysis completed
  - 15 calls (assigned to this rep)
    - 80% booked rate
    - 60% bought rate
    - Longer call durations (120-600 seconds)

### 👔 **Executive/Manager Platform** (`manager@otto-demo.com`)
- **User ID**: `user_36M3Kp5NQjnGhcmu5NM8nhOCqg2`
- **Role**: `manager` (Clerk role: `org:manager`)
- **Data Access**: **Company-wide** (sees all data)
- **Data Available**:
  - All contact cards (15)
  - All leads (15)
  - All calls (36 CSR + 15 Sales Rep + generic rep calls)
  - All appointments (5 CSR + 10 Sales Rep)
  - All sales reps (2 generic + 1 demo Sales Rep)
  - Company-wide metrics and analytics

### 📊 **Performance Variation**

#### **High-Performing Sales Rep** (Demo Sales Rep User)
- 15 calls, 80% booked, 60% bought
- 10 appointments, 75% win rate
- Longer call durations
- More completed shifts

#### **Low-Performing Sales Rep** (Generic Rep: "Bob Closer")
- 8 calls, 40% booked, 20% bought
- Lower appointment win rates (35%)
- Shorter call durations
- Some skipped shifts

#### **High-Performing CSR** (Demo CSR User)
- Better booking rates on calls
- More completed tasks
- Faster response times (reflected in call data)

---

## 🚀 How to Run

```bash
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard

# Set Railway DATABASE_URL
export DATABASE_URL="postgresql://postgres:password@yamabiko.proxy.rlwy.net:56986/railway"

# Run the seed script
python3 -m scripts.seed_demo_data
```

---

## 📋 Demo Credentials Summary

| Platform | Email | Clerk User ID | Clerk Role | Backend Role |
|----------|-------|---------------|------------|--------------|
| CSR | `csr@otto-demo.com` | `user_36EWfrANnNFNL2dN3wdAo9z2FK2` | `org:csr` | `csr` |
| Sales Rep | `salesrep@otto-demo.com` | `user_36M3F0kllDOemX3prAPP1Zb8C5f` | `org:rep` | `sales_rep` |
| Manager | `manager@otto-demo.com` | `user_36M3Kp5NQjnGhcmu5NM8nhOCqg2` | `org:manager` | `manager` |

**Company/Org**: `org_36EW2DYBw4gpJaL4ASL2ZxFZPO9` (otto-demo-co)

---

## 🎯 What Each Platform Sees

### **CSR Dashboard**
- Company-wide calls (not assigned to specific reps)
- All leads
- Appointments (can see all, but filters by CSR context)
- Tasks assigned to CSR
- SMS message threads

### **Sales Rep Mobile App**
- **Only their own** appointments (10 assigned to demo Sales Rep)
- **Only their own** calls (15 assigned to demo Sales Rep)
- **Only their own** rep shifts (10-15 shifts)
- **Only their own** recording sessions (5 sessions)
- Performance metrics (high-performing profile)

### **Executive/Manager Dashboard**
- **All** company data
- **All** calls across all reps
- **All** appointments across all reps
- **All** leads
- Company-wide metrics
- Rep performance comparisons
- Revenue intelligence

---

## 🔄 Idempotency

The script is **idempotent** - safe to run multiple times:
- Reuses existing users/company
- Updates user roles if needed
- Deletes and recreates demo data to ensure freshness
- All data scoped to the same company

---

## 📝 Notes

- **High vs Low Performance**: The demo Sales Rep user is high-performing. One generic rep ("Bob Closer") is low-performing for comparison.
- **CSR Performance**: CSR performance variation is shown through call booking rates and task completion.
- **Manager Access**: Manager sees all company data - no additional seeding needed beyond what's created for CSR/Rep platforms.



