# How to Get the OpenAPI Spec

FastAPI **automatically generates** the OpenAPI spec from your route definitions. **No GitHub push needed!**

## 🚀 Quick Options

### Option 1: From Running Server (Easiest)

#### Local Server:
```bash
# Start your server
uvicorn app.main:app --reload

# Then visit in browser or curl:
curl http://localhost:8000/openapi.json > openapi.json

# Or use the export script:
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend
./export_openapi.sh
```

#### Railway Production Server:
```bash
# Just curl your Railway URL:
curl https://your-railway-app.railway.app/openapi.json > openapi.json

# Or visit in browser:
https://your-railway-app.railway.app/openapi.json
```

### Option 2: Generate Without Running Server

Use the Python script (works offline, no server needed):

```bash
cd /Users/tusharmehrotra/Documents/ottoai-workspace/ottoai-backend/services/dashboard

# Generate to file:
python generate_openapi.py --output openapi.json

# Or output to stdout:
python generate_openapi.py > openapi.json
```

This script generates the spec directly from your FastAPI app code - no server required!

### Option 3: Programmatic Generation

Create a small Python script:

```python
from app.main import app
from fastapi.openapi.utils import get_openapi
import json

openapi_schema = get_openapi(
    title="Otto Backend API",
    version="1.0.0",
    description="FastAPI backend",
    routes=app.routes,
)

with open("openapi.json", "w") as f:
    json.dump(openapi_schema, f, indent=2)
```

## 📍 Interactive Docs (Always Available)

When your server is running, FastAPI automatically provides:

- **Swagger UI**: `http://localhost:8000/docs` - Interactive API explorer
- **ReDoc**: `http://localhost:8000/redoc` - Beautiful documentation
- **OpenAPI JSON**: `http://localhost:8000/openapi.json` - Machine-readable spec

## 🔗 Railway Deployment

**Railway automatically exposes the OpenAPI spec** when your FastAPI app is deployed:

```
https://your-railway-app.railway.app/openapi.json
https://your-railway-app.railway.app/docs
https://your-railway-app.railway.app/redoc
```

No additional configuration needed - it just works!

## ✅ Recommended Workflow

1. **For development**: Use `generate_openapi.py` (no server needed)
2. **For sharing**: Export from running server via `/openapi.json`
3. **For CI/CD**: Use the Python script in your build pipeline

## 📝 Example Usage

```bash
# Generate spec locally (no server)
cd services/dashboard
python generate_openapi.py --output ../../openapi.json

# Or from running server
curl http://localhost:8000/openapi.json | jq > openapi.json

# Share with frontend team
# - Import into Postman
# - Use with openapi-generator for client SDKs
# - Feed into API documentation tools
```

## 🎯 No GitHub Push Required!

The OpenAPI spec is **generated at runtime** from your FastAPI route definitions. FastAPI introspects your code automatically - just access `/openapi.json` on any running instance!

