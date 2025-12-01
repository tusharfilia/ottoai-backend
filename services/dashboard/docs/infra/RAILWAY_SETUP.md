# Railway Deployment Setup Guide

**Date**: 2025-01-30  
**Purpose**: Complete guide for deploying Otto backend on Railway with Celery workers and beat scheduler

---

## Overview

The Otto backend requires **three process types** to run in production:
1. **Web** - FastAPI application (handles HTTP requests)
2. **Worker** - Celery worker (processes background tasks)
3. **Beat** - Celery beat scheduler (runs periodic tasks)

All processes share the same codebase but serve different roles.

---

## Required Railway Add-ons

### 1. PostgreSQL Database ✅

**Status**: Railway-managed (auto-provisioned or add manually)

**Configuration**:
- Railway automatically sets `DATABASE_URL` environment variable
- No additional configuration needed

**Verification**:
```bash
# Check DATABASE_URL is set
railway variables
```

### 2. Redis ⚠️ **CRITICAL - MUST PROVISION**

**Status**: **REQUIRED** - Must be provisioned manually

**Options**:
1. **Upstash Redis** (Recommended for Railway)
   - Add via Railway dashboard: "Add Service" → "Upstash Redis"
   - Automatically sets `UPSTASH_REDIS_URL` environment variable

2. **Railway Redis** (If available)
   - Add via Railway dashboard: "Add Service" → "Redis"
   - Sets `REDIS_URL` environment variable

**Why Required**:
- Celery broker (task queue)
- Celery result backend
- Rate limiting storage
- WebSocket pub/sub
- Distributed locks for missed call queue

**Verification**:
```bash
# Check Redis URL is set
railway variables | grep -i redis

# Should see either:
# REDIS_URL=redis://...
# OR
# UPSTASH_REDIS_URL=redis://...
```

---

## Process Configuration

### Process Types in Procfile

The `Procfile` defines three process types:

```procfile
web: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
worker: celery -A app.celery_app worker --loglevel=info --queues=default,asr,analysis,followups,indexing,uwc,shunya
beat: celery -A app.celery_app beat --loglevel=info
```

### 1. Web Process

**Command**: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}`

**Purpose**:
- Handles all HTTP/HTTPS requests
- Serves FastAPI application
- Processes webhooks (CallRail, Twilio, Shunya, Clerk)
- Serves API endpoints for frontend

**Railway Configuration**:
- **Process Type**: `web`
- **Start Command**: Automatically detected from Procfile
- **Port**: Railway sets `$PORT` automatically (defaults to 8080)

**Resource Requirements**:
- **RAM**: Minimum 512MB, Recommended 1GB
- **CPU**: 1 vCPU sufficient for moderate load
- **Scaling**: Start with 1 dyno, scale to 2-3 for high availability

### 2. Worker Process

**Command**: `celery -A app.celery_app worker --loglevel=info --queues=default,asr,analysis,followups,indexing,uwc,shunya`

**Purpose**:
- Processes background tasks from Celery queues
- Handles Shunya job polling
- Processes call transcriptions
- Runs property intelligence scraping
- Handles follow-up emails
- Processes recording sessions

**Railway Configuration**:
- **Process Type**: `worker`
- **Start Command**: Automatically detected from Procfile
- **Must Set**: `ENABLE_CELERY=true` environment variable

**Resource Requirements**:
- **RAM**: Minimum 512MB, Recommended 1GB (for property intelligence)
- **CPU**: 1 vCPU sufficient
- **Scaling**: Start with 1 worker, scale to 2-3 for task throughput

**Queues Handled**:
- `default` - General tasks
- `asr` - Automatic Speech Recognition tasks
- `analysis` - Call analysis and property intelligence
- `followups` - Follow-up email tasks
- `indexing` - Document indexing tasks
- `uwc` - UWC/Shunya integration tasks
- `shunya` - Shunya job polling tasks

### 3. Beat Process

**Command**: `celery -A app.celery_app beat --loglevel=info`

**Purpose**:
- Celery Beat scheduler (cron-like for Celery)
- Runs periodic tasks on schedule:
  - `process-pending-transcriptions`: Every 60 seconds
  - `generate-daily-reports`: Daily at midnight UTC
  - `cleanup-old-tasks`: Hourly
  - `cleanup-ephemeral-sessions`: Hourly

**Railway Configuration**:
- **Process Type**: `beat`
- **Start Command**: Automatically detected from Procfile
- **Must Set**: `ENABLE_CELERY_BEAT=true` environment variable
- **Important**: Only run **1 instance** (singleton - multiple instances cause duplicate tasks)

**Resource Requirements**:
- **RAM**: 256MB sufficient (lightweight scheduler)
- **CPU**: 0.5 vCPU sufficient
- **Scaling**: **Always 1 instance** (do not scale)

---

## Required Environment Variables

### Critical Variables (Must Set)

#### Celery Configuration
```bash
ENABLE_CELERY=true              # Enable Celery workers
ENABLE_CELERY_BEAT=true         # Enable Celery Beat scheduler
```

#### Redis Connection
```bash
# Either one of these (Railway/Upstash sets automatically):
REDIS_URL=redis://...           # If using Railway Redis
UPSTASH_REDIS_URL=redis://...   # If using Upstash Redis

# The app checks both, so either works
```

#### Database (Auto-set by Railway)
```bash
DATABASE_URL=postgresql://...   # Railway sets automatically
```

### Other Required Variables

See `INFRASTRUCTURE_AUDIT.md` for complete list. Key ones:
- `CLERK_SECRET_KEY` - Authentication
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` - SMS
- `CALLRAIL_API_KEY`, `CALLRAIL_ACCOUNT_ID` - Call tracking
- `UWC_API_KEY`, `UWC_HMAC_SECRET` - Shunya integration
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` - S3 storage
- `ENVIRONMENT=production` - Environment flag

---

## Railway Setup Steps

### Step 1: Create Railway Project

1. Go to [Railway Dashboard](https://railway.app)
2. Click "New Project"
3. Select "Deploy from GitHub repo" (or connect your repo)

### Step 2: Add PostgreSQL

1. Click "New" → "Database" → "PostgreSQL"
2. Railway automatically sets `DATABASE_URL`
3. Wait for database to provision

### Step 3: Add Redis

**Option A: Upstash Redis (Recommended)**
1. Click "New" → "Upstash Redis"
2. Railway automatically sets `UPSTASH_REDIS_URL`
3. Wait for Redis to provision

**Option B: Railway Redis (If available)**
1. Click "New" → "Redis"
2. Railway automatically sets `REDIS_URL`

### Step 4: Configure Environment Variables

1. Go to your service → "Variables"
2. Set the following **critical** variables:

```bash
# Celery (REQUIRED)
ENABLE_CELERY=true
ENABLE_CELERY_BEAT=true

# Environment
ENVIRONMENT=production

# Add all other required variables (see INFRASTRUCTURE_AUDIT.md)
```

### Step 5: Configure Process Types

Railway automatically detects the `Procfile` and creates three services:

1. **Web Service** (from `web:` line)
   - Automatically configured
   - Port exposed via Railway's public domain

2. **Worker Service** (from `worker:` line)
   - Railway may not auto-detect - you may need to:
     - Go to "Settings" → "Service"
     - Set "Start Command" to: `celery -A app.celery_app worker --loglevel=info --queues=default,asr,analysis,followups,indexing,uwc,shunya`
     - Or ensure Railway detects the Procfile

3. **Beat Service** (from `beat:` line)
   - Railway may not auto-detect - you may need to:
     - Create a new service
     - Set "Start Command" to: `celery -A app.celery_app beat --loglevel=info`

**Note**: Railway's Procfile detection varies. If processes don't auto-start:
- Check Railway logs for errors
- Manually create services and set start commands
- Ensure `ENABLE_CELERY=true` and `ENABLE_CELERY_BEAT=true` are set

### Step 6: Set Resource Limits

For each service, set resource limits:

**Web Service**:
- RAM: 1GB
- CPU: 1 vCPU

**Worker Service**:
- RAM: 1GB
- CPU: 1 vCPU

**Beat Service**:
- RAM: 256MB
- CPU: 0.5 vCPU

### Step 7: Deploy

1. Push code to GitHub (Railway auto-deploys)
2. Or trigger manual deploy from Railway dashboard
3. Monitor logs for all three services

---

## Verification

### Check Web Process

```bash
# Check web service is running
curl https://your-app.railway.app/health

# Should return: {"status": "healthy"}
```

### Check Worker Process

```bash
# Check Railway logs for worker service
# Should see:
# [INFO] celery@worker-xxx ready
# [INFO] Connected to redis://...
```

### Check Beat Process

```bash
# Check Railway logs for beat service
# Should see:
# [INFO] beat: Starting...
# [INFO] Scheduler: Sending due task process-pending-transcriptions
```

### Check Redis Connection

```bash
# In Railway, check worker logs for:
# [INFO] Connected to redis://...
# If you see connection errors, verify REDIS_URL or UPSTASH_REDIS_URL is set
```

### Check Celery Tasks

```bash
# In Railway, check worker logs for task processing:
# [INFO] Task app.tasks.shunya_job_polling_tasks.poll_shunya_job_status[...] received
# [INFO] Task app.tasks.shunya_job_polling_tasks.poll_shunya_job_status[...] succeeded
```

---

## Local Development Setup

### Using Foreman (Recommended)

**Install Foreman**:
```bash
# macOS
brew install foreman

# Linux
gem install foreman
```

**Create `.env` file**:
```bash
# Copy from env.template
cp env.template .env

# Set required variables:
ENABLE_CELERY=true
ENABLE_CELERY_BEAT=true
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql://localhost/otto_dev
# ... other variables
```

**Start all processes**:
```bash
# From services/dashboard directory
foreman start

# Output:
# web.1    | INFO:     Uvicorn running on http://0.0.0.0:8080
# worker.1 | [INFO] celery@localhost ready
# beat.1   | [INFO] beat: Starting...
```

**Stop all processes**:
```bash
# Press Ctrl+C
```

### Using Honcho (Alternative)

**Install Honcho**:
```bash
pip install honcho
```

**Start all processes**:
```bash
honcho start
```

### Manual Start (For Debugging)

**Terminal 1 - Web**:
```bash
cd services/dashboard
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

**Terminal 2 - Worker**:
```bash
cd services/dashboard
export ENABLE_CELERY=true
export REDIS_URL=redis://localhost:6379/0
celery -A app.celery_app worker --loglevel=info --queues=default,asr,analysis,followups,indexing,uwc,shunya
```

**Terminal 3 - Beat**:
```bash
cd services/dashboard
export ENABLE_CELERY_BEAT=true
export REDIS_URL=redis://localhost:6379/0
celery -A app.celery_app beat --loglevel=info
```

---

## Troubleshooting

### Worker Not Processing Tasks

**Symptoms**: Tasks queued but not processed

**Checks**:
1. Verify `ENABLE_CELERY=true` is set
2. Verify `REDIS_URL` or `UPSTASH_REDIS_URL` is set and accessible
3. Check worker logs for connection errors
4. Verify worker is listening to correct queues

**Fix**:
```bash
# Check Redis connection
railway variables | grep -i redis

# Check worker logs
railway logs --service worker
```

### Beat Not Running Scheduled Tasks

**Symptoms**: Periodic tasks not running

**Checks**:
1. Verify `ENABLE_CELERY_BEAT=true` is set
2. Verify only **1 beat instance** is running (multiple instances cause conflicts)
3. Check beat logs for errors

**Fix**:
```bash
# Ensure only one beat service exists
# Check beat logs
railway logs --service beat
```

### Redis Connection Errors

**Symptoms**: `Connection refused` or `Unable to connect to Redis`

**Checks**:
1. Verify Redis add-on is provisioned
2. Verify `REDIS_URL` or `UPSTASH_REDIS_URL` is set
3. Check Redis add-on status in Railway dashboard

**Fix**:
```bash
# Re-provision Redis if needed
# Verify connection string format:
# redis://username:password@host:port/db
```

### Web Process Crashes

**Symptoms**: Web service restarts frequently

**Checks**:
1. Check web logs for errors
2. Verify all required environment variables are set
3. Check database connection

**Fix**:
```bash
# Check web logs
railway logs --service web

# Verify DATABASE_URL is set
railway variables | grep DATABASE_URL
```

---

## Scaling Recommendations

### Initial Launch (Low Traffic)

- **Web**: 1 dyno (1GB RAM, 1 vCPU)
- **Worker**: 1 dyno (1GB RAM, 1 vCPU)
- **Beat**: 1 dyno (256MB RAM, 0.5 vCPU)

### Moderate Traffic (10-100 concurrent users)

- **Web**: 2-3 dynos (1GB RAM each, 1 vCPU each)
- **Worker**: 2-3 dynos (1GB RAM each, 1 vCPU each)
- **Beat**: 1 dyno (256MB RAM, 0.5 vCPU) - **Always 1**

### High Traffic (100+ concurrent users)

- **Web**: 3-5 dynos (1GB RAM each, 1 vCPU each)
- **Worker**: 3-5 dynos (1GB RAM each, 1 vCPU each)
- **Beat**: 1 dyno (256MB RAM, 0.5 vCPU) - **Always 1**

**Note**: Monitor Railway metrics and scale based on:
- CPU usage > 70%
- Memory usage > 80%
- Request latency > 500ms
- Task queue backlog

---

## Cost Estimation

### Railway Pricing (Approximate)

**PostgreSQL**: 
- Hobby: Free (512MB RAM, 1GB storage)
- Pro: $20/month (1GB RAM, 10GB storage)

**Redis (Upstash)**:
- Free tier: 10K commands/day
- Pay-as-you-go: ~$0.20 per 100K commands

**Dynos**:
- Web: $5-20/month per dyno (depending on resources)
- Worker: $5-20/month per dyno
- Beat: $2-5/month (small instance)

**Total Estimated Cost**:
- **Minimum (1 web, 1 worker, 1 beat)**: ~$15-30/month
- **Moderate (2-3 web, 2-3 worker, 1 beat)**: ~$40-80/month
- **High (3-5 web, 3-5 worker, 1 beat)**: ~$80-150/month

---

## Additional Resources

- **Infrastructure Audit**: See `INFRASTRUCTURE_AUDIT.md` for complete infrastructure assessment
- **Environment Variables**: See `env.template` for all available variables
- **Celery Configuration**: See `app/celery_app.py` for Celery setup
- **Railway Docs**: https://docs.railway.app

---

## Quick Reference

### Procfile Location
```
services/dashboard/Procfile
```

### Celery App Path
```
app.celery_app:celery_app
```

### Critical Env Vars
```bash
ENABLE_CELERY=true
ENABLE_CELERY_BEAT=true
REDIS_URL=redis://...  # OR UPSTASH_REDIS_URL
DATABASE_URL=postgresql://...
```

### Process Commands
```bash
# Web
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}

# Worker
celery -A app.celery_app worker --loglevel=info --queues=default,asr,analysis,followups,indexing,uwc,shunya

# Beat
celery -A app.celery_app beat --loglevel=info
```



**Date**: 2025-01-30  
**Purpose**: Complete guide for deploying Otto backend on Railway with Celery workers and beat scheduler

---

## Overview

The Otto backend requires **three process types** to run in production:
1. **Web** - FastAPI application (handles HTTP requests)
2. **Worker** - Celery worker (processes background tasks)
3. **Beat** - Celery beat scheduler (runs periodic tasks)

All processes share the same codebase but serve different roles.

---

## Required Railway Add-ons

### 1. PostgreSQL Database ✅

**Status**: Railway-managed (auto-provisioned or add manually)

**Configuration**:
- Railway automatically sets `DATABASE_URL` environment variable
- No additional configuration needed

**Verification**:
```bash
# Check DATABASE_URL is set
railway variables
```

### 2. Redis ⚠️ **CRITICAL - MUST PROVISION**

**Status**: **REQUIRED** - Must be provisioned manually

**Options**:
1. **Upstash Redis** (Recommended for Railway)
   - Add via Railway dashboard: "Add Service" → "Upstash Redis"
   - Automatically sets `UPSTASH_REDIS_URL` environment variable

2. **Railway Redis** (If available)
   - Add via Railway dashboard: "Add Service" → "Redis"
   - Sets `REDIS_URL` environment variable

**Why Required**:
- Celery broker (task queue)
- Celery result backend
- Rate limiting storage
- WebSocket pub/sub
- Distributed locks for missed call queue

**Verification**:
```bash
# Check Redis URL is set
railway variables | grep -i redis

# Should see either:
# REDIS_URL=redis://...
# OR
# UPSTASH_REDIS_URL=redis://...
```

---

## Process Configuration

### Process Types in Procfile

The `Procfile` defines three process types:

```procfile
web: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
worker: celery -A app.celery_app worker --loglevel=info --queues=default,asr,analysis,followups,indexing,uwc,shunya
beat: celery -A app.celery_app beat --loglevel=info
```

### 1. Web Process

**Command**: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}`

**Purpose**:
- Handles all HTTP/HTTPS requests
- Serves FastAPI application
- Processes webhooks (CallRail, Twilio, Shunya, Clerk)
- Serves API endpoints for frontend

**Railway Configuration**:
- **Process Type**: `web`
- **Start Command**: Automatically detected from Procfile
- **Port**: Railway sets `$PORT` automatically (defaults to 8080)

**Resource Requirements**:
- **RAM**: Minimum 512MB, Recommended 1GB
- **CPU**: 1 vCPU sufficient for moderate load
- **Scaling**: Start with 1 dyno, scale to 2-3 for high availability

### 2. Worker Process

**Command**: `celery -A app.celery_app worker --loglevel=info --queues=default,asr,analysis,followups,indexing,uwc,shunya`

**Purpose**:
- Processes background tasks from Celery queues
- Handles Shunya job polling
- Processes call transcriptions
- Runs property intelligence scraping
- Handles follow-up emails
- Processes recording sessions

**Railway Configuration**:
- **Process Type**: `worker`
- **Start Command**: Automatically detected from Procfile
- **Must Set**: `ENABLE_CELERY=true` environment variable

**Resource Requirements**:
- **RAM**: Minimum 512MB, Recommended 1GB (for property intelligence)
- **CPU**: 1 vCPU sufficient
- **Scaling**: Start with 1 worker, scale to 2-3 for task throughput

**Queues Handled**:
- `default` - General tasks
- `asr` - Automatic Speech Recognition tasks
- `analysis` - Call analysis and property intelligence
- `followups` - Follow-up email tasks
- `indexing` - Document indexing tasks
- `uwc` - UWC/Shunya integration tasks
- `shunya` - Shunya job polling tasks

### 3. Beat Process

**Command**: `celery -A app.celery_app beat --loglevel=info`

**Purpose**:
- Celery Beat scheduler (cron-like for Celery)
- Runs periodic tasks on schedule:
  - `process-pending-transcriptions`: Every 60 seconds
  - `generate-daily-reports`: Daily at midnight UTC
  - `cleanup-old-tasks`: Hourly
  - `cleanup-ephemeral-sessions`: Hourly

**Railway Configuration**:
- **Process Type**: `beat`
- **Start Command**: Automatically detected from Procfile
- **Must Set**: `ENABLE_CELERY_BEAT=true` environment variable
- **Important**: Only run **1 instance** (singleton - multiple instances cause duplicate tasks)

**Resource Requirements**:
- **RAM**: 256MB sufficient (lightweight scheduler)
- **CPU**: 0.5 vCPU sufficient
- **Scaling**: **Always 1 instance** (do not scale)

---

## Required Environment Variables

### Critical Variables (Must Set)

#### Celery Configuration
```bash
ENABLE_CELERY=true              # Enable Celery workers
ENABLE_CELERY_BEAT=true         # Enable Celery Beat scheduler
```

#### Redis Connection
```bash
# Either one of these (Railway/Upstash sets automatically):
REDIS_URL=redis://...           # If using Railway Redis
UPSTASH_REDIS_URL=redis://...   # If using Upstash Redis

# The app checks both, so either works
```

#### Database (Auto-set by Railway)
```bash
DATABASE_URL=postgresql://...   # Railway sets automatically
```

### Other Required Variables

See `INFRASTRUCTURE_AUDIT.md` for complete list. Key ones:
- `CLERK_SECRET_KEY` - Authentication
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` - SMS
- `CALLRAIL_API_KEY`, `CALLRAIL_ACCOUNT_ID` - Call tracking
- `UWC_API_KEY`, `UWC_HMAC_SECRET` - Shunya integration
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` - S3 storage
- `ENVIRONMENT=production` - Environment flag

---

## Railway Setup Steps

### Step 1: Create Railway Project

1. Go to [Railway Dashboard](https://railway.app)
2. Click "New Project"
3. Select "Deploy from GitHub repo" (or connect your repo)

### Step 2: Add PostgreSQL

1. Click "New" → "Database" → "PostgreSQL"
2. Railway automatically sets `DATABASE_URL`
3. Wait for database to provision

### Step 3: Add Redis

**Option A: Upstash Redis (Recommended)**
1. Click "New" → "Upstash Redis"
2. Railway automatically sets `UPSTASH_REDIS_URL`
3. Wait for Redis to provision

**Option B: Railway Redis (If available)**
1. Click "New" → "Redis"
2. Railway automatically sets `REDIS_URL`

### Step 4: Configure Environment Variables

1. Go to your service → "Variables"
2. Set the following **critical** variables:

```bash
# Celery (REQUIRED)
ENABLE_CELERY=true
ENABLE_CELERY_BEAT=true

# Environment
ENVIRONMENT=production

# Add all other required variables (see INFRASTRUCTURE_AUDIT.md)
```

### Step 5: Configure Process Types

Railway automatically detects the `Procfile` and creates three services:

1. **Web Service** (from `web:` line)
   - Automatically configured
   - Port exposed via Railway's public domain

2. **Worker Service** (from `worker:` line)
   - Railway may not auto-detect - you may need to:
     - Go to "Settings" → "Service"
     - Set "Start Command" to: `celery -A app.celery_app worker --loglevel=info --queues=default,asr,analysis,followups,indexing,uwc,shunya`
     - Or ensure Railway detects the Procfile

3. **Beat Service** (from `beat:` line)
   - Railway may not auto-detect - you may need to:
     - Create a new service
     - Set "Start Command" to: `celery -A app.celery_app beat --loglevel=info`

**Note**: Railway's Procfile detection varies. If processes don't auto-start:
- Check Railway logs for errors
- Manually create services and set start commands
- Ensure `ENABLE_CELERY=true` and `ENABLE_CELERY_BEAT=true` are set

### Step 6: Set Resource Limits

For each service, set resource limits:

**Web Service**:
- RAM: 1GB
- CPU: 1 vCPU

**Worker Service**:
- RAM: 1GB
- CPU: 1 vCPU

**Beat Service**:
- RAM: 256MB
- CPU: 0.5 vCPU

### Step 7: Deploy

1. Push code to GitHub (Railway auto-deploys)
2. Or trigger manual deploy from Railway dashboard
3. Monitor logs for all three services

---

## Verification

### Check Web Process

```bash
# Check web service is running
curl https://your-app.railway.app/health

# Should return: {"status": "healthy"}
```

### Check Worker Process

```bash
# Check Railway logs for worker service
# Should see:
# [INFO] celery@worker-xxx ready
# [INFO] Connected to redis://...
```

### Check Beat Process

```bash
# Check Railway logs for beat service
# Should see:
# [INFO] beat: Starting...
# [INFO] Scheduler: Sending due task process-pending-transcriptions
```

### Check Redis Connection

```bash
# In Railway, check worker logs for:
# [INFO] Connected to redis://...
# If you see connection errors, verify REDIS_URL or UPSTASH_REDIS_URL is set
```

### Check Celery Tasks

```bash
# In Railway, check worker logs for task processing:
# [INFO] Task app.tasks.shunya_job_polling_tasks.poll_shunya_job_status[...] received
# [INFO] Task app.tasks.shunya_job_polling_tasks.poll_shunya_job_status[...] succeeded
```

---

## Local Development Setup

### Using Foreman (Recommended)

**Install Foreman**:
```bash
# macOS
brew install foreman

# Linux
gem install foreman
```

**Create `.env` file**:
```bash
# Copy from env.template
cp env.template .env

# Set required variables:
ENABLE_CELERY=true
ENABLE_CELERY_BEAT=true
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql://localhost/otto_dev
# ... other variables
```

**Start all processes**:
```bash
# From services/dashboard directory
foreman start

# Output:
# web.1    | INFO:     Uvicorn running on http://0.0.0.0:8080
# worker.1 | [INFO] celery@localhost ready
# beat.1   | [INFO] beat: Starting...
```

**Stop all processes**:
```bash
# Press Ctrl+C
```

### Using Honcho (Alternative)

**Install Honcho**:
```bash
pip install honcho
```

**Start all processes**:
```bash
honcho start
```

### Manual Start (For Debugging)

**Terminal 1 - Web**:
```bash
cd services/dashboard
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

**Terminal 2 - Worker**:
```bash
cd services/dashboard
export ENABLE_CELERY=true
export REDIS_URL=redis://localhost:6379/0
celery -A app.celery_app worker --loglevel=info --queues=default,asr,analysis,followups,indexing,uwc,shunya
```

**Terminal 3 - Beat**:
```bash
cd services/dashboard
export ENABLE_CELERY_BEAT=true
export REDIS_URL=redis://localhost:6379/0
celery -A app.celery_app beat --loglevel=info
```

---

## Troubleshooting

### Worker Not Processing Tasks

**Symptoms**: Tasks queued but not processed

**Checks**:
1. Verify `ENABLE_CELERY=true` is set
2. Verify `REDIS_URL` or `UPSTASH_REDIS_URL` is set and accessible
3. Check worker logs for connection errors
4. Verify worker is listening to correct queues

**Fix**:
```bash
# Check Redis connection
railway variables | grep -i redis

# Check worker logs
railway logs --service worker
```

### Beat Not Running Scheduled Tasks

**Symptoms**: Periodic tasks not running

**Checks**:
1. Verify `ENABLE_CELERY_BEAT=true` is set
2. Verify only **1 beat instance** is running (multiple instances cause conflicts)
3. Check beat logs for errors

**Fix**:
```bash
# Ensure only one beat service exists
# Check beat logs
railway logs --service beat
```

### Redis Connection Errors

**Symptoms**: `Connection refused` or `Unable to connect to Redis`

**Checks**:
1. Verify Redis add-on is provisioned
2. Verify `REDIS_URL` or `UPSTASH_REDIS_URL` is set
3. Check Redis add-on status in Railway dashboard

**Fix**:
```bash
# Re-provision Redis if needed
# Verify connection string format:
# redis://username:password@host:port/db
```

### Web Process Crashes

**Symptoms**: Web service restarts frequently

**Checks**:
1. Check web logs for errors
2. Verify all required environment variables are set
3. Check database connection

**Fix**:
```bash
# Check web logs
railway logs --service web

# Verify DATABASE_URL is set
railway variables | grep DATABASE_URL
```

---

## Scaling Recommendations

### Initial Launch (Low Traffic)

- **Web**: 1 dyno (1GB RAM, 1 vCPU)
- **Worker**: 1 dyno (1GB RAM, 1 vCPU)
- **Beat**: 1 dyno (256MB RAM, 0.5 vCPU)

### Moderate Traffic (10-100 concurrent users)

- **Web**: 2-3 dynos (1GB RAM each, 1 vCPU each)
- **Worker**: 2-3 dynos (1GB RAM each, 1 vCPU each)
- **Beat**: 1 dyno (256MB RAM, 0.5 vCPU) - **Always 1**

### High Traffic (100+ concurrent users)

- **Web**: 3-5 dynos (1GB RAM each, 1 vCPU each)
- **Worker**: 3-5 dynos (1GB RAM each, 1 vCPU each)
- **Beat**: 1 dyno (256MB RAM, 0.5 vCPU) - **Always 1**

**Note**: Monitor Railway metrics and scale based on:
- CPU usage > 70%
- Memory usage > 80%
- Request latency > 500ms
- Task queue backlog

---

## Cost Estimation

### Railway Pricing (Approximate)

**PostgreSQL**: 
- Hobby: Free (512MB RAM, 1GB storage)
- Pro: $20/month (1GB RAM, 10GB storage)

**Redis (Upstash)**:
- Free tier: 10K commands/day
- Pay-as-you-go: ~$0.20 per 100K commands

**Dynos**:
- Web: $5-20/month per dyno (depending on resources)
- Worker: $5-20/month per dyno
- Beat: $2-5/month (small instance)

**Total Estimated Cost**:
- **Minimum (1 web, 1 worker, 1 beat)**: ~$15-30/month
- **Moderate (2-3 web, 2-3 worker, 1 beat)**: ~$40-80/month
- **High (3-5 web, 3-5 worker, 1 beat)**: ~$80-150/month

---

## Additional Resources

- **Infrastructure Audit**: See `INFRASTRUCTURE_AUDIT.md` for complete infrastructure assessment
- **Environment Variables**: See `env.template` for all available variables
- **Celery Configuration**: See `app/celery_app.py` for Celery setup
- **Railway Docs**: https://docs.railway.app

---

## Quick Reference

### Procfile Location
```
services/dashboard/Procfile
```

### Celery App Path
```
app.celery_app:celery_app
```

### Critical Env Vars
```bash
ENABLE_CELERY=true
ENABLE_CELERY_BEAT=true
REDIS_URL=redis://...  # OR UPSTASH_REDIS_URL
DATABASE_URL=postgresql://...
```

### Process Commands
```bash
# Web
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}

# Worker
celery -A app.celery_app worker --loglevel=info --queues=default,asr,analysis,followups,indexing,uwc,shunya

# Beat
celery -A app.celery_app beat --loglevel=info
```



**Date**: 2025-01-30  
**Purpose**: Complete guide for deploying Otto backend on Railway with Celery workers and beat scheduler

---

## Overview

The Otto backend requires **three process types** to run in production:
1. **Web** - FastAPI application (handles HTTP requests)
2. **Worker** - Celery worker (processes background tasks)
3. **Beat** - Celery beat scheduler (runs periodic tasks)

All processes share the same codebase but serve different roles.

---

## Required Railway Add-ons

### 1. PostgreSQL Database ✅

**Status**: Railway-managed (auto-provisioned or add manually)

**Configuration**:
- Railway automatically sets `DATABASE_URL` environment variable
- No additional configuration needed

**Verification**:
```bash
# Check DATABASE_URL is set
railway variables
```

### 2. Redis ⚠️ **CRITICAL - MUST PROVISION**

**Status**: **REQUIRED** - Must be provisioned manually

**Options**:
1. **Upstash Redis** (Recommended for Railway)
   - Add via Railway dashboard: "Add Service" → "Upstash Redis"
   - Automatically sets `UPSTASH_REDIS_URL` environment variable

2. **Railway Redis** (If available)
   - Add via Railway dashboard: "Add Service" → "Redis"
   - Sets `REDIS_URL` environment variable

**Why Required**:
- Celery broker (task queue)
- Celery result backend
- Rate limiting storage
- WebSocket pub/sub
- Distributed locks for missed call queue

**Verification**:
```bash
# Check Redis URL is set
railway variables | grep -i redis

# Should see either:
# REDIS_URL=redis://...
# OR
# UPSTASH_REDIS_URL=redis://...
```

---

## Process Configuration

### Process Types in Procfile

The `Procfile` defines three process types:

```procfile
web: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
worker: celery -A app.celery_app worker --loglevel=info --queues=default,asr,analysis,followups,indexing,uwc,shunya
beat: celery -A app.celery_app beat --loglevel=info
```

### 1. Web Process

**Command**: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}`

**Purpose**:
- Handles all HTTP/HTTPS requests
- Serves FastAPI application
- Processes webhooks (CallRail, Twilio, Shunya, Clerk)
- Serves API endpoints for frontend

**Railway Configuration**:
- **Process Type**: `web`
- **Start Command**: Automatically detected from Procfile
- **Port**: Railway sets `$PORT` automatically (defaults to 8080)

**Resource Requirements**:
- **RAM**: Minimum 512MB, Recommended 1GB
- **CPU**: 1 vCPU sufficient for moderate load
- **Scaling**: Start with 1 dyno, scale to 2-3 for high availability

### 2. Worker Process

**Command**: `celery -A app.celery_app worker --loglevel=info --queues=default,asr,analysis,followups,indexing,uwc,shunya`

**Purpose**:
- Processes background tasks from Celery queues
- Handles Shunya job polling
- Processes call transcriptions
- Runs property intelligence scraping
- Handles follow-up emails
- Processes recording sessions

**Railway Configuration**:
- **Process Type**: `worker`
- **Start Command**: Automatically detected from Procfile
- **Must Set**: `ENABLE_CELERY=true` environment variable

**Resource Requirements**:
- **RAM**: Minimum 512MB, Recommended 1GB (for property intelligence)
- **CPU**: 1 vCPU sufficient
- **Scaling**: Start with 1 worker, scale to 2-3 for task throughput

**Queues Handled**:
- `default` - General tasks
- `asr` - Automatic Speech Recognition tasks
- `analysis` - Call analysis and property intelligence
- `followups` - Follow-up email tasks
- `indexing` - Document indexing tasks
- `uwc` - UWC/Shunya integration tasks
- `shunya` - Shunya job polling tasks

### 3. Beat Process

**Command**: `celery -A app.celery_app beat --loglevel=info`

**Purpose**:
- Celery Beat scheduler (cron-like for Celery)
- Runs periodic tasks on schedule:
  - `process-pending-transcriptions`: Every 60 seconds
  - `generate-daily-reports`: Daily at midnight UTC
  - `cleanup-old-tasks`: Hourly
  - `cleanup-ephemeral-sessions`: Hourly

**Railway Configuration**:
- **Process Type**: `beat`
- **Start Command**: Automatically detected from Procfile
- **Must Set**: `ENABLE_CELERY_BEAT=true` environment variable
- **Important**: Only run **1 instance** (singleton - multiple instances cause duplicate tasks)

**Resource Requirements**:
- **RAM**: 256MB sufficient (lightweight scheduler)
- **CPU**: 0.5 vCPU sufficient
- **Scaling**: **Always 1 instance** (do not scale)

---

## Required Environment Variables

### Critical Variables (Must Set)

#### Celery Configuration
```bash
ENABLE_CELERY=true              # Enable Celery workers
ENABLE_CELERY_BEAT=true         # Enable Celery Beat scheduler
```

#### Redis Connection
```bash
# Either one of these (Railway/Upstash sets automatically):
REDIS_URL=redis://...           # If using Railway Redis
UPSTASH_REDIS_URL=redis://...   # If using Upstash Redis

# The app checks both, so either works
```

#### Database (Auto-set by Railway)
```bash
DATABASE_URL=postgresql://...   # Railway sets automatically
```

### Other Required Variables

See `INFRASTRUCTURE_AUDIT.md` for complete list. Key ones:
- `CLERK_SECRET_KEY` - Authentication
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` - SMS
- `CALLRAIL_API_KEY`, `CALLRAIL_ACCOUNT_ID` - Call tracking
- `UWC_API_KEY`, `UWC_HMAC_SECRET` - Shunya integration
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` - S3 storage
- `ENVIRONMENT=production` - Environment flag

---

## Railway Setup Steps

### Step 1: Create Railway Project

1. Go to [Railway Dashboard](https://railway.app)
2. Click "New Project"
3. Select "Deploy from GitHub repo" (or connect your repo)

### Step 2: Add PostgreSQL

1. Click "New" → "Database" → "PostgreSQL"
2. Railway automatically sets `DATABASE_URL`
3. Wait for database to provision

### Step 3: Add Redis

**Option A: Upstash Redis (Recommended)**
1. Click "New" → "Upstash Redis"
2. Railway automatically sets `UPSTASH_REDIS_URL`
3. Wait for Redis to provision

**Option B: Railway Redis (If available)**
1. Click "New" → "Redis"
2. Railway automatically sets `REDIS_URL`

### Step 4: Configure Environment Variables

1. Go to your service → "Variables"
2. Set the following **critical** variables:

```bash
# Celery (REQUIRED)
ENABLE_CELERY=true
ENABLE_CELERY_BEAT=true

# Environment
ENVIRONMENT=production

# Add all other required variables (see INFRASTRUCTURE_AUDIT.md)
```

### Step 5: Configure Process Types

Railway automatically detects the `Procfile` and creates three services:

1. **Web Service** (from `web:` line)
   - Automatically configured
   - Port exposed via Railway's public domain

2. **Worker Service** (from `worker:` line)
   - Railway may not auto-detect - you may need to:
     - Go to "Settings" → "Service"
     - Set "Start Command" to: `celery -A app.celery_app worker --loglevel=info --queues=default,asr,analysis,followups,indexing,uwc,shunya`
     - Or ensure Railway detects the Procfile

3. **Beat Service** (from `beat:` line)
   - Railway may not auto-detect - you may need to:
     - Create a new service
     - Set "Start Command" to: `celery -A app.celery_app beat --loglevel=info`

**Note**: Railway's Procfile detection varies. If processes don't auto-start:
- Check Railway logs for errors
- Manually create services and set start commands
- Ensure `ENABLE_CELERY=true` and `ENABLE_CELERY_BEAT=true` are set

### Step 6: Set Resource Limits

For each service, set resource limits:

**Web Service**:
- RAM: 1GB
- CPU: 1 vCPU

**Worker Service**:
- RAM: 1GB
- CPU: 1 vCPU

**Beat Service**:
- RAM: 256MB
- CPU: 0.5 vCPU

### Step 7: Deploy

1. Push code to GitHub (Railway auto-deploys)
2. Or trigger manual deploy from Railway dashboard
3. Monitor logs for all three services

---

## Verification

### Check Web Process

```bash
# Check web service is running
curl https://your-app.railway.app/health

# Should return: {"status": "healthy"}
```

### Check Worker Process

```bash
# Check Railway logs for worker service
# Should see:
# [INFO] celery@worker-xxx ready
# [INFO] Connected to redis://...
```

### Check Beat Process

```bash
# Check Railway logs for beat service
# Should see:
# [INFO] beat: Starting...
# [INFO] Scheduler: Sending due task process-pending-transcriptions
```

### Check Redis Connection

```bash
# In Railway, check worker logs for:
# [INFO] Connected to redis://...
# If you see connection errors, verify REDIS_URL or UPSTASH_REDIS_URL is set
```

### Check Celery Tasks

```bash
# In Railway, check worker logs for task processing:
# [INFO] Task app.tasks.shunya_job_polling_tasks.poll_shunya_job_status[...] received
# [INFO] Task app.tasks.shunya_job_polling_tasks.poll_shunya_job_status[...] succeeded
```

---

## Local Development Setup

### Using Foreman (Recommended)

**Install Foreman**:
```bash
# macOS
brew install foreman

# Linux
gem install foreman
```

**Create `.env` file**:
```bash
# Copy from env.template
cp env.template .env

# Set required variables:
ENABLE_CELERY=true
ENABLE_CELERY_BEAT=true
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql://localhost/otto_dev
# ... other variables
```

**Start all processes**:
```bash
# From services/dashboard directory
foreman start

# Output:
# web.1    | INFO:     Uvicorn running on http://0.0.0.0:8080
# worker.1 | [INFO] celery@localhost ready
# beat.1   | [INFO] beat: Starting...
```

**Stop all processes**:
```bash
# Press Ctrl+C
```

### Using Honcho (Alternative)

**Install Honcho**:
```bash
pip install honcho
```

**Start all processes**:
```bash
honcho start
```

### Manual Start (For Debugging)

**Terminal 1 - Web**:
```bash
cd services/dashboard
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

**Terminal 2 - Worker**:
```bash
cd services/dashboard
export ENABLE_CELERY=true
export REDIS_URL=redis://localhost:6379/0
celery -A app.celery_app worker --loglevel=info --queues=default,asr,analysis,followups,indexing,uwc,shunya
```

**Terminal 3 - Beat**:
```bash
cd services/dashboard
export ENABLE_CELERY_BEAT=true
export REDIS_URL=redis://localhost:6379/0
celery -A app.celery_app beat --loglevel=info
```

---

## Troubleshooting

### Worker Not Processing Tasks

**Symptoms**: Tasks queued but not processed

**Checks**:
1. Verify `ENABLE_CELERY=true` is set
2. Verify `REDIS_URL` or `UPSTASH_REDIS_URL` is set and accessible
3. Check worker logs for connection errors
4. Verify worker is listening to correct queues

**Fix**:
```bash
# Check Redis connection
railway variables | grep -i redis

# Check worker logs
railway logs --service worker
```

### Beat Not Running Scheduled Tasks

**Symptoms**: Periodic tasks not running

**Checks**:
1. Verify `ENABLE_CELERY_BEAT=true` is set
2. Verify only **1 beat instance** is running (multiple instances cause conflicts)
3. Check beat logs for errors

**Fix**:
```bash
# Ensure only one beat service exists
# Check beat logs
railway logs --service beat
```

### Redis Connection Errors

**Symptoms**: `Connection refused` or `Unable to connect to Redis`

**Checks**:
1. Verify Redis add-on is provisioned
2. Verify `REDIS_URL` or `UPSTASH_REDIS_URL` is set
3. Check Redis add-on status in Railway dashboard

**Fix**:
```bash
# Re-provision Redis if needed
# Verify connection string format:
# redis://username:password@host:port/db
```

### Web Process Crashes

**Symptoms**: Web service restarts frequently

**Checks**:
1. Check web logs for errors
2. Verify all required environment variables are set
3. Check database connection

**Fix**:
```bash
# Check web logs
railway logs --service web

# Verify DATABASE_URL is set
railway variables | grep DATABASE_URL
```

---

## Scaling Recommendations

### Initial Launch (Low Traffic)

- **Web**: 1 dyno (1GB RAM, 1 vCPU)
- **Worker**: 1 dyno (1GB RAM, 1 vCPU)
- **Beat**: 1 dyno (256MB RAM, 0.5 vCPU)

### Moderate Traffic (10-100 concurrent users)

- **Web**: 2-3 dynos (1GB RAM each, 1 vCPU each)
- **Worker**: 2-3 dynos (1GB RAM each, 1 vCPU each)
- **Beat**: 1 dyno (256MB RAM, 0.5 vCPU) - **Always 1**

### High Traffic (100+ concurrent users)

- **Web**: 3-5 dynos (1GB RAM each, 1 vCPU each)
- **Worker**: 3-5 dynos (1GB RAM each, 1 vCPU each)
- **Beat**: 1 dyno (256MB RAM, 0.5 vCPU) - **Always 1**

**Note**: Monitor Railway metrics and scale based on:
- CPU usage > 70%
- Memory usage > 80%
- Request latency > 500ms
- Task queue backlog

---

## Cost Estimation

### Railway Pricing (Approximate)

**PostgreSQL**: 
- Hobby: Free (512MB RAM, 1GB storage)
- Pro: $20/month (1GB RAM, 10GB storage)

**Redis (Upstash)**:
- Free tier: 10K commands/day
- Pay-as-you-go: ~$0.20 per 100K commands

**Dynos**:
- Web: $5-20/month per dyno (depending on resources)
- Worker: $5-20/month per dyno
- Beat: $2-5/month (small instance)

**Total Estimated Cost**:
- **Minimum (1 web, 1 worker, 1 beat)**: ~$15-30/month
- **Moderate (2-3 web, 2-3 worker, 1 beat)**: ~$40-80/month
- **High (3-5 web, 3-5 worker, 1 beat)**: ~$80-150/month

---

## Additional Resources

- **Infrastructure Audit**: See `INFRASTRUCTURE_AUDIT.md` for complete infrastructure assessment
- **Environment Variables**: See `env.template` for all available variables
- **Celery Configuration**: See `app/celery_app.py` for Celery setup
- **Railway Docs**: https://docs.railway.app

---

## Quick Reference

### Procfile Location
```
services/dashboard/Procfile
```

### Celery App Path
```
app.celery_app:celery_app
```

### Critical Env Vars
```bash
ENABLE_CELERY=true
ENABLE_CELERY_BEAT=true
REDIS_URL=redis://...  # OR UPSTASH_REDIS_URL
DATABASE_URL=postgresql://...
```

### Process Commands
```bash
# Web
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}

# Worker
celery -A app.celery_app worker --loglevel=info --queues=default,asr,analysis,followups,indexing,uwc,shunya

# Beat
celery -A app.celery_app beat --loglevel=info
```


