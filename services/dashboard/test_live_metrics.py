#!/usr/bin/env python3
"""
Test script for Live Metrics System
Tests the live metrics service and WebSocket infrastructure
"""
import asyncio
import json
import time
from datetime import datetime
from app.services.live_metrics_service import live_metrics_service
from app.realtime.bus import emit
from app.database import SessionLocal

async def test_live_metrics_service():
    """Test the live metrics service functionality."""
    print("🧪 Testing Live Metrics Service...")
    
    try:
        # Start the service
        await live_metrics_service.start()
        print("✅ Live metrics service started")
        
        # Wait a bit for metrics to be calculated
        await asyncio.sleep(2)
        
        # Test getting metrics for a specific tenant
        test_tenant_id = "test_tenant_123"
        metrics = await live_metrics_service.get_tenant_metrics(test_tenant_id)
        
        print(f"📊 Metrics for tenant {test_tenant_id}:")
        print(json.dumps(metrics, indent=2, default=str))
        
        # Test event emission
        print("\n📡 Testing event emission...")
        success = emit(
            event_name="metrics.live_updated",
            payload={
                "revenue": {"today": 1500.0, "this_week": 8500.0},
                "calls": {"active_calls": 3, "calls_today": 25},
                "timestamp": datetime.utcnow().isoformat()
            },
            tenant_id=test_tenant_id,
            severity="info"
        )
        
        if success:
            print("✅ Event emitted successfully")
        else:
            print("❌ Failed to emit event")
        
        # Stop the service
        await live_metrics_service.stop()
        print("✅ Live metrics service stopped")
        
    except Exception as e:
        print(f"❌ Error testing live metrics service: {e}")
        import traceback
        traceback.print_exc()

async def test_websocket_connection():
    """Test WebSocket connection (simulation)."""
    print("\n🌐 Testing WebSocket Infrastructure...")
    
    try:
        # Test event bus functionality
        print("📡 Testing event bus...")
        
        # Emit a test event
        success = emit(
            event_name="test.live_metrics",
            payload={
                "message": "Test live metrics event",
                "timestamp": datetime.utcnow().isoformat(),
                "test": True
            },
            tenant_id="test_tenant_123",
            user_id="test_user_456",
            severity="info"
        )
        
        if success:
            print("✅ Event bus working correctly")
        else:
            print("❌ Event bus failed")
        
        # Test channel validation
        from app.realtime.bus import event_bus
        
        # Test valid channels
        valid_channels = [
            "tenant:test_tenant_123:events",
            "user:test_user_456:tasks",
            "lead:test_lead_789:timeline"
        ]
        
        for channel in valid_channels:
            is_valid = event_bus.is_valid_channel_format(channel)
            print(f"Channel {channel}: {'✅ Valid' if is_valid else '❌ Invalid'}")
        
        # Test invalid channels
        invalid_channels = [
            "invalid:channel",
            "tenant:events",  # Missing tenant ID
            "user:tasks"       # Missing user ID
        ]
        
        for channel in invalid_channels:
            is_valid = event_bus.is_valid_channel_format(channel)
            print(f"Channel {channel}: {'❌ Should be invalid' if is_valid else '✅ Correctly invalid'}")
        
    except Exception as e:
        print(f"❌ Error testing WebSocket infrastructure: {e}")
        import traceback
        traceback.print_exc()

async def test_database_queries():
    """Test database queries for metrics calculation."""
    print("\n🗄️ Testing Database Queries...")
    
    try:
        db = SessionLocal()
        
        # Test basic database connection
        result = db.execute("SELECT 1 as test").fetchone()
        if result and result[0] == 1:
            print("✅ Database connection working")
        else:
            print("❌ Database connection failed")
        
        # Test companies table
        try:
            companies = db.execute("SELECT COUNT(*) FROM companies").scalar()
            print(f"✅ Companies table accessible: {companies} companies")
        except Exception as e:
            print(f"⚠️ Companies table query failed: {e}")
        
        # Test calls table
        try:
            calls = db.execute("SELECT COUNT(*) FROM calls").scalar()
            print(f"✅ Calls table accessible: {calls} calls")
        except Exception as e:
            print(f"⚠️ Calls table query failed: {e}")
        
        db.close()
        
    except Exception as e:
        print(f"❌ Error testing database: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Run all tests."""
    print("🚀 Starting Live Metrics System Tests")
    print("=" * 50)
    
    # Test database first
    await test_database_queries()
    
    # Test WebSocket infrastructure
    await test_websocket_connection()
    
    # Test live metrics service
    await test_live_metrics_service()
    
    print("\n" + "=" * 50)
    print("🎉 Live Metrics System Tests Complete!")

if __name__ == "__main__":
    asyncio.run(main())







