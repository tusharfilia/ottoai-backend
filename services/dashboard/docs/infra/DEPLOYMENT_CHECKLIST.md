# Deployment Checklist

**Date**: 2025-01-30  
**Purpose**: Concise deployment checklist for local dev, staging, and production environments

---

## Related Documentation

- **`RAILWAY_SETUP.md`** - Complete Railway deployment guide with process configuration
- **`ENV_VARS_REFERENCE.md`** - Complete list of all environment variables
- **`ASYNC_HOTSPOTS_FIXES.md`** - Async performance fixes applied
- **`DB_INDEXES.md`** - Database indexes for performance optimization
- **`HOTSPOT_FIX_PLAN.md`** - Query optimization and pagination improvements
- **`../INFRASTRUCTURE_AUDIT.md`** - Infrastructure audit and requirements (root level)

---

## Local Development

### Prerequisites

- [ ] Python 3.11+ installed
- [ ] PostgreSQL running locally (or use SQLite for basic testing)
- [ ] Redis running locally (optional, if testing Celery/rate limiting)

### Setup Steps

- [ ] Clone repository and navigate to `services/dashboard`
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Copy `.env.example` to `.env` and configure:
  - [ ] `DATABASE_URL` (PostgreSQL or SQLite)
  - [ ] `CLERK_SECRET_KEY` (or disable auth for testing)
  - [ ] `REDIS_URL` (if testing Celery: `redis://localhost:6379/0`)
- [ ] Run migrations: `alembic upgrade head`
- [ ] Start web process: `uvicorn app.main:app --reload`
- [ ] (Optional) Start Celery worker: `celery -A app.celery_app worker --loglevel=info`
- [ ] (Optional) Start Celery beat: `celery -A app.celery_app beat --loglevel=info`

### Verification

- [ ] Web server starts without errors
- [ ] Health check: `curl http://localhost:8080/health`
- [ ] Database connection works (check logs)
- [ ] (If Celery enabled) Worker connects to Redis and processes tasks

---

## Staging

### Infrastructure

- [ ] **PostgreSQL**: Provisioned and `DATABASE_URL` set
- [ ] **Redis**: Provisioned (Upstash or Railway Redis) and `REDIS_URL` or `UPSTASH_REDIS_URL` set
- [ ] **Procfile processes configured**:
  - [ ] `web` process running (1+ instances)
  - [ ] `worker` process running (1+ instances)
  - [ ] `beat` process running (1 instance only)

### Environment Variables

**Core** (from `ENV_VARS_REFERENCE.md`):
- [ ] `DATABASE_URL` - PostgreSQL connection string
- [ ] `REDIS_URL` or `UPSTASH_REDIS_URL` - Redis connection
- [ ] `CLERK_SECRET_KEY` - Clerk authentication
- [ ] `ALLOWED_ORIGINS` - CORS origins (include staging frontend URL)
- [ ] `ENVIRONMENT=staging`

**Feature Flags**:
- [ ] `ENABLE_CELERY=true`
- [ ] `ENABLE_CELERY_BEAT=true`
- [ ] `ENABLE_RATE_LIMITING=true` (default)

**External Services** (use staging/test keys):
- [ ] `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`
- [ ] `CALLRAIL_API_KEY`, `CALLRAIL_ACCOUNT_ID`
- [ ] `DEEPGRAM_API_KEY`
- [ ] `OPENAI_API_KEY`
- [ ] `BLAND_API_KEY`

**Shunya/UWC** (if enabled):
- [ ] `UWC_API_KEY`
- [ ] `UWC_HMAC_SECRET` (if receiving webhooks)
- [ ] `USE_UWC_STAGING=true` (recommended for staging)

**S3** (if using):
- [ ] `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- [ ] `S3_BUCKET=otto-documents-staging` (or staging bucket name)

### Database

- [ ] **Migrations applied**: `alembic upgrade head`
- [ ] **Indexes created**: Verify indexes from `DB_INDEXES.md` exist
  ```sql
  SELECT indexname FROM pg_indexes WHERE tablename IN ('calls', 'appointments', 'message_threads', 'call_analysis');
  ```

### Celery & Background Tasks

- [ ] **Worker process running**: Check logs for "celery@hostname ready"
- [ ] **Beat process running**: Check logs for "beat: Starting..."
- [ ] **Redis connection**: Worker and beat can connect to Redis
- [ ] **Task queues**: All queues configured (`default`, `asr`, `analysis`, `followups`, `indexing`, `uwc`, `shunya`)

### Webhooks

- [ ] **Shunya webhook HMAC secret**: `UWC_HMAC_SECRET` matches Shunya's configured secret
- [ ] **CallRail webhooks**: Point to `https://your-staging-domain.com/callrail/call.completed`
- [ ] **Twilio webhooks**: Point to `https://your-staging-domain.com/sms/twilio-webhook`
- [ ] **Clerk webhooks** (if used): Point to `https://your-staging-domain.com/webhooks/clerk`

### Verification

- [ ] Health check: `curl https://your-staging-domain.com/health`
- [ ] API endpoints respond (test with auth token)
- [ ] Celery tasks process successfully (check worker logs)
- [ ] Scheduled tasks run (check beat logs)
- [ ] Webhooks receive and process correctly (test with sample payloads)

### Performance

- [ ] **Resource allocation**:
  - Web: 512MB-1GB RAM, 1 vCPU
  - Worker: 512MB-1GB RAM, 1 vCPU
  - Beat: 256MB RAM, 0.5 vCPU
- [ ] **Scaling**: Start with 1 instance each, scale based on load

---

## Production

### Infrastructure

- [ ] **PostgreSQL**: Provisioned (Railway-managed or external), `DATABASE_URL` set
- [ ] **Redis**: Provisioned (Upstash recommended for Railway), `REDIS_URL` or `UPSTASH_REDIS_URL` set
- [ ] **Procfile processes configured**:
  - [ ] `web` process running (2+ instances for HA)
  - [ ] `worker` process running (2+ instances for HA)
  - [ ] `beat` process running (1 instance only - critical!)

### Environment Variables

**Core** (all required in production):
- [ ] `DATABASE_URL` - Production PostgreSQL
- [ ] `REDIS_URL` or `UPSTASH_REDIS_URL` - Production Redis
- [ ] `CLERK_SECRET_KEY` - Production Clerk key
- [ ] `CLERK_ISSUER` - Production Clerk issuer URL
- [ ] `CLERK_FRONTEND_ORIGIN` - Production Clerk frontend origin
- [ ] `ALLOWED_ORIGINS` - Production frontend URLs only
- [ ] `ENVIRONMENT=production`

**Feature Flags**:
- [ ] `ENABLE_CELERY=true`
- [ ] `ENABLE_CELERY_BEAT=true`
- [ ] `ENABLE_RATE_LIMITING=true`

**External Services** (production keys):
- [ ] `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`
- [ ] `CALLRAIL_API_KEY`, `CALLRAIL_ACCOUNT_ID`
- [ ] `DEEPGRAM_API_KEY`
- [ ] `OPENAI_API_KEY` (or `OPENAI_API_KEYS` for rotation)
- [ ] `BLAND_API_KEY`
- [ ] `GOOGLE_MAPS_API_KEY` (if using geocoding)

**Shunya/UWC** (if enabled):
- [ ] `UWC_API_KEY` - Production key
- [ ] `UWC_HMAC_SECRET` - **CRITICAL** - Must match Shunya's production secret
- [ ] `UWC_BASE_URL` - Production Shunya URL
- [ ] `USE_UWC_STAGING=false`

**S3** (if using):
- [ ] `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` - Production IAM credentials
- [ ] `AWS_REGION` - S3 bucket region
- [ ] `S3_BUCKET=otto-documents-prod` (or production bucket name)

**Observability** (recommended):
- [ ] `SENTRY_DSN` - Production Sentry project
- [ ] `LOG_LEVEL=INFO` (or `WARNING` for less verbose)
- [ ] `OTEL_EXPORTER_OTLP_ENDPOINT` (if using OpenTelemetry)

### Database

- [ ] **Migrations applied**: `alembic upgrade head` (run during maintenance window)
- [ ] **Indexes created**: All indexes from `DB_INDEXES.md` exist
  ```sql
  -- Verify critical indexes
  SELECT indexname FROM pg_indexes 
  WHERE tablename IN ('calls', 'appointments', 'message_threads', 'call_analysis')
  AND indexname LIKE 'ix_%';
  ```
- [ ] **Backup configured**: Automated backups enabled
- [ ] **Connection pooling**: Verify SQLAlchemy pool settings are appropriate

### Celery & Background Tasks

- [ ] **Worker process running**: Multiple instances for HA (2+)
- [ ] **Beat process running**: **Exactly 1 instance** (prevent duplicate scheduled tasks)
- [ ] **Redis connection**: All workers and beat can connect
- [ ] **Task queues**: All queues configured and workers listening
- [ ] **Task monitoring**: Set up monitoring/alerts for failed tasks

### Webhooks

- [ ] **Shunya webhook HMAC secret**: `UWC_HMAC_SECRET` matches Shunya's production secret
- [ ] **CallRail webhooks**: Point to `https://your-production-domain.com/callrail/call.completed`
- [ ] **Twilio webhooks**: Point to `https://your-production-domain.com/sms/twilio-webhook`
- [ ] **Clerk webhooks** (if used): Point to `https://your-production-domain.com/webhooks/clerk`
- [ ] **Webhook security**: All webhook endpoints verify signatures

### Security

- [ ] **Secrets management**: All secrets stored securely (Railway variables, not in code)
- [ ] **HTTPS**: All endpoints served over HTTPS
- [ ] **CORS**: `ALLOWED_ORIGINS` includes only production frontend URLs
- [ ] **Rate limiting**: Enabled and configured appropriately
- [ ] **JWT validation**: Clerk JWT validation working correctly

### Performance & Scaling

- [ ] **Resource allocation**:
  - Web: 1GB RAM, 1 vCPU per instance (start with 2 instances)
  - Worker: 1GB RAM, 1 vCPU per instance (start with 2 instances)
  - Beat: 256MB RAM, 0.5 vCPU (1 instance only)
- [ ] **Scaling strategy**:
  - Web: Scale based on request latency/throughput (target: <200ms p95)
  - Worker: Scale based on queue depth (target: <100 tasks queued)
  - Beat: Always 1 instance
- [ ] **Database indexes**: All indexes from `DB_INDEXES.md` created and monitored
- [ ] **Query performance**: Monitor slow queries (target: <500ms for dashboard queries)

### Monitoring & Alerts

- [ ] **Health checks**: Set up monitoring for `/health` endpoint
- [ ] **Error tracking**: Sentry configured and alerts set up
- [ ] **Log aggregation**: Logs accessible and searchable
- [ ] **Metrics**: Key metrics monitored (request rate, error rate, task queue depth)
- [ ] **Alerts configured**:
  - High error rate (>1% of requests)
  - Worker queue depth >1000
  - Database connection pool exhaustion
  - Redis connection failures

### Verification

- [ ] **Health check**: `curl https://your-production-domain.com/health`
- [ ] **API endpoints**: Test key endpoints with production auth tokens
- [ ] **Background tasks**: Verify tasks process successfully
- [ ] **Scheduled tasks**: Verify beat runs scheduled tasks
- [ ] **Webhooks**: Test webhook endpoints with sample payloads
- [ ] **Database queries**: Verify dashboard queries use indexes (check query plans)
- [ ] **Load testing**: Run basic load test to verify scaling

### Post-Deployment

- [ ] **Smoke tests**: Run critical user flows
- [ ] **Monitor logs**: Watch for errors in first hour
- [ ] **Verify metrics**: Check that metrics are being collected
- [ ] **Documentation**: Update any deployment-specific notes

---

## Quick Reference: Procfile Processes

```procfile
web: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
worker: celery -A app.celery_app worker --loglevel=info --queues=default,asr,analysis,followups,indexing,uwc,shunya
beat: celery -A app.celery_app beat --loglevel=info
```

**Process Requirements**:
- **web**: Handles HTTP requests, webhooks, API endpoints
- **worker**: Processes background tasks (ASR, analysis, follow-ups, etc.)
- **beat**: Schedules periodic tasks (reports, cleanup, etc.)

**Scaling**:
- Web: 2+ instances for HA
- Worker: 2+ instances for HA (scale based on queue depth)
- Beat: **Always 1 instance** (prevents duplicate scheduled tasks)

---

## Quick Reference: Required Env Vars (Production)

**Minimum for production**:
```
DATABASE_URL=postgresql://...
REDIS_URL=redis://... (or UPSTASH_REDIS_URL)
CLERK_SECRET_KEY=sk_live_...
ALLOWED_ORIGINS=https://app.otto.ai
ENVIRONMENT=production
ENABLE_CELERY=true
ENABLE_CELERY_BEAT=true
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=+1...
CALLRAIL_API_KEY=...
CALLRAIL_ACCOUNT_ID=...
DEEPGRAM_API_KEY=...
OPENAI_API_KEY=sk-...
BLAND_API_KEY=...
UWC_API_KEY=... (if UWC enabled)
UWC_HMAC_SECRET=... (if receiving webhooks)
AWS_ACCESS_KEY_ID=... (if using S3)
AWS_SECRET_ACCESS_KEY=... (if using S3)
S3_BUCKET=otto-documents-prod (if using S3)
```

See `ENV_VARS_REFERENCE.md` for complete list with descriptions.

---

## Troubleshooting

### Common Issues

**Celery workers not starting**:
- Check `ENABLE_CELERY=true`
- Verify `REDIS_URL` is set and accessible
- Check worker logs for connection errors

**Beat process not running scheduled tasks**:
- Check `ENABLE_CELERY_BEAT=true`
- Verify only 1 beat instance is running
- Check beat logs for scheduling errors

**Webhooks failing**:
- Verify webhook URLs are correct in external service dashboards
- Check `UWC_HMAC_SECRET` matches Shunya's configured secret
- Verify webhook endpoints are accessible (not blocked by firewall)

**Database queries slow**:
- Verify indexes from `DB_INDEXES.md` are created
- Check query plans with `EXPLAIN ANALYZE`
- Monitor database connection pool usage

**High memory usage**:
- Check for memory leaks in long-running processes
- Verify pagination is used for large result sets
- Monitor worker task memory usage

---

## See Also

- **`RAILWAY_SETUP.md`** - Detailed Railway deployment guide
- **`ENV_VARS_REFERENCE.md`** - Complete environment variable reference
- **`DB_INDEXES.md`** - Database index documentation
- **`ASYNC_HOTSPOTS_FIXES.md`** - Performance optimizations applied
- **`HOTSPOT_FIX_PLAN.md`** - Query optimization details
- **`../INFRASTRUCTURE_AUDIT.md`** - Infrastructure audit and requirements

