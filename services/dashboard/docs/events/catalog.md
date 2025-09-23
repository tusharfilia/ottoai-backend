# OttoAI Real-Time Event Catalog

## Overview

This document defines all real-time events emitted by the OttoAI backend and their expected payload structures. Events are delivered via WebSocket connections to authenticated clients.

## Message Envelope Format

All events follow a standardized envelope format:

```json
{
  "version": "1",
  "event": "event.name.kebab-case",
  "ts": "2025-09-20T10:30:00.000Z",
  "severity": "info|warn|error",
  "trace_id": "uuid-or-w3c-trace-id",
  "tenant_id": "tenant-identifier",
  "user_id": "user-identifier",
  "lead_id": "lead-identifier",
  "key": "optional-deduplication-key",
  "data": {
    // Event-specific payload
  }
}
```

## Channel Types

### Tenant Channels
- **Format**: `tenant:{tenant_id}:events`
- **Purpose**: Organization-wide events visible to all users in the tenant
- **Access**: All authenticated users in the tenant

### User Channels  
- **Format**: `user:{user_id}:tasks`
- **Purpose**: User-specific events (tasks, assignments, notifications)
- **Access**: Only the specific user

### Lead Channels
- **Format**: `lead:{lead_id}:timeline`
- **Purpose**: Lead-specific events (call updates, status changes)
- **Access**: Users in the same tenant as the lead

## Event Categories

### 1. Telephony Events

#### `telephony.call.received`
**When**: CallRail pre-call webhook processed
**Channels**: `tenant:{tenant_id}:events`, `lead:{call_id}:timeline`
**Payload**:
```json
{
  "call_id": "string",
  "phone_number": "string",
  "company_id": "string",
  "answered": "boolean"
}
```
**UI Impact**: 
- **Manager Dashboard**: Show incoming call notification
- **Rep Mobile**: Alert assigned rep of new lead

#### `telephony.call.completed`
**When**: CallRail call-complete webhook processed
**Channels**: `tenant:{tenant_id}:events`, `lead:{call_id}:timeline`
**Payload**:
```json
{
  "call_id": "string",
  "phone_number": "string", 
  "company_id": "string",
  "booked": "boolean",
  "qualified": "boolean",
  "objections": "string[]",
  "quote_date": "string|null"
}
```
**UI Impact**:
- **Manager Dashboard**: Update call status, show booking result
- **Rep Mobile**: Show follow-up tasks if booked
- **Analytics**: Update conversion metrics

#### `telephony.sms.received`
**When**: Twilio SMS webhook processed (incoming)
**Channels**: `tenant:{tenant_id}:events`, `lead:{lead_id}:timeline`
**Payload**:
```json
{
  "message_id": "string",
  "from": "string",
  "to": "string", 
  "content": "string",
  "lead_id": "string|null"
}
```
**UI Impact**:
- **Manager Dashboard**: Show SMS notification
- **Rep Mobile**: Alert of customer response

#### `telephony.sms.sent`
**When**: Twilio SMS sent successfully
**Channels**: `tenant:{tenant_id}:events`, `user:{user_id}:tasks`, `lead:{lead_id}:timeline`
**Payload**:
```json
{
  "message_id": "string",
  "to": "string",
  "content": "string",
  "sent_by": "string",
  "lead_id": "string|null"
}
```
**UI Impact**:
- **Rep Mobile**: Confirm message sent
- **Manager Dashboard**: Update communication log

#### `telephony.call.status`
**When**: Twilio call status webhook processed
**Channels**: `tenant:{tenant_id}:events`, `lead:{lead_id}:timeline`
**Payload**:
```json
{
  "call_id": "string",
  "status": "string",
  "duration": "number|null",
  "recording_url": "string|null"
}
```
**UI Impact**:
- **Manager Dashboard**: Update call status in real-time
- **Rep Mobile**: Show call completion

### 2. System Events

#### `system.webhook.processed`
**When**: Any webhook processing completes successfully
**Channels**: `tenant:{tenant_id}:events`
**Payload**:
```json
{
  "provider": "callrail|twilio|clerk|bland",
  "external_id": "string",
  "webhook_type": "string",
  "processing_time_ms": "number"
}
```
**UI Impact**:
- **Admin Dashboard**: System health monitoring
- **Debug Console**: Webhook processing status

#### `system.buffer_dropped`
**When**: WebSocket message queue overflow
**Channels**: Sent directly to affected connection
**Payload**:
```json
{
  "reason": "Queue overflow",
  "max_size": "number",
  "dropped_count": "number"
}
```
**UI Impact**:
- **Client**: Show connection quality warning
- **Admin**: Alert of potential performance issues

### 3. Identity Events

#### `identity.user.created`
**When**: Clerk user creation webhook processed
**Channels**: `tenant:{tenant_id}:events`
**Payload**:
```json
{
  "user_id": "string",
  "email": "string",
  "first_name": "string|null",
  "last_name": "string|null",
  "role": "string|null"
}
```
**UI Impact**:
- **Manager Dashboard**: Show new team member
- **Admin Panel**: Update user list

#### `identity.user.updated`
**When**: Clerk user update webhook processed
**Channels**: `tenant:{tenant_id}:events`, `user:{user_id}:tasks`
**Payload**:
```json
{
  "user_id": "string",
  "changes": "string[]",
  "email": "string",
  "role": "string|null"
}
```
**UI Impact**:
- **User Profile**: Refresh user information
- **Manager Dashboard**: Update team member details

### 4. Task Events

#### `task.updated`
**When**: CSR follow-up task created or updated
**Channels**: `user:{assigned_user_id}:tasks`, `tenant:{tenant_id}:events`
**Payload**:
```json
{
  "task_id": "string",
  "type": "follow_up|quote|callback",
  "status": "assigned|in_progress|completed|cancelled",
  "due_date": "string",
  "lead_id": "string",
  "assigned_to": "string",
  "priority": "low|medium|high|urgent"
}
```
**UI Impact**:
- **Rep Mobile**: Show new task notification
- **Manager Dashboard**: Update task board
- **Follow-Up Board**: Real-time task updates

### 5. Analytics Events

#### `analytics.daily_recap.ready`
**When**: Daily analytics recap is generated
**Channels**: `tenant:{tenant_id}:events`
**Payload**:
```json
{
  "recap_id": "string",
  "date": "string",
  "metrics": {
    "calls_received": "number",
    "calls_booked": "number",
    "conversion_rate": "number",
    "revenue_generated": "number"
  }
}
```
**UI Impact**:
- **Manager Dashboard**: Show daily recap notification
- **Analytics Page**: Auto-refresh with new data

### 6. Appointment Events

#### `appointment.assigned`
**When**: CRM sync assigns appointment to rep
**Channels**: `user:{assigned_rep_id}:tasks`, `tenant:{tenant_id}:events`
**Payload**:
```json
{
  "appointment_id": "string",
  "lead_id": "string",
  "assigned_to": "string",
  "scheduled_date": "string",
  "address": "string",
  "customer_name": "string",
  "service_type": "string"
}
```
**UI Impact**:
- **Rep Mobile**: Show new appointment notification
- **Calendar**: Add appointment to schedule
- **Manager Dashboard**: Update assignment board

### 7. Worker Events

#### `worker.task.finished`
**When**: Celery background task completes successfully
**Channels**: `tenant:{tenant_id}:events`
**Payload**:
```json
{
  "task_name": "string",
  "task_id": "string",
  "duration_ms": "number",
  "result": "any"
}
```
**UI Impact**:
- **Admin Dashboard**: System health monitoring
- **Progress Indicators**: Update task completion status

#### `worker.task.failed`
**When**: Celery background task fails
**Channels**: `tenant:{tenant_id}:events`
**Payload**:
```json
{
  "task_name": "string",
  "task_id": "string",
  "duration_ms": "number",
  "error": "string",
  "retry_count": "number"
}
```
**UI Impact**:
- **Admin Dashboard**: Show error notification
- **System Health**: Alert of background task failures

## Client Implementation Examples

### Web Client (JavaScript)

```javascript
// Connect to WebSocket
const ws = new WebSocket('wss://api.ottoai.com/ws', {
  headers: {
    'Authorization': `Bearer ${clerkToken}`
  }
});

ws.onopen = () => {
  console.log('Connected to OttoAI real-time');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  switch (message.type) {
    case 'welcome':
      // Subscribe to relevant channels
      ws.send(JSON.stringify({
        type: 'subscribe',
        channel: `tenant:${message.tenant_id}:events`
      }));
      break;
      
    case 'ping':
      // Respond to heartbeat
      ws.send(JSON.stringify({type: 'pong'}));
      break;
      
    default:
      // Handle real-time events
      handleRealtimeEvent(message);
  }
};

function handleRealtimeEvent(message) {
  switch (message.event) {
    case 'telephony.call.received':
      showCallNotification(message.data);
      break;
    case 'task.updated':
      updateTaskBoard(message.data);
      break;
    // ... other events
  }
}
```

### Mobile Client (React Native)

```typescript
import { useAuth } from '@clerk/expo';

const useRealtimeConnection = () => {
  const { getToken } = useAuth();
  const [ws, setWs] = useState<WebSocket | null>(null);
  
  useEffect(() => {
    const connectWebSocket = async () => {
      const token = await getToken();
      
      const websocket = new WebSocket('wss://api.ottoai.com/ws', [], {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      websocket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleRealtimeEvent(message);
      };
      
      setWs(websocket);
    };
    
    connectWebSocket();
    
    return () => {
      ws?.close();
    };
  }, []);
  
  const handleRealtimeEvent = (message: any) => {
    switch (message.event) {
      case 'appointment.assigned':
        showAppointmentNotification(message.data);
        break;
      case 'telephony.sms.received':
        updateConversation(message.data);
        break;
      // ... other events
    }
  };
};
```

## Performance Considerations

### Message Size Limits
- **Maximum message size**: 32KB
- **Large payloads**: Automatically converted to pointer messages with resource IDs
- **Clients**: Should fetch full details via REST API when `_truncated: true`

### Connection Limits
- **Per tenant**: No hard limit (monitored via metrics)
- **Per user**: Recommend 1-2 connections (web + mobile)
- **Heartbeat**: 20-second ping/pong cycle
- **Stale timeout**: 40 seconds without pong

### Channel Subscription Limits
- **Per connection**: No hard limit (monitored for abuse)
- **Rate limiting**: 10 subscribe/unsubscribe operations per minute
- **Validation**: Strict channel format and access control

## Security

### Authentication
- **Required**: Valid Clerk JWT token in Authorization header
- **Validation**: Same JWT validation as REST API endpoints
- **Session**: Connection tied to specific tenant and user

### Authorization
- **Channel Access**: Users can only subscribe to their own tenant/user/lead channels
- **Lead Validation**: Lead channels validated against tenant ownership
- **No Wildcards**: Exact channel names required, no pattern matching

### Rate Limiting
- **Control Messages**: 10 subscribe/unsubscribe per minute per connection
- **Connection Limits**: Monitored but not hard-limited
- **Abuse Protection**: Automatic disconnection for protocol violations

## Monitoring

### Metrics Available
- `ws_connections{tenant_id}` - Active connections per tenant
- `ws_messages_sent_total{channel}` - Messages sent per channel type
- `ws_messages_dropped_total{reason}` - Dropped messages by reason
- `ws_subscriptions_total{channel}` - Subscriptions per channel type

### Health Checks
- **WebSocket Health**: Monitor active connections and message throughput
- **Redis Pub/Sub**: Monitor Redis connectivity and message delivery
- **Event Latency**: Track end-to-end event delivery time

### Troubleshooting
- **Connection Issues**: Check `/ready` endpoint for Redis connectivity
- **Event Delivery**: Monitor Redis pub/sub metrics
- **Performance**: Watch message queue sizes and delivery latency
