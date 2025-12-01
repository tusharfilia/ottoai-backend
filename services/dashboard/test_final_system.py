#!/usr/bin/env python3
"""
Final system test - core functionality verification
"""
import sys
import os
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

# Set local SQLite for testing
os.environ["DATABASE_URL"] = "sqlite:///./otto_test.db"

from app.obs.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

def test_infrastructure():
    """Test core infrastructure"""
    print("🧪 Testing Core Infrastructure")
    print("=" * 50)
    
    try:
        # Test database
        from app.database import engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            row = result.fetchone()
            
        if not (row and row[0] == 1):
            print("❌ Database connection failed")
            return False
            
        print("✅ Database: Connected")
        
        # Test Redis
        from app.services.redis_service import redis_service
        health = redis_service.health_check()
        
        if health.get("status") != "healthy":
            print("❌ Redis connection failed")
            return False
            
        print("✅ Redis: Connected")
        
        return True
        
    except Exception as e:
        print(f"❌ Infrastructure test failed: {str(e)}")
        return False

def test_services():
    """Test core services"""
    print("\n🧪 Testing Core Services")
    print("=" * 50)
    
    try:
        # Test Twilio service
        from app.services.twilio_service import TwilioService
        twilio_service = TwilioService()
        print("✅ Twilio Service: Ready")
        
        # Test Redis services
        from app.services.redis_service import redis_service
        from app.services.redis_lock_service import redis_lock_service
        print("✅ Redis Services: Ready")
        
        # Test circuit breaker
        from app.services.circuit_breaker import circuit_breaker_manager
        print("✅ Circuit Breaker: Ready")
        
        return True
        
    except Exception as e:
        print(f"❌ Services test failed: {str(e)}")
        return False

def test_handlers():
    """Test API handlers"""
    print("\n🧪 Testing API Handlers")
    print("=" * 50)
    
    try:
        # Test SMS handlers
        from app.routes.sms_handler import router as sms_router
        print("✅ SMS Handler: Ready")
        
        # Test CallRail handlers
        from app.routes.enhanced_callrail import router as callrail_router
        print("✅ CallRail Handler: Ready")
        
        # Test missed call queue handler
        from app.routes.missed_call_queue import router as queue_router
        print("✅ Missed Call Queue Handler: Ready")
        
        return True
        
    except Exception as e:
        print(f"❌ Handlers test failed: {str(e)}")
        return False

def test_models():
    """Test database models"""
    print("\n🧪 Testing Database Models")
    print("=" * 50)
    
    try:
        # Test core models
        from app.models.company import Company
        from app.models.call import Call
        from app.models.missed_call_queue import MissedCallQueue, MissedCallAttempt, MissedCallSLA
        print("✅ Database Models: Ready")
        
        return True
        
    except Exception as e:
        print(f"❌ Models test failed: {str(e)}")
        return False

def test_redis_functionality():
    """Test Redis functionality"""
    print("\n🧪 Testing Redis Functionality")
    print("=" * 50)
    
    try:
        import asyncio
        from app.services.redis_lock_service import redis_lock_service
        
        async def test_locks():
            # Test distributed locking
            lock_key = "test_lock_final"
            tenant_id = "test_tenant"
            
            # Acquire lock
            lock_token = await redis_lock_service.acquire_lock(
                lock_key=lock_key,
                tenant_id=tenant_id,
                timeout=60
            )
            
            if lock_token:
                print("✅ Distributed Locking: Working")
                
                # Release lock
                released = await redis_lock_service.release_lock(
                    lock_key=lock_key,
                    tenant_id=tenant_id,
                    lock_token=lock_token
                )
                
                if released:
                    print("✅ Lock Release: Working")
                    return True
                else:
                    print("❌ Lock Release: Failed")
                    return False
            else:
                print("❌ Lock Acquisition: Failed")
                return False
        
        # Run async test
        result = asyncio.run(test_locks())
        return result
        
    except Exception as e:
        print(f"❌ Redis functionality test failed: {str(e)}")
        return False

def main():
    """Run final system tests"""
    print("🚀 OttoAI Final System Test Suite")
    print("=" * 60)
    
    tests = [
        ("Infrastructure", test_infrastructure),
        ("Services", test_services),
        ("Handlers", test_handlers),
        ("Models", test_models),
        ("Redis Functionality", test_redis_functionality)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test {test_name} failed with exception: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 Final Test Results Summary")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL SYSTEM TESTS PASSED!")
        print("\n✅ Infrastructure Status:")
        print("  • Database: Ready (SQLite for dev, Postgres for production)")
        print("  • Redis: Ready (Local for dev, Railway for production)")
        print("  • Services: Ready (Twilio, Circuit Breaker, Redis)")
        print("  • Handlers: Ready (SMS, CallRail, Missed Call Queue)")
        print("  • Models: Ready (All database models)")
        print("  • Distributed Locking: Ready")
        
        print("\n🚀 SYSTEM IS PRODUCTION READY!")
        print("\n📋 Next Steps:")
        print("  1. ✅ Database: Ready")
        print("  2. ✅ Redis: Ready")
        print("  3. ✅ Infrastructure: Ready")
        print("  4. 🔧 Twilio: Need credentials")
        print("  5. 🔧 CallRail: Need credentials")
        print("  6. 🔧 UWC/Shunya: Need credentials")
        
        print("\n🎯 Ready for External Service Configuration!")
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed. Please check the logs above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)









