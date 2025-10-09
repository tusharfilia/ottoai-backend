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

## Production Deployment

### Prerequisites

1. **Fly.io Account**: Set up account and install flyctl
2. **Redis Instance**: Provision Redis for rate limiting and Celery
3. **Environment Secrets**: Configure all required environment variables

### Step 1: Provision Redis

Choose one of these Redis options:

#### Option A: Fly.io Redis (Recommended)
```bash
# Create Redis instance
fly redis create
# Name: ottoai-redis
# Region: phx (same as your app)

# Get connection details
fly redis status ottoai-redis
```

#### Option B: Upstash Redis
1. Go to [Upstash Console](https://console.upstash.com/)
2. Create new Redis database
3. Copy the connection URL

### Step 2: Configure Secrets

Set all required secrets in Fly.io:

```bash
# Database and Redis
fly secrets set DATABASE_URL="postgresql://..."
fly secrets set REDIS_URL="redis://..."  # or UPSTASH_REDIS_URL

# Authentication
fly secrets set CLERK_SECRET_KEY="sk_..."
fly secrets set CLERK_PUBLISHABLE_KEY="pk_..."
fly secrets set CLERK_WEBHOOK_SECRET="whsec_..."

# External Services
fly secrets set TWILIO_ACCOUNT_SID="AC..."
fly secrets set TWILIO_AUTH_TOKEN="..."
fly secrets set CALLRAIL_API_KEY="..."
fly secrets set CALLRAIL_ACCOUNT_ID="..."
fly secrets set DEEPGRAM_API_KEY="sk-..."
fly secrets set OPENAI_API_KEY="sk-..."
fly secrets set BLAND_API_KEY="..."

# Configuration
fly secrets set ALLOWED_ORIGINS="https://your-frontend.vercel.app,https://your-domain.com"
fly secrets set ENABLE_CELERY="true"
fly secrets set ENABLE_CELERY_BEAT="true"
fly secrets set LOG_LEVEL="INFO"
fly secrets set OBS_REDACT_PII="true"
```

### Step 3: Deploy Application

Deploy with process groups (API + Worker + Beat):

```bash
# Deploy all processes
fly deploy

# Check deployment status
fly status

# View logs for different processes
fly logs -a tv-mvp           # API logs
fly logs -a tv-mvp --process worker  # Worker logs
fly logs -a tv-mvp --process beat    # Beat logs
```

### Step 4: Verify Deployment

#### Health Checks
```bash
# Basic health
curl https://tv-mvp-test.fly.dev/health

# Comprehensive readiness
curl https://tv-mvp-test.fly.dev/ready

# Expected readiness response:
{
  "ready": true,
  "components": {
    "database": true,
    "redis": true,
    "celery_workers": true
  },
  "timestamp": 1234567890,
  "duration_ms": 123.45,
  "service": "otto-api"
}
```

#### Run Verification Pack
```bash
# Run all verification tests
make verify:all

# Run observability smoke test
BASE=https://tv-mvp-test.fly.dev make smoke:obs

# Run infrastructure validation
python scripts/quick_validation.py https://tv-mvp-test.fly.dev
```

### Step 5: Monitor Deployment

#### Process Status
```bash
# Check all processes are running
fly status

# Scale processes if needed
fly scale count api=2 worker=1 beat=1
```

#### Application Logs
```bash
# Follow all logs
fly logs --follow

# Process-specific logs
fly logs --process api --follow
fly logs --process worker --follow
fly logs --process beat --follow
```

#### Metrics and Monitoring
```bash
# Check Prometheus metrics
curl https://tv-mvp-test.fly.dev/metrics

# Monitor Redis connectivity
curl https://tv-mvp-test.fly.dev/ready | jq '.components.redis'

# Check Celery workers
curl https://tv-mvp-test.fly.dev/internal/worker/heartbeat
```

### Troubleshooting

#### Common Issues

1. **Redis Connection Failed**
   ```bash
   # Check Redis URL format
   fly secrets list | grep REDIS
   
   # Test Redis connectivity
   redis-cli -u $REDIS_URL ping
   ```

2. **Celery Workers Not Starting**
   ```bash
   # Check worker logs
   fly logs --process worker
   
   # Verify Redis connectivity from worker
   fly ssh console --process worker
   # Inside container: redis-cli -u $REDIS_URL ping
   ```

3. **Database Migration Issues**
   ```bash
   # Run migrations manually
   fly ssh console --process api
   # Inside container: alembic upgrade head
   ```

4. **Process Not Starting**
   ```bash
   # Check process configuration
   cat fly.toml
   
   # Restart specific process
   fly restart --process api
   ```

#### Performance Issues

1. **High Memory Usage**
   ```bash
   # Check memory usage
   fly status
   
   # Scale up if needed
   fly scale memory 2gb
   ```

2. **Slow Response Times**
   ```bash
   # Check metrics
   curl https://tv-mvp-test.fly.dev/metrics | grep http_request_duration
   
   # Scale horizontally
   fly scale count api=2
   ```

### Rollback Procedure

If deployment fails:

```bash
# List recent releases
fly releases

# Rollback to previous version
fly releases rollback <version>

# Or deploy previous Docker image
fly deploy --image registry.fly.io/tv-mvp:<previous-tag>
```

### Automated Deployment

Use GitHub Actions for automated deployment:

```bash
# Trigger staging deployment
gh workflow run deploy-staging.yml

# Check deployment status
gh run list --workflow=deploy-staging.yml
```

### Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `CLERK_SECRET_KEY` | Yes | Clerk authentication secret |
| `ENABLE_CELERY` | No | Enable Celery workers (default: false) |
| `ENABLE_CELERY_BEAT` | No | Enable Celery beat scheduler (default: false) |
| `LOG_LEVEL` | No | Logging level (default: INFO) |
| `OBS_REDACT_PII` | No | Enable PII redaction (default: true) |

For complete list, see `.env.example` file.

## Real-Time Transport

The OttoAI backend provides real-time communication via authenticated WebSockets with Redis pub/sub for event distribution.

### WebSocket Connection

**Endpoint**: `/ws`
**Authentication**: Clerk JWT token in Authorization header
**Protocol**: WebSocket with JSON message format

#### Connection Example
```javascript
const ws = new WebSocket('wss://api.ottoai.com/ws', {
  headers: {
    'Authorization': `Bearer ${clerkToken}`
  }
});

ws.onopen = () => {
  console.log('Connected to OttoAI real-time');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  handleRealtimeEvent(message);
};
```

### Channel Subscription

After connection, clients can subscribe to channels:

```javascript
// Subscribe to tenant events
ws.send(JSON.stringify({
  type: 'subscribe',
  channel: 'tenant:your-tenant-id:events'
}));

// Subscribe to user tasks
ws.send(JSON.stringify({
  type: 'subscribe', 
  channel: 'user:your-user-id:tasks'
}));

// Subscribe to lead timeline
ws.send(JSON.stringify({
  type: 'subscribe',
  channel: 'lead:lead-id:timeline'
}));
```

### Message Envelope Format

All events follow a standardized format:

```json
{
  "version": "1",
  "event": "telephony.call.received",
  "ts": "2025-09-20T10:30:00.000Z",
  "severity": "info",
  "trace_id": "uuid-trace-id",
  "tenant_id": "tenant-123",
  "user_id": "user-456",
  "lead_id": "lead-789", 
  "data": {
    "call_id": "call-123",
    "phone_number": "+1234567890",
    "answered": true
  }
}
```

### Available Events

#### Telephony Events
- `telephony.call.received` - Incoming call detected
- `telephony.call.completed` - Call analysis complete
- `telephony.sms.received` - SMS received from customer
- `telephony.sms.sent` - SMS sent to customer
- `telephony.call.status` - Call status update

#### System Events
- `system.webhook.processed` - Webhook processing complete
- `system.buffer_dropped` - Message queue overflow
- `worker.task.finished` - Background task complete
- `worker.task.failed` - Background task failed

#### User Events
- `identity.user.created` - New user added
- `identity.user.updated` - User information updated
- `task.updated` - Task assigned or updated
- `appointment.assigned` - Appointment assigned to rep

#### Analytics Events
- `analytics.daily_recap.ready` - Daily analytics available

### Channel Security

**Access Control**:
- Users can only subscribe to their own tenant's events
- Users can only subscribe to their own user tasks
- Lead channels are validated against tenant ownership
- No wildcard subscriptions allowed

**Channel Formats**:
- `tenant:{tenant_id}:events` - Organization-wide events
- `user:{user_id}:tasks` - User-specific tasks and notifications
- `lead:{lead_id}:timeline` - Lead-specific updates

### Heartbeat & Connection Management

**Heartbeat**: Server sends ping every 20 seconds, client must respond with pong
**Timeout**: Connections closed after 40 seconds without pong response
**Reconnection**: Clients should implement automatic reconnection with exponential backoff

### Rate Limiting

**Control Messages**: 10 subscribe/unsubscribe operations per minute per connection
**Connection Limits**: Monitored but not hard-limited per tenant
**Abuse Protection**: Automatic disconnection for protocol violations

### Performance

**Message Size**: 32KB limit per message
**Large Payloads**: Automatically converted to pointer messages with resource IDs
**Latency**: <1 second end-to-end event delivery
**Throughput**: Designed for thousands of concurrent connections

### Development & Testing

**Test Event Emission** (development only):
```bash
curl "http://localhost:8000/ws/test-emit?event=test.event&tenant_id=tenant-123"
```

**Verification Commands**:
```bash
# Run WebSocket tests
make verify:realtime

# Run real-time smoke test
BASE=https://your-app.fly.dev TOKEN=your-jwt make smoke:realtime
```

**Event Catalog**: See `docs/events/catalog.md` for complete event documentation

### Real-Time Transport Status

- ✅ **WebSocket Endpoint**: Authenticated `/ws` with Clerk JWT validation
- ✅ **Redis Pub/Sub**: Event bus with standardized message envelope
- ✅ **Channel Security**: Strict access control and validation
- ✅ **Event Emission**: Wired from webhooks and background tasks
- ✅ **Connection Management**: Heartbeat, cleanup, and monitoring
- ✅ **Rate Limiting**: Control message rate limiting and abuse protection
- ✅ **Testing**: Comprehensive test suite and smoke tests
- ✅ **Documentation**: Complete event catalog and client examples

## Foundations Verification

The OttoAI backend includes a comprehensive verification pack to ensure all foundational features are working correctly in any environment.

### Quick Verification

**Run all unit and integration tests:**
```bash
make verify:foundations
```

This single command runs comprehensive verification of:
- ✅ **Secrets hygiene** - No hardcoded secrets
- ✅ **CORS + tenant context** - Multi-tenant security
- ✅ **Rate limiting** - Per-user/tenant protection
- ✅ **Webhook idempotency** - Duplicate prevention
- ✅ **Observability** - Logging, tracing, metrics
- ✅ **Real-time transport** - WebSocket functionality
- ✅ **Production readiness** - Health checks and monitoring

### Staging/Production Smoke Tests

**Run end-to-end validation against deployed environment:**
```bash
# Basic smoke test
make smoke:foundations

# With full configuration
BASE=https://tv-mvp-test.fly.dev \
TENANT_ID=your-tenant-id \
TOKEN_A=your-jwt-token \
DEV_EMIT_KEY=your-dev-key \
make smoke:foundations
```

This validates:
- 🏥 **Infrastructure readiness** - DB + Redis connectivity
- 🔒 **Security** - CORS, rate limiting, authentication
- 📊 **Observability** - Metrics, logging, tracing
- ⚡ **Real-time** - WebSocket connectivity and event delivery
- 🔄 **Event emission** - End-to-end event flow
- 🏢 **Multi-tenant isolation** - Data segregation

### Metrics Monitoring

**Get current system health snapshot:**
```bash
# Local development
make metrics:snapshot

# Against specific environment
./scripts/metrics_snapshot.sh https://tv-mvp-test.fly.dev

# JSON format for automation
./scripts/metrics_snapshot.sh https://tv-mvp-test.fly.dev --format=json
```

**Metrics snapshot includes:**
- 🔗 **WebSocket connections** and message throughput
- 🌐 **HTTP request latency** and success rates
- ⚙️ **Worker task** performance and failure rates
- 🔄 **Webhook processing** metrics and idempotency stats
- 💾 **Cache performance** and hit rates

### Manual Testing & Debugging

#### **WebSocket Testing**
```bash
# Test WebSocket connectivity
BASE=https://your-app.fly.dev TOKEN=your-jwt make smoke:realtime

# Manual WebSocket connection (requires wscat)
wscat -c wss://your-app.fly.dev/ws -H "Authorization: Bearer your-jwt"

# Test event emission (dev/staging only)
curl -H "X-Dev-Key: your-key" \
  "https://your-app.fly.dev/ws/test-emit?event=test.manual&tenant_id=your-tenant"
```

#### **Health Check Testing**
```bash
# Basic health
curl https://your-app.fly.dev/health

# Comprehensive readiness
curl https://your-app.fly.dev/ready | jq '.'

# Worker heartbeat
curl https://your-app.fly.dev/internal/worker/heartbeat
```

#### **Security Testing**
```bash
# Test CORS
curl -H "Origin: https://malicious-site.com" https://your-app.fly.dev/health

# Test rate limiting
for i in {1..20}; do curl https://your-app.fly.dev/health & done; wait

# Test authentication
curl -H "Authorization: Bearer invalid-token" https://your-app.fly.dev/companies
```

### CI/CD Integration

**Automated verification in GitHub Actions:**

The `foundations-verify.yml` workflow runs:
1. **Unit tests** - All foundational feature tests
2. **Smoke tests** - End-to-end validation against staging
3. **Security scan** - Secret detection and validation
4. **Metrics snapshot** - Performance and health validation

**Trigger manually:**
```bash
gh workflow run foundations-verify.yml \
  --field target_environment=staging \
  --field run_smoke_tests=true
```

### Environment Configuration

**Required secrets for smoke tests:**
```bash
# GitHub Secrets (for CI/CD)
SMOKE_TEST_TENANT_ID=your-tenant-id
SMOKE_TEST_TOKEN_A=eyJ...
SMOKE_TEST_TOKEN_B=eyJ...
DEV_EMIT_KEY=your-development-key

# Fly.io Secrets (for production)
fly secrets set DEV_EMIT_KEY=your-development-key  # Optional, for testing
```

### Interpreting Results

#### **"Greenlight" Criteria**
✅ **All foundations verified** when:
- `make verify:foundations` passes with 100% success rate
- `make smoke:foundations` passes all smoke tests
- `/ready` endpoint returns `{"ready": true}` with all components healthy
- Metrics snapshot shows healthy values (latency <250ms, dropped=0)

#### **Warning Signs**
⚠️ **Monitor closely** when:
- P95 latency > 500ms
- WebSocket message drop rate > 1%
- Worker task failure rate > 5%
- Cache hit rate < 70%

#### **Critical Issues**
🚨 **Immediate action required** when:
- `/ready` returns 503 (infrastructure down)
- Cross-tenant access detected in logs
- P95 latency > 1000ms sustained
- WebSocket connections dropping to 0

### Troubleshooting

**Common issues and solutions:**

1. **Redis connectivity issues**
   ```bash
   # Check Redis URL
   fly secrets list | grep REDIS
   
   # Test Redis connection
   redis-cli -u $REDIS_URL ping
   ```

2. **WebSocket authentication failures**
   ```bash
   # Verify JWT token format
   echo $TOKEN | cut -d'.' -f2 | base64 -d | jq '.'
   
   # Check Clerk configuration
   fly secrets list | grep CLERK
   ```

3. **Event delivery failures**
   ```bash
   # Check Redis pub/sub
   redis-cli -u $REDIS_URL monitor
   
   # Check WebSocket hub logs
   fly logs | grep "WebSocket\|realtime\|event"
   ```

### Operations Dashboard

For detailed operational guidance, see `docs/ops/foundations-dashboard.md` which includes:
- 📊 Performance baselines and scaling guidelines
- 🔍 Log patterns and troubleshooting procedures  
- 🚨 Alert conditions and response procedures
- 📈 Daily/weekly operational checklists

### Foundations Verification Status

- ✅ **Comprehensive Test Suite**: Unit tests for all foundational features
- ✅ **End-to-End Smoke Tests**: Staging/production validation
- ✅ **Automated CI/CD**: GitHub Actions with complete verification
- ✅ **Metrics Monitoring**: Real-time health and performance tracking
- ✅ **Operations Documentation**: Complete troubleshooting and monitoring guides

---

## RBAC (Role-Based Access Control)

### Overview

Otto implements role-based access control with three roles:
- **leadership**: Business owners and sales managers (full management access, company-wide visibility)
- **csr**: Customer service representatives (call handling, booking, lead management)
- **rep**: Sales representatives (own appointments, follow-ups, learning via Feed)

**Note**: Leadership role combines owners and managers for simplicity. Can be split into separate `exec` and `manager` roles later if needed (see migration guide).

### Protecting Endpoints

Use the `@require_role()` decorator to enforce role-based permissions:

```python
from app.middleware.rbac import require_role, require_tenant_ownership, ROLE_LEADERSHIP, ROLE_CSR, ROLE_REP
from fastapi import Request

@router.get("/admin/settings")
@require_role("leadership")
async def admin_settings(request: Request):
    """Only leadership (owners/managers) can access."""
    # User context available in request.state
    user_role = request.state.user_role  # "leadership", "csr", or "rep"
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id
    ...

@router.put("/companies/{company_id}")
@require_role("leadership")
@require_tenant_ownership("company_id")
async def update_company(request: Request, company_id: str):
    """Only leadership of the company can update."""
    # Decorator validates company_id matches user's tenant_id
    ...

@router.post("/calls")
@require_role("leadership", "csr")
async def create_call(request: Request):
    """Leadership and CSRs can create calls."""
    # Reps cannot create calls directly
    ...
```

### Role Hierarchy

```
leadership (highest privileges)
  ├─ Business owners + Sales managers (merged)
  ├─ Can create/delete users and companies
  ├─ Can modify company settings (API keys, integrations)
  ├─ Can view all data across company
  ├─ Full access to Executive Web/Mobile apps
  └─ Company-wide visibility and control

csr (middle tier)
  ├─ Customer service representatives / Receptionists
  ├─ Can handle calls and book appointments
  ├─ Can view all company leads (shared work)
  ├─ Can see own performance stats only
  ├─ Access to Receptionist Web App only
  └─ Cannot access admin functions or rep domain

rep (focused access)
  ├─ Field sales representatives
  ├─ Can view own calls, appointments, follow-ups
  ├─ Can record appointments and post to Feed
  ├─ Can learn from company Feed (shared posts)
  ├─ Access to Sales Rep Mobile App only
  └─ Cannot view other reps' private data
```

### Getting User Context

```python
from app.middleware.rbac import get_user_context, ROLE_LEADERSHIP, ROLE_CSR, ROLE_REP

@router.get("/my-data")
async def get_my_data(request: Request):
    context = get_user_context(request)
    # Returns: {
    #   "user_id": "user_123",
    #   "tenant_id": "tenant_456",
    #   "user_role": "leadership" | "csr" | "rep",
    #   "rep_id": "rep_789",  # Optional
    #   "meeting_id": "meeting_012"  # Optional
    # }
```

### RBAC Error Handling

When a user attempts to access an endpoint without proper role:

```json
{
  "detail": "Access denied. Required roles: leadership. User role: rep"
}
```

HTTP Status: **403 Forbidden**

All RBAC violations are logged for security auditing.

### Migration to 4 Roles

If you need to split leadership into separate `exec` and `manager` roles:
- See `/docs/workspace/RBAC_MIGRATION_PLAN.md`
- Migration time: ~3 hours
- Difficulty: ⭐⭐ Easy (reversible, low risk)

---

## UWC Integration (AI/ML Partner)

### Overview

UWC (Unified Workflow Composer) by Shunya Labs provides Otto's AI/ML capabilities:
- **ASR**: Voice transcription (batch + real-time)
- **RAG**: Ask Otto intelligence (vector search + LLM reasoning)
- **Personal Clone**: Per-rep AI voice/style modeling
- **Follow-Up AI**: Personalized message drafting

### Configuration

Add to `.env`:

```bash
# UWC API Configuration
UWC_BASE_URL=https://api-dev.shunyalabs.ai
UWC_API_KEY=your_uwc_api_key_here
UWC_HMAC_SECRET=your_uwc_hmac_secret_here
UWC_VERSION=v1
USE_UWC_STAGING=true

# Feature Flags (enable gradually)
ENABLE_UWC_ASR=false
ENABLE_UWC_RAG=false
ENABLE_UWC_TRAINING=false
ENABLE_UWC_FOLLOWUPS=false
```

### Using the UWC Client

```python
from app.services.uwc_client import get_uwc_client

uwc = get_uwc_client()

# Submit ASR batch
result = await uwc.submit_asr_batch(
    company_id=request.state.tenant_id,
    request_id=request.state.trace_id,
    audio_urls=[{"url": "https://...", "call_id": "call_123"}]
)

# Query RAG (Ask Otto)
result = await uwc.query_rag(
    company_id=request.state.tenant_id,
    request_id=request.state.trace_id,
    query="What are the most common objections?",
    context={"user_role": request.state.user_role}
)

# Index documents
result = await uwc.index_documents(
    company_id=request.state.tenant_id,
    request_id=request.state.trace_id,
    documents=[{"document_id": "doc_123", "content": "..."}]
)

# Submit training job
result = await uwc.submit_training_job(
    company_id=request.state.tenant_id,
    request_id=request.state.trace_id,
    training_data={"rep_id": "rep_789", "media_urls": [...]}
)
```

### UWC Webhooks

Otto receives webhooks from UWC for async operations:

**Endpoints:**
- `POST /webhooks/uwc/asr/complete` - ASR batch completion
- `POST /webhooks/uwc/rag/indexed` - Document indexing complete
- `POST /webhooks/uwc/training/status` - Training job status update
- `POST /webhooks/uwc/analysis/complete` - ML analysis complete
- `POST /webhooks/uwc/followup/draft` - Follow-up draft ready

**Security:**
- All webhooks verify HMAC signatures
- Timestamps validated (5-minute window)
- Idempotency enforced (duplicate webhooks ignored)
- Tenant ownership validated

### Local Development with Mock UWC

For local development without UWC staging access:

```bash
# Terminal 1: Start mock UWC server
python tests/mocks/uwc_mock_server.py

# Terminal 2: Configure Otto to use mock
export UWC_BASE_URL=http://localhost:8001
export UWC_API_KEY=mock_key
export ENABLE_UWC_ASR=true
export ENABLE_UWC_RAG=true

# Run Otto API
uvicorn app.main:app --reload

# Terminal 3: Run integration tests
pytest tests/integration/test_uwc_integration.py -v -m integration
```

### UWC Integration Testing

```bash
# Run all UWC integration tests
pytest tests/integration/test_uwc_integration.py -v -m integration

# Run UWC client unit tests
pytest tests/test_uwc_client.py -v

# Test webhook handlers
pytest tests/integration/test_uwc_integration.py::test_uwc_webhook_asr_complete -v
```

### Feature Flag Rollout

Enable UWC features gradually:

**Week 2-3: ASR Only**
```bash
ENABLE_UWC_ASR=true
ENABLE_UWC_RAG=false
ENABLE_UWC_TRAINING=false
ENABLE_UWC_FOLLOWUPS=false
```

**Week 4-5: Add RAG**
```bash
ENABLE_UWC_ASR=true
ENABLE_UWC_RAG=true
ENABLE_UWC_TRAINING=false
ENABLE_UWC_FOLLOWUPS=false
```

**Week 6-7: Add Training & Follow-ups**
```bash
ENABLE_UWC_ASR=true
ENABLE_UWC_RAG=true
ENABLE_UWC_TRAINING=true
ENABLE_UWC_FOLLOWUPS=true
```

### Monitoring UWC Integration

**Prometheus Metrics:**
```
uwc_requests_total{endpoint, method, status}
uwc_request_duration_ms{endpoint, method}
uwc_request_errors_total{endpoint, error_type}
uwc_retries_total{endpoint}
```

**Grafana Dashboard Queries:**
```promql
# UWC API latency (p95)
histogram_quantile(0.95, rate(uwc_request_duration_ms_bucket[5m]))

# UWC error rate
rate(uwc_request_errors_total[5m])

# UWC retry rate
rate(uwc_retries_total[5m])
```

### Troubleshooting UWC Integration

**Connection Issues:**
```bash
# Test UWC connectivity
curl -H "Authorization: Bearer $UWC_API_KEY" $UWC_BASE_URL/health

# Check UWC client logs
fly logs | grep "UWC\|uwc"
```

**Webhook Issues:**
```bash
# Check webhook receipts
fly logs | grep "webhooks/uwc"

# Verify HMAC secret
fly secrets list | grep UWC_HMAC_SECRET

# Test webhook locally
curl -X POST http://localhost:8000/webhooks/uwc/asr/complete \
  -H "Content-Type: application/json" \
  -d '{"job_id": "test", "company_id": "test", "call_id": "test", "status": "completed"}'
```

**Performance Issues:**
```bash
# Check UWC API latency
curl -w "@curl-format.txt" -H "Authorization: Bearer $UWC_API_KEY" \
  $UWC_BASE_URL/uwc/v1/rag/query -d '{"query": "test"}'

# Monitor metrics
curl http://localhost:8000/metrics | grep uwc_request_duration
```

---
- ✅ **Security Validation**: Multi-tenant isolation and access control testing