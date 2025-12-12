# Cleanup Seed Data

## Overview

The `cleanup_seed_data.py` script removes all demo/seed data from the database, allowing you to start fresh with real data.

## What Gets Removed

- Demo company (`otto-demo-co`)
- Demo users:
  - `csr@otto-demo.com`
  - `salesrep@otto-demo.com`
  - `manager@otto-demo.com`
- All associated data:
  - Contact cards
  - Leads
  - Calls
  - Call transcripts
  - Call analyses
  - Appointments
  - Recording sessions
  - Recording transcripts
  - Recording analyses
  - Rep shifts
  - Tasks
  - Message threads
  - Missed call queue entries
  - Sales reps
  - Sales managers

## What Gets Preserved

- Real companies and users (not demo)
- Database structure (tables, schemas)
- Any data not created by seed scripts

## Usage

### Local Development

```bash
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard
export DATABASE_URL="your-database-url"
python3 -m scripts.cleanup_seed_data
```

### Railway Production

```bash
# Option 1: Using Railway CLI
railway run python -m scripts.cleanup_seed_data

# Option 2: Using saved DATABASE_URL
export DATABASE_URL="your-railway-postgres-url"
python3 -m scripts.cleanup_seed_data
```

## After Cleanup

After running the cleanup script:

1. ✅ APIs will return empty results (empty arrays, zero counts)
2. ✅ No errors - all endpoints handle empty data gracefully
3. ✅ Ready for real data - start making real calls, appointments, etc.
4. ✅ Shunya integration will work with real data

## Re-seeding (if needed)

If you need demo data again for testing:

```bash
python3 -m scripts.seed_demo_data
```

## Safety

- The script only deletes data for the demo company (`otto-demo-co`)
- Real companies and users are preserved
- The script is idempotent - safe to run multiple times
- If no demo company exists, the script exits gracefully

