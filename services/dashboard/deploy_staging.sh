#!/bin/bash

# Otto Backend - Staging Deployment Script
# This script deploys the backend to Fly.io staging environment

set -e  # Exit on any error

echo "🚀 Otto Backend - Staging Deployment"
echo "====================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "app/main.py" ]; then
    echo "${RED}❌ Error: Must run from services/dashboard directory${NC}"
    echo "Run: cd services/dashboard && ./deploy_staging.sh"
    exit 1
fi

echo "${YELLOW}📋 Pre-Deployment Checklist${NC}"
echo "=============================="
echo ""

# Check environment variables are set
echo "Checking required environment variables..."

REQUIRED_SECRETS=(
    "DATABASE_URL"
    "REDIS_URL"
    "CLERK_SECRET_KEY"
    "AWS_ACCESS_KEY_ID"
    "AWS_SECRET_ACCESS_KEY"
    "SENTRY_DSN"
)

MISSING_SECRETS=()

for secret in "${REQUIRED_SECRETS[@]}"; do
    if fly secrets list | grep -q "$secret"; then
        echo "${GREEN}✅ $secret${NC}"
    else
        echo "${RED}❌ $secret - NOT SET${NC}"
        MISSING_SECRETS+=("$secret")
    fi
done

if [ ${#MISSING_SECRETS[@]} -gt 0 ]; then
    echo ""
    echo "${RED}❌ Missing required secrets. Please set them first:${NC}"
    for secret in "${MISSING_SECRETS[@]}"; do
        echo "  fly secrets set $secret=\"your_value_here\""
    done
    echo ""
    echo "See env.template for all required secrets"
    exit 1
fi

echo ""
echo "${GREEN}✅ All required secrets configured${NC}"
echo ""

# Step 1: Run database migration
echo "${YELLOW}📊 Step 1: Database Migration${NC}"
echo "=============================="
echo ""
echo "Running Alembic migration to create AI tables..."

# Check if migration has been run
echo "Current database revision:"
alembic current || echo "No migrations run yet"

echo ""
echo "Running migration: 003_add_ai_models"
alembic upgrade head

if [ $? -eq 0 ]; then
    echo "${GREEN}✅ Migration successful${NC}"
else
    echo "${RED}❌ Migration failed${NC}"
    exit 1
fi

echo ""

# Step 2: Build and deploy
echo "${YELLOW}🔨 Step 2: Build & Deploy${NC}"
echo "=============================="
echo ""

echo "Building Docker image and deploying to Fly.io..."
fly deploy

if [ $? -eq 0 ]; then
    echo "${GREEN}✅ Deployment successful${NC}"
else
    echo "${RED}❌ Deployment failed${NC}"
    exit 1
fi

echo ""

# Step 3: Health check
echo "${YELLOW}🏥 Step 3: Health Check${NC}"
echo "=============================="
echo ""

echo "Waiting 10 seconds for app to start..."
sleep 10

APP_URL=$(fly status --json | jq -r '.Hostname' | head -1)
if [ -z "$APP_URL" ]; then
    APP_URL="otto-backend-staging.fly.dev"
fi

echo "Checking health: https://$APP_URL/health"
HEALTH_RESPONSE=$(curl -s "https://$APP_URL/health")

if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo "${GREEN}✅ Backend is healthy${NC}"
    echo "$HEALTH_RESPONSE" | jq '.'
else
    echo "${RED}❌ Health check failed${NC}"
    echo "$HEALTH_RESPONSE"
    exit 1
fi

echo ""

# Step 4: Smoke test endpoints
echo "${YELLOW}🧪 Step 4: Smoke Tests${NC}"
echo "=============================="
echo ""

echo "Note: These tests require a valid JWT token"
echo "Get token from: https://dashboard.clerk.com"
echo ""
echo "Manual smoke tests:"
echo "  1. GET  https://$APP_URL/docs (Swagger UI)"
echo "  2. GET  https://$APP_URL/health (should return healthy)"
echo "  3. POST https://$APP_URL/api/v1/rag/query (with token)"
echo ""

# Success summary
echo "${GREEN}✅ Deployment Complete!${NC}"
echo "=============================="
echo ""
echo "🔗 URLs:"
echo "  Backend:    https://$APP_URL"
echo "  Swagger UI: https://$APP_URL/docs"
echo "  ReDoc:      https://$APP_URL/redoc"
echo "  Health:     https://$APP_URL/health"
echo ""
echo "📊 Monitoring:"
echo "  Sentry:     https://sentry.io"
echo "  Fly.io:     fly status"
echo "  Logs:       fly logs"
echo ""
echo "🎯 Next Steps:"
echo "  1. Test endpoints in Postman (update BASE_URL to https://$APP_URL)"
echo "  2. Share with frontend team"
echo "  3. Set up Grafana dashboards"
echo ""




