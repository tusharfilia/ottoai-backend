-- Create tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id VARCHAR PRIMARY KEY,
    company_id VARCHAR NOT NULL,
    contact_card_id VARCHAR,
    lead_id VARCHAR,
    appointment_id VARCHAR,
    call_id INTEGER,
    description TEXT NOT NULL,
    assigned_to VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    unique_key VARCHAR,
    due_at TIMESTAMP,
    status VARCHAR NOT NULL DEFAULT 'open',
    completed_at TIMESTAMP,
    completed_by VARCHAR,
    priority VARCHAR,
    task_metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (contact_card_id) REFERENCES contact_cards(id),
    FOREIGN KEY (lead_id) REFERENCES leads(id),
    FOREIGN KEY (appointment_id) REFERENCES appointments(id),
    FOREIGN KEY (call_id) REFERENCES calls(call_id)
);

-- Create indexes for tasks
CREATE INDEX IF NOT EXISTS ix_tasks_contact_card ON tasks (contact_card_id);
CREATE INDEX IF NOT EXISTS ix_tasks_lead ON tasks (lead_id);
CREATE INDEX IF NOT EXISTS ix_tasks_appointment ON tasks (appointment_id);
CREATE INDEX IF NOT EXISTS ix_tasks_assigned_to ON tasks (assigned_to);
CREATE INDEX IF NOT EXISTS ix_tasks_status_due ON tasks (status, due_at);
CREATE INDEX IF NOT EXISTS ix_tasks_unique_key ON tasks (unique_key, company_id);

-- Create message_threads table
CREATE TABLE IF NOT EXISTS message_threads (
    id VARCHAR PRIMARY KEY,
    company_id VARCHAR NOT NULL,
    contact_card_id VARCHAR NOT NULL,
    call_id INTEGER,
    sender VARCHAR NOT NULL,
    sender_role VARCHAR NOT NULL,
    body TEXT NOT NULL,
    message_type VARCHAR NOT NULL,
    direction VARCHAR NOT NULL,
    provider VARCHAR,
    message_sid VARCHAR,
    delivered BOOLEAN DEFAULT TRUE,
    delivered_at TIMESTAMP,
    read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (contact_card_id) REFERENCES contact_cards(id),
    FOREIGN KEY (call_id) REFERENCES calls(call_id)
);

-- Create indexes for message_threads
CREATE INDEX IF NOT EXISTS ix_message_threads_contact_card ON message_threads (contact_card_id);
CREATE INDEX IF NOT EXISTS ix_message_threads_call ON message_threads (call_id);
CREATE INDEX IF NOT EXISTS ix_message_threads_company_created ON message_threads (company_id, created_at);



