# Call Analysis Schema Conflict Explanation

## The Problem

There are **two different schemas** for the `call_analysis` table, created by two different migration systems:

### Schema 1: Legacy SQL Migration (`002_post_call_analysis.sql`)
**Created:** Unknown (raw SQL file, not part of Alembic)
**Purpose:** Basic call analysis with simple metrics

**Key Columns:**
- `id` - SERIAL (auto-increment integer)
- `company_id` - VARCHAR(255) - **Note: uses `company_id`, not `tenant_id`**
- `sales_rep_id` - VARCHAR(255)
- `call_metrics` - JSONB (duration, success, etc.)
- `ai_insights` - JSONB (basic AI analysis)
- `coaching_recommendations` - JSONB (simple recommendations)
- `performance_score` - JSONB (overall score)
- `analyzed_at` - TIMESTAMP
- `analysis_version` - VARCHAR(50)

**Used By:**
- `PostCallAnalysisService` (legacy service)
- Tries to insert data using this schema

### Schema 2: Modern Alembic Migration (`003_add_ai_models.py`)
**Created:** 2025-10-09 (Alembic migration)
**Purpose:** UWC-powered AI analysis with advanced features

**Key Columns:**
- `id` - String (UUID) - **Note: different type than Schema 1**
- `tenant_id` - String - **Note: uses `tenant_id`, not `company_id`**
- `call_id` - Integer
- `uwc_job_id` - String (REQUIRED) - Links to UWC analysis job
- `objections` - JSON (detected objections)
- `objection_details` - JSON (detailed objection info)
- `sentiment_score` - Float
- `engagement_score` - Float
- `coaching_tips` - JSON (different structure than `coaching_recommendations`)
- `sop_stages_completed` - JSON
- `sop_stages_missed` - JSON
- `sop_compliance_score` - Float
- `rehash_score` - Float
- `talk_time_ratio` - Float
- `lead_quality` - String
- `conversion_probability` - Float
- `meeting_segments` - JSON
- `analyzed_at` - DateTime
- `analysis_version` - String

**Used By:**
- `CallAnalysis` SQLAlchemy model (current)
- UWC analysis pipeline
- All modern features (objections, SOP compliance, etc.)

## Why This Happened

1. **Legacy Migration System:** The old SQL file (`002_post_call_analysis.sql`) was likely created before Alembic was set up, or was meant to be run manually.

2. **Schema Evolution:** When UWC integration was added, a new schema was created via Alembic (`003_add_ai_models.py`) that better supports:
   - UWC job tracking (`uwc_job_id`)
   - Advanced AI features (objections, SOP compliance, sentiment)
   - Multi-tenant architecture (`tenant_id` instead of `company_id`)

3. **Migration Conflict:** Both migrations try to create the same table with different schemas. The Alembic migration (`003_add_ai_models.py`) **won** because:
   - It's part of the automated migration system
   - It was run when the database was set up
   - The SQL file was likely never run, or was overwritten

## Current Database State

**The database currently has Schema 2** (the modern UWC schema) because:
- Alembic migrations are tracked and run automatically
- The error message confirms: `column "company_id" of relation "call_analysis" does not exist`
- The model in `app/models/call_analysis.py` matches Schema 2

## The Conflict

`PostCallAnalysisService` is trying to insert data using **Schema 1** (legacy):
```python
INSERT INTO call_analysis (
    call_id, company_id, sales_rep_id, analyzed_at,  # ❌ company_id doesn't exist
    call_metrics, ai_insights, coaching_recommendations,  # ❌ These columns don't exist
    performance_score, analysis_version, created_at
)
```

But the database has **Schema 2** (modern):
- Uses `tenant_id` (not `company_id`)
- Has `objections`, `coaching_tips` (not `call_metrics`, `coaching_recommendations`)
- Requires `uwc_job_id` (not provided by legacy service)

## Solution

We've temporarily **disabled** the legacy `PostCallAnalysisService` storage because:
1. The modern schema is populated by **UWC analysis**, not this legacy service
2. The legacy service doesn't have the data structure needed for Schema 2
3. UWC provides much better analysis (objections, SOP compliance, sentiment, etc.)

## What Should Happen

### Option 1: Remove Legacy Service (Recommended)
- Delete or deprecate `PostCallAnalysisService`
- All analysis should go through UWC pipeline
- UWC populates the modern `call_analysis` table correctly

### Option 2: Migrate Legacy Service
- Update `PostCallAnalysisService` to use Schema 2
- Map legacy data fields to new schema
- Add `uwc_job_id` requirement
- Change `company_id` → `tenant_id`

### Option 3: Keep Both (Not Recommended)
- Create a separate table for legacy analysis
- Keep both systems running
- Adds complexity and confusion

## Migration History

The modern schema has been extended with additional migrations:
- `20251208000000_add_followup_recommendations_to_call_analysis.py` - Added `followup_recommendations`
- `20251208000001_add_compliance_details_to_call_analysis.py` - Added compliance fields
- `20251208000003_add_canonical_enums_to_models.py` - Added `booking_status`, `call_type`, `call_outcome_category`

All of these assume Schema 2 (modern schema).

## Recommendation

**Use UWC for all call analysis.** The legacy `PostCallAnalysisService` should be:
1. Deprecated and removed, OR
2. Updated to work with Schema 2, OR  
3. Kept only for backward compatibility with old data (if any exists)

The current fix (skipping storage) is correct for now, but we should decide on one of the options above for a permanent solution.

