# Otto Backend API Documentation

**Version**: 1.0  
**Last Updated**: October 10, 2025  
**Status**: ✅ Complete and Ready for Frontend Team

---

## 📦 What You're Getting

This package includes everything your outsourced frontend team needs to integrate with Otto's backend:

### **1. Interactive Documentation** 
- **Swagger UI**: http://localhost:8000/docs (try API in browser)
- **ReDoc**: http://localhost:8000/redoc (beautiful reference docs)
- **OpenAPI Spec**: http://localhost:8000/openapi.json (machine-readable)

### **2. Postman Collection**
- **File**: `Otto_Backend_API.postman_collection.json`
- **Contains**: 50+ pre-configured API requests with examples
- **Organized**: 10 categories (Companies, Users, Calls, AI Features, etc.)

### **3. Postman Environments**
- **File**: `Otto_Environments.postman_environment.json`
- **Includes**: Local, Staging, Production configs
- **Pre-configured**: Base URLs, sample IDs, JWT token placeholders

### **4. Comprehensive Guides**
- **API Documentation Guide**: `../ottoai-docs/workspace/API_DOCUMENTATION_GUIDE.md` (complete reference)
- **Frontend Integration Guide**: `../ottoai-docs/workspace/FRONTEND_API_INTEGRATION_GUIDE.md` (step-by-step)
- **RBAC Specification**: `../ottoai-docs/workspace/RBAC_SYSTEM_SPECIFICATION.md` (role permissions)

### **5. Export Tools**
- **Script**: `export_openapi.sh` (export latest API spec)

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Start Backend Server

```bash
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard
uvicorn app.main:app --reload
```

### Step 2: Verify Server Running

Open browser: http://localhost:8000/docs

**Expected**: Swagger UI with all API endpoints listed

### Step 3: Import Postman Collection

1. Open Postman Desktop App
2. Click **"Import"** button
3. Select **`Otto_Backend_API.postman_collection.json`**
4. Select **`Otto_Environments.postman_environment.json`**
5. Switch to **"Local Development"** environment (top-right dropdown)

### Step 4: Test an Endpoint

1. In Postman, open **"1. Health & System"** → **"Health Check"**
2. Click **"Send"**
3. **Expected**: `200 OK` with `{"status": "healthy"}`

### Step 5: Share with Frontend Team

**Send them**:
1. ✅ `Otto_Backend_API.postman_collection.json`
2. ✅ `Otto_Environments.postman_environment.json`
3. ✅ `../ottoai-docs/workspace/API_DOCUMENTATION_GUIDE.md`
4. ✅ `../ottoai-docs/workspace/FRONTEND_API_INTEGRATION_GUIDE.md`
5. ✅ Staging backend URL (when deployed)
6. ✅ Test credentials (Clerk test accounts)

---

## 📁 File Locations

```
ottoai-workspace/
├── ottoai-backend/
│   ├── Otto_Backend_API.postman_collection.json    ← Postman collection
│   ├── Otto_Environments.postman_environment.json  ← Environments
│   ├── export_openapi.sh                           ← Export script
│   ├── API_DOCUMENTATION_README.md                 ← This file
│   └── services/dashboard/
│       └── app/
│           ├── main.py                             ← FastAPI app
│           └── routes/                             ← API endpoints (enhanced with docs)
│               ├── company.py                      ← ✅ Enhanced
│               ├── user.py
│               ├── calls.py
│               ├── rag.py
│               ├── analysis.py
│               ├── followups.py
│               └── clones.py
│
└── ottoai-docs/workspace/
    ├── API_DOCUMENTATION_GUIDE.md                  ← Complete API reference
    ├── FRONTEND_API_INTEGRATION_GUIDE.md           ← Integration steps
    ├── RBAC_SYSTEM_SPECIFICATION.md                ← Role permissions
    └── PRODUCT_ROLE_MAPPING.md                     ← Role-to-product mapping
```

---

## 🔧 For Backend Developers: Maintaining Docs

### When API Changes

**1. Update FastAPI route documentation** (in code):

```python
# app/routes/company.py (example)
@router.post(
    "/",
    summary="Create a new company",
    description="""
    Detailed description here...
    
    **Required Role**: leadership
    
    **Security**: Tenant-scoped
    """,
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "example": {"status": "success", "company_id": "org_123"}
                }
            }
        },
        400: {
            "description": "Error",
            "content": {
                "application/json": {
                    "example": {"detail": "Company already exists"}
                }
            }
        }
    },
    tags=["Companies"]
)
async def create_company(...):
    # ... implementation
```

**2. Export updated OpenAPI spec**:

```bash
./export_openapi.sh
```

**3. Update Postman collection**:

```
1. Open Postman
2. Import → openapi.json (replaces existing)
3. Add any new example requests
4. File → Export → Otto_Backend_API.postman_collection.json
5. Commit updated JSON to git
```

**4. Notify frontend team**:

```
Slack: #frontend-team
"🚀 API updated - new endpoints added:
- POST /new-endpoint
- GET /another-endpoint

Download latest: [link to Postman collection]
Docs: http://localhost:8000/docs"
```

---

## 📊 Current API Stats

**Total Endpoints**: ~50+

**By Category**:
- Companies: 7 endpoints
- Users: 5 endpoints
- Calls: 8 endpoints
- AI Features (RAG): 6 endpoints
- AI Features (Analysis): 4 endpoints
- AI Features (Follow-ups): 4 endpoints
- AI Features (Personal Clone): 3 endpoints
- Documents: 3 endpoints
- Webhooks: 3 endpoints
- Health: 1 endpoint

**Documentation Coverage**:
- ✅ Company routes: Enhanced with examples
- ⏳ User routes: Basic docs (can enhance later)
- ⏳ Call routes: Basic docs (can enhance later)
- ✅ AI routes: Mock responses documented
- ✅ All routes: Have tags and summaries

---

## ✅ Handoff Checklist

Before frontend team starts:

**Documentation**:
- [x] Postman collection created
- [x] Postman environments configured
- [x] API Documentation Guide written
- [x] Frontend Integration Guide written
- [x] RBAC specification documented
- [x] OpenAPI export script created

**Testing**:
- [x] Swagger UI accessible
- [x] Postman collection imports successfully
- [x] Health check endpoint working
- [x] Sample requests have example responses

**Access**:
- [ ] Frontend team added to repo
- [ ] Staging backend URL shared
- [ ] Test Clerk accounts created
- [ ] Test company/user IDs provided

**Communication**:
- [ ] Kickoff meeting scheduled
- [ ] Slack channel created (#frontend-backend)
- [ ] Weekly sync meetings scheduled
- [ ] Point of contact assigned

---

## 🆘 Troubleshooting

### Problem: Swagger UI shows "Failed to fetch"

**Solution**:
```bash
# Check if server is running
curl http://localhost:8000/health

# If not, start server
cd services/dashboard
uvicorn app.main:app --reload
```

---

### Problem: Postman requests fail with 401

**Solution**:
1. Check JWT token is set in environment
2. Token must be valid (not expired)
3. Get fresh token from Clerk
4. Update `JWT_TOKEN` in environment

---

### Problem: OpenAPI export script fails

**Solution**:
```bash
# Make sure server is running first
uvicorn app.main:app --reload

# Then run export
./export_openapi.sh

# Or manually
curl http://localhost:8000/openapi.json > openapi.json
```

---

### Problem: Frontend team can't access staging

**Solution**:
1. Check staging backend is deployed: `https://otto-backend-staging.fly.dev/health`
2. Update Postman "Staging" environment with correct URL
3. Ensure CORS is configured (backend handles this)
4. Check JWT tokens are for staging Clerk instance

---

## 📞 Support

**Backend Team**:
- Slack: #otto-backend
- Email: backend@otto.ai
- Response Time: < 4 hours (business hours)

**For Frontend Questions**:
1. Check `API_DOCUMENTATION_GUIDE.md` first
2. Check `FRONTEND_API_INTEGRATION_GUIDE.md` second
3. Try endpoint in Postman (verify it works)
4. Post in Slack with:
   - Endpoint URL
   - Request body/params
   - Error message
   - Screenshot (if applicable)

---

## 🎓 Additional Resources

**OpenAPI/Swagger**:
- Swagger Editor: https://editor.swagger.io/ (validate OpenAPI spec)
- Swagger UI Docs: https://swagger.io/tools/swagger-ui/

**Postman**:
- Postman Learning Center: https://learning.postman.com/

**FastAPI**:
- FastAPI Docs: https://fastapi.tiangolo.com/
- OpenAPI in FastAPI: https://fastapi.tiangolo.com/advanced/extending-openapi/

---

## 🎉 Success Criteria

**You're done when**:

✅ Frontend team can:
1. Import Postman collection successfully
2. Make API calls from Postman
3. See realistic example responses
4. Understand authentication flow
5. Know which role can access which endpoint
6. Handle errors appropriately
7. Test locally against running backend
8. Deploy to staging and test there

---

## 📝 Changelog

### Version 1.0 - October 10, 2025
- ✅ Initial API documentation complete
- ✅ Postman collection with 50+ endpoints
- ✅ Comprehensive API guide written
- ✅ Frontend integration guide written
- ✅ Enhanced company.py routes with rich OpenAPI docs
- ✅ Export script created
- ✅ Ready for frontend team handoff

---

**Status**: ✅ **READY FOR FRONTEND INTEGRATION**

**Next Steps**:
1. ✅ Share files with frontend team
2. ⏳ Schedule kickoff meeting
3. ⏳ Set up staging environment
4. ⏳ Create test accounts
5. ⏳ Begin frontend development

**Last Updated**: October 10, 2025  
**Maintained By**: Otto Backend Team



