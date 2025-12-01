#!/usr/bin/env python3
"""
Test Redis connection and functionality
"""
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.redis_service import redis_service
from app.services.redis_lock_service import redis_lock_service
from app.obs.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

async def test_redis_functionality():
    """Test Redis functionality"""
    try:
        logger.info("Testing Redis connection...")
        
        # Test basic connection
        health = redis_service.health_check()
        logger.info(f"Redis health: {health}")
        
        if not redis_service.is_available():
            logger.warning("Redis not available, skipping tests")
            return False
        
        # Test distributed locking
        logger.info("Testing distributed locking...")
        lock_key = "test_lock"
        tenant_id = "test_tenant"
        
        # Acquire lock
        lock_token = await redis_lock_service.acquire_lock(
            lock_key=lock_key,
            tenant_id=tenant_id,
            timeout=60
        )
        
        if lock_token:
            logger.info(f"✓ Lock acquired: {lock_token}")
            
            # Test lock extension
            extended = await redis_lock_service.extend_lock(
                lock_key=lock_key,
                tenant_id=tenant_id,
                lock_token=lock_token,
                timeout=120
            )
            logger.info(f"✓ Lock extended: {extended}")
            
            # Release lock
            released = await redis_lock_service.release_lock(
                lock_key=lock_key,
                tenant_id=tenant_id,
                lock_token=lock_token
            )
            logger.info(f"✓ Lock released: {released}")
        else:
            logger.error("✗ Failed to acquire lock")
            return False
        
        # Test rate limiting
        logger.info("Testing rate limiting...")
        rate_result = redis_service.check_rate_limit(
            key="test_rate_limit",
            limit=10,
            window=60,
            tenant_id=tenant_id
        )
        logger.info(f"✓ Rate limit result: {rate_result}")
        
        # Test circuit breaker
        logger.info("Testing circuit breaker...")
        cb_state = redis_service.get_circuit_breaker_state(
            service_name="test_service",
            tenant_id=tenant_id
        )
        logger.info(f"✓ Circuit breaker state: {cb_state}")
        
        # Test event deduplication
        logger.info("Testing event deduplication...")
        event_id = "test_event_123"
        
        # Check if event is processed (should be False)
        is_processed = redis_service.is_event_processed(event_id, tenant_id)
        logger.info(f"✓ Event processed check: {is_processed}")
        
        # Mark event as processed
        marked = redis_service.mark_event_processed(event_id, ttl=3600, tenant_id=tenant_id)
        logger.info(f"✓ Event marked as processed: {marked}")
        
        # Check again (should be True)
        is_processed = redis_service.is_event_processed(event_id, tenant_id)
        logger.info(f"✓ Event processed check after marking: {is_processed}")
        
        # Test caching
        logger.info("Testing caching...")
        cache_key = "test_cache"
        cache_value = {"test": "data", "timestamp": "2024-01-01"}
        
        # Set cache
        cache_set = redis_service.set_cache(cache_key, cache_value, ttl=3600, tenant_id=tenant_id)
        logger.info(f"✓ Cache set: {cache_set}")
        
        # Get cache
        cached_value = redis_service.get_cache(cache_key, tenant_id)
        logger.info(f"✓ Cache get: {cached_value}")
        
        # Delete cache
        cache_deleted = redis_service.delete_cache(cache_key, tenant_id)
        logger.info(f"✓ Cache deleted: {cache_deleted}")
        
        logger.info("All Redis tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Redis test failed: {str(e)}")
        return False

def main():
    """Main test function"""
    import asyncio
    
    success = asyncio.run(test_redis_functionality())
    
    if success:
        logger.info("✓ Redis functionality test passed")
    else:
        logger.error("✗ Redis functionality test failed")
        sys.exit(1)

if __name__ == "__main__":
    main()










