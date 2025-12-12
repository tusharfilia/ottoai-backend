# AZ Roof Demo Pilot - Step-by-Step Execution Guide
## Real-Time Execution with Frontend + DB Verification

**Backend**: `https://ottoai-backend-production.up.railway.app`  
**Clerk Org**: `azroofdemo` (org_id: `org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs`)  
**Users**: 
- Manager: `azmanager@demo.com`
- CSR: `azcsr@demo.com`
- Sales Rep: `azsalesrep@demo.com`
**CallRail Number**: `+12028313219`

---

## Phase 1: Pre-Flight Setup (15 minutes)

### Step 1.1: Verify Company Record Exists

**Action**: Check if company record exists in DB

**Option 1: Via API (Recommended - No DB Access Needed)**

**Where to Run**: Any terminal on your local machine (Terminal.app on Mac, Command Prompt/PowerShell on Windows, or any Linux terminal). The curl command makes an HTTP request over the internet, so it doesn't matter where you run it from.

**Step 1**: Get Manager JWT Token

**Method A: From Browser Network Tab (Easiest & Most Reliable)**
1. Open your frontend app in browser: https://otto-omega.vercel.app (or your frontend URL)
2. Log in as `azmanager@demo.com`
3. Open browser DevTools:
   - **Mac**: `Cmd + Option + I` or `F12`
   - **Windows/Linux**: `F12` or `Ctrl + Shift + I`
4. Go to **Network** tab
5. Make any API request (e.g., navigate to dashboard, which will trigger API calls)
6. Find any API request to `ottoai-backend-production.up.railway.app`
7. Click on the request → Go to **Headers** tab
8. Scroll down to **Request Headers** section
9. Look for `Authorization: Bearer eyJhbGciOiJ...`
10. Copy the entire token after "Bearer " (the long string starting with `eyJ`)

**Method B: From Browser Application/Storage Tab**
1. Open frontend app, log in as manager
2. Open DevTools → **Application** tab (Chrome) or **Storage** tab (Firefox)
3. Look in:
   - **Local Storage** → `https://your-frontend-domain.com`
   - **Session Storage** → `https://your-frontend-domain.com`
   - **Cookies** → Look for Clerk-related cookies
4. Common Clerk token keys:
   - `__clerk_db_jwt` or `__session`
   - `clerk-session` or similar
5. Copy the token value

**Method C: From Clerk Dashboard** (If you have API access)
1. Log into Clerk Dashboard: https://dashboard.clerk.com
2. Go to **Users** → Find `azmanager@demo.com`
3. Click on the user → **Sessions** tab
4. Note: Clerk Dashboard doesn't directly show JWT tokens, but you can use Clerk API to generate one

**Method D: Use Clerk API to Generate Token** (Advanced)
```bash
# Get Clerk secret key from Railway variables or Clerk dashboard
CLERK_SECRET_KEY="your_clerk_secret_key"

# Use Clerk API to create a session token (requires Clerk API access)
curl -X POST "https://api.clerk.com/v1/sessions" \
  -H "Authorization: Bearer $CLERK_SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_36kub5UX3lxl2VivI3EQnqn7iOU"
  }'
```

**Recommended**: Use **Method A (Network Tab)** - it's the most reliable and shows the exact token your frontend is using.

**Step 2**: Query Company via API

**Open any terminal** (Terminal.app, iTerm, VS Code terminal, etc.) and run:

**Correct Syntax** (use single quotes for URL, double quotes for headers):
```bash
# ⚠️ IMPORTANT: The endpoint is /company/... NOT /api/v1/company/...
curl -X GET 'https://ottoai-backend-production.up.railway.app/company/org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs' \
  -H 'Authorization: Bearer YOUR_MANAGER_JWT_TOKEN' \
  -H 'Content-Type: application/json'
```

**Note**: The company router uses prefix `/company`, not `/api/v1/company`. The correct path is:
- ✅ Correct: `/company/{company_id}`
- ❌ Wrong: `/api/v1/company/{company_id}`

**Why Single Quotes?**
- **Single quotes (`'`)**: Treats everything literally - no shell interpretation
- **Double quotes (`"`)**: Shell may interpret special characters, causing URL encoding issues

**Common Mistakes**:
- ❌ Wrong: Using quotes around the company ID in the URL path
  ```bash
  curl ... '/api/v1/company/"org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs"'  # WRONG - quotes in URL
  ```
- ✅ Correct: No quotes around the ID in the URL path
  ```bash
  curl ... '/api/v1/company/org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs'  # CORRECT
  ```

**Alternative: Escape Special Characters** (if you must use double quotes):
```bash
curl -X GET "https://ottoai-backend-production.up.railway.app/api/v1/company/org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs" \
  -H "Authorization: Bearer YOUR_MANAGER_JWT_TOKEN" \
  -H "Content-Type: application/json"
```
This should work too, but single quotes are safer.

**Replace `YOUR_MANAGER_JWT_TOKEN`** with the actual token from Step 1.

**Example** (with a real-looking token):
```bash
curl -X GET "https://ottoai-backend-production.up.railway.app/api/v1/company/org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json"
```

**Note**: If you don't have `curl` installed, you can also use:
- **Postman** (GUI tool)
- **VS Code REST Client extension**
- **Browser** (for GET requests only, but won't work for POST/PUT)
- **Python requests**:
  ```python
  import requests
  response = requests.get(
      "https://ottoai-backend-production.up.railway.app/api/v1/company/org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs",
      headers={"Authorization": "Bearer YOUR_TOKEN"}
  )
  print(response.json())
  ```

**Expected Response** (if exists):
```json
{
  "id": "org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs",
  "name": "AZ Roof Demo",
  "phone_number": "+12028313219",
  "address": "...",
  "created_at": "2025-01-XX..."
}
```

**Expected Response** (if missing - 404 error):
```json
{
  "type": "https://tools.ietf.org/html/rfc7231#section-6.5",
  "title": "HTTP Error",
  "detail": "Not Found",
  "status": 404
}
```

**⚠️ If You Get 404 (Company Doesn't Exist)**:

The company record needs to be created. Unfortunately, **there is NO API endpoint that allows you to create a company with an existing Clerk org ID**. Here's why:

- `POST /api/v1/company/` - Creates a NEW Clerk org (won't match your existing `org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs`)
- `POST /api/v1/onboarding/company-basics` - Requires company to already exist (will fail with "Company not found")
- `PUT /api/v1/company/{id}` - Updates existing company (returns 404 if doesn't exist)

**Solution: Create Company Record via Database** (Only Option)

Since the Clerk org already exists, you must create the company record in the database with the existing Clerk org ID. There's no API endpoint for this.

**Option A: Via Railway CLI** (Recommended - Easiest)

**Step 1**: Install Railway CLI (if not installed)
```bash
# Install Railway CLI (works with your current npm version)
npm i -g @railway/cli

# If you get permission errors, use:
sudo npm i -g @railway/cli

# Verify installation
railway --version
```

**Note**: Railway CLI works with Node.js v18+ and npm 10+, so you don't need to upgrade npm.

**Step 2**: Login to Railway
```bash
# Login to Railway (opens browser for authentication)
railway login
```

**Step 3**: Link to your project
```bash
# Option A: If you're in your project directory
cd /path/to/your/project
railway link

# Option B: Link by project ID (if you know it)
railway link --project a11beaf2-6e4c-4953-994b-ba43888ed205

# Option C: Select from list
railway link
# (Will show list of projects to choose from)
```

**Step 4**: Connect to Postgres and create company

**Method A: Interactive psql Session** (Recommended)
```bash
# This command opens an interactive psql session
railway connect postgres
```

**What happens**: Railway CLI will:
1. Connect to your Postgres database
2. Open an interactive `psql` prompt that looks like:
   ```
   psql (15.x)
   Type "help" for help.
   
   railway=# 
   ```

**Step 5**: Run SQL commands in psql

Once you see the `railway=#` prompt, you're in psql. Type your SQL commands:
```sql
-- First, check if company already exists (and delete if wrong ID)
SELECT id, name, phone_number FROM companies WHERE id LIKE 'org_36ku5Z8Wjkhq4jZZbja%';

-- If you see a row with wrong ID (e.g., lowercase 'l' instead of capital 'I'), delete it:
DELETE FROM companies WHERE id = 'org_36ku5Z8Wjkhq4jZZbjaNalhFQGs';

-- Create company record with correct ID
INSERT INTO companies (id, name, phone_number, address, created_at, updated_at)
VALUES (
  'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs',
  'AZ Roof Demo',
  '+12028313219',
  '123 Main St',
  NOW(),
  NOW()
);

-- Verify it was created correctly
SELECT id, name, phone_number, address FROM companies WHERE id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
```

**Expected Output**:
```
 id                              | name        | phone_number   | address
---------------------------------+-------------+----------------+------------
 org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs | AZ Roof Demo | +12028313219  | 123 Main St
```

**Step 6**: Exit psql
```sql
-- Type this command to exit psql
\q
```

**What you'll see**: After typing `\q` and pressing Enter, you'll return to your terminal prompt.

---

**Method B: Run SQL directly without interactive session** (Alternative)

If you prefer to run SQL without entering an interactive session:

```bash
# Run a single SQL command directly
railway run psql $DATABASE_URL -c "INSERT INTO companies (id, name, phone_number, address, created_at, updated_at) VALUES ('org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs', 'AZ Roof Demo', '+12028313219', '123 Main St', NOW(), NOW()) ON CONFLICT (id) DO UPDATE SET phone_number = '+12028313219';"

# Or verify the record
railway run psql $DATABASE_URL -c "SELECT id, name, phone_number FROM companies WHERE id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';"
```

**Note**: This method runs the command and immediately exits - no interactive session.

---

**Troubleshooting Railway CLI Connection**:

**If `railway connect postgres` doesn't work**:
```bash
# Make sure you're linked to the project
railway link

# Or specify the service explicitly
railway connect postgres --service postgres-production-a5217

# Check available services
railway status
```

**If you get "command not found: psql"**:
- Railway CLI should handle this automatically
- If not, you may need to install `psql` locally, or use Railway Dashboard SQL editor instead

---

**Option B: Via Railway Dashboard** (Web UI - No CLI Needed)

**Step 1**: Go to Railway Dashboard
1. Visit: https://railway.app
2. Log in
3. Select your project: `ottoai-backend-production`

**Step 2**: Access Database
1. Click on your **Postgres** service
2. Go to **Data** tab
3. Click **Query** button (or **Connect** if available)

**Step 3**: Run SQL
```sql
-- Create company record
INSERT INTO companies (id, name, phone_number, address, created_at, updated_at)
VALUES (
  'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs',
  'AZ Roof Demo',
  '+12028313219',
  '123 Main St',
  NOW(),
  NOW()
);
```

**Step 4**: Verify
```sql
SELECT id, name, phone_number FROM companies WHERE id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
```

**Expected Result**: Should return 1 row with your company data.

---

**Option C: Via Direct Postgres Connection** (If You Have Connection String)

**Step 1**: Get Database URL from Railway
- Railway Dashboard → Postgres Service → **Variables** tab
- Find `DATABASE_URL` or `POSTGRES_URL`
- Copy the connection string

**Step 2**: Connect via psql
```bash
# Connect using connection string
psql "postgresql://user:password@host:port/database"

# Or if you have DATABASE_URL as environment variable
psql $DATABASE_URL
```

**Step 3**: Run SQL (same as Option A, Step 3)

---

**⚠️ Troubleshooting: Still Getting 404 After Creating Company?**

If you created the company but still get 404, there might be a mismatch between:
1. The `company_id` in the URL path
2. The `tenant_id` extracted from your JWT token
3. The `id` in the database

**Step 1: Verify Exact Match in Database**

Run this SQL query to see the exact ID (including any hidden characters):
```sql
-- Check exact ID with hex representation to catch hidden characters
SELECT 
  id, 
  name, 
  length(id) as id_length,
  encode(id::bytea, 'hex') as id_hex
FROM companies 
WHERE id LIKE 'org_36ku5Z8Wjkhq4jZZbja%';
```

**Step 2: Verify JWT Token's tenant_id**

Your JWT token should have `tenant_id` that matches the company `id`. Decode your JWT token and check:
- `tenant_id` field
- `company_id` field  
- `org_id` field

All should be: `org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs` (exact match, case-sensitive)

**Step 3: Check Backend Logs**

The backend should log the tenant_id it extracted. Check Railway logs:
```bash
railway logs --service ottoai-backend-production
```

Look for lines containing:
- `tenant_id`
- `Missing or invalid tenant_id`
- The trace_id from your error: `c5edb8dc-39cf-450f-b221-46d8a13e4961`

**Step 4: Manual Verification**

If the company exists in the database, verify it exists in the database:

**Step 1: Verify Company Exists in Database**

**Via Railway Dashboard**:
1. Go to Railway Dashboard → Postgres → Database → Data tab
2. Click on `companies` table
3. Look for a row with `id = org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs`
4. **Check for typos**: Make sure it's exactly `org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs` (capital "I", not lowercase "l")

**Via Railway CLI**:
```bash
railway connect postgres
```

Then in psql:
```sql
-- Check if company exists
SELECT id, name, phone_number FROM companies WHERE id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';

-- If no results, check for similar IDs (might have typo)
SELECT id, name FROM companies WHERE id LIKE 'org_36ku5Z8Wjkhq4jZZbja%';
```

**Step 2: If Company Doesn't Exist, Create It**

If the SELECT returns no rows, create the company:
```sql
INSERT INTO companies (id, name, phone_number, address, created_at, updated_at)
VALUES (
  'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs',
  'AZ Roof Demo',
  '+12028313219',
  '123 Main St',
  NOW(),
  NOW()
);
```

**Step 3: Verify Again**

After creating/verifying, try the API call again.

---

**After Creating Company Record, Verify via API Again**:

```bash
# ⚠️ Use /company/... NOT /api/v1/company/...
curl -X GET 'https://ottoai-backend-production.up.railway.app/company/org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs' \
  -H 'Authorization: Bearer YOUR_MANAGER_JWT_TOKEN' \
  -H 'Content-Type: application/json'
```

**Expected Response** (success):
```json
{
  "id": "org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs",
  "name": "AZ Roof Demo",
  "phone_number": "+12028313219",
  "address": "123 Main St",
  "created_at": "2025-01-XX...",
  "updated_at": "2025-01-XX..."
}
```

**Expected Response** (should now work):
```json
{
  "id": "org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs",
  "name": "AZ Roof Demo",
  "phone_number": "+12028313219",
  "address": "123 Main St",
  "created_at": "2025-01-XX...",
  "updated_at": "2025-01-XX..."
}
```

**⚠️ Common Issue: ID Typo**

If you see a company record but still get 404, check for typos in the `id` field:
- ✅ Correct: `org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs` (capital "I")
- ❌ Wrong: `org_36ku5Z8Wjkhq4jZZbjaNalhFQGs` (lowercase "l")

The `id` must match your Clerk org ID exactly. If there's a typo:
1. Delete the incorrect row
2. Create a new row with the exact correct `id`: `org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs`

**Also Verify `phone_number` is Set**:

The `phone_number` column might not be visible in the table view. To check/set it:
1. Click on the row to edit it
2. Look for `phone_number` field
3. Set it to: `+12028313219` (must match CallRail tracking number)
4. Save

Or use SQL query in Railway:
```sql
-- Check current phone_number
SELECT id, name, phone_number FROM companies WHERE id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';

-- Update phone_number if needed
UPDATE companies 
SET phone_number = '+12028313219' 
WHERE id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
```

**If Company Exists But Phone Number is Wrong**:
```bash
# Update phone number
curl -X PUT "https://ottoai-backend-production.up.railway.app/api/v1/company/org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs?phone_number=%2B12028313219" \
  -H "Authorization: Bearer YOUR_MANAGER_JWT_TOKEN"
```

---

**Option 2: Via Railway CLI (If You Have Access)**

**Step 1**: Install Railway CLI (if not installed)
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login
```

**Step 2**: Connect to Database
```bash
# List your projects
railway projects

# Link to your project (if not already linked)
railway link

# Connect to Postgres
railway connect postgres
```

**Step 3**: Run SQL Query
```sql
SELECT id, name, phone_number, primary_tracking_number, created_at 
FROM companies 
WHERE id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
```

**Expected Result**:
- Row exists
- `phone_number = '+12028313219'` or `'12028313219'` (must match CallRail number)

**If Missing/Incorrect**:
```sql
-- Update phone number
UPDATE companies 
SET phone_number = '+12028313219' 
WHERE id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';

-- Verify
SELECT phone_number FROM companies WHERE id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
```

---

**Option 3: Via Railway Dashboard (Web UI)**

**Step 1**: Go to Railway Dashboard
- Visit: https://railway.app
- Log in
- Select your project: `ottoai-backend-production`

**Step 2**: Access Database
- Click on your **Postgres** service
- Go to **Data** tab
- Click **Query** or **Connect** (depending on Railway UI)

**Step 3**: Run SQL Query
```sql
SELECT id, name, phone_number, primary_tracking_number, created_at 
FROM companies 
WHERE id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
```

**Expected Result**: See row with company data

---

**Option 4: Via Direct Postgres Connection (If You Have Connection String)**

**Step 1**: Get Database Connection String
- Railway Dashboard → Postgres Service → **Variables** tab
- Find `DATABASE_URL` or `POSTGRES_URL`
- Copy the connection string

**Step 2**: Connect via psql
```bash
# Connect to database
psql "postgresql://user:password@host:port/database"

# Or use connection string directly
psql $DATABASE_URL
```

**Step 3**: Run Query
```sql
SELECT id, name, phone_number, primary_tracking_number, created_at 
FROM companies 
WHERE id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
```

---

**Recommended Approach**: Use **Option 1 (API)** - it's the simplest and doesn't require database access. If you need to verify DB state directly, use **Option 2 (Railway CLI)** or **Option 3 (Railway Dashboard)**.

---

### Step 1.2: Verify Users Exist in Otto DB

**Action**: Check if users are linked to company

**Via Railway Dashboard**:
1. Go to Railway Dashboard → Postgres → Database → Data tab
2. Click on `users` table
3. Look for rows with `company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs'`

**Or via SQL Query in Railway Dashboard**:
1. Go to Railway Dashboard → Postgres → Database → Data tab
2. Click **Query** button (or look for SQL editor)
3. Run:
```sql
SELECT id, email, role, company_id, clerk_id 
FROM users 
WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
```

**Expected Result**:
- 3 users: manager, csr, sales_rep
- `company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs'`
- `role` matches: `manager`, `csr`, `sales_rep`

---

**Verify Users via API or Railway CLI** (No psql needed):

**Option 1: Via Railway CLI** (Easiest - No psql installation needed):

```bash
# Railway CLI handles psql connection automatically
railway connect postgres
```

Then in the psql session (Railway CLI opens it for you):
```sql
SELECT id, email, role, company_id FROM users WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
```

**Option 2: Via Railway Dashboard Query** (No CLI needed):

1. Go to Railway Dashboard → Postgres → Database → **Data** tab
2. Click **Query** button
3. Run:
```sql
SELECT id, email, role, company_id FROM users WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
```

**Option 3: Via API** (Check if endpoints exist):

```bash
# Try to get sales reps (if endpoint exists)
curl -X GET 'https://ottoai-backend-production.up.railway.app/api/v1/sales-reps?company_id=org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs' \
  -H 'Authorization: Bearer YOUR_MANAGER_JWT_TOKEN'

# Try to get sales managers (if endpoint exists)
curl -X GET 'https://ottoai-backend-production.up.railway.app/api/v1/sales-managers?company_id=org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs' \
  -H 'Authorization: Bearer YOUR_MANAGER_JWT_TOKEN'
```

**Note**: The API endpoints may not return all users (only reps/managers), so Railway Dashboard Query or Railway CLI is the most reliable way to verify all 3 users.

**If Users Are Missing** (Most Likely):

Users exist in Clerk but not in Otto DB. You need to manually create them.

**Step 1: Get Clerk User IDs**

**Option A: From Clerk Dashboard** (Easiest):
1. Go to https://dashboard.clerk.com
2. Go to **Users** tab
3. Find each user and copy their **User ID** (starts with `user_...`):
   - `azmanager@demo.com` → Copy User ID
   - `azcsr@demo.com` → Copy User ID
   - `azsalesrep@demo.com` → Copy User ID

**Option B: From JWT Tokens**:
- Log in as each user in frontend
- Open DevTools → Network tab → Find API request
- Decode JWT token → `sub` field is the Clerk user ID
- From your manager token: `user_36kub5UX3lxl2VivI3EQnqn7iOU`

**Step 2: Insert Users via Railway Dashboard UI** (No SQL Needed!)

**Method A: Using "+ Row" Button** (Easiest):

1. Go to Railway Dashboard → Postgres → Database → **Data** tab
2. Click on `users` table
3. Click **"+ Row"** button at the bottom
4. Fill in the fields for **Manager**:
   - `clerk_id`: `user_36kub5UX3lxl2VivI3EQnqn7iOU` (from your JWT token)
   - `email`: `azmanager@demo.com`
   - `name`: `AZ Manager`
   - `role`: `manager`
   - `company_id`: `org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs`
   - `created_at`: Click field - should auto-fill with current timestamp
   - `updated_at`: Same as created_at
   - Leave other fields NULL (like `phone_number`, `username`, etc.)
5. Click Save/Checkmark
6. Repeat for **CSR** and **Sales Rep** (get their Clerk IDs from Clerk Dashboard first)

**Method B: Using SQL Query** (If UI doesn't work):

1. Go to Railway Dashboard → Postgres → Database → **Data** tab
2. Click **Query** button (or look for SQL editor/console)
3. Run this SQL (replace `CLERK_USER_ID_FOR_CSR` and `CLERK_USER_ID_FOR_SALES_REP` with actual IDs):

```sql
-- Insert Manager (you already have this Clerk ID from JWT)
INSERT INTO users (clerk_id, email, name, role, company_id, created_at, updated_at)
VALUES (
  'user_36kub5UX3lxl2VivI3EQnqn7iOU',
  'azmanager@demo.com',
  'AZ Manager',
  'manager',
  'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs',
  NOW(),
  NOW()
);

-- Insert CSR (replace CLERK_USER_ID_FOR_CSR with actual Clerk user ID)
INSERT INTO users (clerk_id, email, name, role, company_id, created_at, updated_at)
VALUES (
  'CLERK_USER_ID_FOR_CSR',  -- ⚠️ REPLACE THIS with actual Clerk user ID
  'azcsr@demo.com',
  'AZ CSR',
  'csr',
  'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs',
  NOW(),
  NOW()
);

-- Insert Sales Rep (replace CLERK_USER_ID_FOR_SALES_REP with actual Clerk user ID)
INSERT INTO users (clerk_id, email, name, role, company_id, created_at, updated_at)
VALUES (
  'CLERK_USER_ID_FOR_SALES_REP',  -- ⚠️ REPLACE THIS with actual Clerk user ID
  'azsalesrep@demo.com',
  'AZ Sales Rep',
  'sales_rep',
  'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs',
  NOW(),
  NOW()
);
```

**Step 3: Verify Users Were Created**

Run this query in Railway Dashboard:
```sql
SELECT id, email, role, company_id, clerk_id 
FROM users 
WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
```

**Expected**: Should return 3 rows with your users.

**Note**: If you get an error about missing columns, check the `users` table structure first:
```sql
-- Check table structure
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'users';
```

---

### Step 1.3: Verify CallRail Webhooks Configured

**Action**: Check CallRail dashboard

**In CallRail Dashboard**:
1. Go to **Settings** → **Integrations** → **Webhooks**
2. Verify these URLs are configured:
   - `https://ottoai-backend-production.up.railway.app/api/v1/callrail/call.incoming`
   - `https://ottoai-backend-production.up.railway.app/api/v1/callrail/call.answered`
   - `https://ottoai-backend-production.up.railway.app/api/v1/callrail/call.missed`
   - `https://ottoai-backend-production.up.railway.app/api/v1/callrail/call.completed`

**Test Webhook**:
```bash
# Make a test call to +12028313219
# Check Railway logs:
railway logs --filter "callrail" --tail 20
```

**Expected**: Log shows "CallRail call.incoming webhook: {...}"

---

### Step 1.4: Document Ingestion (Recommended - Required for Shunya Features)

**Note**: Document ingestion is **required** for several Shunya features:
- ✅ **Ask Otto** queries (role-scoped document retrieval)
- ✅ **SOP Compliance** scoring (Shunya analyzes calls against SOPs)
- ✅ **Call Analysis** (Shunya uses documents for context)
- ✅ **Objection Handling** (Shunya references training materials)

Documents are uploaded to Otto's S3, then Otto calls **Shunya's ingestion API** to process them. Shunya is the single source of truth for document intelligence.

**Flow**:
1. Otto receives file upload → stores in S3
2. Otto creates Document record in DB
3. Otto triggers Celery task → calls Shunya's ingestion API with `target_role`
4. Shunya processes document → makes it available for Ask Otto queries

**API Endpoint**:
```
POST https://ottoai-backend-production.up.railway.app/api/v1/onboarding/documents/upload
```

**Required Headers**:
- `Authorization: Bearer YOUR_MANAGER_JWT_TOKEN` (get from frontend DevTools)
- `Content-Type: multipart/form-data` (curl adds this automatically)

**Required Form Fields**:
- `file`: The PDF/document file
- `category`: Document category (`sop`, `training`, `reference`, `policy`)
- `role_target`: Target role (`csr`, `sales_rep`, `manager`) - determines which Shunya `target_role` to use
- `metadata`: Optional JSON string with additional metadata

## Detailed Step-by-Step: Document Ingestion

### Step 1: Get Your Manager JWT Token

**Action**: Get authentication token from frontend

1. Open your frontend app in browser: https://otto-omega.vercel.app (or your frontend URL)
2. Log in as `azmanager@demo.com`
3. Open browser DevTools:
   - **Mac**: Press `Cmd + Option + I` or `F12`
   - **Windows/Linux**: Press `F12` or `Ctrl + Shift + I`
4. Go to **Network** tab
5. Refresh the page or navigate to any page (this triggers API calls)
6. Find any API request to `ottoai-backend-production.up.railway.app`
7. Click on the request → Go to **Headers** tab
8. Scroll down to **Request Headers** section
9. Find `Authorization: Bearer eyJhbGciOiJ...` (long token starting with `eyJ`)
10. **Copy the entire token** (everything after "Bearer ")

**Example token** (yours will be different):
```
eyJhbGciOiJSUzI1NiIsImNhdCI6ImNsX0I3ZDRQRDIyMkFBQSIsImtpZCI6Imluc18zNFNRZkYzc1ZVVElTazBUM0ZxT2Eyd3ZZTWkiLCJ0eXAiOiJKV1QifQ.eyJhenAiOiJodHRwczovL290dG8tb21lZ2EudmVyY2VsLmFwcCIsImNvbXBhbnlfaWQiOiJvcmdfMzZrdTVaOFdqa2hxNGpaWmJqYU5hSWhGUUdzIiwiZXhwIjoxNzY1NTcxNDg0LCJpYXQiOjE3NjU1NzA3ODQsImlzcyI6Imh0dHBzOi8vdGFsZW50ZWQtY29yYWwtMTAuY2xlcmsuYWNjb3VudHMuZGV2IiwianRpIjoiMDQzYzdmN2FjYWYwNTEyYmQxODUiLCJuYmYiOjE3NjU1NzA3NzksInJvbGUiOiJvcmc6bWFuYWdlciIsInN0YXRlIjoib3JnXzM2a3U1WjhXamtocTRqWlpiamFOYUloRlFHcyIsInN1YiI6InVzZXJfMzZrdWI1VVgzbHhsMlZpdkkzRVFucW43aU9VIiwidGVuYW50X2lkIjoib3JnXzM2a3U1WjhXamtocTRqWlpiamFOYUloRlFHcyIsInVzZXJfZW1haWwiOiJhem1hbmFnZXJAZGVtby5jb20iLCJ1c2VyX2lkIjoidXNlcl8zNmt1YjVVWDNseGwyVml2STNFUW5xbjdpT1UiLCJ1c2VyX25hbWUiOiJhem1hbmFnZXIifQ.Y0FJoB_0fKvWM01ecBs4tW0VEJ3pelRthywa-g_kvb-9sRQWpq0344SCCGBQjI_u8t0OA8CDIaYDQHArwvDp3wXxveqkDo3UoWbqx6i7gRNS24-6icoT6HsUz6m2L7KJvGDWe7MmovJdjV5br60d3c7CvNhKRAHzkMw1QV0IycaeN7PKGm4kRB9gEhfLh5eF2cOeA1k97wCEpmvxRpQaMsIa4Httvu9KbEhHYQC85CraiW5P2SN9y_29xN7bsOlCe7lZsvv6PTW3yzZsqESl-kvhXd_T_TGZYGmQrgqhXzWekT1yUAGHM4XVcdpQ5FJUTJ2rg4LugyrVSRJzQPZKRA
```

**Save this token** - you'll use it for all document uploads.

---

### Step 2: Prepare Your Documents

**Action**: Locate your document files on your computer

1. Find the PDF/document files you want to upload:
   - CSR SOP (e.g., `csr_sop.pdf`)
   - Sales Rep SOP (e.g., `sales_rep_sop.pdf`)
   - Reference documents (e.g., `product_catalog.pdf`)
   - Training materials (e.g., `sales_training.pdf`)
   - Policy documents (e.g., `company_policy.pdf`)

2. **Note the full file path** for each document:
   - **Mac/Linux**: `/Users/tusharmehrotra/Documents/csr_sop.pdf`
   - **Windows**: `C:\Users\YourName\Documents\csr_sop.pdf`

3. **Verify file exists**:
   ```bash
   # Test if file exists (Mac/Linux)
   ls -la /path/to/your/document.pdf
   
   # Or just check in Finder/File Explorer
   ```

---

### Step 3: Upload CSR SOP Document

**Action**: Upload CSR SOP to Otto backend

**Open Terminal** (any terminal: Terminal.app, iTerm, VS Code terminal, etc.)

**Run this command** (replace placeholders):

```bash
curl -X POST "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/documents/upload" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -F "file=@/FULL/PATH/TO/csr_sop.pdf" \
  -F "category=sop" \
  -F "role_target=csr" \
  -F 'metadata={"document_type":"sop","target_role":"customer_rep"}'
```

**Replace**:
- `YOUR_TOKEN_HERE` → Your JWT token from Step 1
- `/FULL/PATH/TO/csr_sop.pdf` → Actual file path (e.g., `/Users/tusharmehrotra/Documents/csr_sop.pdf`)

**Example with real values**:
```bash
curl -X POST "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/documents/upload" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..." \
  -F "file=@/Users/tusharmehrotra/Documents/csr_sop.pdf" \
  -F "category=sop" \
  -F "role_target=csr" \
  -F 'metadata={"document_type":"sop","target_role":"customer_rep"}'
```

**Expected Response** (Success):
```json
{
  "success": true,
  "data": {
    "document_id": "doc_abc123xyz456",
    "filename": "csr_sop.pdf",
    "s3_url": "https://s3.amazonaws.com/...",
    "ingestion_status": "pending",
    "estimated_processing_time": "2-5 minutes"
  }
}
```

**⚠️ IMPORTANT**: **Save the `document_id`** from the response (e.g., `doc_abc123xyz456`) - you'll need it to check status.

**If Error Occurs**:

**500 Internal Server Error** (Most Common):
This usually means S3 storage is not configured. Check Railway environment variables:

1. **Go to Railway Dashboard** → Your Project → `ottoai-backend-production` service
2. Click **Variables** tab
3. Verify these variables are set:
   - `AWS_ACCESS_KEY_ID` (required)
   - `AWS_SECRET_ACCESS_KEY` (required)
   - `S3_BUCKET` (required, e.g., `otto-documents-prod`)
   - `AWS_REGION` (optional, defaults to `us-east-1`)

**If S3 variables are missing**:
- Document upload requires S3 to store files before sending to Shunya
- You need to set up AWS S3 credentials in Railway
- Or skip document ingestion for now and proceed with pilot (documents are optional)

**Check Railway Logs for Exact Error**:
```bash
# Check logs with trace_id
railway logs --filter "5892c214-fcd7-415e-ad81-b33945569d3f"

# Or check recent logs
railway logs --tail 50
```

**Other Errors**:
- **401 Unauthorized**: Token expired - get a fresh token from Step 1
- **400 Bad Request**: Check file path is correct, file exists, and all fields are provided

---

### Step 4: Upload Sales Rep SOP Document

**Action**: Upload Sales Rep SOP (same process, different file)

**Run this command**:

```bash
curl -X POST "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/documents/upload" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -F "file=@/FULL/PATH/TO/sales_rep_sop.pdf" \
  -F "category=sop" \
  -F "role_target=sales_rep" \
  -F 'metadata={"document_type":"sop","target_role":"sales_rep"}'
```

**Save the `document_id`** from the response.

---

### Step 5: Upload Reference Documents (Optional but Recommended)

**Action**: Upload reference documents for Ask Otto context

**Run this command**:

```bash
curl -X POST "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/documents/upload" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -F "file=@/FULL/PATH/TO/product_catalog.pdf" \
  -F "category=reference" \
  -F "role_target=sales_rep" \
  -F 'metadata={"document_type":"reference","target_role":"sales_rep"}'
```

**Save the `document_id`** from the response.

---

### Step 6: Check Document Ingestion Status

**Action**: Verify documents are being processed by Shunya

**Wait 30 seconds** after upload, then check status:

```bash
curl -X GET "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/documents/status/DOCUMENT_ID_HERE" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Replace**:
- `DOCUMENT_ID_HERE` → The `document_id` from Step 3, 4, or 5 response
- `YOUR_TOKEN_HERE` → Your JWT token

**Expected Response** (Processing):
```json
{
  "success": true,
  "data": {
    "document_id": "doc_abc123xyz456",
    "status": "processing",  // or "pending", "done", "failed"
    "ingestion_job_id": "job_xyz789"
  }
}
```

**Status Values**:
- `pending` - Just uploaded, waiting to be processed
- `processing` - Shunya is currently processing
- `done` - ✅ Successfully ingested (ready for use)
- `failed` - ❌ Processing failed (check logs)

**Check Again After 2-5 Minutes**:
```bash
# Run the same status check command again
curl -X GET "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/documents/status/DOCUMENT_ID_HERE" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Expected**: Status should be `"done"` after 2-5 minutes.

---

### Step 7: Verify in Database (Optional)

**Action**: Confirm documents are stored in Otto database

**Via Railway Dashboard**:
1. Go to Railway Dashboard → Postgres → Database → **Data** tab
2. Click on `documents` table
3. Look for rows with `company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs'`

**Or via SQL Query**:
```sql
SELECT id, filename, category, role_target, ingestion_status, ingestion_job_id, created_at 
FROM documents 
WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs'
ORDER BY created_at DESC;
```

**Expected**: Should see your uploaded documents with `ingestion_status = 'done'` (after processing completes).

---

## Summary Checklist

- [ ] Step 1: Got Manager JWT token from frontend
- [ ] Step 2: Located document files on computer
- [ ] Step 3: Uploaded CSR SOP → Saved `document_id`
- [ ] Step 4: Uploaded Sales Rep SOP → Saved `document_id`
- [ ] Step 5: (Optional) Uploaded Reference documents → Saved `document_id`
- [ ] Step 6: Checked status for each document → Status = `"done"`
- [ ] Step 7: (Optional) Verified in database

**Once all documents show `status = "done"`, they're ready for use in Ask Otto, SOP compliance scoring, and other Shunya features!**

---

**Upload Documents**:

Otto supports **4 document categories** (all mapped to Shunya):
- `sop` - Standard Operating Procedures
- `training` - Training materials
- `reference` - Reference documents
- `policy` - Company policies

**Upload CSR SOP**:
```bash
curl -X POST "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/documents/upload" \
  -H "Authorization: Bearer YOUR_MANAGER_JWT_TOKEN" \
  -F "file=@/path/to/csr_sop.pdf" \
  -F "category=sop" \
  -F "role_target=csr" \
  -F 'metadata={"document_type":"sop","target_role":"customer_rep"}'
```

**Upload Sales Rep SOP**:
```bash
curl -X POST "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/documents/upload" \
  -H "Authorization: Bearer YOUR_MANAGER_JWT_TOKEN" \
  -F "file=@/path/to/sales_rep_sop.pdf" \
  -F "category=sop" \
  -F "role_target=sales_rep" \
  -F 'metadata={"document_type":"sop","target_role":"sales_rep"}'
```

**Upload Reference Documents** (Important for Ask Otto context):
```bash
curl -X POST "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/documents/upload" \
  -H "Authorization: Bearer YOUR_MANAGER_JWT_TOKEN" \
  -F "file=@/path/to/product_catalog.pdf" \
  -F "category=reference" \
  -F "role_target=sales_rep" \
  -F 'metadata={"document_type":"reference","target_role":"sales_rep"}'
```

**Upload Training Materials**:
```bash
curl -X POST "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/documents/upload" \
  -H "Authorization: Bearer YOUR_MANAGER_JWT_TOKEN" \
  -F "file=@/path/to/sales_training.pdf" \
  -F "category=training" \
  -F "role_target=sales_rep" \
  -F 'metadata={"document_type":"training","target_role":"sales_rep"}'
```

**Upload Policy Documents**:
```bash
curl -X POST "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/documents/upload" \
  -H "Authorization: Bearer YOUR_MANAGER_JWT_TOKEN" \
  -F "file=@/path/to/company_policy.pdf" \
  -F "category=policy" \
  -F "role_target=manager" \
  -F 'metadata={"document_type":"policy","target_role":"sales_manager"}'
```

**Note**: All document types use the same endpoint (`/api/v1/onboarding/documents/upload`). Otto maps the `category` to Shunya's `document_type` and calls Shunya's general ingestion endpoint (`/api/v1/ingestion/documents/upload`).

**Example with Real File Path**:
```bash
# If your file is at ~/Documents/csr_sop.pdf
curl -X POST "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/documents/upload" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..." \
  -F "file=@/Users/tusharmehrotra/Documents/csr_sop.pdf" \
  -F "category=sop" \
  -F "role_target=csr" \
  -F 'metadata={"document_type":"sop","target_role":"customer_rep"}'
```

**Expected Response** (Success):
```json
{
  "success": true,
  "data": {
    "document_id": "doc_abc123...",
    "filename": "csr_sop.pdf",
    "s3_url": "https://...",
    "ingestion_status": "pending",
    "estimated_processing_time": "2-5 minutes"
  }
}
```

**Save the `document_id`** from the response - you'll need it to check status.

**Verify Ingestion Status**:

```bash
# Check document status (use document_id from upload response)
curl -X GET "https://ottoai-backend-production.up.railway.app/api/v1/onboarding/documents/status/{document_id}" \
  -H "Authorization: Bearer YOUR_MANAGER_JWT_TOKEN"
```

**Expected Response**:
```json
{
  "success": true,
  "data": {
    "document_id": "...",
    "status": "done",  // or "processing", "pending", "failed"
    "ingestion_job_id": "..."
  }
}
```

**Verify in Database** (via Railway Dashboard):
```sql
SELECT id, filename, category, role_target, ingestion_status, ingestion_job_id, created_at 
FROM documents 
WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
```

**Expected**: Documents with `ingestion_status = 'done'` after 2-5 minutes.

**File References**:
- Otto Endpoint: `app/routes/onboarding/onboarding_routes.py:249-309`
- Otto Celery Task: `app/tasks/onboarding_tasks.py:17-122`
- Shunya Client: `app/services/uwc_client.py:1001-1044`

**Document Types Supported**:
- ✅ **SOP** (`category=sop`) - For SOP compliance scoring, Ask Otto queries
- ✅ **Reference** (`category=reference`) - Product info, catalogs, reference materials (important for Ask Otto context)
- ✅ **Training** (`category=training`) - Training materials, objection handlers
- ✅ **Policy** (`category=policy`) - Company policies, guidelines

**Note**: All document types are supported and mapped to Shunya. Reference documents are especially important for Ask Otto to provide accurate product/service information. If you don't have documents ready, you can skip this step and proceed, but Ask Otto and SOP compliance features will be limited.

---

### Step 1.5: Verify Frontend Access

**Action**: Log into frontend with each user

**Frontend Screens to Check**:

1. **Manager Login** (`azmanager@demo.com`):
   - ✅ Can access Executive Dashboard
   - ✅ Can see company-wide metrics
   - ✅ Can access `/exec/csr` and `/exec/sales` tabs

2. **CSR Login** (`azcsr@demo.com`):
   - ✅ Can access CSR Dashboard
   - ✅ Can see shared leads board
   - ✅ Can access contact cards

3. **Sales Rep Login** (`azsalesrep@demo.com`):
   - ✅ Can access Sales Rep App
   - ✅ Can see "Today's Appointments"
   - ✅ Can see own tasks

**If Access Issues**: Check Clerk role assignments match Otto roles.

---

## Phase 2: Scenario 1 - Booked Call (30 minutes)

### Step 2.1: Make Inbound Call

**Action**: Call `+12028313219` from your phone

**During Call**:
- Answer the call
- Have a conversation that results in booking (e.g., "Yes, I'd like to schedule an appointment for next Tuesday at 2pm")
- End the call

**Expected**: CallRail sends webhook to backend

---

### Step 2.2: Immediate Verification (Within 30 seconds)

#### 2.2.1: Check Railway Logs

**Action**: Verify webhook received

```bash
railway logs --filter "callrail" --tail 30
```

**Look For**:
- ✅ "CallRail call.incoming webhook: {...}"
- ✅ "CallRail call.completed webhook: {...}"

**If Missing**: Check CallRail webhook configuration.

---

#### 2.2.2: Check Call Record Created

**DB Query**:
```sql
SELECT call_id, phone_number, company_id, recording_url, duration, 
       created_at, contact_card_id, lead_id
FROM calls 
WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs' 
ORDER BY created_at DESC 
LIMIT 1;
```

**Expected**:
- ✅ `call_id` exists (integer)
- ✅ `phone_number` = your caller phone number
- ✅ `company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs'`
- ✅ `recording_url` populated (from CallRail)
- ✅ `contact_card_id` populated
- ✅ `lead_id` populated

**Save**: Note the `call_id` and `lead_id` for next steps.

---

#### 2.2.3: Check ContactCard Created

**DB Query**:
```sql
SELECT id, primary_phone, first_name, last_name, company_id, created_at
FROM contact_cards 
WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs' 
AND primary_phone = '<YOUR_CALLER_PHONE_NUMBER>';
```

**Expected**:
- ✅ ContactCard exists
- ✅ `primary_phone` matches your caller number
- ✅ `company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs'`

**Save**: Note the `contact_card_id`.

---

#### 2.2.4: Check Lead Created

**DB Query**:
```sql
SELECT id, contact_card_id, status, source, company_id, created_at
FROM leads 
WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs' 
ORDER BY created_at DESC 
LIMIT 1;
```

**Expected**:
- ✅ Lead exists
- ✅ `contact_card_id` matches from Step 2.2.3
- ✅ `status` = `'new'` (initial state)
- ✅ `source` = `'inbound_call'` or similar

**Save**: Note the `lead_id`.

---

#### 2.2.5: Check Frontend - CSR Dashboard

**Action**: Log into frontend as CSR (`azcsr@demo.com`)

**Frontend Screen**: CSR Dashboard (`/csr` or `/dashboard`)

**Look For**:
- ✅ New call appears in "Recent Calls" or "Calls" list
- ✅ Call shows status: "Processing" or "New"
- ✅ Caller phone number visible
- ✅ Call timestamp matches current time

**If Missing**: Refresh page, check filters.

---

### Step 2.3: Shunya Processing (Wait 2-5 minutes)

#### 2.3.1: Check Shunya Job Created

**DB Query** (after 30-60 seconds):
```sql
SELECT id, job_type, job_status, shunya_job_id, call_id, company_id, 
       created_at, retry_count
FROM shunya_jobs 
WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs' 
AND call_id = <CALL_ID_FROM_2.2.2>
ORDER BY created_at DESC 
LIMIT 1;
```

**Expected**:
- ✅ Job exists
- ✅ `job_type = 'csr_call'`
- ✅ `job_status = 'pending'` or `'running'` (initially)
- ✅ `shunya_job_id` populated (Shunya's job ID)
- ✅ `call_id` matches

**Save**: Note the `shunya_job_id`.

---

#### 2.3.2: Monitor Shunya Job Status

**DB Query** (check every 30 seconds until complete):
```sql
SELECT job_status, processed_output_hash, error_message, retry_count,
       updated_at
FROM shunya_jobs 
WHERE id = <JOB_ID_FROM_2.3.1>;
```

**Expected Progression**:
1. `job_status = 'pending'` → `'running'` → `'succeeded'`
2. `processed_output_hash` populated when complete
3. `error_message` is NULL

**If Stuck**: Check Railway logs for Shunya errors.

---

#### 2.3.3: Check Call Transcript Created

**DB Query** (after job succeeds):
```sql
SELECT call_id, transcript_text, created_at
FROM call_transcripts 
WHERE call_id = <CALL_ID_FROM_2.2.2>;
```

**Expected**:
- ✅ Transcript exists
- ✅ `transcript_text` contains conversation text
- ✅ Text matches what was said in call

---

#### 2.3.4: Check Call Analysis Created

**DB Query**:
```sql
SELECT call_id, lead_quality, booking_status, call_outcome_category,
       objections, sop_compliance_score, sentiment_score, created_at
FROM call_analyses 
WHERE call_id = <CALL_ID_FROM_2.2.2>;
```

**Expected**:
- ✅ Analysis exists
- ✅ `booking_status = 'booked'` (from Shunya, not inferred)
- ✅ `lead_quality` = `'hot'` or `'warm'` or `'cold'` (from Shunya)
- ✅ `call_outcome_category` populated (from Shunya)
- ✅ `objections` = NULL or array (from Shunya)
- ✅ `sop_compliance_score` = number 0-10 (from Shunya)

**Critical**: All values come from Shunya, not Otto inference.

---

#### 2.3.5: Check Lead Status Updated

**DB Query**:
```sql
SELECT id, status, last_qualified_at, updated_at
FROM leads 
WHERE id = <LEAD_ID_FROM_2.2.4>;
```

**Expected**:
- ✅ `status = 'qualified_booked'` (updated from Shunya analysis)
- ✅ `last_qualified_at` populated (timestamp)

---

#### 2.3.6: Check Appointment Created

**DB Query**:
```sql
SELECT id, lead_id, contact_card_id, scheduled_start, scheduled_end,
       status, location_address, assigned_rep_id, company_id
FROM appointments 
WHERE lead_id = <LEAD_ID_FROM_2.2.4> 
AND company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
```

**Expected**:
- ✅ Appointment exists
- ✅ `scheduled_start` populated (if Shunya extracted time from call)
- ✅ `scheduled_end` populated (if provided)
- ✅ `status = 'scheduled'` or `'confirmed'`
- ✅ `location_address` populated (if Shunya extracted address)
- ✅ `assigned_rep_id` = NULL (not yet assigned)

**Save**: Note the `appointment_id`.

---

### Step 2.4: Frontend Verification - CSR Dashboard

**Action**: Log into frontend as CSR (`azcsr@demo.com`)

**Frontend Screen**: CSR Dashboard → Call Detail View

**Navigate To**: Click on the call from Step 2.2.5

**Look For**:
- ✅ **Call Details Tab**:
  - Caller phone number
  - Call duration
  - Recording available (play button)
  
- ✅ **Analysis Tab**:
  - `booking_status: "booked"` (from Shunya)
  - `lead_quality: "hot"` or `"warm"` (from Shunya)
  - `call_outcome_category` displayed
  - `objections` listed (if any from Shunya)
  - `sop_compliance_score` shown
  
- ✅ **Transcript Tab**:
  - Full conversation transcript visible
  - Timestamps for each speaker

**Frontend Screen**: CSR Dashboard → Contact Card View

**Navigate To**: Click on contact name/phone from call

**Look For**:
- ✅ **Contact Card Header**:
  - Name (if extracted)
  - Phone number
  - Status: "Booked" or "Qualified - Booked"
  
- ✅ **Appointment Section**:
  - Appointment card visible
  - Scheduled date/time (if Shunya extracted)
  - Address (if Shunya extracted)
  - Status: "Scheduled" or "Confirmed"
  
- ✅ **Call History**:
  - This call listed
  - Shows booking status

---

### Step 2.5: Dispatch Appointment to Sales Rep

**Action**: Assign appointment to sales rep

**API Call**:
```bash
curl -X POST "https://ottoai-backend-production.up.railway.app/api/v1/appointments/<APPOINTMENT_ID_FROM_2.3.6>/assign" \
  -H "Authorization: Bearer CSR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "rep_id": "<SALES_REP_USER_ID>",
    "allow_double_booking": false
  }'
```

**Get Sales Rep User ID**:
```sql
SELECT id FROM users 
WHERE email = 'azsalesrep@demo.com' 
AND company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
```

**DB Verification**:
```sql
SELECT id, assigned_rep_id, status, updated_at
FROM appointments 
WHERE id = <APPOINTMENT_ID_FROM_2.3.6>;
```

**Expected**:
- ✅ `assigned_rep_id` = sales rep user ID
- ✅ `status` = `'scheduled'` or `'confirmed'`

---

### Step 2.6: Frontend Verification - Sales Rep App

**Action**: Log into frontend as Sales Rep (`azsalesrep@demo.com`)

**Frontend Screen**: Sales Rep App → "Today's Appointments"

**Navigate To**: `/sales-rep/appointments` or `/appointments/today`

**Look For**:
- ✅ **Appointment Card**:
  - Customer name
  - Scheduled time (if Shunya extracted)
  - Address (if Shunya extracted)
  - Status: "Scheduled" or "Confirmed"
  - "View Details" button

**Frontend Screen**: Sales Rep App → Appointment Detail

**Navigate To**: Click on appointment card

**Look For**:
- ✅ **Appointment Details**:
  - Customer contact info
  - Scheduled date/time
  - Location address
  - Call recording link (if available)
  - Property intelligence (if address extracted)

**Frontend Screen**: Sales Rep App → Dashboard

**Look For**:
- ✅ Appointment count updated
- ✅ "Today's Appointments" shows 1 appointment

---

### Step 2.7: API Verification - Sales Rep Endpoints

**Action**: Test sales rep API endpoints

**Get Today's Appointments**:
```bash
curl -X GET "https://ottoai-backend-production.up.railway.app/api/v1/metrics/appointments/today/self" \
  -H "Authorization: Bearer SALES_REP_JWT_TOKEN"
```

**Expected Response**:
```json
{
  "success": true,
  "data": [
    {
      "appointment_id": "<APPOINTMENT_ID>",
      "scheduled_time": "2025-01-XXT14:00:00Z",
      "customer_name": "...",
      "address": "...",
      "status": "scheduled"
    }
  ]
}
```

---

## Phase 3: Scenario 2 - Qualified But Not Booked (30 minutes)

### Step 3.1: Make Second Inbound Call

**Action**: Call `+12028313219` from a different phone number (or same number if testing)

**During Call**:
- Answer the call
- Have a conversation that qualifies but doesn't book (e.g., "I'm interested but need to think about it" or "Let me check with my spouse")
- End the call

**Expected**: CallRail sends webhook to backend

---

### Step 3.2: Immediate Verification (Within 30 seconds)

**Repeat Steps 2.2.1 - 2.2.5** for this new call:

- ✅ Railway logs show webhook
- ✅ Call record created
- ✅ ContactCard created/updated
- ✅ Lead created
- ✅ CSR Dashboard shows new call

**Save**: Note the new `call_id` and `lead_id`.

---

### Step 3.3: Shunya Processing (Wait 2-5 minutes)

**Repeat Steps 2.3.1 - 2.3.5** for this call:

- ✅ Shunya job created
- ✅ Job completes successfully
- ✅ Transcript created
- ✅ Analysis created

**DB Query - Critical Check**:
```sql
SELECT call_id, booking_status, call_outcome_category, lead_quality
FROM call_analyses 
WHERE call_id = <NEW_CALL_ID_FROM_3.2>;
```

**Expected**:
- ✅ `booking_status = 'not_booked'` (from Shunya)
- ✅ `call_outcome_category = 'qualified_but_unbooked'` (from Shunya)
- ✅ `lead_quality = 'hot'` or `'warm'` or `'cold'` (from Shunya)

**Critical**: All values from Shunya, not inferred.

---

### Step 3.4: Check Lead Status Updated

**DB Query**:
```sql
SELECT id, status, last_qualified_at, updated_at
FROM leads 
WHERE id = <NEW_LEAD_ID_FROM_3.2>;
```

**Expected**:
- ✅ `status = 'qualified_unbooked'` or `'warm'` or `'hot'` (updated from Shunya)
- ✅ `last_qualified_at` populated

---

### Step 3.5: Check Tasks Created (If Shunya Provides Pending Actions)

**DB Query**:
```sql
SELECT id, description, assigned_to, source, status, due_at, contact_card_id
FROM tasks 
WHERE contact_card_id = <CONTACT_CARD_ID_FROM_3.2>
AND company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
```

**Expected**:
- ✅ Tasks exist (if Shunya returned `pending_actions`)
- ✅ `source = 'shunya'`
- ✅ `assigned_to = 'csr'` (default)
- ✅ `description` contains action text from Shunya

**Note**: Tasks only created if Shunya provides `pending_actions` in analysis.

---

### Step 3.6: Frontend Verification - CSR Dashboard

**Action**: Log into frontend as CSR (`azcsr@demo.com`)

**Frontend Screen**: CSR Dashboard → "Pending Leads" or "Qualified Unbooked"

**Navigate To**: `/csr/leads?status=qualified_unbooked` or similar

**Look For**:
- ✅ **Lead Card**:
  - Customer name/phone
  - Status: "Qualified - Unbooked" or "Warm" or "Hot"
  - Last contacted timestamp
  - "View Details" button

**Frontend Screen**: CSR Dashboard → Lead Detail / Contact Card

**Navigate To**: Click on lead/contact

**Look For**:
- ✅ **Contact Card Header**:
  - Status: "Qualified - Unbooked" or "Warm"
  - Last qualified timestamp
  
- ✅ **Call Analysis Section**:
  - `booking_status: "not_booked"` (from Shunya)
  - `call_outcome_category: "qualified_but_unbooked"` (from Shunya)
  - `lead_quality: "warm"` or `"hot"` (from Shunya)
  
- ✅ **Tasks Section** (if Shunya provided):
  - Follow-up tasks listed
  - Task descriptions from Shunya
  - Due dates (if provided)

**Frontend Screen**: CSR Dashboard → Metrics

**Navigate To**: `/csr/metrics` or `/metrics/csr/overview/self`

**Look For**:
- ✅ `qualified_but_unbooked_calls: 1` (or incremented)
- ✅ `qualified_calls: 1` (or incremented)
- ✅ `booking_rate` calculated correctly

---

### Step 3.7: API Verification - CSR Metrics

**Action**: Test CSR metrics endpoint

**Get CSR Overview Metrics**:
```bash
curl -X GET "https://ottoai-backend-production.up.railway.app/api/v1/metrics/csr/overview/self" \
  -H "Authorization: Bearer CSR_JWT_TOKEN"
```

**Expected Response**:
```json
{
  "success": true,
  "data": {
    "total_calls": 2,
    "qualified_calls": 2,
    "qualified_rate": 1.0,
    "booked_calls": 1,
    "booking_rate": 0.5,
    "qualified_but_unbooked_calls": 1,
    "service_not_offered_calls": 0
  }
}
```

**Get Pending Leads**:
```bash
curl -X GET "https://ottoai-backend-production.up.railway.app/api/v1/leads?status=qualified_unbooked,warm,hot" \
  -H "Authorization: Bearer CSR_JWT_TOKEN"
```

**Expected Response**:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "<LEAD_ID>",
        "status": "qualified_unbooked",
        "contact_card_id": "...",
        "last_qualified_at": "2025-01-XXT..."
      }
    ],
    "total": 1
  }
}
```

---

## Phase 4: Final Verification (10 minutes)

### Step 4.1: Tenant Isolation Check

**Action**: Verify data is scoped to correct tenant

**DB Query**:
```sql
-- All calls for this tenant
SELECT COUNT(*) as call_count 
FROM calls 
WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
-- Should be 2

-- All leads for this tenant
SELECT COUNT(*) as lead_count 
FROM leads 
WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
-- Should be 2

-- All appointments for this tenant
SELECT COUNT(*) as appointment_count 
FROM appointments 
WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs';
-- Should be 1
```

**Frontend Check**: Log in as manager, verify only this tenant's data visible.

---

### Step 4.2: Role Scoping Check

**Action**: Verify role-based access

**CSR Access** (log in as `azcsr@demo.com`):
- ✅ Can see both leads (shared pool)
- ✅ Can see both calls
- ✅ Can see 1 appointment (but can't see sales rep's personal data)

**Sales Rep Access** (log in as `azsalesrep@demo.com`):
- ✅ Can see only assigned appointment (1 appointment)
- ✅ Cannot see other rep's appointments
- ✅ Cannot see CSR-only data

**Manager Access** (log in as `azmanager@demo.com`):
- ✅ Can see all calls (company-wide)
- ✅ Can see all leads (company-wide)
- ✅ Can see all appointments (company-wide)
- ✅ Can see executive metrics

---

### Step 4.3: Shunya Source of Truth Verification

**Action**: Verify all semantics come from Shunya

**DB Query**:
```sql
SELECT call_id, booking_status, lead_quality, call_outcome_category,
       objections, sop_compliance_score, sentiment_score
FROM call_analyses 
WHERE company_id = 'org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs'
ORDER BY created_at DESC;
```

**Expected**:
- ✅ All `booking_status` values are from Shunya (not NULL unless Shunya didn't provide)
- ✅ All `lead_quality` values are from Shunya
- ✅ All `call_outcome_category` values are from Shunya
- ✅ No inferred values (Otto doesn't infer these)

**Critical**: If any field is NULL, that's correct behavior (Shunya didn't provide it). Otto should NOT infer.

---

## Summary Checklist

### Scenario 1 (Booked Call) - ✅ Complete:
- [ ] Call ingested → Call record in DB
- [ ] Shunya processed → Analysis with `booking_status = 'booked'`
- [ ] Appointment created → Sales rep can see in frontend
- [ ] All data from Shunya (no inference)

### Scenario 2 (Qualified Unbooked) - ✅ Complete:
- [ ] Call ingested → Call record in DB
- [ ] Shunya processed → Analysis with `booking_status = 'not_booked'`, `call_outcome_category = 'qualified_but_unbooked'`
- [ ] Lead in CSR shared pool → Visible in frontend
- [ ] Tasks created (if Shunya provided pending actions)
- [ ] All data from Shunya (no inference)

### Overall - ✅ Complete:
- [ ] Tenant isolation: Only `org_36ku5Z8Wjkhq4jZZbjaNaIhFQGs` data visible
- [ ] Role scoping: CSR shared, sales rep self-scoped, manager company-wide
- [ ] Shunya source of truth: All semantics from Shunya, no inference

---

## Troubleshooting Quick Reference

**Issue**: "No company found for tracking number"
- **Fix**: Verify `Company.phone_number = '+12028313219'`

**Issue**: Shunya job stuck in "pending"
- **Fix**: Check Railway logs for Shunya webhook errors

**Issue**: Appointment not created despite `booking_status = 'booked'`
- **Fix**: Check if Shunya provided appointment time in `entities` JSON

**Issue**: Frontend not showing data
- **Fix**: Refresh page, check filters, verify JWT token has correct `org_id`

---

**Ready to execute!** Start with Phase 1, then proceed through each phase sequentially.

