#!/bin/bash

# Otto AI Infrastructure Setup Script
# This script sets up all foundational services for the Otto AI platform

set -e

echo "🏗️  Setting up Otto AI Infrastructure..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if flyctl is installed
if ! command -v flyctl &> /dev/null; then
    print_error "flyctl is not installed. Please install it first:"
    echo "curl -L https://fly.io/install.sh | sh"
    exit 1
fi

# Check if user is logged in to Fly.io
if ! flyctl auth whoami &> /dev/null; then
    print_error "Not logged in to Fly.io. Please run: flyctl auth login"
    exit 1
fi

print_status "Starting infrastructure setup..."

# 1. Create staging app
print_status "Creating staging app: tv-mvp-staging"
if flyctl apps list | grep -q "tv-mvp-staging"; then
    print_warning "App tv-mvp-staging already exists"
else
    flyctl apps create tv-mvp-staging --org personal
    print_success "Created staging app"
fi

# 2. Create Postgres database
print_status "Creating Postgres database..."
if flyctl postgres list | grep -q "otto-staging-db"; then
    print_warning "Postgres database already exists"
else
    flyctl postgres create --name otto-staging-db --region phx --initial-cluster-size 1 --vm-size shared-cpu-1x
    print_success "Created Postgres database"
fi

# 3. Create Redis instance
print_status "Creating Redis instance..."
if flyctl redis list | grep -q "otto-staging-redis"; then
    print_warning "Redis instance already exists"
else
    flyctl redis create --name otto-staging-redis --region phx
    print_success "Created Redis instance"
fi

# 4. Get database connection details
print_status "Getting database connection details..."
DB_URL=$(flyctl postgres connect --app otto-staging-db --command "echo \$DATABASE_URL" 2>/dev/null || echo "")
if [ -z "$DB_URL" ]; then
    print_error "Failed to get database URL. Please check your Postgres setup."
    exit 1
fi

# 5. Get Redis connection details
print_status "Getting Redis connection details..."
REDIS_URL=$(flyctl redis connect --app otto-staging-redis --command "echo \$REDIS_URL" 2>/dev/null || echo "")
if [ -z "$REDIS_URL" ]; then
    print_error "Failed to get Redis URL. Please check your Redis setup."
    exit 1
fi

# 6. Set secrets for staging app
print_status "Setting secrets for staging app..."

# Database
flyctl secrets set --app tv-mvp-staging DATABASE_URL="$DB_URL"

# Redis
flyctl secrets set --app tv-mvp-staging REDIS_URL="$REDIS_URL"

# AWS S3 (set your credentials)
flyctl secrets set --app tv-mvp-staging AWS_ACCESS_KEY_ID="YOUR_AWS_ACCESS_KEY"
flyctl secrets set --app tv-mvp-staging AWS_SECRET_ACCESS_KEY="YOUR_AWS_SECRET_KEY"
flyctl secrets set --app tv-mvp-staging AWS_DEFAULT_REGION="ap-southeast-2"
flyctl secrets set --app tv-mvp-staging S3_BUCKET="otto-documents-staging"

# Environment
flyctl secrets set --app tv-mvp-staging ENVIRONMENT="staging"
flyctl secrets set --app tv-mvp-staging ENVIRONMENT_NAME="staging"

# UWC/Shunya (using mock API for now)
flyctl secrets set --app tv-mvp-staging UWC_BASE_URL="https://otto.shunyalabs.ai"
flyctl secrets set --app tv-mvp-staging UWC_API_KEY="mock-key-for-testing"

# Feature flags
flyctl secrets set --app tv-mvp-staging ENABLE_UWC_ASR="true"
flyctl secrets set --app tv-mvp-staging ENABLE_UWC_RAG="true"
flyctl secrets set --app tv-mvp-staging ENABLE_UWC_TRAINING="true"
flyctl secrets set --app tv-mvp-staging ENABLE_UWC_FOLLOWUPS="true"

# Rate limiting
flyctl secrets set --app tv-mvp-staging ENABLE_RATE_LIMITING="true"

# Sentry (you'll need to get your DSN)
print_warning "Please set your Sentry DSN:"
echo "flyctl secrets set --app tv-mvp-staging SENTRY_DSN=\"your-sentry-dsn-here\""

# Clerk (you'll need to get your keys)
print_warning "Please set your Clerk keys:"
echo "flyctl secrets set --app tv-mvp-staging CLERK_SECRET_KEY=\"your-clerk-secret-key\""
echo "flyctl secrets set --app tv-mvp-staging CLERK_PUBLISHABLE_KEY=\"your-clerk-publishable-key\""

# Twilio (if you have them)
print_warning "If you have Twilio credentials, set them:"
echo "flyctl secrets set --app tv-mvp-staging TWILIO_ACCOUNT_SID=\"your-twilio-sid\""
echo "flyctl secrets set --app tv-mvp-staging TWILIO_AUTH_TOKEN=\"your-twilio-token\""

# CallRail (if you have them)
print_warning "If you have CallRail credentials, set them:"
echo "flyctl secrets set --app tv-mvp-staging CALLRAIL_API_KEY=\"your-callrail-key\""

print_success "Secrets configured"

# 7. Deploy staging app
print_status "Deploying staging app..."
flyctl deploy --config fly.staging.toml --app tv-mvp-staging

print_success "Infrastructure setup complete!"

echo ""
echo "🎉 Next steps:"
echo "1. Set your Sentry DSN: flyctl secrets set --app tv-mvp-staging SENTRY_DSN=\"your-dsn\""
echo "2. Set your Clerk keys for authentication"
echo "3. Set Twilio/CallRail keys if you have them"
echo "4. Test the staging app: flyctl open --app tv-mvp-staging"
echo "5. Check logs: flyctl logs --app tv-mvp-staging"
echo ""
echo "📊 Monitoring:"
echo "- Health check: https://tv-mvp-staging.fly.dev/health"
echo "- Metrics: https://tv-mvp-staging.fly.dev/metrics"
echo "- API docs: https://tv-mvp-staging.fly.dev/docs"
echo ""
echo "🔧 Management:"
echo "- View secrets: flyctl secrets list --app tv-mvp-staging"
echo "- SSH into app: flyctl ssh console --app tv-mvp-staging"
echo "- Scale workers: flyctl scale worker 2 --app tv-mvp-staging"
