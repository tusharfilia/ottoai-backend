# Otto Backend - Complete API Reference

**Total Endpoints**: **224 endpoints**  
**OpenAPI Version**: 3.0  
**Status**: ✅ **Ready for Frontend Integration**

---

## 🚀 **HOW TO ACCESS**

### **🌐 HOSTED URLs** ⭐ **NO SETUP REQUIRED**

| Resource | URL | Description |
|----------|-----|-------------|
| **Swagger UI** | https://ottoai-backend-production.up.railway.app/docs | Interactive API testing |
| **OpenAPI JSON** | https://ottoai-backend-production.up.railway.app/openapi.json | Machine-readable spec |
| **ReDoc** | https://ottoai-backend-production.up.railway.app/redoc | Beautiful documentation |

**✅ Use these hosted URLs - no localhost needed!**

### **💻 Local Development** (Optional)

| Resource | URL |
|----------|-----|
| **Swagger UI** | http://localhost:8000/docs |
| **OpenAPI JSON** | http://localhost:8000/openapi.json |
| **ReDoc** | http://localhost:8000/redoc |

---

## 📥 **EXPORT OPENAPI SPEC**

### **Quick Export from Hosted URL** ⭐ **EASIEST**
```bash
# Export from Railway production (no setup needed!)
curl https://ottoai-backend-production.up.railway.app/openapi.json > otto-openapi.json

# Pretty print
curl https://ottoai-backend-production.up.railway.app/openapi.json | python3 -m json.tool > otto-openapi-pretty.json
```

**✅ Works immediately - no local server needed!**

### **Export from Localhost** (Optional)
```bash
# Make sure backend is running first
curl http://localhost:8000/openapi.json > otto-openapi.json

# Or use the export script
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend
./export_openapi.sh
```

**Output**: Complete OpenAPI 3.0 specification with all 224 endpoints

---

## 📊 **API ENDPOINT BREAKDOWN**

### **Core Dashboard APIs** (7+ endpoints)
```
GET  /api/v1/dashboard/metrics?company_id={id}
GET  /api/v1/dashboard/calls?status={status}&company_id={id}
```

### **Call Management** (4+ endpoints)
```
GET  /api/v1/calls/call/{call_id}
GET  /api/v1/calls/unassigned-calls
POST /api/v1/calls/add-call
POST /api/v1/calls/update-call-status
```

### **Lead Management** (3+ endpoints)
```
GET  /api/v1/leads/{lead_id}
POST /api/v1/leads
PUT  /api/v1/leads/{lead_id}
```

### **Appointment Management** (3+ endpoints)
```
GET  /api/v1/appointments/{appointment_id}
POST /api/v1/appointments
PUT  /api/v1/appointments/{appointment_id}
```

### **Contact Cards** (3+ endpoints)
```
GET  /api/v1/contact-cards/{contact_card_id}
GET  /api/v1/contact-cards/by-phone?phone={number}
POST /api/v1/contact-cards/{contact_card_id}/refresh-property-intelligence
```

### **Lead Pool** (3+ endpoints)
```
GET  /api/v1/lead-pool
POST /api/v1/lead-pool/{lead_id}/request
POST /api/v1/lead-pool/{lead_id}/assign
```

### **RAG / Ask Otto** (7+ endpoints)
```
POST /api/v1/rag/query
GET  /api/v1/rag/queries
POST /api/v1/rag/queries/{query_id}/feedback
GET  /api/v1/rag/documents
POST /api/v1/rag/documents/upload
GET  /api/v1/rag/documents/{doc_id}
DELETE /api/v1/rag/documents/{doc_id}
```

### **Recording Sessions** (5+ endpoints) - Sales Reps
```
POST /api/v1/recording-sessions/start
POST /api/v1/recording-sessions/{session_id}/stop
POST /api/v1/recording-sessions/{session_id}/upload-audio-complete
PUT  /api/v1/recording-sessions/{session_id}/metadata
GET  /api/v1/recording-sessions/{session_id}
```

### **Rep Shifts** (3+ endpoints) - Sales Reps
```
POST /api/v1/reps/{rep_id}/shifts/clock-in
POST /api/v1/reps/{rep_id}/shifts/clock-out
GET  /api/v1/reps/{rep_id}/shifts/today
```

### **Missed Call Queue** (10+ endpoints)
```
POST /api/v1/missed-call-queue/add
GET  /api/v1/missed-call-queue/status
GET  /api/v1/missed-call-queue/metrics
GET  /api/v1/missed-call-queue/entries
GET  /api/v1/missed-call-queue/entries/{entry_id}
POST /api/v1/missed-call-queue/entries/{entry_id}/process
POST /api/v1/missed-call-queue/entries/{entry_id}/escalate
GET  /api/v1/missed-call-queue/processor/status
POST /api/v1/missed-call-queue/processor/start
POST /api/v1/missed-call-queue/processor/stop
```

### **Live Metrics** (6+ endpoints)
```
GET  /api/v1/live-metrics/current
GET  /api/v1/live-metrics/revenue
GET  /api/v1/live-metrics/calls
GET  /api/v1/live-metrics/leads
GET  /api/v1/live-metrics/csr-performance
```

### **Post-Call Analysis** (4+ endpoints)
```
GET  /api/v1/post-call-analysis/call/{call_id}
GET  /api/v1/post-call-analysis/rep/{rep_id}/performance
GET  /api/v1/post-call-analysis/coaching/{rep_id}
GET  /api/v1/post-call-analysis/summary
```

### **Sales Reps** (6+ endpoints)
```
GET  /api/v1/sales-reps
GET  /api/v1/sales-reps/{rep_id}/appointments
POST /api/v1/sales-reps
PUT  /api/v1/sales-reps/{rep_id}
POST /api/v1/sales-reps/assign/{call_id}
```

### **Companies** (4+ endpoints)
```
GET  /api/v1/companies/{company_id}
POST /api/v1/companies
PUT  /api/v1/companies/{company_id}
POST /api/v1/companies/{company_id}/set-callrail-api-key
POST /api/v1/companies/{company_id}/set-callrail-account-id
```

### **Users** (8+ endpoints)
```
GET  /api/v1/users/{user_id}
POST /api/v1/users
PUT  /api/v1/users/{user_id}
POST /api/v1/users/{user_id}/sync-to-clerk
GET  /api/v1/users/company
```

### **Follow-ups** (4+ endpoints)
```
POST /api/v1/followups/draft
GET  /api/v1/followups/drafts
POST /api/v1/followups/drafts/{draft_id}/approve
POST /api/v1/followups/drafts/{draft_id}/send
```

### **Personal Clones** (4+ endpoints)
```
POST /api/v1/clones/train
GET  /api/v1/clones/{clone_id}/status
GET  /api/v1/clones/history
POST /api/v1/clones/{clone_id}/retry
```

### **GDPR** (3+ endpoints)
```
POST /api/v1/gdpr/users/{user_id}/delete
POST /api/v1/gdpr/users/{user_id}/export
POST /api/v1/gdpr/tenants/{tenant_id}/delete
```

### **Analysis** (4+ endpoints)
```
POST /api/v1/analysis/call/{call_id}
GET  /api/v1/analysis/call/{call_id}
POST /api/v1/analysis/batch
GET  /api/v1/analysis/objections
```

### **Mobile APIs** (10+ endpoints)
```
POST /api/v1/mobile/recording/start
POST /api/v1/mobile/recording/{id}/upload
GET  /api/v1/mobile/appointments
GET  /api/v1/mobile/appointments/{id}
POST /api/v1/mobile/twilio/audio
```

### **Webhooks** (5+ endpoints)
```
POST /callrail/call.incoming
POST /callrail/call.answered
POST /callrail/call.missed
POST /callrail/call.completed
POST /twilio-webhook
POST /sms/callrail-webhook
POST /sms/twilio-webhook
POST /shunya/webhook
```

### **Internal AI APIs** (6+ endpoints) - For Shunya
```
GET  /internal/ai/calls/{call_id}
GET  /internal/ai/reps/{rep_id}
GET  /internal/ai/companies/{company_id}
GET  /internal/ai/leads/{lead_id}
GET  /internal/ai/appointments/{appointment_id}
GET  /internal/ai/services/{company_id}
```

---

## 🔐 **AUTHENTICATION**

### **All Endpoints Require**:
```http
Authorization: Bearer <clerk_jwt_token>
```

### **Backend Automatically Extracts**:
- `tenant_id` (company_id) from JWT `org_id`
- `user_id` from JWT `sub`
- `user_role` from JWT `org_role` (mapped to `manager`/`csr`/`sales_rep`)

### **No Need to Send Separately**:
- ❌ Don't send `company_id` in body (comes from JWT)
- ❌ Don't send `user_id` in body (comes from JWT)
- ❌ Don't send `role` in body (comes from JWT)

---

## 🎯 **FRONTEND INTEGRATION STEPS**

### **Step 1: Get OpenAPI Spec**
```bash
# Option A: From hosted URL (no setup needed!) ⭐
curl https://ottoai-backend-production.up.railway.app/openapi.json > otto-openapi.json

# Option B: From localhost (if running locally)
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard
uvicorn app.main:app --reload
curl http://localhost:8000/openapi.json > otto-openapi.json
```

### **Step 2: Generate TypeScript Types** (Optional)
```bash
# From hosted URL (recommended)
npx openapi-typescript https://ottoai-backend-production.up.railway.app/openapi.json -o src/types/otto-api.ts

# Or from localhost
npx openapi-typescript http://localhost:8000/openapi.json -o src/types/otto-api.ts
```

### **Step 3: Create API Client**
```typescript
// src/lib/api/otto-client.ts
import { useAuth } from '@clerk/nuxt'

class OttoApiClient {
  private baseUrl = process.env.NUXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
  
  private async getHeaders() {
    const { getToken } = useAuth()
    const token = await getToken()
    
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    }
  }
  
  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers = await this.getHeaders()
    
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        ...headers,
        ...options.headers,
      },
    })
    
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || `API Error: ${response.statusText}`)
    }
    
    return response.json()
  }
  
  // Dashboard APIs
  async getDashboardMetrics(companyId: string) {
    return this.request(`/api/v1/dashboard/metrics?company_id=${companyId}`)
  }
  
  async getCalls(status: string, companyId: string) {
    return this.request(`/api/v1/dashboard/calls?status=${status}&company_id=${companyId}`)
  }
  
  // Contact Cards
  async getContactCard(contactCardId: string) {
    return this.request(`/api/v1/contact-cards/${contactCardId}`)
  }
  
  async getContactCardByPhone(phone: string) {
    return this.request(`/api/v1/contact-cards/by-phone?phone=${encodeURIComponent(phone)}`)
  }
  
  // Leads
  async getLead(leadId: string) {
    return this.request(`/api/v1/leads/${leadId}`)
  }
  
  async createLead(data: any) {
    return this.request('/api/v1/leads', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }
  
  // Appointments
  async getAppointment(appointmentId: string) {
    return this.request(`/api/v1/appointments/${appointmentId}`)
  }
  
  async createAppointment(data: any) {
    return this.request('/api/v1/appointments', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }
  
  // RAG / Ask Otto
  async queryAskOtto(query: string, maxResults = 5) {
    return this.request('/api/v1/rag/query', {
      method: 'POST',
      body: JSON.stringify({
        query,
        max_results: maxResults,
      }),
    })
  }
  
  // ... add more methods as needed
}

export const ottoApi = new OttoApiClient()
```

### **Step 4: Use in Components**
```vue
<script setup>
import { ottoApi } from '@/lib/api/otto-client'

const missedCalls = ref([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const response = await ottoApi.getCalls('missed', 'dev-test-company')
    missedCalls.value = response.calls || []
  } catch (error) {
    console.error('Failed to fetch missed calls:', error)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <div v-if="loading">Loading...</div>
    <div v-else>
      <div v-for="call in missedCalls" :key="call.call_id">
        {{ call.name }} - {{ call.phone_number }}
      </div>
    </div>
  </div>
</template>
```

---

## 📚 **ADDITIONAL RESOURCES**

### **Documentation Files**
- `OTTO_OPENAPI_GUIDE.md` - Complete OpenAPI guide
- `EXPORT_OPENAPI.md` - Export instructions
- `API_DOCUMENTATION_README.md` - Full API documentation
- `AUTHENTICATION_RBAC_STATUS.md` - Auth & RBAC status

### **Postman Collections**
- `Otto_Backend_API.postman_collection.json` - Pre-configured requests
- `Otto_Environments.postman_environment.json` - Environment configs

---

## ✅ **SUMMARY**

✅ **224 endpoints** fully documented  
✅ **OpenAPI 3.0 spec** auto-generated by FastAPI  
✅ **Interactive docs** at `/docs`  
✅ **Machine-readable** spec at `/openapi.json`  
✅ **Ready for frontend integration**

**Next Steps**:
1. **Open hosted Swagger UI**: https://ottoai-backend-production.up.railway.app/docs
2. **Export spec**: `curl https://ottoai-backend-production.up.railway.app/openapi.json > otto-openapi.json`
3. **Generate TypeScript types** (optional): `npx openapi-typescript https://ottoai-backend-production.up.railway.app/openapi.json -o src/types/otto-api.ts`
4. **Start integrating!** 🚀

**No localhost needed - use hosted URLs!**


**Total Endpoints**: **224 endpoints**  
**OpenAPI Version**: 3.0  
**Status**: ✅ **Ready for Frontend Integration**

---

## 🚀 **HOW TO ACCESS**

### **🌐 HOSTED URLs** ⭐ **NO SETUP REQUIRED**

| Resource | URL | Description |
|----------|-----|-------------|
| **Swagger UI** | https://ottoai-backend-production.up.railway.app/docs | Interactive API testing |
| **OpenAPI JSON** | https://ottoai-backend-production.up.railway.app/openapi.json | Machine-readable spec |
| **ReDoc** | https://ottoai-backend-production.up.railway.app/redoc | Beautiful documentation |

**✅ Use these hosted URLs - no localhost needed!**

### **💻 Local Development** (Optional)

| Resource | URL |
|----------|-----|
| **Swagger UI** | http://localhost:8000/docs |
| **OpenAPI JSON** | http://localhost:8000/openapi.json |
| **ReDoc** | http://localhost:8000/redoc |

---

## 📥 **EXPORT OPENAPI SPEC**

### **Quick Export from Hosted URL** ⭐ **EASIEST**
```bash
# Export from Railway production (no setup needed!)
curl https://ottoai-backend-production.up.railway.app/openapi.json > otto-openapi.json

# Pretty print
curl https://ottoai-backend-production.up.railway.app/openapi.json | python3 -m json.tool > otto-openapi-pretty.json
```

**✅ Works immediately - no local server needed!**

### **Export from Localhost** (Optional)
```bash
# Make sure backend is running first
curl http://localhost:8000/openapi.json > otto-openapi.json

# Or use the export script
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend
./export_openapi.sh
```

**Output**: Complete OpenAPI 3.0 specification with all 224 endpoints

---

## 📊 **API ENDPOINT BREAKDOWN**

### **Core Dashboard APIs** (7+ endpoints)
```
GET  /api/v1/dashboard/metrics?company_id={id}
GET  /api/v1/dashboard/calls?status={status}&company_id={id}
```

### **Call Management** (4+ endpoints)
```
GET  /api/v1/calls/call/{call_id}
GET  /api/v1/calls/unassigned-calls
POST /api/v1/calls/add-call
POST /api/v1/calls/update-call-status
```

### **Lead Management** (3+ endpoints)
```
GET  /api/v1/leads/{lead_id}
POST /api/v1/leads
PUT  /api/v1/leads/{lead_id}
```

### **Appointment Management** (3+ endpoints)
```
GET  /api/v1/appointments/{appointment_id}
POST /api/v1/appointments
PUT  /api/v1/appointments/{appointment_id}
```

### **Contact Cards** (3+ endpoints)
```
GET  /api/v1/contact-cards/{contact_card_id}
GET  /api/v1/contact-cards/by-phone?phone={number}
POST /api/v1/contact-cards/{contact_card_id}/refresh-property-intelligence
```

### **Lead Pool** (3+ endpoints)
```
GET  /api/v1/lead-pool
POST /api/v1/lead-pool/{lead_id}/request
POST /api/v1/lead-pool/{lead_id}/assign
```

### **RAG / Ask Otto** (7+ endpoints)
```
POST /api/v1/rag/query
GET  /api/v1/rag/queries
POST /api/v1/rag/queries/{query_id}/feedback
GET  /api/v1/rag/documents
POST /api/v1/rag/documents/upload
GET  /api/v1/rag/documents/{doc_id}
DELETE /api/v1/rag/documents/{doc_id}
```

### **Recording Sessions** (5+ endpoints) - Sales Reps
```
POST /api/v1/recording-sessions/start
POST /api/v1/recording-sessions/{session_id}/stop
POST /api/v1/recording-sessions/{session_id}/upload-audio-complete
PUT  /api/v1/recording-sessions/{session_id}/metadata
GET  /api/v1/recording-sessions/{session_id}
```

### **Rep Shifts** (3+ endpoints) - Sales Reps
```
POST /api/v1/reps/{rep_id}/shifts/clock-in
POST /api/v1/reps/{rep_id}/shifts/clock-out
GET  /api/v1/reps/{rep_id}/shifts/today
```

### **Missed Call Queue** (10+ endpoints)
```
POST /api/v1/missed-call-queue/add
GET  /api/v1/missed-call-queue/status
GET  /api/v1/missed-call-queue/metrics
GET  /api/v1/missed-call-queue/entries
GET  /api/v1/missed-call-queue/entries/{entry_id}
POST /api/v1/missed-call-queue/entries/{entry_id}/process
POST /api/v1/missed-call-queue/entries/{entry_id}/escalate
GET  /api/v1/missed-call-queue/processor/status
POST /api/v1/missed-call-queue/processor/start
POST /api/v1/missed-call-queue/processor/stop
```

### **Live Metrics** (6+ endpoints)
```
GET  /api/v1/live-metrics/current
GET  /api/v1/live-metrics/revenue
GET  /api/v1/live-metrics/calls
GET  /api/v1/live-metrics/leads
GET  /api/v1/live-metrics/csr-performance
```

### **Post-Call Analysis** (4+ endpoints)
```
GET  /api/v1/post-call-analysis/call/{call_id}
GET  /api/v1/post-call-analysis/rep/{rep_id}/performance
GET  /api/v1/post-call-analysis/coaching/{rep_id}
GET  /api/v1/post-call-analysis/summary
```

### **Sales Reps** (6+ endpoints)
```
GET  /api/v1/sales-reps
GET  /api/v1/sales-reps/{rep_id}/appointments
POST /api/v1/sales-reps
PUT  /api/v1/sales-reps/{rep_id}
POST /api/v1/sales-reps/assign/{call_id}
```

### **Companies** (4+ endpoints)
```
GET  /api/v1/companies/{company_id}
POST /api/v1/companies
PUT  /api/v1/companies/{company_id}
POST /api/v1/companies/{company_id}/set-callrail-api-key
POST /api/v1/companies/{company_id}/set-callrail-account-id
```

### **Users** (8+ endpoints)
```
GET  /api/v1/users/{user_id}
POST /api/v1/users
PUT  /api/v1/users/{user_id}
POST /api/v1/users/{user_id}/sync-to-clerk
GET  /api/v1/users/company
```

### **Follow-ups** (4+ endpoints)
```
POST /api/v1/followups/draft
GET  /api/v1/followups/drafts
POST /api/v1/followups/drafts/{draft_id}/approve
POST /api/v1/followups/drafts/{draft_id}/send
```

### **Personal Clones** (4+ endpoints)
```
POST /api/v1/clones/train
GET  /api/v1/clones/{clone_id}/status
GET  /api/v1/clones/history
POST /api/v1/clones/{clone_id}/retry
```

### **GDPR** (3+ endpoints)
```
POST /api/v1/gdpr/users/{user_id}/delete
POST /api/v1/gdpr/users/{user_id}/export
POST /api/v1/gdpr/tenants/{tenant_id}/delete
```

### **Analysis** (4+ endpoints)
```
POST /api/v1/analysis/call/{call_id}
GET  /api/v1/analysis/call/{call_id}
POST /api/v1/analysis/batch
GET  /api/v1/analysis/objections
```

### **Mobile APIs** (10+ endpoints)
```
POST /api/v1/mobile/recording/start
POST /api/v1/mobile/recording/{id}/upload
GET  /api/v1/mobile/appointments
GET  /api/v1/mobile/appointments/{id}
POST /api/v1/mobile/twilio/audio
```

### **Webhooks** (5+ endpoints)
```
POST /callrail/call.incoming
POST /callrail/call.answered
POST /callrail/call.missed
POST /callrail/call.completed
POST /twilio-webhook
POST /sms/callrail-webhook
POST /sms/twilio-webhook
POST /shunya/webhook
```

### **Internal AI APIs** (6+ endpoints) - For Shunya
```
GET  /internal/ai/calls/{call_id}
GET  /internal/ai/reps/{rep_id}
GET  /internal/ai/companies/{company_id}
GET  /internal/ai/leads/{lead_id}
GET  /internal/ai/appointments/{appointment_id}
GET  /internal/ai/services/{company_id}
```

---

## 🔐 **AUTHENTICATION**

### **All Endpoints Require**:
```http
Authorization: Bearer <clerk_jwt_token>
```

### **Backend Automatically Extracts**:
- `tenant_id` (company_id) from JWT `org_id`
- `user_id` from JWT `sub`
- `user_role` from JWT `org_role` (mapped to `manager`/`csr`/`sales_rep`)

### **No Need to Send Separately**:
- ❌ Don't send `company_id` in body (comes from JWT)
- ❌ Don't send `user_id` in body (comes from JWT)
- ❌ Don't send `role` in body (comes from JWT)

---

## 🎯 **FRONTEND INTEGRATION STEPS**

### **Step 1: Get OpenAPI Spec**
```bash
# Option A: From hosted URL (no setup needed!) ⭐
curl https://ottoai-backend-production.up.railway.app/openapi.json > otto-openapi.json

# Option B: From localhost (if running locally)
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard
uvicorn app.main:app --reload
curl http://localhost:8000/openapi.json > otto-openapi.json
```

### **Step 2: Generate TypeScript Types** (Optional)
```bash
# From hosted URL (recommended)
npx openapi-typescript https://ottoai-backend-production.up.railway.app/openapi.json -o src/types/otto-api.ts

# Or from localhost
npx openapi-typescript http://localhost:8000/openapi.json -o src/types/otto-api.ts
```

### **Step 3: Create API Client**
```typescript
// src/lib/api/otto-client.ts
import { useAuth } from '@clerk/nuxt'

class OttoApiClient {
  private baseUrl = process.env.NUXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
  
  private async getHeaders() {
    const { getToken } = useAuth()
    const token = await getToken()
    
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    }
  }
  
  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers = await this.getHeaders()
    
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        ...headers,
        ...options.headers,
      },
    })
    
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || `API Error: ${response.statusText}`)
    }
    
    return response.json()
  }
  
  // Dashboard APIs
  async getDashboardMetrics(companyId: string) {
    return this.request(`/api/v1/dashboard/metrics?company_id=${companyId}`)
  }
  
  async getCalls(status: string, companyId: string) {
    return this.request(`/api/v1/dashboard/calls?status=${status}&company_id=${companyId}`)
  }
  
  // Contact Cards
  async getContactCard(contactCardId: string) {
    return this.request(`/api/v1/contact-cards/${contactCardId}`)
  }
  
  async getContactCardByPhone(phone: string) {
    return this.request(`/api/v1/contact-cards/by-phone?phone=${encodeURIComponent(phone)}`)
  }
  
  // Leads
  async getLead(leadId: string) {
    return this.request(`/api/v1/leads/${leadId}`)
  }
  
  async createLead(data: any) {
    return this.request('/api/v1/leads', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }
  
  // Appointments
  async getAppointment(appointmentId: string) {
    return this.request(`/api/v1/appointments/${appointmentId}`)
  }
  
  async createAppointment(data: any) {
    return this.request('/api/v1/appointments', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }
  
  // RAG / Ask Otto
  async queryAskOtto(query: string, maxResults = 5) {
    return this.request('/api/v1/rag/query', {
      method: 'POST',
      body: JSON.stringify({
        query,
        max_results: maxResults,
      }),
    })
  }
  
  // ... add more methods as needed
}

export const ottoApi = new OttoApiClient()
```

### **Step 4: Use in Components**
```vue
<script setup>
import { ottoApi } from '@/lib/api/otto-client'

const missedCalls = ref([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const response = await ottoApi.getCalls('missed', 'dev-test-company')
    missedCalls.value = response.calls || []
  } catch (error) {
    console.error('Failed to fetch missed calls:', error)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <div v-if="loading">Loading...</div>
    <div v-else>
      <div v-for="call in missedCalls" :key="call.call_id">
        {{ call.name }} - {{ call.phone_number }}
      </div>
    </div>
  </div>
</template>
```

---

## 📚 **ADDITIONAL RESOURCES**

### **Documentation Files**
- `OTTO_OPENAPI_GUIDE.md` - Complete OpenAPI guide
- `EXPORT_OPENAPI.md` - Export instructions
- `API_DOCUMENTATION_README.md` - Full API documentation
- `AUTHENTICATION_RBAC_STATUS.md` - Auth & RBAC status

### **Postman Collections**
- `Otto_Backend_API.postman_collection.json` - Pre-configured requests
- `Otto_Environments.postman_environment.json` - Environment configs

---

## ✅ **SUMMARY**

✅ **224 endpoints** fully documented  
✅ **OpenAPI 3.0 spec** auto-generated by FastAPI  
✅ **Interactive docs** at `/docs`  
✅ **Machine-readable** spec at `/openapi.json`  
✅ **Ready for frontend integration**

**Next Steps**:
1. **Open hosted Swagger UI**: https://ottoai-backend-production.up.railway.app/docs
2. **Export spec**: `curl https://ottoai-backend-production.up.railway.app/openapi.json > otto-openapi.json`
3. **Generate TypeScript types** (optional): `npx openapi-typescript https://ottoai-backend-production.up.railway.app/openapi.json -o src/types/otto-api.ts`
4. **Start integrating!** 🚀

**No localhost needed - use hosted URLs!**


**Total Endpoints**: **224 endpoints**  
**OpenAPI Version**: 3.0  
**Status**: ✅ **Ready for Frontend Integration**

---

## 🚀 **HOW TO ACCESS**

### **🌐 HOSTED URLs** ⭐ **NO SETUP REQUIRED**

| Resource | URL | Description |
|----------|-----|-------------|
| **Swagger UI** | https://ottoai-backend-production.up.railway.app/docs | Interactive API testing |
| **OpenAPI JSON** | https://ottoai-backend-production.up.railway.app/openapi.json | Machine-readable spec |
| **ReDoc** | https://ottoai-backend-production.up.railway.app/redoc | Beautiful documentation |

**✅ Use these hosted URLs - no localhost needed!**

### **💻 Local Development** (Optional)

| Resource | URL |
|----------|-----|
| **Swagger UI** | http://localhost:8000/docs |
| **OpenAPI JSON** | http://localhost:8000/openapi.json |
| **ReDoc** | http://localhost:8000/redoc |

---

## 📥 **EXPORT OPENAPI SPEC**

### **Quick Export from Hosted URL** ⭐ **EASIEST**
```bash
# Export from Railway production (no setup needed!)
curl https://ottoai-backend-production.up.railway.app/openapi.json > otto-openapi.json

# Pretty print
curl https://ottoai-backend-production.up.railway.app/openapi.json | python3 -m json.tool > otto-openapi-pretty.json
```

**✅ Works immediately - no local server needed!**

### **Export from Localhost** (Optional)
```bash
# Make sure backend is running first
curl http://localhost:8000/openapi.json > otto-openapi.json

# Or use the export script
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend
./export_openapi.sh
```

**Output**: Complete OpenAPI 3.0 specification with all 224 endpoints

---

## 📊 **API ENDPOINT BREAKDOWN**

### **Core Dashboard APIs** (7+ endpoints)
```
GET  /api/v1/dashboard/metrics?company_id={id}
GET  /api/v1/dashboard/calls?status={status}&company_id={id}
```

### **Call Management** (4+ endpoints)
```
GET  /api/v1/calls/call/{call_id}
GET  /api/v1/calls/unassigned-calls
POST /api/v1/calls/add-call
POST /api/v1/calls/update-call-status
```

### **Lead Management** (3+ endpoints)
```
GET  /api/v1/leads/{lead_id}
POST /api/v1/leads
PUT  /api/v1/leads/{lead_id}
```

### **Appointment Management** (3+ endpoints)
```
GET  /api/v1/appointments/{appointment_id}
POST /api/v1/appointments
PUT  /api/v1/appointments/{appointment_id}
```

### **Contact Cards** (3+ endpoints)
```
GET  /api/v1/contact-cards/{contact_card_id}
GET  /api/v1/contact-cards/by-phone?phone={number}
POST /api/v1/contact-cards/{contact_card_id}/refresh-property-intelligence
```

### **Lead Pool** (3+ endpoints)
```
GET  /api/v1/lead-pool
POST /api/v1/lead-pool/{lead_id}/request
POST /api/v1/lead-pool/{lead_id}/assign
```

### **RAG / Ask Otto** (7+ endpoints)
```
POST /api/v1/rag/query
GET  /api/v1/rag/queries
POST /api/v1/rag/queries/{query_id}/feedback
GET  /api/v1/rag/documents
POST /api/v1/rag/documents/upload
GET  /api/v1/rag/documents/{doc_id}
DELETE /api/v1/rag/documents/{doc_id}
```

### **Recording Sessions** (5+ endpoints) - Sales Reps
```
POST /api/v1/recording-sessions/start
POST /api/v1/recording-sessions/{session_id}/stop
POST /api/v1/recording-sessions/{session_id}/upload-audio-complete
PUT  /api/v1/recording-sessions/{session_id}/metadata
GET  /api/v1/recording-sessions/{session_id}
```

### **Rep Shifts** (3+ endpoints) - Sales Reps
```
POST /api/v1/reps/{rep_id}/shifts/clock-in
POST /api/v1/reps/{rep_id}/shifts/clock-out
GET  /api/v1/reps/{rep_id}/shifts/today
```

### **Missed Call Queue** (10+ endpoints)
```
POST /api/v1/missed-call-queue/add
GET  /api/v1/missed-call-queue/status
GET  /api/v1/missed-call-queue/metrics
GET  /api/v1/missed-call-queue/entries
GET  /api/v1/missed-call-queue/entries/{entry_id}
POST /api/v1/missed-call-queue/entries/{entry_id}/process
POST /api/v1/missed-call-queue/entries/{entry_id}/escalate
GET  /api/v1/missed-call-queue/processor/status
POST /api/v1/missed-call-queue/processor/start
POST /api/v1/missed-call-queue/processor/stop
```

### **Live Metrics** (6+ endpoints)
```
GET  /api/v1/live-metrics/current
GET  /api/v1/live-metrics/revenue
GET  /api/v1/live-metrics/calls
GET  /api/v1/live-metrics/leads
GET  /api/v1/live-metrics/csr-performance
```

### **Post-Call Analysis** (4+ endpoints)
```
GET  /api/v1/post-call-analysis/call/{call_id}
GET  /api/v1/post-call-analysis/rep/{rep_id}/performance
GET  /api/v1/post-call-analysis/coaching/{rep_id}
GET  /api/v1/post-call-analysis/summary
```

### **Sales Reps** (6+ endpoints)
```
GET  /api/v1/sales-reps
GET  /api/v1/sales-reps/{rep_id}/appointments
POST /api/v1/sales-reps
PUT  /api/v1/sales-reps/{rep_id}
POST /api/v1/sales-reps/assign/{call_id}
```

### **Companies** (4+ endpoints)
```
GET  /api/v1/companies/{company_id}
POST /api/v1/companies
PUT  /api/v1/companies/{company_id}
POST /api/v1/companies/{company_id}/set-callrail-api-key
POST /api/v1/companies/{company_id}/set-callrail-account-id
```

### **Users** (8+ endpoints)
```
GET  /api/v1/users/{user_id}
POST /api/v1/users
PUT  /api/v1/users/{user_id}
POST /api/v1/users/{user_id}/sync-to-clerk
GET  /api/v1/users/company
```

### **Follow-ups** (4+ endpoints)
```
POST /api/v1/followups/draft
GET  /api/v1/followups/drafts
POST /api/v1/followups/drafts/{draft_id}/approve
POST /api/v1/followups/drafts/{draft_id}/send
```

### **Personal Clones** (4+ endpoints)
```
POST /api/v1/clones/train
GET  /api/v1/clones/{clone_id}/status
GET  /api/v1/clones/history
POST /api/v1/clones/{clone_id}/retry
```

### **GDPR** (3+ endpoints)
```
POST /api/v1/gdpr/users/{user_id}/delete
POST /api/v1/gdpr/users/{user_id}/export
POST /api/v1/gdpr/tenants/{tenant_id}/delete
```

### **Analysis** (4+ endpoints)
```
POST /api/v1/analysis/call/{call_id}
GET  /api/v1/analysis/call/{call_id}
POST /api/v1/analysis/batch
GET  /api/v1/analysis/objections
```

### **Mobile APIs** (10+ endpoints)
```
POST /api/v1/mobile/recording/start
POST /api/v1/mobile/recording/{id}/upload
GET  /api/v1/mobile/appointments
GET  /api/v1/mobile/appointments/{id}
POST /api/v1/mobile/twilio/audio
```

### **Webhooks** (5+ endpoints)
```
POST /callrail/call.incoming
POST /callrail/call.answered
POST /callrail/call.missed
POST /callrail/call.completed
POST /twilio-webhook
POST /sms/callrail-webhook
POST /sms/twilio-webhook
POST /shunya/webhook
```

### **Internal AI APIs** (6+ endpoints) - For Shunya
```
GET  /internal/ai/calls/{call_id}
GET  /internal/ai/reps/{rep_id}
GET  /internal/ai/companies/{company_id}
GET  /internal/ai/leads/{lead_id}
GET  /internal/ai/appointments/{appointment_id}
GET  /internal/ai/services/{company_id}
```

---

## 🔐 **AUTHENTICATION**

### **All Endpoints Require**:
```http
Authorization: Bearer <clerk_jwt_token>
```

### **Backend Automatically Extracts**:
- `tenant_id` (company_id) from JWT `org_id`
- `user_id` from JWT `sub`
- `user_role` from JWT `org_role` (mapped to `manager`/`csr`/`sales_rep`)

### **No Need to Send Separately**:
- ❌ Don't send `company_id` in body (comes from JWT)
- ❌ Don't send `user_id` in body (comes from JWT)
- ❌ Don't send `role` in body (comes from JWT)

---

## 🎯 **FRONTEND INTEGRATION STEPS**

### **Step 1: Get OpenAPI Spec**
```bash
# Option A: From hosted URL (no setup needed!) ⭐
curl https://ottoai-backend-production.up.railway.app/openapi.json > otto-openapi.json

# Option B: From localhost (if running locally)
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard
uvicorn app.main:app --reload
curl http://localhost:8000/openapi.json > otto-openapi.json
```

### **Step 2: Generate TypeScript Types** (Optional)
```bash
# From hosted URL (recommended)
npx openapi-typescript https://ottoai-backend-production.up.railway.app/openapi.json -o src/types/otto-api.ts

# Or from localhost
npx openapi-typescript http://localhost:8000/openapi.json -o src/types/otto-api.ts
```

### **Step 3: Create API Client**
```typescript
// src/lib/api/otto-client.ts
import { useAuth } from '@clerk/nuxt'

class OttoApiClient {
  private baseUrl = process.env.NUXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
  
  private async getHeaders() {
    const { getToken } = useAuth()
    const token = await getToken()
    
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    }
  }
  
  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers = await this.getHeaders()
    
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        ...headers,
        ...options.headers,
      },
    })
    
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || `API Error: ${response.statusText}`)
    }
    
    return response.json()
  }
  
  // Dashboard APIs
  async getDashboardMetrics(companyId: string) {
    return this.request(`/api/v1/dashboard/metrics?company_id=${companyId}`)
  }
  
  async getCalls(status: string, companyId: string) {
    return this.request(`/api/v1/dashboard/calls?status=${status}&company_id=${companyId}`)
  }
  
  // Contact Cards
  async getContactCard(contactCardId: string) {
    return this.request(`/api/v1/contact-cards/${contactCardId}`)
  }
  
  async getContactCardByPhone(phone: string) {
    return this.request(`/api/v1/contact-cards/by-phone?phone=${encodeURIComponent(phone)}`)
  }
  
  // Leads
  async getLead(leadId: string) {
    return this.request(`/api/v1/leads/${leadId}`)
  }
  
  async createLead(data: any) {
    return this.request('/api/v1/leads', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }
  
  // Appointments
  async getAppointment(appointmentId: string) {
    return this.request(`/api/v1/appointments/${appointmentId}`)
  }
  
  async createAppointment(data: any) {
    return this.request('/api/v1/appointments', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }
  
  // RAG / Ask Otto
  async queryAskOtto(query: string, maxResults = 5) {
    return this.request('/api/v1/rag/query', {
      method: 'POST',
      body: JSON.stringify({
        query,
        max_results: maxResults,
      }),
    })
  }
  
  // ... add more methods as needed
}

export const ottoApi = new OttoApiClient()
```

### **Step 4: Use in Components**
```vue
<script setup>
import { ottoApi } from '@/lib/api/otto-client'

const missedCalls = ref([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const response = await ottoApi.getCalls('missed', 'dev-test-company')
    missedCalls.value = response.calls || []
  } catch (error) {
    console.error('Failed to fetch missed calls:', error)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <div v-if="loading">Loading...</div>
    <div v-else>
      <div v-for="call in missedCalls" :key="call.call_id">
        {{ call.name }} - {{ call.phone_number }}
      </div>
    </div>
  </div>
</template>
```

---

## 📚 **ADDITIONAL RESOURCES**

### **Documentation Files**
- `OTTO_OPENAPI_GUIDE.md` - Complete OpenAPI guide
- `EXPORT_OPENAPI.md` - Export instructions
- `API_DOCUMENTATION_README.md` - Full API documentation
- `AUTHENTICATION_RBAC_STATUS.md` - Auth & RBAC status

### **Postman Collections**
- `Otto_Backend_API.postman_collection.json` - Pre-configured requests
- `Otto_Environments.postman_environment.json` - Environment configs

---

## ✅ **SUMMARY**

✅ **224 endpoints** fully documented  
✅ **OpenAPI 3.0 spec** auto-generated by FastAPI  
✅ **Interactive docs** at `/docs`  
✅ **Machine-readable** spec at `/openapi.json`  
✅ **Ready for frontend integration**

**Next Steps**:
1. **Open hosted Swagger UI**: https://ottoai-backend-production.up.railway.app/docs
2. **Export spec**: `curl https://ottoai-backend-production.up.railway.app/openapi.json > otto-openapi.json`
3. **Generate TypeScript types** (optional): `npx openapi-typescript https://ottoai-backend-production.up.railway.app/openapi.json -o src/types/otto-api.ts`
4. **Start integrating!** 🚀

**No localhost needed - use hosted URLs!**

