#!/bin/bash

# Quick start script for local development

echo "🚀 Starting Otto Backend in Dev Mode..."
echo ""

# Set environment variables
export DEV_MODE=true
export DEV_TEST_COMPANY_ID=dev-test-company
export DEV_TEST_USER_ID=dev-test-user
export DEV_TEST_PHONE_NUMBER=+12028313219
export DATABASE_URL=${DATABASE_URL:-"sqlite:///./otto_dev.db"}
export ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-"http://localhost:3000,exp://*"}

echo "📋 Configuration:"
echo "   DEV_MODE: $DEV_MODE"
echo "   Company ID: $DEV_TEST_COMPANY_ID"
echo "   Phone: $DEV_TEST_PHONE_NUMBER"
echo "   Database: $DATABASE_URL"
echo ""

# Find the correct Python (prefer 3.11, fallback to python3)
PYTHON_CMD=""
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif [ -f "/opt/homebrew/bin/python3.11" ]; then
    PYTHON_CMD="/opt/homebrew/bin/python3.11"
else
    PYTHON_CMD="python3"
fi

echo "🐍 Using Python: $PYTHON_CMD"
$PYTHON_CMD --version

# Check if test data exists, seed if needed
echo "🌱 Checking test data..."
$PYTHON_CMD scripts/seed_dev_data.py 2>/dev/null || echo "⚠️  Note: Seed script may have warnings, continuing..."

echo ""
echo "🌐 Starting FastAPI server..."
echo "   Backend will be available at: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press CTRL+C to stop"
echo ""

# Start the server using the correct Python
$PYTHON_CMD -m uvicorn app.main:app --reload --port 8000


# Quick start script for local development

echo "🚀 Starting Otto Backend in Dev Mode..."
echo ""

# Set environment variables
export DEV_MODE=true
export DEV_TEST_COMPANY_ID=dev-test-company
export DEV_TEST_USER_ID=dev-test-user
export DEV_TEST_PHONE_NUMBER=+12028313219
export DATABASE_URL=${DATABASE_URL:-"sqlite:///./otto_dev.db"}
export ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-"http://localhost:3000,exp://*"}

echo "📋 Configuration:"
echo "   DEV_MODE: $DEV_MODE"
echo "   Company ID: $DEV_TEST_COMPANY_ID"
echo "   Phone: $DEV_TEST_PHONE_NUMBER"
echo "   Database: $DATABASE_URL"
echo ""

# Find the correct Python (prefer 3.11, fallback to python3)
PYTHON_CMD=""
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif [ -f "/opt/homebrew/bin/python3.11" ]; then
    PYTHON_CMD="/opt/homebrew/bin/python3.11"
else
    PYTHON_CMD="python3"
fi

echo "🐍 Using Python: $PYTHON_CMD"
$PYTHON_CMD --version

# Check if test data exists, seed if needed
echo "🌱 Checking test data..."
$PYTHON_CMD scripts/seed_dev_data.py 2>/dev/null || echo "⚠️  Note: Seed script may have warnings, continuing..."

echo ""
echo "🌐 Starting FastAPI server..."
echo "   Backend will be available at: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press CTRL+C to stop"
echo ""

# Start the server using the correct Python
$PYTHON_CMD -m uvicorn app.main:app --reload --port 8000


# Quick start script for local development

echo "🚀 Starting Otto Backend in Dev Mode..."
echo ""

# Set environment variables
export DEV_MODE=true
export DEV_TEST_COMPANY_ID=dev-test-company
export DEV_TEST_USER_ID=dev-test-user
export DEV_TEST_PHONE_NUMBER=+12028313219
export DATABASE_URL=${DATABASE_URL:-"sqlite:///./otto_dev.db"}
export ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-"http://localhost:3000,exp://*"}

echo "📋 Configuration:"
echo "   DEV_MODE: $DEV_MODE"
echo "   Company ID: $DEV_TEST_COMPANY_ID"
echo "   Phone: $DEV_TEST_PHONE_NUMBER"
echo "   Database: $DATABASE_URL"
echo ""

# Find the correct Python (prefer 3.11, fallback to python3)
PYTHON_CMD=""
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif [ -f "/opt/homebrew/bin/python3.11" ]; then
    PYTHON_CMD="/opt/homebrew/bin/python3.11"
else
    PYTHON_CMD="python3"
fi

echo "🐍 Using Python: $PYTHON_CMD"
$PYTHON_CMD --version

# Check if test data exists, seed if needed
echo "🌱 Checking test data..."
$PYTHON_CMD scripts/seed_dev_data.py 2>/dev/null || echo "⚠️  Note: Seed script may have warnings, continuing..."

echo ""
echo "🌐 Starting FastAPI server..."
echo "   Backend will be available at: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press CTRL+C to stop"
echo ""

# Start the server using the correct Python
$PYTHON_CMD -m uvicorn app.main:app --reload --port 8000

