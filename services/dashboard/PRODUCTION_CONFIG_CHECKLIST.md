# Production Configuration Checklist

## 🎯 Quick Verification Guide

### 1. Check Environment Variables

#### If using Railway:
```bash
# Install Railway CLI (if not installed)
npm i -g @railway/cli

# Login
railway login

# Link to your project (if needed)
railway link

# Check variables
railway variables
```

#### If using Railway Dashboard:
1. Go to https://railway.app
2. Select your project
3. Click on your service → Variables tab
4. Verify all variables are set

### 2. Required Production Variables

#### ✅ Critical Variables (MUST be set):

```bash
# OpenAI (5 keys for rotation)
OPENAI_API_KEYS=sk-key1,sk-key2,sk-key3,sk-key4,sk-key5

# Redis (for Celery + rate limiting)
REDIS_URL=redis://host:port
# OR
UPSTASH_REDIS_URL=redis://:password@host:port

# Celery (required for property intelligence)
ENABLE_CELERY=true

# Database
DATABASE_URL=postgresql://user:pass@host:port/db

# Environment
ENVIRONMENT=production
```

#### ⚙️ Optional (but recommended):

```bash
# OpenAI rotation strategy
OPENAI_KEY_ROTATION_STRATEGY=round_robin
# Options: round_robin, random, least_used

# Celery Beat (for scheduled tasks)
ENABLE_CELERY_BEAT=true
```

### 3. Verify Redis Connection

#### Option A: Via Production API
```bash
# Get your production URL first
PROD_URL=https://your-app.railway.app

# Test health (includes Redis check)
curl $PROD_URL/health/detailed
```

Expected response:
```json
{
  "status": "healthy",
  "redis": {
    "status": "healthy",
    "connected": true
  }
}
```

#### Option B: Check Production Logs
In Railway dashboard:
1. Go to your service → Logs
2. Look for: `"Connected to Redis successfully"` or `"Failed to connect to Redis"`

#### Option C: Check via Railway CLI
```bash
# Connect to your service
railway shell

# Test Redis connection (if redis-cli is available)
python -c "from app.services.redis_service import redis_service; print(redis_service.health_check())"
```

### 4. Verify OpenAI Keys

#### Via Production API:
```bash
# Get auth token (exec/manager role required)
AUTH_TOKEN="your-jwt-token"

# Check OpenAI stats
curl -H "Authorization: Bearer $AUTH_TOKEN" \
  $PROD_URL/api/v1/admin/openai/stats
```

Expected response:
```json
{
  "success": true,
  "data": {
    "total_keys": 5,
    "healthy_keys": 5,
    "rotation_strategy": "round_robin",
    "keys": { ... }
  }
}
```

#### Via Production Logs:
Look for startup message:
```
INFO: Initialized OpenAI client manager with 5 key(s), strategy: round_robin
```

### 5. Verify Celery Worker

Property intelligence requires a Celery worker running. Check:

#### Option A: Railway Service Status
1. Go to Railway dashboard
2. Check if you have a separate Celery worker service
3. Verify it's running: `celery -A app.celery_app worker --queues=analysis`

#### Option B: Check Production Logs
Look for:
```
INFO: Celery worker started
```

Or check worker process:
```bash
railway logs --service worker  # if separate service
```

### 6. Test Property Intelligence

#### Manual Trigger:
```bash
# Get contact card ID and auth token
CONTACT_ID="your-contact-card-id"
AUTH_TOKEN="your-jwt-token"

# Trigger property scrape
curl -X POST \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  $PROD_URL/api/v1/contact-cards/$CONTACT_ID/refresh-property
```

Expected: `202 Accepted` with `{"status": "queued"}`

#### Check Celery Task:
1. Check worker logs for task execution
2. Look for: `scrape_property_intelligence` task logs
3. Verify no errors

### 7. Common Issues & Solutions

#### ❌ "No healthy OpenAI API keys available"
**Fix:**
- Verify `OPENAI_API_KEYS` is set in production
- Check format: comma-separated, no spaces: `key1,key2,key3`
- Verify keys are valid (check OpenAI dashboard)

#### ❌ "REDIS_URL or UPSTASH_REDIS_URL must be set"
**Fix:**
- Add `REDIS_URL` or `UPSTASH_REDIS_URL` to production environment
- For Railway: Add Redis service and link it
- For Upstash: Create Redis database and copy connection URL

#### ❌ "Celery worker not processing tasks"
**Fix:**
- Ensure `ENABLE_CELERY=true` is set
- Check if Celery worker service is running
- Verify Redis is accessible from worker
- Check worker logs for errors

#### ❌ "Property intelligence not scraping"
**Fix:**
- Verify Celery worker is running with `--queues=analysis`
- Check if `ENABLE_CELERY=true` is set
- Verify contact card has an address set
- Check worker logs for task execution

### 8. Railway-Specific Commands

```bash
# View all environment variables
railway variables

# Set a variable
railway variables set OPENAI_API_KEYS="sk-key1,sk-key2,sk-key3"

# Get a specific variable
railway variables get REDIS_URL

# View logs
railway logs

# View logs for specific service
railway logs --service api
railway logs --service worker

# Connect to service shell
railway shell

# Restart service
railway restart
```

### 9. Production Monitoring

#### Health Endpoints:
- `GET /health` - Basic health check
- `GET /health/detailed` - Full health (database, Redis, services)
- `GET /health/ready` - Kubernetes readiness probe
- `GET /metrics` - Prometheus metrics

#### Admin Endpoints (require auth):
- `GET /api/v1/admin/openai/stats` - OpenAI key usage stats

### 10. Quick Verification Script

Run the automated check:
```bash
./check_production.sh
```

This will:
- Check Railway CLI availability
- List critical environment variables
- Test production API endpoints
- Provide verification steps

## ✅ Production Checklist Summary

- [ ] `OPENAI_API_KEYS` set with 5 keys (comma-separated)
- [ ] `REDIS_URL` or `UPSTASH_REDIS_URL` set and accessible
- [ ] `ENABLE_CELERY=true` is set
- [ ] `DATABASE_URL` is set and accessible
- [ ] `ENVIRONMENT=production` is set
- [ ] Celery worker service is running
- [ ] Redis connection test passes (`/health/detailed`)
- [ ] OpenAI keys are loaded (check startup logs)
- [ ] Property intelligence scraping works (test via API)
- [ ] All services are healthy (check `/health/detailed`)

