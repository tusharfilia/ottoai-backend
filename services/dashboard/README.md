# OttoAI Backend API

FastAPI backend for the OttoAI platform (formerly TrueView).

## Environment Setup

### Required Environment Variables

Copy `.env.example` to `.env` and fill in your actual values:

```bash
cp .env.example .env
```

**Required variables:**
- `DATABASE_URL` - PostgreSQL connection string
- `CLERK_SECRET_KEY` - Clerk authentication secret key
- `CLERK_PUBLISHABLE_KEY` - Clerk publishable key
- `TWILIO_ACCOUNT_SID` - Twilio account SID
- `TWILIO_AUTH_TOKEN` - Twilio auth token
- `TWILIO_FROM_NUMBER` - Twilio phone number
- `CALLRAIL_API_KEY` - CallRail API key
- `CALLRAIL_ACCOUNT_ID` - CallRail account ID
- `DEEPGRAM_API_KEY` - Deepgram API key
- `OPENAI_API_KEY` - OpenAI API key
- `BLAND_API_KEY` - Bland AI API key
- `ALLOWED_ORIGINS` - Comma-separated list of allowed CORS origins
- `REDIS_URL` - Redis connection URL for rate limiting
- `RATE_LIMIT_USER` - Per-user rate limit (default: 60/minute)
- `RATE_LIMIT_TENANT` - Per-tenant rate limit (default: 600/minute)
- `LOG_LEVEL` - Logging level (default: INFO)
- `OBS_REDACT_PII` - Enable PII redaction in logs (default: true)
- `OTEL_EXPORTER_OTLP_ENDPOINT` - OpenTelemetry OTLP endpoint (optional)
- `OTEL_SERVICE_NAME_API` - OpenTelemetry service name for API (default: otto-api)
- `OTEL_SERVICE_NAME_WORKER` - OpenTelemetry service name for workers (default: otto-worker)

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

3. **Run the application:**
   ```bash
   uvicorn app.main:app --reload
   ```

4. **Run tests:**
   ```bash
   # Set test environment variables
   export CALLRAIL_API_KEY_TEST=your_test_key
   export CALLRAIL_ACCOUNT_ID_TEST=your_test_account_id
   
   python test_callrail_endpoints.py
   ```

### Configuration

All configuration is centralized in `app/config.py`. The application will:
- Load environment variables from `.env` file
- Validate required variables on startup
- Raise clear errors if placeholder values are detected in production

## Deployment

### Test Environment
```bash
flyctl deploy --config fly.test.toml --dockerfile Dockerfile.test -a tv-mvp-test
```

### Production
```bash
flyctl deploy
```

### Setting Secrets
```bash
# Test environment
flyctl secrets set <SECRET_NAME>=<VALUE> -a tv-mvp-test

# Production
flyctl secrets set <SECRET_NAME>=<VALUE>
```

## Security

- All secrets are loaded from environment variables
- No hardcoded secrets in code
- Secret scanning CI prevents accidental secret commits
- Centralized configuration with validation

## CORS Configuration

The API uses environment-driven CORS configuration for security:

```bash
# Example .env configuration
ALLOWED_ORIGINS=https://ottoai-frontend.vercel.app,http://localhost:3000,exp://*
```

**Important:**
- Requests from non-allowed origins will be rejected with 403
- Local development origins must be explicitly allowed
- Production deployments should only allow specific frontend domains

## Webhook Idempotency

The API implements comprehensive webhook idempotency to prevent duplicate processing from provider retries. All webhook handlers are protected against duplicate deliveries while ensuring first-time deliveries process exactly once.

### What is Webhook Idempotency?

Webhook providers (CallRail, Twilio, Clerk, Bland AI) may retry failed webhook deliveries. Without idempotency protection, this can cause:
- Duplicate data processing
- Inconsistent application state
- Unintended side effects (e.g., sending duplicate emails)

### Key Derivation by Provider

Each provider uses a stable external identifier for idempotency:

**CallRail:**
- `external_id = payload["call"]["id"]` (UUID from CallRail)
- Used for: pre-call, call-complete, call-modified webhooks

**Twilio:**
- Calls: `external_id = form["CallSid"]`
- SMS: `external_id = form["MessageSid"]`
- Recording: `external_id = form["RecordingSid"]`

**Clerk:**
- `external_id = payload["event_id"]` (preferred) or `payload["data"]["id"]`
- Used for: user/organization events

**Bland AI:**
- `external_id = payload["call_id"]` or `payload["session_id"]`
- Used for: callback webhooks

### Idempotency Behavior

**First-time Delivery:**
- Returns: `200 OK` with `{"status": "processed", "provider": "..."}`
- Side effects: Execute exactly once
- Database: Record idempotency key with `first_processed_at`

**Duplicate Delivery:**
- Returns: `200 OK` with `{"status": "duplicate_ignored", "provider": "..."}`
- Side effects: None (no-op)
- Database: Update `last_seen_at` and increment `attempts`

**Processing Failure:**
- Returns: Error status code
- Database: Remove idempotency key (allows retry to succeed)
- Side effects: Rolled back

### Configuration

```bash
# Idempotency key TTL (days)
IDEMPOTENCY_TTL_DAYS=90
```

### Cleanup Schedule

Old idempotency keys are automatically purged:
- **Schedule**: Daily at 02:00 UTC
- **Retention**: 90 days (configurable via `IDEMPOTENCY_TTL_DAYS`)
- **Task**: Celery Beat scheduled task
- **Logging**: Structured logs with purge counts

### Metrics & Monitoring

Prometheus counters track idempotency events:
- `webhook_processed_total{provider,tenant_id}`
- `webhook_duplicates_total{provider,tenant_id}`
- `webhook_failures_total{provider,tenant_id}`
- `webhook_idempotency_purged_total`

### Testing Idempotency

```bash
# Run idempotency tests
make verify:idempotency

# Manual test (same payload twice)
curl -X POST /webhook/callrail/pre-call -d '{"call_id": "test-123"}'
# Returns: {"status": "processed"}

curl -X POST /webhook/callrail/pre-call -d '{"call_id": "test-123"}'
# Returns: {"status": "duplicate_ignored"}
```

## Tenant Context & Multi-Tenancy

The API enforces tenant isolation for data security:

### How it works:
1. **JWT Validation**: All authenticated requests must include a valid Clerk JWT token
2. **Tenant Extraction**: The middleware extracts `tenant_id` (organization ID) from JWT claims
3. **Database Scoping**: All database queries are automatically scoped to the user's organization
4. **Access Control**: Cross-tenant data access is blocked at the database level

### Why tenant_id is required:
- **Data Isolation**: Ensures users can only access data from their organization
- **Security**: Prevents accidental or malicious cross-tenant data access
- **Compliance**: Required for multi-tenant SaaS applications
- **Scalability**: Enables proper data partitioning and performance optimization

### For developers:
- All route handlers can access `request.state.tenant_id`
- Database sessions automatically filter by tenant
- Health checks and public endpoints bypass tenant validation
- Invalid or missing tenant context returns 403 Forbidden

### Testing:
```bash
# Run CORS and tenant validation tests
python -m pytest tests/test_cors_tenant.py -v

# Run rate limiting tests
python -m pytest tests/test_rate_limiting.py -v
```

## Rate Limiting

The API implements comprehensive rate limiting with per-user and per-tenant buckets:

### Configuration:
```bash
# Redis connection for distributed rate limiting
REDIS_URL=redis://localhost:6379/0

# Default rate limits
RATE_LIMIT_USER=60/minute
RATE_LIMIT_TENANT=600/minute
```

### How it works:
1. **Per-User Limits**: Each user has individual rate limits within their organization
2. **Per-Tenant Limits**: Organizations have shared rate limits across all users
3. **Redis Backend**: Distributed rate limiting using Redis for scalability
4. **Automatic Enforcement**: Global middleware applies default limits to all routes
5. **Route Overrides**: Specific routes can have custom limits using `@limits()` decorator

### Rate Limit Keys:
- **Per-user**: `tenant:{tenant_id}:user:{user_id}`
- **Per-tenant**: `tenant:{tenant_id}`

### Custom Route Limits:
```python
from app.middleware.rate_limiter import limits

@router.post("/api/expensive-operation")
@limits(user="20/minute", tenant="100/minute")
async def expensive_operation():
    # Custom rate limits for this route
    pass
```

### Rate Limit Response:
When rate limits are exceeded, the API returns:
- **Status Code**: 429 Too Many Requests
- **Headers**: `Retry-After` (seconds), `X-Trace-Id`
- **Body**: JSON Problem Details format
```json
{
  "type": "https://tools.ietf.org/html/rfc6585#section-4",
  "title": "Too Many Requests",
  "detail": "Rate limit exceeded. Please try again later.",
  "retry_after": 60,
  "trace_id": "uuid-here"
}
```

### Exempt Routes:
The following routes bypass rate limiting:
- `/health`, `/ready`, `/metrics`
- `/docs`, `/redoc`, `/openapi.json`
- WebSocket upgrade requests

### Telemetry:
- Rate limit hits are logged with structured data
- Metrics include route, tenant_id, user_id, and limit type
- Prometheus metrics: `rate_limit_hits_total`

### Environment Adjustments:
Rate limits can be adjusted via environment variables without code changes:
```bash
# Stricter limits for production
RATE_LIMIT_USER=30/minute
RATE_LIMIT_TENANT=300/minute

# More lenient for development
RATE_LIMIT_USER=120/minute
RATE_LIMIT_TENANT=1200/minute
```

## Foundations Verification

The OttoAI backend implements three core security foundations that are automatically verified:

### 1. Secrets & Environment Hygiene
- **No hardcoded secrets** in codebase
- **Centralized configuration** via environment variables
- **Automatic secret scanning** in CI/CD

### 2. CORS Lockdown + Tenant Middleware
- **Environment-driven CORS** allowlist
- **JWT-based tenant validation** for all protected routes
- **Automatic database scoping** by tenant

### 3. API Rate Limiting
- **Per-user rate limiting** (default: 60/minute)
- **Per-tenant rate limiting** (default: 600/minute)
- **Redis-backed** with graceful degradation
- **Exempt routes** for health checks and documentation

### Verification Commands

**Run all foundation verifications:**
```bash
make verify
```

**Run individual verification checks:**
```bash
make verify:secrets    # Scan for hardcoded secrets
make verify:tests      # Run CORS and rate limiting tests
make verify:idempotency # Run webhook idempotency tests
make verify:obs        # Run observability tests
```

**Run human-friendly smoke test:**
```bash
make smoke            # Run foundations smoke test
make smoke:obs        # Run observability smoke test
```

### Smoke Test Configuration

The smoke test requires environment variables for full validation:

```bash
export BASE="http://localhost:8000"
export ORIGIN_OK="http://localhost:3000"
export ORIGIN_BAD="https://malicious-site.com"
export TOKEN_A="your_jwt_token_for_user_a"
export TOKEN_B="your_jwt_token_for_user_b"
make smoke
```

**Smoke test validates:**
- ✅ CORS allowed vs disallowed origins
- ✅ Tenant enforcement (no token, bad token, good token)
- ✅ Rate limit per-user (5 requests pass, 6th 429)
- ✅ Rate limit per-tenant (A:6 + B:6 → some 429s after total >10)
- ✅ Exempt routes never 429

### CI/CD Integration

The foundations are automatically verified in CI/CD:
- **Secret scanning** on every PR
- **Comprehensive test suite** for all security features
- **Rate limiting validation** with Redis service
- **CORS and tenant middleware** verification

### Security Status

- ✅ **Secrets**: No hardcoded secrets, environment-driven configuration
- ✅ **CORS**: Environment-driven allowlist, malicious origins blocked
- ✅ **Tenant**: JWT validation, database scoping, cross-tenant isolation
- ✅ **Rate Limiting**: Per-user/tenant limits, Redis backend, exempt routes
- ✅ **CI/CD**: Automated verification, secret scanning, comprehensive tests

## Observability Core

The OttoAI backend implements comprehensive observability with structured logging, distributed tracing, and metrics collection.

### 1. Structured Logging
- **JSON-formatted logs** with consistent fields
- **Trace ID correlation** across requests and tasks
- **PII redaction** for sensitive data (phones, emails)
- **Service identification** (api/worker) in all logs

**Log Fields:**
- `ts` - ISO timestamp
- `level` - Log level (INFO, WARN, ERROR)
- `service` - Service type (api/worker)
- `message` - Log message
- `trace_id` - Request correlation ID
- `route`, `method`, `status` - HTTP request details
- `latency_ms` - Request duration
- `tenant_id`, `user_id` - Context information
- `provider`, `external_id` - Webhook details

### 2. Distributed Tracing
- **OpenTelemetry integration** for FastAPI and Celery
- **Trace propagation** across API requests and background tasks
- **Span correlation** with parent-child relationships
- **Console exporter** for development, OTLP for production

**Trace Context:**
- Automatic trace ID generation or propagation from headers
- `X-Request-Id` header in all responses
- Celery task spans linked to originating API requests
- Error correlation with stack traces

### 3. Prometheus Metrics
- **HTTP request metrics** (count, duration, status)
- **Celery task metrics** (count, duration, status)
- **Webhook processing metrics** (processed, duplicates, failures)
- **Business metrics** (ASR minutes, LLM tokens, SMS sent)
- **System metrics** (cache hits/misses, active connections)

**Available Metrics:**
- `http_requests_total{route,method,status}`
- `http_request_duration_ms_bucket{route,method}`
- `worker_task_total{name,status}`
- `worker_task_duration_ms_bucket{name}`
- `webhook_processed_total{provider,status}`
- `asr_minutes_total{tenant_id}`
- `llm_tokens_total{tenant_id,model}`
- `sms_sent_total{tenant_id}`

### 4. Error Handling
- **RFC-7807 Problem Details** for all errors
- **Structured error logging** with stack traces
- **Trace ID correlation** in error responses
- **Consistent error format** across all endpoints

**Error Response Format:**
```json
{
  "type": "https://tools.ietf.org/html/rfc7231#section-6.5.1",
  "title": "HTTP Error",
  "detail": "Error description",
  "status": 400,
  "instance": "/api/endpoint",
  "trace_id": "uuid-trace-id"
}
```

### Observability Configuration

**Environment Variables:**
```bash
# Logging
LOG_LEVEL=INFO                    # Log level (DEBUG, INFO, WARN, ERROR)
OBS_REDACT_PII=true              # Enable PII redaction

# Tracing
OTEL_EXPORTER_OTLP_ENDPOINT=     # OTLP endpoint (blank = console)
OTEL_SERVICE_NAME_API=otto-api   # API service name
OTEL_SERVICE_NAME_WORKER=otto-worker  # Worker service name
```

**Endpoints:**
- `GET /health` - Health check with trace ID
- `GET /metrics` - Prometheus metrics endpoint

### Verification Commands

**Run observability tests:**
```bash
make verify:obs
```

**Run observability smoke test:**
```bash
make smoke:obs
```

**Manual verification:**
```bash
# Check structured logging
curl -H "X-Request-Id: test-123" http://localhost:8000/health

# Check metrics
curl http://localhost:8000/metrics

# Check error format
curl http://localhost:8000/non-existent-route
```

### Observability Status

- ✅ **Structured Logging**: JSON format, trace correlation, PII redaction
- ✅ **Distributed Tracing**: OpenTelemetry, span correlation, error tracking
- ✅ **Metrics Collection**: Prometheus format, HTTP/task/business metrics
- ✅ **Error Handling**: RFC-7807 format, trace correlation, structured logging
- ✅ **Testing**: Comprehensive test suite, smoke tests, CI integration