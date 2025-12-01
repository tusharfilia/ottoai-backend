# Changelog: Ask Otto Integration Alignment

**Date**: 2025-01-28  
**Status**: ✅ **Complete - Ready for Testing**

---

## Overview

This changelog documents all changes made to align the Otto backend with the final Shunya (Ask Otto engine) integration contracts. All changes are **internal-only** and do not modify public Otto API responses.

---

## 1. Webhook Security Alignment

### Changes Made

**File**: `app/utils/shunya_webhook_security.py`

- Updated to use **X-Shunya-*** headers (replacing X-UWC-*):
  - `X-Shunya-Signature`: HMAC-SHA256 hex digest
  - `X-Shunya-Timestamp`: Epoch milliseconds (string format)
  - `X-Shunya-Task-Id`: Task ID for idempotency tracking
  
- Updated signature formula to match Shunya contract:
  - Format: `HMAC_SHA256(secret, "{timestamp}.{raw_body_bytes}")`
  - Timestamp is raw string value (epoch milliseconds)
  - Raw body is exact bytes (no decoding/encoding)
  - Digest is lowercase hex string
  
- Updated timestamp validation:
  - Now expects epoch milliseconds instead of ISO 8601
  - Validation window: 5 minutes (300 seconds) for replay attack prevention
  - Constant-time comparison maintained

**File**: `app/routes/shunya_webhook.py`

- Updated route handler to accept new header names:
  - `x_shunya_signature` (was `x_uwc_signature`)
  - `x_shunya_timestamp` (was `x_uwc_timestamp`)
  - `x_shunya_task_id` (new, optional, for idempotency logging)

- Updated documentation to reflect:
  - Webhook delivery guarantees (at-least-once)
  - Idempotency handling via `ShunyaJob` + output hash
  - Expected header format

### Behavior Changes

- **Breaking**: Webhook signature verification now expects epoch milliseconds instead of ISO 8601 timestamps
- **Breaking**: Header names changed from `X-UWC-*` to `X-Shunya-*`
- **Non-breaking**: Existing idempotency logic unchanged
- **Non-breaking**: Tenant isolation checks unchanged

### Testing Notes

- Webhook signature tests should use epoch milliseconds format
- Header name updates required in webhook test fixtures
- Verify constant-time comparison still prevents timing attacks

---

## 2. Error Envelope Handling Alignment

### Changes Made

**File**: `app/services/uwc_client.py`

- Added `ShunyaAPIError` exception class:
  - Captures canonical error envelope fields:
    - `error_code`: Machine-readable error code
    - `error_type`: Error type category
    - `message`: Human-readable message
    - `retryable`: Boolean indicating if error is retryable
    - `details`: Additional error context
    - `timestamp`: When error occurred
    - `request_id`: Correlation ID for tracing
  
- Added `_parse_shunya_error_envelope()` method:
  - Parses canonical error envelope format:
    ```json
    {
      "success": false,
      "error": {
        "error_code": "string",
        "error_type": "string",
        "message": "string",
        "retryable": true,
        "details": {},
        "timestamp": "2025-11-28T10:15:42.123Z",
        "request_id": "uuid"
      }
    }
    ```
  - Graceful handling of missing fields
  - Supports legacy error formats (backward compatible)

- Updated `_make_request()` error handling:
  - Checks for canonical error envelope in all responses (including 200 with `success: false`)
  - Maps errors to appropriate exception types:
    - 401/403 → `UWCAuthenticationError`
    - 429 → `UWCRateLimitError`
    - 5xx → `UWCServerError`
    - Others → `ShunyaAPIError` or appropriate type
  - Honors `retryable` flag for retry logic
  - Preserves `request_id` for observability

**File**: `app/schemas/shunya_contracts.py`

- Updated `ShunyaErrorEnvelope` model:
  - Added `success` field (boolean)
  - Added direct access to error object fields for convenience
  - Added `error_code`, `error_type`, `retryable`, `request_id` fields
  - Maintained backward compatibility with legacy fields

### Behavior Changes

- **Non-breaking**: Enhanced error parsing and logging
- **Non-breaking**: Better observability via `request_id` capture
- **Non-breaking**: Retry logic now respects `retryable` flag
- **Non-breaking**: Existing exception types maintained for backward compatibility

### Testing Notes

- Test error envelope parsing with canonical format
- Verify retry logic respects `retryable: false` flag
- Confirm `request_id` is logged for tracing

---

## 3. Segmentation Contract Alignment

### Changes Made

**File**: `app/schemas/shunya_contracts.py`

- Updated `ShunyaSegmentationPart` model:
  - Added new fields: `start_time`, `end_time`, `duration`, `content`, `key_points`
  - Maintained legacy fields for backward compatibility
  - All fields optional for graceful degradation

- Updated `ShunyaMeetingSegmentation` model:
  - Added `success` field (boolean)
  - Updated `call_id` to accept `int | str`
  - Added new fields:
    - `transition_indicators`: List of transition indicators
    - `call_type`: Type of call (e.g., "sales_appointment")
    - `created_at`: Creation timestamp
  - Updated field descriptions to match final contract
  - Maintained legacy fields for backward compatibility

**File**: `app/services/shunya_response_normalizer.py`

- Updated `normalize_meeting_segmentation()`:
  - Handles new structure with `content` and `key_points`
  - Falls back to legacy `summary`/`transcript` if needed
  - Extracts `transition_indicators`, `call_type`, `created_at`
  - Preserves all new fields in normalized output

**File**: `app/services/shunya_adapters_v2.py`

- Updated `ShunyaSegmentationAdapter.adapt()`:
  - Handles new structure with `success`, `call_id`, `call_type`, etc.
  - Maps both new and legacy field names
  - Preserves `transition_indicators` and other new fields

- Updated `_adapt_segmentation_part()`:
  - Handles both new structure (`content`, `key_points`) and legacy (`summary`, `transcript`)
  - Maps `duration` from new structure or `duration_seconds` from legacy
  - Graceful fallback to legacy fields

### Behavior Changes

- **Non-breaking**: Supports new segmentation structure while maintaining backward compatibility
- **Non-breaking**: Enhanced segmentation data with transition indicators and call type
- **Non-breaking**: Graceful degradation if Shunya omits fields

### Testing Notes

- Test with new segmentation structure (Part1/Part2 with content/key_points)
- Verify backward compatibility with legacy structure
- Confirm graceful handling of missing fields

---

## 4. Pending Actions Free-String Handling

### Changes Made

**File**: `app/schemas/shunya_contracts.py`

- Updated `ShunyaPendingAction` model documentation:
  - Clarified that `action_type` accepts **free-string** values
  - Examples: "follow up tomorrow", "send technician"
  - Noted that adapters must map common patterns with graceful fallback

**File**: `app/services/shunya_adapters_v2.py`

- Updated `_adapt_pending_actions()`:
  - Handles free-string `action_type` values
  - Attempts to map common patterns (e.g., "follow up tomorrow", "send technician")
  - Adds `is_known_pattern` flag to indicate if action type is recognized
  - Preserves original free-string value for future reference
  - Graceful fallback to generic/custom type for unknown strings

### Behavior Changes

- **Non-breaking**: Supports arbitrary action type strings from Shunya
- **Non-breaking**: Maps known patterns to internal enums when possible
- **Non-breaking**: Graceful fallback for unknown action types

### Testing Notes

- Test with known action types (should map correctly)
- Test with unknown/free-string action types (should handle gracefully)
- Verify `is_known_pattern` flag is set correctly

---

## 5. Documentation Updates

### Files to Update

- `docs/integrations/shunya/PENDING_CONFIRMATION.md`: Mark resolved items
- `docs/integrations/shunya/INTEGRATION_HARDENING_GAP_ANALYSIS.md`: Mark resolved gaps
- `docs/integrations/shunya/ADAPTER_DESIGN.md`: Update with new contract details
- `docs/integrations/shunya/INTEGRATION_HARDENING_SUMMARY.md`: Update summary

### New Documentation

- This changelog: `CHANGELOG_ASK_OTTO_ALIGNMENT.md`

### Documentation Status

- ✅ Changelog created
- ⏳ Other docs to be updated in follow-up PR

---

## 6. Summary of Files Changed

### Core Implementation Files

1. **`app/utils/shunya_webhook_security.py`**
   - Webhook signature verification with X-Shunya-* headers
   - Epoch milliseconds timestamp handling
   - Updated signature formula

2. **`app/routes/shunya_webhook.py`**
   - Updated route handler to accept new header names
   - Added X-Shunya-Task-Id header support

3. **`app/services/uwc_client.py`**
   - Added `ShunyaAPIError` exception class
   - Added `_parse_shunya_error_envelope()` method
   - Updated error handling to parse canonical error envelope
   - Honors `retryable` flag in retry logic

4. **`app/schemas/shunya_contracts.py`**
   - Updated `ShunyaErrorEnvelope` model
   - Updated `ShunyaSegmentationPart` model
   - Updated `ShunyaMeetingSegmentation` model
   - Updated `ShunyaPendingAction` documentation

5. **`app/services/shunya_response_normalizer.py`**
   - Updated `normalize_meeting_segmentation()` for new structure

6. **`app/services/shunya_adapters_v2.py`**
   - Updated `_adapt_pending_actions()` for free-string handling
   - Updated `ShunyaSegmentationAdapter` for new structure
   - Updated `_adapt_segmentation_part()` for new fields

### Documentation Files

7. **`docs/integrations/shunya/CHANGELOG_ASK_OTTO_ALIGNMENT.md`** (this file)
   - Complete changelog of all changes

---

## 7. Testing Checklist

### Webhook Security

- [ ] Test webhook signature verification with X-Shunya-* headers
- [ ] Test epoch milliseconds timestamp validation
- [ ] Test replay attack prevention (5-minute window)
- [ ] Test constant-time comparison

### Error Envelope Handling

- [ ] Test canonical error envelope parsing
- [ ] Test retry logic with `retryable: false` flag
- [ ] Test `request_id` capture and logging
- [ ] Test backward compatibility with legacy error formats

### Segmentation

- [ ] Test new segmentation structure (Part1/Part2 with content/key_points)
- [ ] Test backward compatibility with legacy structure
- [ ] Test graceful handling of missing fields
- [ ] Test transition indicators and call type extraction

### Pending Actions

- [ ] Test known action type patterns (should map correctly)
- [ ] Test unknown/free-string action types (should handle gracefully)
- [ ] Test `is_known_pattern` flag

### Integration Tests

- [ ] End-to-end webhook processing with new headers
- [ ] Error handling with canonical error envelope
- [ ] Segmentation processing with new structure
- [ ] Pending actions processing with free strings

---

## 8. Breaking Changes

### Webhook Security (Breaking)

- **Header Names**: Changed from `X-UWC-*` to `X-Shunya-*`
  - Impact: External webhook configurations must be updated
  - Migration: Update Shunya webhook configuration to use new header names
  
- **Timestamp Format**: Changed from ISO 8601 to epoch milliseconds
  - Impact: Webhook timestamp validation now expects milliseconds
  - Migration: Shunya must send epoch milliseconds in `X-Shunya-Timestamp`

### Non-Breaking Changes

- Error envelope handling: Backward compatible
- Segmentation contract: Backward compatible (handles both new and legacy)
- Pending actions: Backward compatible (free-strings accepted)

---

## 9. Migration Guide

### For Webhook Configuration

1. Update webhook endpoint configuration in Shunya:
   - Use `X-Shunya-Signature` header (instead of `X-UWC-Signature`)
   - Use `X-Shunya-Timestamp` header with epoch milliseconds (instead of ISO 8601)
   - Optionally include `X-Shunya-Task-Id` header for idempotency tracking

2. Verify HMAC secret:
   - Ensure `UWC_HMAC_SECRET` environment variable is set
   - Verify signature formula: `HMAC_SHA256(secret, "{timestamp}.{raw_body_bytes}")`

### For Development/Testing

1. Update test fixtures:
   - Use epoch milliseconds in timestamp headers
   - Use X-Shunya-* header names
   - Include canonical error envelope in error test cases

2. Update integration tests:
   - Test with new segmentation structure
   - Test with free-string action types
   - Verify error envelope parsing

---

## 10. Next Steps

1. **Update remaining documentation**:
   - Mark resolved items in `PENDING_CONFIRMATION.md`
   - Update `INTEGRATION_HARDENING_GAP_ANALYSIS.md`
   - Update `ADAPTER_DESIGN.md` with new contract details

2. **Add/update tests**:
   - Webhook security tests with new headers
   - Error envelope parsing tests
   - Segmentation adapter tests with new structure
   - Pending actions free-string tests

3. **Coordinate with Shunya team**:
   - Confirm webhook header changes are implemented
   - Verify error envelope format is consistent
   - Test end-to-end integration

4. **Monitor in production**:
   - Watch for webhook signature verification failures
   - Monitor error envelope parsing logs
   - Track segmentation processing success rates

---

## 11. Notes

- All changes are **internal-only** - no public Otto API changes
- Backward compatibility maintained where possible
- Graceful degradation for missing/incomplete data
- All fields optional in contracts for resilience

---

**End of Changelog**


