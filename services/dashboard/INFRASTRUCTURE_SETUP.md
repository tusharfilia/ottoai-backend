# Otto AI Infrastructure Setup Guide

## 🏗️ Foundational Services Setup

This guide will help you set up all the foundational infrastructure for Otto AI platform.

### Prerequisites
- Fly.io CLI installed and authenticated
- AWS credentials configured
- Python 3.8+ with pip

### 1. Database Setup (Postgres)

```bash
# Create Postgres database
flyctl postgres create --name otto-staging-db --region phx --initial-cluster-size 1 --vm-size shared-cpu-1x

# Get connection string
flyctl postgres connect --app otto-staging-db --command "echo \$DATABASE_URL"
```

### 2. Redis Setup

```bash
# Create Redis instance
flyctl redis create --name otto-staging-redis --region phx

# Get connection string
flyctl redis connect --app otto-staging-redis --command "echo \$REDIS_URL"
```

### 3. S3 Configuration

```bash
# Install boto3
pip install boto3

# Run S3 setup script
python setup_s3.py
```

### 4. Staging App Setup

```bash
# Run the infrastructure setup script
chmod +x setup_infrastructure.sh
./setup_infrastructure.sh
```

### 5. Manual Secret Configuration

After running the setup script, you'll need to set these secrets manually:

```bash
# Sentry (get your DSN from Sentry dashboard)
flyctl secrets set --app tv-mvp-staging SENTRY_DSN="your-sentry-dsn-here"

# Clerk Authentication
flyctl secrets set --app tv-mvp-staging CLERK_SECRET_KEY="your-clerk-secret-key"
flyctl secrets set --app tv-mvp-staging CLERK_PUBLISHABLE_KEY="your-clerk-publishable-key"

# Twilio (if you have credentials)
flyctl secrets set --app tv-mvp-staging TWILIO_ACCOUNT_SID="your-twilio-sid"
flyctl secrets set --app tv-mvp-staging TWILIO_AUTH_TOKEN="your-twilio-token"

# CallRail (if you have credentials)
flyctl secrets set --app tv-mvp-staging CALLRAIL_API_KEY="your-callrail-key"
```

### 6. Deploy Staging App

```bash
# Deploy with staging config
flyctl deploy --config fly.staging.toml --app tv-mvp-staging
```

### 7. Verify Setup

```bash
# Check app status
flyctl status --app tv-mvp-staging

# Check logs
flyctl logs --app tv-mvp-staging

# Test health endpoint
curl https://tv-mvp-staging.fly.dev/health

# Test detailed health
curl https://tv-mvp-staging.fly.dev/health/detailed
```

## 🔧 Service Configuration

### Redis Configuration
- **Purpose**: Rate limiting, caching, Celery broker, session storage
- **Queues**: asr, analysis, followups, indexing, uwc, default
- **Retention**: 7 days for task results

### S3 Configuration
- **Buckets**: `otto-documents-staging` (staging), `otto-documents` (production)
- **Folders**: audio/, documents/, temp/, exports/, backups/
- **Lifecycle**: Audio → IA (30d) → Glacier (90d) → Delete (7y)
- **CORS**: Enabled for Otto AI domains
- **Encryption**: AES256

### Celery Workers
- **API Process**: Main FastAPI application
- **Worker Process**: Background task processing
- **Beat Process**: Scheduled tasks and periodic jobs

### Health Checks
- **Basic**: `/health` - Simple status check
- **Detailed**: `/health/detailed` - All dependencies
- **Readiness**: `/health/ready` - Kubernetes ready probe
- **Liveness**: `/health/live` - Kubernetes live probe
- **Metrics**: `/metrics` - Prometheus metrics

## 📊 Monitoring Setup

### Sentry Integration
1. Create Sentry project
2. Get DSN from project settings
3. Set `SENTRY_DSN` secret in Fly.io

### Health Monitoring
- **Health Endpoint**: `https://tv-mvp-staging.fly.dev/health`
- **Metrics Endpoint**: `https://tv-mvp-staging.fly.dev/metrics`
- **API Docs**: `https://tv-mvp-staging.fly.dev/docs`

### Log Monitoring
```bash
# View real-time logs
flyctl logs --app tv-mvp-staging --follow

# View specific process logs
flyctl logs --app tv-mvp-staging --process api
flyctl logs --app tv-mvp-staging --process worker
flyctl logs --app tv-mvp-staging --process beat
```

## 🚀 Next Steps

1. **Test All Services**: Verify database, Redis, S3, and UWC connections
2. **Set Up Authentication**: Configure Clerk with proper webhooks
3. **Configure Webhooks**: Set up CallRail, Twilio, and UWC webhooks
4. **Add Monitoring**: Set up Sentry alerts and health monitoring
5. **Load Testing**: Test with realistic traffic loads

## 🔍 Troubleshooting

### Common Issues

1. **Database Connection Issues**
   ```bash
   # Check database status
   flyctl postgres list
   flyctl postgres connect --app otto-staging-db
   ```

2. **Redis Connection Issues**
   ```bash
   # Check Redis status
   flyctl redis list
   flyctl redis connect --app otto-staging-redis
   ```

3. **S3 Access Issues**
   ```bash
   # Test S3 access
   aws s3 ls s3://otto-documents-staging/
   ```

4. **App Deployment Issues**
   ```bash
   # Check app status
   flyctl status --app tv-mvp-staging
   
   # View deployment logs
   flyctl logs --app tv-mvp-staging
   ```

### Debug Commands

```bash
# SSH into app
flyctl ssh console --app tv-mvp-staging

# Check secrets
flyctl secrets list --app tv-mvp-staging

# Scale workers
flyctl scale worker 2 --app tv-mvp-staging

# Restart app
flyctl restart --app tv-mvp-staging
```

## 📋 Checklist

- [ ] Postgres database created and accessible
- [ ] Redis instance created and accessible
- [ ] S3 bucket configured with CORS and lifecycle rules
- [ ] Staging app deployed successfully
- [ ] All secrets configured
- [ ] Health checks passing
- [ ] Celery workers running
- [ ] UWC integration working
- [ ] Monitoring configured
- [ ] Documentation updated

## 🆘 Support

If you encounter issues:
1. Check the logs: `flyctl logs --app tv-mvp-staging`
2. Verify secrets: `flyctl secrets list --app tv-mvp-staging`
3. Test health endpoint: `curl https://tv-mvp-staging.fly.dev/health/detailed`
4. Check Fly.io status page for service issues
