# Pending Shunya Confirmations

**Date**: 2025-11-24  
**Status**: ⏸️ Waiting on Shunya Team

---

## Overview

This document tracks items that require confirmation or samples from Shunya Labs before full implementation can proceed. All items have been scaffolded in code but are disabled or use placeholder values until Shunya confirms.

---

## Pending Items

### 1. Outcome Enum Values

**Status**: ⏸️ Waiting for final enum values from Shunya

**Description**: Shunya may return outcome classifications with slightly different naming conventions than Otto's internal enums. We need to confirm exact strings.

**Expected Values** (from Responsibility Matrix):
- CSR calls: `qualified_and_booked`, `qualified_not_booked`, `qualified_service_not_offered`, `not_qualified`
- Sales visits: `won`, `lost`, `pending_decision`, `no_show`, `rescheduled`

**Current Implementation**:
- Outcome mapping in `shunya_integration_service.py` (lines 574-579, 786-792)
- Uses normalized values from `ShunyaResponseNormalizer`

**Action Required**:
- [ ] Shunya confirms exact outcome string values
- [ ] Update outcome mapping if needed
- [ ] Test with real Shunya responses

**Code Location**:
- `app/services/shunya_integration_service.py` → `_process_shunya_analysis_for_call()` (lines 574-579)
- `app/services/shunya_integration_service.py` → `_process_shunya_analysis_for_visit()` (lines 786-792)
- `app/services/shunya_adapters.py` → Outcome adapter (placeholder)

---

### 2. Pending Actions Free-String Handling

**Status**: ✅ **RESOLVED** (2025-01-28)

**Resolution**: Shunya confirmed that pending actions use free-string action types (e.g., "follow up tomorrow", "send technician"). Shunya may later freeze these into enums, but we must be tolerant of arbitrary strings.

**Implementation**:
- ✅ Contract updated in `app/schemas/shunya_contracts.py` (`ShunyaPendingAction` - action_type accepts free strings)
- ✅ Adapter updated in `app/services/shunya_adapters_v2.py` (`_adapt_pending_actions()` handles free-strings with graceful mapping)
- ✅ Mapping logic attempts to map common patterns to internal enums, falls back to generic/custom for unknown strings
- ✅ Tests added in `app/tests/shunya_integration/test_adapter_simulation.py`

**Code Location**:
- `app/schemas/shunya_contracts.py` → `ShunyaPendingAction` (documentation updated)
- `app/services/shunya_adapters_v2.py` → `_adapt_pending_actions()` (free-string handling)
- `docs/integrations/shunya/CHANGELOG_ASK_OTTO_ALIGNMENT.md` → Section 4

**Note**: Adapters gracefully handle arbitrary action type strings, mapping known patterns when possible and falling back to generic types for unknown strings.

---

### 2b. Objection Label Taxonomy

**Status**: ⏸️ Waiting for Shunya objection taxonomy document

**Description**: Shunya may categorize objections into a standardized taxonomy. We need the complete list of objection categories/labels.

**Expected Structure**:
```json
{
  "objections": [
    {
      "objection_text": "...",
      "objection_label": "price",  // or "timing", "trust", etc.
      "severity": "high" | "medium" | "low",
      "resolved": false
    }
  ]
}
```

**Current Implementation**:
- Objections stored in `CallAnalysis.objections` as JSON array
- No standardized taxonomy yet
- Search endpoint supports filtering by `objection_labels` (expects list of strings)

**Action Required**:
- [ ] Shunya provides complete objection label taxonomy
- [ ] Update `ShunyaResponseNormalizer` to handle standardized labels
- [ ] Add objection label validation if needed
- [ ] Update search endpoint filters to match taxonomy

**Code Location**:
- `app/services/shunya_response_normalizer.py` → `_normalize_objections()` (lines 105-137)
- `app/routes/ai_search.py` → Objection label filtering (if exists)
- `app/services/shunya_adapters.py` → Objection adapter (placeholder)

---

### 3. Webhook Payload Structure & Security

**Status**: ✅ **RESOLVED** (2025-01-28)

**Resolution**: Final Shunya contracts confirmed and implemented:
- **Headers**: `X-Shunya-Signature`, `X-Shunya-Timestamp` (epoch milliseconds), `X-Shunya-Task-Id`
- **Signature Formula**: `HMAC_SHA256(secret, "{timestamp}.{raw_body_bytes}")`
- **Delivery Guarantees**: At-least-once delivery with exponential backoff retries (30 min window)

**Implementation**:
- ✅ Webhook handler updated in `app/routes/shunya_webhook.py` (uses X-Shunya-* headers)
- ✅ Signature verification updated in `app/utils/shunya_webhook_security.py` (epoch milliseconds, correct formula)
- ✅ Tests updated in `app/tests/test_shunya_webhook_security.py`

**Code Location**:
- `app/routes/shunya_webhook.py` → `shunya_webhook()` endpoint
- `app/utils/shunya_webhook_security.py` → Signature verification (epoch millis format)
- `docs/integrations/shunya/CHANGELOG_ASK_OTTO_ALIGNMENT.md` → Complete changelog

**Note**: Webhook payload structure remains the same (shunya_job_id, status, result, error, company_id). Security headers and signature formula were updated to match final Shunya contract.

---

### 4. Segmentation Output Shape

**Status**: ✅ **RESOLVED** (2025-01-28)

**Resolution**: Final segmentation structure confirmed and implemented:
```json
{
  "success": true,
  "call_id": 3070,
  "part1": {
    "start_time": 0,
    "end_time": 240,
    "duration": 240,
    "content": "Introduction, agenda setting, discovery, rapport building",
    "key_points": ["Introduction", "Agenda setting", "Discovery questions"]
  },
  "part2": {
    "start_time": 240,
    "end_time": 420,
    "duration": 180,
    "content": "Presentation, proposal, closing, next steps",
    "key_points": ["Presentation of solution", "Scheduling of appointment"]
  },
  "segmentation_confidence": 0.8,
  "transition_point": 240,
  "transition_indicators": ["Scheduling of appointment", "Confirmation of details"],
  "meeting_structure_score": 4,
  "call_type": "sales_appointment",
  "created_at": null
}
```

**Implementation**:
- ✅ Contract updated in `app/schemas/shunya_contracts.py` (`ShunyaMeetingSegmentation`, `ShunyaSegmentationPart`)
- ✅ Normalizer updated in `app/services/shunya_response_normalizer.py` (handles new structure)
- ✅ Adapter updated in `app/services/shunya_adapters_v2.py` (`ShunyaSegmentationAdapter`)
- ✅ Tests updated in `app/tests/shunya_integration/test_adapter_simulation.py`

**Code Location**:
- `app/schemas/shunya_contracts.py` → `ShunyaMeetingSegmentation`, `ShunyaSegmentationPart`
- `app/services/shunya_response_normalizer.py` → `normalize_meeting_segmentation()`
- `app/services/shunya_adapters_v2.py` → `ShunyaSegmentationAdapter`
- `docs/integrations/shunya/CHANGELOG_ASK_OTTO_ALIGNMENT.md` → Section 3

**Note**: Backward compatible - handles both new structure (content, key_points) and legacy fields (summary, transcript).

---

### 5. Error Envelope Format

**Status**: ✅ **RESOLVED** (2025-01-28)

**Resolution**: Canonical error envelope format confirmed and implemented:
```json
{
  "success": false,
  "error": {
    "error_code": "RATE_LIMIT",
    "error_type": "throttling",
    "message": "Too many requests",
    "retryable": true,
    "details": {"limit": 100},
    "timestamp": "2025-11-28T10:15:42.123Z",
    "request_id": "abc-123"
  }
}
```

**Implementation**:
- ✅ Error parsing added in `app/services/uwc_client.py` (`ShunyaAPIError` exception, `_parse_shunya_error_envelope()` method)
- ✅ Contract updated in `app/schemas/shunya_contracts.py` (`ShunyaErrorEnvelope` model)
- ✅ Error handling respects `retryable` flag and preserves `request_id` for observability
- ✅ Tests added in `app/tests/shunya_integration/test_uwc_client_errors.py`

**Code Location**:
- `app/services/uwc_client.py` → `ShunyaAPIError`, `_parse_shunya_error_envelope()`, error handling in `_make_request()`
- `app/schemas/shunya_contracts.py` → `ShunyaErrorEnvelope`
- `docs/integrations/shunya/CHANGELOG_ASK_OTTO_ALIGNMENT.md` → Section 2

**Note**: Backward compatible - handles both canonical format and legacy error structures gracefully.

---

## Adapter Scaffolding

All pending items are fully scaffolded with a three-layer architecture:

### Layer 1: Contract Stubs (`app/schemas/shunya_contracts.py`)

Pydantic models defining expected Shunya response shapes:
- `ShunyaCSRCallAnalysis`: Complete CSR analysis structure
- `ShunyaVisitAnalysis`: Visit analysis structure
- `ShunyaMeetingSegmentation`: Segmentation structure
- `ShunyaWebhookPayload`: Webhook payload structure
- `ShunyaErrorEnvelope`: Error envelope structure
- Supporting models for objections, qualification, compliance, etc.

**When Shunya confirms**: Update Pydantic model fields with final names/types.

### Layer 2: Mapping Tables (`app/services/shunya_mappings.py`)

Mapping functions translating Shunya values → Otto enums:
- `map_shunya_csr_outcome_to_lead_status()`: CSR outcomes → LeadStatus
- `map_shunya_visit_outcome_to_appointment_outcome()`: Visit outcomes → AppointmentOutcome
- `normalize_shunya_objection_label()`: Objection labels (pass-through)
- `map_shunya_action_to_task_assignee()`: Action types → TaskAssignee
- `map_shunya_opportunity_to_signal_type()`: Opportunities → SignalType

**When Shunya confirms**: Update mapping dictionaries with final enum values.

### Layer 3: Adapter Orchestration (`app/services/shunya_adapters_v2.py`)

Adapters that orchestrate contract validation + mapping:
- `ShunyaCSRCallAdapter`: CSR analysis → Otto format
- `ShunyaVisitAdapter`: Visit analysis → Otto format
- `ShunyaSegmentationAdapter`: Segmentation → Otto format
- `ShunyaWebhookAdapter`: Webhook payload extraction
- `ShunyaErrorAdapter`: Error normalization

**When Shunya confirms**: Adapters automatically work with updated contracts/mappings.

See **`ADAPTER_DESIGN.md`** for complete architecture documentation.

---

## Testing Scaffolding

Tests are scaffolded in `tests/shunya_integration/test_pending_flows.py`:

- Tests for outcome enum translation
- Tests for objection label taxonomy
- Tests for webhook payload variations
- Tests for segmentation field expansion
- Tests for error envelope parsing

All tests are currently skipped with `@pytest.mark.skip(reason="Waiting for Shunya confirmation")`.

---

## Next Steps

1. **Wait for Shunya confirmations** on all pending items above
2. **Update contracts** (`app/schemas/shunya_contracts.py`) with final field names/types
3. **Update mappings** (`app/services/shunya_mappings.py`) with final enum values
4. **Enable tests** by removing skip markers in:
   - `app/tests/shunya_integration/test_pending_flows.py`
   - `app/tests/shunya_integration/test_adapter_simulation.py`
5. **Run integration tests** with real Shunya responses
6. **Update this document** with confirmation dates and implementation status

---

## 📚 Related Documentation

- **Adapter Design**: `ADAPTER_DESIGN.md` - Complete architecture documentation
- **Adapter Layer Complete**: `ADAPTER_LAYER_COMPLETE.md` - Implementation summary
- **Gap Analysis**: `INTEGRATION_HARDENING_GAP_ANALYSIS.md`
- **Hardening Summary**: `INTEGRATION_HARDENING_SUMMARY.md`

---

## 🔧 Implementation Files

All scaffolding is complete and ready:

- **Contracts**: `app/schemas/shunya_contracts.py`
- **Mappings**: `app/services/shunya_mappings.py`
- **Adapters**: `app/services/shunya_adapters_v2.py`
- **Tests**: `app/tests/shunya_integration/test_adapter_simulation.py`

**Status**: ✅ **Plug-and-Play Ready** - Just update contracts/mappings when Shunya confirms.

---

**Last Updated**: 2025-01-28

---

## ✅ Recently Resolved Items (2025-01-28)

The following items have been resolved based on final Shunya integration contracts:

1. ✅ **Webhook Security** - Headers (X-Shunya-*), signature formula, epoch milliseconds timestamp
2. ✅ **Error Envelope Format** - Canonical error envelope structure with error_code, error_type, retryable, request_id
3. ✅ **Segmentation Output Shape** - Part1/Part2 structure with content, key_points, transition_indicators, call_type
4. ✅ **Pending Actions Free-String** - Free-string action types with graceful mapping

See `docs/integrations/shunya/CHANGELOG_ASK_OTTO_ALIGNMENT.md` for complete details of all changes.

