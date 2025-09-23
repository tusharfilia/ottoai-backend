# Redis Deployment for OttoAI Backend

## Overview

Redis is required for rate limiting and Celery task queue functionality in the OttoAI backend. This document covers Redis provisioning options for production deployment.

## Option 1: Fly.io Redis (Recommended)

### Provision Redis on Fly.io

```bash
# Create a Redis instance
fly redis create

# Follow prompts to configure:
# - Name: ottoai-redis
# - Region: phx (same as your app)
# - Plan: Choose based on needs (nano for development, micro for production)

# Get connection URL
fly redis status ottoai-redis

# Set the Redis URL as a secret
fly secrets set REDIS_URL="redis://default:<password>@<hostname>:6379"
```

### Configuration

Add to your Fly.io app secrets:

```bash
fly secrets set \
  REDIS_URL="redis://default:<password>@<hostname>:6379" \
  ENABLE_CELERY=true \
  ENABLE_CELERY_BEAT=true
```

## Option 2: Upstash Redis (Alternative)

### Create Upstash Redis Instance

1. Go to [Upstash Console](https://console.upstash.com/)
2. Create a new Redis database
3. Choose region closest to your Fly.io app (Phoenix)
4. Copy the Redis URL

### Configuration

```bash
fly secrets set \
  UPSTASH_REDIS_URL="rediss://:<password>@<hostname>:6380" \
  ENABLE_CELERY=true \
  ENABLE_CELERY_BEAT=true
```

## Option 3: External Redis Provider

### Popular Redis Providers

- **AWS ElastiCache**: High performance, fully managed
- **Google Cloud Memorystore**: Integrated with GCP
- **Azure Cache for Redis**: Microsoft Azure managed service
- **Redis Cloud**: Official Redis hosting

### Configuration

For any external provider:

```bash
fly secrets set \
  REDIS_URL="redis://username:password@hostname:port/database" \
  ENABLE_CELERY=true \
  ENABLE_CELERY_BEAT=true
```

## Terraform Configuration (Optional)

If using Infrastructure as Code, here's a basic Terraform configuration for Fly.io Redis:

```hcl
# terraform/redis.tf
resource "fly_app" "redis" {
  name = "ottoai-redis"
  org  = var.fly_org
}

resource "fly_volume" "redis_data" {
  name   = "redis_data"
  app    = fly_app.redis.name
  size   = 10
  region = var.primary_region
}

resource "fly_machine" "redis" {
  app    = fly_app.redis.name
  region = var.primary_region
  name   = "redis"
  image  = "redis:7-alpine"

  services = [
    {
      ports = [
        {
          port     = 6379
          handlers = ["redis"]
        }
      ]
      protocol      = "tcp"
      internal_port = 6379
    }
  ]

  mounts = [
    {
      volume = fly_volume.redis_data.id
      path   = "/data"
    }
  ]

  env = {
    REDIS_ARGS = "--appendonly yes --appendfsync everysec"
  }
}
```

## Security Considerations

### Network Security
- Redis should not be exposed to the public internet
- Use Fly.io private networking when possible
- Enable TLS/SSL for external providers

### Authentication
- Always use strong passwords
- Rotate Redis passwords regularly
- Use Redis AUTH for additional security

### Data Protection
- Enable Redis persistence (AOF/RDB) for production
- Set up regular backups
- Monitor Redis memory usage and performance

## Monitoring and Maintenance

### Health Checks
The backend includes Redis connectivity checks in the `/ready` endpoint:

```bash
curl https://your-app.fly.dev/ready
```

Should return:
```json
{
  "ready": true,
  "components": {
    "database": true,
    "redis": true,
    "celery_workers": true
  }
}
```

### Monitoring Metrics
- Redis memory usage
- Connection count
- Command statistics
- Key expiration rates

### Maintenance Tasks
- Monitor Redis memory usage
- Clean up expired keys
- Monitor slow queries
- Regular performance tuning

## Troubleshooting

### Common Issues

1. **Connection Refused**
   ```bash
   # Check Redis URL format
   echo $REDIS_URL
   
   # Test Redis connection
   redis-cli -u $REDIS_URL ping
   ```

2. **Authentication Failed**
   ```bash
   # Verify password in connection string
   # Format: redis://username:password@hostname:port/database
   ```

3. **SSL/TLS Issues**
   ```bash
   # For TLS connections, use rediss:// instead of redis://
   # Ensure certificates are valid
   ```

4. **Memory Issues**
   ```bash
   # Check Redis memory usage
   redis-cli -u $REDIS_URL info memory
   
   # Set maxmemory policy
   redis-cli -u $REDIS_URL config set maxmemory-policy allkeys-lru
   ```

### Performance Tuning

1. **Memory Optimization**
   - Set appropriate `maxmemory` limit
   - Configure `maxmemory-policy`
   - Use efficient data structures

2. **Connection Pooling**
   - Configure connection pool size
   - Set appropriate timeouts
   - Monitor connection usage

3. **Persistence Configuration**
   - Choose between RDB and AOF
   - Configure save intervals
   - Monitor disk I/O

## Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `REDIS_URL` | Yes* | Primary Redis connection URL | `redis://user:pass@host:6379/0` |
| `UPSTASH_REDIS_URL` | Yes* | Alternative Upstash Redis URL | `rediss://user:pass@host:6380` |
| `ENABLE_CELERY` | No | Enable Celery workers | `true` |
| `ENABLE_CELERY_BEAT` | No | Enable Celery beat scheduler | `true` |

*Either `REDIS_URL` or `UPSTASH_REDIS_URL` must be provided when Celery or rate limiting is enabled.

## Next Steps

After provisioning Redis:

1. Update your Fly.io secrets with the Redis URL
2. Deploy your application with the new configuration
3. Verify connectivity using the `/ready` endpoint
4. Monitor Redis performance and adjust configuration as needed
