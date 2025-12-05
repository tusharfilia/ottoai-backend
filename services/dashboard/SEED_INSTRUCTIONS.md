# Step-by-Step Guide: Running the Demo Data Seed Script

## 📋 Prerequisites

- You should be in the dashboard service directory
- Have the Railway DATABASE_URL ready

---

## 🚀 Steps to Run Seed Script

### Step 1: Navigate to the Dashboard Directory

```bash
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard
```

### Step 2: Set the Database URL

Export the Railway database URL as an environment variable:

```bash
export DATABASE_URL="postgresql://postgres:EqYHYqcKNulbDZyRjCeMWcuAXxhYvobT@yamabiko.proxy.rlwy.net:56986/railway"
```

### Step 3: Run the Seed Script

Run the seed script using Python:

```bash
python3 -m scripts.seed_demo_data
```

---

## 🎯 All Commands in One Block (Copy-Paste Ready)

```bash
# Navigate to dashboard directory
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard

# Set database URL
export DATABASE_URL="postgresql://postgres:EqYHYqcKNulbDZyRjCeMWcuAXxhYvobT@yamabiko.proxy.rlwy.net:56986/railway"

# Run seed script
python3 -m scripts.seed_demo_data
```

---

## ✅ Expected Output

You should see output like:

```
🌱 Seeding demo data for all platforms (CSR, Sales Rep, Executive)...
✓ Created demo company: otto-demo-co (org_36EW2DYBw4gpJaL4ASL2ZxFZPO9)
✓ Created demo CSR user: csr@otto-demo.com
✓ Created 15 demo contact cards
✓ Created 15 demo leads
...
📱 Creating Sales Rep platform demo data...
✓ Created demo Sales Rep user: salesrep@otto-demo.com
...
👔 Creating Executive/Manager platform demo data...
✓ Created demo Manager user: manager@otto-demo.com

✅ Demo data seeded successfully!
```

---

## 🔍 Verify the Data Was Created

After running, you can verify the data was created by:

1. **Checking the logs** - You should see all the "✓ Created" messages
2. **Logging into the apps** - Try logging in as one of the demo users:
   - `csr@otto-demo.com`
   - `salesrep@otto-demo.com`
   - `manager@otto-demo.com`

---

## ⚠️ Troubleshooting

### If you get "DATABASE_URL not set" error:

Make sure you exported the DATABASE_URL in the same terminal session:

```bash
echo $DATABASE_URL
```

If it's empty, re-export it:

```bash
export DATABASE_URL="postgresql://postgres:EqYHYqcKNulbDZyRjCeMWcuAXxhYvobT@yamabiko.proxy.rlwy.net:56986/railway"
```

### If you get "Module not found" errors:

Make sure you're in the correct directory:

```bash
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard
```

### If you get connection errors:

- Check that the DATABASE_URL is correct
- Make sure you're using the **public/external** Railway URL (not the internal one)
- Verify your internet connection

---

## 🔄 Re-running the Script

The script is **idempotent** - safe to run multiple times. Just run it again:

```bash
python3 -m scripts.seed_demo_data
```

It will update existing data and recreate demo data as needed.

---

## 📝 Notes

- The script creates demo data for all three platforms (CSR, Sales Rep, Executive)
- All data is scoped to the same company (`org_36EW2DYBw4gpJaL4ASL2ZxFZPO9`)
- The script includes high-performing and low-performing scenarios
- All demo users are in the same Clerk organization

---

## 🎉 Next Steps

After seeding:
1. Test logging in as each demo user
2. Verify data appears in each platform
3. Share credentials with your frontend engineers



