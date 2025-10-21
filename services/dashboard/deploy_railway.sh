#!/bin/bash

# Railway Deployment Script for Otto AI Backend
echo "🚀 Setting up Railway deployment..."

# Check if we're in the right directory
if [ ! -f "app/main.py" ]; then
    echo "❌ Error: Please run this script from the dashboard directory"
    exit 1
fi

echo "✅ Found app/main.py"

# Create Procfile for Railway
echo "web: uvicorn app.main:app --host 0.0.0.0 --port \$PORT" > Procfile

echo "✅ Created Procfile"

# Create runtime.txt for Python version
echo "python-3.11" > runtime.txt

echo "✅ Created runtime.txt"

echo ""
echo "🎯 Next steps:"
echo "1. Go to https://railway.app"
echo "2. Sign up/login with GitHub"
echo "3. Click 'New Project' → 'Deploy from GitHub repo'"
echo "4. Select your ottoai-backend repository"
echo "5. Set the root directory to: services/dashboard"
echo "6. Add these environment variables:"
echo ""
echo "DATABASE_URL=postgresql://user:pass@host:port/db"
echo "REDIS_URL=redis://host:port"
echo "AWS_ACCESS_KEY_ID=your_key"
echo "AWS_SECRET_ACCESS_KEY=your_secret"
echo "AWS_DEFAULT_REGION=ap-southeast-2"
echo "S3_BUCKET=otto-documents-staging"
echo "UWC_BASE_URL=https://otto.shunyalabs.ai"
echo "UWC_API_KEY=your_uwc_key"
echo "UWC_SECRET=your_uwc_secret"
echo "ENABLE_UWC_ASR=true"
echo "ENABLE_UWC_RAG=true"
echo "ENABLE_UWC_TRAINING=true"
echo "ENABLE_UWC_FOLLOWUPS=true"
echo "ENVIRONMENT=staging"
echo "SENTRY_DSN=your_sentry_dsn"
echo ""
echo "7. Click 'Deploy'"
echo ""
echo "🚀 Railway will automatically:"
echo "   - Install Python dependencies"
echo "   - Run database migrations"
echo "   - Start the FastAPI server"
echo "   - Provide a public URL"
