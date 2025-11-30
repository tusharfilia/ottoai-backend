# Export Otto OpenAPI Specification

**Quick guide to export the complete OpenAPI spec for frontend integration**

---

## 🚀 **QUICK EXPORT** (Backend Must Be Running)

```bash
# Method 1: Direct curl
curl http://localhost:8000/openapi.json > otto-openapi.json

# Method 2: Using export script
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend
./export_openapi.sh

# Method 3: Pretty print
curl http://localhost:8000/openapi.json | python3 -m json.tool > otto-openapi-pretty.json
```

---

## 📋 **WHAT YOU GET**

The OpenAPI spec includes:
- ✅ **185+ endpoints** with full schemas
- ✅ **Request/response models** with examples
- ✅ **Authentication** requirements
- ✅ **Role-based access** control info
- ✅ **Error responses** documented
- ✅ **All query/path parameters** defined

---

## 🔗 **ACCESS POINTS**

| Resource | URL | Purpose |
|----------|-----|---------|
| **Swagger UI** | http://localhost:8000/docs | Interactive API testing |
| **ReDoc** | http://localhost:8000/redoc | Beautiful documentation |
| **OpenAPI JSON** | http://localhost:8000/openapi.json | Machine-readable spec |
| **OpenAPI YAML** | http://localhost:8000/openapi.yaml | YAML format (if enabled) |

---

## 📦 **USE CASES**

### **1. Import into Postman**
```bash
# Export spec
curl http://localhost:8000/openapi.json > otto-openapi.json

# In Postman: File → Import → Select otto-openapi.json
```

### **2. Generate TypeScript Client**
```bash
# Using openapi-typescript
npx openapi-typescript http://localhost:8000/openapi.json -o src/types/otto-api.ts

# Using openapi-generator
openapi-generator-cli generate \
  -i http://localhost:8000/openapi.json \
  -g typescript-axios \
  -o src/api/otto-client
```

### **3. Generate React Query Hooks**
```bash
# Using orval
npx orval --input http://localhost:8000/openapi.json --output src/api/hooks.ts
```

### **4. API Documentation Site**
```bash
# Using redoc-cli
npx @redocly/cli build-docs http://localhost:8000/openapi.json -o docs/index.html
```

---

## ✅ **VERIFICATION**

After exporting, verify the spec:

```bash
# Check endpoint count
grep -o '"path"' otto-openapi.json | wc -l

# Check tags/categories
grep -o '"tags":\["[^"]*"' otto-openapi.json | sort | uniq

# Validate JSON
python3 -m json.tool otto-openapi.json > /dev/null && echo "✅ Valid JSON"
```

---

## 🎯 **READY TO USE**

Once exported, you have:
- ✅ Complete API specification
- ✅ All endpoints documented
- ✅ Request/response schemas
- ✅ Authentication requirements
- ✅ Ready for frontend integration

**Start integrating!** 🚀

