# Shunya Integration Overview

**Document Version**: 1.0  
**Last Updated**: 2025-01-XX  
**Intended Audience**: Shunya Infrastructure / Backend Team  
**Purpose**: Technical reference for how Otto integrates with Shunya for ASR/NLU and call analysis

---

## Table of Contents

1. [High-level Architecture](#high-level-architecture)
2. [Code Locations & Modules](#code-locations--modules)
3. [Shunya API Usage](#shunya-api-usage)
4. [Data Model & Normalization](#data-model--normalization)
5. [Auth to Shunya](#auth-to-shunya)
6. [Networking Details](#networking-details)
7. [Storage Pattern](#storage-pattern)
8. [Access Pattern from Otto to Shunya Data](#access-pattern-from-otto-to-shunya-data)
9. [Rate Limiting / Concurrency Assumptions](#rate-limiting--concurrency-assumptions)
10. [Versioning](#versioning)
11. [Processing Flow & State Machine](#processing-flow--state-machine)
12. [Multi-tenant & RBAC Behavior](#multi-tenant--rbac-behavior)
13. [Idempotency & Retry Safety](#idempotency--retry-safety)
14. [Configuration & Environment](#configuration--environment)
15. [Error Handling & Observability](#error-handling--observability)
16. [Known Limitations & TODOs](#known-limitations--todos)

---

## High-level Architecture

### Where Shunya Sits in Otto Architecture

Shunya (UWC - Unified Workflow Composer) is integrated as an **external AI service** that Otto calls for:

1. **ASR (Automatic Speech Recognition)**: Transcribing audio recordings to text
2. **NLU (Natural Language Understanding)**: Analyzing transcripts for:
   - Lead qualification (BANT scores, qualification status)
   - Objection detection
   - SOP compliance checking
   - Sentiment analysis
   - Meeting segmentation (for sales visits)

**Integration Points**:
- **Primary Client**: `app/services/uwc_client.py` - HTTP client wrapper for all Shunya API calls
- **Integration Service**: `app/services/shunya_integration_service.py` - Orchestrates full pipeline (transcription → analysis → persistence)
- **Job Management**: `app/services/shunya_job_service.py` - Tracks async jobs, handles retries, ensures idempotency
- **Webhook Handler**: `app/routes/shunya_webhook.py` - Receives job completion notifications from Shunya
- **Background Workers**: `app/tasks/shunya_integration_tasks.py`, `app/tasks/shunya_job_polling_tasks.py` - Async processing

### Which Parts of Otto Depend on Shunya

1. **CSR Dashboard** (`/Users/tusharmehrotra/otto` - React/Next.js frontend):
   - Displays call transcripts (Shunya ASR)
   - Shows lead qualification results
   - Lists objections detected
   - Displays SOP compliance scores
   - Shows sentiment analysis

2. **Sales Rep Mobile App** (`/Users/tusharmehrotra/Documents/Otto_Salesrep` - React Native/Expo):
   - Displays appointment recording transcripts
   - Shows meeting segmentation (Part 1: Rapport, Part 2: Proposal/Close)
   - Displays coaching insights from visit analysis
   - Shows outcome classification (won/lost/pending)

3. **Executive Dashboard** (Future):
   - Aggregated analytics from Shunya analysis
   - Team performance metrics
   - Compliance reporting

### Request → Processing → Persistence → Frontend Consumption Flow

#### Flow 1: Recorded Call (CSR Call)

```
1. Call arrives via CallRail webhook
   → app/routes/enhanced_callrail.py::handle_call_completed()
   
2. Audio URL extracted from CallRail payload
   → Background task triggered: process_call_with_shunya.delay()
   
3. Shunya Integration Service called
   → app/services/shunya_integration_service.py::process_csr_call()
   
4. Transcription Request
   → UWCClient.transcribe_audio(company_id, request_id, audio_url)
   → POST /api/v1/transcription/transcribe
   → Returns: {task_id, transcript_id}
   
5. Poll for Transcript (or wait for webhook)
   → UWCClient.get_transcript(company_id, request_id, call_id)
   → GET /api/v1/transcription/transcript/{call_id}
   → Returns: {transcript_text, speaker_labels, confidence_score}
   
6. Store Transcript
   → CallTranscript model persisted
   → app/models/call_transcript.py
   → Fields: transcript_text, speaker_labels, confidence_score, uwc_job_id
   
7. Start Analysis Pipeline
   → UWCClient.start_analysis(company_id, request_id, call_id)
   → POST /api/v1/analysis/start/{call_id}
   → Returns: {job_id}
   
8. Poll for Complete Analysis (or wait for webhook)
   → UWCClient.get_complete_analysis(company_id, request_id, call_id)
   → GET /api/v1/analysis/complete/{call_id}
   → Returns: {qualification, objections, compliance, summary, sentiment_score, entities}
   
9. Normalize Response
   → ShunyaResponseNormalizer.normalize_complete_analysis(response)
   → app/services/shunya_response_normalizer.py
   → Handles variations in response format, missing fields
   
10. Persist Analysis
    → CallAnalysis model persisted
    → app/models/call_analysis.py
    → Fields: objections, sentiment_score, sop_stages_completed, sop_compliance_score, lead_quality
    
11. Update Domain Models
    → Lead.status updated based on qualification_status
    → Appointment created if qualified_booked
    → Tasks created from pending_actions
    → KeySignal entries created for high-priority insights
    
12. Emit Events
    → app/realtime/bus.py::emit("call.transcribed", ...)
    → app/realtime/bus.py::emit("lead.updated", ...)
    
13. Frontend Consumption
    → GET /api/v1/calls/{call_id} (includes transcript)
    → GET /api/v1/calls/{call_id}/analysis (includes objections, compliance, qualification)
    → CSR dashboard displays results
```

#### Flow 2: Follow-up Analysis / Coaching Scenario (Sales Visit)

```
1. Sales Rep completes appointment recording
   → app/routes/recording_sessions.py::upload_audio_complete()
   → RecordingSession created with audio_url
   
2. Async Job Submitted
   → shunya_async_job_service.submit_sales_visit_job()
   → app/services/shunya_async_job_service.py
   → ShunyaJob created (job_type="sales_visit")
   
3. Background Worker Processes
   → app/tasks/shunya_integration_tasks.py::process_visit_with_shunya()
   → OR webhook received: app/routes/shunya_webhook.py::shunya_webhook()
   
4. Transcription (if not Ghost Mode)
   → UWCClient.transcribe_audio(company_id, request_id, audio_url)
   → POST /api/v1/transcription/transcribe
   → RecordingTranscript persisted
   
5. Meeting Segmentation Analysis
   → UWCClient.analyze_meeting_segmentation(company_id, request_id, call_id)
   → POST /api/v1/meeting-segmentation/analyze
   → Returns: {part1, part2, transition_point, segmentation_confidence}
   
6. Complete Analysis
   → UWCClient.get_complete_analysis(company_id, request_id, call_id)
   → GET /api/v1/analysis/complete/{call_id}
   → Returns: {objections, compliance, outcome, sentiment_score}
   
7. Normalize & Merge
   → ShunyaResponseNormalizer.normalize_meeting_segmentation()
   → ShunyaResponseNormalizer.normalize_complete_analysis()
   → Merged into single normalized_analysis dict
   
8. Persist Analysis
   → RecordingAnalysis model persisted
   → app/models/recording_analysis.py
   → Fields: outcome, sentiment_score, sop_compliance_score
   
9. Update Appointment Outcome
   → Appointment.outcome updated (WON/LOST/PENDING)
   → Lead.status updated if outcome is WON/LOST
   → Appointment.status = COMPLETED if outcome is WON/LOST
   
10. Create Coaching Tasks
    → Tasks created from visit_actions / pending_actions
    → Assigned to REP (TaskAssignee.REP)
    
11. Emit Events
    → emit("recording_session.analyzed", ...)
    → emit("appointment.outcome_updated", ...)
    
12. Frontend Consumption
    → GET /api/v1/recording-sessions/{session_id}
    → GET /api/v1/appointments/{appointment_id}
    → Sales Rep app displays meeting segmentation, outcome, coaching tips
```

---

## Code Locations & Modules

### Core Integration Files

| File | Role | Key Responsibilities |
|------|------|---------------------|
| `app/services/uwc_client.py` | HTTP Client Wrapper | Makes all Shunya API calls, handles retries, error parsing, JWT generation, HMAC signatures |
| `app/services/shunya_integration_service.py` | Orchestration Service | Full pipeline orchestration: transcription → analysis → persistence → domain updates |
| `app/services/shunya_job_service.py` | Job Management | Creates ShunyaJob records, tracks status, handles retries with exponential backoff, idempotency checks |
| `app/services/shunya_response_normalizer.py` | Response Normalization | Defensive parsing of Shunya responses, handles format variations, provides consistent structure |
| `app/services/shunya_async_job_service.py` | Async Job Submission | Submits jobs to background queue, manages job lifecycle |
| `app/routes/shunya_webhook.py` | Webhook Handler | Receives job completion notifications, verifies HMAC signature, processes results |
| `app/utils/shunya_webhook_security.py` | Webhook Security | HMAC-SHA256 signature verification, timestamp validation, replay attack prevention |
| `app/tasks/shunya_integration_tasks.py` | Background Tasks | Celery tasks for async processing (legacy, being phased out) |
| `app/tasks/shunya_job_polling_tasks.py` | Polling Tasks | Polls Shunya for job status if webhook not received |

### Data Models

| Model | File | Purpose |
|-------|------|---------|
| `ShunyaJob` | `app/models/shunya_job.py` | Tracks async Shunya API jobs, status, retries, idempotency |
| `CallTranscript` | `app/models/call_transcript.py` | Stores ASR transcription results (transcript_text, speaker_labels, confidence_score) |
| `CallAnalysis` | `app/models/call_analysis.py` | Stores NLU analysis results (objections, compliance, sentiment, qualification) |
| `RecordingTranscript` | `app/models/recording_transcript.py` | Stores transcription for sales visit recordings |
| `RecordingAnalysis` | `app/models/recording_analysis.py` | Stores analysis for sales visit recordings (outcome, sentiment, compliance) |

### Route Handlers (Trigger Points)

| Route | File | When Shunya is Called |
|-------|------|----------------------|
| `POST /api/v1/recording-sessions/{session_id}/upload-audio` | `app/routes/recording_sessions.py` | After audio upload, triggers sales visit analysis |
| `POST /api/v1/calls/{call_id}/analyze` | `app/routes/analysis.py` | Manual trigger for call analysis |
| `POST /api/v1/shunya/webhook` | `app/routes/shunya_webhook.py` | Receives job completion notifications |

---

## Shunya API Usage

### Endpoint 1: Transcription (ASR)

**Endpoint**: `POST /api/v1/transcription/transcribe`  
**Called From**: `app/services/uwc_client.py::transcribe_audio()`  
**Triggered By**: 
- `app/services/shunya_integration_service.py::process_csr_call()` (CSR calls)
- `app/services/shunya_integration_service.py::process_sales_visit()` (Sales visits)

**Request Payload**:
```python
{
    "call_id": 12345,  # Integer call ID
    "audio_url": "https://s3.amazonaws.com/bucket/audio.mp3",  # Publicly accessible URL
    "call_type": "csr_call",  # or "sales_call"
    "language": "en-US",  # Optional, default: "en-US"
    "model": "default"  # Optional ASR model identifier
}
```

**Response Fields We Rely On**:
- `task_id` / `transcript_id` / `job_id` - Used for status polling
- `success` - Boolean indicating if request was accepted

**Status Polling**:
- `GET /api/v1/transcription/status/{call_id}` - Check transcription status
- `GET /api/v1/transcription/transcript/{call_id}` - Get final transcript

**Transcript Response Fields**:
- `transcript_text` - Full transcript text (required)
- `speaker_labels` - Speaker diarization segments (optional, array of {speaker, text, start_time, end_time})
- `confidence_score` - ASR confidence (0.0-1.0, optional)

**Timeouts & Retries**:
- HTTP timeout: 30 seconds (configurable via `UWCClient.timeout`)
- Max retries: 3 attempts with exponential backoff (5s, 10s, 30s)
- Circuit breaker: 5 failures → 30s cooldown (per endpoint per tenant)

**Error Codes Handled**:
- `401` / `403` → `UWCAuthenticationError` (no retry)
- `429` → `UWCRateLimitError` (retry with backoff)
- `5xx` → `UWCServerError` (retry with backoff if `retryable=true` in error envelope)
- Timeout → `UWCClientError` (retry with backoff)

---

### Endpoint 2: Start Analysis Pipeline

**Endpoint**: `POST /api/v1/analysis/start/{call_id}`  
**Called From**: `app/services/uwc_client.py::start_analysis()`  
**Triggered By**: `app/services/shunya_integration_service.py::process_csr_call()`

**Request Payload**:
```python
# No body required - call_id is in path
# Headers include: company_id, request_id, JWT token
```

**Response Fields We Rely On**:
- `job_id` / `task_id` - Used for status polling
- `success` - Boolean

**Status Polling**:
- `GET /api/v1/analysis/status/{call_id}` - Check analysis status per type
- `GET /api/v1/analysis/complete/{call_id}` - Get complete analysis results

**Timeouts & Retries**: Same as transcription (30s timeout, 3 retries, exponential backoff)

---

### Endpoint 3: Get Complete Analysis

**Endpoint**: `GET /api/v1/analysis/complete/{call_id}`  
**Called From**: `app/services/uwc_client.py::get_complete_analysis()`  
**Triggered By**: 
- `app/services/shunya_integration_service.py::process_csr_call()` (after start_analysis)
- `app/routes/shunya_webhook.py::shunya_webhook()` (when webhook received)

**Request**: No body, `call_id` in path

**Response Fields We Rely On** (normalized by `ShunyaResponseNormalizer`):

```python
{
    "qualification": {
        "qualification_status": "qualified_booked" | "qualified_unbooked" | "qualified_service_not_offered" | "not_qualified",
        "bant_scores": {"budget": 0.8, "authority": 0.7, "need": 0.9, "timeline": 0.6},
        "overall_score": 0.75,
        "confidence_score": 0.85,
        "decision_makers": ["John Smith"],
        "urgency_signals": ["immediate need"],
        "budget_indicators": ["$50k budget"]
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
                "speaker_id": "SPEAKER_02"
            }
        ],
        "total_objections": 1
    },
    "compliance": {
        "compliance_score": 0.85,
        "stages_followed": ["connect", "agenda", "assess"],
        "stages_missed": ["ask", "close"],
        "violations": [],
        "positive_behaviors": [],
        "recommendations": []
    },
    "summary": {
        "summary": "Customer called about roof repair...",
        "key_points": ["Urgent need", "Budget approved"],
        "action_items": ["Follow up in 24 hours"],
        "next_steps": [],
        "confidence_score": 0.9
    },
    "sentiment_score": 0.7,  # 0.0 (negative) to 1.0 (positive)
    "pending_actions": [
        {
            "action": "Send quote via email",
            "due_at": "2025-01-15T10:00:00Z",
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

**Timeouts & Retries**: Same as transcription

---

### Endpoint 4: Meeting Segmentation (Sales Visits)

**Endpoint**: `POST /api/v1/meeting-segmentation/analyze`  
**Called From**: `app/services/uwc_client.py::analyze_meeting_segmentation()`  
**Triggered By**: `app/services/shunya_integration_service.py::process_sales_visit()`

**Request Payload**:
```python
{
    "call_id": 12345,  # Integer call ID (from related call)
    "analysis_type": "full"  # or "quick"
}
```

**Response Fields We Rely On** (normalized by `ShunyaResponseNormalizer`):

```python
{
    "success": true,
    "call_id": 12345,
    "part1": {
        "start_time": 0,
        "end_time": 240,
        "duration": 240,
        "content": "Rapport building, agenda setting...",
        "key_points": ["Relationship building", "Agenda set"]
    },
    "part2": {
        "start_time": 240,
        "end_time": 420,
        "duration": 180,
        "content": "Proposal presentation, closing...",
        "key_points": ["Proposal presented", "Deal closed"]
    },
    "segmentation_confidence": 0.8,
    "transition_point": 240,  # Seconds
    "transition_indicators": ["Let's talk about pricing", "Here's our proposal"],
    "meeting_structure_score": 4,  # 1-5 scale
    "call_type": "sales_appointment",
    "outcome": "won"  # Inferred from part2 content
}
```

**Status Polling**:
- `GET /api/v1/meeting-segmentation/status/{call_id}` - Check status
- `GET /api/v1/meeting-segmentation/analysis/{call_id}` - Get full analysis

**Timeouts & Retries**: Same as transcription

---

### Endpoint 5: Webhook (Job Completion Notification)

**Endpoint**: `POST /api/v1/shunya/webhook` (Otto endpoint, receives from Shunya)  
**Handler**: `app/routes/shunya_webhook.py::shunya_webhook()`

**Shunya Sends**:
- Headers:
  - `X-Shunya-Signature`: HMAC-SHA256 hex digest
  - `X-Shunya-Timestamp`: Epoch milliseconds (string)
  - `X-Shunya-Task-Id`: Task ID for idempotency (optional)

**Payload**:
```python
{
    "shunya_job_id": "shunya_job_12345",
    "status": "completed" | "failed",
    "result": {...},  # Optional, if status is "completed"
    "error": {...},   # Optional, if status is "failed" (canonical error envelope)
    "company_id": "company_abc123"  # Required for tenant verification
}
```

**Otto Processing**:
1. Verify HMAC signature (reject if invalid → 401)
2. Validate timestamp (reject if >5min old → 401, replay attack prevention)
3. Look up ShunyaJob by `shunya_job_id` (tenant-scoped)
4. Verify `company_id` matches job.company_id (reject if mismatch → 403, cross-tenant attack)
5. If status="completed": fetch result, normalize, persist, emit events
6. If status="failed": mark job as failed, schedule retry if applicable

**Idempotency**: Webhook handler checks `processed_output_hash` to prevent duplicate processing

---

## Data Model & Normalization

### How Shunya Responses Are Persisted

#### Model 1: CallTranscript

**File**: `app/models/call_transcript.py`  
**Shunya-Derived Fields**:
- `transcript_text` (Text) - From Shunya `transcript_text` or `transcript`
- `speaker_labels` (JSON) - From Shunya `speaker_labels` or `speakers` or `diarization`
- `confidence_score` (Float) - From Shunya `confidence_score` or `confidence`
- `uwc_job_id` (String, unique) - From Shunya `task_id` or `transcript_id` or `job_id`
- `word_count` (Integer) - Computed from `transcript_text`
- `language` (String) - Default "en-US"

**State Modeling**: No explicit state enum - transcript is either present or absent. If `transcript_text` is empty, transcript is considered "not available".

**Linking**:
- `call_id` → `calls.call_id` (FK)
- `tenant_id` → `companies.id` (FK, for tenant isolation)

---

#### Model 2: CallAnalysis

**File**: `app/models/call_analysis.py`  
**Shunya-Derived Fields**:
- `objections` (JSON) - Array of objection texts, from `objections.objections[]`
- `sentiment_score` (Float) - From `sentiment_score` (0.0-1.0)
- `sop_stages_completed` (JSON) - Array, from `compliance.stages_followed`
- `sop_stages_missed` (JSON) - Array, from `compliance.stages_missed`
- `sop_compliance_score` (Float) - From `compliance.compliance_score` (0-10 scale)
- `lead_quality` (String) - From `qualification.qualification_status` (mapped to: "qualified", "unqualified", "hot", "warm", "cold")
- `uwc_job_id` (String, unique) - From `job_id` or `task_id`

**State Modeling**: No explicit state enum - analysis is either present or absent. If `analyzed_at` is NULL, analysis is considered "not available".

**Linking**:
- `call_id` → `calls.call_id` (FK)
- `tenant_id` → `companies.id` (FK)

---

#### Model 3: RecordingTranscript

**File**: `app/models/recording_transcript.py`  
**Shunya-Derived Fields**: Same as CallTranscript, but linked to `recording_sessions.id`

**Linking**:
- `recording_session_id` → `recording_sessions.id` (FK)
- `company_id` → `companies.id` (FK)

---

#### Model 4: RecordingAnalysis

**File**: `app/models/recording_analysis.py`  
**Shunya-Derived Fields**:
- `outcome` (String) - From `outcome` or `appointment_outcome` (normalized to: "won", "lost", "pending", "no_show")
- `sentiment_score` (Float) - From `sentiment_score`
- `sop_compliance_score` (Float) - From `compliance.compliance_score`

**Linking**:
- `recording_session_id` → `recording_sessions.id` (FK)
- `appointment_id` → `appointments.id` (FK)
- `lead_id` → `leads.id` (FK)
- `company_id` → `companies.id` (FK)

---

#### Model 5: ShunyaJob

**File**: `app/models/shunya_job.py`  
**Purpose**: Tracks async Shunya API jobs for idempotency and retry management

**Fields**:
- `job_type` (Enum): `csr_call`, `sales_visit`, `segmentation`
- `job_status` (Enum): `pending`, `running`, `succeeded`, `failed`, `timeout`
- `shunya_job_id` (String) - Shunya's job ID (returned by API)
- `input_payload` (JSON) - Input sent to Shunya (audio_url, call_id, etc.)
- `output_payload` (JSON) - Normalized Shunya response
- `processed_output_hash` (String) - SHA256 hash of output_payload for idempotency
- `num_attempts` (Integer) - Retry counter
- `max_attempts` (Integer) - Default: 5
- `next_retry_at` (DateTime) - When to retry (exponential backoff)

**State Machine**:
```
pending → running → succeeded
                ↓
              failed → (retry) → pending
                ↓
              timeout (after 24h)
```

**Linking**:
- `company_id` → `companies.id` (FK, tenant isolation)
- `call_id` → `calls.call_id` (FK, optional)
- `recording_session_id` → `recording_sessions.id` (FK, optional)
- `lead_id` → `leads.id` (FK, optional)
- `appointment_id` → `appointments.id` (FK, optional)

---

### Normalization Logic

**File**: `app/services/shunya_response_normalizer.py`

**Purpose**: Defensive parsing of Shunya responses to handle:
- Variations in field names (e.g., `transcript` vs `transcript_text`)
- Missing/null fields (provides defaults)
- Type conversions (string → float, etc.)
- Nested data extraction

**Key Methods**:
- `normalize_complete_analysis()` - Normalizes analysis response
- `normalize_transcript_response()` - Normalizes transcript response
- `normalize_meeting_segmentation()` - Normalizes meeting segmentation response
- `_normalize_qualification()`, `_normalize_objections()`, `_normalize_compliance()`, etc. - Field-specific normalization

**Example**: If Shunya returns `{"summary": "text"}` (string), normalizer converts to:
```python
{
    "summary": {
        "summary": "text",
        "key_points": [],
        "action_items": [],
        "next_steps": [],
        "confidence_score": None
    }
}
```

---

## Auth to Shunya

### Authentication Method

**Primary**: JWT (HS256) with short-lived tokens (5-minute TTL)  
**Fallback**: API Key (legacy, deprecated)

**Implementation**: `app/services/uwc_client.py::_generate_jwt()`

```python
def _generate_jwt(self, company_id: str) -> str:
    """Generate short-lived HS256 JWT for UWC per OpenAPI (HTTP Bearer)."""
    iat = int(time.time())
    exp = iat + 60 * 5  # 5 minutes TTL
    claims = {
        "company_id": company_id,
        "iat": iat,
        "exp": exp,
        "iss": "otto-backend",
        "aud": "uwc"
    }
    token = jwt.encode(claims, self.jwt_secret, algorithm="HS256")
    return token
```

**JWT Secret**: Read from `UWC_JWT_SECRET` environment variable  
**Per-Tenant**: Yes - `company_id` is included in JWT claims

**Headers Sent**:
```python
{
    "Authorization": f"Bearer {jwt_token}",  # or f"Bearer {api_key}" if JWT not available
    "X-Company-ID": company_id,  # Redundant but included for explicit tenant context
    "X-Request-ID": request_id,  # Correlation ID for tracing
    "X-UWC-Version": "v1",  # API version
    "Content-Type": "application/json",
    "X-UWC-Timestamp": timestamp,  # ISO 8601 UTC
    "X-Signature": hmac_signature,  # HMAC-SHA256 (if payload provided)
    "Idempotency-Key": request_id  # For mutating requests (POST/PUT/DELETE)
}
```

**HMAC Signature** (optional, for additional security):
- Secret: `UWC_HMAC_SECRET` environment variable
- Algorithm: HMAC-SHA256
- Message: `"{timestamp}.{json_payload}"` (sorted keys)
- Digest: Lowercase hex string

**Where Keys Are Read From**:
- `UWC_JWT_SECRET` - From `app/config.py::Settings.UWC_JWT_SECRET` (env: `UWC_JWT_SECRET`)
- `UWC_API_KEY` - From `app/config.py::Settings.UWC_API_KEY` (env: `UWC_API_KEY`, legacy)
- `UWC_HMAC_SECRET` - From `app/config.py::Settings.UWC_HMAC_SECRET` (env: `UWC_HMAC_SECRET`)

**Injection**: Headers are generated in `app/services/uwc_client.py::_get_headers()` and included in all HTTP requests via `httpx.AsyncClient`.

---

## Networking Details

### Network Type

**Public Internet**: All Shunya API calls are made over HTTPS to `UWC_BASE_URL` (default: `https://otto.shunyalabs.ai`)

**No VPC Peering**: Otto and Shunya are not on the same internal network. All communication is over public internet.

**HTTPS Validation**: 
- Production: HTTPS is **required** (enforced in `UWCClient.__init__()`)
- Development: HTTPS is **recommended** (warning logged if HTTP used)

**Implementation**: `app/services/uwc_client.py::_make_request()` uses `httpx.AsyncClient(timeout=self.timeout)` for all requests.

### Connection Pooling

**HTTP Client Reuse**: Yes - `httpx.AsyncClient` is created per request (context manager), but connection pooling is handled by httpx internally.

**No Persistent Client**: Each `_make_request()` call creates a new `AsyncClient` instance (within async context manager). This is acceptable because:
- Requests are infrequent (per call/visit, not high-volume)
- Connection overhead is minimal
- Simplifies error handling and timeout management

**Future Optimization**: Could use a singleton `AsyncClient` with connection pooling if request volume increases.

---

## Storage Pattern

### Raw Shunya Responses

**Stored**: Yes, but normalized

**Where**:
- `ShunyaJob.output_payload` (JSON column) - Stores normalized (not raw) Shunya response
- `ShunyaJob.input_payload` (JSON column) - Stores input sent to Shunya (audio_url, call_id, etc.)

**Raw vs Normalized**: We store **normalized** responses (after `ShunyaResponseNormalizer` processing), not raw Shunya responses. This ensures:
- Consistent structure regardless of Shunya API format changes
- Easier debugging (consistent format)
- Idempotency (hash of normalized output)

**Retention**: 
- No explicit TTL configured in code
- Data persists indefinitely (subject to database retention policies)
- `ShunyaJob` records are kept for audit/debugging purposes

### Normalized Data Storage

**CallTranscript**: Stores only essential fields (transcript_text, speaker_labels, confidence_score) - not full raw response

**CallAnalysis**: Stores only essential fields (objections, compliance, sentiment) - not full raw response

**RecordingTranscript / RecordingAnalysis**: Same pattern

**Rationale**: We extract only the fields we need for Otto's domain models. Full raw responses are not stored (except in `ShunyaJob.output_payload` for debugging).

---

## Access Pattern from Otto to Shunya Data

### Which Otto Endpoints Read Shunya-Derived Data

#### Endpoint 1: Get Call Details

**Route**: `GET /api/v1/calls/{call_id}`  
**File**: `app/routes/calls.py::get_call_details()`

**Shunya-Derived Fields Returned**:
- `transcript` - From `Call.transcript` (populated from `CallTranscript.transcript_text`)

**Note**: This endpoint returns basic call data. For full analysis, use `/api/v1/calls/{call_id}/analysis`.

---

#### Endpoint 2: Get Call Analysis

**Route**: `GET /api/v1/calls/{call_id}/analysis`  
**File**: `app/routes/analysis.py::get_call_analysis()`

**Shunya-Derived Fields Returned**:
```python
{
    "call_id": 12345,
    "analysis_id": "uuid",
    "status": "complete" | "not_analyzed" | "processing",
    "transcript": "...",  # From CallTranscript.transcript_text
    "objections": [...],  # From CallAnalysis.objections
    "objection_details": [...],  # From CallAnalysis.objection_details (if available)
    "coaching_tips": [...],  # From CallAnalysis.coaching_tips (if available)
    "sentiment_score": 0.7,  # From CallAnalysis.sentiment_score
    "sop_stages_completed": [...],  # From CallAnalysis.sop_stages_completed
    "sop_stages_missed": [...],  # From CallAnalysis.sop_stages_missed
    "sop_compliance_score": 8.5,  # From CallAnalysis.sop_compliance_score
    "rehash_score": 7.2,  # From CallAnalysis.rehash_score (if available)
    "lead_quality": "qualified",  # From CallAnalysis.lead_quality
    "qualification": {
        "qualification_status": "qualified_booked",
        "bant_scores": {...}  # From ShunyaJob.output_payload (if available)
    }
}
```

**Data Source**: 
- Primary: `CallAnalysis` model (from database)
- Secondary: `CallTranscript` model (for transcript)
- Tertiary: `ShunyaJob.output_payload` (for qualification details, if not in CallAnalysis)

---

#### Endpoint 3: Get Recording Session

**Route**: `GET /api/v1/recording-sessions/{session_id}`  
**File**: `app/routes/recording_sessions.py::get_recording_session()`

**Shunya-Derived Fields Returned**:
- `transcript` - From `RecordingTranscript.transcript_text` (if available)
- `analysis` - From `RecordingAnalysis` (outcome, sentiment_score, sop_compliance_score)

---

#### Endpoint 4: Get Appointment

**Route**: `GET /api/v1/appointments/{appointment_id}`  
**File**: `app/routes/appointments.py::get_appointment()`

**Shunya-Derived Fields Returned**:
- `outcome` - From `Appointment.outcome` (updated by Shunya analysis: WON/LOST/PENDING)
- Related `RecordingAnalysis` fields (if linked)

---

### Caching Layers

**No Caching**: Currently, no caching layer between database and API responses. All data is read directly from PostgreSQL.

**Future Consideration**: Could add Redis caching for frequently accessed analysis results, but not implemented yet.

---

## Rate Limiting / Concurrency Assumptions

### Explicit Limits

**None Configured**: Otto does not enforce explicit rate limits on Shunya API calls. We rely on:
- Shunya's rate limiting (429 responses)
- Circuit breaker (5 failures → 30s cooldown per endpoint per tenant)
- Retry backoff (exponential: 5s, 10s, 30s, 60s, 300s)

### Batching Logic

**No Batching**: Each call/visit is processed individually. We do not batch multiple audio files into a single Shunya request.

**Batch Endpoint Available**: Shunya provides `POST /uwc/v1/asr/batch` for batch ASR, but Otto does not use it. Each transcription is submitted separately.

**Rationale**: 
- Calls/visits arrive asynchronously (webhooks, user uploads)
- Batching would require queuing and delay processing
- Individual processing provides better UX (faster feedback)

### Background Queues / Workers

**Celery Workers** (optional, legacy):
- `app/tasks/shunya_integration_tasks.py` - Legacy Celery tasks
- Concurrency: Not visible in code (depends on Celery worker configuration)

**Async Job Service** (current):
- `app/services/shunya_async_job_service.py` - Submits jobs to background queue
- Concurrency: Not visible in code (depends on async worker configuration)

**Polling Workers**:
- `app/tasks/shunya_job_polling_tasks.py` - Polls Shunya for job status
- Concurrency: Not visible in code

**Assumption**: Background workers process jobs sequentially per tenant (or with low concurrency) to avoid overwhelming Shunya API.

---

## Versioning

### API Version Assumption

**Single Version**: Otto assumes Shunya API version `v1` (configurable via `UWC_VERSION` env var, default: "v1")

**Version Header**: `X-UWC-Version: v1` is sent in all requests, but Shunya may not enforce versioning yet.

**No Versioned Endpoints**: Otto does not use versioned URLs (e.g., `/api/v1/...` vs `/api/v2/...`). All endpoints are hardcoded to `/api/v1/...`.

**Future Consideration**: If Shunya introduces breaking changes, Otto would need to:
1. Add version detection logic
2. Support multiple endpoint versions
3. Migrate tenants gradually

**Not Implemented Yet**: Version negotiation or multi-version support is not in the codebase.

---

## Processing Flow & State Machine

### Typical Call/Recording Flow

#### Trigger: What Sends Audio to Shunya?

**CSR Calls**:
1. Call arrives via CallRail webhook → `app/routes/enhanced_callrail.py::handle_call_completed()`
2. Background task triggered: `process_call_with_shunya.delay()`
3. `ShunyaIntegrationService.process_csr_call()` called with `audio_url`

**Sales Visits**:
1. Rep uploads audio → `app/routes/recording_sessions.py::upload_audio_complete()`
2. Async job submitted: `shunya_async_job_service.submit_sales_visit_job()`
3. Background worker processes: `ShunyaIntegrationService.process_sales_visit()`

#### Synchronous vs Async

**Async (Background Jobs)**: All Shunya processing is done asynchronously:
- Transcription: Async (returns `task_id`, poll or wait for webhook)
- Analysis: Async (returns `job_id`, poll or wait for webhook)

**No Synchronous Blocking**: Otto never blocks HTTP requests waiting for Shunya. All processing happens in background workers or via webhooks.

#### Progress Tracking

**Database Flags**:
- `ShunyaJob.job_status`: `pending` → `running` → `succeeded` / `failed` / `timeout`
- `CallTranscript` presence indicates transcription complete
- `CallAnalysis` presence indicates analysis complete

**Job Queues**: `ShunyaJob` table tracks all async jobs with status, retry info, timestamps

**Polling**: `app/tasks/shunya_job_polling_tasks.py` polls Shunya for job status if webhook not received

**Webhooks**: `app/routes/shunya_webhook.py` receives job completion notifications (preferred method)

#### Frontend Notification

**Polling Endpoints**: Frontend polls:
- `GET /api/v1/calls/{call_id}/analysis` - Returns `status: "complete" | "not_analyzed" | "processing"`
- `GET /api/v1/recording-sessions/{session_id}` - Returns analysis status

**Real-time Events** (future): `app/realtime/bus.py::emit()` emits events, but real-time push to frontend is not fully implemented yet.

**Current Pattern**: Frontend polls every 3-5 seconds until `status === "complete"`.

---

## Multi-tenant & RBAC Behavior

### Tenant Context Passing to Shunya

**How**: `company_id` is included in:
1. JWT claims: `{"company_id": "company_abc123", ...}`
2. HTTP header: `X-Company-ID: company_abc123`
3. Request payload (where applicable): `{"company_id": "company_abc123", ...}`

**Where**: All Shunya API calls include tenant context via `UWCClient._get_headers(company_id, ...)`.

**Shunya Responsibility**: Shunya should use `company_id` for:
- Tenant isolation (data scoping)
- Rate limiting (per tenant)
- Billing/usage tracking

**Otto Assumption**: Shunya enforces tenant isolation server-side. Otto does not trust client-supplied `company_id` from Shunya responses - we always verify `company_id` matches the JWT/request context.

### Tenant Scoping on Otto Side

**Database Filters**: All queries filter by `company_id` / `tenant_id`:
- `CallTranscript.tenant_id = company_id`
- `CallAnalysis.tenant_id = company_id`
- `ShunyaJob.company_id = company_id`

**Middleware Enforcement**: `app/middleware/tenant.py::TenantContextMiddleware` extracts `company_id` from Clerk JWT and injects into request context. All database queries are automatically scoped to this tenant.

**Webhook Verification**: `app/routes/shunya_webhook.py` verifies `company_id` in webhook payload matches `ShunyaJob.company_id` (rejects with 403 if mismatch - cross-tenant attack prevention).

### Role-Based Access Control (RBAC)

**Which Roles Can See Shunya Data**:

| Role | Can See | Enforced By |
|------|---------|-------------|
| **CSR** | Own calls' transcripts, analysis | `app/middleware/rbac.py::require_role("csr")` + tenant scoping |
| **Sales Rep** | Own appointments' recordings, analysis | `app/middleware/rbac.py::require_role("sales_rep")` + tenant scoping |
| **Manager** | All company calls, recordings, analysis | `app/middleware/rbac.py::require_role("manager")` + tenant scoping |
| **Executive** | All company data (aggregated) | `app/middleware/rbac.py::require_role("manager")` (exec uses manager role) |

**Enforcement**:
- Route-level: `@require_role("csr", "manager")` decorator on FastAPI routes
- Data-level: Database queries filter by `company_id` (tenant) + `assigned_rep_id` (for reps) or no filter (for managers)

**Shunya-Derived Fields**: All Shunya-derived fields (transcript, objections, compliance) are subject to the same RBAC rules as the parent entity (Call, Appointment).

**No Special Shunya Permissions**: There are no Shunya-specific permissions. Access is based on role + tenant + ownership (for reps).

---

## Idempotency & Retry Safety

### How We Avoid Double-Processing

#### Method 1: Shunya Job ID Tracking

**Unique Constraint**: `ShunyaJob` table has unique constraint on `(company_id, shunya_job_id)`:
```python
UniqueConstraint('company_id', 'shunya_job_id', name='uq_shunya_job_company_shunya_id')
```

**Check Before Processing**: `app/services/shunya_job_service.py::is_idempotent()` checks if `shunya_job_id` already exists and succeeded.

**Webhook Idempotency**: Webhook handler checks if job already succeeded before processing:
```python
if job.job_status == ShunyaJobStatus.SUCCEEDED:
    return {"status": "already_processed"}
```

#### Method 2: Output Hash

**Hash Storage**: `ShunyaJob.processed_output_hash` stores SHA256 hash of normalized output payload.

**Check Before Persisting**: `app/services/shunya_job_service.py::should_process()` checks if output hash matches existing hash:
```python
if job.processed_output_hash == new_hash:
    return False  # Already processed
```

**Implementation**: `app/utils/idempotency.py::generate_output_payload_hash()` creates deterministic hash from normalized JSON.

#### Method 3: Unique Keys for Tasks/Signals

**Task Unique Keys**: Tasks created from Shunya `pending_actions` use unique keys:
```python
task_unique_key = generate_task_unique_key(
    source=TaskSource.SHUNYA,
    description=action_text,
    contact_card_id=contact_card_id,
)
```

**Check Before Creating**: `task_exists_by_unique_key()` checks if task already exists.

**Signal Unique Keys**: Similar pattern for `KeySignal` entries.

### Retry Handling

#### Network Failures

**Automatic Retry**: `UWCClient._make_request()` retries on:
- 5xx errors (if `retryable=true` in error envelope)
- 429 (rate limit)
- Timeout exceptions

**Retry Strategy**: Exponential backoff (5s, 10s, 30s, 60s, 300s), max 3 retries.

**Circuit Breaker**: 5 failures → 30s cooldown (per endpoint per tenant).

#### Shunya 5xx Errors

**Error Envelope**: Shunya returns canonical error envelope:
```python
{
    "success": false,
    "error": {
        "error_code": "INTERNAL_ERROR",
        "error_type": "server_error",
        "message": "Processing failed",
        "retryable": true,  # Key field
        "details": {},
        "timestamp": "2025-01-15T10:00:00Z",
        "request_id": "uuid"
    }
}
```

**Retry Logic**: If `retryable=true`, Otto retries with backoff. If `retryable=false`, job is marked as failed permanently.

**Implementation**: `app/services/uwc_client.py::_parse_shunya_error_envelope()` extracts `retryable` flag.

#### Preventing Corrupted/Incomplete Analysis

**Validation**: `ShunyaResponseNormalizer` validates response structure and provides defaults for missing fields.

**Idempotency Check**: Before persisting, `should_process()` checks output hash to prevent duplicate processing.

**Transaction Safety**: Database transactions ensure atomicity - either all updates succeed or none (rollback on error).

**Partial Updates**: If analysis is incomplete (e.g., transcript available but analysis failed), we store what we have (transcript) and mark analysis as "not available". Frontend handles missing fields gracefully.

---

## Configuration & Environment

### Environment Variables

| Variable | Purpose | Default | Required |
|----------|---------|---------|----------|
| `UWC_BASE_URL` | Shunya API base URL | `https://otto.shunyalabs.ai` | Yes (production) |
| `UWC_API_KEY` | Legacy API key (fallback) | `""` | No (deprecated, use JWT) |
| `UWC_JWT_SECRET` | JWT signing secret (HS256) | `""` | Yes (production) |
| `UWC_HMAC_SECRET` | HMAC signature secret | `""` | Yes (production, for webhooks) |
| `UWC_VERSION` | API version | `"v1"` | No |
| `USE_UWC_STAGING` | Use staging environment | `false` | No |
| `ENABLE_UWC_ASR` | Enable ASR features | `false` | No |
| `ENABLE_UWC_RAG` | Enable RAG features | `false` | No |
| `ENABLE_UWC_SUMMARIZATION` | Enable summarization | `false` | No |

**File**: `app/config.py::Settings`

**Services Using Them**:
- `app/services/uwc_client.py` - Reads all UWC_* variables
- `app/routes/shunya_webhook.py` - Reads `UWC_HMAC_SECRET` for signature verification
- `app/routes/analysis.py` - Checks `ENABLE_UWC_ASR` feature flag

**Ghost Mode**: Not a Shunya-specific config - it's an Otto feature flag for recording sessions (stored in `RecordingSession.mode`). When Ghost Mode is enabled, audio is not sent to Shunya (no transcription/analysis).

---

## Error Handling & Observability

### How Shunya Errors Are Surfaced

#### Internal Logging

**Logger**: `app/core/pii_masking.py::PIISafeLogger` - PII-safe logger (redacts sensitive data)

**Log Levels**:
- `ERROR`: Shunya API failures, webhook signature failures, processing errors
- `WARNING`: Rate limits, retries, missing fields
- `INFO`: Job creation, completion, status updates
- `DEBUG`: Request/response details (only in development)

**PII Redaction**: Logger automatically redacts phone numbers, emails, addresses from log messages.

**Correlation IDs**: All log messages include `request_id` / `job_id` for tracing.

#### Error Translation

**Shunya Error Envelope → Otto Error Codes**:
- `401` / `403` → `UWCAuthenticationError` → HTTP 401 to frontend
- `429` → `UWCRateLimitError` → HTTP 429 to frontend (with retry-after)
- `5xx` → `UWCServerError` → HTTP 502 to frontend (if retryable) or 500 (if not retryable)
- Timeout → `UWCClientError` → HTTP 504 to frontend

**Frontend Response**: Frontend receives RFC-7807 format error responses:
```python
{
    "success": false,
    "error": {
        "error_code": "SHUNYA_API_ERROR",
        "error_type": "external_service_error",
        "message": "Shunya API request failed",
        "retryable": true,
        "details": {
            "shunya_error_code": "INTERNAL_ERROR",
            "request_id": "uuid"
        }
    }
}
```

#### Correlation IDs

**Request ID**: `X-Request-ID` header is sent to Shunya in all requests and logged on Otto side.

**Job ID**: `ShunyaJob.id` is used for correlation between Otto and Shunya.

**Webhook Task ID**: `X-Shunya-Task-Id` header (from webhook) is logged for correlation.

**Implementation**: `app/services/uwc_client.py::_get_headers()` includes `X-Request-ID` in all requests.

#### Degraded Behavior

**If Shunya Fails**:
- **Transcription fails**: Call is still stored, but `transcript` field is empty. Frontend shows "Transcript not available".
- **Analysis fails**: `CallAnalysis` is not created. Frontend shows "Analysis not available" or "Processing...".
- **Webhook fails**: Polling worker will eventually fetch results (if webhook never arrives, job times out after 24h).

**No Partial Data**: We do not surface partial/corrupted analysis. If analysis is incomplete, we mark job as failed and retry.

**User Feedback**: Frontend shows appropriate error messages:
- "Analysis is processing, please check back in a few minutes"
- "Analysis failed, please try again"
- "Transcript not available"

---

## Known Limitations & TODOs

### Current Limitations

1. **No Batch Processing**: Each call/visit is processed individually. Batch ASR endpoint (`/uwc/v1/asr/batch`) is available but not used.

2. **Synchronous Polling**: After starting analysis, Otto polls Shunya immediately (with `asyncio.sleep(2)`) instead of waiting for webhook. This is inefficient but works.

3. **No Real-time Push**: Frontend must poll endpoints to check analysis status. Real-time events (`app/realtime/bus.py::emit()`) are emitted but not pushed to frontend yet.

4. **Limited Error Recovery**: If Shunya returns partial data (e.g., transcript but no analysis), we don't have logic to retry only the failed part. We retry the entire job.

5. **No Version Negotiation**: Otto assumes Shunya API version `v1`. If Shunya introduces breaking changes, Otto would need code updates.

6. **Ghost Mode Handling**: In Ghost Mode, no audio is sent to Shunya, but we still create `ShunyaJob` records. This is intentional but could be optimized.

7. **Meeting Segmentation Limitation**: Meeting segmentation requires a `call_id`, but sales visits may not have a related call. We use a workaround (find related call by `lead_id`).

### TODOs (Visible in Code)

1. **`app/services/shunya_integration_service.py:127`**: "Poll for transcription to complete (or wait for webhook)" - Currently uses `asyncio.sleep(5)` instead of proper webhook/polling.

2. **`app/services/shunya_integration_service.py:167`**: "Analysis may be async - poll or wait for webhook" - Currently uses `asyncio.sleep(2)` instead of proper webhook/polling.

3. **`app/tasks/recording_session_tasks.py:117`**: "TODO: Store transcript in a separate table or attach to session" - Transcript storage for recording sessions is incomplete.

4. **Webhook Reliability**: Webhook delivery is "at-least-once" (duplicates possible). Idempotency is handled, but we could add deduplication at webhook level.

5. **Polling Worker**: `app/tasks/shunya_job_polling_tasks.py` exists but may not be scheduled. Need to verify Celery beat configuration.

### Not Yet Implemented

1. **Batch ASR**: Not using `/uwc/v1/asr/batch` endpoint.

2. **Document Ingestion**: Shunya provides document ingestion endpoints (`/api/v1/ingestion/documents/upload`), but Otto does not use them yet. Documents are ingested via other means.

3. **RAG Queries**: Shunya provides RAG query endpoint (`/api/v1/search/`), but Otto does not use it yet. RAG is handled by other services.

4. **Personal Clones**: Shunya provides personal clone training endpoints, but Otto does not use them yet.

5. **Follow-up Drafts**: Shunya provides follow-up draft generation endpoints, but Otto does not use them yet.

---

## Summary

Otto integrates with Shunya as an **external AI service** for ASR transcription and NLU analysis. The integration is **async-first** (background jobs + webhooks), **multi-tenant** (company_id scoping), and **idempotent** (job tracking + output hashing). All Shunya API calls are made over **public HTTPS** with **JWT authentication** and **HMAC signature verification** for webhooks. Shunya-derived data is **normalized** and stored in Otto's domain models (`CallTranscript`, `CallAnalysis`, `RecordingTranscript`, `RecordingAnalysis`), with **RBAC enforcement** at the API layer.

**Key Files for Shunya Team**:
- `app/services/uwc_client.py` - All Shunya API calls
- `app/services/shunya_integration_service.py` - Full pipeline orchestration
- `app/routes/shunya_webhook.py` - Webhook handler
- `app/services/shunya_response_normalizer.py` - Response normalization
- `app/models/shunya_job.py` - Job tracking model

**Questions for Shunya Team**:
1. What is the expected SLA for transcription/analysis completion?
2. Are webhooks guaranteed to be delivered, or should we always poll as fallback?
3. What is the rate limit per tenant? Should we implement client-side rate limiting?
4. Are there any planned breaking changes to the API that would require version negotiation?
5. How should we handle partial failures (e.g., transcript succeeds but analysis fails)?

---

**Document End**



