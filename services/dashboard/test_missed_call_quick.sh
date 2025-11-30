#!/bin/bash

# Quick Test Script for Missed Call Flow
# Usage: ./test_missed_call_quick.sh

set -e

# Configuration - UPDATE THESE VALUES
RAILWAY_URL="https://ottoai-backend-production.up.railway.app"
TRACKING_NUMBER="+15205232772"  # Your CallRail tracking number
CALLER_NUMBER="+1YOUR_PHONE"    # Your phone number (the one calling)
CALL_ID="test_$(date +%s)"

echo "🧪 Testing Missed Call Flow"
echo "============================"
echo ""
echo "Configuration:"
echo "  Railway URL: $RAILWAY_URL"
echo "  Tracking Number: $TRACKING_NUMBER"
echo "  Caller Number: $CALLER_NUMBER"
echo "  Call ID: $CALL_ID"
echo ""

# Step 1: Simulate call.incoming (creates call record)
echo "1️⃣  Simulating call.incoming webhook..."
CALL_INCOMING_RESPONSE=$(curl -s -X POST "${RAILWAY_URL}/callrail/call.incoming" \
  -H "Content-Type: application/json" \
  -d "{
    \"call_id\": \"${CALL_ID}\",
    \"caller_number\": \"${CALLER_NUMBER}\",
    \"tracking_number\": \"${TRACKING_NUMBER}\",
    \"customer_phone_number\": \"${CALLER_NUMBER}\",
    \"tracking_phone_number\": \"${TRACKING_NUMBER}\",
    \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\"
  }")

echo "Response: $CALL_INCOMING_RESPONSE"
echo ""

sleep 2

# Step 2: Simulate call.missed (triggers missed call queue)
echo "2️⃣  Simulating call.missed webhook..."
CALL_MISSED_RESPONSE=$(curl -s -X POST "${RAILWAY_URL}/callrail/call.missed" \
  -H "Content-Type: application/json" \
  -d "{
    \"call_id\": \"${CALL_ID}\",
    \"caller_number\": \"${CALLER_NUMBER}\",
    \"tracking_number\": \"${TRACKING_NUMBER}\",
    \"customer_phone_number\": \"${CALLER_NUMBER}\",
    \"tracking_phone_number\": \"${TRACKING_NUMBER}\",
    \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\",
    \"answered\": false
  }")

echo "Response: $CALL_MISSED_RESPONSE"
echo ""

echo "✅ Test complete!"
echo ""
echo "📋 Next Steps:"
echo "   1. Check your phone ($CALLER_NUMBER) for SMS in 30-60 seconds"
echo "   2. Check Railway logs: railway logs --tail | grep -i missed"
echo "   3. Check database for queue entry:"
echo "      SELECT * FROM missed_call_queue WHERE customer_phone = '$CALLER_NUMBER' ORDER BY created_at DESC LIMIT 1;"
echo ""

