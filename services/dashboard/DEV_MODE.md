# Dev Mode - Local Testing Without Clerk

Dev mode allows you to test the Otto backend locally without setting up Clerk authentication. This is useful for:
- Testing the missed call flow
- Developing features before Clerk frontend is ready
- Quick local debugging

## Setup

### 1. Set Environment Variables

Add these to your `.env` file or export them:

```bash
# Enable dev mode
export DEV_MODE=true

# Optional: Customize test company/user IDs (defaults shown)
export DEV_TEST_COMPANY_ID=dev-test-company
export DEV_TEST_USER_ID=dev-test-user
export DEV_TEST_USER_EMAIL=tushar@otto.ai
export DEV_TEST_USER_NAME="Tushar"

# Required: Your CallRail/Twilio tracking number
export DEV_TEST_PHONE_NUMBER=+15205232772
```

### 2. Seed Test Data

Run the seed script to create the test company and user:

```bash
cd services/dashboard
python scripts/seed_dev_data.py
```

This will create:
- A test company with your CallRail/Twilio phone number
- A test CSR user (Tushar) linked to that company

### 3. Start Your Backend

```bash
# Make sure DEV_MODE=true is set
uvicorn app.main:app --reload
```

## How It Works

When `DEV_MODE=true`:
- **No authentication required**: Requests without `Authorization` header will automatically use the test company/user
- **Test company ID**: `dev-test-company` (or your `DEV_TEST_COMPANY_ID`)
- **Test user ID**: `dev-test-user` (or your `DEV_TEST_USER_ID`)
- **Test user role**: `csr`

The middleware will:
1. Check if `DEV_MODE=true`
2. If no auth token is provided, use test company/user
3. If auth token is invalid, fall back to test company/user
4. Otherwise, use normal Clerk authentication

## Frontend Usage

In your frontend, you can make requests without authentication headers:

```typescript
// No Authorization header needed in dev mode
const response = await fetch('http://localhost:8000/api/v1/dashboard/calls?status=missed&company_id=dev-test-company');
```

Or if you want to be explicit:

```typescript
// Works with or without auth header in dev mode
const response = await fetch('http://localhost:8000/api/v1/dashboard/calls?status=missed&company_id=dev-test-company', {
  headers: {
    // Authorization header optional in dev mode
    'Content-Type': 'application/json',
  }
});
```

## Disabling Dev Mode

When you're ready to use Clerk:

1. **Set `DEV_MODE=false`** or remove it from your environment
2. **Restart your backend**
3. **Set up Clerk authentication** in your frontend

Dev mode is **automatically disabled** in production (it only works when explicitly enabled).

## Important Notes

⚠️ **Security**: Dev mode should **NEVER** be enabled in production or staging environments.

✅ **Safe for local development**: Dev mode only works when `DEV_MODE=true` is explicitly set.

🔄 **Easy to remove**: When you're done testing, just set `DEV_MODE=false` and the normal Clerk flow will work.

## Troubleshooting

### "Missing or invalid tenant_id" error
- Make sure `DEV_MODE=true` is set
- Check that you've run the seed script
- Verify `DEV_TEST_COMPANY_ID` matches the company ID in your database

### Test company/user not found
- Run `python scripts/seed_dev_data.py` again
- Check that `DEV_TEST_PHONE_NUMBER` is set correctly
- Verify your database connection

### Still seeing Clerk errors
- Make sure `DEV_MODE=true` (not `DEV_MODE=1` or other variations)
- Restart your backend after setting the env var
- Check backend logs for "DEV_MODE enabled" messages


