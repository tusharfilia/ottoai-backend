#!/usr/bin/env python3
"""
Quick script to check Redis connection status.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def check_redis():
    """Check Redis connection status."""
    print("🔍 Checking Redis Configuration\n")
    print("=" * 50)
    
    # Check environment variable
    redis_url = os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_URL")
    
    if redis_url:
        print(f"✅ REDIS_URL is set: {redis_url[:50]}...")
    else:
        print("❌ REDIS_URL not found in environment")
        print("\n💡 Default Redis URL for local: redis://localhost:6379/0")
        return False
    
    # Try to import and test
    try:
        from app.services.redis_service import redis_service
        
        print("\n🔌 Testing Redis Connection...")
        health = redis_service.health_check()
        
        if health.get("status") == "healthy":
            print(f"✅ Redis is connected and healthy!")
            print(f"   Response time: {health.get('response_time_ms', 'N/A')}ms")
            return True
        else:
            print(f"❌ Redis connection failed: {health.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking Redis: {str(e)}")
        return False

if __name__ == "__main__":
    success = check_redis()
    sys.exit(0 if success else 1)



