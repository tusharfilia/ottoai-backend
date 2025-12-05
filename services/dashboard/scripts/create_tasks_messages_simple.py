#!/usr/bin/env python3
"""
Create tasks and message_threads tables using raw SQL.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect
from app.database import engine

def create_tables():
    """Create tasks and message_threads tables using raw SQL."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    sql_file = Path(__file__).parent / "create_tasks_messages_tables.sql"
    with open(sql_file, 'r') as f:
        sql = f.read()
    
    # Split into CREATE TABLE and CREATE INDEX statements
    statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]
    table_statements = [s for s in statements if s.startswith('CREATE TABLE')]
    index_statements = [s for s in statements if s.startswith('CREATE INDEX')]
    
    # Execute table creation statements first (each in its own transaction)
    for statement in table_statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(statement))
                print(f"✓ Executed: {statement[:60]}...")
        except Exception as e:
            error_msg = str(e)
            if "already exists" not in error_msg.lower() and "duplicate" not in error_msg.lower():
                print(f"⚠️  Warning: {error_msg}")
    
    # Then execute index creation statements (each in its own transaction)
    for statement in index_statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(statement))
        except Exception as e:
            error_msg = str(e)
            if "already exists" not in error_msg.lower() and "duplicate" not in error_msg.lower():
                print(f"⚠️  Warning: {error_msg}")
    
    # Verify tables were created
    inspector = inspect(engine)
    new_tables = inspector.get_table_names()
    
    created = []
    if 'tasks' in new_tables and 'tasks' not in existing_tables:
        created.append('tasks')
    if 'message_threads' in new_tables and 'message_threads' not in existing_tables:
        created.append('message_threads')
    
    if created:
        print(f"✅ Created tables: {', '.join(created)}")
    else:
        if 'tasks' in new_tables:
            print("✅ 'tasks' table already exists")
        if 'message_threads' in new_tables:
            print("✅ 'message_threads' table already exists")
    
    return len(created) > 0

if __name__ == "__main__":
    print("🔧 Creating tasks and message_threads tables...\n")
    try:
        create_tables()
        print("\n✅ Done!")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

