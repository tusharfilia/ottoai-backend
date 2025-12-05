#!/usr/bin/env python3
"""
Create tasks and message_threads tables directly.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect
from app.database import engine

def create_tasks_table():
    """Create tasks table."""
    create_tasks_sql = """
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
    """
    
    with engine.begin() as conn:
        try:
            conn.execute(text(create_tasks_sql))
            print("✅ Created 'tasks' table")
            return True
        except Exception as e:
            if "already exists" in str(e).lower():
                print("✅ 'tasks' table already exists")
                return True
            else:
                print(f"❌ Error creating tasks table: {e}")
                return False

def create_message_threads_table():
    """Create message_threads table."""
    create_messages_sql = """
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
    """
    
    with engine.begin() as conn:
        try:
            conn.execute(text(create_messages_sql))
            print("✅ Created 'message_threads' table")
            return True
        except Exception as e:
            if "already exists" in str(e).lower():
                print("✅ 'message_threads' table already exists")
                return True
            else:
                print(f"❌ Error creating message_threads table: {e}")
                return False

if __name__ == "__main__":
    print("🔧 Creating tasks and message_threads tables...\n")
    tasks_ok = create_tasks_table()
    messages_ok = create_message_threads_table()
    
    if tasks_ok and messages_ok:
        print("\n✅ All tables created successfully!")
    else:
        print("\n⚠️  Some tables may not have been created. Check errors above.")
        sys.exit(1)



