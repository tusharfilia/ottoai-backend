"""
Circuit Breaker Service
Implements circuit breaker pattern for external service calls
Prevents cascade failures and provides graceful degradation
"""
import asyncio
import time
from enum import Enum
from typing import Callable, Any, Optional, Dict
from datetime import datetime, timedelta
import logging

from app.obs.logging import get_logger

logger = get_logger(__name__)

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking calls
    HALF_OPEN = "half_open"  # Testing if service recovered

class CircuitBreaker:
    """Circuit breaker implementation with tenant isolation"""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        tenant_id: Optional[str] = None
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.tenant_id = tenant_id
        
        # State tracking
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.success_count = 0
        
        # Metrics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result or raises exception
        """
        self.total_calls += 1
        
        # Check circuit state
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker {self.name} transitioning to HALF_OPEN")
            else:
                raise Exception(f"Circuit breaker {self.name} is OPEN - service unavailable")
        
        try:
            # Execute function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success - reset failure count
            self._on_success()
            return result
            
        except self.expected_exception as e:
            # Expected failure - increment failure count
            self._on_failure()
            logger.warning(f"Circuit breaker {self.name} failure: {str(e)}")
            raise e
            
        except Exception as e:
            # Unexpected failure - also increment failure count
            self._on_failure()
            logger.error(f"Circuit breaker {self.name} unexpected failure: {str(e)}")
            raise e
    
    def _on_success(self):
        """Handle successful call"""
        self.success_count += 1
        self.total_successes += 1
        
        if self.state == CircuitState.HALF_OPEN:
            # Success in half-open state - close circuit
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            logger.info(f"Circuit breaker {self.name} closed after successful call")
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            # Too many failures - open circuit
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker {self.name} opened after {self.failure_count} failures")
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset"""
        if self.last_failure_time is None:
            return True
        
        time_since_failure = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return time_since_failure >= self.recovery_timeout
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state"""
        return {
            "name": self.name,
            "tenant_id": self.tenant_id,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "failure_rate": self.total_failures / self.total_calls if self.total_calls > 0 else 0
        }
    
    def reset(self):
        """Reset circuit breaker to closed state"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        logger.info(f"Circuit breaker {self.name} manually reset")

class CircuitBreakerManager:
    """Manages multiple circuit breakers with tenant isolation"""
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
    
    def get_breaker(
        self,
        name: str,
        tenant_id: Optional[str] = None,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ) -> CircuitBreaker:
        """
        Get or create circuit breaker
        
        Args:
            name: Circuit breaker name
            tenant_id: Tenant ID for isolation
            failure_threshold: Number of failures before opening
            recovery_timeout: Seconds to wait before attempting reset
            expected_exception: Exception type to track
            
        Returns:
            Circuit breaker instance
        """
        # Create tenant-isolated key
        breaker_key = f"{tenant_id}:{name}" if tenant_id else name
        
        if breaker_key not in self.breakers:
            self.breakers[breaker_key] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception,
                tenant_id=tenant_id
            )
            logger.info(f"Created circuit breaker: {breaker_key}")
        
        return self.breakers[breaker_key]
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get state of all circuit breakers"""
        return {
            key: breaker.get_state()
            for key, breaker in self.breakers.items()
        }
    
    def reset_breaker(self, name: str, tenant_id: Optional[str] = None):
        """Reset specific circuit breaker"""
        breaker_key = f"{tenant_id}:{name}" if tenant_id else name
        
        if breaker_key in self.breakers:
            self.breakers[breaker_key].reset()
            logger.info(f"Reset circuit breaker: {breaker_key}")
        else:
            logger.warning(f"Circuit breaker not found: {breaker_key}")
    
    def reset_all(self):
        """Reset all circuit breakers"""
        for breaker in self.breakers.values():
            breaker.reset()
        logger.info("Reset all circuit breakers")

# Global circuit breaker manager
circuit_breaker_manager = CircuitBreakerManager()










