# Shunya Webhook Security Implementation

**Date**: 2025-11-24  
**Status**: ✅ **Implementation Complete**

---

## ✅ **Implementation Summary**

Implemented HMAC-SHA256 signature verification for Shunya webhooks with full tenant isolation and security hardening.

### **New Files Created**

1. **`app/utils/shunya_webhook_security.py`**
   - `verify_shunya_webhook_signature()` - Core HMAC signature verification
   - `validate_shunya_webhook()` - Convenience wrapper with error handling
   - Custom exceptions: `InvalidSignatureError`, `MissingHeadersError`, `TimestampExpiredError`

2. **`app/tests/test_shunya_webhook_security.py`**
   - Comprehensive test suite for signature verification
   - Tests for valid signatures, invalid signatures, missing headers
   - Tests for body tampering, cross-tenant attacks, idempotency

### **Modified Files**

1. **`app/routes/shunya_webhook.py`**
   - Reads raw request body FIRST (before JSON parsing)
   - Verifies HMAC signature BEFORE any processing
   - Enhanced tenant isolation check (company_id must match job.company_id)
   - Returns 401 for invalid signatures
   - Returns 403 for cross-tenant violations
   - Manual JSON parsing from raw body bytes

---

## 🔒 **Security Features**

### **1. HMAC-SHA256 Signature Verification**

**Signature Format**:
```
signed_message = "{timestamp}.{raw_body_bytes}"
signature = hmac_sha256(UWC_HMAC_SECRET, signed_message)
```

**Headers Required**:
- `X-UWC-Signature`: HMAC-SHA256 hex digest
- `X-UWC-Timestamp`: ISO 8601 timestamp (e.g., "2025-11-24T10:30:00Z")

**Verification Process**:
1. Read raw request body bytes
2. Extract `X-UWC-Signature` and `X-UWC-Timestamp` headers
3. Construct signed message: `"{timestamp}.{raw_body}"`
4. Compute expected signature using `UWC_HMAC_SECRET`
5. Compare using constant-time comparison (`hmac.compare_digest()`)
6. Validate timestamp is within 5-minute window (prevents replay attacks)

**If Invalid**:
- Returns HTTP 401
- Response: `{"success": false, "error": "invalid_signature"}`
- **NO processing occurs** - webhook is rejected immediately

### **2. Tenant Isolation**

**Enforcement Points**:

1. **Webhook Payload Validation**:
   - `company_id` is REQUIRED in webhook payload
   - Missing `company_id` → HTTP 400

2. **Job Lookup**:
   - Jobs are looked up using tenant-scoped query
   - `get_job_by_shunya_id(db, company_id, shunya_job_id)` only searches within that company

3. **Company ID Matching**:
   - After job lookup, verify: `job.company_id == payload.company_id`
   - Mismatch → HTTP 403 (potential cross-tenant attack)
   - Logged as security violation

**Security Benefits**:
- Prevents cross-tenant data access
- Prevents cross-tenant job poisoning
- Ensures webhooks only affect the correct tenant's data

### **3. Replay Attack Prevention**

**Timestamp Validation**:
- Webhook timestamp must be within 5 minutes of current time
- Expired timestamps → `TimestampExpiredError` → HTTP 401
- Prevents replay of old webhooks

### **4. Constant-Time Comparison**

**Timing Attack Prevention**:
- Uses `hmac.compare_digest()` for signature comparison
- Prevents timing-based signature guessing attacks

---

## 📝 **Raw Body Access Implementation**

### **Challenge**

FastAPI's `request.json()` consumes the request body stream. Once consumed, the raw body bytes are no longer available. However, signature verification requires the **exact raw bytes** (not parsed JSON).

### **Solution**

Read raw body FIRST, then parse JSON manually:

```python
# Step 1: Read raw body BEFORE parsing JSON
raw_body = await request.body()

# Step 2: Verify signature using raw body
verify_shunya_webhook_signature(
    raw_body=raw_body,
    signature=x_uwc_signature,
    timestamp=x_uwc_timestamp,
)

# Step 3: Parse JSON manually from raw body bytes
payload = json.loads(raw_body.decode('utf-8'))
```

### **Why This Works**

- `await request.body()` reads the entire request body as bytes
- We store it in `raw_body` variable
- We can verify signature using raw bytes
- Then parse JSON from the same bytes using `json.loads()`
- FastAPI's `request.json()` is never called (which would consume the stream)

---

## 🧪 **Test Coverage**

### **Test Cases**

1. ✅ **Valid signature** → webhook processes successfully
2. ✅ **Invalid signature** → HTTP 401, no processing
3. ✅ **Missing signature header** → HTTP 401
4. ✅ **Missing timestamp header** → HTTP 401
5. ✅ **Expired timestamp** → HTTP 401 (replay attack prevention)
6. ✅ **Body tampering** → HTTP 401 (signature mismatch)
7. ✅ **Cross-tenant tampering** → HTTP 403 (company_id mismatch)
8. ✅ **Missing company_id** → HTTP 400
9. ✅ **Idempotency preserved** → already processed jobs return success without reprocessing

### **Test File**

`app/tests/test_shunya_webhook_security.py`

**Test Classes**:
- `TestSignatureVerification` - Signature verification tests
- `TestWebhookHandler` - Endpoint integration tests
- `TestTenantIsolation` - Tenant isolation tests
- `TestIdempotency` - Idempotency preservation tests

---

## 🚀 **Production Enablement Instructions**

### **1. Environment Variables**

Set the following environment variables in production:

```bash
# Required for webhook signature verification
UWC_HMAC_SECRET=<your_webhook_hmac_secret_key>

# Optional: Adjust timestamp window (default: 300 seconds / 5 minutes)
UWC_WEBHOOK_MAX_AGE_SECONDS=300

# Environment
ENVIRONMENT=production
```

**Important**: 
- `UWC_HMAC_SECRET` **MUST** match the secret Shunya uses to sign webhooks
- This secret should be **different** from other secrets (JWT secret, API keys)
- Store securely (environment variable, secrets manager)
- **Never** commit to version control

### **2. Shunya Configuration**

Ensure Shunya is configured to:

1. **Sign webhooks** using HMAC-SHA256
2. **Include headers**:
   - `X-UWC-Signature`: HMAC signature
   - `X-UWC-Timestamp`: ISO 8601 timestamp
3. **Include `company_id`** in webhook payload
4. **Use same secret** as `UWC_HMAC_SECRET` in Otto

### **3. Webhook URL**

Shunya should send webhooks to:
```
POST https://your-otto-domain.com/api/v1/shunya/webhook
```

### **4. Verification Steps**

1. **Test with valid signature**:
   ```bash
   # Generate test webhook with signature
   timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
   body='{"shunya_job_id":"test_job","company_id":"test_company","status":"completed"}'
   signed_message="${timestamp}.${body}"
   signature=$(echo -n "$signed_message" | openssl dgst -sha256 -hmac "$UWC_HMAC_SECRET" | cut -d' ' -f2)
   
   curl -X POST https://your-otto-domain.com/api/v1/shunya/webhook \
     -H "Content-Type: application/json" \
     -H "X-UWC-Signature: $signature" \
     -H "X-UWC-Timestamp: $timestamp" \
     -d "$body"
   ```

2. **Test with invalid signature** (should return 401):
   ```bash
   curl -X POST https://your-otto-domain.com/api/v1/shunya/webhook \
     -H "Content-Type: application/json" \
     -H "X-UWC-Signature: invalid_signature" \
     -H "X-UWC-Timestamp: $timestamp" \
     -d "$body"
   ```

3. **Monitor logs** for:
   - `"Shunya webhook signature verified successfully"` (success)
   - `"Invalid Shunya webhook signature"` (security violation)
   - `"Company ID mismatch"` (cross-tenant attack attempt)

### **5. Monitoring & Alerts**

Set up alerts for:
- **401 responses** on webhook endpoint (invalid signatures)
- **403 responses** on webhook endpoint (cross-tenant violations)
- **Missing `UWC_HMAC_SECRET`** in production (should never happen)

### **6. Gradual Rollout**

1. **Phase 1**: Deploy with signature verification **optional** (dev mode)
   - Verify webhooks are being received
   - Monitor logs for signature verification results
   - Ensure Shunya is sending correct headers

2. **Phase 2**: Enable signature verification for **one tenant**
   - Test end-to-end with real Shunya webhooks
   - Verify no false positives/negatives

3. **Phase 3**: Enable for **all tenants**
   - Monitor for any issues
   - Ensure Shunya is correctly signing all webhooks

### **7. Rollback Plan**

If signature verification causes issues:

1. **Temporary workaround**: Set `ENVIRONMENT=development` (signature optional)
2. **Investigate**: Check logs for signature mismatches
3. **Fix**: Ensure Shunya and Otto use the same secret
4. **Re-enable**: Set `ENVIRONMENT=production` again

---

## 🔍 **Code Flow**

```
POST /api/v1/shunya/webhook
  ↓
1. Read raw_body = await request.body()
  ↓
2. Verify signature (if invalid → 401, STOP)
  ↓
3. Parse JSON: payload = json.loads(raw_body.decode('utf-8'))
  ↓
4. Validate: shunya_job_id, company_id (if missing → 400)
  ↓
5. Lookup job: get_job_by_shunya_id(company_id, shunya_job_id)
  ↓
6. Verify tenant isolation: job.company_id == company_id (if mismatch → 403)
  ↓
7. Check idempotency: if job.status == SUCCEEDED → return "already_processed"
  ↓
8. Process webhook (normalize, persist, emit events - all idempotent)
  ↓
9. Return success
```

---

## ✅ **Verification Checklist**

Before enabling in production, verify:

- [ ] `UWC_HMAC_SECRET` is set in production environment
- [ ] `ENVIRONMENT=production` is set
- [ ] Shunya is configured to sign webhooks with same secret
- [ ] Shunya includes `X-UWC-Signature` and `X-UWC-Timestamp` headers
- [ ] Shunya includes `company_id` in webhook payload
- [ ] Test webhook with valid signature returns 200
- [ ] Test webhook with invalid signature returns 401
- [ ] Test webhook with wrong company_id returns 403
- [ ] Logs show successful signature verifications
- [ ] Monitoring/alerts configured for security violations

---

## 📊 **Security Benefits**

✅ **Webhook Authenticity**: Only webhooks signed by Shunya are processed  
✅ **Replay Protection**: Old webhooks cannot be replayed (timestamp validation)  
✅ **Tenant Isolation**: Cross-tenant attacks are prevented  
✅ **Body Integrity**: Tampered webhook bodies are detected  
✅ **Timing Attack Prevention**: Constant-time signature comparison  

---

**Implementation Status**: ✅ **COMPLETE AND READY FOR PRODUCTION**


