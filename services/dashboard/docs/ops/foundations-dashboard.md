# OttoAI Backend - Foundations Operations Dashboard

## Overview

This document provides operational guidance for monitoring and maintaining the foundational features of the OttoAI backend in production.

## 📊 Health Indicators

### ✅ Expected Healthy Values

#### **Response Latency**
- **P95 < 250ms**: Excellent performance
- **P95 < 500ms**: Acceptable performance  
- **P95 > 1000ms**: 🚨 Performance issue requiring investigation

#### **Real-Time Transport**
- **Event E2E Latency < 1s**: Real-time requirement met
- **WebSocket Connections > 0**: Active users connected
- **Messages Dropped = 0**: No backpressure issues
- **Heartbeat Timeouts < 5%**: Healthy connection management

#### **Worker Tasks**
- **Task Success Rate > 95%**: Healthy background processing
- **Task Duration < 30s**: Efficient task processing
- **Queue Length < 100**: No backlog issues

#### **Webhook Processing**
- **Webhook Failures = 0**: All webhooks processing successfully
- **Idempotency Duplicates > 0**: Duplicate prevention working
- **Processing Time < 500ms**: Efficient webhook handling

#### **Database & Cache**
- **Database Connections < 80% of pool**: Healthy connection usage
- **Cache Hit Rate > 80%**: Efficient caching
- **Redis Connectivity = 100%**: No Redis issues

### 🔍 Monitoring Endpoints

#### **Health Checks**
```bash
# Basic health
curl https://your-app.fly.dev/health

# Comprehensive readiness
curl https://your-app.fly.dev/ready

# Worker heartbeat
curl https://your-app.fly.dev/internal/worker/heartbeat
```

#### **Metrics Collection**
```bash
# Get metrics snapshot
./scripts/metrics_snapshot.sh https://your-app.fly.dev

# Raw Prometheus metrics
curl https://your-app.fly.dev/metrics
```

#### **Real-Time Testing**
```bash
# Test WebSocket connectivity
BASE=https://your-app.fly.dev TOKEN=your-jwt make smoke:realtime

# Test event emission (dev/staging only)
curl -H "X-Dev-Key: your-key" \
  "https://your-app.fly.dev/ws/test-emit?event=test.health&tenant_id=your-tenant"
```

## 📋 What to Check in Logs

### **Connection Events**
Look for structured JSON logs with these patterns:

#### **WebSocket Connections**
```json
{
  "level": "INFO",
  "message": "WebSocket connection established",
  "connection_id": "uuid",
  "tenant_id": "tenant-123",
  "user_id": "user-456",
  "trace_id": "trace-789",
  "ip": "192.168.1.1"
}
```

#### **Heartbeat Management**
```json
{
  "level": "INFO", 
  "message": "Disconnecting stale connection",
  "connection_id": "uuid",
  "reason": "heartbeat_timeout"
}
```

#### **Event Emission**
```json
{
  "level": "INFO",
  "message": "Event telephony.call.received published to 2 channels",
  "event": "telephony.call.received",
  "channels": ["tenant:123:events", "lead:456:timeline"],
  "tenant_id": "tenant-123",
  "trace_id": "trace-789"
}
```

#### **Idempotency Processing**
```json
{
  "level": "INFO",
  "message": "Webhook processed successfully",
  "provider": "callrail",
  "external_id": "call-123",
  "status": "processed",
  "trace_id": "trace-789"
}
```

### **Rate Limiting Events**
```json
{
  "level": "WARNING",
  "message": "Rate limit hit: user",
  "event_type": "rate_limit_hit",
  "limit_type": "user",
  "tenant_id": "tenant-123",
  "user_id": "user-456",
  "route": "/api/calls"
}
```

## 🚨 Red Flags & Alert Conditions

### **Critical Issues (Immediate Action Required)**

#### **Redis Connectivity Issues**
- **Symptom**: `/ready` returns `{"redis": false}`
- **Impact**: Rate limiting and real-time transport disabled
- **Action**: Check Redis service health, connection string, network connectivity

#### **Database Connection Issues**
- **Symptom**: `/ready` returns `{"database": false}`
- **Impact**: All API operations failing
- **Action**: Check database service, connection pool, migrations

#### **Cross-Tenant Data Leakage**
- **Symptom**: Logs show `tenant_id` mismatches or unauthorized access
- **Impact**: Security breach, compliance violation
- **Action**: Immediate investigation, potential rollback

#### **WebSocket Connection Failures**
- **Symptom**: `ws_connections` dropping to 0, authentication errors
- **Impact**: Real-time features not working
- **Action**: Check JWT validation, WebSocket endpoint health

### **Warning Conditions (Monitor Closely)**

#### **High Response Latency**
- **Symptom**: P95 latency > 500ms
- **Impact**: Poor user experience
- **Action**: Check database queries, Redis performance, scale resources

#### **Event Delivery Issues**
- **Symptom**: `ws_messages_dropped_total` increasing
- **Impact**: Real-time updates not reaching clients
- **Action**: Check WebSocket client health, message queue sizes

#### **Worker Task Failures**
- **Symptom**: `worker_task_total{status="failure"}` increasing
- **Impact**: Background processing issues
- **Action**: Check Celery worker logs, Redis connectivity

#### **Excessive Rate Limiting**
- **Symptom**: High rate of 429 responses
- **Impact**: Legitimate requests being blocked
- **Action**: Review rate limit configuration, check for abuse

### **Performance Degradation Indicators**

#### **Memory Usage**
- **Symptom**: Container memory usage > 80%
- **Action**: Check for memory leaks, scale resources
- **Commands**: `fly status`, `fly scale memory 2gb`

#### **Database Performance**
- **Symptom**: Slow database queries, connection pool exhaustion
- **Action**: Optimize queries, add indexes, scale database
- **Commands**: Check slow query logs, database connection metrics

#### **Redis Performance**
- **Symptom**: Redis latency increasing, connection timeouts
- **Action**: Check Redis memory usage, scale Redis instance
- **Commands**: `redis-cli info`, check Redis metrics

## 🔧 Troubleshooting Procedures

### **WebSocket Issues**

#### **No Connections**
```bash
# Check WebSocket endpoint
curl -I https://your-app.fly.dev/ws

# Check authentication
# Verify JWT token is valid and contains org_id

# Check Redis connectivity
curl https://your-app.fly.dev/ready | jq '.components.redis'
```

#### **Events Not Delivered**
```bash
# Check Redis pub/sub
redis-cli -u $REDIS_URL monitor

# Check event emission
curl -H "X-Dev-Key: $DEV_KEY" \
  "https://your-app.fly.dev/ws/test-emit?event=test.debug&tenant_id=your-tenant"

# Check WebSocket hub logs
fly logs --app your-app | grep "WebSocket\|realtime\|event"
```

### **Rate Limiting Issues**

#### **Excessive 429 Responses**
```bash
# Check rate limit metrics
curl https://your-app.fly.dev/metrics | grep rate_limit

# Check Redis connectivity
redis-cli -u $REDIS_URL ping

# Review rate limit configuration
fly secrets list | grep RATE_LIMIT
```

### **Idempotency Issues**

#### **Webhooks Being Ignored**
```bash
# Check idempotency table
psql $DATABASE_URL -c "SELECT provider, COUNT(*) FROM idempotency_keys GROUP BY provider;"

# Check webhook processing logs
fly logs | grep "idempotency\|webhook"

# Test webhook manually
curl -X POST https://your-app.fly.dev/call-rail/pre-call \
  -H "Content-Type: application/json" \
  -d '{"call": {"id": "test-123"}}'
```

### **Observability Issues**

#### **Missing Traces**
```bash
# Check OpenTelemetry configuration
fly secrets list | grep OTEL

# Verify trace headers
curl -H "X-Request-Id: test-123" https://your-app.fly.dev/health

# Check structured logs
fly logs | head -10 | jq '.'
```

## 📈 Performance Baselines

### **Load Testing Results**
Based on initial testing with realistic workloads:

#### **HTTP API Performance**
- **Concurrent Users**: 100
- **Requests/Second**: 500
- **P95 Latency**: 180ms
- **Error Rate**: <0.1%

#### **WebSocket Performance**
- **Concurrent Connections**: 1000
- **Messages/Second**: 10,000
- **Event E2E Latency**: 150ms
- **Connection Drops**: <1%

#### **Worker Task Performance**
- **Tasks/Minute**: 1000
- **Processing Time**: 200ms average
- **Failure Rate**: <0.5%

### **Resource Usage**
- **API Process**: 512MB RAM, 0.5 CPU
- **Worker Process**: 256MB RAM, 0.3 CPU
- **Beat Process**: 128MB RAM, 0.1 CPU
- **Redis**: 256MB RAM, minimal CPU

## 🚀 Scaling Guidelines

### **Horizontal Scaling**
```bash
# Scale API processes
fly scale count api=3

# Scale worker processes
fly scale count worker=2

# Keep beat at 1 (scheduler)
fly scale count beat=1
```

### **Vertical Scaling**
```bash
# Increase memory for API
fly scale memory api=1gb

# Increase memory for workers
fly scale memory worker=512mb
```

### **Redis Scaling**
- **Development**: nano plan (25MB)
- **Staging**: micro plan (100MB)
- **Production**: small plan (250MB) or larger

## 📋 Daily Operations Checklist

### **Morning Health Check**
- [ ] Run `make metrics:snapshot` - verify all systems healthy
- [ ] Check `/ready` endpoint - all components true
- [ ] Review overnight logs for errors or warnings
- [ ] Verify WebSocket connections > 0 during business hours

### **Weekly Review**
- [ ] Run `make verify:foundations` - ensure all tests pass
- [ ] Run `make smoke:foundations` against production
- [ ] Review performance trends and resource usage
- [ ] Check for any security alerts or rate limiting issues

### **Monthly Maintenance**
- [ ] Review and rotate development keys
- [ ] Clean up old metrics and logs
- [ ] Performance testing and optimization
- [ ] Review and update alert thresholds

## 🔔 Alerting Recommendations

### **Critical Alerts**
- `/ready` endpoint returns 503
- P95 latency > 1000ms for 5+ minutes
- WebSocket connections drop to 0 during business hours
- Worker task failure rate > 5%
- Cross-tenant access attempts detected

### **Warning Alerts**
- P95 latency > 500ms for 10+ minutes
- WebSocket message drop rate > 1%
- Cache hit rate < 70%
- Rate limiting triggered > 100 times/hour

### **Info Alerts**
- New webhook providers detected
- Unusual traffic patterns
- Resource usage approaching limits

This operations guide ensures that all foundational features are properly monitored and maintained in production.
