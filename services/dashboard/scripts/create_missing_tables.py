#!/usr/bin/env python3
"""
Create missing tables (tasks and message_threads) if they don't exist.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect
from app.database import Base, engine
# Import all models to ensure relationships are loaded
from app.models import (
    company, user, contact_card, lead, appointment, call,
    task, message_thread, sales_rep, sales_manager
)

def create_missing_tables():
    """Create tasks and message_threads tables if they don't exist."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    created = []
    
    # Create tasks table if it doesn't exist
    if 'tasks' not in existing_tables:
        print("Creating 'tasks' table...")
        task.Task.__table__.create(engine, checkfirst=True)
        print("✓ Created 'tasks' table")
        created.append('tasks')
    else:
        print("✓ 'tasks' table already exists")
    
    # Create message_threads table if it doesn't exist
    if 'message_threads' not in existing_tables:
        print("Creating 'message_threads' table...")
        message_thread.MessageThread.__table__.create(engine, checkfirst=True)
        print("✓ Created 'message_threads' table")
        created.append('message_threads')
    else:
        print("✓ 'message_threads' table already exists")
    
    if created:
        print(f"\n✅ Successfully created {len(created)} table(s): {', '.join(created)}")
    else:
        print("\n✅ All tables already exist - nothing to create")
    
    return len(created) > 0

if __name__ == "__main__":
    print("🔧 Creating missing tables (tasks, message_threads)...\n")
    
    try:
        create_missing_tables()
        print("\n✅ Done!")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

