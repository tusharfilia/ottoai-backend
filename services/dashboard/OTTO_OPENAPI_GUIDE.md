# Otto Backend - Complete OpenAPI Guide

**For**: Frontend Integration  
**Last Updated**: 2025-11-24  
**Status**: ✅ **READY** - FastAPI auto-generates OpenAPI specs

---

## 🚀 **QUICK ACCESS**

### **🌐 HOSTED (No Setup Required)** ⭐ **RECOMMENDED**

| Resource | URL |
|----------|-----|
| **Swagger UI** | https://ottoai-backend-production.up.railway.app/docs |
| **OpenAPI JSON** | https://ottoai-backend-production.up.railway.app/openapi.json |
| **ReDoc** | https://ottoai-backend-production.up.railway.app/redoc |

**✅ No localhost needed! Use these hosted URLs directly.**

### **💻 Local Development** (Optional)

```bash
# 1. Start backend server
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard
uvicorn app.main:app --reload --port 8000

# 2. Open in browser
http://localhost:8000/docs
```

**What you get**:
- ✅ All 185+ endpoints listed
- ✅ Try APIs directly in browser
- ✅ See request/response schemas
- ✅ Test with authentication
- ✅ Copy curl commands

### **Option 2: ReDoc (Beautiful Docs)**
```
http://localhost:8000/redoc
```

**What you get**:
- ✅ Clean, readable documentation
- ✅ All endpoints organized by tags
- ✅ Request/response examples
- ✅ Better for reading (not testing)

### **Option 3: OpenAPI JSON (Machine-Readable)**
```
http://localhost:8000/openapi.json
```

**What you get**:
- ✅ Complete OpenAPI 3.0 spec
- ✅ Import into Postman
- ✅ Generate TypeScript clients
- ✅ Use with API testing tools

---

## 📥 **EXPORT OPENAPI SPEC**

### **Method 1: From Hosted URL** ⭐ **EASIEST** (No Setup)

```bash
# Export from Railway production (no backend needed!)
curl https://ottoai-backend-production.up.railway.app/openapi.json > otto-openapi.json

# Pretty print it
python3 -m json.tool otto-openapi.json > otto-openapi-formatted.json
```

**✅ Works immediately - no local server needed!**

### **Method 2: Using Export Script** (Local)

```bash
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend
./export_openapi.sh
```

**Output**: `openapi.json` in the backend root directory

### **Method 3: Manual Export** (Local)

```bash
# Make sure backend is running first
curl http://localhost:8000/openapi.json > otto-openapi.json

# Pretty print it
python3 -m json.tool otto-openapi.json > otto-openapi-formatted.json
```

### **Method 3: From Python**

```python
# In Python shell (with backend running)
import requests
import json

response = requests.get('http://localhost:8000/openapi.json')
spec = response.json()

with open('otto-openapi.json', 'w') as f:
    json.dump(spec, f, indent=2)

print(f"✅ Exported {len(spec['paths'])} endpoints")
```

---

## 📊 **API ENDPOINT SUMMARY**

### **Total Endpoints**: ~185+ endpoints across 30+ categories

### **Main API Categories**:

| Category | Endpoints | Base Path | Description |
|----------|-----------|-----------|-------------|
| **Dashboard** | 7+ | `/api/v1/dashboard/*` | Metrics, calls, analytics |
| **Calls** | 4+ | `/api/v1/calls/*` | Call management, details |
| **Leads** | 3+ | `/api/v1/leads/*` | Lead CRUD operations |
| **Appointments** | 3+ | `/api/v1/appointments/*` | Appointment management |
| **Contact Cards** | 3+ | `/api/v1/contact-cards/*` | Contact information |
| **Lead Pool** | 3+ | `/api/v1/lead-pool/*` | Lead assignment, requests |
| **RAG/Ask Otto** | 7+ | `/api/v1/rag/*` | AI queries, documents |
| **Recording Sessions** | 5+ | `/api/v1/recording-sessions/*` | In-person meeting recordings |
| **Rep Shifts** | 3+ | `/api/v1/reps/*/shifts/*` | Clock in/out, shift tracking |
| **Missed Call Queue** | 10+ | `/api/v1/missed-call-queue/*` | Queue management |
| **Live Metrics** | 6+ | `/api/v1/live-metrics/*` | Real-time KPIs |
| **Post-Call Analysis** | 4+ | `/api/v1/post-call-analysis/*` | Coaching, insights |
| **Sales Reps** | 6+ | `/api/v1/sales-reps/*` | Rep management |
| **Companies** | 4+ | `/api/v1/companies/*` | Company settings |
| **Users** | 8+ | `/api/v1/users/*` | User management |
| **Follow-ups** | 4+ | `/api/v1/followups/*` | Draft generation |
| **Clones** | 4+ | `/api/v1/clones/*` | Personal AI training |
| **GDPR** | 3+ | `/api/v1/gdpr/*` | Data export/deletion |
| **Analysis** | 4+ | `/api/v1/analysis/*` | Call analysis |
| **Webhooks** | 5+ | `/webhooks/*` | External integrations |
| **Internal AI** | 6+ | `/internal/ai/*` | Shunya metadata APIs |
| **Mobile** | 10+ | `/api/v1/mobile/*` | Mobile app endpoints |

---

## 🔑 **KEY ENDPOINTS FOR FRONTEND**

### **Dashboard & Metrics**
```
GET  /api/v1/dashboard/metrics?company_id={id}
GET  /api/v1/dashboard/calls?status={status}&company_id={id}
GET  /api/v1/live-metrics/current
GET  /api/v1/live-metrics/revenue
GET  /api/v1/live-metrics/calls
GET  /api/v1/live-metrics/leads
```

### **Calls**
```
GET  /api/v1/calls/call/{call_id}
GET  /api/v1/calls/unassigned-calls
POST /api/v1/calls/add-call
```

### **Leads**
```
GET  /api/v1/leads/{lead_id}
POST /api/v1/leads
PUT  /api/v1/leads/{lead_id}
```

### **Appointments**
```
GET  /api/v1/appointments/{appointment_id}
POST /api/v1/appointments
PUT  /api/v1/appointments/{appointment_id}
```

### **Contact Cards**
```
GET  /api/v1/contact-cards/{contact_card_id}
GET  /api/v1/contact-cards/by-phone?phone={number}
POST /api/v1/contact-cards/{contact_card_id}/refresh-property-intelligence
```

### **Lead Pool**
```
GET  /api/v1/lead-pool
POST /api/v1/lead-pool/{lead_id}/request
POST /api/v1/lead-pool/{lead_id}/assign
```

### **RAG/Ask Otto**
```
POST /api/v1/rag/query
GET  /api/v1/rag/queries
POST /api/v1/rag/queries/{query_id}/feedback
GET  /api/v1/rag/documents
POST /api/v1/rag/documents/upload
```

### **Recording Sessions** (Sales Reps)
```
POST /api/v1/recording-sessions/start
POST /api/v1/recording-sessions/{session_id}/stop
POST /api/v1/recording-sessions/{session_id}/upload-audio-complete
GET  /api/v1/recording-sessions/{session_id}
```

### **Rep Shifts** (Sales Reps)
```
POST /api/v1/reps/{rep_id}/shifts/clock-in
POST /api/v1/reps/{rep_id}/shifts/clock-out
GET  /api/v1/reps/{rep_id}/shifts/today
```

---

## 🔐 **AUTHENTICATION IN OPENAPI**

### **How to Test with Authentication**

**In Swagger UI** (`/docs`):
1. Click **"Authorize"** button (top right)
2. Enter: `Bearer <your_clerk_jwt_token>`
3. Click **"Authorize"**
4. All requests will include the token

**In Postman**:
1. Import `openapi.json`
2. Set environment variable: `JWT_TOKEN`
3. Use in Authorization header: `Bearer {{JWT_TOKEN}}`

**In Code**:
```typescript
const response = await fetch('http://localhost:8000/api/v1/dashboard/calls', {
  headers: {
    'Authorization': `Bearer ${clerkToken}`,
    'Content-Type': 'application/json'
  }
});
```

---

## 📦 **GENERATE TYPESCRIPT CLIENT**

### **Using openapi-typescript**

```bash
# Install
npm install -D openapi-typescript

# Generate types
npx openapi-typescript http://localhost:8000/openapi.json -o src/types/otto-api.ts
```

**Usage**:
```typescript
import type { paths } from './types/otto-api'

// Type-safe API calls
type GetCallsResponse = paths['/api/v1/dashboard/calls']['get']['responses']['200']['content']['application/json']
```

### **Using openapi-generator**

```bash
# Install
npm install -g @openapitools/openapi-generator-cli

# Generate TypeScript client
openapi-generator-cli generate \
  -i http://localhost:8000/openapi.json \
  -g typescript-axios \
  -o src/api/otto-client
```

---

## 📋 **IMPORT INTO POSTMAN**

### **Step 1: Export OpenAPI Spec**
```bash
curl http://localhost:8000/openapi.json > otto-openapi.json
```

### **Step 2: Import into Postman**
1. Open Postman
2. Click **"Import"**
3. Select `otto-openapi.json`
4. ✅ All endpoints imported with schemas!

### **Step 3: Set Environment Variables**
Create environment with:
- `base_url`: `http://localhost:8000`
- `jwt_token`: Your Clerk JWT token
- `company_id`: Your test company ID

### **Step 4: Configure Authorization**
1. Select collection → **Authorization** tab
2. Type: **Bearer Token**
3. Token: `{{jwt_token}}`

---

## 🎯 **FRONTEND INTEGRATION WORKFLOW**

### **Step 1: Get OpenAPI Spec**
```bash
# Start backend
uvicorn app.main:app --reload

# Export spec
curl http://localhost:8000/openapi.json > otto-openapi.json
```

### **Step 2: Review Endpoints**
- Open `http://localhost:8000/docs` in browser
- Browse all endpoints
- Test with "Try it out" button

### **Step 3: Generate TypeScript Types** (Optional)
```bash
npx openapi-typescript http://localhost:8000/openapi.json -o src/types/otto-api.ts
```

### **Step 4: Create API Client**
```typescript
// src/lib/api/otto-client.ts
import type { paths } from '@/types/otto-api'

class OttoApiClient {
  private baseUrl = 'http://localhost:8000'
  
  async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = await getClerkToken() // Your Clerk token getter
    
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })
    
    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`)
    }
    
    return response.json()
  }
  
  // Typed methods
  async getMissedCalls(companyId: string) {
    return this.request<GetCallsResponse>(
      `/api/v1/dashboard/calls?status=missed&company_id=${companyId}`
    )
  }
  
  async getContactCard(contactCardId: string) {
    return this.request<ContactCardResponse>(
      `/api/v1/contact-cards/${contactCardId}`
    )
  }
  
  // ... more methods
}

export const ottoApi = new OttoApiClient()
```

### **Step 5: Use in Components**
```vue
<script setup>
import { ottoApi } from '@/lib/api/otto-client'

const missedCalls = ref([])

onMounted(async () => {
  try {
    missedCalls.value = await ottoApi.getMissedCalls('dev-test-company')
  } catch (error) {
    console.error('Failed to fetch missed calls:', error)
  }
})
</script>
```

---

## 🔍 **FINDING SPECIFIC ENDPOINTS**

### **By Category (Tags)**
OpenAPI spec organizes endpoints by tags:
- `Dashboard` - Dashboard endpoints
- `Calls` - Call management
- `Leads` - Lead management
- `Appointments` - Appointment management
- `Contact Cards` - Contact information
- `RAG` - Ask Otto AI
- `Recording Sessions` - Meeting recordings
- `Rep Shifts` - Shift management
- `Missed Call Queue` - Queue management
- `Live Metrics` - Real-time metrics
- `Sales Reps` - Rep management
- `Companies` - Company settings
- `Users` - User management

### **Search in Swagger UI**
1. Open `http://localhost:8000/docs`
2. Use browser search (Cmd+F / Ctrl+F)
3. Search for endpoint name or path

### **Search in OpenAPI JSON**
```bash
# Search for specific endpoint
grep -i "dashboard/calls" otto-openapi.json

# Count endpoints by tag
grep -o '"tags":\["[^"]*"' otto-openapi.json | sort | uniq -c
```

---

## 📚 **ADDITIONAL RESOURCES**

### **Documentation Files**
- `API_DOCUMENTATION_README.md` - Complete API guide
- `FRONTEND_API_INTEGRATION_GUIDE.md` - Frontend integration steps
- `RBAC_SYSTEM_SPECIFICATION.md` - Role-based access control
- `AUTHENTICATION_RBAC_STATUS.md` - Auth status

### **Postman Collections**
- `Otto_Backend_API.postman_collection.json` - Pre-configured requests
- `Otto_Environments.postman_environment.json` - Environment configs

### **External Docs**
- FastAPI Docs: https://fastapi.tiangolo.com/
- OpenAPI Spec: https://swagger.io/specification/
- Clerk Auth: https://clerk.com/docs

---

## ✅ **QUICK CHECKLIST**

- [ ] Backend server running (`uvicorn app.main:app --reload`)
- [ ] Swagger UI accessible (`http://localhost:8000/docs`)
- [ ] OpenAPI spec exported (`http://localhost:8000/openapi.json`)
- [ ] Postman collection imported (optional)
- [ ] TypeScript types generated (optional)
- [ ] API client created in frontend
- [ ] Authentication token included in requests

---

## 🎯 **SUMMARY**

✅ **FastAPI auto-generates OpenAPI 3.0 spec**  
✅ **185+ endpoints documented**  
✅ **Interactive docs at `/docs`**  
✅ **Machine-readable spec at `/openapi.json`**  
✅ **Ready for frontend integration**

**Next Steps**:
1. Start backend: `uvicorn app.main:app --reload`
2. Open Swagger UI: `http://localhost:8000/docs`
3. Export spec: `curl http://localhost:8000/openapi.json > otto-openapi.json`
4. Start integrating! 🚀




**For**: Frontend Integration  
**Last Updated**: 2025-11-24  
**Status**: ✅ **READY** - FastAPI auto-generates OpenAPI specs

---

## 🚀 **QUICK ACCESS**

### **🌐 HOSTED (No Setup Required)** ⭐ **RECOMMENDED**

| Resource | URL |
|----------|-----|
| **Swagger UI** | https://ottoai-backend-production.up.railway.app/docs |
| **OpenAPI JSON** | https://ottoai-backend-production.up.railway.app/openapi.json |
| **ReDoc** | https://ottoai-backend-production.up.railway.app/redoc |

**✅ No localhost needed! Use these hosted URLs directly.**

### **💻 Local Development** (Optional)

```bash
# 1. Start backend server
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard
uvicorn app.main:app --reload --port 8000

# 2. Open in browser
http://localhost:8000/docs
```

**What you get**:
- ✅ All 185+ endpoints listed
- ✅ Try APIs directly in browser
- ✅ See request/response schemas
- ✅ Test with authentication
- ✅ Copy curl commands

### **Option 2: ReDoc (Beautiful Docs)**
```
http://localhost:8000/redoc
```

**What you get**:
- ✅ Clean, readable documentation
- ✅ All endpoints organized by tags
- ✅ Request/response examples
- ✅ Better for reading (not testing)

### **Option 3: OpenAPI JSON (Machine-Readable)**
```
http://localhost:8000/openapi.json
```

**What you get**:
- ✅ Complete OpenAPI 3.0 spec
- ✅ Import into Postman
- ✅ Generate TypeScript clients
- ✅ Use with API testing tools

---

## 📥 **EXPORT OPENAPI SPEC**

### **Method 1: From Hosted URL** ⭐ **EASIEST** (No Setup)

```bash
# Export from Railway production (no backend needed!)
curl https://ottoai-backend-production.up.railway.app/openapi.json > otto-openapi.json

# Pretty print it
python3 -m json.tool otto-openapi.json > otto-openapi-formatted.json
```

**✅ Works immediately - no local server needed!**

### **Method 2: Using Export Script** (Local)

```bash
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend
./export_openapi.sh
```

**Output**: `openapi.json` in the backend root directory

### **Method 3: Manual Export** (Local)

```bash
# Make sure backend is running first
curl http://localhost:8000/openapi.json > otto-openapi.json

# Pretty print it
python3 -m json.tool otto-openapi.json > otto-openapi-formatted.json
```

### **Method 3: From Python**

```python
# In Python shell (with backend running)
import requests
import json

response = requests.get('http://localhost:8000/openapi.json')
spec = response.json()

with open('otto-openapi.json', 'w') as f:
    json.dump(spec, f, indent=2)

print(f"✅ Exported {len(spec['paths'])} endpoints")
```

---

## 📊 **API ENDPOINT SUMMARY**

### **Total Endpoints**: ~185+ endpoints across 30+ categories

### **Main API Categories**:

| Category | Endpoints | Base Path | Description |
|----------|-----------|-----------|-------------|
| **Dashboard** | 7+ | `/api/v1/dashboard/*` | Metrics, calls, analytics |
| **Calls** | 4+ | `/api/v1/calls/*` | Call management, details |
| **Leads** | 3+ | `/api/v1/leads/*` | Lead CRUD operations |
| **Appointments** | 3+ | `/api/v1/appointments/*` | Appointment management |
| **Contact Cards** | 3+ | `/api/v1/contact-cards/*` | Contact information |
| **Lead Pool** | 3+ | `/api/v1/lead-pool/*` | Lead assignment, requests |
| **RAG/Ask Otto** | 7+ | `/api/v1/rag/*` | AI queries, documents |
| **Recording Sessions** | 5+ | `/api/v1/recording-sessions/*` | In-person meeting recordings |
| **Rep Shifts** | 3+ | `/api/v1/reps/*/shifts/*` | Clock in/out, shift tracking |
| **Missed Call Queue** | 10+ | `/api/v1/missed-call-queue/*` | Queue management |
| **Live Metrics** | 6+ | `/api/v1/live-metrics/*` | Real-time KPIs |
| **Post-Call Analysis** | 4+ | `/api/v1/post-call-analysis/*` | Coaching, insights |
| **Sales Reps** | 6+ | `/api/v1/sales-reps/*` | Rep management |
| **Companies** | 4+ | `/api/v1/companies/*` | Company settings |
| **Users** | 8+ | `/api/v1/users/*` | User management |
| **Follow-ups** | 4+ | `/api/v1/followups/*` | Draft generation |
| **Clones** | 4+ | `/api/v1/clones/*` | Personal AI training |
| **GDPR** | 3+ | `/api/v1/gdpr/*` | Data export/deletion |
| **Analysis** | 4+ | `/api/v1/analysis/*` | Call analysis |
| **Webhooks** | 5+ | `/webhooks/*` | External integrations |
| **Internal AI** | 6+ | `/internal/ai/*` | Shunya metadata APIs |
| **Mobile** | 10+ | `/api/v1/mobile/*` | Mobile app endpoints |

---

## 🔑 **KEY ENDPOINTS FOR FRONTEND**

### **Dashboard & Metrics**
```
GET  /api/v1/dashboard/metrics?company_id={id}
GET  /api/v1/dashboard/calls?status={status}&company_id={id}
GET  /api/v1/live-metrics/current
GET  /api/v1/live-metrics/revenue
GET  /api/v1/live-metrics/calls
GET  /api/v1/live-metrics/leads
```

### **Calls**
```
GET  /api/v1/calls/call/{call_id}
GET  /api/v1/calls/unassigned-calls
POST /api/v1/calls/add-call
```

### **Leads**
```
GET  /api/v1/leads/{lead_id}
POST /api/v1/leads
PUT  /api/v1/leads/{lead_id}
```

### **Appointments**
```
GET  /api/v1/appointments/{appointment_id}
POST /api/v1/appointments
PUT  /api/v1/appointments/{appointment_id}
```

### **Contact Cards**
```
GET  /api/v1/contact-cards/{contact_card_id}
GET  /api/v1/contact-cards/by-phone?phone={number}
POST /api/v1/contact-cards/{contact_card_id}/refresh-property-intelligence
```

### **Lead Pool**
```
GET  /api/v1/lead-pool
POST /api/v1/lead-pool/{lead_id}/request
POST /api/v1/lead-pool/{lead_id}/assign
```

### **RAG/Ask Otto**
```
POST /api/v1/rag/query
GET  /api/v1/rag/queries
POST /api/v1/rag/queries/{query_id}/feedback
GET  /api/v1/rag/documents
POST /api/v1/rag/documents/upload
```

### **Recording Sessions** (Sales Reps)
```
POST /api/v1/recording-sessions/start
POST /api/v1/recording-sessions/{session_id}/stop
POST /api/v1/recording-sessions/{session_id}/upload-audio-complete
GET  /api/v1/recording-sessions/{session_id}
```

### **Rep Shifts** (Sales Reps)
```
POST /api/v1/reps/{rep_id}/shifts/clock-in
POST /api/v1/reps/{rep_id}/shifts/clock-out
GET  /api/v1/reps/{rep_id}/shifts/today
```

---

## 🔐 **AUTHENTICATION IN OPENAPI**

### **How to Test with Authentication**

**In Swagger UI** (`/docs`):
1. Click **"Authorize"** button (top right)
2. Enter: `Bearer <your_clerk_jwt_token>`
3. Click **"Authorize"**
4. All requests will include the token

**In Postman**:
1. Import `openapi.json`
2. Set environment variable: `JWT_TOKEN`
3. Use in Authorization header: `Bearer {{JWT_TOKEN}}`

**In Code**:
```typescript
const response = await fetch('http://localhost:8000/api/v1/dashboard/calls', {
  headers: {
    'Authorization': `Bearer ${clerkToken}`,
    'Content-Type': 'application/json'
  }
});
```

---

## 📦 **GENERATE TYPESCRIPT CLIENT**

### **Using openapi-typescript**

```bash
# Install
npm install -D openapi-typescript

# Generate types
npx openapi-typescript http://localhost:8000/openapi.json -o src/types/otto-api.ts
```

**Usage**:
```typescript
import type { paths } from './types/otto-api'

// Type-safe API calls
type GetCallsResponse = paths['/api/v1/dashboard/calls']['get']['responses']['200']['content']['application/json']
```

### **Using openapi-generator**

```bash
# Install
npm install -g @openapitools/openapi-generator-cli

# Generate TypeScript client
openapi-generator-cli generate \
  -i http://localhost:8000/openapi.json \
  -g typescript-axios \
  -o src/api/otto-client
```

---

## 📋 **IMPORT INTO POSTMAN**

### **Step 1: Export OpenAPI Spec**
```bash
curl http://localhost:8000/openapi.json > otto-openapi.json
```

### **Step 2: Import into Postman**
1. Open Postman
2. Click **"Import"**
3. Select `otto-openapi.json`
4. ✅ All endpoints imported with schemas!

### **Step 3: Set Environment Variables**
Create environment with:
- `base_url`: `http://localhost:8000`
- `jwt_token`: Your Clerk JWT token
- `company_id`: Your test company ID

### **Step 4: Configure Authorization**
1. Select collection → **Authorization** tab
2. Type: **Bearer Token**
3. Token: `{{jwt_token}}`

---

## 🎯 **FRONTEND INTEGRATION WORKFLOW**

### **Step 1: Get OpenAPI Spec**
```bash
# Start backend
uvicorn app.main:app --reload

# Export spec
curl http://localhost:8000/openapi.json > otto-openapi.json
```

### **Step 2: Review Endpoints**
- Open `http://localhost:8000/docs` in browser
- Browse all endpoints
- Test with "Try it out" button

### **Step 3: Generate TypeScript Types** (Optional)
```bash
npx openapi-typescript http://localhost:8000/openapi.json -o src/types/otto-api.ts
```

### **Step 4: Create API Client**
```typescript
// src/lib/api/otto-client.ts
import type { paths } from '@/types/otto-api'

class OttoApiClient {
  private baseUrl = 'http://localhost:8000'
  
  async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = await getClerkToken() // Your Clerk token getter
    
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })
    
    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`)
    }
    
    return response.json()
  }
  
  // Typed methods
  async getMissedCalls(companyId: string) {
    return this.request<GetCallsResponse>(
      `/api/v1/dashboard/calls?status=missed&company_id=${companyId}`
    )
  }
  
  async getContactCard(contactCardId: string) {
    return this.request<ContactCardResponse>(
      `/api/v1/contact-cards/${contactCardId}`
    )
  }
  
  // ... more methods
}

export const ottoApi = new OttoApiClient()
```

### **Step 5: Use in Components**
```vue
<script setup>
import { ottoApi } from '@/lib/api/otto-client'

const missedCalls = ref([])

onMounted(async () => {
  try {
    missedCalls.value = await ottoApi.getMissedCalls('dev-test-company')
  } catch (error) {
    console.error('Failed to fetch missed calls:', error)
  }
})
</script>
```

---

## 🔍 **FINDING SPECIFIC ENDPOINTS**

### **By Category (Tags)**
OpenAPI spec organizes endpoints by tags:
- `Dashboard` - Dashboard endpoints
- `Calls` - Call management
- `Leads` - Lead management
- `Appointments` - Appointment management
- `Contact Cards` - Contact information
- `RAG` - Ask Otto AI
- `Recording Sessions` - Meeting recordings
- `Rep Shifts` - Shift management
- `Missed Call Queue` - Queue management
- `Live Metrics` - Real-time metrics
- `Sales Reps` - Rep management
- `Companies` - Company settings
- `Users` - User management

### **Search in Swagger UI**
1. Open `http://localhost:8000/docs`
2. Use browser search (Cmd+F / Ctrl+F)
3. Search for endpoint name or path

### **Search in OpenAPI JSON**
```bash
# Search for specific endpoint
grep -i "dashboard/calls" otto-openapi.json

# Count endpoints by tag
grep -o '"tags":\["[^"]*"' otto-openapi.json | sort | uniq -c
```

---

## 📚 **ADDITIONAL RESOURCES**

### **Documentation Files**
- `API_DOCUMENTATION_README.md` - Complete API guide
- `FRONTEND_API_INTEGRATION_GUIDE.md` - Frontend integration steps
- `RBAC_SYSTEM_SPECIFICATION.md` - Role-based access control
- `AUTHENTICATION_RBAC_STATUS.md` - Auth status

### **Postman Collections**
- `Otto_Backend_API.postman_collection.json` - Pre-configured requests
- `Otto_Environments.postman_environment.json` - Environment configs

### **External Docs**
- FastAPI Docs: https://fastapi.tiangolo.com/
- OpenAPI Spec: https://swagger.io/specification/
- Clerk Auth: https://clerk.com/docs

---

## ✅ **QUICK CHECKLIST**

- [ ] Backend server running (`uvicorn app.main:app --reload`)
- [ ] Swagger UI accessible (`http://localhost:8000/docs`)
- [ ] OpenAPI spec exported (`http://localhost:8000/openapi.json`)
- [ ] Postman collection imported (optional)
- [ ] TypeScript types generated (optional)
- [ ] API client created in frontend
- [ ] Authentication token included in requests

---

## 🎯 **SUMMARY**

✅ **FastAPI auto-generates OpenAPI 3.0 spec**  
✅ **185+ endpoints documented**  
✅ **Interactive docs at `/docs`**  
✅ **Machine-readable spec at `/openapi.json`**  
✅ **Ready for frontend integration**

**Next Steps**:
1. Start backend: `uvicorn app.main:app --reload`
2. Open Swagger UI: `http://localhost:8000/docs`
3. Export spec: `curl http://localhost:8000/openapi.json > otto-openapi.json`
4. Start integrating! 🚀



