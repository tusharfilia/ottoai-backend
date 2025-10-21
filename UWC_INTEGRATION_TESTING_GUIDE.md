# UWC Integration Testing Guide

## Overview
This guide provides comprehensive testing instructions for the UWC (Unified Workflow Composer) integration with Otto AI backend. The integration includes ASR, RAG, Training, and Follow-up generation with fallback mechanisms.

## Prerequisites

### 1. Environment Setup
```bash
# Enable UWC features (one at a time for testing)
export ENABLE_UWC_ASR=true
export ENABLE_UWC_RAG=true
export ENABLE_UWC_TRAINING=true
export ENABLE_UWC_FOLLOWUPS=true

# UWC Configuration
export UWC_BASE_URL="https://otto.shunyalabs.ai"
export UWC_API_KEY="your-uwc-bearer-token"

# Keep fallback services configured
export DEEPGRAM_API_KEY="your-deepgram-key"
```

### 2. UWC Mock API Access
- Base URL: `https://otto.shunyalabs.ai`
- Follow the `MOCK_API_TESTING_GUIDE.md` to get authentication tokens
- Test with the 3 roles: Admin, Sales Rep, CSR

## Testing Scenarios

### 1. ASR Integration Testing

#### Test 1: UWC ASR Success Path
```bash
# Start server
uvicorn app.main:app --reload

# Test mobile recording with UWC ASR
curl -X POST "http://localhost:8000/mobile/audio/start-recording" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-clerk-jwt" \
  -H "X-Company-ID: test-company" \
  -d '{
    "session_id": "uwc-asr-test-123",
    "company_id": "test-company"
  }'

# Stop recording to trigger UWC ASR
curl -X POST "http://localhost:8000/mobile/audio/stop-recording/uwc-asr-test-123" \
  -H "Authorization: Bearer your-clerk-jwt" \
  -H "X-Company-ID: test-company"
```

**Expected Behavior:**
- Recording starts successfully
- When stopped, audio is uploaded to S3
- UWC ASR is called with audio URL
- Transcription is returned from UWC
- Logs show: "UWC ASR transcription successful"

#### Test 2: UWC ASR Fallback Path
```bash
# Test with invalid UWC token to force fallback
export UWC_API_KEY="invalid-token"

# Repeat the recording test
curl -X POST "http://localhost:8000/mobile/audio/start-recording" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-clerk-jwt" \
  -H "X-Company-ID: test-company" \
  -d '{
    "session_id": "fallback-test-123",
    "company_id": "test-company"
  }'

curl -X POST "http://localhost:8000/mobile/audio/stop-recording/fallback-test-123" \
  -H "Authorization: Bearer your-clerk-jwt" \
  -H "X-Company-ID: test-company"
```

**Expected Behavior:**
- UWC ASR fails (401/403 error)
- Logs show: "UWC ASR failed, falling back to Deepgram"
- Deepgram transcription succeeds
- Logs show: "Using Deepgram transcription"

#### Test 3: Deepgram Only (UWC Disabled)
```bash
# Disable UWC ASR
export ENABLE_UWC_ASR=false

# Test recording
curl -X POST "http://localhost:8000/mobile/audio/start-recording" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-clerk-jwt" \
  -H "X-Company-ID: test-company" \
  -d '{
    "session_id": "deepgram-only-test-123",
    "company_id": "test-company"
  }'
```

**Expected Behavior:**
- UWC ASR is skipped entirely
- Direct Deepgram transcription
- Logs show: "Using Deepgram transcription"

### 2. RAG Integration Testing

#### Test 1: UWC RAG Success Path
```bash
# Enable UWC RAG
export ENABLE_UWC_RAG=true

# Test Ask Otto with UWC RAG
curl -X POST "http://localhost:8000/api/v1/rag/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-clerk-jwt" \
  -H "X-Company-ID: test-company" \
  -d '{
    "query": "What are the most common objections my reps face?",
    "filters": {"date_range": "last_30_days"},
    "max_results": 10
  }'
```

**Expected Behavior:**
- UWC RAG is called with query and context
- Real AI answer is returned with citations
- Logs show: "UWC RAG query successful"
- Response includes `confidence_score` and `citations`

#### Test 2: UWC RAG Fallback Path
```bash
# Test with invalid UWC token
export UWC_API_KEY="invalid-token"

# Repeat the query
curl -X POST "http://localhost:8000/api/v1/rag/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-clerk-jwt" \
  -H "X-Company-ID: test-company" \
  -d '{
    "query": "What are the most common objections my reps face?",
    "max_results": 10
  }'
```

**Expected Behavior:**
- UWC RAG fails
- Logs show: "UWC RAG failed, falling back to mock"
- Mock response is returned
- Logs show: "Using mock RAG response"

#### Test 3: Document Upload and Indexing
```bash
# Upload a document for RAG indexing
curl -X POST "http://localhost:8000/api/v1/rag/documents/upload" \
  -H "Authorization: Bearer your-clerk-jwt" \
  -H "X-Company-ID: test-company" \
  -F "file=@sales_script.pdf" \
  -F "document_type=sop"
```

**Expected Behavior:**
- Document uploaded to S3
- UWC indexing job is submitted
- Response includes `uwc_job_id`
- Logs show document processing status

### 3. Training Integration Testing

#### Test 1: UWC Training Success Path
```bash
# Enable UWC Training
export ENABLE_UWC_TRAINING=true

# Submit training job
curl -X POST "http://localhost:8000/api/v1/clone/train" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-clerk-jwt" \
  -H "X-Company-ID: test-company" \
  -d '{
    "rep_id": "rep_123",
    "training_data_type": "mixed",
    "training_call_ids": [101, 102, 103],
    "training_media_urls": ["https://youtube.com/shorts/abc123"],
    "notes": "Training with top performing calls"
  }'
```

**Expected Behavior:**
- Training job submitted to UWC
- Response includes `uwc_job_id`
- Logs show: "Training job submitted to UWC"
- Job status can be tracked

#### Test 2: Training Fallback Path
```bash
# Test with invalid UWC token
export UWC_API_KEY="invalid-token"

# Repeat training submission
curl -X POST "http://localhost:8000/api/v1/clone/train" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-clerk-jwt" \
  -H "X-Company-ID: test-company" \
  -d '{
    "rep_id": "rep_123",
    "training_data_type": "calls",
    "training_call_ids": [101, 102, 103]
  }'
```

**Expected Behavior:**
- UWC training fails
- Local training job is created
- Logs show fallback to local processing

### 4. Follow-up Generation Testing

#### Test 1: UWC Follow-up Success Path
```bash
# Enable UWC Follow-ups
export ENABLE_UWC_FOLLOWUPS=true

# Generate follow-up draft
curl -X POST "http://localhost:8000/api/v1/followups/generate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-clerk-jwt" \
  -H "X-Company-ID: test-company" \
  -d '{
    "call_id": 123,
    "draft_type": "sms",
    "tone": "friendly",
    "use_personal_clone": true
  }'
```

**Expected Behavior:**
- UWC follow-up generation is called
- Personalized draft is returned
- Response includes `generated_by` field
- Logs show: "UWC follow-up generation successful"

#### Test 2: Follow-up Fallback Path
```bash
# Test with invalid UWC token
export UWC_API_KEY="invalid-token"

# Repeat follow-up generation
curl -X POST "http://localhost:8000/api/v1/followups/generate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-clerk-jwt" \
  -H "X-Company-ID: test-company" \
  -d '{
    "call_id": 123,
    "draft_type": "sms",
    "tone": "professional"
  }'
```

**Expected Behavior:**
- UWC follow-up generation fails
- Mock draft is generated
- Logs show: "Using mock follow-up generation"

## Monitoring and Logs

### Key Log Messages to Look For

#### UWC Success Messages
```
"Attempting UWC ASR transcription for recording {recording_id}"
"UWC ASR transcription successful for recording {recording_id}"
"Attempting UWC RAG query for: {query}"
"UWC RAG query successful for: {query}"
"Training job submitted to UWC"
"UWC follow-up generation successful for call {call_id}"
```

#### Fallback Messages
```
"UWC ASR failed for recording {recording_id}, falling back to Deepgram: {error}"
"UWC RAG failed for query '{query}', falling back to mock: {error}"
"UWC follow-up generation failed for call {call_id}, falling back to mock: {error}"
"Using Deepgram transcription for recording {recording_id}"
"Using mock RAG response for: {query}"
"Using mock follow-up generation for call {call_id}"
```

### Metrics to Monitor
- UWC success/failure rates
- Fallback usage frequency
- Response latency (UWC vs fallback)
- Error rates by service type

## Troubleshooting

### Common Issues

#### 1. Authentication Errors
**Error**: `401 Unauthorized` or `403 Forbidden`
**Solution**: 
- Verify UWC API key is correct
- Check token expiration
- Ensure proper `X-Company-ID` header

#### 2. Service Unavailable
**Error**: `503 Service Unavailable` or connection timeout
**Solution**:
- Check UWC mock API status
- Verify network connectivity
- Check fallback services are configured

#### 3. Empty Responses
**Error**: UWC returns 200 but empty response
**Solution**:
- Check request payload format
- Verify required fields are present
- Review UWC API documentation

#### 4. Fallback Not Working
**Error**: UWC fails but fallback doesn't trigger
**Solution**:
- Check fallback service configuration
- Verify feature flags are set correctly
- Review error handling logic

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Check UWC client configuration
curl -X GET "http://localhost:8000/health" \
  -H "Authorization: Bearer your-clerk-jwt"
```

## Performance Testing

### Load Testing with Locust
```bash
# Run load tests
cd tests/load
locust -f locustfile.py --host=http://localhost:8000

# Test UWC endpoints under load
# - ASR transcription: 10 concurrent users
# - RAG queries: 20 concurrent users
# - Follow-up generation: 15 concurrent users
```

### Expected Performance
- **UWC ASR**: < 2 seconds response time
- **UWC RAG**: < 1 second response time
- **UWC Training**: < 5 seconds job submission
- **UWC Follow-ups**: < 1 second generation

## Integration Checklist

### Pre-deployment
- [ ] All UWC endpoints tested with mock API
- [ ] Fallback mechanisms verified
- [ ] Error handling tested
- [ ] Performance benchmarks met
- [ ] Logging and monitoring configured

### Post-deployment
- [ ] UWC services responding correctly
- [ ] Fallback services working as expected
- [ ] Metrics and alerts configured
- [ ] Error rates within acceptable limits
- [ ] User acceptance testing completed

## Next Steps

1. **Complete Week 5**: Finish remaining UWC integrations
2. **Move to Week 7**: Implement real-time features
3. **Production Deployment**: Deploy with UWC production endpoints
4. **Performance Optimization**: Fine-tune based on real usage data
5. **Feature Enhancement**: Add advanced UWC capabilities

