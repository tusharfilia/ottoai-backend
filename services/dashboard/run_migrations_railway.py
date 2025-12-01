#!/usr/bin/env python3
"""
Run Alembic migrations on Railway production database.
This script connects directly using DATABASE_URL and runs pending migrations.
"""

import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

def run_migrations():
    """Run Alembic migrations on Railway database."""
    
    # Get DATABASE_URL from environment or prompt
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ Error: DATABASE_URL environment variable is not set.")
        print()
        print("To run migrations on Railway:")
        print("1. Get your Railway DATABASE_URL from Railway dashboard")
        print("2. Run: DATABASE_URL='your_railway_db_url' python3 run_migrations_railway.py")
        print()
        print("Or set it in your shell:")
        print("   export DATABASE_URL='your_railway_db_url'")
        print("   python3 run_migrations_railway.py")
        return False
    
    # Fix postgres:// to postgresql:// if needed
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        os.environ["DATABASE_URL"] = database_url
    
    print("=" * 60)
    print("RUNNING RAILWAY DATABASE MIGRATIONS")
    print("=" * 60)
    print()
    print(f"Database: {database_url.split('@')[1] if '@' in database_url else 'hidden'}")
    print()
    
    # Set DATABASE_URL for Alembic
    os.environ["DATABASE_URL"] = database_url
    
    # Import and run Alembic
    try:
        from alembic.config import Config
        from alembic import command
        
        # Get Alembic config
        alembic_cfg = Config("alembic.ini")
        
        # Check current revision
        print("📋 Checking current database revision...")
        try:
            from alembic.runtime.migration import MigrationContext
            from sqlalchemy import create_engine
            
            engine = create_engine(database_url)
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                current_rev = context.get_current_revision()
                print(f"   Current revision: {current_rev or 'None (fresh database)'}")
        except Exception as e:
            print(f"   ⚠️  Could not check current revision: {e}")
        
        print()
        print("🚀 Running migrations...")
        print()
        
        # Run migrations
        command.upgrade(alembic_cfg, "head")
        
        print()
        print("✅ Migrations completed successfully!")
        print()
        print("📋 Verifying contact_cards table exists...")
        
        # Verify contact_cards table was created
        from sqlalchemy import create_engine, inspect
        
        engine = create_engine(database_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if "contact_cards" in tables:
            print("   ✅ contact_cards table exists")
        else:
            print("   ❌ contact_cards table NOT found!")
            print("   This is unexpected. Please check the migration logs above.")
        
        if "leads" in tables:
            print("   ✅ leads table exists")
        else:
            print("   ⚠️  leads table NOT found")
        
        if "appointments" in tables:
            print("   ✅ appointments table exists")
        else:
            print("   ⚠️  appointments table NOT found")
        
        print()
        print("=" * 60)
        print("✅ Migration complete! Your missed call webhook should work now.")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print()
        print("❌ Error running migrations:")
        print(f"   {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)


