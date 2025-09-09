# OttoAI Backend

**FastAPI backend for the TrueView platform**

This is the backend service for the TrueView end-to-end sales intelligence platform, providing APIs for call tracking, sales management, and AI-powered analytics.

## 🏗️ Architecture

- **Framework:** FastAPI 0.100.0
- **Database:** PostgreSQL with SQLAlchemy 2.0.17
- **Authentication:** Clerk JWT integration
- **Deployment:** Fly.io (https://tv-mvp-test.fly.dev)
- **API Endpoints:** 131+ endpoints

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Node.js 18+ (for some scripts)

### Setup
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload
```

## 🔧 Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/truview

# Clerk Authentication
CLERK_SECRET_KEY=your_clerk_secret_key

# External Services
OPENAI_API_KEY=your_openai_api_key
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_FROM_NUMBER=your_twilio_phone_number

# CallRail Integration
CALLRAIL_API_KEY=your_callrail_api_key

# Bland.ai Integration
BLAND_API_KEY=your_bland_api_key
```

## 📊 Features

### Core APIs
- **Call Management** - Call tracking, recording, and analysis
- **Sales Rep Management** - Rep profiles, assignments, and performance
- **Company Management** - Multi-tenant company data
- **User Management** - Clerk integration for authentication
- **AI Analysis** - Transcript analysis and insights
- **Scheduled Tasks** - Background job processing

### External Integrations
- **CallRail** - Call tracking and webhook data
- **Twilio** - SMS and voice communications
- **OpenAI** - AI transcript analysis
- **Bland.ai** - AI-powered follow-up calls
- **Deepgram** - Speech-to-text transcription

## 🗄️ Database Schema

### Core Tables
- **companies** - Multi-tenant company data
- **users** - User accounts (Clerk integration)
- **sales_reps** - Sales representative profiles
- **sales_managers** - Sales manager profiles
- **calls** - Call records and transcripts
- **transcript_analyses** - AI analysis results
- **scheduled_calls** - Follow-up call scheduling
- **services** - Service catalog per company

## 🚀 Deployment

### Fly.io (Current)
```bash
# Deploy to Fly.io
fly deploy

# Check status
fly status
```

### Environment Variables on Fly.io
All environment variables are configured on Fly.io for production deployment.

## 📚 API Documentation

- **Swagger UI:** Available at `/docs` when running locally
- **OpenAPI Spec:** Available at `/openapi.json`
- **Health Check:** Available at `/health`

## 🧪 Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app
```

## 🔗 Related Repositories

- **Frontend:** [ottoai-frontend](https://github.com/tusharfilia/ottoai-frontend)
- **Mobile:** [ottoai-mobile](https://github.com/tusharfilia/ottoai-mobile)
- **Documentation:** [ottoai-docs](https://github.com/tusharfilia/ottoai-docs)

## 📄 License

[Add your license here]

---

**Note:** This backend is part of the TrueView platform. See the main documentation in the ottoai-docs repository for complete platform information.
