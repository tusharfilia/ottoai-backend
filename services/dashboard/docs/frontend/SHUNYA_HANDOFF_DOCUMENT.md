# Shunya ↔ Otto Integration Handoff Document

**Document Version**: 2.0  
**Last Updated**: 2025-01-XX  
**Intended Audience**: Shunya Infrastructure / Backend Engineering Team  
**Purpose**: Definitive engineering guide for machine-to-machine backend integration between Otto and Shunya

---

## Table of Contents

1. [End-to-End Architecture Diagram](#1-end-to-end-architecture-diagram)
2. [Otto ↔ Shunya Integration Responsibilities](#2-otto--shunya-integration-responsibilities)
3. [Trigger → Request → Processing → Persistence → Frontend Flow](#3-trigger--request--processing--persistence--frontend-flow)
4. [Otto → Shunya API Calls](#4-otto--shunya-api-calls)
5. [Shunya Error Envelope → Otto Error Normalization Flow](#5-shunya-error-envelope--otto-error-normalization-flow)
6. [Payload Contracts](#6-payload-contracts)
7. [Multi-Tenant Rules](#7-multi-tenant-rules)
8. [Webhook Contract](#8-webhook-contract)
9. [Retry, Failure, and Degraded Mode Behavior](#9-retry-failure-and-degraded-mode-behavior)
10. [Data Storage Expectations](#10-data-storage-expectations)
11. [Performance Expectations](#11-performance-expectations)
12. [Open Questions for Shunya](#12-open-questions-for-shunya)
13. [Shunya Confirmation Checklist](#13-shunya-confirmation-checklist)

---

## 1. End-to-End Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           OTTO BACKEND                                   │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    Trigger Points                                │    │
│  │  ┌──────────────────┐         ┌──────────────────────────┐     │    │
│  │  │ CallRail Webhook  │         │ Recording Session Upload │     │    │
│  │  │ POST /webhooks/   │         │ POST /recording-sessions │     │    │
│  │  │ callrail/call.    │         │ /{id}/upload-audio       │     │    │
│  │  │ completed         │         │                          │     │    │
│  │  └────────┬──────────┘         └──────────┬───────────────┘     │    │
│  │           │                                │                     │    │
│  │           └────────────┬───────────────────┘                     │    │
│  │                        │                                           │    │
│  │                        ▼                                           │    │
│  │            ┌──────────────────────────┐                           │    │
│  │            │ ShunyaAsyncJobService    │                           │    │
│  │            │ - submit_csr_call_job()  │                           │    │
│  │            │ - submit_sales_visit_job │                           │    │
│  │            └──────────┬───────────────┘                           │    │
│  │                       │                                             │    │
│  │                       ▼                                             │    │
│  │            ┌──────────────────────────┐                           │    │
│  │            │ ShunyaJob (Database)     │                           │    │
│  │            │ - job_type: csr_call     │                           │    │
│  │            │ - job_status: pending    │                           │    │
│  │            │ - company_id: tenant     │                           │    │
│  │            └──────────┬───────────────┘                           │    │
│  └───────────────────────┼───────────────────────────────────────────┘    │
│                          │                                                 │
│                          ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              Background Workers (Celery)                        │    │
│  │  ┌──────────────────────────────────────────────────────────┐   │    │
│  │  │ ShunyaIntegrationService                                 │   │    │
│  │  │ - process_csr_call()                                     │   │    │
│  │  │ - process_sales_visit()                                  │   │    │
│  │  └──────────┬───────────────────────────────────────────────┘   │    │
│  │             │                                                     │    │
│  │             ▼                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────┐   │    │
│  │  │ UWCClient (HTTP Client)                                  │   │    │
│  │  │ - JWT Generation (HS256, 5min TTL)                      │   │    │
│  │  │ - HMAC Signature (optional)                              │   │    │
│  │  │ - Retry Logic (exponential backoff)                     │   │    │
│  │  │ - Circuit Breaker (5 failures → 30s cooldown)           │   │    │
│  │  └──────────┬───────────────────────────────────────────────┘   │    │
│  └──────────────┼───────────────────────────────────────────────────┘    │
└─────────────────┼─────────────────────────────────────────────────────────┘
                  │
                  │ HTTPS (Public Internet)
                  │ Headers: Authorization, X-Company-ID, X-Request-ID
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        SHUNYA API (UWC)                                 │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    API Endpoints                                │    │
│  │                                                                 │    │
│  │  POST /api/v1/transcription/transcribe                         │    │
│  │  GET  /api/v1/transcription/transcript/{call_id}                │    │
│  │  POST /api/v1/analysis/start/{call_id}                         │    │
│  │  GET  /api/v1/analysis/complete/{call_id}                      │    │
│  │  POST /api/v1/meeting-segmentation/analyze                     │    │
│  │  GET  /api/v1/meeting-segmentation/analysis/{call_id}         │    │
│  │                                                                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              Async Processing (Shunya Internal)                 │    │
│  │  - ASR Transcription                                            │    │
│  │  - NLU Analysis                                                  │    │
│  │  - Meeting Segmentation                                          │    │
│  └──────────┬──────────────────────────────────────────────────────┘    │
│             │                                                              │
│             ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              Webhook Delivery                                   │    │
│  │  POST /api/v1/shunya/webhook (Otto endpoint)                   │    │
│  │  Headers: X-Shunya-Signature, X-Shunya-Timestamp               │    │
│  │  Payload: {shunya_job_id, status, result, company_id}          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                  │
                  │ HTTPS (Public Internet)
                  │ HMAC-SHA256 Signature Verification
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           OTTO BACKEND                                   │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              Webhook Handler                                    │    │
│  │  app/routes/shunya_webhook.py::shunya_webhook()                 │    │
│  │  - Verify HMAC signature                                         │    │
│  │  - Validate timestamp (replay attack prevention)                 │    │
│  │  - Verify company_id (tenant isolation)                          │    │
│  │  - Check idempotency (ShunyaJob + output hash)                    │    │
│  └──────────┬───────────────────────────────────────────────────────┘    │
│             │                                                              │
│             ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              Response Normalization                             │    │
│  │  ShunyaResponseNormalizer                                        │    │
│  │  - normalize_complete_analysis()                                │    │
│  │  - normalize_meeting_segmentation()                              │    │
│  │  - normalize_transcript_response()                               │    │
│  └──────────┬───────────────────────────────────────────────────────┘    │
│             │                                                              │
│             ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              Domain Model Persistence                           │    │
│  │  - CallTranscript (transcript_text, speaker_labels)            │    │
│  │  - CallAnalysis (objections, compliance, sentiment)           │    │
│  │  - RecordingTranscript (sales visit transcripts)               │    │
│  │  - RecordingAnalysis (outcome, sentiment, compliance)          │    │
│  │  - Lead.status updates (qualified_booked, etc.)               │    │
│  │  - Appointment creation/outcome updates                         │    │
│  │  - Task creation (from pending_actions)                        │    │
│  └──────────┬───────────────────────────────────────────────────────┘    │
│             │                                                              │
│             ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              Event Emission                                     │    │
│  │  - call.transcribed                                             │    │
│  │  - call.analyzed                                                │    │
│  │  - lead.updated                                                 │    │
│  │  - appointment.outcome_updated                                  │    │
│  │  - shunya.job.succeeded                                         │    │
│  └──────────┬───────────────────────────────────────────────────────┘    │
│             │                                                              │
│             ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              Frontend Consumption                               │    │
│  │  GET /api/v1/calls/{call_id}/analysis                          │    │
│  │  GET /api/v1/recording-sessions/{session_id}                    │    │
│  │  GET /api/v1/appointments/{appointment_id}                      │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Otto ↔ Shunya Integration Responsibilities

### 2.1 Otto Responsibilities

**Authentication & Security:**
- Generate JWT tokens (HS256, 5-minute TTL) with `company_id` in claims
- Include `X-Company-ID` header in all requests for explicit tenant context
- Generate HMAC-SHA256 signatures for request payloads (optional, for additional security)
- Verify HMAC signatures on incoming webhooks
- Validate webhook timestamps to prevent replay attacks (max 5 minutes old)
- Enforce tenant isolation (verify `company_id` matches in webhook payloads)

**Request Management:**
- Generate unique `X-Request-ID` for correlation (UUID v4)
- Include `Idempotency-Key` header for mutating requests (POST/PUT/DELETE)
- Implement retry logic with exponential backoff (5s, 10s, 30s, 60s, 300s, max 3 retries)
- Implement circuit breaker (5 failures → 30s cooldown per endpoint per tenant)
- Handle timeouts (30 seconds default)

**Job Tracking:**
- Create `ShunyaJob` records before making API calls
- Track job status: `pending` → `running` → `succeeded` / `failed` / `timeout`
- Store normalized responses in `ShunyaJob.output_payload`
- Compute and store `processed_output_hash` (SHA256) for idempotency
- Implement idempotency checks (prevent duplicate processing)

**Response Normalization:**
- Normalize all Shunya responses via `ShunyaResponseNormalizer`
- Handle variations in field names (e.g., `transcript` vs `transcript_text`)
- Provide default values for missing/null fields
- Convert types (string → float, etc.)

**Data Persistence:**
- Store transcripts in `CallTranscript` / `RecordingTranscript` models
- Store analysis in `CallAnalysis` / `RecordingAnalysis` models
- Update domain models (Lead status, Appointment outcome)
- Create Tasks from `pending_actions`
- Trigger property intelligence when address extracted

**Error Handling:**
- Parse Shunya error envelopes (canonical format)
- Map Shunya errors to Otto error codes
- Retry on retryable errors (check `retryable` flag)
- Log all errors with correlation IDs

**Polling (Fallback):**
- Poll Shunya for job status if webhook not received
- Use exponential backoff for polling intervals
- Timeout jobs after 24 hours

### 2.2 Shunya Responsibilities

**Authentication & Security:**
- Verify JWT tokens (HS256, validate `company_id` claim)
- Validate `X-Company-ID` header matches JWT `company_id`
- Generate HMAC-SHA256 signatures for webhook payloads
- Include `X-Shunya-Timestamp` (epoch milliseconds) in webhooks
- Include `X-Shunya-Signature` (lowercase hex) in webhooks

**Request Processing:**
- Accept `X-Request-ID` for correlation
- Honor `Idempotency-Key` header (return same response for duplicate requests)
- Process requests asynchronously (return job/task ID immediately)
- Return canonical error envelopes with `retryable` flag

**Job Management:**
- Return unique `job_id` / `task_id` / `transcript_id` for async tracking
- Process jobs asynchronously (ASR, NLU, segmentation)
- Update job status (pending → running → completed/failed)
- Deliver webhooks reliably (at-least-once delivery)

**Response Format:**
- Return consistent response structures (per OpenAPI spec)
- Include all required fields (even if null)
- Use standardized field names (per contract)
- Include confidence scores where applicable

**Webhook Delivery:**
- Send webhook to `POST /api/v1/shunya/webhook` (Otto endpoint)
- Include `shunya_job_id` in payload (for correlation)
- Include `company_id` in payload (for tenant verification)
- Include `status` ("completed" or "failed")
- Include `result` (if completed) or `error` (if failed)
- Retry webhook delivery on failure (with exponential backoff)

**Error Handling:**
- Return canonical error envelopes:
  ```json
  {
    "success": false,
    "error": {
      "error_code": "INTERNAL_ERROR",
      "error_type": "server_error",
      "message": "Processing failed",
      "retryable": true,
      "details": {},
      "timestamp": "2025-01-15T10:00:00Z",
      "request_id": "uuid"
    }
  }
  ```
- Set `retryable: true` for transient errors (5xx, rate limits)
- Set `retryable: false` for permanent errors (4xx validation errors)

**Performance:**
- Process transcription within SLA (TBD)
- Process analysis within SLA (TBD)
- Handle concurrent requests per tenant (rate limiting)
- Support max audio file size (TBD)

---

## 3. Trigger → Request → Processing → Persistence → Frontend Flow

### 3.1 Flow 1: CSR Call (CallRail Webhook)

```
1. TRIGGER
   └─> CallRail webhook: POST /webhooks/callrail/call.completed
       └─> Payload: {recording_url, call_id, customer_phone, ...}
       └─> Handler: app/routes/enhanced_callrail.py::handle_call_completed()

2. JOB CREATION
   └─> ShunyaAsyncJobService.submit_csr_call_job()
       └─> Creates ShunyaJob record:
           - job_type: "csr_call"
           - job_status: "pending"
           - company_id: <tenant>
           - input_payload: {call_id, audio_url, call_type: "csr_call"}
       └─> Returns: ShunyaJob.id (UUID)

3. BACKGROUND PROCESSING (Celery Worker)
   └─> ShunyaIntegrationService.process_csr_call()
       └─> Step 3.1: Transcription
           └─> UWCClient.transcribe_audio()
               └─> POST /api/v1/transcription/transcribe
                   └─> Headers: Authorization (JWT), X-Company-ID, X-Request-ID
                   └─> Payload: {call_id, audio_url, call_type: "csr_call"}
                   └─> Response: {success: true, task_id, transcript_id}
           └─> Poll for completion (or wait for webhook)
               └─> GET /api/v1/transcription/transcript/{call_id}
                   └─> Response: {transcript_text, speaker_labels, confidence_score}
           └─> Normalize: ShunyaResponseNormalizer.normalize_transcript_response()
           └─> Persist: CallTranscript model
               - transcript_text
               - speaker_labels (JSON)
               - confidence_score
               - uwc_job_id

       └─> Step 3.2: Analysis
           └─> UWCClient.start_analysis()
               └─> POST /api/v1/analysis/start/{call_id}
                   └─> Response: {success: true, job_id}
           └─> Poll for completion (or wait for webhook)
               └─> GET /api/v1/analysis/complete/{call_id}
                   └─> Response: {qualification, objections, compliance, summary, sentiment_score, entities}
           └─> Normalize: ShunyaResponseNormalizer.normalize_complete_analysis()
           └─> Persist: CallAnalysis model
               - objections (JSON array)
               - sentiment_score (0.0-1.0)
               - sop_stages_completed (JSON array)
               - sop_stages_missed (JSON array)
               - sop_compliance_score (0-10)
               - lead_quality (string)

       └─> Step 3.3: Domain Updates
           └─> Update Lead.status based on qualification_status
               - "qualified_booked" → LeadStatus.QUALIFIED_BOOKED
               - "qualified_unbooked" → LeadStatus.QUALIFIED_UNBOOKED
               - "not_qualified" → LeadStatus.CLOSED_LOST
           └─> Create Appointment if "qualified_booked"
           └─> Create Tasks from pending_actions
           └─> Extract address from entities → trigger property intelligence
           └─> Create KeySignal entries for high-priority insights

       └─> Step 3.4: Events
           └─> emit("call.transcribed", {call_id, transcript_id, confidence_score})
           └─> emit("lead.updated", {lead_id, status, classification})
           └─> emit("appointment.created", {appointment_id, lead_id})

4. WEBHOOK (Alternative Path)
   └─> Shunya sends: POST /api/v1/shunya/webhook
       └─> Headers: X-Shunya-Signature, X-Shunya-Timestamp, X-Shunya-Task-Id
       └─> Payload: {shunya_job_id, status: "completed", result: {...}, company_id}
       └─> Handler: app/routes/shunya_webhook.py::shunya_webhook()
           └─> Verify HMAC signature
           └─> Validate timestamp (max 5 minutes old)
           └─> Look up ShunyaJob by shunya_job_id (tenant-scoped)
           └─> Verify company_id matches job.company_id
           └─> Check idempotency (processed_output_hash)
           └─> Normalize result
           └─> Persist to domain models (same as Step 3.3)
           └─> Emit events

5. FRONTEND CONSUMPTION
   └─> GET /api/v1/calls/{call_id}/analysis
       └─> Returns:
           {
             "status": "complete" | "not_analyzed" | "processing",
             "transcript": "...",
             "objections": [...],
             "sentiment_score": 0.7,
             "sop_stages_completed": [...],
             "sop_compliance_score": 8.5,
             "lead_quality": "qualified",
             "qualification": {
               "qualification_status": "qualified_booked",
               "bant_scores": {...}
             }
           }
```

### 3.2 Flow 2: Sales Visit (Recording Session Upload)

```
1. TRIGGER
   └─> Sales rep uploads audio: POST /api/v1/recording-sessions/{session_id}/upload-audio
       └─> Handler: app/routes/recording_sessions.py::upload_audio_complete()
       └─> Creates RecordingSession with audio_url

2. JOB CREATION
   └─> ShunyaAsyncJobService.submit_sales_visit_job()
       └─> Creates ShunyaJob record:
           - job_type: "sales_visit"
           - job_status: "pending"
           - company_id: <tenant>
           - recording_session_id: <session_id>
           - input_payload: {recording_session_id, audio_url, appointment_id}

3. BACKGROUND PROCESSING
   └─> ShunyaIntegrationService.process_sales_visit()
       └─> Step 3.1: Transcription (if not Ghost Mode)
           └─> UWCClient.transcribe_audio()
               └─> POST /api/v1/transcription/transcribe
               └─> Persist: RecordingTranscript model

       └─> Step 3.2: Meeting Segmentation
           └─> Find related call_id (from appointment.lead_id)
           └─> UWCClient.analyze_meeting_segmentation()
               └─> POST /api/v1/meeting-segmentation/analyze
                   └─> Payload: {call_id, analysis_type: "full"}
               └─> Response: {part1, part2, transition_point, segmentation_confidence}
           └─> Normalize: ShunyaResponseNormalizer.normalize_meeting_segmentation()

       └─> Step 3.3: Complete Analysis
           └─> UWCClient.get_complete_analysis()
               └─> GET /api/v1/analysis/complete/{call_id}
               └─> Response: {objections, compliance, outcome, sentiment_score}
           └─> Normalize: ShunyaResponseNormalizer.normalize_complete_analysis()
           └─> Merge segmentation + analysis

       └─> Step 3.4: Domain Updates
           └─> Persist: RecordingAnalysis model
               - outcome: "won" | "lost" | "pending" | "no_show"
               - sentiment_score
               - sop_compliance_score
           └─> Update Appointment.outcome
           └─> Update Lead.status (if WON/LOST)
           └─> Create Tasks from visit_actions

       └─> Step 3.5: Events
           └─> emit("recording_session.analyzed", {session_id, outcome})
           └─> emit("appointment.outcome_updated", {appointment_id, outcome})

4. FRONTEND CONSUMPTION
   └─> GET /api/v1/recording-sessions/{session_id}
       └─> Returns:
           {
             "transcript": "...",
             "analysis": {
               "outcome": "won",
               "sentiment_score": 0.8,
               "sop_compliance_score": 9.0,
               "part1": {...},
               "part2": {...}
             }
           }
```

---

## 4. Otto → Shunya API Calls

### 4.1 Endpoint 1: Transcription (ASR)

**Endpoint**: `POST /api/v1/transcription/transcribe`  
**Called From**: `app/services/uwc_client.py::transcribe_audio()`  
**Triggered By**: 
- `app/services/shunya_integration_service.py::process_csr_call()` (CSR calls)
- `app/services/shunya_integration_service.py::process_sales_visit()` (Sales visits)

**Request Headers:**
```http
Authorization: Bearer <JWT_TOKEN>
X-Company-ID: company_abc123
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
X-UWC-Version: v1
Content-Type: application/json
X-UWC-Timestamp: 2025-01-15T10:00:00.000Z
X-Signature: <HMAC_SHA256_HEX> (optional)
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
```

**Request Payload:**
```json
{
  "call_id": 12345,
  "audio_url": "https://s3.amazonaws.com/bucket/audio.mp3",
  "call_type": "csr_call",
  "language": "en-US",
  "model": "default"
}
```

**Response (Success):**
```json
{
  "success": true,
  "task_id": "shunya_task_12345",
  "transcript_id": 67890,
  "message": "Transcription job submitted"
}
```

**Response (Error - Canonical Envelope):**
```json
{
  "success": false,
  "error": {
    "error_code": "INVALID_AUDIO_URL",
    "error_type": "client_error",
    "message": "Audio URL is not accessible",
    "retryable": false,
    "details": {
      "audio_url": "https://s3.amazonaws.com/bucket/audio.mp3",
      "http_status": 404
    },
    "timestamp": "2025-01-15T10:00:00.000Z",
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Status Polling:**
- `GET /api/v1/transcription/status/{call_id}` - Check transcription status
- `GET /api/v1/transcription/transcript/{call_id}` - Get final transcript

**Transcript Response:**
```json
{
  "success": true,
  "call_id": 12345,
  "transcript_text": "Hello, this is John from ABC Company. How can I help you today?",
  "speaker_labels": [
    {
      "speaker": "rep",
      "text": "Hello, this is John from ABC Company. How can I help you today?",
      "start_time": 0.0,
      "end_time": 5.2
    },
    {
      "speaker": "customer",
      "text": "Hi, I need a quote for roof repair.",
      "start_time": 5.5,
      "end_time": 8.1
    }
  ],
  "confidence_score": 0.95,
  "language": "en-US",
  "word_count": 15
}
```

**Timeouts & Retries:**
- HTTP timeout: 30 seconds
- Max retries: 3 attempts
- Retry delays: 5s, 10s, 30s (exponential backoff)
- Circuit breaker: 5 failures → 30s cooldown (per endpoint per tenant)

**Error Codes Handled:**
- `401` / `403` → `UWCAuthenticationError` (no retry)
- `429` → `UWCRateLimitError` (retry with backoff)
- `5xx` → `UWCServerError` (retry if `retryable=true`)
- Timeout → `UWCClientError` (retry with backoff)

---

### 4.2 Endpoint 2: Start Analysis Pipeline

**Endpoint**: `POST /api/v1/analysis/start/{call_id}`  
**Called From**: `app/services/uwc_client.py::start_analysis()`  
**Triggered By**: `app/services/shunya_integration_service.py::process_csr_call()`

**Request Headers:** (Same as transcription)

**Request Payload:** (No body - `call_id` is in path)

**Response (Success):**
```json
{
  "success": true,
  "job_id": "shunya_job_12345",
  "message": "Analysis pipeline started"
}
```

**Status Polling:**
- `GET /api/v1/analysis/status/{call_id}` - Check analysis status per type
- `GET /api/v1/analysis/complete/{call_id}` - Get complete analysis results

**Timeouts & Retries:** (Same as transcription)

---

### 4.3 Endpoint 3: Get Complete Analysis

**Endpoint**: `GET /api/v1/analysis/complete/{call_id}`  
**Called From**: `app/services/uwc_client.py::get_complete_analysis()`  
**Triggered By**: 
- `app/services/shunya_integration_service.py::process_csr_call()` (after start_analysis)
- `app/routes/shunya_webhook.py::shunya_webhook()` (when webhook received)

**Request Headers:** (Same as transcription, no body)

**Response (Success - Normalized Structure):**
```json
{
  "success": true,
  "call_id": 12345,
  "qualification": {
    "qualification_status": "qualified_booked",
    "bant_scores": {
      "budget": 0.8,
      "authority": 0.7,
      "need": 0.9,
      "timeline": 0.6
    },
    "overall_score": 0.75,
    "confidence_score": 0.85,
    "decision_makers": ["John Smith"],
    "urgency_signals": ["immediate need", "roof leak"],
    "budget_indicators": ["$50k budget approved"]
  },
  "objections": {
    "objections": [
      {
        "objection_text": "That seems expensive",
        "category_id": 1,
        "category_text": "Pricing",
        "severity": "medium",
        "overcome": false,
        "timestamp": 45.5,
        "speaker_id": "SPEAKER_02",
        "response_suggestions": ["Discuss payment plans", "Highlight value proposition"],
        "confidence_score": 0.9
      }
    ],
    "total_objections": 1,
    "severity_breakdown": {
      "high": 0,
      "medium": 1,
      "low": 0
    }
  },
  "compliance": {
    "compliance_score": 8.5,
    "stages_followed": ["connect", "agenda", "assess"],
    "stages_missed": ["ask", "close"],
    "violations": [],
    "positive_behaviors": ["Active listening", "Empathy"],
    "recommendations": ["Ask for referral", "Set follow-up appointment"]
  },
  "summary": {
    "summary": "Customer called about roof repair. Urgent need identified. Budget approved. Appointment scheduled for next week.",
    "key_points": ["Urgent need", "Budget approved", "Appointment scheduled"],
    "action_items": ["Follow up in 24 hours", "Send quote via email"],
    "next_steps": ["Schedule inspection", "Prepare quote"],
    "confidence_score": 0.9
  },
  "sentiment_score": 0.7,
  "pending_actions": [
    {
      "action": "Send quote via email",
      "due_at": "2025-01-16T10:00:00Z",
      "priority": "high"
    }
  ],
  "missed_opportunities": [
    {
      "opportunity": "Did not ask for referral",
      "severity": "medium",
      "timestamp": 300.0
    }
  ],
  "entities": {
    "address": "123 Main St, City, State 12345",
    "appointment_date": "2025-01-20T14:00:00Z",
    "scheduled_time": "2025-01-20T14:00:00Z",
    "name": "John Smith",
    "phone": "+1234567890",
    "email": "john@example.com"
  },
  "job_id": "shunya_job_12345"
}
```

**Timeouts & Retries:** (Same as transcription)

---

### 4.4 Endpoint 4: Meeting Segmentation (Sales Visits)

**Endpoint**: `POST /api/v1/meeting-segmentation/analyze`  
**Called From**: `app/services/uwc_client.py::analyze_meeting_segmentation()`  
**Triggered By**: `app/services/shunya_integration_service.py::process_sales_visit()`

**Request Payload:**
```json
{
  "call_id": 12345,
  "analysis_type": "full"
}
```

**Response (Success - Normalized Structure):**
```json
{
  "success": true,
  "call_id": 12345,
  "part1": {
    "start_time": 0,
    "end_time": 240,
    "duration": 240,
    "content": "Rapport building, agenda setting, relationship establishment. Customer discussed their needs and concerns.",
    "key_points": ["Relationship building", "Agenda set", "Needs assessment"]
  },
  "part2": {
    "start_time": 240,
    "end_time": 420,
    "duration": 180,
    "content": "Proposal presentation, pricing discussion, closing. Customer agreed to move forward.",
    "key_points": ["Proposal presented", "Pricing discussed", "Deal closed"]
  },
  "segmentation_confidence": 0.8,
  "transition_point": 240,
  "transition_indicators": ["Let's talk about pricing", "Here's our proposal"],
  "meeting_structure_score": 4,
  "call_type": "sales_appointment",
  "outcome": "won",
  "created_at": "2025-01-15T10:00:00Z"
}
```

**Status Polling:**
- `GET /api/v1/meeting-segmentation/status/{call_id}` - Check status
- `GET /api/v1/meeting-segmentation/analysis/{call_id}` - Get full analysis

**Timeouts & Retries:** (Same as transcription)

---

### 4.5 Authentication Details

**JWT Token Generation:**
```python
# Algorithm: HS256
# TTL: 5 minutes
# Claims:
{
  "company_id": "company_abc123",
  "iat": 1705315200,
  "exp": 1705315500,  # iat + 300 seconds
  "iss": "otto-backend",
  "aud": "uwc"
}
# Secret: UWC_JWT_SECRET (environment variable)
```

**HMAC Signature (Optional, for Additional Security):**
```python
# Algorithm: HMAC-SHA256
# Message: "{timestamp}.{json_payload}" (sorted keys)
# Secret: UWC_HMAC_SECRET (environment variable)
# Digest: Lowercase hex string
```

**Headers Sent:**
```http
Authorization: Bearer <JWT_TOKEN>
X-Company-ID: company_abc123
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
X-UWC-Version: v1
Content-Type: application/json
X-UWC-Timestamp: 2025-01-15T10:00:00.000Z
X-Signature: <HMAC_SHA256_HEX> (if payload provided)
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000 (for POST/PUT/DELETE)
```

---

### 4.6 Idempotency Strategies

**Method 1: Idempotency-Key Header**
- Otto sends `Idempotency-Key: <request_id>` for mutating requests
- Shunya should return same response for duplicate `Idempotency-Key` values
- Shunya should store idempotency keys for at least 24 hours

**Method 2: Shunya Job ID Tracking**
- Otto stores `shunya_job_id` in `ShunyaJob` table
- Unique constraint: `(company_id, shunya_job_id)`
- Otto checks if `shunya_job_id` already exists before processing

**Method 3: Output Hash**
- Otto computes SHA256 hash of normalized output payload
- Stores in `ShunyaJob.processed_output_hash`
- Checks hash before persisting to domain models

**Method 4: Webhook Idempotency**
- Webhook handler checks `ShunyaJob.job_status == SUCCEEDED`
- Checks `processed_output_hash` matches
- Returns `{"status": "already_processed"}` if duplicate

---

## 5. Shunya Error Envelope → Otto Error Normalization Flow

### 5.1 Shunya Error Envelope Format

**Canonical Structure:**
```json
{
  "success": false,
  "error": {
    "error_code": "INTERNAL_ERROR",
    "error_type": "server_error",
    "message": "Processing failed due to internal error",
    "retryable": true,
    "details": {
      "component": "asr_engine",
      "error_id": "asr_12345"
    },
    "timestamp": "2025-01-15T10:00:00.000Z",
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Error Types:**
- `client_error`: 4xx errors (validation, bad request) - `retryable: false`
- `server_error`: 5xx errors (internal, timeout) - `retryable: true`
- `rate_limit_error`: 429 errors - `retryable: true`
- `authentication_error`: 401/403 errors - `retryable: false`

### 5.2 Otto Error Normalization

**Error Parsing:**
```python
# app/services/uwc_client.py::_parse_shunya_error_envelope()
error_code = error_obj.get("error_code") or "UNKNOWN_ERROR"
error_type = error_obj.get("error_type") or "unknown"
message = error_obj.get("message") or "Unknown error"
retryable = error_obj.get("retryable", False)
details = error_obj.get("details") or {}
timestamp = error_obj.get("timestamp")
request_id = error_obj.get("request_id")
```

**Exception Mapping:**
- `401` / `403` → `UWCAuthenticationError` (no retry)
- `429` → `UWCRateLimitError` (retry with backoff)
- `5xx` + `retryable: true` → `UWCServerError` (retry with backoff)
- `5xx` + `retryable: false` → `UWCServerError` (no retry)
- Timeout → `UWCClientError` (retry with backoff)

**Frontend Error Response (RFC-7807):**
```json
{
  "success": false,
  "error": {
    "error_code": "SHUNYA_API_ERROR",
    "error_type": "external_service_error",
    "message": "Shunya API request failed",
    "retryable": true,
    "details": {
      "shunya_error_code": "INTERNAL_ERROR",
      "shunya_request_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    "timestamp": "2025-01-15T10:00:00.000Z",
    "request_id": "660e8400-e29b-41d4-a716-446655440001"
  }
}
```

---

## 6. Payload Contracts

### 6.1 Transcript Fields

**Required Fields:**
- `transcript_text` (string): Full transcript text
- `call_id` (integer): Call ID

**Optional Fields:**
- `speaker_labels` (array): Speaker diarization segments
  ```json
  [
    {
      "speaker": "rep" | "customer",
      "text": "Hello, how can I help?",
      "start_time": 0.0,
      "end_time": 3.2
    }
  ]
  ```
- `confidence_score` (float, 0.0-1.0): ASR confidence
- `language` (string): Language code (default: "en-US")
- `word_count` (integer): Word count

**Field Name Variations (Handled by Normalizer):**
- `transcript` → `transcript_text`
- `speakers` → `speaker_labels`
- `diarization` → `speaker_labels`
- `confidence` → `confidence_score`

### 6.2 Segmentation Fields

**Required Fields:**
- `part1` (object): Rapport/Agenda phase
  ```json
  {
    "start_time": 0,
    "end_time": 240,
    "duration": 240,
    "content": "...",
    "key_points": [...]
  }
  ```
- `part2` (object): Proposal/Close phase
  ```json
  {
    "start_time": 240,
    "end_time": 420,
    "duration": 180,
    "content": "...",
    "key_points": [...]
  }
  ```

**Optional Fields:**
- `segmentation_confidence` (float, 0.0-1.0)
- `transition_point` (integer, seconds)
- `transition_indicators` (array of strings)
- `meeting_structure_score` (integer, 1-5)
- `call_type` (string): "sales_appointment"
- `outcome` (string): "won" | "lost" | "pending"

### 6.3 Objections

**Structure:**
```json
{
  "objections": [
    {
      "objection_text": "That seems expensive",
      "category_id": 1,
      "category_text": "Pricing",
      "severity": "high" | "medium" | "low",
      "overcome": false,
      "timestamp": 45.5,
      "speaker_id": "SPEAKER_02",
      "response_suggestions": ["Discuss payment plans"],
      "confidence_score": 0.9
    }
  ],
  "total_objections": 1,
  "severity_breakdown": {
    "high": 0,
    "medium": 1,
    "low": 0
  }
}
```

**Field Name Variations:**
- `objection` → `objection_text`
- `category` → `category_text`

### 6.4 Sentiment

**Field:** `sentiment_score` (float, 0.0-1.0)
- `0.0`: Very negative
- `0.5`: Neutral
- `1.0`: Very positive

**Field Name Variations:**
- `sentiment` → `sentiment_score`
- `sentiment_analysis.score` → `sentiment_score`

### 6.5 Coaching Tips

**Structure (in `compliance.recommendations` or `summary.action_items`):**
```json
[
  {
    "tip": "Set agenda earlier in conversation",
    "priority": "high" | "medium" | "low",
    "category": "sales_process",
    "timestamp": 5.2
  }
]
```

### 6.6 Confidence Scores

**All confidence scores:**
- Range: `0.0` to `1.0` (float)
- `null` if not available
- Field names: `confidence_score`, `confidence`, `segmentation_confidence`

### 6.7 Ordering Guarantees

**Speaker Labels:**
- Ordered by `start_time` (ascending)
- No gaps (consecutive segments)

**Objections:**
- Ordered by `timestamp` (ascending)
- May have same timestamp (multiple objections at once)

**Pending Actions:**
- Ordered by `due_at` (ascending, nulls last)
- Priority: `high` → `medium` → `low`

---

## 7. Multi-Tenant Rules

### 7.1 Tenant Tokens

**JWT Claims:**
```json
{
  "company_id": "company_abc123",
  "iat": 1705315200,
  "exp": 1705315500,
  "iss": "otto-backend",
  "aud": "uwc"
}
```

**Header:**
```http
X-Company-ID: company_abc123
```

**Shunya Responsibility:**
- Verify `company_id` in JWT matches `X-Company-ID` header
- Enforce tenant isolation (data scoping)
- Rate limit per tenant
- Track usage per tenant

### 7.2 Per-Tenant Secrets

**Otto Configuration:**
- `UWC_JWT_SECRET`: Shared secret for JWT signing (HS256)
- `UWC_HMAC_SECRET`: Shared secret for HMAC signatures
- `UWC_API_KEY`: Legacy API key (deprecated)

**Shunya Configuration:**
- Same `UWC_JWT_SECRET` for JWT verification
- Same `UWC_HMAC_SECRET` for webhook signatures
- Per-tenant secrets not currently used (shared secrets)

### 7.3 How Otto Scoping Works

**Database Queries:**
- All queries filter by `company_id` / `tenant_id`
- `CallTranscript.tenant_id = company_id`
- `CallAnalysis.tenant_id = company_id`
- `ShunyaJob.company_id = company_id`

**Middleware Enforcement:**
- `TenantContextMiddleware` extracts `company_id` from Clerk JWT
- Injects into request context
- All database queries automatically scoped

**Webhook Verification:**
- Webhook handler verifies `company_id` in payload matches `ShunyaJob.company_id`
- Rejects with `403` if mismatch (cross-tenant attack prevention)

---

## 8. Webhook Contract

### 8.1 Security (HMAC)

**Signature Generation (Shunya Side):**
```python
# Message: "{timestamp}.{raw_body_bytes}"
# Algorithm: HMAC-SHA256
# Secret: UWC_HMAC_SECRET
# Digest: Lowercase hex string

import hmac
import hashlib

timestamp_ms = str(int(time.time() * 1000))  # Epoch milliseconds
message = f"{timestamp_ms}.".encode('utf-8') + raw_body_bytes
signature = hmac.new(
    secret.encode('utf-8'),
    message,
    hashlib.sha256
).hexdigest().lower()
```

**Signature Verification (Otto Side):**
```python
# app/utils/shunya_webhook_security.py::verify_shunya_webhook_signature()
# 1. Check timestamp (max 5 minutes old)
# 2. Construct message: "{timestamp}.{raw_body_bytes}"
# 3. Compute expected signature
# 4. Constant-time comparison (prevent timing attacks)
```

### 8.2 Timestamp Rules

**Format:** Epoch milliseconds (string)
- Example: `"1705315200000"`
- Max age: 5 minutes (300 seconds)
- Reject if older (replay attack prevention)

### 8.3 Header Schemas

**Required Headers:**
```http
X-Shunya-Signature: a1b2c3d4e5f6... (HMAC-SHA256 hex, lowercase)
X-Shunya-Timestamp: 1705315200000 (epoch milliseconds, string)
X-Shunya-Task-Id: shunya_task_12345 (optional, for idempotency)
```

### 8.4 Examples of Valid/Invalid Signatures

**Valid Signature:**
```http
POST /api/v1/shunya/webhook HTTP/1.1
Host: otto-backend.example.com
X-Shunya-Signature: a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456
X-Shunya-Timestamp: 1705315200000
X-Shunya-Task-Id: shunya_task_12345
Content-Type: application/json

{
  "shunya_job_id": "shunya_job_12345",
  "status": "completed",
  "result": {...},
  "company_id": "company_abc123"
}
```

**Invalid Signature (Wrong Secret):**
```http
X-Shunya-Signature: wrong_signature_here...
# → 401 Unauthorized
```

**Invalid Signature (Expired Timestamp):**
```http
X-Shunya-Timestamp: 1705314900000  # 6 minutes ago
# → 401 Unauthorized (timestamp expired)
```

**Invalid Signature (Missing Header):**
```http
# Missing X-Shunya-Signature
# → 401 Unauthorized (missing required headers)
```

**Invalid Signature (Company ID Mismatch):**
```http
# Payload: {"company_id": "company_xyz789"}
# ShunyaJob.company_id: "company_abc123"
# → 403 Forbidden (company ID mismatch)
```

---

## 9. Retry, Failure, and Degraded Mode Behavior

### 9.1 Retry Logic

**Automatic Retries:**
- Max retries: 3 attempts
- Retry delays: 5s, 10s, 30s (exponential backoff)
- Retry on: 5xx errors (if `retryable=true`), 429 errors, timeouts
- No retry on: 401/403 errors, 4xx validation errors

**Circuit Breaker:**
- Threshold: 5 failures
- Cooldown: 30 seconds
- Scope: Per endpoint per tenant
- Implementation: `app/services/circuit_breaker.py`

**Job-Level Retries:**
- Max attempts: 5 (configurable per job)
- Retry delays: 5s, 10s, 30s, 60s, 300s (exponential backoff)
- Timeout: 24 hours from job creation
- Implementation: `app/services/shunya_job_service.py`

### 9.2 Failure Handling

**Transient Failures (Retryable):**
- 5xx errors with `retryable: true`
- 429 rate limit errors
- Timeout errors
- Network errors

**Permanent Failures (No Retry):**
- 401/403 authentication errors
- 4xx validation errors
- 5xx errors with `retryable: false`

**Job Status Transitions:**
```
pending → running → succeeded
                ↓
              failed → (retry) → pending
                ↓
              timeout (after 24h)
```

### 9.3 Degraded Mode Behavior

**If Transcription Fails:**
- Call is still stored
- `transcript_text` is empty
- Frontend shows "Transcript not available"
- Analysis is skipped (requires transcript)

**If Analysis Fails:**
- `CallAnalysis` is not created
- Frontend shows "Analysis not available" or "Processing..."
- Lead status is not updated
- Tasks are not created

**If Webhook Fails:**
- Polling worker will eventually fetch results
- If webhook never arrives, job times out after 24h
- Polling interval: exponential backoff (5s, 10s, 30s, 60s, 300s)

**Partial Data:**
- Otto does not surface partial/corrupted analysis
- If analysis is incomplete, job is marked as failed and retried
- Frontend handles missing fields gracefully (shows "N/A")

---

## 10. Data Storage Expectations

### 10.1 What Otto Stores

**CallTranscript:**
- `transcript_text` (full transcript)
- `speaker_labels` (diarization segments)
- `confidence_score` (ASR confidence)
- `uwc_job_id` (Shunya job correlation ID)
- `word_count` (computed)
- `language` (default: "en-US")

**CallAnalysis:**
- `objections` (JSON array of objection texts)
- `sentiment_score` (0.0-1.0)
- `sop_stages_completed` (JSON array)
- `sop_stages_missed` (JSON array)
- `sop_compliance_score` (0-10)
- `lead_quality` (string: "qualified", "unqualified", etc.)
- `uwc_job_id` (Shunya job correlation ID)

**RecordingTranscript:**
- Same as CallTranscript, but linked to `recording_sessions.id`

**RecordingAnalysis:**
- `outcome` ("won", "lost", "pending", "no_show")
- `sentiment_score` (0.0-1.0)
- `sop_compliance_score` (0-10)

**ShunyaJob:**
- `input_payload` (JSON: input sent to Shunya)
- `output_payload` (JSON: normalized Shunya response)
- `processed_output_hash` (SHA256 hash for idempotency)
- `job_status` (pending, running, succeeded, failed, timeout)
- `shunya_job_id` (Shunya's job ID)

### 10.2 What Otto Never Stores

**Raw Shunya Responses:**
- Otto stores normalized responses only (after `ShunyaResponseNormalizer`)
- Raw responses are not persisted (except in `ShunyaJob.output_payload` for debugging)

**Audio Files:**
- Otto does not store audio files
- Audio URLs are passed to Shunya (must be publicly accessible)
- Audio files are stored in S3 (Otto's storage, not Shunya's)

**Intermediate Processing State:**
- Otto does not store partial transcripts or analysis
- Only final results are persisted

### 10.3 What Shunya Must Return for Proper UX

**For Transcription:**
- `transcript_text` (required)
- `speaker_labels` (optional, but recommended)
- `confidence_score` (optional, but recommended)

**For Analysis:**
- `qualification.qualification_status` (required for lead status updates)
- `objections.objections` (required for objection display)
- `compliance.compliance_score` (required for SOP compliance display)
- `sentiment_score` (required for sentiment display)
- `summary.summary` (required for call summary)

**For Meeting Segmentation:**
- `part1` and `part2` (required for sales visit analysis)
- `transition_point` (optional, but recommended)
- `outcome` (optional, but recommended for appointment outcome)

---

## 11. Performance Expectations

### 11.1 Concurrency

**Otto Side:**
- Background workers: Celery workers (concurrency configurable)
- Default: 1 worker per tenant (sequential processing)
- Can scale to multiple workers per tenant

**Shunya Side:**
- Expected: Handle concurrent requests per tenant
- Rate limiting: Per tenant (TBD: specific limits)
- Otto assumes: Shunya can handle at least 10 concurrent requests per tenant

### 11.2 Scale Limits

**Per Tenant:**
- Max concurrent jobs: 10 (configurable)
- Max jobs per hour: 1000 (TBD: Shunya to confirm)

**Global:**
- No explicit limits on Otto side
- Relies on Shunya rate limiting (429 responses)

### 11.3 Max Audio Size

**Current Assumption:**
- Max file size: 100 MB (TBD: Shunya to confirm)
- Supported formats: MP3, WAV, M4A (TBD: Shunya to confirm)
- Max duration: 2 hours (TBD: Shunya to confirm)

### 11.4 Expected Processing SLAs

**Transcription:**
- Target: < 2 minutes for 10-minute call (TBD: Shunya to confirm)
- Max: < 5 minutes for 10-minute call (TBD: Shunya to confirm)

**Analysis:**
- Target: < 1 minute after transcript available (TBD: Shunya to confirm)
- Max: < 3 minutes after transcript available (TBD: Shunya to confirm)

**Meeting Segmentation:**
- Target: < 2 minutes after transcript available (TBD: Shunya to confirm)
- Max: < 5 minutes after transcript available (TBD: Shunya to confirm)

**Webhook Delivery:**
- Target: < 30 seconds after job completion (TBD: Shunya to confirm)
- Max: < 5 minutes after job completion (TBD: Shunya to confirm)

---

## 12. Open Questions for Shunya

### 12.1 API & Endpoints

1. **What is the exact OpenAPI specification for all Shunya endpoints?**
   - Request/response schemas
   - Error response formats
   - Authentication requirements

2. **Are there any additional endpoints not documented?**
   - Batch processing endpoints
   - Status polling endpoints
   - Health check endpoints

3. **What is the API versioning strategy?**
   - How are breaking changes handled?
   - Is version negotiation supported?

### 12.2 Authentication & Security

4. **What is the exact JWT verification process?**
   - Which claims are validated?
   - What is the token expiration policy?
   - Are there any additional validation rules?

5. **What is the HMAC signature algorithm for webhooks?**
   - Confirmed: HMAC-SHA256
   - Message format: `"{timestamp}.{raw_body_bytes}"`
   - Digest format: lowercase hex

6. **What is the webhook delivery guarantee?**
   - At-least-once? Exactly-once?
   - What is the retry policy for failed webhooks?
   - How long are webhooks retried?

### 12.3 Performance & SLAs

7. **What are the exact processing SLAs?**
   - Transcription time per minute of audio
   - Analysis time after transcript available
   - Meeting segmentation time

8. **What are the rate limits per tenant?**
   - Requests per minute
   - Requests per hour
   - Concurrent jobs per tenant

9. **What are the audio file size limits?**
   - Max file size (MB)
   - Max duration (minutes)
   - Supported formats

10. **What is the expected concurrency?**
    - Max concurrent requests per tenant
    - Max global concurrent requests

### 12.4 Error Handling

11. **What are all possible error codes?**
    - Complete list of `error_code` values
    - When is `retryable: true` vs `false`?

12. **How are partial failures handled?**
    - What if transcript succeeds but analysis fails?
    - Can we retry only the failed part?

### 12.5 Data & Payloads

13. **What is the exact payload structure for all endpoints?**
    - Required vs optional fields
    - Field name variations (if any)
    - Default values

14. **What is the ordering guarantee for arrays?**
    - Speaker labels (by time?)
    - Objections (by timestamp?)
    - Pending actions (by due_at?)

15. **What confidence score ranges are used?**
    - All scores 0.0-1.0?
    - Any scores use different ranges?

### 12.6 Webhooks

16. **What is the webhook payload structure?**
    - Exact fields in `result` object
    - Exact fields in `error` object
    - Are there any optional fields?

17. **What is the webhook retry policy?**
    - How many retries?
    - What is the backoff strategy?
    - How long are webhooks retried?

18. **What happens if webhook delivery fails permanently?**
    - Is there a dead letter queue?
    - How does Otto know to poll instead?

### 12.7 Multi-Tenancy

19. **How does Shunya enforce tenant isolation?**
    - Database-level scoping?
    - Application-level scoping?
    - Any cross-tenant data leakage risks?

20. **Are there per-tenant configuration options?**
    - Custom models per tenant?
    - Custom processing parameters?

### 12.8 Idempotency

21. **How does Shunya handle idempotency?**
    - Does `Idempotency-Key` header work?
    - How long are idempotency keys stored?
    - What happens for duplicate requests?

---

## 13. Shunya Confirmation Checklist

### 13.1 API & Endpoints

- [ ] **OpenAPI Specification**: Shunya provides complete OpenAPI 3.0 specification for all endpoints
- [ ] **Endpoint URLs**: All endpoints are accessible at documented URLs
- [ ] **Request/Response Schemas**: All request/response schemas match OpenAPI spec
- [ ] **Error Responses**: All error responses use canonical error envelope format
- [ ] **Versioning**: API versioning strategy is documented and implemented

### 13.2 Authentication & Security

- [ ] **JWT Verification**: Shunya verifies JWT tokens (HS256) with `company_id` claim
- [ ] **Header Validation**: Shunya validates `X-Company-ID` header matches JWT `company_id`
- [ ] **HMAC Signatures**: Shunya generates HMAC-SHA256 signatures for webhooks
- [ ] **Webhook Security**: Shunya includes `X-Shunya-Signature` and `X-Shunya-Timestamp` headers
- [ ] **Timestamp Format**: Webhook timestamps are epoch milliseconds (string)
- [ ] **Secret Management**: Shunya has access to `UWC_JWT_SECRET` and `UWC_HMAC_SECRET`

### 13.3 Request Processing

- [ ] **Idempotency-Key**: Shunya honors `Idempotency-Key` header (returns same response for duplicates)
- [ ] **Request ID**: Shunya logs `X-Request-ID` for correlation
- [ ] **Async Processing**: All processing is async (returns job/task ID immediately)
- [ ] **Job IDs**: Shunya returns unique `job_id` / `task_id` / `transcript_id` for tracking

### 13.4 Response Format

- [ ] **Consistent Structure**: All responses use consistent structure (per OpenAPI spec)
- [ ] **Required Fields**: All required fields are always present (even if null)
- [ ] **Field Names**: Field names match documented contract (no variations)
- [ ] **Confidence Scores**: All confidence scores are 0.0-1.0 (float)
- [ ] **Ordering**: Arrays are ordered as documented (by time, timestamp, etc.)

### 13.5 Webhook Delivery

- [ ] **Webhook Endpoint**: Shunya can deliver webhooks to `POST /api/v1/shunya/webhook`
- [ ] **Webhook Payload**: Webhook payload includes `shunya_job_id`, `status`, `result`/`error`, `company_id`
- [ ] **Webhook Headers**: Webhook includes `X-Shunya-Signature`, `X-Shunya-Timestamp`, `X-Shunya-Task-Id`
- [ ] **Webhook Reliability**: Webhooks are delivered reliably (at-least-once)
- [ ] **Webhook Retry**: Shunya retries failed webhook deliveries with exponential backoff

### 13.6 Error Handling

- [ ] **Error Envelope**: All errors use canonical error envelope format
- [ ] **Retryable Flag**: All errors include `retryable` flag (true/false)
- [ ] **Error Codes**: All error codes are documented
- [ ] **Error Details**: Error details include correlation IDs for debugging

### 13.7 Performance & SLAs

- [ ] **Processing SLAs**: Shunya confirms processing SLAs (transcription, analysis, segmentation)
- [ ] **Rate Limits**: Shunya confirms rate limits per tenant (requests/minute, requests/hour)
- [ ] **Audio Limits**: Shunya confirms max audio file size, duration, and supported formats
- [ ] **Concurrency**: Shunya confirms max concurrent requests per tenant

### 13.8 Multi-Tenancy

- [ ] **Tenant Isolation**: Shunya enforces tenant isolation (no cross-tenant data access)
- [ ] **Company ID Validation**: Shunya validates `company_id` in JWT and header
- [ ] **Rate Limiting**: Shunya rate limits per tenant (not global)

### 13.9 Idempotency

- [ ] **Idempotency-Key Support**: Shunya supports `Idempotency-Key` header
- [ ] **Duplicate Handling**: Shunya returns same response for duplicate requests
- [ ] **Idempotency Storage**: Shunya stores idempotency keys for at least 24 hours

### 13.10 Data & Payloads

- [ ] **Payload Structure**: All payload structures match documented contract
- [ ] **Field Variations**: Shunya confirms no field name variations (uses exact names)
- [ ] **Default Values**: Shunya confirms default values for optional fields
- [ ] **Ordering Guarantees**: Shunya confirms ordering guarantees for arrays

### 13.11 Testing & Validation

- [ ] **Test Environment**: Shunya provides test/staging environment URL
- [ ] **Test Credentials**: Shunya provides test credentials (JWT secret, HMAC secret)
- [ ] **Test Data**: Shunya provides test audio files and expected responses
- [ ] **Integration Testing**: Shunya confirms integration testing process

### 13.12 Documentation

- [ ] **API Documentation**: Shunya provides complete API documentation
- [ ] **Webhook Documentation**: Shunya provides webhook delivery documentation
- [ ] **Error Documentation**: Shunya provides error code documentation
- [ ] **Changelog**: Shunya provides API changelog and version history

### 13.13 Monitoring & Observability

- [ ] **Metrics**: Shunya provides metrics endpoint or dashboard
- [ ] **Logging**: Shunya logs requests with correlation IDs
- [ ] **Alerts**: Shunya has alerting for critical failures
- [ ] **Status Page**: Shunya provides status page or health check endpoint

### 13.14 Support & Escalation

- [ ] **Support Channel**: Shunya provides support channel (email, Slack, etc.)
- [ ] **Escalation Process**: Shunya provides escalation process for critical issues
- [ ] **SLA Response Times**: Shunya confirms SLA response times for support requests

---

## Document End

**Next Steps:**
1. Shunya team reviews this document
2. Shunya team confirms all checklist items
3. Shunya team provides answers to open questions
4. Both teams align on any discrepancies
5. Integration testing begins
6. Production deployment

**Contact:**
- Otto Backend Team: [Contact Information]
- Shunya Backend Team: [Contact Information]

**Document Maintenance:**
- This document should be updated whenever integration changes
- Version history should be maintained
- Both teams should review and approve changes

