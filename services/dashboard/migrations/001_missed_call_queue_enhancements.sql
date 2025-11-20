-- Migration: 001_missed_call_queue_enhancements.sql
-- Description: Add P0 critical fields for missed call queue system
-- Date: 2024-01-XX
-- Author: OttoAI Team

-- Add compliance tracking fields
ALTER TABLE missed_call_queue 
ADD COLUMN IF NOT EXISTS consent_status VARCHAR(50) DEFAULT 'pending' NOT NULL,
ADD COLUMN IF NOT EXISTS opt_out_reason TEXT,
ADD COLUMN IF NOT EXISTS consent_granted_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS consent_withdrawn_at TIMESTAMP;

-- Add data privacy fields
ALTER TABLE missed_call_queue 
ADD COLUMN IF NOT EXISTS phone_number_encrypted TEXT,
ADD COLUMN IF NOT EXISTS data_retention_expires_at TIMESTAMP;

-- Add business hours and timezone fields
ALTER TABLE missed_call_queue 
ADD COLUMN IF NOT EXISTS business_hours_override BOOLEAN DEFAULT FALSE NOT NULL,
ADD COLUMN IF NOT EXISTS customer_timezone VARCHAR(50),
ADD COLUMN IF NOT EXISTS preferred_contact_time VARCHAR(20);

-- Add performance indexes
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_status ON missed_call_queue(status);
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_phone ON missed_call_queue(customer_phone);
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_company ON missed_call_queue(company_id);
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_consent ON missed_call_queue(consent_status);
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_created_at ON missed_call_queue(created_at);
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_sla_deadline ON missed_call_queue(sla_deadline);
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_next_attempt ON missed_call_queue(next_attempt_at);

-- Add composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_company_status ON missed_call_queue(company_id, status);
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_phone_company ON missed_call_queue(customer_phone, company_id);
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_priority_created ON missed_call_queue(priority, created_at);

-- Add constraints for data integrity
ALTER TABLE missed_call_queue 
ADD CONSTRAINT chk_consent_status CHECK (consent_status IN ('pending', 'granted', 'denied', 'withdrawn')),
ADD CONSTRAINT chk_preferred_contact_time CHECK (preferred_contact_time IN ('morning', 'afternoon', 'evening', 'anytime'));

-- Add comments for documentation
COMMENT ON COLUMN missed_call_queue.consent_status IS 'Consent status for SMS communications (pending/granted/denied/withdrawn)';
COMMENT ON COLUMN missed_call_queue.opt_out_reason IS 'Reason provided by customer for opting out';
COMMENT ON COLUMN missed_call_queue.phone_number_encrypted IS 'Encrypted phone number for data privacy';
COMMENT ON COLUMN missed_call_queue.data_retention_expires_at IS 'When this record should be deleted for GDPR compliance';
COMMENT ON COLUMN missed_call_queue.business_hours_override IS 'Override business hours restrictions for urgent cases';
COMMENT ON COLUMN missed_call_queue.customer_timezone IS 'Customer timezone for proper scheduling';
COMMENT ON COLUMN missed_call_queue.preferred_contact_time IS 'Customer preferred contact time of day';

-- Update existing records with default values
UPDATE missed_call_queue 
SET consent_status = 'pending',
    data_retention_expires_at = created_at + INTERVAL '2 years'
WHERE consent_status IS NULL;

-- Add audit trail for compliance
CREATE TABLE IF NOT EXISTS missed_call_queue_audit (
    id SERIAL PRIMARY KEY,
    queue_id INTEGER NOT NULL,
    action VARCHAR(50) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    changed_by VARCHAR(100),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tenant_id VARCHAR(100) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_missed_call_queue_audit_queue_id ON missed_call_queue_audit(queue_id);
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_audit_tenant_id ON missed_call_queue_audit(tenant_id);
CREATE INDEX IF NOT EXISTS idx_missed_call_queue_audit_changed_at ON missed_call_queue_audit(changed_at);

-- Create function for audit trail
CREATE OR REPLACE FUNCTION missed_call_queue_audit_trigger()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO missed_call_queue_audit (queue_id, action, new_values, tenant_id)
        VALUES (NEW.id, 'INSERT', row_to_json(NEW), NEW.company_id);
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO missed_call_queue_audit (queue_id, action, old_values, new_values, tenant_id)
        VALUES (NEW.id, 'UPDATE', row_to_json(OLD), row_to_json(NEW), NEW.company_id);
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO missed_call_queue_audit (queue_id, action, old_values, tenant_id)
        VALUES (OLD.id, 'DELETE', row_to_json(OLD), OLD.company_id);
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create audit trigger
DROP TRIGGER IF EXISTS missed_call_queue_audit_trigger ON missed_call_queue;
CREATE TRIGGER missed_call_queue_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON missed_call_queue
    FOR EACH ROW EXECUTE FUNCTION missed_call_queue_audit_trigger();

-- Add dead letter queue table for failed SMS
CREATE TABLE IF NOT EXISTS sms_dead_letter_queue (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(100) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    message_body TEXT NOT NULL,
    failure_reason TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_attempt_at TIMESTAMP,
    next_retry_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'failed', 'resolved'))
);

CREATE INDEX IF NOT EXISTS idx_sms_dlq_tenant_id ON sms_dead_letter_queue(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sms_dlq_status ON sms_dead_letter_queue(status);
CREATE INDEX IF NOT EXISTS idx_sms_dlq_next_retry ON sms_dead_letter_queue(next_retry_at);

-- Add circuit breaker state table
CREATE TABLE IF NOT EXISTS circuit_breaker_state (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    tenant_id VARCHAR(100) NOT NULL,
    state VARCHAR(20) NOT NULL CHECK (state IN ('closed', 'open', 'half_open')),
    failure_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    last_failure_at TIMESTAMP,
    opened_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(service_name, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_circuit_breaker_service_tenant ON circuit_breaker_state(service_name, tenant_id);
CREATE INDEX IF NOT EXISTS idx_circuit_breaker_state ON circuit_breaker_state(state);

-- Add rate limiting tables
CREATE TABLE IF NOT EXISTS rate_limit_tracking (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(100) NOT NULL,
    client_ip VARCHAR(45) NOT NULL,
    endpoint VARCHAR(200) NOT NULL,
    request_count INTEGER DEFAULT 1,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_tenant_ip ON rate_limit_tracking(tenant_id, client_ip);
CREATE INDEX IF NOT EXISTS idx_rate_limit_window ON rate_limit_tracking(window_start, window_end);

-- Add abuse detection table
CREATE TABLE IF NOT EXISTS abuse_detection (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(100) NOT NULL,
    client_ip VARCHAR(45) NOT NULL,
    request_count INTEGER NOT NULL,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    blocked_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_abuse_tenant_ip ON abuse_detection(tenant_id, client_ip);
CREATE INDEX IF NOT EXISTS idx_abuse_blocked_until ON abuse_detection(blocked_until);

-- Add event deduplication table
CREATE TABLE IF NOT EXISTS event_deduplication (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(100) NOT NULL UNIQUE,
    tenant_id VARCHAR(100) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_event_dedup_event_id ON event_deduplication(event_id);
CREATE INDEX IF NOT EXISTS idx_event_dedup_tenant_id ON event_deduplication(tenant_id);
CREATE INDEX IF NOT EXISTS idx_event_dedup_expires_at ON event_deduplication(expires_at);

-- Create cleanup function for expired records
CREATE OR REPLACE FUNCTION cleanup_expired_records()
RETURNS void AS $$
BEGIN
    -- Clean up expired event deduplication records
    DELETE FROM event_deduplication WHERE expires_at < CURRENT_TIMESTAMP;
    
    -- Clean up expired abuse detection records
    DELETE FROM abuse_detection WHERE blocked_until < CURRENT_TIMESTAMP;
    
    -- Clean up old rate limit tracking (older than 24 hours)
    DELETE FROM rate_limit_tracking WHERE window_start < CURRENT_TIMESTAMP - INTERVAL '24 hours';
    
    -- Clean up old audit records (older than 1 year)
    DELETE FROM missed_call_queue_audit WHERE changed_at < CURRENT_TIMESTAMP - INTERVAL '1 year';
END;
$$ LANGUAGE plpgsql;

-- Create scheduled cleanup job (run every hour)
-- Note: This would typically be set up as a cron job or scheduled task
-- For now, we'll create the function and recommend manual scheduling

-- Add performance monitoring views
CREATE OR REPLACE VIEW missed_call_queue_stats AS
SELECT 
    company_id,
    status,
    COUNT(*) as count,
    AVG(EXTRACT(EPOCH FROM (processed_at - created_at))) as avg_processing_time_seconds,
    MIN(created_at) as oldest_entry,
    MAX(created_at) as newest_entry
FROM missed_call_queue
GROUP BY company_id, status;

CREATE OR REPLACE VIEW sms_delivery_stats AS
SELECT 
    tenant_id,
    COUNT(*) as total_attempts,
    COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_deliveries,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_deliveries,
    ROUND(
        COUNT(CASE WHEN status = 'success' THEN 1 END) * 100.0 / COUNT(*), 2
    ) as success_rate_percent
FROM sms_dead_letter_queue
GROUP BY tenant_id;

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON missed_call_queue TO ottoai_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON missed_call_queue_audit TO ottoai_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON sms_dead_letter_queue TO ottoai_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON circuit_breaker_state TO ottoai_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON rate_limit_tracking TO ottoai_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON abuse_detection TO ottoai_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON event_deduplication TO ottoai_app;

-- Grant view permissions
GRANT SELECT ON missed_call_queue_stats TO ottoai_app;
GRANT SELECT ON sms_delivery_stats TO ottoai_app;

-- Add comments for documentation
COMMENT ON TABLE missed_call_queue_audit IS 'Audit trail for missed call queue changes for compliance';
COMMENT ON TABLE sms_dead_letter_queue IS 'Failed SMS messages for retry processing';
COMMENT ON TABLE circuit_breaker_state IS 'Circuit breaker state tracking for external services';
COMMENT ON TABLE rate_limit_tracking IS 'Rate limiting tracking for API endpoints';
COMMENT ON TABLE abuse_detection IS 'Abuse detection and IP blocking';
COMMENT ON TABLE event_deduplication IS 'Event deduplication to prevent replay attacks';

-- Migration completed successfully
SELECT 'Migration 001_missed_call_queue_enhancements completed successfully' as status;







