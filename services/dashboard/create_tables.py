#!/usr/bin/env python3
"""
Create database tables for missed call queue system
"""
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import init_db, engine
from app.models.missed_call_queue import MissedCallQueue, MissedCallAttempt, MissedCallSLA
from app.obs.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

def create_missed_call_tables():
    """Create missed call queue tables using SQLAlchemy"""
    try:
        logger.info("Creating missed call queue tables...")
        
        # Create all tables
        MissedCallQueue.__table__.create(engine, checkfirst=True)
        MissedCallAttempt.__table__.create(engine, checkfirst=True)
        MissedCallSLA.__table__.create(engine, checkfirst=True)
        
        logger.info("Missed call queue tables created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        return False

def verify_tables():
    """Verify tables were created correctly"""
    try:
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        required_tables = ['missed_call_queue', 'missed_call_attempts', 'missed_call_sla']
        
        for table in required_tables:
            if table in tables:
                logger.info(f"✓ Table {table} exists")
            else:
                logger.error(f"✗ Table {table} missing")
                return False
        
        logger.info("All required tables exist")
        return True
        
    except Exception as e:
        logger.error(f"Error verifying tables: {str(e)}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Create missed call queue tables')
    parser.add_argument('--verify', action='store_true', help='Verify tables exist')
    
    args = parser.parse_args()
    
    if args.verify:
        success = verify_tables()
    else:
        success = create_missed_call_tables()
        if success:
            verify_tables()
    
    if not success:
        sys.exit(1)









