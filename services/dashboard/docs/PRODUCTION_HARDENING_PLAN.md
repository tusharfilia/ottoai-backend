# Production Hardening Plan

**Date**: 2025-01-20  
**Status**: Audit Complete - Implementation In Progress  
**Purpose**: Identify and fix production-grade readiness gaps for scalability, idempotency, multi-tenancy, concurrency safety, reliability, and observability.

---

## Executive Summary

This document provides a comprehensive audit of the Otto backend codebase for production readiness. It identifies gaps across six critical areas and proposes a prioritized patch plan with minimal, incremental changes.

**Key Findings**:
- ✅ **Strong Foundation**: Idempotency exists for webhooks, Shunya job processing has output hash deduplication
- ⚠️ **Race Conditions**: Webhook vs polling duplication risk, recording session start/stop races, appointment assignment races
- ⚠️ **Idempotency Gaps**: Missing idempotency keys for write endpoints (recording sessions, appointment assignment)
- ⚠️ **Multi-Tenancy**: Tenant scoping exists but needs hardening tests
- ⚠️ **Observability**: Metrics exist but missing Shunya failure counters and webhook dedupe metrics
- ⚠️ **Queue Backpressure**: Basic retry policies exist, but no DLQ strategy

---

## A) Concurrency & Race Conditions

### A1. Webhook vs Polling Duplication ⚠️ **P0**

**Issue**: Both webhook (`/api/v1/shunya/webhook`) and polling task (`poll_shunya_job_status`) can process the same Shunya job, leading to duplicate processing.

**Current State**:
- ✅ Idempotency check exists: `shunya_job_service.should_process()` uses `processed_output_hash`
- ⚠️ **Race Condition**: Both webhook and polling can pass idempotency check simultaneously before either commits

**Risk**: 
- Duplicate call analysis processing
- Duplicate lead/appointment updates
- Data inconsistency

**Location**:
- `app/routes/shunya_webhook.py:234-240` (webhook idempotency check)
- `app/tasks/shunya_job_polling_tasks.py:123-129` (polling idempotency check)

**Fix Required**: Distributed lock around job processing
- Lock key: `shunya_job:{job_id}`
- Acquire lock before idempotency check
- Release lock after commit

**Files to Change**:
- `app/routes/shunya_webhook.py` - Add distributed lock around processing
- `app/tasks/shunya_job_polling_tasks.py` - Add distributed lock around processing
- `app/services/redis_lock_service.py` - Already exists, use it

---

### A2. Recording Session Start/Stop Duplicates ⚠️ **P0**

**Issue**: Multiple concurrent requests to start/stop recording sessions can create duplicates.

**Current State**:
- ✅ Check exists: `RecordingSessionService.start_session()` checks for existing sessions
- ⚠️ **Race Condition**: Two requests can both pass the check before either commits

**Risk**:
- Duplicate recording sessions for same appointment
- Multiple Shunya analysis jobs for same session
- Wasted resources

**Location**:
- `app/services/recording_session_service.py:83-92` (start session check)
- `app/routes/recordings.py:46-107` (start endpoint)
- `app/routes/recording_sessions.py:54-203` (start endpoint)

**Fix Required**: 
1. Add distributed lock: `recording_session:start:{appointment_id}`
2. Add idempotency key to start/stop endpoints
3. Database unique constraint: `(appointment_id, company_id, status) WHERE status IN ('pending', 'recording')`

**Files to Change**:
- `app/services/recording_session_service.py` - Add lock + idempotency
- `app/routes/recordings.py` - Add idempotency key extraction
- `app/routes/recording_sessions.py` - Add idempotency key extraction
- Database migration: Add partial unique index

---

### A3. Appointment Assignment Duplicates ⚠️ **P0**

**Issue**: Concurrent assignment requests can assign same appointment to different reps or create duplicate assignments.

**Current State**:
- ✅ Double-booking check exists: `AppointmentDispatchService.assign_appointment_to_rep()` checks for overlaps
- ⚠️ **Race Condition**: Two requests can both pass the check before either commits

**Risk**:
- Same appointment assigned to multiple reps
- Double-booking conflicts
- Customer confusion

**Location**:
- `app/services/appointment_dispatch_service.py:93-116` (double-booking check)
- `app/routes/appointments.py:922-983` (assign endpoint)

**Fix Required**:
1. Add distributed lock: `appointment:assign:{appointment_id}`
2. Add idempotency key to assignment endpoint
3. Database unique constraint: `(appointment_id, company_id)` with status check

**Files to Change**:
- `app/services/appointment_dispatch_service.py` - Add lock + idempotency
- `app/routes/appointments.py` - Add idempotency key extraction

---

### A4. Repeated Task Enqueues ⚠️ **P1**

**Issue**: Celery tasks can be enqueued multiple times for the same work item.

**Current State**:
- ✅ Basic retry policies exist in Celery config
- ⚠️ No idempotency for task enqueueing
- ⚠️ No deduplication of task arguments

**Risk**:
- Duplicate Shunya analysis jobs
- Duplicate document indexing
- Wasted compute

**Location**:
- `app/tasks/shunya_job_polling_tasks.py` - Task enqueueing
- `app/tasks/recording_session_tasks.py` - Task enqueueing
- `app/tasks/onboarding_tasks.py` - Task enqueueing

**Fix Required**: Task-level idempotency using Redis
- Store task signature hash in Redis with TTL
- Check before enqueueing
- Use Celery's `task_id` for deduplication

**Files to Change**:
- `app/services/celery_tasks.py` - Add task idempotency helper
- All task files - Use idempotency helper

---

## B) Idempotency

### B1. Write Endpoints Missing Idempotency Keys ⚠️ **P0**

**Issue**: Critical write endpoints don't accept or use idempotency keys.

**Current State**:
- ✅ Webhook idempotency exists: `app/services/idempotency.py`
- ✅ Shunya job idempotency exists: `processed_output_hash`
- ❌ **Missing**: Recording session start/stop, appointment assignment

**Endpoints Requiring Idempotency**:

| Endpoint | Method | Current State | Priority |
|----------|--------|---------------|----------|
| `/api/v1/recordings/sessions/start` | POST | ❌ No idempotency | **P0** |
| `/api/v1/recordings/sessions/{id}/stop` | POST | ❌ No idempotency | **P0** |
| `/api/v1/appointments/{id}/assign` | POST | ❌ No idempotency | **P0** |
| `/api/v1/recordings/start` | POST | ❌ No idempotency | **P1** |
| `/api/v1/recordings/{id}/stop` | POST | ❌ No idempotency | **P1** |

**Fix Required**:
1. Add `Idempotency-Key` header support to endpoints
2. Store idempotency keys in database with response caching
3. Return cached response for duplicate requests

**Files to Change**:
- `app/routes/recordings.py` - Add idempotency key extraction
- `app/routes/recording_sessions.py` - Add idempotency key extraction
- `app/routes/appointments.py` - Add idempotency key extraction
- `app/services/idempotency.py` - Extend to support write endpoints

---

### B2. Task Idempotency Patterns ⚠️ **P1**

**Issue**: Celery tasks don't have consistent idempotency patterns.

**Current State**:
- ✅ Some tasks check for existing records (e.g., `task_exists_by_unique_key`)
- ⚠️ Inconsistent patterns across tasks
- ⚠️ No centralized task idempotency service

**Fix Required**: Create `TaskIdempotencyService`
- Store task signature hash in Redis
- Check before task execution
- TTL-based cleanup

**Files to Change**:
- `app/services/task_idempotency_service.py` - New service
- All task files - Use service

---

### B3. DB Uniqueness Constraints ⚠️ **P1**

**Issue**: Missing database-level uniqueness constraints for natural keys.

**Current State**:
- ✅ Some unique indexes exist (e.g., `ix_tasks_unique_key`)
- ⚠️ Missing constraints for:
  - Recording sessions (active sessions per appointment)
  - Appointment assignments (prevent duplicate assignments)
  - Shunya jobs (prevent duplicate job creation)

**Fix Required**: Add partial unique indexes

```sql
-- Recording sessions: Only one active session per appointment
CREATE UNIQUE INDEX idx_recording_sessions_active_appointment 
ON recording_sessions (appointment_id, company_id) 
WHERE status IN ('pending', 'recording');

-- Shunya jobs: Prevent duplicate job creation (if needed)
CREATE UNIQUE INDEX idx_shunya_jobs_unique 
ON shunya_jobs (shunya_job_id, company_id) 
WHERE shunya_job_id IS NOT NULL;
```

**Files to Change**:
- Database migration: Add unique constraints

---

## C) Queue & Backpressure

### C1. Retry Policies + Jitter ⚠️ **P1**

**Current State**:
- ✅ Basic retry config exists: `task_default_retry_delay=60`, `task_retry_jitter=True`
- ⚠️ Fixed retry delays (no exponential backoff for all tasks)
- ⚠️ No per-tenant rate limiting

**Fix Required**:
1. Implement exponential backoff with jitter for all tasks
2. Add per-tenant rate limiting using Redis
3. Add retry budget per tenant

**Files to Change**:
- `app/celery_app.py` - Enhance retry config
- `app/services/rate_limiter.py` - New service for per-tenant rate limiting

---

### C2. DLQ or Failure Quarantine Strategy ⚠️ **P1**

**Issue**: Failed tasks are retried indefinitely or dropped silently.

**Current State**:
- ✅ `max_retries=3` for some tasks
- ❌ No dead letter queue
- ❌ No failure quarantine
- ❌ No alerting for persistent failures

**Fix Required**:
1. Create DLQ table for failed tasks
2. Move tasks to DLQ after max retries
3. Alert on DLQ growth
4. Manual retry endpoint for DLQ items

**Files to Change**:
- `app/models/dead_letter_queue.py` - New model
- `app/services/dlq_service.py` - New service
- `app/tasks/*` - Use DLQ service

---

### C3. Per-Tenant Rate Limiting ⚠️ **P2**

**Issue**: No rate limiting per tenant, allowing one tenant to overwhelm the system.

**Current State**:
- ❌ No rate limiting implementation
- ⚠️ Redis exists but not used for rate limiting

**Fix Required**:
1. Implement Redis-based rate limiter
2. Per-tenant limits for:
   - API requests (requests/minute)
   - Shunya API calls (calls/minute)
   - Task enqueueing (tasks/minute)

**Files to Change**:
- `app/services/rate_limiter.py` - New service
- `app/middleware/rate_limit_middleware.py` - New middleware

---

## D) Multi-Tenancy Hardening

### D1. Tenant Isolation Tests ⚠️ **P0**

**Issue**: No comprehensive tests ensuring tenant isolation.

**Current State**:
- ✅ Tenant scoping exists: `TenantScopedSession` in `app/database.py`
- ✅ Most queries filter by `company_id`
- ❌ **Missing**: Comprehensive tenant isolation tests

**Risk**: Cross-tenant data leakage

**Fix Required**: Create tenant isolation test suite
- Test that queries from tenant A don't return tenant B data
- Test that updates from tenant A don't affect tenant B
- Test that deletes from tenant A don't affect tenant B
- Test cross-tenant ID access attempts

**Files to Change**:
- `app/tests/test_tenant_isolation.py` - New test file (P0)
- All route tests - Add tenant isolation assertions

---

### D2. Guardrails Against Cross-Tenant Access by ID ⚠️ **P0**

**Issue**: Endpoints accept resource IDs without verifying tenant ownership.

**Current State**:
- ✅ Most endpoints use `get_tenant_id()` dependency
- ⚠️ Some endpoints may not verify tenant ownership before access
- ⚠️ No centralized tenant ownership verification

**Risk**: Tenant A can access Tenant B's data by guessing IDs

**Fix Required**: 
1. Create `verify_tenant_ownership()` helper
2. Use in all endpoints that accept resource IDs
3. Return 404 (not 403) to prevent ID enumeration

**Files to Change**:
- `app/core/tenant.py` - Add ownership verification helper
- All route files - Use helper for ID-based access

---

## E) Observability

### E1. Structured Logs with Trace ID Propagation ⚠️ **P1**

**Current State**:
- ✅ `trace_id` exists in request state
- ✅ Some logging includes `trace_id`
- ⚠️ Inconsistent trace ID propagation to Celery tasks
- ⚠️ Missing trace ID in some log statements

**Fix Required**:
1. Ensure all log statements include `trace_id`
2. Propagate `trace_id` to Celery tasks via task context
3. Add trace ID to all error logs

**Files to Change**:
- `app/obs/logging.py` - Enhance trace ID propagation
- All route files - Ensure trace ID in logs
- All task files - Extract trace ID from context

---

### E2. Prometheus Metrics ⚠️ **P0**

**Current State**:
- ✅ Metrics exist: `app/obs/metrics.py`
- ✅ UWC metrics exist: `uwc_requests_total`, `uwc_request_duration_ms`
- ❌ **Missing**: Shunya failure counters
- ❌ **Missing**: Webhook dedupe metrics

**Missing Metrics** (P0):
1. `shunya_job_failures_total` - Counter for Shunya job failures by type
2. `shunya_api_errors_total` - Counter for Shunya API errors by endpoint
3. `webhook_dedupe_hits_total` - Counter for webhook deduplication hits
4. `webhook_dedupe_misses_total` - Counter for webhook deduplication misses

**Fix Required**:
1. Add missing metrics to `app/obs/metrics.py`
2. Instrument Shunya client with failure metrics
3. Instrument webhook handlers with dedupe metrics

**Files to Change**:
- `app/obs/metrics.py` - Add missing metrics
- `app/services/uwc_client.py` - Add failure metrics
- `app/routes/shunya_webhook.py` - Add dedupe metrics
- `app/services/idempotency.py` - Add dedupe metrics

---

### E3. Queue Depth Metrics ⚠️ **P1**

**Issue**: No visibility into Celery queue depths.

**Current State**:
- ❌ No queue depth metrics
- ⚠️ Redis exists but not instrumented for queue depth

**Fix Required**: Add queue depth gauges
- `celery_queue_depth` - Gauge for each queue
- `celery_active_tasks` - Gauge for active tasks per queue

**Files to Change**:
- `app/obs/metrics.py` - Add queue depth metrics
- `app/services/celery_monitor.py` - New service to poll queue depths

---

### E4. DB Pool Metrics ⚠️ **P1**

**Issue**: No visibility into database connection pool health.

**Current State**:
- ✅ Pool config exists: `pool_size=20`, `max_overflow=40`
- ❌ No metrics for pool utilization

**Fix Required**: Add DB pool metrics
- `db_pool_size` - Gauge for pool size
- `db_pool_active` - Gauge for active connections
- `db_pool_idle` - Gauge for idle connections
- `db_pool_overflow` - Gauge for overflow connections

**Files to Change**:
- `app/obs/metrics.py` - Add DB pool metrics
- `app/database.py` - Instrument pool stats

---

### E5. Recommended Alerts/SLOs ⚠️ **P2**

**Recommended Alerts**:

| Alert | Condition | Severity | SLO Target |
|-------|-----------|----------|------------|
| High Error Rate | >5% errors for 2min | Critical | <1% errors |
| High Latency | P95 >500ms for 2min | Warning | P95 <200ms |
| Shunya API Failures | >10 failures/min | Critical | <1% failure rate |
| Webhook Dedupe Miss | Dedupe miss rate >10% | Warning | <5% miss rate |
| Queue Depth | Queue depth >1000 | Warning | <500 tasks |
| DB Pool Exhaustion | Pool active = max | Critical | <80% utilization |

**Files to Change**:
- `grafana/alerts/alerts.yaml` - Add alert rules

---

## F) Data Lifecycle & Compliance

### F1. Retention Defaults ⚠️ **P2**

**Issue**: No default retention policies for data.

**Current State**:
- ⚠️ Some retention logic exists (e.g., Ghost Mode retention)
- ❌ No company-level retention policies
- ❌ No automated cleanup

**Fix Required**:
1. Add retention policy model
2. Default retention: 90 days for calls, 365 days for appointments
3. Automated cleanup task

**Files to Change**:
- `app/models/retention_policy.py` - New model
- `app/tasks/cleanup_tasks.py` - Add retention cleanup

---

### F2. Deletion Flows ⚠️ **P2**

**Issue**: No comprehensive deletion flows for GDPR compliance.

**Current State**:
- ✅ Soft deletes exist for some models
- ❌ No hard delete flows
- ❌ No cascade deletion
- ❌ No audit trail for deletions

**Fix Required**:
1. Implement hard delete flows
2. Cascade deletion (with confirmation)
3. Audit trail for all deletions

**Files to Change**:
- `app/services/deletion_service.py` - New service
- `app/routes/gdpr.py` - Enhance deletion endpoints

---

### F3. Consent Evidence Storage Checks ⚠️ **P2**

**Issue**: No verification that consent evidence is stored before processing.

**Current State**:
- ❌ No consent tracking
- ❌ No consent evidence storage

**Fix Required**:
1. Add consent model
2. Store consent evidence (timestamp, IP, user agent)
3. Check consent before processing

**Files to Change**:
- `app/models/consent.py` - New model
- `app/services/consent_service.py` - New service

---

## Risk Register

| Risk ID | Risk Description | Severity | Likelihood | Impact | Mitigation | Status |
|---------|------------------|----------|------------|--------|------------|--------|
| R1 | Webhook vs polling duplication | **HIGH** | Medium | High | Distributed lock (P0) | 🔴 Open |
| R2 | Recording session start/stop races | **HIGH** | Medium | Medium | Lock + idempotency (P0) | 🔴 Open |
| R3 | Appointment assignment races | **HIGH** | Medium | High | Lock + idempotency (P0) | 🔴 Open |
| R4 | Cross-tenant data leakage | **CRITICAL** | Low | Critical | Tenant isolation tests (P0) | 🔴 Open |
| R5 | Missing idempotency keys | **MEDIUM** | High | Medium | Add idempotency (P0) | 🔴 Open |
| R6 | Shunya API failures not tracked | **MEDIUM** | Medium | Medium | Add metrics (P0) | 🔴 Open |
| R7 | Queue backpressure | **MEDIUM** | Low | High | DLQ + rate limiting (P1) | 🟡 Planned |
| R8 | No data retention | **LOW** | Low | Low | Retention policies (P2) | 🟢 Deferred |

---

## Prioritized Task List

### P0 - Critical (Must Fix Before Production)

1. ✅ **Distributed lock for webhook/poll processing** (R1)
   - Files: `app/routes/shunya_webhook.py`, `app/tasks/shunya_job_polling_tasks.py`
   - Tests: `app/tests/test_shunya_job_locking.py`

2. ✅ **Idempotency for recording sessions** (R2)
   - Files: `app/services/recording_session_service.py`, `app/routes/recordings.py`
   - Tests: `app/tests/test_recording_session_idempotency.py`

3. ✅ **Idempotency for appointment assignment** (R3)
   - Files: `app/services/appointment_dispatch_service.py`, `app/routes/appointments.py`
   - Tests: `app/tests/test_appointment_assignment_idempotency.py`

4. ✅ **Tenant isolation test scaffolding** (R4)
   - Files: `app/tests/test_tenant_isolation.py`
   - Tests: Comprehensive tenant isolation test suite

5. ✅ **Basic metrics counters for Shunya failures + webhook dedupe** (R6)
   - Files: `app/obs/metrics.py`, `app/services/uwc_client.py`, `app/routes/shunya_webhook.py`
   - Tests: `app/tests/test_metrics.py`

### P1 - Important (Fix Soon)

6. Task idempotency patterns
7. DB uniqueness constraints
8. Retry policies + jitter
9. DLQ strategy
10. Structured logs with trace ID
11. Queue depth metrics
12. DB pool metrics

### P2 - Nice to Have

13. Per-tenant rate limiting
14. Retention defaults
15. Deletion flows
16. Consent evidence storage
17. Recommended alerts/SLOs

---

## File-Level Change List

### P0 Changes

**New Files**:
- `app/tests/test_shunya_job_locking.py`
- `app/tests/test_recording_session_idempotency.py`
- `app/tests/test_appointment_assignment_idempotency.py`
- `app/tests/test_tenant_isolation.py`
- `app/tests/test_metrics.py`

**Modified Files**:
- `app/routes/shunya_webhook.py` - Add distributed lock
- `app/tasks/shunya_job_polling_tasks.py` - Add distributed lock
- `app/services/recording_session_service.py` - Add lock + idempotency
- `app/routes/recordings.py` - Add idempotency key extraction
- `app/routes/recording_sessions.py` - Add idempotency key extraction
- `app/services/appointment_dispatch_service.py` - Add lock + idempotency
- `app/routes/appointments.py` - Add idempotency key extraction
- `app/obs/metrics.py` - Add Shunya failure + webhook dedupe metrics
- `app/services/uwc_client.py` - Instrument with failure metrics
- `app/services/idempotency.py` - Add dedupe metrics
- `app/core/tenant.py` - Add tenant ownership verification helper

**Database Migrations**:
- Add partial unique index for recording sessions
- Add idempotency_keys table extension (if needed)

---

## Implementation Notes

### Constraints

1. **Do NOT infer Shunya semantics** - Only use stored Shunya-normalized fields
2. **Preserve API contracts** - Only add nullable fields if needed
3. **Ensure tenant-scoped** - All changes must be tenant-safe
4. **Minimal changes** - Only fix what's broken, don't refactor

### Testing Strategy

1. **Unit Tests**: Test locking, idempotency, tenant isolation
2. **Integration Tests**: Test end-to-end flows with locks
3. **Load Tests**: Test concurrent requests to verify race condition fixes

---

**Last Updated**: 2025-01-20  
**Next Review**: After P0 implementation



