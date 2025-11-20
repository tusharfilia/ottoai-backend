#!/bin/bash
#
# Production Configuration Verification Script
# Checks Redis, OpenAI keys, and other critical production settings
#

echo "🔍 Production Configuration Check"
echo "=================================="
echo ""

# Check if Railway CLI is installed
if command -v railway &> /dev/null; then
    echo "✅ Railway CLI detected"
    echo ""
    echo "📋 Checking Railway Environment Variables..."
    echo ""
    
    # Check critical variables
    echo "🔑 OpenAI Configuration:"
    railway variables get OPENAI_API_KEYS 2>/dev/null && echo "  ✅ OPENAI_API_KEYS is set" || echo "  ❌ OPENAI_API_KEYS not found"
    railway variables get OPENAI_KEY_ROTATION_STRATEGY 2>/dev/null && echo "  ✅ OPENAI_KEY_ROTATION_STRATEGY is set" || echo "  ⚠️  OPENAI_KEY_ROTATION_STRATEGY not set (will default to round_robin)"
    echo ""
    
    echo "🔴 Redis Configuration:"
    railway variables get REDIS_URL 2>/dev/null && echo "  ✅ REDIS_URL is set" || echo "  ⚠️  REDIS_URL not found, checking UPSTASH_REDIS_URL..."
    railway variables get UPSTASH_REDIS_URL 2>/dev/null && echo "  ✅ UPSTASH_REDIS_URL is set" || echo "  ❌ Neither REDIS_URL nor UPSTASH_REDIS_URL found"
    echo ""
    
    echo "⚙️  Celery Configuration:"
    railway variables get ENABLE_CELERY 2>/dev/null && echo "  ✅ ENABLE_CELERY is set" || echo "  ❌ ENABLE_CELERY not found (required for property intelligence)"
    echo ""
    
    echo "🗄️  Database Configuration:"
    railway variables get DATABASE_URL 2>/dev/null && echo "  ✅ DATABASE_URL is set" || echo "  ❌ DATABASE_URL not found"
    echo ""
    
    echo "🌍 Environment:"
    railway variables get ENVIRONMENT 2>/dev/null && echo "  ✅ ENVIRONMENT is set" || echo "  ⚠️  ENVIRONMENT not set (will default to development)"
    echo ""
    
    echo ""
    echo "📊 To view all environment variables:"
    echo "   railway variables"
    echo ""
    echo "🔍 To check specific variable:"
    echo "   railway variables get VARIABLE_NAME"
    echo ""
    
elif command -v vercel &> /dev/null; then
    echo "✅ Vercel CLI detected"
    echo ""
    echo "📋 Checking Vercel Environment Variables..."
    echo ""
    echo "To check production environment variables:"
    echo "   vercel env ls production"
    echo ""
    echo "To check a specific variable:"
    echo "   vercel env pull .env.production"
    echo ""
    
else
    echo "⚠️  No deployment CLI detected (Railway/Vercel)"
    echo ""
    echo "📋 Manual Production Checks:"
    echo ""
    echo "1. Check your production dashboard (Railway/Vercel/etc.)"
    echo "2. Go to Environment Variables section"
    echo "3. Verify these are set:"
    echo "   ✅ OPENAI_API_KEYS (comma-separated)"
    echo "   ✅ REDIS_URL or UPSTASH_REDIS_URL"
    echo "   ✅ ENABLE_CELERY=true"
    echo "   ✅ DATABASE_URL"
    echo "   ✅ ENVIRONMENT=production"
    echo ""
fi

echo "🧪 Testing Production API (if URL is known):"
echo ""
read -p "Enter your production API URL (or press Enter to skip): " PROD_URL

if [ ! -z "$PROD_URL" ]; then
    echo ""
    echo "Testing $PROD_URL..."
    echo ""
    
    # Test health endpoint
    echo "1️⃣ Health Check:"
    curl -s "$PROD_URL/health" | head -20 || echo "  ❌ Health check failed"
    echo ""
    
    # Test OpenAI stats (if you have auth token)
    echo "2️⃣ OpenAI Stats (requires auth):"
    echo "   GET $PROD_URL/api/v1/admin/openai/stats"
    echo "   (Add Authorization header with your token)"
    echo ""
    
    # Test detailed health (includes Redis check)
    echo "3️⃣ Detailed Health (includes Redis check):"
    curl -s "$PROD_URL/health/detailed" | head -30 || echo "  ❌ Detailed health check failed"
    echo ""
fi

echo ""
echo "✅ Production Check Complete!"
echo ""
echo "📝 Next Steps:"
echo "1. Verify all required variables are set in production"
echo "2. Check production logs for startup messages"
echo "3. Test property intelligence scraping via API"
echo "4. Monitor OpenAI key usage via /api/v1/admin/openai/stats"

