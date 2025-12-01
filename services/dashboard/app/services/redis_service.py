"""
Redis Service for OttoAI
Handles distributed locking, rate limiting, and caching
"""
import redis
import json
import time
import hashlib
import hmac
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from app.config import settings
from app.obs.logging import get_logger

logger = get_logger(__name__)

class RedisService:
    """Redis service for distributed operations"""
    
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self.client = None
        self._connect()
    
    def _connect(self):
        """Connect to Redis"""
        try:
            if self.redis_url:
                self.client = redis.from_url(self.redis_url, decode_responses=True)
                # Test connection
                self.client.ping()
                logger.info("Connected to Redis successfully")
            else:
                logger.warning("Redis URL not configured, using in-memory fallback")
                self.client = None
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self.client = None
    
    def is_available(self) -> bool:
        """Check if Redis is available"""
        if not self.client:
            return False
        try:
            self.client.ping()
            return True
        except:
            return False
    
    # Distributed Locking
    def acquire_lock(self, key: str, timeout: int = 300, tenant_id: str = None) -> Optional[str]:
        """
        Acquire a distributed lock
        
        Args:
            key: Lock key
            timeout: Lock timeout in seconds
            tenant_id: Tenant ID for isolation
            
        Returns:
            Lock token if acquired, None if failed
        """
        if not self.is_available():
            logger.warning("Redis not available, skipping lock acquisition")
            return "no-redis"
        
        try:
            lock_key = f"lock:{tenant_id or 'default'}:{key}" if tenant_id else f"lock:{key}"
            lock_token = f"{int(time.time() * 1000)}:{hashlib.md5(key.encode()).hexdigest()[:8]}"
            
            # Try to acquire lock with expiration
            if self.client.set(lock_key, lock_token, nx=True, ex=timeout):
                logger.info(f"Lock acquired: {lock_key}")
                return lock_token
            else:
                logger.warning(f"Lock already exists: {lock_key}")
                return None
                
        except Exception as e:
            logger.error(f"Error acquiring lock: {str(e)}")
            return None
    
    def release_lock(self, key: str, lock_token: str, tenant_id: str = None) -> bool:
        """
        Release a distributed lock
        
        Args:
            key: Lock key
            lock_token: Lock token from acquire_lock
            tenant_id: Tenant ID for isolation
            
        Returns:
            True if released successfully
        """
        if not self.is_available():
            return True  # Assume success if Redis not available
        
        try:
            lock_key = f"lock:{tenant_id or 'default'}:{key}" if tenant_id else f"lock:{key}"
            
            # Use Lua script to ensure atomic release
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            
            result = self.client.eval(lua_script, 1, lock_key, lock_token)
            if result:
                logger.info(f"Lock released: {lock_key}")
                return True
            else:
                logger.warning(f"Lock not released (token mismatch): {lock_key}")
                return False
                
        except Exception as e:
            logger.error(f"Error releasing lock: {str(e)}")
            return False
    
    def extend_lock(self, key: str, lock_token: str, timeout: int = 300, tenant_id: str = None) -> bool:
        """
        Extend a distributed lock
        
        Args:
            key: Lock key
            lock_token: Lock token from acquire_lock
            timeout: New timeout in seconds
            tenant_id: Tenant ID for isolation
            
        Returns:
            True if extended successfully
        """
        if not self.is_available():
            return True
        
        try:
            lock_key = f"lock:{tenant_id or 'default'}:{key}" if tenant_id else f"lock:{key}"
            
            # Use Lua script to ensure atomic extension
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("expire", KEYS[1], ARGV[2])
            else
                return 0
            end
            """
            
            result = self.client.eval(lua_script, 1, lock_key, lock_token, timeout)
            if result:
                logger.info(f"Lock extended: {lock_key}")
                return True
            else:
                logger.warning(f"Lock not extended (token mismatch): {lock_key}")
                return False
                
        except Exception as e:
            logger.error(f"Error extending lock: {str(e)}")
            return False
    
    # Rate Limiting
    def check_rate_limit(self, key: str, limit: int, window: int, tenant_id: str = None) -> Dict[str, Any]:
        """
        Check rate limit for a key
        
        Args:
            key: Rate limit key
            limit: Maximum requests allowed
            window: Time window in seconds
            tenant_id: Tenant ID for isolation
            
        Returns:
            Dict with allowed, remaining, reset_time
        """
        if not self.is_available():
            return {"allowed": True, "remaining": limit, "reset_time": int(time.time()) + window}
        
        try:
            rate_key = f"rate:{tenant_id or 'default'}:{key}" if tenant_id else f"rate:{key}"
            current_time = int(time.time())
            window_start = current_time - window
            
            # Use sliding window approach
            pipe = self.client.pipeline()
            
            # Remove old entries
            pipe.zremrangebyscore(rate_key, 0, window_start)
            
            # Count current entries
            pipe.zcard(rate_key)
            
            # Add current request
            pipe.zadd(rate_key, {str(current_time): current_time})
            
            # Set expiration
            pipe.expire(rate_key, window)
            
            results = pipe.execute()
            current_count = results[1]
            
            allowed = current_count < limit
            remaining = max(0, limit - current_count - 1)
            reset_time = current_time + window
            
            return {
                "allowed": allowed,
                "remaining": remaining,
                "reset_time": reset_time,
                "current_count": current_count
            }
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            return {"allowed": True, "remaining": limit, "reset_time": int(time.time()) + window}
    
    # Circuit Breaker
    def get_circuit_breaker_state(self, service_name: str, tenant_id: str = None) -> Dict[str, Any]:
        """Get circuit breaker state for a service"""
        if not self.is_available():
            return {"state": "closed", "failure_count": 0, "success_count": 0}
        
        try:
            cb_key = f"circuit_breaker:{tenant_id or 'default'}:{service_name}" if tenant_id else f"circuit_breaker:{service_name}"
            state = self.client.hgetall(cb_key)
            
            if not state:
                return {"state": "closed", "failure_count": 0, "success_count": 0}
            
            return {
                "state": state.get("state", "closed"),
                "failure_count": int(state.get("failure_count", 0)),
                "success_count": int(state.get("success_count", 0)),
                "last_failure_at": state.get("last_failure_at"),
                "opened_at": state.get("opened_at")
            }
            
        except Exception as e:
            logger.error(f"Error getting circuit breaker state: {str(e)}")
            return {"state": "closed", "failure_count": 0, "success_count": 0}
    
    def update_circuit_breaker_state(self, service_name: str, state: str, tenant_id: str = None, **kwargs) -> bool:
        """Update circuit breaker state"""
        if not self.is_available():
            return True
        
        try:
            cb_key = f"circuit_breaker:{tenant_id or 'default'}:{service_name}" if tenant_id else f"circuit_breaker:{service_name}"
            
            update_data = {
                "state": state,
                "updated_at": int(time.time())
            }
            update_data.update(kwargs)
            
            self.client.hset(cb_key, mapping=update_data)
            self.client.expire(cb_key, 3600)  # Expire after 1 hour
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating circuit breaker state: {str(e)}")
            return False
    
    # Event Deduplication
    def is_event_processed(self, event_id: str, tenant_id: str = None) -> bool:
        """Check if an event has already been processed"""
        if not self.is_available():
            return False
        
        try:
            dedup_key = f"dedup:{tenant_id or 'default'}:{event_id}" if tenant_id else f"dedup:{event_id}"
            return self.client.exists(dedup_key) > 0
            
        except Exception as e:
            logger.error(f"Error checking event deduplication: {str(e)}")
            return False
    
    def mark_event_processed(self, event_id: str, ttl: int = 3600, tenant_id: str = None) -> bool:
        """Mark an event as processed"""
        if not self.is_available():
            return True
        
        try:
            dedup_key = f"dedup:{tenant_id or 'default'}:{event_id}" if tenant_id else f"dedup:{event_id}"
            self.client.setex(dedup_key, ttl, "processed")
            return True
            
        except Exception as e:
            logger.error(f"Error marking event as processed: {str(e)}")
            return False
    
    # Caching
    def get_cache(self, key: str, tenant_id: str = None) -> Optional[Any]:
        """Get value from cache"""
        if not self.is_available():
            return None
        
        try:
            cache_key = f"cache:{tenant_id or 'default'}:{key}" if tenant_id else f"cache:{key}"
            value = self.client.get(cache_key)
            if value:
                return json.loads(value)
            return None
            
        except Exception as e:
            logger.error(f"Error getting cache: {str(e)}")
            return None
    
    def set_cache(self, key: str, value: Any, ttl: int = 3600, tenant_id: str = None) -> bool:
        """Set value in cache"""
        if not self.is_available():
            return True
        
        try:
            cache_key = f"cache:{tenant_id or 'default'}:{key}" if tenant_id else f"cache:{key}"
            self.client.setex(cache_key, ttl, json.dumps(value))
            return True
            
        except Exception as e:
            logger.error(f"Error setting cache: {str(e)}")
            return False
    
    def delete_cache(self, key: str, tenant_id: str = None) -> bool:
        """Delete value from cache"""
        if not self.is_available():
            return True
        
        try:
            cache_key = f"cache:{tenant_id or 'default'}:{key}" if tenant_id else f"cache:{key}"
            self.client.delete(cache_key)
            return True
            
        except Exception as e:
            logger.error(f"Error deleting cache: {str(e)}")
            return False
    
    # Health Check
    def health_check(self) -> Dict[str, Any]:
        """Check Redis health"""
        if not self.is_available():
            return {
                "status": "unhealthy",
                "error": "Redis not available",
                "connected": False
            }
        
        try:
            start_time = time.time()
            self.client.ping()
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "connected": True,
                "response_time_ms": round(response_time, 2)
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "connected": False
            }

# Global Redis service instance
redis_service = RedisService()










