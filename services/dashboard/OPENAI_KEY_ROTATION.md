# OpenAI API Key Rotation & Multi-Key Setup

## Overview

The OpenAI client manager supports multiple API keys with automatic rotation, circuit breaking, and rate limit handling. This enables:

- **Load Distribution**: Spread requests across multiple keys to avoid hitting per-key rate limits
- **Fault Tolerance**: Automatically failover to healthy keys if one fails
- **Rate Limit Handling**: Automatically back off and rotate to other keys when rate limited
- **Quota Management**: Distribute usage across multiple OpenAI accounts

## Configuration

### Option 1: Comma-Separated List (Recommended)

Set `OPENAI_API_KEYS` as a comma-separated list:

```bash
OPENAI_API_KEYS=sk-key1,sk-key2,sk-key3
```

### Option 2: Numbered Keys

Set individual keys with numbered environment variables:

```bash
OPENAI_API_KEY_1=sk-key1
OPENAI_API_KEY_2=sk-key2
OPENAI_API_KEY_3=sk-key3
```

### Option 3: Single Key (Backward Compatible)

For single-key setups, use the original `OPENAI_API_KEY`:

```bash
OPENAI_API_KEY=sk-key1
```

### Rotation Strategy

Configure how keys are selected using `OPENAI_KEY_ROTATION_STRATEGY`:

- **`round_robin`** (default): Rotate through keys in order
- **`random`**: Select a random healthy key each time
- **`least_used`**: Always use the key with the fewest requests

```bash
OPENAI_KEY_ROTATION_STRATEGY=round_robin
```

## Production Setup (Railway/Vercel/etc.)

### Railway

1. **Add Multiple Keys to Railway Environment**:

   ```bash
   # In Railway dashboard, add:
   OPENAI_API_KEYS=sk-key1,sk-key2,sk-key3
   OPENAI_KEY_ROTATION_STRATEGY=round_robin
   ```

2. **Or use Railway CLI**:

   ```bash
   railway variables set OPENAI_API_KEYS="sk-key1,sk-key2,sk-key3"
   railway variables set OPENAI_KEY_ROTATION_STRATEGY=round_robin
   ```

### Vercel (if deploying backend there)

```bash
vercel env add OPENAI_API_KEYS production
# Paste: sk-key1,sk-key2,sk-key3

vercel env add OPENAI_KEY_ROTATION_STRATEGY production
# Paste: round_robin
```

## How It Works

### Automatic Key Rotation

1. **Request comes in** → Manager selects a healthy key based on strategy
2. **Key succeeds** → Success is recorded, failure count decreases
3. **Key fails (rate limit)** → Key is marked as rate-limited, request retries with different key
4. **Key fails (circuit breaker)** → After 3 failures, key is disabled for 5 minutes

### Circuit Breaker

- **Threshold**: 3 consecutive failures open the circuit
- **Timeout**: Circuit opens for 5 minutes, then auto-resets
- **Recovery**: On success, failure count decreases

### Rate Limit Handling

- **Detection**: Automatic detection of `RateLimitError`
- **Backoff**: Rate-limited keys are disabled for 60 seconds
- **Retry**: Requests automatically retry with different keys

## Monitoring

### View Key Statistics

Access the admin endpoint (requires `exec` or `manager` role):

```bash
GET /api/v1/admin/openai/stats
```

Response:

```json
{
  "success": true,
  "data": {
    "total_keys": 3,
    "healthy_keys": 2,
    "rotation_strategy": "round_robin",
    "keys": {
      "sk-proj-abc...xyz1": {
        "requests": 150,
        "successes": 148,
        "failures": 2,
        "circuit_open": false,
        "rate_limited": false,
        "last_used": "2024-11-15T10:30:00"
      },
      "sk-proj-def...uvw2": {
        "requests": 145,
        "successes": 145,
        "failures": 0,
        "circuit_open": false,
        "rate_limited": false,
        "last_used": "2024-11-15T10:29:45"
      },
      "sk-proj-ghi...rst3": {
        "requests": 100,
        "successes": 95,
        "failures": 5,
        "circuit_open": true,
        "rate_limited": false,
        "last_used": "2024-11-15T10:25:00"
      }
    }
  }
}
```

### Logs

Key usage and failures are logged with masked keys:

```
INFO: Using OpenAI key: sk-proj-abc...xyz1
WARNING: Rate limited on OpenAI key sk-proj-def...uvw2 backing off for 60s
WARNING: Circuit breaker opened for OpenAI key sk-proj-ghi...rst3 after 3 failures
```

## Best Practices

### 1. Key Distribution

- **Start with 2-3 keys** for redundancy
- **Add more keys** as volume increases
- **Distribute across accounts** if using multiple OpenAI accounts

### 2. Monitoring

- **Check stats regularly** via admin endpoint
- **Set up alerts** for circuit breaker activations
- **Monitor rate limit frequency** to determine if more keys are needed

### 3. Key Rotation

- **Rotate keys periodically** (e.g., every 90 days)
- **Add new key first**, then remove old key after verifying it's not used
- **Monitor for failures** after rotating

### 4. Quota Management

- **Use `least_used` strategy** if you want even distribution
- **Use `round_robin`** for predictable load balancing
- **Use `random`** for simple distribution without tracking overhead

## Troubleshooting

### All Keys Unhealthy

If all keys are marked unhealthy, the manager will:
1. Reset all circuit breakers
2. Try all keys again
3. Log a warning if still failing

### Rate Limits Persist

If you're still hitting rate limits with multiple keys:
1. **Add more keys** to increase total quota
2. **Check individual key quotas** in OpenAI dashboard
3. **Consider upgrading** OpenAI plan for higher limits

### Key Not Working

If a key consistently fails:
1. **Check key validity** in OpenAI dashboard
2. **Verify key permissions** (must have API access)
3. **Remove key** from rotation until resolved

## Code Usage

### Property Intelligence Task

The property intelligence scraping automatically uses the key manager:

```python
from app.services.openai_client_manager import get_openai_client_manager

manager = get_openai_client_manager()

# Automatically rotates keys and retries on failure
response = manager.execute_with_retry(
    lambda client: client.chat.completions.create(...),
    max_retries=len(manager.keys) + 1
)
```

### Direct Client Access

For other use cases:

```python
from app.services.openai_client_manager import get_openai_client

client = get_openai_client()
if client:
    response = client.chat.completions.create(...)
```

## Security Notes

- **Never commit keys** to git (already in `.gitignore`)
- **Use environment variables** for all keys
- **Rotate compromised keys** immediately
- **Monitor usage** for unexpected spikes (potential key leak)




