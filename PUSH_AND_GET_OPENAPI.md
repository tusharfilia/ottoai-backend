# Push to GitHub & Get OpenAPI from Railway

## Quick Steps

### 1. Review Changes (Optional but Recommended)
```bash
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend
git status
```

### 2. Stage All Changes
```bash
git add .
```

### 3. Commit
```bash
git commit -m "Add Shunya integration tests and documentation updates"
```

### 4. Push to GitHub
```bash
git push origin main
```

### 5. Wait for Railway Deployment
- Railway will auto-deploy (usually takes 2-5 minutes)
- Check Railway dashboard: https://railway.app

### 6. Get OpenAPI Spec
Once Railway deployment is live:

```bash
# Replace with your actual Railway URL
RAILWAY_URL="https://your-app.railway.app"

# Get OpenAPI spec
curl "$RAILWAY_URL/openapi.json" > openapi.json

# Or just visit in browser:
# $RAILWAY_URL/openapi.json
# $RAILWAY_URL/docs (Swagger UI)
```

## Find Your Railway URL

1. Go to https://railway.app
2. Select your project
3. Click on the deployed service
4. Check "Settings" → "Domains" or look at the service URL

Usually looks like: `https://your-app-production.up.railway.app`

## One-Liner to Get Spec

```bash
# Replace with your Railway URL
curl https://your-app.railway.app/openapi.json | python3 -m json.tool > openapi.json && echo "✅ Saved to openapi.json"
```

