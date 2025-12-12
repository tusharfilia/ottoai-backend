# Re-running the Seed Script on Railway Database

After Railway deploys your changes, you can re-run the seed script to ensure all demo data is created under the correct org ID.

## Step 1: Get Railway Database URL

1. Go to your Railway dashboard
2. Navigate to your **Postgres** service
3. Click on the **"Variables"** tab
4. Find the `DATABASE_URL` variable (or `POSTGRES_URL`)
5. Copy the **external/public** database URL (not the internal one)

   The external URL looks like:
   ```
   postgresql://postgres:password@containers-us-west-xxx.railway.app:5432/railway
   ```

   ⚠️ **Important**: Use the **external/public** URL, not the internal one (`postgres.railway.internal`)

## Step 2: Run the Seed Script Locally

From your local machine, run:

```bash
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard

# Set the DATABASE_URL environment variable with Railway's external URL
export DATABASE_URL="postgresql://postgres:password@containers-us-west-xxx.railway.app:5432/railway"

# Run the seed script
python3 -m scripts.seed_demo_data
```

Or run it in one line:

```bash
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard && \
DATABASE_URL="your-railway-postgres-external-url" python3 -m scripts.seed_demo_data
```

## Step 3: Verify the Output

You should see output like:

```
🌱 Starting demo data seed script...
🌱 Seeding demo data for CSR dashboard...
✓ Using existing demo company: otto-demo-co (org_36EW2DYBw4gpJaL4ASL2ZxFZPO9)
✓ Using existing demo CSR user: csr@otto-demo.com (user_36EWfrANnNFNL2dN3wdAo9z2FK2)
✓ Created 15 demo contact cards
✓ Created 15 demo leads with various statuses
...
✅ Demo data seeded successfully!
```

## What the Script Does

The script is **idempotent** - it's safe to run multiple times:

- ✅ Reuses existing demo company/user if they exist
- ✅ Updates the user's role to `csr` if it was wrong
- ✅ Deletes and recreates demo data (contacts, leads, calls, etc.) to ensure freshness
- ✅ All data is scoped to the correct org ID: `org_36EW2DYBw4gpJaL4ASL2ZxFZPO9`

## Alternative: Run via Railway CLI

If you have Railway CLI installed, you can also run it directly in Railway:

```bash
railway run python -m scripts.seed_demo_data
```

This automatically uses Railway's environment variables, so you don't need to set `DATABASE_URL` manually.





