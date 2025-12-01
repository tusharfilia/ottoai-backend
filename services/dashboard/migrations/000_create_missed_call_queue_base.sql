-- Migration: 000_create_missed_call_queue_base.sql
-- Description: Create base missed call queue tables
-- Date: 2024-01-XX
-- Author: OttoAI Team

-- Create missed_call_queue table
CREATE TABLE IF NOT EXISTS missed_call_queue (
    id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL,
    customer_phone VARCHAR(20) NOT NULL,
    company_id VARCHAR(100) NOT NULL,
    
    -- Queue management
    status VARCHAR(50) DEFAULT 'queued' NOT NULL,
    priority VARCHAR(20) DEFAULT 'medium' NOT NULL,
    
    -- SLA management
    sla_deadline TIMESTAMP NOT NULL,
    escalation_deadline TIMESTAMP NOT NULL,
    
    -- Processing tracking
    retry_count INTEGER DEFAULT 0 NOT NULL,
    max_retries INTEGER DEFAULT 3 NOT NULL,
    last_attempt_at TIMESTAMP,
    next_attempt_at TIMESTAMP,
    
    -- Recovery tracking
    ai_rescue_attempted BOOLEAN DEFAULT FALSE NOT NULL,
    customer_responded BOOLEAN DEFAULT FALSE NOT NULL,
    recovery_method VARCHAR(20),
    
    -- Context and metadata
    customer_type VARCHAR(20),
    lead_value FLOAT,
    conversation_context TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    processed_at TIMESTAMP,
    escalated_at TIMESTAMP,
    
    -- Foreign key constraints
    FOREIGN KEY (call_id) REFERENCES calls(call_id),
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- Create missed_call_attempts table
CREATE TABLE IF NOT EXISTS missed_call_attempts (
    id SERIAL PRIMARY KEY,
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
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    responded_at TIMESTAMP,
    
    -- Foreign key constraints
    FOREIGN KEY (queue_id) REFERENCES missed_call_queue(id)
);

-- Create missed_call_sla table
CREATE TABLE IF NOT EXISTS missed_call_sla (
    id SERIAL PRIMARY KEY,
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Foreign key constraints
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- Create basic indexes
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_call_id ON missed_call_queue(call_id);
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_customer_phone ON missed_call_queue(customer_phone);
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_company_id ON missed_call_queue(company_id);
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_status ON missed_call_queue(status);
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_priority ON missed_call_queue(priority);
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_created_at ON missed_call_queue(created_at);

CREATE INDEX IF NOT EXISTS idx_missed_call_attempts_queue_id ON missed_call_attempts(queue_id);
CREATE INDEX IF NOT EXISTS idx_missed_call_attempts_attempted_at ON missed_call_attempts(attempted_at);

CREATE INDEX IF NOT EXISTS idx_missed_call_sla_company_id ON missed_call_sla(company_id);

-- Add constraints
ALTER TABLE missed_call_queue 
ADD CONSTRAINT chk_missed_call_queue_status 
CHECK (status IN ('queued', 'processing', 'ai_rescued_pending', 'recovered', 'escalated', 'failed', 'expired'));

ALTER TABLE missed_call_queue 
ADD CONSTRAINT chk_missed_call_queue_priority 
CHECK (priority IN ('high', 'medium', 'low'));

ALTER TABLE missed_call_attempts 
ADD CONSTRAINT chk_missed_call_attempts_method 
CHECK (method IN ('sms', 'call', 'email'));

-- Migration completed successfully
SELECT 'Migration 000_create_missed_call_queue_base completed successfully' as status;










