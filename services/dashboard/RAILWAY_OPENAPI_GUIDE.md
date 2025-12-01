# Getting OpenAPI Spec from Railway

## 🚀 Quick Steps

1. **Push your code to GitHub:**
   ```bash
   cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend
   
   # Check what branch you're on
   git branch --show-current
   
   # Add all changes
   git add .
   
   # Commit (or skip if you want to review first)
   git commit -m "Add tests and update Shunya integration"
   
   # Push to GitHub
   git push origin main  # or your branch name
   ```

2. **Railway will auto-deploy** (if connected to your GitHub repo)

3. **Get the OpenAPI spec** once deployed:
   ```bash
   # Replace with your Railway URL
   curl https://your-app.railway.app/openapi.json > openapi.json
   
   # Or visit in browser:
   # https://your-app.railway.app/openapi.json
   # https://your-app.railway.app/docs  (Swagger UI)
   ```

## 🔍 Finding Your Railway URL

Once deployed on Railway:
- Check your Railway dashboard: https://railway.app
- Look for your deployed service
- Click on it → find the "Domains" or "Settings" tab
- Your URL will be something like: `https://your-app-production.up.railway.app`

## ✅ Verify Deployment

```bash
# Health check
curl https://your-app.railway.app/health

# OpenAPI spec
curl https://your-app.railway.app/openapi.json | jq .info

# Swagger UI
open https://your-app.railway.app/docs
```

## 📝 Quick Commands

```bash
# Export OpenAPI spec from Railway
RAILWAY_URL="https://your-app.railway.app"
curl -s "$RAILWAY_URL/openapi.json" | python3 -m json.tool > openapi.json

# Count endpoints
cat openapi.json | jq '.paths | keys | length'

# View all endpoints
cat openapi.json | jq '.paths | keys'
```

---

**Note:** Railway auto-generates the OpenAPI spec from your FastAPI code - no additional configuration needed!



## 🚀 Quick Steps

1. **Push your code to GitHub:**
   ```bash
   cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend
   
   # Check what branch you're on
   git branch --show-current
   
   # Add all changes
   git add .
   
   # Commit (or skip if you want to review first)
   git commit -m "Add tests and update Shunya integration"
   
   # Push to GitHub
   git push origin main  # or your branch name
   ```

2. **Railway will auto-deploy** (if connected to your GitHub repo)

3. **Get the OpenAPI spec** once deployed:
   ```bash
   # Replace with your Railway URL
   curl https://your-app.railway.app/openapi.json > openapi.json
   
   # Or visit in browser:
   # https://your-app.railway.app/openapi.json
   # https://your-app.railway.app/docs  (Swagger UI)
   ```

## 🔍 Finding Your Railway URL

Once deployed on Railway:
- Check your Railway dashboard: https://railway.app
- Look for your deployed service
- Click on it → find the "Domains" or "Settings" tab
- Your URL will be something like: `https://your-app-production.up.railway.app`

## ✅ Verify Deployment

```bash
# Health check
curl https://your-app.railway.app/health

# OpenAPI spec
curl https://your-app.railway.app/openapi.json | jq .info

# Swagger UI
open https://your-app.railway.app/docs
```

## 📝 Quick Commands

```bash
# Export OpenAPI spec from Railway
RAILWAY_URL="https://your-app.railway.app"
curl -s "$RAILWAY_URL/openapi.json" | python3 -m json.tool > openapi.json

# Count endpoints
cat openapi.json | jq '.paths | keys | length'

# View all endpoints
cat openapi.json | jq '.paths | keys'
```

---

**Note:** Railway auto-generates the OpenAPI spec from your FastAPI code - no additional configuration needed!



## 🚀 Quick Steps

1. **Push your code to GitHub:**
   ```bash
   cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend
   
   # Check what branch you're on
   git branch --show-current
   
   # Add all changes
   git add .
   
   # Commit (or skip if you want to review first)
   git commit -m "Add tests and update Shunya integration"
   
   # Push to GitHub
   git push origin main  # or your branch name
   ```

2. **Railway will auto-deploy** (if connected to your GitHub repo)

3. **Get the OpenAPI spec** once deployed:
   ```bash
   # Replace with your Railway URL
   curl https://your-app.railway.app/openapi.json > openapi.json
   
   # Or visit in browser:
   # https://your-app.railway.app/openapi.json
   # https://your-app.railway.app/docs  (Swagger UI)
   ```

## 🔍 Finding Your Railway URL

Once deployed on Railway:
- Check your Railway dashboard: https://railway.app
- Look for your deployed service
- Click on it → find the "Domains" or "Settings" tab
- Your URL will be something like: `https://your-app-production.up.railway.app`

## ✅ Verify Deployment

```bash
# Health check
curl https://your-app.railway.app/health

# OpenAPI spec
curl https://your-app.railway.app/openapi.json | jq .info

# Swagger UI
open https://your-app.railway.app/docs
```

## 📝 Quick Commands

```bash
# Export OpenAPI spec from Railway
RAILWAY_URL="https://your-app.railway.app"
curl -s "$RAILWAY_URL/openapi.json" | python3 -m json.tool > openapi.json

# Count endpoints
cat openapi.json | jq '.paths | keys | length'

# View all endpoints
cat openapi.json | jq '.paths | keys'
```

---

**Note:** Railway auto-generates the OpenAPI spec from your FastAPI code - no additional configuration needed!


