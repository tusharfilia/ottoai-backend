# Onboarding API Documentation

Complete API reference for the Otto onboarding flow. All endpoints are multi-tenant, idempotent, and require Clerk authentication with `org:admin` or `org:primary_admin` role.

## Base URL

All endpoints are under `/api/v1/onboarding`

## Authentication

All endpoints require:
- **Authorization Header**: `Bearer <clerk_jwt_token>`
- **Role**: `manager` (org:admin or org:primary_admin in Clerk)
- **Tenant Isolation**: Automatically enforced via JWT `org_id` → `tenant_id`

## Response Format

All endpoints return:
```json
{
  "success": true,
  "data": { ... },
  "meta": { ... }
}
```

Errors return RFC-7807 format:
```json
{
  "detail": {
    "error_code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": { ... }
  }
}
```

---

## Phase 1: Company Basics

### `POST /api/v1/onboarding/company-basics`

Save company basic information.

**Request Body:**
```json
{
  "company_name": "Acme Roofing Co",
  "company_phone": "+1-555-123-4567",
  "company_email": "info@acmeroofing.com",
  "company_domain": "acmeroofing.com",
  "company_address": "123 Main St, City, State 12345",
  "industry": "roofing",
  "timezone": "America/New_York",
  "team_size": 15,
  "admin_name": "John Doe",
  "admin_email": "john@acmeroofing.com"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "company_id": "org_abc123",
    "onboarding_step": "call_tracking",
    "step_already_completed": false
  }
}
```

**Idempotency**: Safe to call multiple times. If step already completed, returns `step_already_completed: true`.

---

## Phase 2: Call Tracking Integration

### `POST /api/v1/onboarding/callrail/connect`

Connect CallRail account.

**Request Body:**
```json
{
  "api_key": "abc123...",
  "account_id": "123456",
  "primary_tracking_number": "+1-555-123-4567"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "provider": "callrail",
    "onboarding_step": "document_ingestion",
    "webhook_url": "https://ottoai-backend-production.up.railway.app/callrail/call.completed",
    "step_already_completed": false
  }
}
```

### `POST /api/v1/onboarding/twilio/connect`

Connect Twilio account.

**Request Body:**
```json
{
  "account_sid": "AC...",
  "auth_token": "abc123...",
  "primary_tracking_number": "+1-555-123-4567"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "provider": "twilio",
    "onboarding_step": "document_ingestion",
    "webhook_url": "https://ottoai-backend-production.up.railway.app/mobile/twilio-voice-webhook",
    "step_already_completed": false
  }
}
```

### `POST /api/v1/onboarding/callrail/test`

Test CallRail connection without saving.

**Request Body:** Same as `callrail/connect`

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "connected": true,
    "webhook_url": "https://...",
    "message": "Connection successful"
  }
}
```

### `POST /api/v1/onboarding/twilio/test`

Test Twilio connection without saving.

**Request Body:** Same as `twilio/connect`

**Response:** Same format as CallRail test.

---

## Phase 3: Document Upload & Ingestion

### `POST /api/v1/onboarding/documents/upload`

Upload document for Shunya ingestion.

**Request:** `multipart/form-data`
- `file`: File (PDF, DOCX, TXT, etc.)
- `category`: `"sop" | "training" | "reference" | "policy"`
- `role_target`: `"manager" | "csr" | "sales_rep" | null` (optional)
- `metadata`: JSON string (optional)

**Example:**
```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -F "file=@sales_script.pdf" \
  -F "category=sop" \
  -F "role_target=sales_rep" \
  https://api.example.com/api/v1/onboarding/documents/upload
```

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "document_id": "doc_abc123",
    "filename": "sales_script.pdf",
    "s3_url": "https://s3.../documents/.../sales_script.pdf",
    "ingestion_job_id": "job_xyz789",
    "ingestion_status": "processing",
    "estimated_processing_time": "2-5 minutes"
  }
}
```

**Note**: Document ingestion happens asynchronously via Celery. Status can be checked via `/documents/status/{document_id}`.

### `GET /api/v1/onboarding/documents/status/{document_id}`

Get document ingestion status.

**Response:**
```json
{
  "success": true,
  "data": {
    "document_id": "doc_abc123",
    "ingestion_status": "done",
    "ingestion_job_id": "job_xyz789",
    "progress": null,
    "error_message": null
  }
}
```

**Status Values:**
- `pending`: Not yet sent to Shunya
- `processing`: Shunya is processing
- `done`: Successfully ingested
- `failed`: Ingestion failed

---

## Phase 4: Goals & Preferences

### `POST /api/v1/onboarding/goals`

Save company goals and preferences.

**Request Body:**
```json
{
  "primary_goals": [
    "Increase conversion rate",
    "Reduce response time",
    "Improve customer satisfaction"
  ],
  "target_metrics": {
    "conversion_rate": 0.25,
    "response_time_hours": 2,
    "customer_satisfaction_score": 4.5
  },
  "notification_preferences": {
    "email": true,
    "sms": false,
    "in_app": true
  },
  "quiet_hours_start": "20:00",
  "quiet_hours_end": "08:00"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "onboarding_step": "team_invites",
    "step_already_completed": false
  }
}
```

---

## Phase 5: Team Invitations

### `POST /api/v1/onboarding/invite-user`

Invite a team member via Clerk.

**Request Body:**
```json
{
  "email": "rep@acmeroofing.com",
  "role": "sales_rep",
  "territory": "North Region",
  "department": "Sales"
}
```

**Valid Roles:**
- `manager`: Executive/admin/manager
- `csr`: Customer service representative
- `sales_rep`: Sales representative

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "invite_id": "inv_abc123",
    "email": "rep@acmeroofing.com",
    "role": "sales_rep",
    "status": "sent"
  }
}
```

**Note**: Invitation is sent via Clerk API. When user accepts, Clerk webhook will create user record in database.

### `GET /api/v1/onboarding/invited-users`

List all invited users.

**Response:**
```json
{
  "success": true,
  "data": {
    "invited_users": [
      {
        "invite_id": "inv_abc123",
        "email": "rep@acmeroofing.com",
        "role": "sales_rep",
        "territory": "North Region",
        "status": "pending",
        "invited_at": "2025-12-01T15:00:00Z",
        "accepted_at": null
      }
    ],
    "total": 1
  }
}
```

---

## Phase 6: Final Verification

### `POST /api/v1/onboarding/verify`

Verify all onboarding steps are complete.

**Request Body:** `{}` (empty)

**Response (Success):**
```json
{
  "success": true,
  "data": {
    "success": true,
    "onboarding_completed": true,
    "onboarding_completed_at": "2025-12-01T15:30:00Z",
    "checks": {
      "company_basics": true,
      "call_tracking": true,
      "documents": true,
      "team_members": true
    },
    "errors": []
  }
}
```

**Response (Failure):**
```json
{
  "success": true,
  "data": {
    "success": false,
    "onboarding_completed": false,
    "onboarding_completed_at": null,
    "checks": {
      "company_basics": true,
      "call_tracking": true,
      "documents": false,
      "team_members": false
    },
    "errors": [
      "No documents uploaded or documents still processing",
      "No team members (CSR or sales rep) added"
    ]
  }
}
```

**Verification Checks:**
1. **company_basics**: Company name, phone, industry, timezone are set
2. **call_tracking**: CallRail or Twilio is configured
3. **documents**: At least one document is uploaded and processed (`done` status)
4. **team_members**: At least one CSR or sales_rep user exists

---

## Status & Progress

### `GET /api/v1/onboarding/status`

Get current onboarding status and progress.

**Response:**
```json
{
  "success": true,
  "data": {
    "company_id": "org_abc123",
    "onboarding_step": "team_invites",
    "onboarding_completed": false,
    "onboarding_completed_at": null,
    "progress": {
      "company_basics": true,
      "call_tracking": true,
      "documents": true,
      "goals_preferences": true,
      "team_invites": false
    }
  }
}
```

---

## Onboarding Flow

```
1. Company Basics
   ↓
2. Call Tracking (CallRail OR Twilio)
   ↓
3. Document Ingestion (upload multiple documents)
   ↓
4. Goals & Preferences
   ↓
5. Team Invitations (invite multiple users)
   ↓
6. Verification (auto-checks all steps)
   ↓
✅ Onboarding Complete
```

---

## Idempotency

All endpoints are **idempotent**:
- Safe to call multiple times
- Won't create duplicate records
- Returns `step_already_completed: true` if step was already done
- Document uploads are deduplicated by filename + company_id

---

## Multi-Tenancy

All endpoints:
- Extract `tenant_id` from JWT `org_id`
- Enforce tenant isolation (403 if cross-tenant access attempted)
- All database queries are tenant-scoped

---

## Error Handling

**400 Bad Request**: Invalid input data
```json
{
  "detail": "Invalid domain format"
}
```

**403 Forbidden**: 
- Missing or invalid tenant_id
- Insufficient role (not manager)
- Cross-tenant access attempt

**404 Not Found**: Resource not found (document, company, etc.)

**500 Internal Server Error**: Unexpected server error

---

## Integration Notes

### Clerk Webhooks

When a user accepts an invitation:
1. Clerk sends `organizationMembership.created` webhook
2. Backend webhook handler creates User record
3. User is automatically linked to company

### Shunya Document Ingestion

1. Document uploaded to S3
2. Celery task calls Shunya `/api/v1/ingestion/documents/upload`
3. Shunya processes document asynchronously
4. Status updated via webhook or polling

### Call Tracking Webhooks

After connecting CallRail/Twilio:
- Webhook URLs are automatically configured
- Test endpoints verify connection before saving
- Webhooks must be manually configured in CallRail/Twilio dashboards using the returned `webhook_url`

---

## Example Frontend Flow

```typescript
// 1. Company Basics
await api.post('/api/v1/onboarding/company-basics', {
  company_name: "Acme Co",
  // ... other fields
});

// 2. Connect CallRail
await api.post('/api/v1/onboarding/callrail/test', {
  api_key: "...",
  account_id: "..."
});
await api.post('/api/v1/onboarding/callrail/connect', {
  api_key: "...",
  account_id: "..."
});

// 3. Upload Documents
const formData = new FormData();
formData.append('file', file);
formData.append('category', 'sop');
await api.post('/api/v1/onboarding/documents/upload', formData);

// 4. Goals
await api.post('/api/v1/onboarding/goals', {
  primary_goals: [...],
  // ...
});

// 5. Invite Users
await api.post('/api/v1/onboarding/invite-user', {
  email: "rep@example.com",
  role: "sales_rep"
});

// 6. Verify
await api.post('/api/v1/onboarding/verify', {});
```

---

## Database Schema

### Companies Table (New Fields)
- `industry`: String
- `timezone`: String (default: "America/New_York")
- `domain`: String
- `domain_verified`: Boolean
- `call_provider`: Enum('callrail', 'twilio')
- `twilio_account_sid`: String
- `twilio_auth_token`: String
- `primary_tracking_number`: String
- `onboarding_step`: String (default: "company_basics")
- `onboarding_completed`: Boolean (default: false)
- `onboarding_completed_at`: DateTime
- `subscription_status`: String (default: "trialing")
- `trial_ends_at`: DateTime
- `max_seats`: Integer (default: 5)

### Documents Table (New)
- `id`: String (PK)
- `company_id`: String (FK → companies.id)
- `filename`: String
- `category`: Enum('sop', 'training', 'reference', 'policy')
- `role_target`: String (nullable)
- `s3_url`: String
- `ingestion_job_id`: String (nullable)
- `ingestion_status`: Enum('pending', 'processing', 'done', 'failed')
- `metadata`: JSON
- `created_at`: DateTime
- `updated_at`: DateTime

### Onboarding Events Table (New)
- `id`: String (PK)
- `company_id`: String (FK → companies.id)
- `user_id`: String (FK → users.id, nullable)
- `step`: String
- `action`: String
- `metadata`: JSON
- `timestamp`: DateTime

### Users Table (New Fields)
- `territory`: String (nullable)
- `preferences_json`: JSON (nullable)

---

## Testing

### Test Company Basics
```bash
curl -X POST https://api.example.com/api/v1/onboarding/company-basics \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Test Co",
    "company_phone": "+1-555-123-4567",
    "company_email": "test@example.com",
    "company_domain": "example.com",
    "industry": "roofing",
    "timezone": "America/New_York",
    "team_size": 5,
    "admin_name": "Test Admin",
    "admin_email": "admin@example.com"
  }'
```

### Test Document Upload
```bash
curl -X POST https://api.example.com/api/v1/onboarding/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@document.pdf" \
  -F "category=sop" \
  -F "role_target=sales_rep"
```

---

## Security Notes

1. **API Keys**: CallRail/Twilio credentials are stored encrypted in database
2. **Tenant Isolation**: All queries are tenant-scoped via middleware
3. **Role-Based Access**: Only managers can access onboarding endpoints
4. **Idempotency**: Prevents duplicate processing and race conditions
5. **Input Validation**: All inputs validated via Pydantic schemas

---

## Troubleshooting

### "Missing or invalid tenant_id in JWT claims"
- Ensure JWT contains `org_id` claim
- Check JWT hasn't expired
- Verify Clerk organization exists

### "Document ingestion stuck in processing"
- Check Celery worker is running
- Check Shunya API is accessible
- Review Celery task logs
- Manually retry via task queue

### "Call tracking test fails"
- Verify API credentials are correct
- Check network connectivity
- Review CallRail/Twilio account status

---

## Support

For issues or questions:
1. Check Railway logs for backend errors
2. Review Celery worker logs for task failures
3. Verify Clerk webhook configuration
4. Check Shunya API status

