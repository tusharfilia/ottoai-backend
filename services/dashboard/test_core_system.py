#!/usr/bin/env python3
"""
Test core system functionality without external dependencies
"""
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.obs.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

def test_database_connection():
    """Test database connection"""
    print("🧪 Testing Database Connection")
    print("=" * 40)
    
    try:
        from app.database import engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            row = result.fetchone()
            
        if row and row[0] == 1:
            print("✅ Database connection successful")
            return True
        else:
            print("❌ Database connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        return False

def test_redis_connection():
    """Test Redis connection"""
    print("\n🧪 Testing Redis Connection")
    print("=" * 40)
    
    try:
        from app.services.redis_service import redis_service
        
        health = redis_service.health_check()
        print(f"Redis health: {health}")
        
        if health.get("status") == "healthy":
            print("✅ Redis connection successful")
            return True
        else:
            print("❌ Redis connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Redis connection failed: {str(e)}")
        return False

def test_missed_call_queue_models():
    """Test missed call queue models"""
    print("\n🧪 Testing Missed Call Queue Models")
    print("=" * 40)
    
    try:
        from app.models.missed_call_queue import MissedCallQueue, MissedCallAttempt, MissedCallSLA
        from app.database import get_db
        
        db = next(get_db())
        
        # Test creating a queue entry
        queue_entry = MissedCallQueue(
            call_id=999999,  # Use a test ID
            customer_phone="+1234567890",
            company_id="test_company",
            sla_deadline="2024-01-01T00:00:00Z",
            escalation_deadline="2024-01-02T00:00:00Z"
        )
        
        print("✅ Missed call queue models imported successfully")
        print("✅ Queue entry creation test passed")
        return True
        
    except Exception as e:
        print(f"❌ Missed call queue models test failed: {str(e)}")
        return False

def test_sms_handlers():
    """Test SMS handler imports"""
    print("\n🧪 Testing SMS Handlers")
    print("=" * 40)
    
    try:
        from app.routes.sms_handler import router as sms_router
        from app.routes.enhanced_callrail import router as callrail_router
        
        print("✅ SMS handler imports successful")
        print("✅ CallRail handler imports successful")
        return True
        
    except Exception as e:
        print(f"❌ SMS handlers test failed: {str(e)}")
        return False

def test_twilio_service():
    """Test Twilio service"""
    print("\n🧪 Testing Twilio Service")
    print("=" * 40)
    
    try:
        from app.services.twilio_service import TwilioService
        
        service = TwilioService()
        print("✅ Twilio service imported successfully")
        print("✅ Twilio service initialization successful")
        return True
        
    except Exception as e:
        print(f"❌ Twilio service test failed: {str(e)}")
        return False

def main():
    """Run core system tests"""
    print("🚀 OttoAI Core System Test Suite")
    print("=" * 50)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Redis Connection", test_redis_connection),
        ("Missed Call Queue Models", test_missed_call_queue_models),
        ("SMS Handlers", test_sms_handlers),
        ("Twilio Service", test_twilio_service)
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
    print(f"\n{'='*50}")
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All core system tests passed!")
        print("✅ Database: Ready")
        print("✅ Redis: Ready") 
        print("✅ Models: Ready")
        print("✅ Handlers: Ready")
        print("✅ Services: Ready")
        print("\n🚀 System is ready for external service configuration!")
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed. Please check the logs above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)















