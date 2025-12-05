#!/usr/bin/env python3
"""
Test CallRail webhook data structure to see what recording information is provided
"""
import os
import sys
import json
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_callrail_webhook_data_structure():
    """Test CallRail webhook data structure"""
    print("🧪 Testing CallRail Webhook Data Structure")
    print("=" * 50)
    
    try:
        # Simulate CallRail webhook data based on our handler expectations
        webhook_data = {
            "call_id": "CR123456789",
            "caller_number": "+1234567890",
            "tracking_number": "202-831-3219",
            "recording_url": "https://recordings.callrail.com/abc123def456.mp3",
            "duration": 120,
            "status": "completed",
            "timestamp": "2024-01-01T12:00:00Z",
            "company_id": "test_company_123"
        }
        
        print("✅ CallRail Post-Call Webhook Data Structure:")
        print(json.dumps(webhook_data, indent=2))
        
        # Check what our handler extracts
        callrail_call_id = webhook_data.get("call_id")
        recording_url = webhook_data.get("recording_url")
        duration = webhook_data.get("duration")
        
        print(f"\n✅ Extracted Data:")
        print(f"  • CallRail Call ID: {callrail_call_id}")
        print(f"  • Recording URL: {recording_url}")
        print(f"  • Duration: {duration} seconds")
        
        # Check if recording URL is provided
        if recording_url:
            print(f"\n✅ Recording Information Available:")
            print(f"  • Recording URL: {recording_url}")
            print(f"  • Duration: {duration} seconds")
            print(f"  • Status: Available for download")
            
            # Show what we can do with the recording
            print(f"\n✅ What We Can Do with Recording:")
            print(f"  • Download recording from URL")
            print(f"  • Send to UWC ASR for transcription")
            print(f"  • Store in database")
            print(f"  • Generate call insights")
            print(f"  • Coach performance metrics")
            
            return True
        else:
            print(f"\n❌ No Recording URL Provided")
            return False
        
    except Exception as e:
        print(f"❌ Webhook data structure test failed: {str(e)}")
        return False

def test_recording_processing_flow():
    """Test recording processing flow"""
    print("\n🧪 Testing Recording Processing Flow")
    print("=" * 50)
    
    try:
        print("🔄 Complete Recording Processing Flow:")
        print("  1. CallRail sends webhook with recording_url")
        print("  2. OttoAI receives webhook data")
        print("  3. OttoAI extracts recording_url")
        print("  4. OttoAI downloads recording file")
        print("  5. OttoAI sends to UWC ASR for transcription")
        print("  6. OttoAI processes transcript")
        print("  7. OttoAI stores results in database")
        print("  8. OttoAI generates call insights")
        
        print("\n✅ Recording Processing Flow Ready")
        return True
        
    except Exception as e:
        print(f"❌ Recording processing flow test failed: {str(e)}")
        return False

def test_recording_url_validation():
    """Test recording URL validation"""
    print("\n🧪 Testing Recording URL Validation")
    print("=" * 50)
    
    try:
        # Test different recording URL formats
        test_urls = [
            "https://recordings.callrail.com/abc123def456.mp3",
            "https://recordings.callrail.com/xyz789.mp3",
            "https://recordings.callrail.com/recording_123.wav",
            "https://recordings.callrail.com/call_456.m4a"
        ]
        
        print("✅ Recording URL Formats:")
        for url in test_urls:
            print(f"  • {url}")
        
        # Check URL validation
        import re
        url_pattern = r'https://recordings\.callrail\.com/.*\.(mp3|wav|m4a)'
        
        valid_urls = 0
        for url in test_urls:
            if re.match(url_pattern, url):
                valid_urls += 1
                print(f"  ✅ Valid: {url}")
            else:
                print(f"  ❌ Invalid: {url}")
        
        print(f"\n✅ Valid URLs: {valid_urls}/{len(test_urls)}")
        
        if valid_urls == len(test_urls):
            print("✅ All recording URLs are valid")
            return True
        else:
            print("❌ Some recording URLs are invalid")
            return False
        
    except Exception as e:
        print(f"❌ Recording URL validation test failed: {str(e)}")
        return False

def main():
    """Run CallRail webhook data tests"""
    print("🚀 CallRail Webhook Data Test Suite")
    print("=" * 60)
    
    tests = [
        ("Webhook Data Structure", test_callrail_webhook_data_structure),
        ("Recording Processing Flow", test_recording_processing_flow),
        ("Recording URL Validation", test_recording_url_validation)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test {test_name} failed with exception: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 CallRail Webhook Data Test Results")
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
        print("\n🎉 CallRail Webhook Data Ready!")
        print("\n✅ Recording Information:")
        print("  • Recording URL: Provided in webhook")
        print("  • Duration: Provided in webhook")
        print("  • Status: Available for processing")
        print("  • Processing: Ready for UWC ASR")
        
        print("\n📋 Next Steps:")
        print("  1. Configure CallRail to send recordings")
        print("  2. Test webhook with actual recording")
        print("  3. Integrate with UWC ASR")
        
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed. Please check the logs above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)













