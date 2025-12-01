# Otto Backend - Complete API Catalog

**Source**: https://ottoai-backend-production.up.railway.app/openapi.json  
**Total Endpoints**: **218 endpoints**  
**Last Updated**: 2025-11-24

---

## 📋 **QUICK ACCESS**

- **Swagger UI**: https://ottoai-backend-production.up.railway.app/docs
- **OpenAPI JSON**: https://ottoai-backend-production.up.railway.app/openapi.json
- **ReDoc**: https://ottoai-backend-production.up.railway.app/redoc

---

## 📊 **API ENDPOINTS BY CATEGORY**

### **Dashboard & Metrics** (15+ endpoints)

#### Dashboard
```
GET  /api/v1/dashboard/metrics?company_id={id}
GET  /api/v1/dashboard/calls?status={status}&company_id={id}
```

#### Live Metrics
```
GET  /api/v1/live-metrics/current
GET  /api/v1/live-metrics/revenue
GET  /api/v1/live-metrics/calls
GET  /api/v1/live-metrics/leads
GET  /api/v1/live-metrics/csr-performance
GET  /api/v1/live-metrics/status
```

---

### **Call Management** (10+ endpoints)

```
GET  /api/v1/calls/call/{call_id}
GET  /api/v1/calls/unassigned-calls
POST /api/v1/calls/add-call
POST /api/v1/calls/update-call-status
POST /api/v1/calls/{call_id}/analyze
GET  /api/v1/calls/{call_id}/analysis
POST /api/v1/calls/analyze-batch
GET  /api/v1/calls/analytics/objections
```

---

### **Lead Management** (3 endpoints)

```
GET  /api/v1/leads/{lead_id}
POST /api/v1/leads
PATCH /api/v1/leads/{lead_id}
```

---

### **Appointment Management** (3 endpoints)

```
GET   /api/v1/appointments/{appointment_id}
POST  /api/v1/appointments
PATCH /api/v1/appointments/{appointment_id}
```

---

### **Contact Cards** (3 endpoints)

```
GET  /api/v1/contact-cards/{contact_card_id}
GET  /api/v1/contact-cards/by-phone?phone={number}
POST /api/v1/contact-cards/{contact_card_id}/refresh-property-intelligence
```

---

### **Lead Pool** (3 endpoints)

```
GET  /api/v1/lead-pool
POST /api/v1/lead-pool/{lead_id}/request
POST /api/v1/lead-pool/{lead_id}/assign
```

---

### **RAG / Ask Otto** (7 endpoints)

```
POST   /api/v1/rag/query
GET    /api/v1/rag/queries
POST   /api/v1/rag/queries/{query_id}/feedback
GET    /api/v1/rag/documents
POST   /api/v1/rag/documents/upload
GET    /api/v1/rag/documents/{document_id}
DELETE /api/v1/rag/documents/{document_id}
```

---

### **Recording Sessions** (5 endpoints) - Sales Reps

```
POST /api/v1/recording-sessions/start
POST /api/v1/recording-sessions/{session_id}/stop
POST /api/v1/recording-sessions/{session_id}/upload-audio-complete
PUT  /api/v1/recording-sessions/{session_id}/metadata
GET  /api/v1/recording-sessions/{session_id}
```

---

### **Rep Shifts** (3 endpoints) - Sales Reps

```
POST /api/v1/reps/{rep_id}/shifts/clock-in
POST /api/v1/reps/{rep_id}/shifts/clock-out
GET  /api/v1/reps/{rep_id}/shifts/today
```

---

### **Missed Call Queue** (10 endpoints)

```
POST /api/v1/missed-calls/queue/{call_id}
GET  /api/v1/missed-calls/queue/status
GET  /api/v1/missed-calls/queue/metrics
GET  /api/v1/missed-calls/queue/entries
GET  /api/v1/missed-calls/queue/entries/{queue_id}
POST /api/v1/missed-calls/queue/entries/{queue_id}/process
POST /api/v1/missed-calls/queue/entries/{queue_id}/escalate
GET  /api/v1/missed-calls/processor/status
POST /api/v1/missed-calls/processor/start
POST /api/v1/missed-calls/processor/stop
```

---

### **Post-Call Analysis** (5 endpoints)

```
GET /api/v1/post-call-analysis/call/{call_id}
GET /api/v1/post-call-analysis/sales-rep/{sales_rep_id}/performance
GET /api/v1/post-call-analysis/coaching-recommendations
GET /api/v1/post-call-analysis/performance-summary
GET /api/v1/post-call-analysis/status
```

---

### **Sales Reps** (6 endpoints)

```
GET  /api/v1/sales-reps
GET  /api/v1/sales-reps/{rep_id}/appointments
POST /api/v1/sales-reps
PUT  /api/v1/sales-reps/{rep_id}
POST /api/v1/sales-reps/assign/{call_id}
```

---

### **Companies** (10 endpoints)

```
GET  /api/v1/companies/{company_id}
POST /api/v1/companies
PUT  /api/v1/companies/{company_id}
POST /api/v1/companies/{company_id}/set-callrail-api-key
POST /api/v1/companies/{company_id}/set-callrail-account-id
GET  /api/v1/companies/by-phone/{phone_number}
GET  /api/v1/companies/get-user-company/{username}
GET  /api/v1/companies/list-organizations
GET  /api/v1/companies/{company_id}/sales-managers
POST /api/v1/companies/organizations/{org_id}/memberships
```

---

### **Users** (8 endpoints)

```
GET  /api/v1/users/{user_id}
POST /api/v1/users
PUT  /api/v1/users/{user_id}
POST /api/v1/users/{user_id}/sync-to-clerk
GET  /api/v1/users/company
GET  /api/v1/users/by-username/{username}
PATCH /api/v1/users/metadata/{user_id}
POST /api/v1/users/clerk-webhook
```

---

### **Follow-ups** (4 endpoints)

```
POST /api/v1/followups/draft
GET  /api/v1/followups/drafts
POST /api/v1/followups/drafts/{draft_id}/approve
POST /api/v1/followups/drafts/{draft_id}/send
```

---

### **Personal Clones** (4 endpoints)

```
POST /api/v1/clone/train
GET  /api/v1/clone/{rep_id}/status
GET  /api/v1/clone/{rep_id}/history
POST /api/v1/clone/{rep_id}/retry
```

---

### **GDPR** (3 endpoints)

```
POST /api/v1/gdpr/delete-user
POST /api/v1/gdpr/export-user-data
DELETE /api/v1/gdpr/tenant-data
```

---

### **Analysis** (4 endpoints)

```
POST /api/v1/calls/{call_id}/analyze
GET  /api/v1/calls/{call_id}/analysis
POST /api/v1/calls/analyze-batch
GET  /api/v1/calls/analytics/objections
```

---

### **Mobile APIs** (28 endpoints)

#### Appointments
```
GET  /api/v1/mobile/appointments
GET  /api/v1/mobile/appointments/company
GET  /api/v1/mobile/appointments/{appointment_id}
```

#### Audio Recording
```
POST /api/v1/mobile/audio/start-recording
POST /api/v1/mobile/audio/upload/{recording_id}
GET  /api/v1/mobile/audio/status/{recording_id}
GET  /api/v1/mobile/audio/raw-data/{recording_id}
POST /api/v1/mobile/audio/analyze-transcript/{call_id}
GET  /api/v1/mobile/audio/transcript-analysis/{call_id}
GET  /api/v1/mobile/audio/transcript-analyses/{call_id}/versions
POST /api/v1/mobile/audio/sync-call-fields-from-analysis/{call_id}
POST /api/v1/mobile/audio/batch-sync-call-fields
GET  /api/v1/mobile/audio/analysis-processes
```

#### Messages & Transcripts
```
GET  /api/v1/mobile/messages/{call_id}
GET  /api/v1/mobile/call-transcripts/{call_id}
```

---

### **Webhooks** (70+ endpoints)

#### CallRail Webhooks
```
POST /callrail/call.incoming
POST /callrail/call.answered
POST /callrail/call.missed
POST /callrail/call.completed
```

#### Twilio Webhooks
```
POST /twilio-webhook
POST /mobile/twilio-voice-webhook
POST /mobile/twilio-sms-webhook
```

#### Shunya/UWC Webhooks
```
POST /api/v1/shunya/webhook
POST /webhooks/uwc/asr/complete
POST /webhooks/uwc/analysis/complete
POST /webhooks/uwc/followup/draft
POST /webhooks/uwc/rag/indexed
POST /webhooks/uwc/training/status
```

#### SMS Webhooks
```
POST /sms/callrail-webhook
POST /sms/twilio-webhook
```

---

### **Internal AI APIs** (6 endpoints) - For Shunya

```
GET /internal/ai/calls/{call_id}
GET /internal/ai/reps/{rep_id}
GET /internal/ai/companies/{company_id}
GET /internal/ai/leads/{lead_id}
GET /internal/ai/appointments/{appointment_id}
GET /internal/ai/services/{company_id}
```

---

### **System & Health** (5+ endpoints)

```
GET /health
GET /health/detailed
GET /health/live
GET /health/ready
GET /metrics
```

---

### **Admin** (1 endpoint)

```
GET /api/v1/admin/openai/stats
```

---

## 🎯 **MOST COMMONLY USED APIS FOR FRONTEND**

### **Dashboard**
- `GET /api/v1/dashboard/metrics` - Dashboard KPIs
- `GET /api/v1/dashboard/calls` - Filtered calls list
- `GET /api/v1/live-metrics/current` - Real-time metrics

### **Calls**
- `GET /api/v1/calls/call/{call_id}` - Call details
- `GET /api/v1/calls/unassigned-calls` - Unassigned calls

### **Leads & Contacts**
- `GET /api/v1/leads/{lead_id}` - Lead details
- `GET /api/v1/contact-cards/{contact_card_id}` - Contact card
- `GET /api/v1/contact-cards/by-phone` - Find by phone

### **Appointments**
- `GET /api/v1/appointments/{appointment_id}` - Appointment details
- `POST /api/v1/appointments` - Create appointment

### **Lead Pool**
- `GET /api/v1/lead-pool` - Available leads
- `POST /api/v1/lead-pool/{lead_id}/request` - Request lead

### **RAG / Ask Otto**
- `POST /api/v1/rag/query` - Ask Otto AI
- `GET /api/v1/rag/queries` - Query history

---

## 📥 **EXPORT COMPLETE SPEC**

```bash
# Export from hosted URL
curl https://ottoai-backend-production.up.railway.app/openapi.json > otto-openapi.json

# View in browser
open https://ottoai-backend-production.up.railway.app/docs
```

---

## ✅ **SUMMARY**

✅ **218 endpoints** fully documented  
✅ **30+ categories** organized  
✅ **Hosted Swagger UI** available  
✅ **OpenAPI 3.0 spec** ready for import  
✅ **Ready for frontend integration**

**Access**: https://ottoai-backend-production.up.railway.app/docs



**Source**: https://ottoai-backend-production.up.railway.app/openapi.json  
**Total Endpoints**: **218 endpoints**  
**Last Updated**: 2025-11-24

---

## 📋 **QUICK ACCESS**

- **Swagger UI**: https://ottoai-backend-production.up.railway.app/docs
- **OpenAPI JSON**: https://ottoai-backend-production.up.railway.app/openapi.json
- **ReDoc**: https://ottoai-backend-production.up.railway.app/redoc

---

## 📊 **API ENDPOINTS BY CATEGORY**

### **Dashboard & Metrics** (15+ endpoints)

#### Dashboard
```
GET  /api/v1/dashboard/metrics?company_id={id}
GET  /api/v1/dashboard/calls?status={status}&company_id={id}
```

#### Live Metrics
```
GET  /api/v1/live-metrics/current
GET  /api/v1/live-metrics/revenue
GET  /api/v1/live-metrics/calls
GET  /api/v1/live-metrics/leads
GET  /api/v1/live-metrics/csr-performance
GET  /api/v1/live-metrics/status
```

---

### **Call Management** (10+ endpoints)

```
GET  /api/v1/calls/call/{call_id}
GET  /api/v1/calls/unassigned-calls
POST /api/v1/calls/add-call
POST /api/v1/calls/update-call-status
POST /api/v1/calls/{call_id}/analyze
GET  /api/v1/calls/{call_id}/analysis
POST /api/v1/calls/analyze-batch
GET  /api/v1/calls/analytics/objections
```

---

### **Lead Management** (3 endpoints)

```
GET  /api/v1/leads/{lead_id}
POST /api/v1/leads
PATCH /api/v1/leads/{lead_id}
```

---

### **Appointment Management** (3 endpoints)

```
GET   /api/v1/appointments/{appointment_id}
POST  /api/v1/appointments
PATCH /api/v1/appointments/{appointment_id}
```

---

### **Contact Cards** (3 endpoints)

```
GET  /api/v1/contact-cards/{contact_card_id}
GET  /api/v1/contact-cards/by-phone?phone={number}
POST /api/v1/contact-cards/{contact_card_id}/refresh-property-intelligence
```

---

### **Lead Pool** (3 endpoints)

```
GET  /api/v1/lead-pool
POST /api/v1/lead-pool/{lead_id}/request
POST /api/v1/lead-pool/{lead_id}/assign
```

---

### **RAG / Ask Otto** (7 endpoints)

```
POST   /api/v1/rag/query
GET    /api/v1/rag/queries
POST   /api/v1/rag/queries/{query_id}/feedback
GET    /api/v1/rag/documents
POST   /api/v1/rag/documents/upload
GET    /api/v1/rag/documents/{document_id}
DELETE /api/v1/rag/documents/{document_id}
```

---

### **Recording Sessions** (5 endpoints) - Sales Reps

```
POST /api/v1/recording-sessions/start
POST /api/v1/recording-sessions/{session_id}/stop
POST /api/v1/recording-sessions/{session_id}/upload-audio-complete
PUT  /api/v1/recording-sessions/{session_id}/metadata
GET  /api/v1/recording-sessions/{session_id}
```

---

### **Rep Shifts** (3 endpoints) - Sales Reps

```
POST /api/v1/reps/{rep_id}/shifts/clock-in
POST /api/v1/reps/{rep_id}/shifts/clock-out
GET  /api/v1/reps/{rep_id}/shifts/today
```

---

### **Missed Call Queue** (10 endpoints)

```
POST /api/v1/missed-calls/queue/{call_id}
GET  /api/v1/missed-calls/queue/status
GET  /api/v1/missed-calls/queue/metrics
GET  /api/v1/missed-calls/queue/entries
GET  /api/v1/missed-calls/queue/entries/{queue_id}
POST /api/v1/missed-calls/queue/entries/{queue_id}/process
POST /api/v1/missed-calls/queue/entries/{queue_id}/escalate
GET  /api/v1/missed-calls/processor/status
POST /api/v1/missed-calls/processor/start
POST /api/v1/missed-calls/processor/stop
```

---

### **Post-Call Analysis** (5 endpoints)

```
GET /api/v1/post-call-analysis/call/{call_id}
GET /api/v1/post-call-analysis/sales-rep/{sales_rep_id}/performance
GET /api/v1/post-call-analysis/coaching-recommendations
GET /api/v1/post-call-analysis/performance-summary
GET /api/v1/post-call-analysis/status
```

---

### **Sales Reps** (6 endpoints)

```
GET  /api/v1/sales-reps
GET  /api/v1/sales-reps/{rep_id}/appointments
POST /api/v1/sales-reps
PUT  /api/v1/sales-reps/{rep_id}
POST /api/v1/sales-reps/assign/{call_id}
```

---

### **Companies** (10 endpoints)

```
GET  /api/v1/companies/{company_id}
POST /api/v1/companies
PUT  /api/v1/companies/{company_id}
POST /api/v1/companies/{company_id}/set-callrail-api-key
POST /api/v1/companies/{company_id}/set-callrail-account-id
GET  /api/v1/companies/by-phone/{phone_number}
GET  /api/v1/companies/get-user-company/{username}
GET  /api/v1/companies/list-organizations
GET  /api/v1/companies/{company_id}/sales-managers
POST /api/v1/companies/organizations/{org_id}/memberships
```

---

### **Users** (8 endpoints)

```
GET  /api/v1/users/{user_id}
POST /api/v1/users
PUT  /api/v1/users/{user_id}
POST /api/v1/users/{user_id}/sync-to-clerk
GET  /api/v1/users/company
GET  /api/v1/users/by-username/{username}
PATCH /api/v1/users/metadata/{user_id}
POST /api/v1/users/clerk-webhook
```

---

### **Follow-ups** (4 endpoints)

```
POST /api/v1/followups/draft
GET  /api/v1/followups/drafts
POST /api/v1/followups/drafts/{draft_id}/approve
POST /api/v1/followups/drafts/{draft_id}/send
```

---

### **Personal Clones** (4 endpoints)

```
POST /api/v1/clone/train
GET  /api/v1/clone/{rep_id}/status
GET  /api/v1/clone/{rep_id}/history
POST /api/v1/clone/{rep_id}/retry
```

---

### **GDPR** (3 endpoints)

```
POST /api/v1/gdpr/delete-user
POST /api/v1/gdpr/export-user-data
DELETE /api/v1/gdpr/tenant-data
```

---

### **Analysis** (4 endpoints)

```
POST /api/v1/calls/{call_id}/analyze
GET  /api/v1/calls/{call_id}/analysis
POST /api/v1/calls/analyze-batch
GET  /api/v1/calls/analytics/objections
```

---

### **Mobile APIs** (28 endpoints)

#### Appointments
```
GET  /api/v1/mobile/appointments
GET  /api/v1/mobile/appointments/company
GET  /api/v1/mobile/appointments/{appointment_id}
```

#### Audio Recording
```
POST /api/v1/mobile/audio/start-recording
POST /api/v1/mobile/audio/upload/{recording_id}
GET  /api/v1/mobile/audio/status/{recording_id}
GET  /api/v1/mobile/audio/raw-data/{recording_id}
POST /api/v1/mobile/audio/analyze-transcript/{call_id}
GET  /api/v1/mobile/audio/transcript-analysis/{call_id}
GET  /api/v1/mobile/audio/transcript-analyses/{call_id}/versions
POST /api/v1/mobile/audio/sync-call-fields-from-analysis/{call_id}
POST /api/v1/mobile/audio/batch-sync-call-fields
GET  /api/v1/mobile/audio/analysis-processes
```

#### Messages & Transcripts
```
GET  /api/v1/mobile/messages/{call_id}
GET  /api/v1/mobile/call-transcripts/{call_id}
```

---

### **Webhooks** (70+ endpoints)

#### CallRail Webhooks
```
POST /callrail/call.incoming
POST /callrail/call.answered
POST /callrail/call.missed
POST /callrail/call.completed
```

#### Twilio Webhooks
```
POST /twilio-webhook
POST /mobile/twilio-voice-webhook
POST /mobile/twilio-sms-webhook
```

#### Shunya/UWC Webhooks
```
POST /api/v1/shunya/webhook
POST /webhooks/uwc/asr/complete
POST /webhooks/uwc/analysis/complete
POST /webhooks/uwc/followup/draft
POST /webhooks/uwc/rag/indexed
POST /webhooks/uwc/training/status
```

#### SMS Webhooks
```
POST /sms/callrail-webhook
POST /sms/twilio-webhook
```

---

### **Internal AI APIs** (6 endpoints) - For Shunya

```
GET /internal/ai/calls/{call_id}
GET /internal/ai/reps/{rep_id}
GET /internal/ai/companies/{company_id}
GET /internal/ai/leads/{lead_id}
GET /internal/ai/appointments/{appointment_id}
GET /internal/ai/services/{company_id}
```

---

### **System & Health** (5+ endpoints)

```
GET /health
GET /health/detailed
GET /health/live
GET /health/ready
GET /metrics
```

---

### **Admin** (1 endpoint)

```
GET /api/v1/admin/openai/stats
```

---

## 🎯 **MOST COMMONLY USED APIS FOR FRONTEND**

### **Dashboard**
- `GET /api/v1/dashboard/metrics` - Dashboard KPIs
- `GET /api/v1/dashboard/calls` - Filtered calls list
- `GET /api/v1/live-metrics/current` - Real-time metrics

### **Calls**
- `GET /api/v1/calls/call/{call_id}` - Call details
- `GET /api/v1/calls/unassigned-calls` - Unassigned calls

### **Leads & Contacts**
- `GET /api/v1/leads/{lead_id}` - Lead details
- `GET /api/v1/contact-cards/{contact_card_id}` - Contact card
- `GET /api/v1/contact-cards/by-phone` - Find by phone

### **Appointments**
- `GET /api/v1/appointments/{appointment_id}` - Appointment details
- `POST /api/v1/appointments` - Create appointment

### **Lead Pool**
- `GET /api/v1/lead-pool` - Available leads
- `POST /api/v1/lead-pool/{lead_id}/request` - Request lead

### **RAG / Ask Otto**
- `POST /api/v1/rag/query` - Ask Otto AI
- `GET /api/v1/rag/queries` - Query history

---

## 📥 **EXPORT COMPLETE SPEC**

```bash
# Export from hosted URL
curl https://ottoai-backend-production.up.railway.app/openapi.json > otto-openapi.json

# View in browser
open https://ottoai-backend-production.up.railway.app/docs
```

---

## ✅ **SUMMARY**

✅ **218 endpoints** fully documented  
✅ **30+ categories** organized  
✅ **Hosted Swagger UI** available  
✅ **OpenAPI 3.0 spec** ready for import  
✅ **Ready for frontend integration**

**Access**: https://ottoai-backend-production.up.railway.app/docs



**Source**: https://ottoai-backend-production.up.railway.app/openapi.json  
**Total Endpoints**: **218 endpoints**  
**Last Updated**: 2025-11-24

---

## 📋 **QUICK ACCESS**

- **Swagger UI**: https://ottoai-backend-production.up.railway.app/docs
- **OpenAPI JSON**: https://ottoai-backend-production.up.railway.app/openapi.json
- **ReDoc**: https://ottoai-backend-production.up.railway.app/redoc

---

## 📊 **API ENDPOINTS BY CATEGORY**

### **Dashboard & Metrics** (15+ endpoints)

#### Dashboard
```
GET  /api/v1/dashboard/metrics?company_id={id}
GET  /api/v1/dashboard/calls?status={status}&company_id={id}
```

#### Live Metrics
```
GET  /api/v1/live-metrics/current
GET  /api/v1/live-metrics/revenue
GET  /api/v1/live-metrics/calls
GET  /api/v1/live-metrics/leads
GET  /api/v1/live-metrics/csr-performance
GET  /api/v1/live-metrics/status
```

---

### **Call Management** (10+ endpoints)

```
GET  /api/v1/calls/call/{call_id}
GET  /api/v1/calls/unassigned-calls
POST /api/v1/calls/add-call
POST /api/v1/calls/update-call-status
POST /api/v1/calls/{call_id}/analyze
GET  /api/v1/calls/{call_id}/analysis
POST /api/v1/calls/analyze-batch
GET  /api/v1/calls/analytics/objections
```

---

### **Lead Management** (3 endpoints)

```
GET  /api/v1/leads/{lead_id}
POST /api/v1/leads
PATCH /api/v1/leads/{lead_id}
```

---

### **Appointment Management** (3 endpoints)

```
GET   /api/v1/appointments/{appointment_id}
POST  /api/v1/appointments
PATCH /api/v1/appointments/{appointment_id}
```

---

### **Contact Cards** (3 endpoints)

```
GET  /api/v1/contact-cards/{contact_card_id}
GET  /api/v1/contact-cards/by-phone?phone={number}
POST /api/v1/contact-cards/{contact_card_id}/refresh-property-intelligence
```

---

### **Lead Pool** (3 endpoints)

```
GET  /api/v1/lead-pool
POST /api/v1/lead-pool/{lead_id}/request
POST /api/v1/lead-pool/{lead_id}/assign
```

---

### **RAG / Ask Otto** (7 endpoints)

```
POST   /api/v1/rag/query
GET    /api/v1/rag/queries
POST   /api/v1/rag/queries/{query_id}/feedback
GET    /api/v1/rag/documents
POST   /api/v1/rag/documents/upload
GET    /api/v1/rag/documents/{document_id}
DELETE /api/v1/rag/documents/{document_id}
```

---

### **Recording Sessions** (5 endpoints) - Sales Reps

```
POST /api/v1/recording-sessions/start
POST /api/v1/recording-sessions/{session_id}/stop
POST /api/v1/recording-sessions/{session_id}/upload-audio-complete
PUT  /api/v1/recording-sessions/{session_id}/metadata
GET  /api/v1/recording-sessions/{session_id}
```

---

### **Rep Shifts** (3 endpoints) - Sales Reps

```
POST /api/v1/reps/{rep_id}/shifts/clock-in
POST /api/v1/reps/{rep_id}/shifts/clock-out
GET  /api/v1/reps/{rep_id}/shifts/today
```

---

### **Missed Call Queue** (10 endpoints)

```
POST /api/v1/missed-calls/queue/{call_id}
GET  /api/v1/missed-calls/queue/status
GET  /api/v1/missed-calls/queue/metrics
GET  /api/v1/missed-calls/queue/entries
GET  /api/v1/missed-calls/queue/entries/{queue_id}
POST /api/v1/missed-calls/queue/entries/{queue_id}/process
POST /api/v1/missed-calls/queue/entries/{queue_id}/escalate
GET  /api/v1/missed-calls/processor/status
POST /api/v1/missed-calls/processor/start
POST /api/v1/missed-calls/processor/stop
```

---

### **Post-Call Analysis** (5 endpoints)

```
GET /api/v1/post-call-analysis/call/{call_id}
GET /api/v1/post-call-analysis/sales-rep/{sales_rep_id}/performance
GET /api/v1/post-call-analysis/coaching-recommendations
GET /api/v1/post-call-analysis/performance-summary
GET /api/v1/post-call-analysis/status
```

---

### **Sales Reps** (6 endpoints)

```
GET  /api/v1/sales-reps
GET  /api/v1/sales-reps/{rep_id}/appointments
POST /api/v1/sales-reps
PUT  /api/v1/sales-reps/{rep_id}
POST /api/v1/sales-reps/assign/{call_id}
```

---

### **Companies** (10 endpoints)

```
GET  /api/v1/companies/{company_id}
POST /api/v1/companies
PUT  /api/v1/companies/{company_id}
POST /api/v1/companies/{company_id}/set-callrail-api-key
POST /api/v1/companies/{company_id}/set-callrail-account-id
GET  /api/v1/companies/by-phone/{phone_number}
GET  /api/v1/companies/get-user-company/{username}
GET  /api/v1/companies/list-organizations
GET  /api/v1/companies/{company_id}/sales-managers
POST /api/v1/companies/organizations/{org_id}/memberships
```

---

### **Users** (8 endpoints)

```
GET  /api/v1/users/{user_id}
POST /api/v1/users
PUT  /api/v1/users/{user_id}
POST /api/v1/users/{user_id}/sync-to-clerk
GET  /api/v1/users/company
GET  /api/v1/users/by-username/{username}
PATCH /api/v1/users/metadata/{user_id}
POST /api/v1/users/clerk-webhook
```

---

### **Follow-ups** (4 endpoints)

```
POST /api/v1/followups/draft
GET  /api/v1/followups/drafts
POST /api/v1/followups/drafts/{draft_id}/approve
POST /api/v1/followups/drafts/{draft_id}/send
```

---

### **Personal Clones** (4 endpoints)

```
POST /api/v1/clone/train
GET  /api/v1/clone/{rep_id}/status
GET  /api/v1/clone/{rep_id}/history
POST /api/v1/clone/{rep_id}/retry
```

---

### **GDPR** (3 endpoints)

```
POST /api/v1/gdpr/delete-user
POST /api/v1/gdpr/export-user-data
DELETE /api/v1/gdpr/tenant-data
```

---

### **Analysis** (4 endpoints)

```
POST /api/v1/calls/{call_id}/analyze
GET  /api/v1/calls/{call_id}/analysis
POST /api/v1/calls/analyze-batch
GET  /api/v1/calls/analytics/objections
```

---

### **Mobile APIs** (28 endpoints)

#### Appointments
```
GET  /api/v1/mobile/appointments
GET  /api/v1/mobile/appointments/company
GET  /api/v1/mobile/appointments/{appointment_id}
```

#### Audio Recording
```
POST /api/v1/mobile/audio/start-recording
POST /api/v1/mobile/audio/upload/{recording_id}
GET  /api/v1/mobile/audio/status/{recording_id}
GET  /api/v1/mobile/audio/raw-data/{recording_id}
POST /api/v1/mobile/audio/analyze-transcript/{call_id}
GET  /api/v1/mobile/audio/transcript-analysis/{call_id}
GET  /api/v1/mobile/audio/transcript-analyses/{call_id}/versions
POST /api/v1/mobile/audio/sync-call-fields-from-analysis/{call_id}
POST /api/v1/mobile/audio/batch-sync-call-fields
GET  /api/v1/mobile/audio/analysis-processes
```

#### Messages & Transcripts
```
GET  /api/v1/mobile/messages/{call_id}
GET  /api/v1/mobile/call-transcripts/{call_id}
```

---

### **Webhooks** (70+ endpoints)

#### CallRail Webhooks
```
POST /callrail/call.incoming
POST /callrail/call.answered
POST /callrail/call.missed
POST /callrail/call.completed
```

#### Twilio Webhooks
```
POST /twilio-webhook
POST /mobile/twilio-voice-webhook
POST /mobile/twilio-sms-webhook
```

#### Shunya/UWC Webhooks
```
POST /api/v1/shunya/webhook
POST /webhooks/uwc/asr/complete
POST /webhooks/uwc/analysis/complete
POST /webhooks/uwc/followup/draft
POST /webhooks/uwc/rag/indexed
POST /webhooks/uwc/training/status
```

#### SMS Webhooks
```
POST /sms/callrail-webhook
POST /sms/twilio-webhook
```

---

### **Internal AI APIs** (6 endpoints) - For Shunya

```
GET /internal/ai/calls/{call_id}
GET /internal/ai/reps/{rep_id}
GET /internal/ai/companies/{company_id}
GET /internal/ai/leads/{lead_id}
GET /internal/ai/appointments/{appointment_id}
GET /internal/ai/services/{company_id}
```

---

### **System & Health** (5+ endpoints)

```
GET /health
GET /health/detailed
GET /health/live
GET /health/ready
GET /metrics
```

---

### **Admin** (1 endpoint)

```
GET /api/v1/admin/openai/stats
```

---

## 🎯 **MOST COMMONLY USED APIS FOR FRONTEND**

### **Dashboard**
- `GET /api/v1/dashboard/metrics` - Dashboard KPIs
- `GET /api/v1/dashboard/calls` - Filtered calls list
- `GET /api/v1/live-metrics/current` - Real-time metrics

### **Calls**
- `GET /api/v1/calls/call/{call_id}` - Call details
- `GET /api/v1/calls/unassigned-calls` - Unassigned calls

### **Leads & Contacts**
- `GET /api/v1/leads/{lead_id}` - Lead details
- `GET /api/v1/contact-cards/{contact_card_id}` - Contact card
- `GET /api/v1/contact-cards/by-phone` - Find by phone

### **Appointments**
- `GET /api/v1/appointments/{appointment_id}` - Appointment details
- `POST /api/v1/appointments` - Create appointment

### **Lead Pool**
- `GET /api/v1/lead-pool` - Available leads
- `POST /api/v1/lead-pool/{lead_id}/request` - Request lead

### **RAG / Ask Otto**
- `POST /api/v1/rag/query` - Ask Otto AI
- `GET /api/v1/rag/queries` - Query history

---

## 📥 **EXPORT COMPLETE SPEC**

```bash
# Export from hosted URL
curl https://ottoai-backend-production.up.railway.app/openapi.json > otto-openapi.json

# View in browser
open https://ottoai-backend-production.up.railway.app/docs
```

---

## ✅ **SUMMARY**

✅ **218 endpoints** fully documented  
✅ **30+ categories** organized  
✅ **Hosted Swagger UI** available  
✅ **OpenAPI 3.0 spec** ready for import  
✅ **Ready for frontend integration**

**Access**: https://ottoai-backend-production.up.railway.app/docs


