"""
Redis Distributed Lock Service
Provides distributed locking for missed call queue processing
"""
import asyncio
import time
from typing import Optional, Dict, Any
from app.services.redis_service import redis_service
from app.obs.logging import get_logger

logger = get_logger(__name__)

class RedisLockService:
    """Redis-based distributed lock service"""
    
    def __init__(self):
        self.redis = redis_service
        self.active_locks: Dict[str, Dict[str, Any]] = {}
    
    async def acquire_lock(
        self, 
        lock_key: str, 
        tenant_id: str, 
        timeout: int = 300,
        retry_attempts: int = 3,
        retry_delay: float = 1.0
    ) -> Optional[str]:
        """
        Acquire a distributed lock with retry logic
        
        Args:
            lock_key: Unique lock identifier
            tenant_id: Tenant ID for isolation
            timeout: Lock timeout in seconds
            retry_attempts: Number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            Lock token if acquired, None if failed
        """
        for attempt in range(retry_attempts):
            try:
                lock_token = self.redis.acquire_lock(
                    key=lock_key,
                    timeout=timeout,
                    tenant_id=tenant_id
                )
                
                if lock_token:
                    # Track active lock
                    self.active_locks[lock_key] = {
                        "token": lock_token,
                        "tenant_id": tenant_id,
                        "acquired_at": time.time(),
                        "timeout": timeout
                    }
                    
                    logger.info(f"Lock acquired: {lock_key} (attempt {attempt + 1})")
                    return lock_token
                else:
                    logger.warning(f"Lock acquisition failed: {lock_key} (attempt {attempt + 1})")
                    
                    if attempt < retry_attempts - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    else:
                        logger.error(f"Failed to acquire lock after {retry_attempts} attempts: {lock_key}")
                        return None
                        
            except Exception as e:
                logger.error(f"Error acquiring lock {lock_key}: {str(e)}")
                if attempt < retry_attempts - 1:
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    return None
        
        return None
    
    async def release_lock(self, lock_key: str, tenant_id: str, lock_token: str) -> bool:
        """
        Release a distributed lock
        
        Args:
            lock_key: Lock identifier
            tenant_id: Tenant ID for isolation
            lock_token: Lock token from acquire_lock
            
        Returns:
            True if released successfully
        """
        try:
            success = self.redis.release_lock(
                key=lock_key,
                lock_token=lock_token,
                tenant_id=tenant_id
            )
            
            if success:
                # Remove from active locks
                if lock_key in self.active_locks:
                    del self.active_locks[lock_key]
                
                logger.info(f"Lock released: {lock_key}")
                return True
            else:
                logger.warning(f"Lock release failed: {lock_key}")
                return False
                
        except Exception as e:
            logger.error(f"Error releasing lock {lock_key}: {str(e)}")
            return False
    
    async def extend_lock(self, lock_key: str, tenant_id: str, lock_token: str, timeout: int = 300) -> bool:
        """
        Extend a distributed lock
        
        Args:
            lock_key: Lock identifier
            tenant_id: Tenant ID for isolation
            lock_token: Lock token from acquire_lock
            timeout: New timeout in seconds
            
        Returns:
            True if extended successfully
        """
        try:
            success = self.redis.extend_lock(
                key=lock_key,
                lock_token=lock_token,
                timeout=timeout,
                tenant_id=tenant_id
            )
            
            if success:
                # Update active lock info
                if lock_key in self.active_locks:
                    self.active_locks[lock_key]["timeout"] = timeout
                
                logger.info(f"Lock extended: {lock_key}")
                return True
            else:
                logger.warning(f"Lock extension failed: {lock_key}")
                return False
                
        except Exception as e:
            logger.error(f"Error extending lock {lock_key}: {str(e)}")
            return False
    
    async def is_lock_held(self, lock_key: str, tenant_id: str) -> bool:
        """
        Check if a lock is currently held
        
        Args:
            lock_key: Lock identifier
            tenant_id: Tenant ID for isolation
            
        Returns:
            True if lock is held
        """
        try:
            # Check if we have it in our active locks
            if lock_key in self.active_locks:
                lock_info = self.active_locks[lock_key]
                if lock_info["tenant_id"] == tenant_id:
                    return True
            
            # Check Redis directly
            return self.redis.acquire_lock(lock_key, timeout=1, tenant_id=tenant_id) is None
            
        except Exception as e:
            logger.error(f"Error checking lock status {lock_key}: {str(e)}")
            return False
    
    async def cleanup_expired_locks(self):
        """Clean up expired locks from active_locks dict"""
        try:
            current_time = time.time()
            expired_locks = []
            
            for lock_key, lock_info in self.active_locks.items():
                if current_time - lock_info["acquired_at"] > lock_info["timeout"]:
                    expired_locks.append(lock_key)
            
            for lock_key in expired_locks:
                del self.active_locks[lock_key]
                logger.info(f"Cleaned up expired lock: {lock_key}")
                
        except Exception as e:
            logger.error(f"Error cleaning up expired locks: {str(e)}")
    
    async def get_lock_info(self, lock_key: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a lock
        
        Args:
            lock_key: Lock identifier
            
        Returns:
            Lock information dict or None
        """
        return self.active_locks.get(lock_key)
    
    async def get_all_active_locks(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all active locks
        
        Returns:
            Dict of active locks
        """
        return self.active_locks.copy()
    
    async def force_release_lock(self, lock_key: str, tenant_id: str) -> bool:
        """
        Force release a lock (use with caution)
        
        Args:
            lock_key: Lock identifier
            tenant_id: Tenant ID for isolation
            
        Returns:
            True if released
        """
        try:
            # Remove from active locks
            if lock_key in self.active_locks:
                del self.active_locks[lock_key]
            
            # Force release in Redis
            redis_key = f"lock:{tenant_id}:{lock_key}"
            self.redis.client.delete(redis_key)
            
            logger.warning(f"Force released lock: {lock_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error force releasing lock {lock_key}: {str(e)}")
            return False

# Global lock service instance
redis_lock_service = RedisLockService()