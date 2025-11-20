#!/usr/bin/env python3
"""
Simple system test using local SQLite
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

def test_database_connection():
    """Test database connection with local SQLite"""
    print("🧪 Testing Database Connection (Local SQLite)")
    print("=" * 50)
    
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
    print("=" * 50)
    
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

def test_missed_call_queue_system():
    """Test missed call queue system"""
    print("\n🧪 Testing Missed Call Queue System")
    print("=" * 50)
    
    try:
        from app.services.missed_call_queue_service import MissedCallQueueService
        from app.database import SessionLocal
        from app.models import call, company
        
        # Create test data
        db = SessionLocal()
        
        # Create test company
        test_company = company.Company(
            id="test_company_123",
            name="Test Company",
            phone_number="+1234567890",
            address="123 Test St"
        )
        
        # Create test call
        test_call = call.Call(
            phone_number="+1987654321",
            company_id="test_company_123",
            missed_call=True,
            status="missed"
        )
        
        db.add(test_company)
        db.add(test_call)
        db.commit()
        
        print("✅ Test data created successfully")
        
        # Test missed call queue service
        queue_service = MissedCallQueueService()
        
        # Test adding missed call to queue
        queue_entry = queue_service.add_missed_call_to_queue(
            call_id=test_call.call_id,
            customer_phone=test_call.phone_number,
            company_id=test_call.company_id,
            db=db
        )
        
        print(f"✅ Missed call added to queue: {queue_entry.id}")
        
        # Clean up
        db.delete(test_call)
        db.delete(test_company)
        db.commit()
        db.close()
        
        print("✅ Test data cleaned up")
        print("✅ Missed call queue system test passed")
        return True
        
    except Exception as e:
        print(f"❌ Missed call queue system test failed: {str(e)}")
        return False

def test_twilio_service():
    """Test Twilio service"""
    print("\n🧪 Testing Twilio Service")
    print("=" * 50)
    
    try:
        from app.services.twilio_service import TwilioService
        
        service = TwilioService()
        print("✅ Twilio service imported successfully")
        print("✅ Twilio service initialization successful")
        
        # Test phone number normalization
        normalized = service._normalize_phone_number("1234567890")
        print(f"✅ Phone number normalization: {normalized}")
        
        return True
        
    except Exception as e:
        print(f"❌ Twilio service test failed: {str(e)}")
        return False

def test_sms_handlers():
    """Test SMS handlers"""
    print("\n🧪 Testing SMS Handlers")
    print("=" * 50)
    
    try:
        from app.routes.sms_handler import router as sms_router
        from app.routes.enhanced_callrail import router as callrail_router
        
        print("✅ SMS handler imports successful")
        print("✅ CallRail handler imports successful")
        print("✅ All handlers ready")
        
        return True
        
    except Exception as e:
        print(f"❌ SMS handlers test failed: {str(e)}")
        return False

def main():
    """Run system tests"""
    print("🚀 OttoAI System Test Suite")
    print("=" * 60)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Redis Connection", test_redis_connection),
        ("Missed Call Queue System", test_missed_call_queue_system),
        ("Twilio Service", test_twilio_service),
        ("SMS Handlers", test_sms_handlers)
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
    print("📊 Test Results Summary")
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
        print("\n🎉 All system tests passed!")
        print("\n✅ Infrastructure Status:")
        print("  • Database: Ready (SQLite for dev, Postgres for production)")
        print("  • Redis: Ready (Local for dev, Railway for production)")
        print("  • Missed Call Queue: Ready")
        print("  • Twilio Service: Ready")
        print("  • SMS Handlers: Ready")
        print("\n🚀 System is ready for external service configuration!")
        print("\n📋 Next Steps:")
        print("  1. Set up Twilio account and get credentials")
        print("  2. Set up CallRail account and get credentials")
        print("  3. Configure webhook endpoints")
        print("  4. Test end-to-end flow")
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed. Please check the logs above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)







