"""
OpenAI API Client Manager with multi-key support, rotation, and circuit breaking.

Supports:
- Multiple API keys for load distribution
- Round-robin and random key rotation
- Circuit breaker for failed keys
- Rate limit handling per key
- Automatic fallback to healthy keys
"""
import random
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum

from openai import OpenAI
from openai import RateLimitError, APIError, APIConnectionError, APITimeoutError

from app.config import settings
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)


class KeyRotationStrategy(str, Enum):
    """Strategy for selecting API keys."""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_USED = "least_used"


class OpenAIClientManager:
    """
    Manages multiple OpenAI API keys with rotation, circuit breaking, and rate limit handling.
    
    Environment variable format:
    - Single key: OPENAI_API_KEY=sk-...
    - Multiple keys: OPENAI_API_KEYS=sk-key1,sk-key2,sk-key3
    - Or: OPENAI_API_KEY_1, OPENAI_API_KEY_2, OPENAI_API_KEY_3, ...
    """
    
    def __init__(
        self,
        rotation_strategy: KeyRotationStrategy = KeyRotationStrategy.ROUND_ROBIN,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_timeout: int = 300,  # 5 minutes
        rate_limit_backoff: int = 60,  # 1 minute
    ):
        """
        Initialize the OpenAI client manager.
        
        Args:
            rotation_strategy: How to select keys (round_robin, random, least_used)
            circuit_breaker_threshold: Number of failures before disabling a key
            circuit_breaker_timeout: Seconds before retrying a failed key
            rate_limit_backoff: Seconds to wait after rate limit error
        """
        self.rotation_strategy = rotation_strategy
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self.rate_limit_backoff = rate_limit_backoff
        
        # Load API keys from environment
        self.keys = self._load_api_keys()
        
        if not self.keys:
            logger.warning("No OpenAI API keys configured - property intelligence will be disabled")
        
        # Initialize key state tracking
        self.key_states: Dict[str, Dict[str, Any]] = {}
        for key_id in self.keys:
            self.key_states[key_id] = {
                "failures": 0,
                "circuit_open": False,
                "circuit_open_until": None,
                "rate_limited_until": None,
                "last_used": None,
                "request_count": 0,
                "success_count": 0,
            }
        
        # Round-robin state
        self._round_robin_index = 0
        self._current_key_id: Optional[str] = None  # Track which key we're using
        
        logger.info(
            f"Initialized OpenAI client manager with {len(self.keys)} key(s), strategy: {rotation_strategy.value}"
        )
    
    def _load_api_keys(self) -> List[str]:
        """Load API keys from environment variables."""
        keys = []
        
        # Option 1: Comma-separated list in OPENAI_API_KEYS
        keys_str = settings.OPENAI_API_KEYS if hasattr(settings, 'OPENAI_API_KEYS') else None
        if keys_str:
            keys.extend([k.strip() for k in keys_str.split(",") if k.strip()])
        
        # Option 2: Single key in OPENAI_API_KEY (backward compatible)
        if settings.OPENAI_API_KEY:
            keys.append(settings.OPENAI_API_KEY)
        
        # Option 3: Numbered keys OPENAI_API_KEY_1, OPENAI_API_KEY_2, ...
        import os
        i = 1
        while True:
            key = os.getenv(f"OPENAI_API_KEY_{i}")
            if not key:
                break
            keys.append(key)
            i += 1
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keys = []
        for key in keys:
            if key not in seen:
                seen.add(key)
                unique_keys.append(key)
        
        return unique_keys
    
    def _select_key(self) -> Optional[str]:
        """Select the next API key based on rotation strategy."""
        if not self.keys:
            return None
        
        # Filter to healthy keys
        healthy_keys = [
            key_id for key_id in self.keys
            if self._is_key_healthy(key_id)
        ]
        
        # If no healthy keys, reset circuit breakers and try all keys
        if not healthy_keys:
            logger.warning("All keys are unhealthy - resetting circuit breakers and retrying")
            for key_id in self.keys:
                self._reset_circuit_breaker(key_id)
            healthy_keys = self.keys
        
        if not healthy_keys:
            return None
        
        # Select key based on strategy
        if self.rotation_strategy == KeyRotationStrategy.ROUND_ROBIN:
            selected = healthy_keys[self._round_robin_index % len(healthy_keys)]
            self._round_robin_index = (self._round_robin_index + 1) % len(healthy_keys)
            return selected
        
        elif self.rotation_strategy == KeyRotationStrategy.RANDOM:
            return random.choice(healthy_keys)
        
        elif self.rotation_strategy == KeyRotationStrategy.LEAST_USED:
            # Select key with lowest request count
            return min(healthy_keys, key=lambda k: self.key_states[k]["request_count"])
        
        else:
            # Default to round-robin
            return healthy_keys[0]
    
    def _is_key_healthy(self, key_id: str) -> bool:
        """Check if a key is healthy and available."""
        state = self.key_states[key_id]
        
        # Check circuit breaker
        if state["circuit_open"]:
            if state["circuit_open_until"] and datetime.utcnow() < state["circuit_open_until"]:
                return False
            else:
                # Timeout expired, reset circuit breaker
                self._reset_circuit_breaker(key_id)
        
        # Check rate limit backoff
        if state["rate_limited_until"] and datetime.utcnow() < state["rate_limited_until"]:
            return False
        
        return True
    
    def _reset_circuit_breaker(self, key_id: str):
        """Reset circuit breaker for a key."""
        self.key_states[key_id]["circuit_open"] = False
        self.key_states[key_id]["circuit_open_until"] = None
        self.key_states[key_id]["failures"] = 0
        logger.info(f"Reset circuit breaker for OpenAI key {key_id[:10]}...")
    
    def _record_failure(self, key_id: str, error: Exception):
        """Record a failure for a key."""
        state = self.key_states[key_id]
        state["failures"] += 1
        
        # Check if we should open circuit breaker
        if state["failures"] >= self.circuit_breaker_threshold:
            state["circuit_open"] = True
            state["circuit_open_until"] = datetime.utcnow() + timedelta(seconds=self.circuit_breaker_timeout)
            logger.warning(
                f"Circuit breaker opened for OpenAI key {key_id[:10]}... "
                f"after {state['failures']} failures. Will retry after {self.circuit_breaker_timeout}s"
            )
        
        # Handle rate limit errors specially
        if isinstance(error, RateLimitError):
            state["rate_limited_until"] = datetime.utcnow() + timedelta(seconds=self.rate_limit_backoff)
            logger.warning(
                f"Rate limited on OpenAI key {key_id[:10]}... "
                f"backing off for {self.rate_limit_backoff}s"
            )
    
    def _record_success(self, key_id: str):
        """Record a successful request for a key."""
        state = self.key_states[key_id]
        state["last_used"] = datetime.utcnow()
        state["request_count"] += 1
        state["success_count"] += 1
        
        # Reset failure count on success
        if state["failures"] > 0:
            state["failures"] = max(0, state["failures"] - 1)
    
    def get_client(self) -> Optional[OpenAI]:
        """
        Get an OpenAI client with a healthy API key.
        
        Returns:
            OpenAI client instance, or None if no healthy keys available
        """
        key_id = self._select_key()
        if not key_id:
            logger.error("No healthy OpenAI API keys available")
            return None
        
        # Store key ID for tracking
        self._current_key_id = key_id
        
        # Masks key for logging
        masked_key = f"{key_id[:10]}...{key_id[-4:]}" if len(key_id) > 14 else "***"
        logger.debug(f"Using OpenAI key: {masked_key}")
        
        return OpenAI(api_key=key_id)
    
    def execute_with_retry(
        self,
        func,
        max_retries: int = 3,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute an OpenAI API call with automatic key rotation and retry.
        
        Args:
            func: Function that takes an OpenAI client and returns a result
            max_retries: Maximum number of retries across different keys
            *args, **kwargs: Arguments to pass to func
            
        Returns:
            Result from func
            
        Raises:
            Exception: If all keys fail after retries
        """
        last_error = None
        
        for attempt in range(max_retries):
            client = self.get_client()
            if not client:
                raise RuntimeError("No healthy OpenAI API keys available")
            
            # Get the key ID for this client (we need to track which key we're using)
            key_id = self._get_key_for_client(client)
            
            try:
                result = func(client, *args, **kwargs)
                self._record_success(key_id)
                return result
                
            except RateLimitError as e:
                self._record_failure(key_id, e)
                last_error = e
                logger.warning(
                    f"Rate limit error on attempt {attempt + 1}/{max_retries}. "
                    f"Retrying with different key..."
                )
                # Short delay before retry
                time.sleep(1)
                
            except (APIConnectionError, APITimeoutError) as e:
                self._record_failure(key_id, e)
                last_error = e
                logger.warning(
                    f"Connection/timeout error on attempt {attempt + 1}/{max_retries}. "
                    f"Retrying with different key..."
                )
                time.sleep(2)
                
            except APIError as e:
                # For other API errors, try different key once
                self._record_failure(key_id, e)
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"API error on attempt {attempt + 1}/{max_retries}. "
                        f"Retrying with different key..."
                    )
                    time.sleep(1)
                else:
                    raise
                    
            except Exception as e:
                # Unexpected error - don't retry
                self._record_failure(key_id, e)
                logger.error(f"Unexpected error in OpenAI API call: {str(e)}")
                raise
        
        # All retries exhausted
        logger.error(f"All OpenAI API keys failed after {max_retries} retries")
        if last_error:
            raise last_error
        raise RuntimeError("OpenAI API call failed after retries")
    
    def _get_key_for_client(self, client: OpenAI) -> str:
        """Get the key ID for a client instance."""
        # Return the key we're currently using
        if self._current_key_id:
            return self._current_key_id
        # Fallback: return first healthy key
        for key_id in self.keys:
            if self._is_key_healthy(key_id):
                return key_id
        return self.keys[0] if self.keys else ""
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about key usage and health."""
        stats = {
            "total_keys": len(self.keys),
            "healthy_keys": sum(1 for k in self.keys if self._is_key_healthy(k)),
            "rotation_strategy": self.rotation_strategy.value,
            "keys": {},
        }
        
        for key_id in self.keys:
            state = self.key_states[key_id]
            masked_key = f"{key_id[:10]}...{key_id[-4:]}" if len(key_id) > 14 else "***"
            stats["keys"][masked_key] = {
                "requests": state["request_count"],
                "successes": state["success_count"],
                "failures": state["failures"],
                "circuit_open": state["circuit_open"],
                "rate_limited": bool(
                    state["rate_limited_until"] and datetime.utcnow() < state["rate_limited_until"]
                ),
                "last_used": state["last_used"].isoformat() if state["last_used"] else None,
            }
        
        return stats


# Global instance
_openai_client_manager: Optional[OpenAIClientManager] = None


def get_openai_client_manager() -> OpenAIClientManager:
    """Get or create the global OpenAI client manager."""
    global _openai_client_manager
    if _openai_client_manager is None:
        import os
        rotation_strategy_str = os.getenv("OPENAI_KEY_ROTATION_STRATEGY", "round_robin")
        try:
            rotation_strategy = KeyRotationStrategy(rotation_strategy_str)
        except ValueError:
            logger.warning(f"Invalid rotation strategy '{rotation_strategy_str}', using round_robin")
            rotation_strategy = KeyRotationStrategy.ROUND_ROBIN
        _openai_client_manager = OpenAIClientManager(rotation_strategy=rotation_strategy)
    return _openai_client_manager


def get_openai_client() -> Optional[OpenAI]:
    """Get an OpenAI client with automatic key rotation."""
    manager = get_openai_client_manager()
    return manager.get_client()

