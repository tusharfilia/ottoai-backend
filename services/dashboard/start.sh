#!/bin/bash

# Otto AI Backend Start Script for Railway
echo "🚀 Starting Otto AI Backend..."

# Install dependencies if not already installed
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Run database migrations
echo "🗄️ Running database migrations..."
alembic upgrade head || echo "⚠️ Migration failed, continuing..."

# Start the FastAPI server
echo "🌐 Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
