#!/usr/bin/env python3
"""
Create missed call queue tables without foreign key constraints
"""
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import engine
from sqlalchemy import text
from app.obs.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger(__name__)

def create_missed_call_tables():
    """Create missed call queue tables without foreign keys"""
    try:
        logger.info("Creating missed call queue tables...")
        
        # Create missed_call_queue table
        create_queue_table = """
        CREATE TABLE IF NOT EXISTS missed_call_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id INTEGER NOT NULL,
            customer_phone VARCHAR(20) NOT NULL,
            company_id VARCHAR(100) NOT NULL,
            
            -- Queue management
            status VARCHAR(50) DEFAULT 'queued' NOT NULL,
            priority VARCHAR(20) DEFAULT 'medium' NOT NULL,
            
            -- SLA management
            sla_deadline DATETIME NOT NULL,
            escalation_deadline DATETIME NOT NULL,
            
            -- Processing tracking
            retry_count INTEGER DEFAULT 0 NOT NULL,
            max_retries INTEGER DEFAULT 3 NOT NULL,
            last_attempt_at DATETIME,
            next_attempt_at DATETIME,
            
            -- Recovery tracking
            ai_rescue_attempted BOOLEAN DEFAULT FALSE NOT NULL,
            customer_responded BOOLEAN DEFAULT FALSE NOT NULL,
            recovery_method VARCHAR(20),
            
            -- Context and metadata
            customer_type VARCHAR(20),
            lead_value FLOAT,
            conversation_context TEXT,
            
            -- Compliance tracking
            consent_status VARCHAR(50) DEFAULT 'pending' NOT NULL,
            opt_out_reason TEXT,
            consent_granted_at DATETIME,
            consent_withdrawn_at DATETIME,
            
            -- Data privacy
            phone_number_encrypted TEXT,
            data_retention_expires_at DATETIME,
            
            -- Business hours and timezone
            business_hours_override BOOLEAN DEFAULT FALSE NOT NULL,
            customer_timezone VARCHAR(50),
            preferred_contact_time VARCHAR(20),
            
            -- Timestamps
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            processed_at DATETIME,
            escalated_at DATETIME
        );
        """
        
        # Create missed_call_attempts table
        create_attempts_table = """
        CREATE TABLE IF NOT EXISTS missed_call_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            queue_id INTEGER NOT NULL,
            
            -- Attempt details
            attempt_number INTEGER NOT NULL,
            method VARCHAR(20) NOT NULL,
            message_sent TEXT,
            response_received TEXT,
            
            -- AI processing
            ai_intent_analysis TEXT,
            ai_response_generated TEXT,
            confidence_score FLOAT,
            
            -- Results
            success BOOLEAN DEFAULT FALSE NOT NULL,
            customer_engaged BOOLEAN DEFAULT FALSE NOT NULL,
            escalation_triggered BOOLEAN DEFAULT FALSE NOT NULL,
            
            -- Timestamps
            attempted_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            responded_at DATETIME
        );
        """
        
        # Create missed_call_sla table
        create_sla_table = """
        CREATE TABLE IF NOT EXISTS missed_call_sla (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id VARCHAR(100) NOT NULL UNIQUE,
            
            -- SLA settings
            response_time_hours INTEGER DEFAULT 2 NOT NULL,
            escalation_time_hours INTEGER DEFAULT 48 NOT NULL,
            max_retries INTEGER DEFAULT 3 NOT NULL,
            
            -- Business hours
            business_hours_start VARCHAR(10) DEFAULT '09:00' NOT NULL,
            business_hours_end VARCHAR(10) DEFAULT '17:00' NOT NULL,
            business_days VARCHAR(20) DEFAULT '1,2,3,4,5' NOT NULL,
            
            -- AI settings
            ai_enabled BOOLEAN DEFAULT TRUE NOT NULL,
            ai_confidence_threshold FLOAT DEFAULT 0.7 NOT NULL,
            escalation_ai_failure BOOLEAN DEFAULT TRUE NOT NULL,
            
            -- Timestamps
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
        );
        """
        
        # Create indexes
        create_indexes = """
        CREATE INDEX IF NOT EXISTS idx_missed_call_queue_call_id ON missed_call_queue(call_id);
        CREATE INDEX IF NOT EXISTS idx_missed_call_queue_customer_phone ON missed_call_queue(customer_phone);
        CREATE INDEX IF NOT EXISTS idx_missed_call_queue_company_id ON missed_call_queue(company_id);
        CREATE INDEX IF NOT EXISTS idx_missed_call_queue_status ON missed_call_queue(status);
        CREATE INDEX IF NOT EXISTS idx_missed_call_queue_priority ON missed_call_queue(priority);
        CREATE INDEX IF NOT EXISTS idx_missed_call_queue_created_at ON missed_call_queue(created_at);
        CREATE INDEX IF NOT EXISTS idx_missed_call_queue_sla_deadline ON missed_call_queue(sla_deadline);
        CREATE INDEX IF NOT EXISTS idx_missed_call_queue_next_attempt ON missed_call_queue(next_attempt_at);
        
        CREATE INDEX IF NOT EXISTS idx_missed_call_attempts_queue_id ON missed_call_attempts(queue_id);
        CREATE INDEX IF NOT EXISTS idx_missed_call_attempts_attempted_at ON missed_call_attempts(attempted_at);
        
        CREATE INDEX IF NOT EXISTS idx_missed_call_sla_company_id ON missed_call_sla(company_id);
        """
        
        with engine.connect() as conn:
            # Create tables
            conn.execute(text(create_queue_table))
            logger.info("✓ missed_call_queue table created")
            
            conn.execute(text(create_attempts_table))
            logger.info("✓ missed_call_attempts table created")
            
            conn.execute(text(create_sla_table))
            logger.info("✓ missed_call_sla table created")
            
            # Create indexes
            for statement in create_indexes.split(';'):
                if statement.strip():
                    conn.execute(text(statement))
            
            conn.commit()
            logger.info("✓ All indexes created")
        
        logger.info("All missed call queue tables created successfully")
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
                columns = inspector.get_columns(table)
                logger.info(f"✓ Table {table} exists with {len(columns)} columns")
            else:
                logger.error(f"✗ Table {table} missing")
                return False
        
        logger.info("All required tables exist")
        return True
        
    except Exception as e:
        logger.error(f"Error verifying tables: {str(e)}")
        return False

if __name__ == "__main__":
    success = create_missed_call_tables()
    if success:
        verify_tables()
    
    if not success:
        sys.exit(1)







