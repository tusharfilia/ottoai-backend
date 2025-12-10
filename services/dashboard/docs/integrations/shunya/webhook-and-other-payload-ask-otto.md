# API Reference: Webhooks, Error Envelopes, and Testing Guide

**Date**: 2025-12-08  
**Status**: ✅ Complete  
**Purpose**: Comprehensive reference for webhook structures, error handling, API payloads, and testing

---

## Table of Contents

1. [Webhook Structure](#webhook-structure)
2. [Error Envelope](#error-envelope)
3. [Complete Analysis API - Sample Payloads](#complete-analysis-api---sample-payloads)
4. [Meeting Segmentation Payload](#meeting-segmentation-payload)
5. [Ask Otto API Testing](#ask-otto-api-testing)

---

## Webhook Structure

### Overview

Shunya sends webhooks to Otto Backend to notify about job completion (transcription, analysis, segmentation).

**Endpoint**: `POST {OTTO_BACKEND_WEBHOOK_URL}/api/v1/shunya/webhook`

### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `X-Shunya-Signature` | ✅ Yes | HMAC-SHA256 hex digest of payload |
| `X-Shunya-Timestamp` | ✅ Yes | Epoch milliseconds (string) for replay attack prevention |
| `X-Shunya-Task-Id` | 🟡 Optional | Task ID for idempotency tracking |
| `Content-Type` | ✅ Yes | `application/json` |

### Webhook Payload Structure

```json
{
  "shunya_job_id": "shunya_job_12345",
  "job_id": "shunya_job_12345",  // Alias
  "task_id": "shunya_job_12345",  // Alias
  "status": "completed" | "failed" | "processing",
  "company_id": "company_abc123",
  "result": { /* Analysis result (if status is "completed") */ },
  "error": { /* Error envelope (if status is "failed") */ },
  "timestamp": "2025-12-08T10:30:00Z",
  "created_at": "2025-12-08T10:30:00Z"  // Alias for timestamp
}
```

### Webhook Event Types

| Event Type | Description | Payload Contains |
|------------|-------------|------------------|
| `call.transcription.complete` | Transcription finished | `data: {transcript_text, speaker_labels, confidence_score}` |
| `call.transcription.failed` | Transcription failed | `error: {error_envelope}` |
| `call.analysis.complete` | Complete analysis finished | `data: {summary, objections, qualification, compliance, ...}` |
| `call.analysis.failed` | Analysis failed | `error: {error_envelope}` |
| `meeting.segmentation.complete` | Meeting segmentation finished | `data: {part1, part2, transition_point, ...}` |
| `meeting.segmentation.failed` | Segmentation failed | `error: {error_envelope}` |

### Webhook Payload Examples

#### Example 1: Transcription Complete

```json
{
  "event_type": "call.transcription.complete",
  "task_id": "call_123_company_abc_transcription",
  "call_id": 123,
  "company_id": "company_abc",
  "timestamp": "2025-12-08T10:30:00Z",
  "status": "completed",
  "data": {
    "transcript_text": "Hello, this is a test call...",
    "speaker_labels": [
      {"speaker": "SPEAKER_01", "text": "Hello, this is a test call", "start_time": 0.0, "end_time": 2.5},
      {"speaker": "SPEAKER_02", "text": "Hi, how can I help you?", "start_time": 2.5, "end_time": 5.0}
    ],
    "confidence_score": 0.95,
    "word_count": 150,
    "language": "en-US"
  }
}
```

#### Example 2: Analysis Complete

```json
{
  "event_type": "call.analysis.complete",
  "task_id": "call_123_company_abc_analysis",
  "call_id": 123,
  "company_id": "company_abc",
  "timestamp": "2025-12-08T10:35:00Z",
  "status": "completed",
  "data": {
    "summary": {
      "summary": "Customer called about roof repair...",
      "key_points": ["Roof leak identified", "Customer needs urgent repair"],
      "pending_actions": [
        {
          "type": "schedule_appointment",
          "due_at": "2025-12-09T10:00:00Z",
          "contact_method": "phone",
          "confidence": 0.92,
          "raw_text": "Customer wants appointment tomorrow"
        }
      ],
      "sentiment_score": 0.7,
      "confidence_score": 0.88
    },
    "objections": {
      "objections": [
        {
          "id": 1,
          "category_id": 1,
          "category_text": "Price/Budget",
          "objection_text": "The price seems too high",
          "overcome": false,
          "speaker_id": "SPEAKER_02",
          "timestamp": 120.5,
          "severity": "medium",
          "confidence_score": 0.85,
          "response_suggestions": [
            "Focus on value proposition",
            "Offer payment plan options"
          ]
        }
      ],
      "total_count": 1
    },
    "qualification": {
      "bant_scores": {
        "budget": 0.8,
        "authority": 0.9,
        "need": 0.7,
        "timeline": 0.6
      },
      "overall_score": 0.75,
      "qualification_status": "hot",
      "booking_status": "booked",
      "appointment_type": "in-person",
      "appointment_date": "2025-12-09T10:00:00Z"
    },
    "compliance": {
      "compliance_score": 0.85,
      "target_role": "sales_rep",
      "stages_followed": ["Introduction", "Discovery", "Proposal"],
      "stages_missed": ["Closing"],
      "violations": [],
      "positive_behaviors": ["Active listening", "Clear communication"]
    }
  }
}
```

#### Example 3: Analysis Failed

```json
{
  "event_type": "call.analysis.failed",
  "task_id": "call_123_company_abc_analysis",
  "call_id": 123,
  "company_id": "company_abc",
  "timestamp": "2025-12-08T10:35:00Z",
  "status": "failed",
  "error": {
    "success": false,
    "error": {
      "error_code": "ANALYSIS_FAILED",
      "error_type": "processing_error",
      "message": "Failed to generate analysis for call 123",
      "retryable": true,
      "details": {
        "call_id": 123,
        "error_type": "LLM_TIMEOUT",
        "retry_available": true
      },
      "timestamp": "2025-12-08T10:35:00Z",
      "request_id": "req_abc123"
    }
  }
}
```

### HMAC Signature Generation

**Algorithm**: HMAC-SHA256  
**Input**: `{timestamp}:{json_payload}` (sorted keys)  
**Output**: Hex-encoded digest

**Python Example**:
```python
import hmac
import hashlib
import json

def generate_webhook_signature(payload: dict, timestamp: str, secret: str) -> str:
    message = f"{timestamp}:{json.dumps(payload, sort_keys=True)}"
    signature = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature
```

### Otto Backend Validation

1. **Verify HMAC Signature**: Reject if invalid → 401
2. **Validate Timestamp**: Reject if >5min old → 401 (replay attack prevention)
3. **Lookup Job**: Find `ShunyaJob` by `shunya_job_id` (tenant-scoped)
4. **Verify Company ID**: Reject if `company_id` mismatch → 403
5. **Process Result**: Normalize, persist, emit events (idempotent)

---

## Error Envelope

### Standard Error Response Structure

All error responses from Shunya follow this canonical format:

```json
{
  "success": false,
  "error": {
    "error_code": "MACHINE_READABLE_CODE",
    "error_type": "error_category",
    "message": "Human-readable error message",
    "retryable": true | false,
    "details": {
      "field": "additional_context",
      "reason": "why_it_failed"
    },
    "timestamp": "2025-12-08T10:30:00Z",
    "request_id": "req_abc123"
  },
  "timestamp": "2025-12-08T10:30:00Z"
}
```

### Error Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `success` | boolean | ✅ Yes | Always `false` for errors |
| `error` | object | ✅ Yes | Error details object |
| `error.error_code` | string | ✅ Yes | Machine-readable code (UPPER_SNAKE_CASE) |
| `error.error_type` | string | ✅ Yes | Error category (e.g., "validation_error", "processing_error") |
| `error.message` | string | ✅ Yes | Human-readable error message |
| `error.retryable` | boolean | ✅ Yes | Whether error is retryable (affects retry logic) |
| `error.details` | object | 🟡 Optional | Additional error context |
| `error.timestamp` | string | ✅ Yes | When error occurred (ISO 8601) |
| `error.request_id` | string | 🟡 Optional | Request ID for tracing/correlation |
| `timestamp` | string | ✅ Yes | Response timestamp (ISO 8601) |

### Common Error Codes

| Error Code | HTTP Status | Description | Retryable |
|------------|-------------|-------------|-----------|
| `BAD_REQUEST` | 400 | Invalid request parameters | ❌ No |
| `VALIDATION_ERROR` | 400 | Field validation failed | ❌ No |
| `UNAUTHORIZED` | 401 | Authentication failed | ❌ No |
| `FORBIDDEN` | 403 | Permission denied | ❌ No |
| `NOT_FOUND` | 404 | Resource not found | ❌ No |
| `ANALYSIS_NOT_AVAILABLE` | 404 | Analysis not yet available | ❌ No |
| `INTERNAL_SERVER_ERROR` | 500 | Unexpected server error | ✅ Yes |
| `ANALYSIS_FAILED` | 500 | Analysis processing failed | ✅ Yes |
| `TRANSCRIPTION_FAILED` | 500 | Transcription failed | ✅ Yes |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable | ✅ Yes |
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit exceeded | ✅ Yes (with retry_after) |

### Error Response Examples

#### Example 1: Validation Error

```json
{
  "success": false,
  "error": {
    "error_code": "VALIDATION_ERROR",
    "error_type": "validation_error",
    "message": "Invalid value for field 'call_id': expected integer, got string",
    "retryable": false,
    "details": {
      "field": "call_id",
      "value": "123",
      "expected": "integer"
    },
    "timestamp": "2025-12-08T10:30:00Z",
    "request_id": "req_abc123"
  },
  "timestamp": "2025-12-08T10:30:00Z"
}
```

#### Example 2: Resource Not Found

```json
{
  "success": false,
  "error": {
    "error_code": "CALL_NOT_FOUND",
    "error_type": "not_found",
    "message": "No call found with ID 999 for company company_abc",
    "retryable": false,
    "details": {
      "resource_type": "call",
      "resource_id": 999,
      "company_id": "company_abc"
    },
    "timestamp": "2025-12-08T10:30:00Z",
    "request_id": "req_abc123"
  },
  "timestamp": "2025-12-08T10:30:00Z"
}
```

#### Example 3: Analysis Failed (Retryable)

```json
{
  "success": false,
  "error": {
    "error_code": "ANALYSIS_FAILED",
    "error_type": "processing_error",
    "message": "Failed to generate analysis for call 123",
    "retryable": true,
    "details": {
      "call_id": 123,
      "error_type": "LLM_TIMEOUT",
      "retry_available": true
    },
    "timestamp": "2025-12-08T10:30:00Z",
    "request_id": "req_abc123"
  },
  "timestamp": "2025-12-08T10:30:00Z"
}
```

#### Example 4: Permission Denied

```json
{
  "success": false,
  "error": {
    "error_code": "PERMISSION_DENIED",
    "error_type": "authorization_error",
    "message": "Role 'customer_rep' cannot access team-wide objection data. Try asking about your own objections or request SOP guidance instead.",
    "retryable": false,
    "details": {
      "user_role": "customer_rep",
      "attempted_action": "query this data",
      "suggested_actions": [
        "Ask about your own performance instead",
        "Request knowledge-based guidance from SOPs",
        "Contact your manager for company-wide insights"
      ]
    },
    "timestamp": "2025-12-08T10:30:00Z",
    "request_id": "req_abc123"
  },
  "timestamp": "2025-12-08T10:30:00Z"
}
```

#### Example 5: Rate Limit Exceeded

```json
{
  "success": false,
  "error": {
    "error_code": "RATE_LIMIT_EXCEEDED",
    "error_type": "rate_limit",
    "message": "Rate limit exceeded. Please try again later.",
    "retryable": true,
    "details": {
      "limit": 100,
      "window": "1 hour",
      "retry_after": 3600
    },
    "timestamp": "2025-12-08T10:30:00Z",
    "request_id": "req_abc123"
  },
  "timestamp": "2025-12-08T10:30:00Z"
}
```

---

## Complete Analysis API - Sample Payloads

### Endpoint

**GET** `/api/v1/analysis/complete/{call_id}`

**Headers**:
- `Authorization: Bearer <JWT_TOKEN>` (required)
- `X-Company-ID: <company_id>` (required)
- `X-Target-Role: sales_rep | customer_rep` (optional, defaults to `sales_rep`)

### Response Structure

```json
{
  "call_id": 123,
  "status": "completed" | "pending" | "failed",
  "summary": { /* Summary data */ },
  "compliance": { /* Compliance data */ },
  "objections": { /* Objections data */ },
  "qualification": { /* Qualification data */ },
  "opportunity_analysis": { /* Opportunity analysis data */ },
  "created_at": "2025-12-08T10:00:00Z",
  "completed_at": "2025-12-08T10:05:00Z"
}
```

### Sample Payload: Sales Rep Role

**Request**:
```bash
curl -X GET "http://localhost:8000/api/v1/analysis/complete/123" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "X-Company-ID: company_abc" \
  -H "X-Target-Role: sales_rep"
```

**Response**:
```json
{
  "call_id": 123,
  "status": "completed",
  "summary": {
    "call_id": 123,
    "summary": "Sales rep John called customer about roof repair. Customer expressed urgency due to recent storm damage. Rep identified leak location and discussed repair options. Customer agreed to schedule in-person inspection for tomorrow.",
    "key_points": [
      "Customer has urgent roof leak from storm damage",
      "Rep identified leak location during call",
      "Customer agreed to in-person inspection",
      "Appointment scheduled for tomorrow at 2 PM"
    ],
    "action_items": [
      "Schedule inspection appointment",
      "Prepare repair estimate",
      "Follow up with customer tomorrow"
    ],
    "next_steps": [
      "Confirm appointment details",
      "Prepare inspection checklist"
    ],
    "pending_actions": [
      {
        "type": "schedule_appointment",
        "due_at": "2025-12-09T14:00:00Z",
        "contact_method": "phone",
        "confidence": 0.95,
        "raw_text": "Customer wants appointment tomorrow at 2 PM"
      },
      {
        "type": "send_estimate",
        "due_at": "2025-12-09T18:00:00Z",
        "contact_method": "email",
        "confidence": 0.88,
        "raw_text": "Send repair estimate after inspection"
      }
    ],
    "sentiment_score": 0.75,
    "confidence_score": 0.92,
    "created_at": "2025-12-08T10:05:00Z"
  },
  "compliance": {
    "call_id": 123,
    "compliance_score": 0.85,
    "target_role": "sales_rep",
    "stages_followed": [
      "Introduction",
      "Discovery",
      "Needs Assessment",
      "Proposal"
    ],
    "stages_missed": [
      "Closing"
    ],
    "violations": [],
    "positive_behaviors": [
      "Active listening demonstrated",
      "Clear communication of value proposition",
      "Professional tone maintained"
    ],
    "recommendations": [
      "Practice closing techniques",
      "Ask for commitment more directly"
    ],
    "confidence_score": 0.88,
    "created_at": "2025-12-08T10:05:00Z"
  },
  "objections": {
    "call_id": 123,
    "objections": [
      {
        "id": 1,
        "category_id": 1,
        "category_text": "Price/Budget",
        "objection_text": "The price seems a bit high for my budget",
        "overcome": true,
        "speaker_id": "SPEAKER_02",
        "timestamp": 180.5,
        "severity": "medium",
        "confidence_score": 0.90,
        "response_suggestions": [
          "Focus on value proposition",
          "Offer payment plan options"
        ],
        "created_at": "2025-12-08T10:05:00Z"
      },
      {
        "id": 2,
        "category_id": 6,
        "category_text": "Decision Authority",
        "objection_text": "I need to check with my spouse first",
        "overcome": true,
        "speaker_id": "SPEAKER_02",
        "timestamp": 240.0,
        "severity": "low",
        "confidence_score": 0.85,
        "response_suggestions": [
          "Offer to include spouse in consultation",
          "Provide information for spouse review"
        ],
        "created_at": "2025-12-08T10:05:00Z"
      }
    ],
    "total_count": 2
  },
  "qualification": {
    "call_id": 123,
    "bant_scores": {
      "budget": 0.85,
      "authority": 0.90,
      "need": 0.95,
      "timeline": 0.80
    },
    "overall_score": 0.875,
    "qualification_status": "hot",
    "decision_makers": ["Customer", "Spouse"],
    "urgency_signals": [
      "Recent storm damage",
      "Active leak",
      "Immediate need expressed"
    ],
    "budget_indicators": [
      "Discussed payment options",
      "Mentioned insurance coverage"
    ],
    "confidence_score": 0.90,
    "booking_status": "booked",
    "call_outcome_category": "qualified_and_booked",
    "appointment_confirmed": true,
    "appointment_date": "2025-12-09T14:00:00Z",
    "appointment_type": "in-person",
    "service_requested": "Roof Repair",
    "service_not_offered_reason": null,
    "follow_up_required": false,
    "follow_up_reason": null,
    "created_at": "2025-12-08T10:05:00Z"
  },
  "opportunity_analysis": {
    "call_id": 123,
    "risk_assessment": {
      "level": "low",
      "score": 25,
      "risk_factors": [],
      "positive_factors": [
        "Strong qualification scores",
        "Urgent need identified",
        "Appointment booked"
      ],
      "mitigation_strategies": [],
      "recommendation": "Deal is in good shape. Focus on delivering excellent service during inspection."
    },
    "missed_opportunities": [
      {
        "type": "cross_sell",
        "description": "Customer mentioned gutters but rep only discussed roof repair",
        "impact": "medium",
        "reasoning": "Customer said 'I might need new gutters too' but rep didn't explore this opportunity",
        "suggestion": "During inspection, assess gutter condition and offer bundle pricing"
      }
    ],
    "created_at": "2025-12-08T10:05:00Z"
  },
  "created_at": "2025-12-08T10:00:00Z",
  "completed_at": "2025-12-08T10:05:00Z"
}
```

### Sample Payload: Customer Rep Role

**Request**:
```bash
curl -X GET "http://localhost:8000/api/v1/analysis/complete/456" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "X-Company-ID: company_abc" \
  -H "X-Target-Role: customer_rep"
```

**Response**:
```json
{
  "call_id": 456,
  "status": "completed",
  "summary": {
    "call_id": 456,
    "summary": "Customer service rep Sarah handled a customer inquiry about billing. Customer was confused about recent charges. Rep explained charges clearly and resolved the issue. Customer expressed satisfaction with the service.",
    "key_points": [
      "Customer had billing question about recent charges",
      "Rep explained charges clearly and professionally",
      "Issue resolved to customer's satisfaction",
      "Customer thanked rep for helpful service"
    ],
    "action_items": [
      "Follow up with customer to ensure satisfaction",
      "Document resolution for records"
    ],
    "next_steps": [],
    "pending_actions": [
      {
        "type": "follow_up_call",
        "due_at": "2025-12-10T10:00:00Z",
        "contact_method": "phone",
        "confidence": 0.75,
        "raw_text": "Customer requested follow-up call to confirm everything is clear"
      }
    ],
    "sentiment_score": 0.85,
    "confidence_score": 0.90,
    "created_at": "2025-12-08T11:00:00Z"
  },
  "compliance": {
    "call_id": 456,
    "compliance_score": 0.92,
    "target_role": "customer_rep",
    "stages_followed": [
      "Greeting",
      "Active Listening",
      "Problem Identification",
      "Solution Explanation",
      "Confirmation"
    ],
    "stages_missed": [],
    "violations": [],
    "positive_behaviors": [
      "Empathetic listening",
      "Clear explanation of charges",
      "Professional tone throughout",
      "Proactive follow-up offer"
    ],
    "recommendations": [],
    "confidence_score": 0.90,
    "created_at": "2025-12-08T11:00:00Z"
  },
  "objections": {
    "call_id": 456,
    "objections": [
      {
        "id": 1,
        "category_id": 1,
        "category_text": "Price/Budget",
        "objection_text": "I don't understand why I was charged this amount",
        "overcome": true,
        "speaker_id": "SPEAKER_02",
        "timestamp": 45.0,
        "severity": "low",
        "confidence_score": 0.88,
        "response_suggestions": [],
        "created_at": "2025-12-08T11:00:00Z"
      }
    ],
    "total_count": 1
  },
  "qualification": {
    "call_id": 456,
    "bant_scores": {
      "budget": 0.0,
      "authority": 0.0,
      "need": 0.0,
      "timeline": 0.0
    },
    "overall_score": 0.0,
    "qualification_status": "unqualified",
    "decision_makers": [],
    "urgency_signals": [],
    "budget_indicators": [],
    "confidence_score": 0.85,
    "booking_status": "not_booked",
    "call_outcome_category": "qualified_but_unbooked",
    "appointment_confirmed": false,
    "appointment_date": null,
    "appointment_type": null,
    "service_requested": null,
    "service_not_offered_reason": null,
    "follow_up_required": true,
    "follow_up_reason": "Customer requested follow-up to confirm understanding",
    "created_at": "2025-12-08T11:00:00Z"
  },
  "opportunity_analysis": {
    "call_id": 456,
    "risk_assessment": {
      "level": "low",
      "score": 10,
      "risk_factors": [],
      "positive_factors": [
        "Issue resolved successfully",
        "Customer satisfied",
        "Professional service delivery"
      ],
      "mitigation_strategies": [],
      "recommendation": "No risks identified. Continue providing excellent customer service."
    },
    "missed_opportunities": [],
    "created_at": "2025-12-08T11:00:00Z"
  },
  "created_at": "2025-12-08T11:00:00Z",
  "completed_at": "2025-12-08T11:00:00Z"
}
```

### Key Differences Between Roles

| Aspect | Sales Rep | Customer Rep |
|--------|-----------|--------------|
| **Qualification** | Full BANT scoring, booking status | Minimal/no qualification (service calls) |
| **Compliance** | Sales SOP stages (discovery, proposal, closing) | Customer service SOP stages (greeting, listening, resolution) |
| **Objections** | Sales objections (price, timing, authority) | Service objections (billing, service quality) |
| **Outcome** | Booking/appointment focused | Issue resolution focused |
| **Opportunity Analysis** | Revenue opportunities (upsell, cross-sell) | Service improvement opportunities |

---

## Meeting Segmentation Payload

### Endpoint

**POST** `/api/v1/meeting-segmentation/analyze`  
**GET** `/api/v1/meeting-segmentation/analysis/{call_id}`

**Headers**:
- `Authorization: Bearer <JWT_TOKEN>` (required)
- `X-Company-ID: <company_id>` (required)

### Request Payload

```json
{
  "call_id": 789,
  "analysis_type": "full" | "quick"
}
```

### Response Payload

```json
{
  "success": true,
  "call_id": 789,
  "part1": {
    "start_time": 0.0,
    "end_time": 900.0,
    "duration": 900.0,
    "content": "Rep introduced himself and built rapport with customer. Discussed customer's needs and current situation. Asked discovery questions about roof condition and previous repairs. Customer shared information about recent storm damage and leak location.",
    "key_points": [
      "Rapport building and introductions",
      "Discovery questions about roof condition",
      "Customer shared storm damage details",
      "Identified leak location"
    ]
  },
  "part2": {
    "start_time": 900.0,
    "end_time": 1800.0,
    "duration": 900.0,
    "content": "Rep presented repair options and pricing. Discussed materials and timeline. Addressed customer's price concerns. Rep used closing techniques and secured appointment booking for tomorrow at 2 PM.",
    "key_points": [
      "Presented repair options and pricing",
      "Addressed price objections",
      "Used closing techniques",
      "Secured appointment booking"
    ]
  },
  "segmentation_confidence": 0.92,
  "transition_point": 900.0,
  "transition_indicators": [
    "Rep shifted from discovery to proposal",
    "Customer asked 'How much will this cost?'",
    "Rep began presenting solutions"
  ],
  "meeting_structure_score": 4,
  "call_type": "sales_appointment",
  "created_at": "2025-12-08T12:00:00Z"
}
```

### Status Endpoint Response

**GET** `/api/v1/meeting-segmentation/status/{call_id}`

```json
{
  "success": true,
  "call_id": 789,
  "has_segmentation_analysis": true,
  "segmentation_analysis_available": true,
  "part1_duration": 900.0,
  "part2_duration": 900.0,
  "meeting_structure_score": 4,
  "created_at": "2025-12-08T12:00:00Z",
  "status": "completed"
}
```

---

## Ask Otto API Testing

### Normal API (Non-Streaming)

#### Endpoint

**POST** `/api/v1/ask-otto/query`

#### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | ✅ Yes | `Bearer <JWT_TOKEN>` |
| `X-Company-ID` | ✅ Yes | Company ID |
| `X-Target-Role` | 🟡 Optional | `sales_rep` (default) or `customer_rep` |

#### Request Payload

```json
{
  "question": "What are my top objections this month?",
  "conversation_id": "5a00bcc7-d1a1-407d-9511-2a7a9422be69",
  "context": {}
}
```

#### Response Payload

```json
{
  "success": true,
  "query_id": "6fb77d39-3524-42f8-87e4-66a14db5457b",
  "conversation_id": "5a00bcc7-d1a1-407d-9511-2a7a9422be69",
  "question": "What are my top objections this month?",
  "answer": "Your top objections this month are price-related, with 27% of calls citing 'price too high' as a concern. This is a 12% increase from the previous period, making it a key area to address.\n\nHere are some key insights:\n* 'Price too high' objections account for 27% of calls, up 12% from last period\n* 'Need to talk to spouse' objections make up 20% of calls, down 5% from last period\n* 'Timeline too long' objections represent 16% of calls, up 8% from last period\n\n**Next Steps:**\n- Review your pricing strategy to see if there are opportunities to offer more competitive rates or flexible payment plans\n- Develop targeted responses to address price concerns and practice handling these objections to improve your conversion rates\n- Consider adjusting your sales approach to better manage customer expectations around timelines and spur-of-the-moment decisions.",
  "confidence": 0.7,
  "sources": [
    {
      "type": "database",
      "title": "Top Objections Data (2025-11-08T07:13:02Z to 2025-12-08T07:13:02Z)",
      "reference": "get_top_objections",
      "record_count": 3,
      "confidence": 0.9
    }
  ],
  "suggested_follow_ups": [
    "What strategies can I use to address price-related objections?",
    "How can I effectively communicate the value of our product to justify the price?",
    "Are there any pricing tiers or discounts that I can offer to alleviate 'price too high' concerns?"
  ],
  "metadata": {
    "query_type": "analytical",
    "intent": "objection_handling",
    "processing_time_ms": 1677,
    "node_timings": {
      "classify_query": 450,
      "check_permissions": 12,
      "fetch_analytics": 800,
      "synthesize_response": 415
    },
    "analytics_data_used": true,
    "search_results_used": false,
    "call_analysis_used": false
  }
}
```

#### Testing with curl

```bash
# Basic query
curl -X POST "https://otto.shunyalabs.ai/api/v1/ask-otto/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "X-Company-ID: company_abc" \
  -H "X-Target-Role: sales_rep" \
  -d '{
    "question": "What are my top objections this month?",
    "conversation_id": null,
    "context": {}
  }'

# With conversation context
curl -X POST "https://otto.shunyalabs.ai/api/v1/ask-otto/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "X-Company-ID: company_abc" \
  -H "X-Target-Role: customer_rep" \
  -d '{
    "question": "How should I handle price objections?",
    "conversation_id": "5a00bcc7-d1a1-407d-9511-2a7a9422be69",
    "context": {}
  }'
```

#### Testing with Python

```python
import requests
import json

url = "https://otto.shunyalabs.ai/api/v1/ask-otto/query"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer <JWT_TOKEN>",
    "X-Company-ID": "company_abc",
    "X-Target-Role": "sales_rep"
}
payload = {
    "question": "What are my top objections this month?",
    "conversation_id": None,
    "context": {}
}

response = requests.post(url, headers=headers, json=payload)
print(json.dumps(response.json(), indent=2))
```

---

### SSE Streaming API

#### Endpoint

**POST** `/api/v1/ask-otto/query-stream`

#### Headers

Same as normal API.

#### Request Payload

Same as normal API.

#### Response Format (SSE)

The response is a Server-Sent Events (SSE) stream with the following event types:

| Event Type | Description | Data Structure |
|------------|-------------|----------------|
| `start` | Query processing started | `{query_id, conversation_id, question}` |
| `classification` | Query classified | `{query_type, intent, entities, ...}` |
| `data_fetched` | Data sources retrieved | `{sources: count}` |
| `answer_start` | Answer generation started | `{}` |
| `token` | Token chunk (streamed) | `{content: "token text"}` |
| `answer_complete` | Answer generation complete | `{full_answer: "complete answer"}` |
| `metadata` | Response metadata | `{confidence, sources, suggested_follow_ups, ...}` |
| `done` | Stream complete | `{query_id, conversation_id}` |
| `error` | Error occurred | `{error, message, code}` |

#### SSE Event Examples

```
event: start
data: {"query_id":"6fb77d39-3524-42f8-87e4-66a14db5457b","conversation_id":"5a00bcc7-d1a1-407d-9511-2a7a9422be69","question":"What are my top objections this month?"}

event: classification
data: {"query_type":"analytical","intent":"objection_handling","entities":{"date_range":{"start":"2025-11-08","end":"2025-12-08"}},"confidence":0.95}

event: data_fetched
data: {"sources":1}

event: answer_start
data: {}

event: token
data: {"content":"Your top objections"}

event: token
data: {"content":" this month"}

event: token
data: {"content":" are price-related"}

event: token
data: {"content":", with 27% of calls"}

event: token
data: {"content":" citing 'price too high'"}

... (more token events) ...

event: answer_complete
data: {"full_answer":"Your top objections this month are price-related, with 27% of calls citing 'price too high' as a concern..."}

event: metadata
data: {"confidence":0.7,"sources":[{"type":"database","title":"Top Objections Data","reference":"get_top_objections","record_count":3,"confidence":0.9}],"suggested_follow_ups":["What strategies can I use to address price-related objections?","How can I effectively communicate the value of our product?","Are there any pricing tiers or discounts?"],"processing_time_ms":1677}

event: done
data: {"query_id":"6fb77d39-3524-42f8-87e4-66a14db5457b","conversation_id":"5a00bcc7-d1a1-407d-9511-2a7a9422be69"}
```

#### Testing with curl

```bash
# Basic streaming test
curl -N -X POST "https://otto.shunyalabs.ai/api/v1/ask-otto/query-stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "X-Company-ID: company_abc" \
  -H "X-Target-Role: sales_rep" \
  -d '{
    "question": "What are my top objections this month?",
    "conversation_id": null,
    "context": {}
  }'
```

**Note**: The `-N` flag disables buffering for real-time streaming.

#### Testing with Python

```python
import requests
import json

url = "https://otto.shunyalabs.ai/api/v1/ask-otto/query-stream"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer <JWT_TOKEN>",
    "X-Company-ID": "company_abc",
    "X-Target-Role": "sales_rep"
}
payload = {
    "question": "What are my top objections this month?",
    "conversation_id": None,
    "context": {}
}

response = requests.post(url, headers=headers, json=payload, stream=True)

current_event = None
for line in response.iter_lines():
    if line:
        line_str = line.decode('utf-8')
        if line_str.startswith('event:'):
            current_event = line_str.split(':', 1)[1].strip()
        elif line_str.startswith('data:'):
            data_str = line_str.split(':', 1)[1].strip()
            try:
                data = json.loads(data_str)
                if current_event == 'token':
                    print(data.get('content', ''), end='', flush=True)
                elif current_event == 'answer_complete':
                    print(f"\n\n[Complete Answer]:\n{data.get('full_answer', '')}")
                elif current_event == 'metadata':
                    print(f"\n\n[Metadata]:\n{json.dumps(data, indent=2)}")
                elif current_event == 'done':
                    print("\n[Stream complete]")
                    break
                elif current_event == 'error':
                    print(f"\n[Error]: {data.get('message', 'Unknown error')}")
                    break
            except json.JSONDecodeError:
                pass
```

#### Testing with HTML Test Page

**URL**: `https://otto.shunyalabs.ai/static/test-sse.html`

**Features**:
- Interactive UI for testing streaming endpoints
- Real-time token display
- Event log showing all SSE events
- Metadata visualization
- Cancel button to stop the stream
- JWT token saved in localStorage

**Usage**:
1. Open the URL in your browser
2. Paste your JWT token
3. Enter a question
4. Click "Ask Otto" or press Enter
5. Watch the answer stream in real-time

#### Testing with JavaScript/Fetch API

```javascript
const response = await fetch('/api/v1/ask-otto/query-stream', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${jwtToken}`,
        'X-Company-ID': 'company_abc',
        'X-Target-Role': 'sales_rep'
    },
    body: JSON.stringify({
        question: 'What are my top objections this month?',
        conversation_id: null,
        context: {}
    })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = '';

while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop(); // Keep incomplete line in buffer
    
    let currentEvent = null;
    for (const line of lines) {
        if (line.startsWith('event:')) {
            currentEvent = line.substring(6).trim();
        } else if (line.startsWith('data:')) {
            const data = JSON.parse(line.substring(5).trim());
            if (currentEvent === 'token') {
                // Append token to answer
                document.getElementById('answer').textContent += data.content;
            } else if (currentEvent === 'done') {
                console.log('Stream complete');
            }
        }
    }
}
```

---

## Testing Checklist

### Complete Analysis API

- [ ] Test with `sales_rep` role
- [ ] Test with `customer_rep` role
- [ ] Verify all sections present (summary, compliance, objections, qualification, opportunity_analysis)
- [ ] Test with missing analysis sections
- [ ] Test with non-existent call_id (should return 404)
- [ ] Test with wrong company_id (should return 403)
- [ ] Test with invalid JWT token (should return 401)

### Meeting Segmentation API

- [ ] Test POST `/analyze` endpoint
- [ ] Test GET `/status/{call_id}` endpoint
- [ ] Test GET `/analysis/{call_id}` endpoint
- [ ] Verify part1 and part2 structure
- [ ] Verify transition_point and transition_indicators
- [ ] Test with CSR call (should return error - segmentation not applicable)
- [ ] Test with non-existent call_id

### Ask Otto Normal API

- [ ] Test with `sales_rep` role
- [ ] Test with `customer_rep` role
- [ ] Test analytical queries (e.g., "What are my top objections?")
- [ ] Test knowledge queries (e.g., "How should I handle price objections?")
- [ ] Test with conversation context
- [ ] Test permission denied scenarios
- [ ] Test error handling

### Ask Otto SSE Streaming API

- [ ] Test with `sales_rep` role
- [ ] Test with `customer_rep` role
- [ ] Verify all event types received (start, classification, data_fetched, answer_start, token, answer_complete, metadata, done)
- [ ] Verify tokens stream in real-time
- [ ] Test cancel/abort functionality
- [ ] Test error events
- [ ] Test with HTML test page
- [ ] Test with curl
- [ ] Test with Python script
- [ ] Test with JavaScript/Fetch API

---

## Common Issues and Solutions

### Issue 1: SSE Stream Not Working

**Symptoms**: No tokens received, connection closes immediately

**Solutions**:
- Ensure `-N` flag is used with curl (disables buffering)
- Check that `stream=True` is set in Python requests
- Verify browser supports EventSource API
- Check network tab for connection errors

### Issue 2: Missing target_role Header

**Symptoms**: Defaults to `sales_rep` when should be `customer_rep`

**Solutions**:
- Explicitly set `X-Target-Role: customer_rep` header
- Verify JWT token has correct role claim
- Check RBAC permissions

### Issue 3: Webhook Signature Validation Fails

**Symptoms**: Otto Backend returns 401 on webhook

**Solutions**:
- Verify HMAC secret matches between Shunya and Otto Backend
- Check timestamp format (epoch milliseconds)
- Ensure payload JSON is sorted by keys
- Verify signature is hex-encoded

### Issue 4: Error Envelope Not Parsed Correctly

**Symptoms**: Error details not accessible

**Solutions**:
- Check error structure matches canonical format
- Verify `success: false` is present
- Ensure `error` object contains all required fields
- Check error_code is in UPPER_SNAKE_CASE

---

**Document Maintained By**: Shunya Team (ottoai-rag)  
**Last Updated**: 2025-12-08  
**Next Review**: 2026-01-08

