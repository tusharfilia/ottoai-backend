# Otto AI Backend Deployment Guide

## 🚀 Quick Deployment Options

We've prepared configurations for 3 deployment platforms. Choose the one that works best for you:

### Option 1: Railway (Recommended)
**Pros:** Simple, good for Python, built-in databases
**Setup time:** 5 minutes

1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub
3. Click "New Project" → "Deploy from GitHub repo"
4. Select `ottoai-backend` repository
5. Set root directory to: `services/dashboard`
6. Add environment variables (see below)
7. Click "Deploy"

### Option 2: Render
**Pros:** Simple, good free tier, managed databases
**Setup time:** 5 minutes

1. Go to [render.com](https://render.com)
2. Sign up with GitHub
3. Click "New Web Service"
4. Connect `ottoai-backend` repository
5. Set root directory to: `services/dashboard`
6. Add environment variables (see below)
7. Click "Deploy"

### Option 3: Heroku
**Pros:** Most mature, extensive add-ons
**Setup time:** 10 minutes

1. Install Heroku CLI: `brew install heroku/brew/heroku`
2. Login: `heroku login`
3. Create app: `heroku create otto-backend-staging`
4. Add Postgres: `heroku addons:create heroku-postgresql:mini`
5. Add Redis: `heroku addons:create heroku-redis:mini`
6. Set environment variables (see below)
7. Deploy: `git push heroku main`

## 🔧 Required Environment Variables

Set these in your chosen platform:

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:port/db

# Redis
REDIS_URL=redis://host:port

# AWS S3
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_DEFAULT_REGION=ap-southeast-2
S3_BUCKET=otto-documents-staging

# UWC Integration
UWC_BASE_URL=https://otto.shunyalabs.ai
UWC_API_KEY=your_uwc_key
UWC_SECRET=your_uwc_secret
ENABLE_UWC_ASR=true
ENABLE_UWC_RAG=true
ENABLE_UWC_TRAINING=true
ENABLE_UWC_FOLLOWUPS=true

# App Config
ENVIRONMENT=staging
SENTRY_DSN=your_sentry_dsn
```

## 🎯 What Happens After Deployment

1. **Automatic Setup:**
   - Python dependencies installed
   - Database migrations run
   - FastAPI server starts
   - Health check at `/health`

2. **Available Endpoints:**
   - API docs: `https://your-app.railway.app/docs`
   - Health: `https://your-app.railway.app/health`
   - Metrics: `https://your-app.railway.app/metrics`

3. **Background Services:**
   - Celery workers for ASR processing
   - Redis for caching and rate limiting
   - S3 for file storage

## 🧪 Testing Your Deployment

Once deployed, test these endpoints:

```bash
# Health check
curl https://your-app.railway.app/health

# API documentation
open https://your-app.railway.app/docs

# Test UWC integration
curl -X POST https://your-app.railway.app/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "tenant_id": "test-tenant"}'
```

## 🔄 Next Steps After Deployment

1. **Update Frontend:** Point your frontend to the new backend URL
2. **Test UWC Integration:** Verify all UWC endpoints work
3. **Set up Monitoring:** Configure Sentry and metrics
4. **Deploy to Production:** Use the same process for production

## 🆘 Troubleshooting

**Common Issues:**

1. **Import Errors:** Check that all dependencies are in `requirements.txt`
2. **Database Connection:** Verify `DATABASE_URL` is correct
3. **Redis Connection:** Verify `REDIS_URL` is correct
4. **UWC Integration:** Check `UWC_API_KEY` and `UWC_SECRET`

**Debug Commands:**
```bash
# Check logs
railway logs
# or
render logs
# or
heroku logs --tail

# Check environment variables
railway variables
# or
render env
# or
heroku config
```

## 📊 Monitoring & Observability

After deployment, you'll have:
- **Health checks** at `/health`
- **Metrics** at `/metrics`
- **API documentation** at `/docs`
- **Sentry error tracking** (if configured)
- **Database monitoring** (platform-specific)

---

**Ready to deploy?** Choose your platform and follow the steps above! 🚀
