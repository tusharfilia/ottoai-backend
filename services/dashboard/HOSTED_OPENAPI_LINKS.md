# Otto Backend - Hosted OpenAPI Links

**Last Updated**: 2025-11-24  
**Status**: ✅ **Available on Railway Production**

---

## 🌐 **HOSTED OPENAPI LINKS**

### **Railway Production** (Your Current Deployment)

| Resource | URL | Description |
|----------|-----|-------------|
| **Swagger UI** | https://ottoai-backend-production.up.railway.app/docs | Interactive API testing |
| **ReDoc** | https://ottoai-backend-production.up.railway.app/redoc | Beautiful documentation |
| **OpenAPI JSON** | https://ottoai-backend-production.up.railway.app/openapi.json | Machine-readable spec |
| **Health Check** | https://ottoai-backend-production.up.railway.app/health | Server status |

### **Quick Access**
```
✅ Swagger UI: https://ottoai-backend-production.up.railway.app/docs
✅ OpenAPI Spec: https://ottoai-backend-production.up.railway.app/openapi.json
```

---

## 📥 **EXPORT FROM HOSTED URL**

### **Export OpenAPI Spec**
```bash
# Export from Railway production
curl https://ottoai-backend-production.up.railway.app/openapi.json > otto-openapi-production.json

# Pretty print
curl https://ottoai-backend-production.up.railway.app/openapi.json | python3 -m json.tool > otto-openapi-pretty.json
```

### **Import into Postman**
1. Open Postman
2. Click **"Import"**
3. Enter URL: `https://ottoai-backend-production.up.railway.app/openapi.json`
4. ✅ All endpoints imported!

### **Generate TypeScript Client**
```bash
# From hosted URL
npx openapi-typescript https://ottoai-backend-production.up.railway.app/openapi.json -o src/types/otto-api.ts

# Or download first, then generate
curl https://ottoai-backend-production.up.railway.app/openapi.json > otto-openapi.json
npx openapi-typescript otto-openapi.json -o src/types/otto-api.ts
```

---

## 🔐 **AUTHENTICATION ON HOSTED URL**

### **Testing in Swagger UI**

1. Open: https://ottoai-backend-production.up.railway.app/docs
2. Click **"Authorize"** button (top right)
3. Enter: `Bearer <your_clerk_jwt_token>`
4. Click **"Authorize"**
5. All requests will include the token

### **Note**: 
- Hosted URL requires **real Clerk authentication** (no dev mode)
- You'll need a valid Clerk JWT token to test endpoints
- Dev mode only works on localhost

---

## 🎯 **FRONTEND INTEGRATION**

### **Use Hosted URL in Frontend**

```typescript
// src/lib/api/otto-client.ts
const BASE_URL = process.env.NUXT_PUBLIC_BACKEND_URL || 
                 'https://ottoai-backend-production.up.railway.app'

class OttoApiClient {
  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const token = await getClerkToken()
    
    const response = await fetch(`${BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })
    
    return response.json()
  }
}
```

### **Environment Variables**

```bash
# .env.production
NUXT_PUBLIC_BACKEND_URL=https://ottoai-backend-production.up.railway.app
NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...
```

---

## ✅ **VERIFICATION**

### **Check if Hosted URL is Accessible**
```bash
# Health check
curl https://ottoai-backend-production.up.railway.app/health

# OpenAPI spec
curl https://ottoai-backend-production.up.railway.app/openapi.json | head -20
```

### **Expected Response**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-24T..."
}
```

---

## 📋 **SUMMARY**

✅ **Hosted Swagger UI**: https://ottoai-backend-production.up.railway.app/docs  
✅ **Hosted OpenAPI Spec**: https://ottoai-backend-production.up.railway.app/openapi.json  
✅ **Hosted ReDoc**: https://ottoai-backend-production.up.railway.app/redoc  
✅ **224 endpoints** available  
✅ **Ready for frontend integration**

**No localhost needed!** Use the hosted URLs directly. 🚀

