# 🚨 DEPLOYMENT VALIDATION CHECKLIST

## **CRITICAL INFRASTRUCTURE INTEGRATION ISSUES TO VALIDATE**

### **1. FLY.IO INTEGRATION CONCERNS**

#### **Observability Conflicts:**
- [ ] **OpenTelemetry Console Exporter**: May conflict with Fly.io's built-in logging
- [ ] **Structured JSON Logs**: May interfere with Fly.io log aggregation
- [ ] **Trace ID Headers**: May not work properly with Fly.io's load balancer
- [ ] **Metrics Endpoint**: May not be accessible through Fly.io's routing

#### **Performance Impact:**
- [ ] **Middleware Stack**: 5+ middleware layers may add significant latency
- [ ] **Database Queries**: Idempotency checks on every webhook may cause bottlenecks
- [ ] **Redis Connections**: Rate limiting Redis calls may fail or timeout
- [ ] **Memory Usage**: OpenTelemetry instrumentation may increase memory usage

#### **Environment Variables:**
- [ ] **Missing Variables**: New observability env vars may not be set in Fly.io
- [ ] **Redis URL**: May not be properly configured for production
- [ ] **OTEL Settings**: OpenTelemetry settings may conflict with Fly.io

### **2. CLERK INTEGRATION CONCERNS**

#### **Authentication Flow:**
- [ ] **CORS Headers**: May block Clerk's authentication requests
- [ ] **Rate Limiting**: May interfere with Clerk's authentication flow
- [ ] **Tenant Middleware**: May conflict with Clerk's JWT validation
- [ ] **Webhook Processing**: Clerk webhooks may be rate limited

#### **JWT Validation:**
- [ ] **Token Parsing**: Our tenant middleware may break Clerk's JWT flow
- [ ] **Organization Context**: May not properly extract tenant_id from Clerk tokens
- [ ] **Error Handling**: May return wrong error codes for auth failures

### **3. WEBHOOK INTEGRATION CONCERNS**

#### **CallRail Integration:**
- [ ] **Idempotency**: May cause webhooks to be ignored on retries
- [ ] **Rate Limiting**: May block legitimate CallRail webhooks
- [ ] **Database Locks**: Idempotency table may cause deadlocks

#### **Twilio Integration:**
- [ ] **SMS Webhooks**: May be rate limited or blocked
- [ ] **Call Status**: May not process call status updates properly
- [ ] **Recording Callbacks**: May fail due to observability overhead

### **4. FRONTEND INTEGRATION CONCERNS**

#### **CORS Issues:**
- [ ] **Preflight Requests**: May be blocked by CORS middleware
- [ ] **Authentication Headers**: May not be allowed by CORS
- [ ] **Error Responses**: May not be properly formatted for frontend

#### **API Calls:**
- [ ] **Rate Limiting**: Frontend may hit rate limits during normal usage
- [ ] **Error Handling**: May not receive proper error messages
- [ ] **Trace IDs**: May not be properly handled in frontend error reporting

## **VALIDATION STEPS**

### **Step 1: Run Quick Validation**
```bash
cd ottoai-backend/services/dashboard
python scripts/quick_validation.py https://tv-mvp-test.fly.dev
```

### **Step 2: Test Frontend Integration**
```bash
cd ottoai-frontend
npm run dev
# Test authentication flow
# Test API calls
# Check for CORS errors in browser console
```

### **Step 3: Test Webhook Integration**
```bash
# Test CallRail webhook
curl -X POST https://tv-mvp-test.fly.dev/call-rail/pre-call \
  -H "Content-Type: application/json" \
  -d '{"call": {"id": "test-123"}}'

# Test Twilio webhook
curl -X POST https://tv-mvp-test.fly.dev/twilio/call-status \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "CallSid=test-123&CallStatus=completed"
```

### **Step 4: Performance Testing**
```bash
# Test response times
for i in {1..10}; do
  time curl -s https://tv-mvp-test.fly.dev/health > /dev/null
done

# Test metrics endpoint
curl -s https://tv-mvp-test.fly.dev/metrics | grep http_requests_total
```

### **Step 5: Error Scenario Testing**
```bash
# Test 404 handling
curl -s https://tv-mvp-test.fly.dev/non-existent-endpoint

# Test rate limiting
for i in {1..20}; do
  curl -s https://tv-mvp-test.fly.dev/health &
done
wait
```

## **ROLLBACK PLAN**

### **If Observability Breaks Production:**

1. **Disable Observability Middleware:**
   ```python
   # In main.py, comment out:
   # app.add_middleware(ObservabilityMiddleware)
   ```

2. **Disable OpenTelemetry:**
   ```python
   # In main.py, comment out:
   # setup_tracing()
   # instrument_fastapi(app)
   ```

3. **Disable Structured Logging:**
   ```python
   # In main.py, comment out:
   # setup_logging()
   ```

4. **Disable Metrics Endpoint:**
   ```python
   # In main.py, comment out:
   # @app.get("/metrics")
   ```

### **If Rate Limiting Breaks Production:**

1. **Disable Rate Limiting:**
   ```python
   # In main.py, comment out:
   # app.add_middleware(RateLimitMiddleware)
   ```

2. **Fallback to In-Memory Rate Limiting:**
   ```python
   # In rate_limiter.py, set:
   # self.redis_client = None
   ```

### **If CORS Breaks Frontend:**

1. **Relax CORS Settings:**
   ```python
   # In main.py, update:
   # allow_origins=["*"]
   ```

## **MONITORING DURING VALIDATION**

### **Key Metrics to Watch:**
- Response time increase
- Error rate increase
- Memory usage increase
- Database connection pool exhaustion
- Redis connection failures

### **Logs to Monitor:**
- OpenTelemetry errors
- Rate limiting blocks
- CORS rejections
- Database connection errors
- Redis connection errors

## **SUCCESS CRITERIA**

### **Infrastructure Integration:**
- [ ] All endpoints respond within 2 seconds
- [ ] No increase in error rates
- [ ] CORS allows frontend requests
- [ ] Rate limiting doesn't block legitimate traffic
- [ ] Webhooks process successfully

### **Observability:**
- [ ] Metrics endpoint returns Prometheus format
- [ ] Trace IDs are present in responses
- [ ] Structured logs are generated
- [ ] Error handling returns RFC-7807 format

### **Performance:**
- [ ] Response times < 2 seconds
- [ ] Memory usage < 1GB
- [ ] Database queries < 100ms
- [ ] Redis operations < 50ms

## **NEXT STEPS AFTER VALIDATION**

1. **If Validation Passes:**
   - Deploy to production
   - Monitor for 24 hours
   - Set up alerting for key metrics

2. **If Validation Fails:**
   - Identify specific issues
   - Implement fixes
   - Re-run validation
   - Consider gradual rollout

3. **If Critical Issues Found:**
   - Rollback to previous version
   - Fix issues in development
   - Re-test before deployment
