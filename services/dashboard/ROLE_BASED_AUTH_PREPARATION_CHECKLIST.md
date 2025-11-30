# Role-Based Authentication Preparation Checklist

**Date**: 2025-11-24  
**Status**: ✅ **READY** - Most things are already set up!

---

## ✅ **WHAT'S ALREADY DONE**

### **Backend** ✅
- ✅ Clerk JWT authentication middleware (`TenantContextMiddleware`)
- ✅ RBAC decorators (`@require_role()`) on all endpoints
- ✅ Role standardization (`manager`, `csr`, `sales_rep`)
- ✅ Tenant isolation (automatic filtering by `company_id`)
- ✅ Dev mode bypass (for local testing without Clerk)
- ✅ JWKS URL configuration (auto-generated from `CLERK_FRONTEND_ORIGIN`)

### **Frontend** ✅
- ✅ Clerk integration (`@clerk/nuxt` module)
- ✅ Clerk plugin configured
- ✅ Environment variables structure in place

---

## 🔧 **WHAT NEEDS TO BE DONE**

### **1. Backend Environment Variables** ⚠️ **REQUIRED FOR PRODUCTION**

**For Local Development (Dev Mode)**:
```bash
# Already working - no Clerk needed!
export DEV_MODE=true
export DEV_TEST_COMPANY_ID=dev-test-company
export DEV_TEST_USER_ID=dev-test-user
```

**For Production/Staging (Real Clerk)**:
```bash
# Required Clerk credentials
export CLERK_SECRET_KEY=sk_live_...          # From Clerk Dashboard
export CLERK_PUBLISHABLE_KEY=pk_live_...     # From Clerk Dashboard
export CLERK_FRONTEND_ORIGIN=https://your-clerk-instance.clerk.accounts.dev
export CLERK_API_URL=https://api.clerk.dev/v1  # Default is fine
```

**Where to get Clerk credentials**:
1. Go to https://dashboard.clerk.com/
2. Select your application
3. Go to **API Keys** section
4. Copy:
   - **Secret Key** → `CLERK_SECRET_KEY`
   - **Publishable Key** → `CLERK_PUBLISHABLE_KEY`
   - **Frontend API** URL → `CLERK_FRONTEND_ORIGIN`

**JWKS URL** (auto-generated):
- Backend automatically constructs: `{CLERK_FRONTEND_ORIGIN}/.well-known/jwks.json`
- No manual configuration needed ✅

---

### **2. Frontend Environment Variables** ⚠️ **REQUIRED**

**Location**: `ottoai-frontend/.env.local` or `.env`

```bash
# Backend API URL
NUXT_PUBLIC_BACKEND_URL=http://localhost:8000

# Clerk Publishable Key (same as backend)
NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...  # From Clerk Dashboard
```

**Where to get**:
- Same Clerk Dashboard → **Publishable Key**

---

### **3. Frontend API Client** ⚠️ **VERIFY THIS**

**Check**: Does your frontend API client include the Clerk token?

**Expected Pattern**:
```typescript
// lib/api/client.ts or similar
import { useAuth } from '@clerk/nuxt'

async function apiRequest(endpoint: string, options: RequestInit = {}) {
  const { getToken } = useAuth()
  const token = await getToken()
  
  return fetch(`${BACKEND_URL}${endpoint}`, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,  // ← MUST include this
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
}
```

**If missing**: Add token to all API requests.

---

### **4. Clerk Organization Setup** ⚠️ **REQUIRED FOR PRODUCTION**

**In Clerk Dashboard**:

1. **Create Organizations** (one per company):
   - Go to **Organizations** → **Create Organization**
   - Name: Your company name
   - This becomes the `org_id` (tenant_id) in JWT

2. **Assign Roles to Users**:
   - Go to **Users** → Select user → **Organizations** tab
   - Add user to organization
   - Assign role: `manager`, `csr`, or `rep` (Clerk will map to `sales_rep`)

3. **Role Mapping** (already handled by backend):
   - Clerk role `admin`/`exec`/`manager` → Otto role `manager`
   - Clerk role `csr` → Otto role `csr`
   - Clerk role `rep` → Otto role `sales_rep`

---

### **5. Frontend Role Context** ⚠️ **RECOMMENDED**

**Create a composable/hook to get user role**:

```typescript
// composables/useUserRole.ts
import { useAuth, useUser } from '@clerk/nuxt'
import jwtDecode from 'jwt-decode'

export const useUserRole = () => {
  const { getToken } = useAuth()
  const { user } = useUser()
  
  const getUserRole = async (): Promise<string> => {
    const token = await getToken()
    if (!token) return null
    
    const decoded = jwtDecode(token) as any
    const clerkRole = decoded.org_role || decoded.role
    
    // Map Clerk role to Otto role (same as backend)
    if (['admin', 'exec', 'manager'].includes(clerkRole)) {
      return 'manager'
    } else if (clerkRole === 'csr') {
      return 'csr'
    } else {
      return 'sales_rep'
    }
  }
  
  return {
    getUserRole,
    userRole: useState('userRole', () => null)
  }
}
```

**Usage in components**:
```vue
<script setup>
const { getUserRole, userRole } = useUserRole()

onMounted(async () => {
  userRole.value = await getUserRole()
})
</script>

<template>
  <div v-if="userRole === 'manager'">
    <!-- Manager-only UI -->
  </div>
</template>
```

---

### **6. Testing Checklist** ✅

**Local Development (Dev Mode)**:
```bash
# ✅ Already works - no Clerk needed!
# Backend uses DEV_MODE=true to bypass authentication
# All endpoints work with default test company/user
```

**With Real Clerk**:
1. ✅ User logs in via Clerk
2. ✅ Frontend gets JWT token
3. ✅ Frontend includes token in API requests
4. ✅ Backend extracts role from token
5. ✅ Backend enforces RBAC
6. ✅ Backend filters data by role

**Test Endpoints**:
```bash
# Test with Clerk token
curl -H "Authorization: Bearer <clerk_jwt_token>" \
     "http://localhost:8000/api/v1/dashboard/calls?status=missed&company_id=YOUR_COMPANY_ID"

# Should return 200 if role has permission
# Should return 403 if role doesn't have permission
```

---

## 🚨 **CRITICAL: What Happens If Not Configured**

### **Scenario 1: Dev Mode (Current Setup)** ✅
- **Status**: ✅ **WORKS**
- **No Clerk needed**: Backend uses `DEV_MODE=true`
- **Default role**: `manager` (full access)
- **Default company**: `dev-test-company`
- **No authentication required**: All endpoints accessible

### **Scenario 2: Production Without Clerk** ❌
- **Status**: ❌ **WILL FAIL**
- **All requests**: Will return `403 Forbidden`
- **Error**: "Missing or invalid tenant_id in JWT claims"
- **Fix**: Set up Clerk credentials

### **Scenario 3: Frontend Without Token** ❌
- **Status**: ❌ **WILL FAIL**
- **All API calls**: Will return `401 Unauthorized` or `403 Forbidden`
- **Error**: "Authorization header missing or invalid"
- **Fix**: Include `Authorization: Bearer <token>` in all requests

---

## 📋 **QUICK START CHECKLIST**

### **For Local Development (Right Now)**:
- [x] ✅ Dev mode is enabled (`DEV_MODE=true`)
- [x] ✅ Backend is running
- [x] ✅ All endpoints are protected with RBAC
- [x] ✅ Role standardization is complete
- [ ] ⚠️ **Optional**: Test with real Clerk token (if you want)

### **For Production**:
- [ ] ⚠️ Get Clerk credentials from dashboard
- [ ] ⚠️ Set `CLERK_SECRET_KEY` in backend `.env`
- [ ] ⚠️ Set `CLERK_PUBLISHABLE_KEY` in frontend `.env`
- [ ] ⚠️ Set `CLERK_FRONTEND_ORIGIN` in backend `.env`
- [ ] ⚠️ Create organizations in Clerk (one per company)
- [ ] ⚠️ Assign users to organizations with roles
- [ ] ⚠️ Verify frontend API client includes tokens
- [ ] ⚠️ Test authentication flow end-to-end

---

## 🎯 **SUMMARY**

### **Current Status**: ✅ **READY FOR LOCAL DEVELOPMENT**

**What works now**:
- ✅ Backend RBAC fully implemented
- ✅ Dev mode bypass working
- ✅ All endpoints protected
- ✅ Role standardization complete

**What needs to be done for production**:
1. ⚠️ Get Clerk credentials
2. ⚠️ Set environment variables
3. ⚠️ Verify frontend includes tokens
4. ⚠️ Set up Clerk organizations and roles

**For your current testing**:
- ✅ **Nothing needs to be done** - dev mode handles everything!
- ✅ You can test the missed call flow right now
- ✅ All endpoints work without Clerk authentication

---

## 🔍 **VERIFICATION COMMANDS**

**Check if backend is ready**:
```bash
# Should return 200
curl http://localhost:8000/health

# Should return 200 (dev mode bypasses auth)
curl "http://localhost:8000/api/v1/dashboard/calls?status=missed&company_id=dev-test-company"
```

**Check if Clerk is configured** (optional):
```bash
# Check if JWKS URL is accessible
curl https://your-clerk-instance.clerk.accounts.dev/.well-known/jwks.json
```

---

## 📚 **NEXT STEPS**

1. **Continue with local testing** (dev mode is fine)
2. **When ready for production**: Set up Clerk credentials
3. **Frontend integration**: Ensure API client includes tokens
4. **Test with real users**: Create Clerk organizations and assign roles

**You're ready to go!** 🚀

