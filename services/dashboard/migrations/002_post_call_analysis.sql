-- Post-Call Analysis System Migration
-- Creates tables for storing call analysis results, coaching recommendations, and performance metrics

-- Create call_analysis table
CREATE TABLE IF NOT EXISTS call_analysis (
    id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL,
    company_id VARCHAR(255) NOT NULL,
    sales_rep_id VARCHAR(255),
    analyzed_at TIMESTAMP NOT NULL,
    call_metrics JSONB,
    ai_insights JSONB,
    coaching_recommendations JSONB,
    performance_score JSONB,
    analysis_version VARCHAR(50) DEFAULT '1.0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_call_analysis_call_id FOREIGN KEY (call_id) REFERENCES calls(call_id) ON DELETE CASCADE,
    CONSTRAINT fk_call_analysis_company_id FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    CONSTRAINT fk_call_analysis_sales_rep_id FOREIGN KEY (sales_rep_id) REFERENCES sales_reps(sales_rep_id) ON DELETE SET NULL
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_call_analysis_call_id ON call_analysis(call_id);
CREATE INDEX IF NOT EXISTS idx_call_analysis_company_id ON call_analysis(company_id);
CREATE INDEX IF NOT EXISTS idx_call_analysis_sales_rep_id ON call_analysis(sales_rep_id);
CREATE INDEX IF NOT EXISTS idx_call_analysis_analyzed_at ON call_analysis(analyzed_at);
CREATE INDEX IF NOT EXISTS idx_call_analysis_created_at ON call_analysis(created_at);

-- Create composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_call_analysis_company_sales_rep ON call_analysis(company_id, sales_rep_id);
CREATE INDEX IF NOT EXISTS idx_call_analysis_company_analyzed ON call_analysis(company_id, analyzed_at);

-- Create coaching_recommendations table for detailed tracking
CREATE TABLE IF NOT EXISTS coaching_recommendations (
    id SERIAL PRIMARY KEY,
    call_analysis_id INTEGER NOT NULL,
    category VARCHAR(100) NOT NULL,
    priority VARCHAR(20) NOT NULL CHECK (priority IN ('high', 'medium', 'low')),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    suggestion TEXT,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'dismissed')),
    assigned_to VARCHAR(255), -- sales_rep_id or manager_id
    due_date TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_coaching_recommendations_analysis_id FOREIGN KEY (call_analysis_id) REFERENCES call_analysis(id) ON DELETE CASCADE,
    CONSTRAINT fk_coaching_recommendations_assigned_to FOREIGN KEY (assigned_to) REFERENCES sales_reps(sales_rep_id) ON DELETE SET NULL
);

-- Create indexes for coaching recommendations
CREATE INDEX IF NOT EXISTS idx_coaching_recommendations_analysis_id ON coaching_recommendations(call_analysis_id);
CREATE INDEX IF NOT EXISTS idx_coaching_recommendations_category ON coaching_recommendations(category);
CREATE INDEX IF NOT EXISTS idx_coaching_recommendations_priority ON coaching_recommendations(priority);
CREATE INDEX IF NOT EXISTS idx_coaching_recommendations_status ON coaching_recommendations(status);
CREATE INDEX IF NOT EXISTS idx_coaching_recommendations_assigned_to ON coaching_recommendations(assigned_to);
CREATE INDEX IF NOT EXISTS idx_coaching_recommendations_due_date ON coaching_recommendations(due_date);

-- Create performance_metrics table for aggregated metrics
CREATE TABLE IF NOT EXISTS performance_metrics (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(255) NOT NULL,
    sales_rep_id VARCHAR(255),
    metric_date DATE NOT NULL,
    metric_type VARCHAR(100) NOT NULL, -- 'daily', 'weekly', 'monthly'
    total_calls INTEGER DEFAULT 0,
    successful_calls INTEGER DEFAULT 0,
    avg_duration_seconds INTEGER DEFAULT 0,
    avg_performance_score DECIMAL(5,2) DEFAULT 0,
    coaching_recommendations_count INTEGER DEFAULT 0,
    high_priority_recommendations INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_performance_metrics_company_id FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    CONSTRAINT fk_performance_metrics_sales_rep_id FOREIGN KEY (sales_rep_id) REFERENCES sales_reps(sales_rep_id) ON DELETE CASCADE,
    
    -- Unique constraint to prevent duplicates
    CONSTRAINT uk_performance_metrics_unique UNIQUE (company_id, sales_rep_id, metric_date, metric_type)
);

-- Create indexes for performance metrics
CREATE INDEX IF NOT EXISTS idx_performance_metrics_company_id ON performance_metrics(company_id);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_sales_rep_id ON performance_metrics(sales_rep_id);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_metric_date ON performance_metrics(metric_date);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_metric_type ON performance_metrics(metric_type);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_company_date ON performance_metrics(company_id, metric_date);

-- Create audit log table for tracking analysis events
CREATE TABLE IF NOT EXISTS analysis_audit_log (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL, -- 'analysis_started', 'analysis_completed', 'coaching_recommendation_created', etc.
    call_id INTEGER,
    company_id VARCHAR(255),
    sales_rep_id VARCHAR(255),
    event_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_analysis_audit_call_id FOREIGN KEY (call_id) REFERENCES calls(call_id) ON DELETE CASCADE,
    CONSTRAINT fk_analysis_audit_company_id FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    CONSTRAINT fk_analysis_audit_sales_rep_id FOREIGN KEY (sales_rep_id) REFERENCES sales_reps(sales_rep_id) ON DELETE SET NULL
);

-- Create indexes for audit log
CREATE INDEX IF NOT EXISTS idx_analysis_audit_event_type ON analysis_audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_analysis_audit_call_id ON analysis_audit_log(call_id);
CREATE INDEX IF NOT EXISTS idx_analysis_audit_company_id ON analysis_audit_log(company_id);
CREATE INDEX IF NOT EXISTS idx_analysis_audit_created_at ON analysis_audit_log(created_at);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_call_analysis_updated_at 
    BEFORE UPDATE ON call_analysis 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_coaching_recommendations_updated_at 
    BEFORE UPDATE ON coaching_recommendations 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_performance_metrics_updated_at 
    BEFORE UPDATE ON performance_metrics 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create view for easy access to analysis data with call details
CREATE OR REPLACE VIEW call_analysis_with_details AS
SELECT 
    ca.id as analysis_id,
    ca.call_id,
    ca.company_id,
    ca.sales_rep_id,
    ca.analyzed_at,
    ca.call_metrics,
    ca.ai_insights,
    ca.coaching_recommendations,
    ca.performance_score,
    ca.analysis_version,
    ca.created_at as analysis_created_at,
    c.caller_number,
    c.duration as call_duration,
    c.status as call_status,
    c.created_at as call_created_at,
    sr.name as sales_rep_name,
    comp.name as company_name
FROM call_analysis ca
JOIN calls c ON ca.call_id = c.call_id
LEFT JOIN sales_reps sr ON ca.sales_rep_id = sr.sales_rep_id
LEFT JOIN companies comp ON ca.company_id = comp.company_id;

-- Create view for performance summary
CREATE OR REPLACE VIEW performance_summary AS
SELECT 
    pm.company_id,
    pm.sales_rep_id,
    pm.metric_date,
    pm.metric_type,
    pm.total_calls,
    pm.successful_calls,
    pm.avg_duration_seconds,
    pm.avg_performance_score,
    pm.coaching_recommendations_count,
    pm.high_priority_recommendations,
    sr.name as sales_rep_name,
    comp.name as company_name,
    CASE 
        WHEN pm.total_calls > 0 THEN ROUND((pm.successful_calls::DECIMAL / pm.total_calls) * 100, 2)
        ELSE 0 
    END as success_rate
FROM performance_metrics pm
LEFT JOIN sales_reps sr ON pm.sales_rep_id = sr.sales_rep_id
LEFT JOIN companies comp ON pm.company_id = comp.company_id;

-- Insert sample data for testing (optional)
-- This can be removed in production
INSERT INTO call_analysis (
    call_id, company_id, sales_rep_id, analyzed_at, 
    call_metrics, ai_insights, coaching_recommendations, 
    performance_score, analysis_version
) VALUES (
    1, 'sample_company', 'sample_rep', CURRENT_TIMESTAMP,
    '{"duration_seconds": 300, "duration_minutes": 5.0, "is_successful": true}',
    '{"ai_available": true, "call_quality": "good", "engagement_level": "medium"}',
    '[{"category": "call_duration", "priority": "medium", "title": "Good Call Duration", "description": "Call had appropriate duration"}]',
    '{"overall_score": 75, "performance_level": "good"}',
    '1.0'
) ON CONFLICT DO NOTHING;








