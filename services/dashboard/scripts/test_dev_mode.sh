#!/bin/bash

# Quick test script to verify dev mode is working
# Make sure your backend is running with DEV_MODE=true

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"

echo "🧪 Testing Dev Mode"
echo "==================="
echo "Backend URL: $BACKEND_URL"
echo ""

# Test 1: Health check (should work without auth)
echo "1️⃣  Testing health endpoint..."
curl -s "$BACKEND_URL/health" | jq . || echo "❌ Health check failed"
echo ""

# Test 2: Dashboard calls endpoint (should work in dev mode without auth)
echo "2️⃣  Testing dashboard calls endpoint (dev mode)..."
curl -s "$BACKEND_URL/api/v1/dashboard/calls?status=missed&company_id=dev-test-company" \
  -H "Content-Type: application/json" | jq . || echo "❌ Dashboard calls failed"
echo ""

echo "✅ Test complete!"
echo ""
echo "💡 If you see errors, make sure:"
echo "   1. Backend is running with DEV_MODE=true"
echo "   2. You've run: python3 scripts/seed_dev_data.py"
echo "   3. Backend URL is correct: $BACKEND_URL"

