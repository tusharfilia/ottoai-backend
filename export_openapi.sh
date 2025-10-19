#!/bin/bash

# Otto Backend - OpenAPI Spec Export Script
# This script exports the OpenAPI specification from your running FastAPI server

echo "🚀 Otto Backend - OpenAPI Export Tool"
echo "======================================"
echo ""

# Check if server is running
echo "📡 Checking if backend server is running..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Server is running"
else
    echo "❌ Server is not running"
    echo ""
    echo "Please start the server first:"
    echo "  cd services/dashboard"
    echo "  uvicorn app.main:app --reload"
    exit 1
fi

# Export OpenAPI JSON
echo ""
echo "📥 Exporting OpenAPI specification..."
curl -s http://localhost:8000/openapi.json | python3 -m json.tool > openapi.json

if [ $? -eq 0 ]; then
    echo "✅ OpenAPI spec exported to: openapi.json"
else
    echo "❌ Failed to export OpenAPI spec"
    exit 1
fi

# Display stats
echo ""
echo "📊 API Statistics:"
echo "=================="
ENDPOINT_COUNT=$(grep -o '"path"' openapi.json | wc -l | tr -d ' ')
echo "  Total Endpoints: ~$ENDPOINT_COUNT"

TAG_COUNT=$(grep -o '"tags"' openapi.json | wc -l | tr -d ' ')
echo "  Categories: ~$TAG_COUNT"

echo ""
echo "✅ Export complete!"
echo ""
echo "📝 Next Steps:"
echo "  1. Import openapi.json into Postman (File → Import)"
echo "  2. Review endpoints at http://localhost:8000/docs"
echo "  3. Share openapi.json with frontend team"
echo ""
echo "🔗 Useful Links:"
echo "  Swagger UI: http://localhost:8000/docs"
echo "  ReDoc:      http://localhost:8000/redoc"
echo "  OpenAPI:    http://localhost:8000/openapi.json"


