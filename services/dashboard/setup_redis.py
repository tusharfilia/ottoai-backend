#!/usr/bin/env python3
"""
Setup Redis for development
"""
import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

def setup_redis_development():
    """Setup Redis for development"""
    try:
        # Check if Redis is available
        import redis
        
        # Try to connect to local Redis
        redis_url = "redis://localhost:6379"
        client = redis.from_url(redis_url, decode_responses=True)
        
        # Test connection
        client.ping()
        print(f"✓ Redis connection successful: {redis_url}")
        
        # Set environment variable
        os.environ["REDIS_URL"] = redis_url
        print(f"✓ Set REDIS_URL environment variable: {redis_url}")
        
        return True
        
    except ImportError:
        print("✗ Redis package not installed. Installing...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "redis"])
        print("✓ Redis package installed")
        return setup_redis_development()
        
    except redis.ConnectionError:
        print("✗ Redis not running locally. Starting Redis...")
        print("Please install and start Redis:")
        print("  macOS: brew install redis && brew services start redis")
        print("  Ubuntu: sudo apt install redis-server && sudo systemctl start redis")
        print("  Docker: docker run -d -p 6379:6379 redis:alpine")
        return False
        
    except Exception as e:
        print(f"✗ Redis setup failed: {str(e)}")
        return False

def setup_redis_cloud():
    """Setup Redis cloud service (Upstash)"""
    try:
        # For development, we can use a free Upstash Redis instance
        print("Setting up Redis cloud service...")
        print("Please sign up for a free Upstash Redis instance:")
        print("1. Go to https://upstash.com/")
        print("2. Create a free Redis database")
        print("3. Copy the Redis URL")
        print("4. Set the REDIS_URL environment variable")
        
        redis_url = input("Enter your Redis URL (or press Enter to skip): ").strip()
        
        if redis_url:
            os.environ["REDIS_URL"] = redis_url
            print(f"✓ Set REDIS_URL environment variable: {redis_url}")
            return True
        else:
            print("Skipping Redis cloud setup")
            return False
            
    except Exception as e:
        print(f"✗ Redis cloud setup failed: {str(e)}")
        return False

def main():
    """Main setup function"""
    print("Redis Setup for OttoAI Development")
    print("=" * 40)
    
    # Try local Redis first
    if setup_redis_development():
        print("\n✓ Redis development setup completed")
        return True
    
    # Fallback to cloud Redis
    print("\nTrying Redis cloud setup...")
    if setup_redis_cloud():
        print("\n✓ Redis cloud setup completed")
        return True
    
    print("\n✗ Redis setup failed")
    print("\nFor development without Redis, the system will use in-memory fallbacks")
    print("This is fine for testing but not recommended for production")
    
    return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)















