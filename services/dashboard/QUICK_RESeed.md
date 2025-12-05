# Quick Re-Seed Instructions

## ✅ Deployment Status: SUCCESS

Railway deployment completed successfully. The middleware fix for `org:csr` role mapping is now live.

## 🚀 Re-Run Seed Script

**Option 1: Using your saved Railway DATABASE_URL**

If you still have the Railway DATABASE_URL from before, run:

```bash
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard
DATABASE_URL="your-railway-external-postgres-url" python3 -m scripts.seed_demo_data
```

**Option 2: Get fresh Railway DATABASE_URL**

1. Go to Railway Dashboard → Your Postgres Service → Variables tab
2. Copy the `DATABASE_URL` (external/public URL, not internal)
3. Run the seed script:

```bash
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard
export DATABASE_URL="paste-your-railway-url-here"
python3 -m scripts.seed_demo_data
```

**Option 3: Railway CLI (if installed)**

```bash
railway run python -m scripts.seed_demo_data
```

## What Will Happen

- ✅ Finds/creates company with org ID: `org_36EW2DYBw4gpJaL4ASL2ZxFZPO9`
- ✅ Updates user role to `csr` (fixes any wrong role)
- ✅ Creates fresh demo data (contacts, leads, calls, appointments, etc.)

The script is safe to run multiple times - it won't create duplicates.



