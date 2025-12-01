# Environment Variables Reference

**Date**: 2025-01-30  
**Purpose**: Complete reference of all environment variables used by the Otto dashboard service (backend + Celery)

---

## Overview

This document lists all environment variables read by the dashboard service, grouped by category. Each variable includes:
- **Name**: The exact environment variable name
- **Usage**: What it's used for
- **Required in Production**: Whether it must be set in production
- **Example Value**: Sensible example (not actual secrets)

**Source**: Derived from `app/config.py` and direct `os.getenv()` calls in the codebase.

---

## Core Application

### Database

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `DATABASE_URL` | PostgreSQL connection string. Used by SQLAlchemy for all database operations. | ✅ **Yes** | `postgresql://user:pass@host:5432/dbname` |

**Notes**:
- Railway automatically sets this when PostgreSQL add-on is provisioned
- Fallback for local dev: `sqlite:///./otto_dev.db` (not for production)

---

### Redis

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `REDIS_URL` | Redis connection URL. Used for Celery broker, result backend, rate limiting, WebSocket pub/sub. | ✅ **Yes** (if Celery/rate limiting enabled) | `redis://localhost:6379/0` |
| `UPSTASH_REDIS_URL` | Alternative Redis URL (Upstash). Used if `REDIS_URL` is not set. | ✅ **Yes** (if `REDIS_URL` not set and Celery/rate limiting enabled) | `rediss://default:token@host.upstash.io:6379` |

**Notes**:
- Either `REDIS_URL` or `UPSTASH_REDIS_URL` must be set if `ENABLE_CELERY=true` or rate limiting is enabled
- Railway Upstash add-on automatically sets `UPSTASH_REDIS_URL`

---

### Authentication & JWT (Clerk)

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `CLERK_SECRET_KEY` | Clerk secret key for JWT verification and API calls. | ✅ **Yes** | `sk_test_abc123...` |
| `CLERK_PUBLISHABLE_KEY` | Clerk publishable key (for frontend). | ⚠️ **Recommended** | `pk_test_abc123...` |
| `CLERK_API_URL` | Clerk API base URL. | ❌ No (has default) | `https://api.clerk.dev/v1` |
| `CLERK_ISSUER` | Clerk JWT issuer URL. Used for JWT validation. | ⚠️ **Recommended** | `https://your-app.clerk.accounts.dev` |
| `CLERK_FRONTEND_ORIGIN` | Clerk frontend origin. Used to construct JWKS URL. | ⚠️ **Recommended** | `https://your-app.clerk.accounts.dev` |
| `CLERK_WEBHOOK_SECRET` | Secret for verifying Clerk webhook signatures. | ⚠️ **Recommended** (if using Clerk webhooks) | `whsec_abc123...` |

**Notes**:
- `CLERK_SECRET_KEY` is validated in production (must not be placeholder)
- `CLERK_ISSUER` and `CLERK_FRONTEND_ORIGIN` default to a dev instance (update for production)

---

## Shunya / UWC Integration

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `UWC_BASE_URL` | Shunya API base URL. | ❌ No (has default) | `https://otto.shunyalabs.ai` |
| `UWC_API_KEY` | Shunya API key for authentication. | ✅ **Yes** (if UWC features enabled) | `uwc_key_abc123...` |
| `UWC_JWT_SECRET` | JWT secret for UWC authentication (if used). | ⚠️ **Conditional** | `jwt_secret_abc123...` |
| `UWC_HMAC_SECRET` | HMAC secret for verifying Shunya webhook signatures. | ✅ **Yes** (if receiving Shunya webhooks) | `hmac_secret_abc123...` |
| `UWC_VERSION` | UWC API version. | ❌ No (has default) | `v1` |
| `USE_UWC_STAGING` | Use UWC staging environment instead of production. | ❌ No (default: `false`) | `false` |

### UWC Feature Flags

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `ENABLE_UWC_RAG` | Enable RAG (Retrieval-Augmented Generation) features. | ❌ No (default: `false`) | `true` |
| `ENABLE_UWC_ASR` | Enable ASR (Automatic Speech Recognition) via UWC. | ❌ No (default: `false`) | `true` |
| `ENABLE_UWC_TRAINING` | Enable training features. | ❌ No (default: `false`) | `true` |
| `ENABLE_UWC_FOLLOWUPS` | Enable automated follow-up features. | ❌ No (default: `false`) | `true` |
| `ENABLE_UWC_SUMMARIZATION` | Enable summarization features. | ❌ No (default: `false`) | `true` |

**Notes**:
- `UWC_HMAC_SECRET` is **critical** for webhook security - must match Shunya's configured secret
- Feature flags can be enabled independently
- If no UWC features are enabled, `UWC_API_KEY` is not required

---

## Twilio / SMS

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `TWILIO_ACCOUNT_SID` | Twilio account SID. | ✅ **Yes** | `AC1234567890abcdef...` |
| `TWILIO_AUTH_TOKEN` | Twilio authentication token. | ✅ **Yes** | `abc123def456...` |
| `TWILIO_FROM_NUMBER` | Twilio phone number to send SMS from. | ✅ **Yes** | `+1234567890` |
| `TWILIO_CALLBACK_NUMBER` | Twilio callback number for voice calls. | ⚠️ **Recommended** | `+1234567890` |
| `TWILIO_API_BASE_URL` | Twilio API base URL. | ❌ No (has default) | `https://api.twilio.com` |

**Notes**:
- `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` are validated in production (must not be placeholder)
- `TWILIO_FROM_NUMBER` must be a verified Twilio phone number
- Webhook URLs must be configured in Twilio dashboard to point to your deployment

---

## CallRail

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `CALLRAIL_API_KEY` | CallRail API key for fetching call data. | ✅ **Yes** | `abc123def456...` |
| `CALLRAIL_ACCOUNT_ID` | CallRail account ID. | ✅ **Yes** | `123456789` |
| `CALLRAIL_BASE_URL` | CallRail API base URL. | ❌ No (has default) | `https://api.callrail.com/v3` |

**Notes**:
- `CALLRAIL_API_KEY` is validated in production (must not be placeholder)
- Webhook URLs must be configured in CallRail dashboard to point to your deployment
- Webhook endpoint: `POST /callrail/call.completed` (without `/api/v1` prefix)

---

## AWS / S3 Storage

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `AWS_ACCESS_KEY_ID` | AWS access key ID for S3 access. | ✅ **Yes** (if using S3 storage) | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | AWS secret access key. | ✅ **Yes** (if using S3 storage) | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_REGION` | AWS region for S3 bucket. | ❌ No (default: `us-east-1`) | `us-east-1` |
| `AWS_DEFAULT_REGION` | Alternative AWS region (used if `AWS_REGION` not set). | ❌ No (fallback) | `us-east-1` |
| `S3_BUCKET` | S3 bucket name for storing documents/audio. | ✅ **Yes** (if using S3 storage) | `otto-documents-prod` |

**Notes**:
- Defaults to `otto-documents-prod` in production, `otto-documents-staging` otherwise
- Ensure S3 bucket exists and IAM user has appropriate permissions
- Used for storing audio files, transcripts, and other documents

---

## External AI Services

### Deepgram

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `DEEPGRAM_API_KEY` | Deepgram API key for speech-to-text. | ✅ **Yes** | `abc123def456...` |
| `DEEPGRAM_API_BASE_URL` | Deepgram API base URL. | ❌ No (has default) | `https://api.deepgram.com` |

**Notes**:
- `DEEPGRAM_API_KEY` is validated in production (must not be placeholder)

---

### OpenAI

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `OPENAI_API_KEY` | OpenAI API key for AI features. | ✅ **Yes** | `sk-abc123def456...` |
| `OPENAI_API_KEYS` | Comma-separated list of OpenAI API keys for rotation. | ⚠️ **Optional** (alternative to single key) | `sk-key1,sk-key2,sk-key3` |
| `OPENAI_KEY_ROTATION_STRATEGY` | Strategy for rotating multiple keys. | ❌ No (default: `round_robin`) | `round_robin`, `random`, `least_used` |

**Notes**:
- `OPENAI_API_KEY` is validated in production (must not be placeholder)
- If `OPENAI_API_KEYS` is set, it takes precedence over `OPENAI_API_KEY`
- Key rotation helps with rate limits and redundancy

---

### Bland AI

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `BLAND_API_KEY` | Bland AI API key for voice agent features. | ✅ **Yes** | `abc123def456...` |

**Notes**:
- `BLAND_API_KEY` is validated in production (must not be placeholder)

---

### Google Maps

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `GOOGLE_MAPS_API_KEY` | Google Maps API key for geocoding. | ⚠️ **Recommended** (if using geocoding) | `AIzaSyAbc123...` |

**Notes**:
- Used for geocoding addresses to coordinates
- Not required if geocoding is disabled

---

## Feature Flags

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `ENABLE_CELERY` | Enable Celery workers for background tasks. | ✅ **Yes** (for production) | `true` |
| `ENABLE_CELERY_BEAT` | Enable Celery beat scheduler for periodic tasks. | ✅ **Yes** (for production) | `true` |
| `ENABLE_RATE_LIMITING` | Enable rate limiting (requires Redis). | ❌ No (default: `true`) | `true` |

**Notes**:
- `ENABLE_CELERY=true` and `ENABLE_CELERY_BEAT=true` are required for production
- Rate limiting is enabled by default but requires Redis

---

## Observability & Logging

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR). | ❌ No (default: `INFO`) | `INFO` |
| `OBS_REDACT_PII` | Enable PII redaction in logs. | ❌ No (default: `true`) | `true` |
| `SENTRY_DSN` | Sentry DSN for error tracking. | ⚠️ **Recommended** | `https://abc123@o123456.ingest.sentry.io/123456` |
| `SENTRY_TRACES_SAMPLE_RATE` | Sentry trace sampling rate (0.0-1.0). | ❌ No (default: `0.1`) | `0.1` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OpenTelemetry OTLP endpoint for traces/metrics. | ❌ No | `https://otel-collector.example.com:4318` |
| `OTEL_SERVICE_NAME_API` | OpenTelemetry service name for API. | ❌ No (default: `otto-api`) | `otto-api` |
| `OTEL_SERVICE_NAME_WORKER` | OpenTelemetry service name for workers. | ❌ No (default: `otto-worker`) | `otto-worker` |

**Notes**:
- Sentry is highly recommended for production error tracking
- OpenTelemetry is optional but useful for distributed tracing

---

## Application Configuration

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `ENVIRONMENT` | Environment name (development, staging, production). | ⚠️ **Recommended** | `production` |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins. | ✅ **Yes** | `https://app.otto.ai,https://staging.otto.ai` |
| `PORT` | Port for web server (Railway sets automatically). | ❌ No (default: `8080`) | `8080` |

**Notes**:
- `ENVIRONMENT=production` triggers stricter validation
- `ALLOWED_ORIGINS` must include all frontend URLs that will call the API
- Railway automatically sets `PORT` - don't override

---

## Rate Limiting Configuration

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `RATE_LIMIT_USER` | Per-user rate limit. | ❌ No (default: `60/minute`) | `60/minute` |
| `RATE_LIMIT_TENANT` | Per-tenant rate limit. | ❌ No (default: `600/minute`) | `600/minute` |

**Notes**:
- Format: `{number}/{unit}` (e.g., `60/minute`, `1000/hour`)
- Requires Redis if rate limiting is enabled

---

## Idempotency Configuration

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `IDEMPOTENCY_TTL_DAYS` | Days to keep idempotency keys in database. | ❌ No (default: `90`) | `90` |

**Notes**:
- Controls how long idempotency keys are retained
- Used for preventing duplicate operations

---

## Development / Testing

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `DEV_MODE` | Enable development mode (relaxes validations). | ❌ No (default: `false`) | `false` |
| `DEV_EMIT_KEY` | Key for emitting test events. | ❌ No | `dev_test_key` |
| `DEV_TEST_COMPANY_ID` | Test company ID for development. | ❌ No | `dev-test-company` |
| `DEV_TEST_USER_ID` | Test user ID for development. | ❌ No | `dev-test-user` |

**Notes**:
- **Never set these in production**
- Used for local development and testing only

---

## Internal AI API

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `AI_INTERNAL_TOKEN` | Token for internal AI API authentication. | ⚠️ **Conditional** (if using internal AI endpoints) | `internal_token_abc123...` |

**Notes**:
- Used for authenticating internal AI API calls
- Not required for standard CSR/dashboard operations

---

## Summary by Environment

### Production (Required)

**Core**:
- `DATABASE_URL`
- `REDIS_URL` or `UPSTASH_REDIS_URL` (if Celery/rate limiting enabled)
- `CLERK_SECRET_KEY`
- `ALLOWED_ORIGINS`

**External Services**:
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`
- `CALLRAIL_API_KEY`, `CALLRAIL_ACCOUNT_ID`
- `DEEPGRAM_API_KEY`
- `OPENAI_API_KEY`
- `BLAND_API_KEY`

**Feature Flags**:
- `ENABLE_CELERY=true`
- `ENABLE_CELERY_BEAT=true`

**Shunya/UWC** (if enabled):
- `UWC_API_KEY`
- `UWC_HMAC_SECRET` (if receiving webhooks)

**S3** (if using):
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET`

---

### Staging

Same as production, but:
- May use staging S3 bucket (`otto-documents-staging`)
- May use `USE_UWC_STAGING=true`
- May use staging API keys for external services

---

### Local Development

**Minimum**:
- `DATABASE_URL` (or use SQLite default)
- `CLERK_SECRET_KEY` (or disable auth for testing)
- `REDIS_URL` (if testing Celery/rate limiting)

**Optional**:
- All external service keys (can use placeholders if features disabled)
- Feature flags can be `false` to disable features

---

## Validation

The application validates environment variables on startup:

1. **Production checks**: In `ENVIRONMENT=production`, validates that required secrets are not placeholders
2. **Redis requirement**: If `ENABLE_CELERY=true` or rate limiting enabled, `REDIS_URL` or `UPSTASH_REDIS_URL` must be set
3. **Feature flags**: Feature flags default to safe values (disabled) if not set

---

## See Also

- `docs/infra/RAILWAY_SETUP.md` - Railway deployment guide
- `docs/infra/DEPLOYMENT_CHECKLIST.md` - Deployment checklist
- `app/config.py` - Source code for all environment variable definitions



**Date**: 2025-01-30  
**Purpose**: Complete reference of all environment variables used by the Otto dashboard service (backend + Celery)

---

## Overview

This document lists all environment variables read by the dashboard service, grouped by category. Each variable includes:
- **Name**: The exact environment variable name
- **Usage**: What it's used for
- **Required in Production**: Whether it must be set in production
- **Example Value**: Sensible example (not actual secrets)

**Source**: Derived from `app/config.py` and direct `os.getenv()` calls in the codebase.

---

## Core Application

### Database

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `DATABASE_URL` | PostgreSQL connection string. Used by SQLAlchemy for all database operations. | ✅ **Yes** | `postgresql://user:pass@host:5432/dbname` |

**Notes**:
- Railway automatically sets this when PostgreSQL add-on is provisioned
- Fallback for local dev: `sqlite:///./otto_dev.db` (not for production)

---

### Redis

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `REDIS_URL` | Redis connection URL. Used for Celery broker, result backend, rate limiting, WebSocket pub/sub. | ✅ **Yes** (if Celery/rate limiting enabled) | `redis://localhost:6379/0` |
| `UPSTASH_REDIS_URL` | Alternative Redis URL (Upstash). Used if `REDIS_URL` is not set. | ✅ **Yes** (if `REDIS_URL` not set and Celery/rate limiting enabled) | `rediss://default:token@host.upstash.io:6379` |

**Notes**:
- Either `REDIS_URL` or `UPSTASH_REDIS_URL` must be set if `ENABLE_CELERY=true` or rate limiting is enabled
- Railway Upstash add-on automatically sets `UPSTASH_REDIS_URL`

---

### Authentication & JWT (Clerk)

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `CLERK_SECRET_KEY` | Clerk secret key for JWT verification and API calls. | ✅ **Yes** | `sk_test_abc123...` |
| `CLERK_PUBLISHABLE_KEY` | Clerk publishable key (for frontend). | ⚠️ **Recommended** | `pk_test_abc123...` |
| `CLERK_API_URL` | Clerk API base URL. | ❌ No (has default) | `https://api.clerk.dev/v1` |
| `CLERK_ISSUER` | Clerk JWT issuer URL. Used for JWT validation. | ⚠️ **Recommended** | `https://your-app.clerk.accounts.dev` |
| `CLERK_FRONTEND_ORIGIN` | Clerk frontend origin. Used to construct JWKS URL. | ⚠️ **Recommended** | `https://your-app.clerk.accounts.dev` |
| `CLERK_WEBHOOK_SECRET` | Secret for verifying Clerk webhook signatures. | ⚠️ **Recommended** (if using Clerk webhooks) | `whsec_abc123...` |

**Notes**:
- `CLERK_SECRET_KEY` is validated in production (must not be placeholder)
- `CLERK_ISSUER` and `CLERK_FRONTEND_ORIGIN` default to a dev instance (update for production)

---

## Shunya / UWC Integration

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `UWC_BASE_URL` | Shunya API base URL. | ❌ No (has default) | `https://otto.shunyalabs.ai` |
| `UWC_API_KEY` | Shunya API key for authentication. | ✅ **Yes** (if UWC features enabled) | `uwc_key_abc123...` |
| `UWC_JWT_SECRET` | JWT secret for UWC authentication (if used). | ⚠️ **Conditional** | `jwt_secret_abc123...` |
| `UWC_HMAC_SECRET` | HMAC secret for verifying Shunya webhook signatures. | ✅ **Yes** (if receiving Shunya webhooks) | `hmac_secret_abc123...` |
| `UWC_VERSION` | UWC API version. | ❌ No (has default) | `v1` |
| `USE_UWC_STAGING` | Use UWC staging environment instead of production. | ❌ No (default: `false`) | `false` |

### UWC Feature Flags

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `ENABLE_UWC_RAG` | Enable RAG (Retrieval-Augmented Generation) features. | ❌ No (default: `false`) | `true` |
| `ENABLE_UWC_ASR` | Enable ASR (Automatic Speech Recognition) via UWC. | ❌ No (default: `false`) | `true` |
| `ENABLE_UWC_TRAINING` | Enable training features. | ❌ No (default: `false`) | `true` |
| `ENABLE_UWC_FOLLOWUPS` | Enable automated follow-up features. | ❌ No (default: `false`) | `true` |
| `ENABLE_UWC_SUMMARIZATION` | Enable summarization features. | ❌ No (default: `false`) | `true` |

**Notes**:
- `UWC_HMAC_SECRET` is **critical** for webhook security - must match Shunya's configured secret
- Feature flags can be enabled independently
- If no UWC features are enabled, `UWC_API_KEY` is not required

---

## Twilio / SMS

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `TWILIO_ACCOUNT_SID` | Twilio account SID. | ✅ **Yes** | `AC1234567890abcdef...` |
| `TWILIO_AUTH_TOKEN` | Twilio authentication token. | ✅ **Yes** | `abc123def456...` |
| `TWILIO_FROM_NUMBER` | Twilio phone number to send SMS from. | ✅ **Yes** | `+1234567890` |
| `TWILIO_CALLBACK_NUMBER` | Twilio callback number for voice calls. | ⚠️ **Recommended** | `+1234567890` |
| `TWILIO_API_BASE_URL` | Twilio API base URL. | ❌ No (has default) | `https://api.twilio.com` |

**Notes**:
- `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` are validated in production (must not be placeholder)
- `TWILIO_FROM_NUMBER` must be a verified Twilio phone number
- Webhook URLs must be configured in Twilio dashboard to point to your deployment

---

## CallRail

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `CALLRAIL_API_KEY` | CallRail API key for fetching call data. | ✅ **Yes** | `abc123def456...` |
| `CALLRAIL_ACCOUNT_ID` | CallRail account ID. | ✅ **Yes** | `123456789` |
| `CALLRAIL_BASE_URL` | CallRail API base URL. | ❌ No (has default) | `https://api.callrail.com/v3` |

**Notes**:
- `CALLRAIL_API_KEY` is validated in production (must not be placeholder)
- Webhook URLs must be configured in CallRail dashboard to point to your deployment
- Webhook endpoint: `POST /callrail/call.completed` (without `/api/v1` prefix)

---

## AWS / S3 Storage

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `AWS_ACCESS_KEY_ID` | AWS access key ID for S3 access. | ✅ **Yes** (if using S3 storage) | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | AWS secret access key. | ✅ **Yes** (if using S3 storage) | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_REGION` | AWS region for S3 bucket. | ❌ No (default: `us-east-1`) | `us-east-1` |
| `AWS_DEFAULT_REGION` | Alternative AWS region (used if `AWS_REGION` not set). | ❌ No (fallback) | `us-east-1` |
| `S3_BUCKET` | S3 bucket name for storing documents/audio. | ✅ **Yes** (if using S3 storage) | `otto-documents-prod` |

**Notes**:
- Defaults to `otto-documents-prod` in production, `otto-documents-staging` otherwise
- Ensure S3 bucket exists and IAM user has appropriate permissions
- Used for storing audio files, transcripts, and other documents

---

## External AI Services

### Deepgram

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `DEEPGRAM_API_KEY` | Deepgram API key for speech-to-text. | ✅ **Yes** | `abc123def456...` |
| `DEEPGRAM_API_BASE_URL` | Deepgram API base URL. | ❌ No (has default) | `https://api.deepgram.com` |

**Notes**:
- `DEEPGRAM_API_KEY` is validated in production (must not be placeholder)

---

### OpenAI

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `OPENAI_API_KEY` | OpenAI API key for AI features. | ✅ **Yes** | `sk-abc123def456...` |
| `OPENAI_API_KEYS` | Comma-separated list of OpenAI API keys for rotation. | ⚠️ **Optional** (alternative to single key) | `sk-key1,sk-key2,sk-key3` |
| `OPENAI_KEY_ROTATION_STRATEGY` | Strategy for rotating multiple keys. | ❌ No (default: `round_robin`) | `round_robin`, `random`, `least_used` |

**Notes**:
- `OPENAI_API_KEY` is validated in production (must not be placeholder)
- If `OPENAI_API_KEYS` is set, it takes precedence over `OPENAI_API_KEY`
- Key rotation helps with rate limits and redundancy

---

### Bland AI

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `BLAND_API_KEY` | Bland AI API key for voice agent features. | ✅ **Yes** | `abc123def456...` |

**Notes**:
- `BLAND_API_KEY` is validated in production (must not be placeholder)

---

### Google Maps

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `GOOGLE_MAPS_API_KEY` | Google Maps API key for geocoding. | ⚠️ **Recommended** (if using geocoding) | `AIzaSyAbc123...` |

**Notes**:
- Used for geocoding addresses to coordinates
- Not required if geocoding is disabled

---

## Feature Flags

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `ENABLE_CELERY` | Enable Celery workers for background tasks. | ✅ **Yes** (for production) | `true` |
| `ENABLE_CELERY_BEAT` | Enable Celery beat scheduler for periodic tasks. | ✅ **Yes** (for production) | `true` |
| `ENABLE_RATE_LIMITING` | Enable rate limiting (requires Redis). | ❌ No (default: `true`) | `true` |

**Notes**:
- `ENABLE_CELERY=true` and `ENABLE_CELERY_BEAT=true` are required for production
- Rate limiting is enabled by default but requires Redis

---

## Observability & Logging

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR). | ❌ No (default: `INFO`) | `INFO` |
| `OBS_REDACT_PII` | Enable PII redaction in logs. | ❌ No (default: `true`) | `true` |
| `SENTRY_DSN` | Sentry DSN for error tracking. | ⚠️ **Recommended** | `https://abc123@o123456.ingest.sentry.io/123456` |
| `SENTRY_TRACES_SAMPLE_RATE` | Sentry trace sampling rate (0.0-1.0). | ❌ No (default: `0.1`) | `0.1` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OpenTelemetry OTLP endpoint for traces/metrics. | ❌ No | `https://otel-collector.example.com:4318` |
| `OTEL_SERVICE_NAME_API` | OpenTelemetry service name for API. | ❌ No (default: `otto-api`) | `otto-api` |
| `OTEL_SERVICE_NAME_WORKER` | OpenTelemetry service name for workers. | ❌ No (default: `otto-worker`) | `otto-worker` |

**Notes**:
- Sentry is highly recommended for production error tracking
- OpenTelemetry is optional but useful for distributed tracing

---

## Application Configuration

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `ENVIRONMENT` | Environment name (development, staging, production). | ⚠️ **Recommended** | `production` |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins. | ✅ **Yes** | `https://app.otto.ai,https://staging.otto.ai` |
| `PORT` | Port for web server (Railway sets automatically). | ❌ No (default: `8080`) | `8080` |

**Notes**:
- `ENVIRONMENT=production` triggers stricter validation
- `ALLOWED_ORIGINS` must include all frontend URLs that will call the API
- Railway automatically sets `PORT` - don't override

---

## Rate Limiting Configuration

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `RATE_LIMIT_USER` | Per-user rate limit. | ❌ No (default: `60/minute`) | `60/minute` |
| `RATE_LIMIT_TENANT` | Per-tenant rate limit. | ❌ No (default: `600/minute`) | `600/minute` |

**Notes**:
- Format: `{number}/{unit}` (e.g., `60/minute`, `1000/hour`)
- Requires Redis if rate limiting is enabled

---

## Idempotency Configuration

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `IDEMPOTENCY_TTL_DAYS` | Days to keep idempotency keys in database. | ❌ No (default: `90`) | `90` |

**Notes**:
- Controls how long idempotency keys are retained
- Used for preventing duplicate operations

---

## Development / Testing

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `DEV_MODE` | Enable development mode (relaxes validations). | ❌ No (default: `false`) | `false` |
| `DEV_EMIT_KEY` | Key for emitting test events. | ❌ No | `dev_test_key` |
| `DEV_TEST_COMPANY_ID` | Test company ID for development. | ❌ No | `dev-test-company` |
| `DEV_TEST_USER_ID` | Test user ID for development. | ❌ No | `dev-test-user` |

**Notes**:
- **Never set these in production**
- Used for local development and testing only

---

## Internal AI API

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `AI_INTERNAL_TOKEN` | Token for internal AI API authentication. | ⚠️ **Conditional** (if using internal AI endpoints) | `internal_token_abc123...` |

**Notes**:
- Used for authenticating internal AI API calls
- Not required for standard CSR/dashboard operations

---

## Summary by Environment

### Production (Required)

**Core**:
- `DATABASE_URL`
- `REDIS_URL` or `UPSTASH_REDIS_URL` (if Celery/rate limiting enabled)
- `CLERK_SECRET_KEY`
- `ALLOWED_ORIGINS`

**External Services**:
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`
- `CALLRAIL_API_KEY`, `CALLRAIL_ACCOUNT_ID`
- `DEEPGRAM_API_KEY`
- `OPENAI_API_KEY`
- `BLAND_API_KEY`

**Feature Flags**:
- `ENABLE_CELERY=true`
- `ENABLE_CELERY_BEAT=true`

**Shunya/UWC** (if enabled):
- `UWC_API_KEY`
- `UWC_HMAC_SECRET` (if receiving webhooks)

**S3** (if using):
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET`

---

### Staging

Same as production, but:
- May use staging S3 bucket (`otto-documents-staging`)
- May use `USE_UWC_STAGING=true`
- May use staging API keys for external services

---

### Local Development

**Minimum**:
- `DATABASE_URL` (or use SQLite default)
- `CLERK_SECRET_KEY` (or disable auth for testing)
- `REDIS_URL` (if testing Celery/rate limiting)

**Optional**:
- All external service keys (can use placeholders if features disabled)
- Feature flags can be `false` to disable features

---

## Validation

The application validates environment variables on startup:

1. **Production checks**: In `ENVIRONMENT=production`, validates that required secrets are not placeholders
2. **Redis requirement**: If `ENABLE_CELERY=true` or rate limiting enabled, `REDIS_URL` or `UPSTASH_REDIS_URL` must be set
3. **Feature flags**: Feature flags default to safe values (disabled) if not set

---

## See Also

- `docs/infra/RAILWAY_SETUP.md` - Railway deployment guide
- `docs/infra/DEPLOYMENT_CHECKLIST.md` - Deployment checklist
- `app/config.py` - Source code for all environment variable definitions



**Date**: 2025-01-30  
**Purpose**: Complete reference of all environment variables used by the Otto dashboard service (backend + Celery)

---

## Overview

This document lists all environment variables read by the dashboard service, grouped by category. Each variable includes:
- **Name**: The exact environment variable name
- **Usage**: What it's used for
- **Required in Production**: Whether it must be set in production
- **Example Value**: Sensible example (not actual secrets)

**Source**: Derived from `app/config.py` and direct `os.getenv()` calls in the codebase.

---

## Core Application

### Database

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `DATABASE_URL` | PostgreSQL connection string. Used by SQLAlchemy for all database operations. | ✅ **Yes** | `postgresql://user:pass@host:5432/dbname` |

**Notes**:
- Railway automatically sets this when PostgreSQL add-on is provisioned
- Fallback for local dev: `sqlite:///./otto_dev.db` (not for production)

---

### Redis

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `REDIS_URL` | Redis connection URL. Used for Celery broker, result backend, rate limiting, WebSocket pub/sub. | ✅ **Yes** (if Celery/rate limiting enabled) | `redis://localhost:6379/0` |
| `UPSTASH_REDIS_URL` | Alternative Redis URL (Upstash). Used if `REDIS_URL` is not set. | ✅ **Yes** (if `REDIS_URL` not set and Celery/rate limiting enabled) | `rediss://default:token@host.upstash.io:6379` |

**Notes**:
- Either `REDIS_URL` or `UPSTASH_REDIS_URL` must be set if `ENABLE_CELERY=true` or rate limiting is enabled
- Railway Upstash add-on automatically sets `UPSTASH_REDIS_URL`

---

### Authentication & JWT (Clerk)

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `CLERK_SECRET_KEY` | Clerk secret key for JWT verification and API calls. | ✅ **Yes** | `sk_test_abc123...` |
| `CLERK_PUBLISHABLE_KEY` | Clerk publishable key (for frontend). | ⚠️ **Recommended** | `pk_test_abc123...` |
| `CLERK_API_URL` | Clerk API base URL. | ❌ No (has default) | `https://api.clerk.dev/v1` |
| `CLERK_ISSUER` | Clerk JWT issuer URL. Used for JWT validation. | ⚠️ **Recommended** | `https://your-app.clerk.accounts.dev` |
| `CLERK_FRONTEND_ORIGIN` | Clerk frontend origin. Used to construct JWKS URL. | ⚠️ **Recommended** | `https://your-app.clerk.accounts.dev` |
| `CLERK_WEBHOOK_SECRET` | Secret for verifying Clerk webhook signatures. | ⚠️ **Recommended** (if using Clerk webhooks) | `whsec_abc123...` |

**Notes**:
- `CLERK_SECRET_KEY` is validated in production (must not be placeholder)
- `CLERK_ISSUER` and `CLERK_FRONTEND_ORIGIN` default to a dev instance (update for production)

---

## Shunya / UWC Integration

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `UWC_BASE_URL` | Shunya API base URL. | ❌ No (has default) | `https://otto.shunyalabs.ai` |
| `UWC_API_KEY` | Shunya API key for authentication. | ✅ **Yes** (if UWC features enabled) | `uwc_key_abc123...` |
| `UWC_JWT_SECRET` | JWT secret for UWC authentication (if used). | ⚠️ **Conditional** | `jwt_secret_abc123...` |
| `UWC_HMAC_SECRET` | HMAC secret for verifying Shunya webhook signatures. | ✅ **Yes** (if receiving Shunya webhooks) | `hmac_secret_abc123...` |
| `UWC_VERSION` | UWC API version. | ❌ No (has default) | `v1` |
| `USE_UWC_STAGING` | Use UWC staging environment instead of production. | ❌ No (default: `false`) | `false` |

### UWC Feature Flags

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `ENABLE_UWC_RAG` | Enable RAG (Retrieval-Augmented Generation) features. | ❌ No (default: `false`) | `true` |
| `ENABLE_UWC_ASR` | Enable ASR (Automatic Speech Recognition) via UWC. | ❌ No (default: `false`) | `true` |
| `ENABLE_UWC_TRAINING` | Enable training features. | ❌ No (default: `false`) | `true` |
| `ENABLE_UWC_FOLLOWUPS` | Enable automated follow-up features. | ❌ No (default: `false`) | `true` |
| `ENABLE_UWC_SUMMARIZATION` | Enable summarization features. | ❌ No (default: `false`) | `true` |

**Notes**:
- `UWC_HMAC_SECRET` is **critical** for webhook security - must match Shunya's configured secret
- Feature flags can be enabled independently
- If no UWC features are enabled, `UWC_API_KEY` is not required

---

## Twilio / SMS

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `TWILIO_ACCOUNT_SID` | Twilio account SID. | ✅ **Yes** | `AC1234567890abcdef...` |
| `TWILIO_AUTH_TOKEN` | Twilio authentication token. | ✅ **Yes** | `abc123def456...` |
| `TWILIO_FROM_NUMBER` | Twilio phone number to send SMS from. | ✅ **Yes** | `+1234567890` |
| `TWILIO_CALLBACK_NUMBER` | Twilio callback number for voice calls. | ⚠️ **Recommended** | `+1234567890` |
| `TWILIO_API_BASE_URL` | Twilio API base URL. | ❌ No (has default) | `https://api.twilio.com` |

**Notes**:
- `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` are validated in production (must not be placeholder)
- `TWILIO_FROM_NUMBER` must be a verified Twilio phone number
- Webhook URLs must be configured in Twilio dashboard to point to your deployment

---

## CallRail

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `CALLRAIL_API_KEY` | CallRail API key for fetching call data. | ✅ **Yes** | `abc123def456...` |
| `CALLRAIL_ACCOUNT_ID` | CallRail account ID. | ✅ **Yes** | `123456789` |
| `CALLRAIL_BASE_URL` | CallRail API base URL. | ❌ No (has default) | `https://api.callrail.com/v3` |

**Notes**:
- `CALLRAIL_API_KEY` is validated in production (must not be placeholder)
- Webhook URLs must be configured in CallRail dashboard to point to your deployment
- Webhook endpoint: `POST /callrail/call.completed` (without `/api/v1` prefix)

---

## AWS / S3 Storage

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `AWS_ACCESS_KEY_ID` | AWS access key ID for S3 access. | ✅ **Yes** (if using S3 storage) | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | AWS secret access key. | ✅ **Yes** (if using S3 storage) | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_REGION` | AWS region for S3 bucket. | ❌ No (default: `us-east-1`) | `us-east-1` |
| `AWS_DEFAULT_REGION` | Alternative AWS region (used if `AWS_REGION` not set). | ❌ No (fallback) | `us-east-1` |
| `S3_BUCKET` | S3 bucket name for storing documents/audio. | ✅ **Yes** (if using S3 storage) | `otto-documents-prod` |

**Notes**:
- Defaults to `otto-documents-prod` in production, `otto-documents-staging` otherwise
- Ensure S3 bucket exists and IAM user has appropriate permissions
- Used for storing audio files, transcripts, and other documents

---

## External AI Services

### Deepgram

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `DEEPGRAM_API_KEY` | Deepgram API key for speech-to-text. | ✅ **Yes** | `abc123def456...` |
| `DEEPGRAM_API_BASE_URL` | Deepgram API base URL. | ❌ No (has default) | `https://api.deepgram.com` |

**Notes**:
- `DEEPGRAM_API_KEY` is validated in production (must not be placeholder)

---

### OpenAI

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `OPENAI_API_KEY` | OpenAI API key for AI features. | ✅ **Yes** | `sk-abc123def456...` |
| `OPENAI_API_KEYS` | Comma-separated list of OpenAI API keys for rotation. | ⚠️ **Optional** (alternative to single key) | `sk-key1,sk-key2,sk-key3` |
| `OPENAI_KEY_ROTATION_STRATEGY` | Strategy for rotating multiple keys. | ❌ No (default: `round_robin`) | `round_robin`, `random`, `least_used` |

**Notes**:
- `OPENAI_API_KEY` is validated in production (must not be placeholder)
- If `OPENAI_API_KEYS` is set, it takes precedence over `OPENAI_API_KEY`
- Key rotation helps with rate limits and redundancy

---

### Bland AI

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `BLAND_API_KEY` | Bland AI API key for voice agent features. | ✅ **Yes** | `abc123def456...` |

**Notes**:
- `BLAND_API_KEY` is validated in production (must not be placeholder)

---

### Google Maps

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `GOOGLE_MAPS_API_KEY` | Google Maps API key for geocoding. | ⚠️ **Recommended** (if using geocoding) | `AIzaSyAbc123...` |

**Notes**:
- Used for geocoding addresses to coordinates
- Not required if geocoding is disabled

---

## Feature Flags

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `ENABLE_CELERY` | Enable Celery workers for background tasks. | ✅ **Yes** (for production) | `true` |
| `ENABLE_CELERY_BEAT` | Enable Celery beat scheduler for periodic tasks. | ✅ **Yes** (for production) | `true` |
| `ENABLE_RATE_LIMITING` | Enable rate limiting (requires Redis). | ❌ No (default: `true`) | `true` |

**Notes**:
- `ENABLE_CELERY=true` and `ENABLE_CELERY_BEAT=true` are required for production
- Rate limiting is enabled by default but requires Redis

---

## Observability & Logging

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR). | ❌ No (default: `INFO`) | `INFO` |
| `OBS_REDACT_PII` | Enable PII redaction in logs. | ❌ No (default: `true`) | `true` |
| `SENTRY_DSN` | Sentry DSN for error tracking. | ⚠️ **Recommended** | `https://abc123@o123456.ingest.sentry.io/123456` |
| `SENTRY_TRACES_SAMPLE_RATE` | Sentry trace sampling rate (0.0-1.0). | ❌ No (default: `0.1`) | `0.1` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OpenTelemetry OTLP endpoint for traces/metrics. | ❌ No | `https://otel-collector.example.com:4318` |
| `OTEL_SERVICE_NAME_API` | OpenTelemetry service name for API. | ❌ No (default: `otto-api`) | `otto-api` |
| `OTEL_SERVICE_NAME_WORKER` | OpenTelemetry service name for workers. | ❌ No (default: `otto-worker`) | `otto-worker` |

**Notes**:
- Sentry is highly recommended for production error tracking
- OpenTelemetry is optional but useful for distributed tracing

---

## Application Configuration

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `ENVIRONMENT` | Environment name (development, staging, production). | ⚠️ **Recommended** | `production` |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins. | ✅ **Yes** | `https://app.otto.ai,https://staging.otto.ai` |
| `PORT` | Port for web server (Railway sets automatically). | ❌ No (default: `8080`) | `8080` |

**Notes**:
- `ENVIRONMENT=production` triggers stricter validation
- `ALLOWED_ORIGINS` must include all frontend URLs that will call the API
- Railway automatically sets `PORT` - don't override

---

## Rate Limiting Configuration

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `RATE_LIMIT_USER` | Per-user rate limit. | ❌ No (default: `60/minute`) | `60/minute` |
| `RATE_LIMIT_TENANT` | Per-tenant rate limit. | ❌ No (default: `600/minute`) | `600/minute` |

**Notes**:
- Format: `{number}/{unit}` (e.g., `60/minute`, `1000/hour`)
- Requires Redis if rate limiting is enabled

---

## Idempotency Configuration

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `IDEMPOTENCY_TTL_DAYS` | Days to keep idempotency keys in database. | ❌ No (default: `90`) | `90` |

**Notes**:
- Controls how long idempotency keys are retained
- Used for preventing duplicate operations

---

## Development / Testing

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `DEV_MODE` | Enable development mode (relaxes validations). | ❌ No (default: `false`) | `false` |
| `DEV_EMIT_KEY` | Key for emitting test events. | ❌ No | `dev_test_key` |
| `DEV_TEST_COMPANY_ID` | Test company ID for development. | ❌ No | `dev-test-company` |
| `DEV_TEST_USER_ID` | Test user ID for development. | ❌ No | `dev-test-user` |

**Notes**:
- **Never set these in production**
- Used for local development and testing only

---

## Internal AI API

| Variable | Usage | Required (Prod) | Example Value |
|----------|-------|-----------------|---------------|
| `AI_INTERNAL_TOKEN` | Token for internal AI API authentication. | ⚠️ **Conditional** (if using internal AI endpoints) | `internal_token_abc123...` |

**Notes**:
- Used for authenticating internal AI API calls
- Not required for standard CSR/dashboard operations

---

## Summary by Environment

### Production (Required)

**Core**:
- `DATABASE_URL`
- `REDIS_URL` or `UPSTASH_REDIS_URL` (if Celery/rate limiting enabled)
- `CLERK_SECRET_KEY`
- `ALLOWED_ORIGINS`

**External Services**:
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`
- `CALLRAIL_API_KEY`, `CALLRAIL_ACCOUNT_ID`
- `DEEPGRAM_API_KEY`
- `OPENAI_API_KEY`
- `BLAND_API_KEY`

**Feature Flags**:
- `ENABLE_CELERY=true`
- `ENABLE_CELERY_BEAT=true`

**Shunya/UWC** (if enabled):
- `UWC_API_KEY`
- `UWC_HMAC_SECRET` (if receiving webhooks)

**S3** (if using):
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET`

---

### Staging

Same as production, but:
- May use staging S3 bucket (`otto-documents-staging`)
- May use `USE_UWC_STAGING=true`
- May use staging API keys for external services

---

### Local Development

**Minimum**:
- `DATABASE_URL` (or use SQLite default)
- `CLERK_SECRET_KEY` (or disable auth for testing)
- `REDIS_URL` (if testing Celery/rate limiting)

**Optional**:
- All external service keys (can use placeholders if features disabled)
- Feature flags can be `false` to disable features

---

## Validation

The application validates environment variables on startup:

1. **Production checks**: In `ENVIRONMENT=production`, validates that required secrets are not placeholders
2. **Redis requirement**: If `ENABLE_CELERY=true` or rate limiting enabled, `REDIS_URL` or `UPSTASH_REDIS_URL` must be set
3. **Feature flags**: Feature flags default to safe values (disabled) if not set

---

## See Also

- `docs/infra/RAILWAY_SETUP.md` - Railway deployment guide
- `docs/infra/DEPLOYMENT_CHECKLIST.md` - Deployment checklist
- `app/config.py` - Source code for all environment variable definitions


