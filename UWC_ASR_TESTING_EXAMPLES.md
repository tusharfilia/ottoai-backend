# UWC ASR Integration Testing Examples

## Overview
This document provides examples for testing the UWC ASR integration with the Otto AI backend. The integration uses UWC ASR as the primary transcription service with Deepgram as fallback.

## Environment Setup

### 1. Enable UWC ASR
Set the following environment variable to enable UWC ASR:
```bash
export ENABLE_UWC_ASR=true
```

### 2. UWC Mock API Configuration
The backend is configured to use the UWC mock API at `https://otto.shunyalabs.ai` by default.

### 3. Get UWC Authentication Token
Follow the UWC Mock API Testing Guide to get a Bearer token:
```bash
# Example token (replace with actual token from UWC)
export UWC_API_KEY="your-uwc-bearer-token-here"
```

## Testing Scenarios

### Scenario 1: Mobile Recording with UWC ASR Enabled

**Endpoint:** `POST /mobile/audio/start-recording`

**Request:**
```json
{
  "session_id": "test-session-123",
  "company_id": "test-company"
}
```

**Expected Behavior:**
1. Recording starts successfully
2. When `stop-recording` is called, audio is processed with UWC ASR
3. If UWC succeeds: Uses UWC transcription
4. If UWC fails: Falls back to Deepgram transcription

**cURL Example:**
```bash
# Start recording
curl -X POST "http://localhost:8000/mobile/audio/start-recording" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-clerk-jwt-token" \
  -H "X-Company-ID: test-company" \
  -d '{
    "session_id": "test-session-123",
    "company_id": "test-company"
  }'

# Stop recording (triggers transcription)
curl -X POST "http://localhost:8000/mobile/audio/stop-recording/test-session-123" \
  -H "Authorization: Bearer your-clerk-jwt-token" \
  -H "X-Company-ID: test-company"
```

### Scenario 2: Twilio Recording Callback with UWC ASR

**Endpoint:** `POST /mobile/twilio-recording-callback`

**Request:** (Twilio webhook payload)
```
RecordingSid=RE1234567890abcdef
RecordingStatus=completed
RecordingUrl=https://api.twilio.com/2010-04-01/Accounts/AC.../Recordings/RE1234567890abcdef
CallSid=CA1234567890abcdef
RecordingDuration=45
```

**Expected Behavior:**
1. Twilio webhook received
2. Recording downloaded from Twilio
3. Audio uploaded to S3
4. UWC ASR transcription attempted
5. Fallback to Deepgram if UWC fails

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/mobile/twilio-recording-callback" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "RecordingSid=RE1234567890abcdef&RecordingStatus=completed&RecordingUrl=https://api.twilio.com/2010-04-01/Accounts/AC.../Recordings/RE1234567890abcdef&CallSid=CA1234567890abcdef&RecordingDuration=45"
```

### Scenario 3: Direct UWC ASR API Test

**Endpoint:** Direct UWC Mock API call

**Request:**
```bash
curl -X POST "https://otto.shunyalabs.ai/api/v1/asr/transcribe" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-uwc-token" \
  -H "X-Company-ID: test-company" \
  -H "X-Request-ID: test-request-123" \
  -d '{
    "request_id": "test-request-123",
    "company_id": "test-company",
    "audio_url": "https://example.com/test-audio.wav",
    "language": "en-US",
    "model": "nova-2"
  }'
```

## Testing UWC ASR Integration

### 1. Test UWC Success Path
```bash
# Enable UWC ASR
export ENABLE_UWC_ASR=true

# Start local server
cd ottoai-backend/services/dashboard
uvicorn app.main:app --reload

# Test mobile recording (should use UWC ASR)
curl -X POST "http://localhost:8000/mobile/audio/start-recording" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-clerk-jwt" \
  -H "X-Company-ID: test-company" \
  -d '{"session_id": "uwc-test-123", "company_id": "test-company"}'
```

### 2. Test Fallback Path
```bash
# Enable UWC ASR but provide invalid token to force fallback
export ENABLE_UWC_ASR=true
export UWC_API_KEY="invalid-token"

# Test mobile recording (should fall back to Deepgram)
curl -X POST "http://localhost:8000/mobile/audio/start-recording" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-clerk-jwt" \
  -H "X-Company-ID: test-company" \
  -d '{"session_id": "fallback-test-123", "company_id": "test-company"}'
```

### 3. Test Deepgram Only
```bash
# Disable UWC ASR
export ENABLE_UWC_ASR=false

# Test mobile recording (should use Deepgram only)
curl -X POST "http://localhost:8000/mobile/audio/start-recording" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-clerk-jwt" \
  -H "X-Company-ID: test-company" \
  -d '{"session_id": "deepgram-only-test-123", "company_id": "test-company"}'
```

## Monitoring and Logs

### Check Logs for UWC Integration
```bash
# Look for these log messages:
# - "Attempting UWC ASR transcription for recording {recording_id}"
# - "UWC ASR transcription successful for recording {recording_id}"
# - "UWC ASR failed for recording {recording_id}, falling back to Deepgram: {error}"
# - "Using Deepgram transcription for recording {recording_id}"
```

### Verify Transcription Results
```bash
# Get transcript for a recording session
curl -X GET "http://localhost:8000/mobile/audio/transcript/{recording_id}" \
  -H "Authorization: Bearer your-clerk-jwt" \
  -H "X-Company-ID: test-company"
```

## Troubleshooting

### Common Issues

1. **UWC API Key Missing**
   - Error: "UWC API key not configured"
   - Solution: Set `UWC_API_KEY` environment variable

2. **S3 Upload Fails**
   - Error: "Failed to upload audio to S3"
   - Solution: Check AWS credentials and S3 bucket permissions

3. **UWC Service Unavailable**
   - Error: "UWC ASR service unavailable"
   - Expected: Should fall back to Deepgram automatically

4. **Deepgram Fallback Fails**
   - Error: "Deepgram transcription failed"
   - Solution: Check `DEEPGRAM_API_KEY` environment variable

### Debug Mode
Enable debug logging to see detailed UWC integration flow:
```bash
export LOG_LEVEL=DEBUG
```

## Next Steps

1. **RAG Integration**: Wire UWC RAG into the RAG endpoints
2. **Training Jobs**: Implement UWC training job integration
3. **Follow-up Generation**: Wire UWC follow-up generation
4. **Monitoring**: Add metrics for UWC success/failure rates
5. **Load Testing**: Test UWC integration under load
