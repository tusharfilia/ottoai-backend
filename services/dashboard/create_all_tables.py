#!/usr/bin/env python3
"""
Create all database tables for OttoAI system
"""
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import init_db, engine
from app.obs.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

def create_all_tables():
    """Create all tables using SQLAlchemy"""
    try:
        logger.info("Creating all database tables...")
        
        # Initialize database - this should create all tables
        init_db()
        
        logger.info("All tables created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        return False

def verify_tables():
    """Verify all required tables exist"""
    try:
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        # Core tables that should exist
        required_tables = [
            'companies',
            'users', 
            'calls',
            'missed_call_queue',
            'missed_call_attempts',
            'missed_call_sla',
            'sales_reps',
            'sales_managers',
            'scheduled_calls',
            'services'
        ]
        
        missing_tables = []
        for table in required_tables:
            if table in tables:
                logger.info(f"✓ Table {table} exists")
            else:
                logger.error(f"✗ Table {table} missing")
                missing_tables.append(table)
        
        if missing_tables:
            logger.error(f"Missing tables: {missing_tables}")
            return False
        
        logger.info("All required tables exist")
        return True
        
    except Exception as e:
        logger.error(f"Error verifying tables: {str(e)}")
        return False

def show_table_info():
    """Show information about all tables"""
    try:
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        logger.info(f"Found {len(tables)} tables:")
        for table in sorted(tables):
            columns = inspector.get_columns(table)
            logger.info(f"  {table}: {len(columns)} columns")
        
        return True
        
    except Exception as e:
        logger.error(f"Error showing table info: {str(e)}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Create all database tables')
    parser.add_argument('--verify', action='store_true', help='Verify tables exist')
    parser.add_argument('--info', action='store_true', help='Show table information')
    
    args = parser.parse_args()
    
    if args.info:
        success = show_table_info()
    elif args.verify:
        success = verify_tables()
    else:
        success = create_all_tables()
        if success:
            verify_tables()
    
    if not success:
        sys.exit(1)















