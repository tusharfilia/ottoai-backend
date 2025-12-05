#!/usr/bin/env python3
"""
Seed script for development test data.
Creates a test company and CSR user for local development with DEV_MODE.

Usage:
    python scripts/seed_dev_data.py

Environment Variables:
    DEV_TEST_COMPANY_ID: Company ID (default: "dev-test-company")
    DEV_TEST_USER_ID: User ID (default: "dev-test-user")
    DEV_TEST_USER_EMAIL: User email (default: "tushar@otto.ai")
    DEV_TEST_USER_NAME: User name (default: "Tushar")
    DEV_TEST_PHONE_NUMBER: Company phone number for CallRail/Twilio (required)
    DATABASE_URL: Database connection string
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.config import settings

# Import all models to ensure relationships are resolved
from app.models import (
    company,
    user,
    call,
    sales_rep,
    sales_manager,
    service,
    scheduled_call,
    transcript_analysis,
    call_transcript,
    call_analysis,
    rag_document,
    rag_query,
    followup_draft,
    personal_clone_job,
    audit_log,
    contact_card,
    lead,
    appointment,
    rep_shift,
    recording_session,
    recording_transcript,
    recording_analysis,
    task,
    key_signal,
    lead_status_history,
    rep_assignment_history,
    event_log,
    sop_compliance_result
)

# Use the imported modules
Company = company.Company
User = user.User

# Default test data
DEFAULT_COMPANY_ID = os.getenv("DEV_TEST_COMPANY_ID", "dev-test-company")
DEFAULT_USER_ID = os.getenv("DEV_TEST_USER_ID", "dev-test-user")
DEFAULT_USER_EMAIL = os.getenv("DEV_TEST_USER_EMAIL", "tushar@otto.ai")
DEFAULT_USER_NAME = os.getenv("DEV_TEST_USER_NAME", "Tushar")
DEFAULT_PHONE_NUMBER = os.getenv("DEV_TEST_PHONE_NUMBER", "")


def seed_dev_data(db: Session):
    """Create test company and user for development."""
    
    if not DEFAULT_PHONE_NUMBER:
        print("❌ ERROR: DEV_TEST_PHONE_NUMBER environment variable is required")
        print("   Set it to your CallRail/Twilio tracking number (e.g., +12028313219)")
        sys.exit(1)
    
    from sqlalchemy import text
    
    # Use raw SQL to avoid schema mismatch issues
    # Check what columns actually exist
    from sqlalchemy import inspect
    inspector = inspect(db.bind)
    
    company_cols = [c['name'] for c in inspector.get_columns('companies')]
    user_cols = [c['name'] for c in inspector.get_columns('users')]
    
    # Build company insert based on available columns
    company_fields = ["id", "name", "phone_number"]
    company_values = [":id", ":name", ":phone"]
    if "created_at" in company_cols:
        company_fields.append("created_at")
        company_values.append("datetime('now')")
    if "updated_at" in company_cols:
        company_fields.append("updated_at")
        company_values.append("datetime('now')")
    
    # Create or update test company using raw SQL
    db.execute(text(f"""
        INSERT INTO companies ({', '.join(company_fields)})
        VALUES ({', '.join(company_values)})
        ON CONFLICT(id) DO UPDATE SET
            phone_number = :phone
    """), {
        "id": DEFAULT_COMPANY_ID,
        "name": "Test Company (Dev Mode)",
        "phone": DEFAULT_PHONE_NUMBER
    })
    print(f"✓ Created/updated test company: {DEFAULT_COMPANY_ID}")
    print(f"  Phone: {DEFAULT_PHONE_NUMBER}")
    
    # Build user insert based on available columns
    username = DEFAULT_USER_EMAIL.split("@")[0]
    user_fields = ["id", "email", "username", "name", "role", "company_id"]
    user_values = [":id", ":email", ":username", ":name", ":role", ":company_id"]
    
    # Create or update test user using raw SQL
    db.execute(text(f"""
        INSERT INTO users ({', '.join(user_fields)})
        VALUES ({', '.join(user_values)})
        ON CONFLICT(id) DO UPDATE SET
            email = :email,
            name = :name,
            role = :role,
            company_id = :company_id
    """), {
        "id": DEFAULT_USER_ID,
        "email": DEFAULT_USER_EMAIL,
        "username": username,
        "name": DEFAULT_USER_NAME,
        "role": "csr",
        "company_id": DEFAULT_COMPANY_ID
    })
    print(f"✓ Created/updated test user: {DEFAULT_USER_NAME} ({DEFAULT_USER_ID})")
    print(f"  Email: {DEFAULT_USER_EMAIL}")
    print(f"  Role: CSR")
    
    db.commit()
    print("\n✅ Dev data seeded successfully!")
    print(f"\n📋 Test Credentials:")
    print(f"   Company ID: {DEFAULT_COMPANY_ID}")
    print(f"   User ID: {DEFAULT_USER_ID}")
    print(f"   Email: {DEFAULT_USER_EMAIL}")
    print(f"   Role: CSR")
    print(f"\n💡 To use dev mode, set DEV_MODE=true in your environment")


if __name__ == "__main__":
    print("🌱 Seeding development test data...\n")
    
    # Create session and seed data (skip init_db since tables likely exist)
    db = SessionLocal()
    try:
        seed_dev_data(db)
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error seeding dev data: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()




Seed script for development test data.
Creates a test company and CSR user for local development with DEV_MODE.

Usage:
    python scripts/seed_dev_data.py

Environment Variables:
    DEV_TEST_COMPANY_ID: Company ID (default: "dev-test-company")
    DEV_TEST_USER_ID: User ID (default: "dev-test-user")
    DEV_TEST_USER_EMAIL: User email (default: "tushar@otto.ai")
    DEV_TEST_USER_NAME: User name (default: "Tushar")
    DEV_TEST_PHONE_NUMBER: Company phone number for CallRail/Twilio (required)
    DATABASE_URL: Database connection string
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.config import settings

# Import all models to ensure relationships are resolved
from app.models import (
    company,
    user,
    call,
    sales_rep,
    sales_manager,
    service,
    scheduled_call,
    transcript_analysis,
    call_transcript,
    call_analysis,
    rag_document,
    rag_query,
    followup_draft,
    personal_clone_job,
    audit_log,
    contact_card,
    lead,
    appointment,
    rep_shift,
    recording_session,
    recording_transcript,
    recording_analysis,
    task,
    key_signal,
    lead_status_history,
    rep_assignment_history,
    event_log,
    sop_compliance_result
)

# Use the imported modules
Company = company.Company
User = user.User

# Default test data
DEFAULT_COMPANY_ID = os.getenv("DEV_TEST_COMPANY_ID", "dev-test-company")
DEFAULT_USER_ID = os.getenv("DEV_TEST_USER_ID", "dev-test-user")
DEFAULT_USER_EMAIL = os.getenv("DEV_TEST_USER_EMAIL", "tushar@otto.ai")
DEFAULT_USER_NAME = os.getenv("DEV_TEST_USER_NAME", "Tushar")
DEFAULT_PHONE_NUMBER = os.getenv("DEV_TEST_PHONE_NUMBER", "")


def seed_dev_data(db: Session):
    """Create test company and user for development."""
    
    if not DEFAULT_PHONE_NUMBER:
        print("❌ ERROR: DEV_TEST_PHONE_NUMBER environment variable is required")
        print("   Set it to your CallRail/Twilio tracking number (e.g., +12028313219)")
        sys.exit(1)
    
    from sqlalchemy import text
    
    # Use raw SQL to avoid schema mismatch issues
    # Check what columns actually exist
    from sqlalchemy import inspect
    inspector = inspect(db.bind)
    
    company_cols = [c['name'] for c in inspector.get_columns('companies')]
    user_cols = [c['name'] for c in inspector.get_columns('users')]
    
    # Build company insert based on available columns
    company_fields = ["id", "name", "phone_number"]
    company_values = [":id", ":name", ":phone"]
    if "created_at" in company_cols:
        company_fields.append("created_at")
        company_values.append("datetime('now')")
    if "updated_at" in company_cols:
        company_fields.append("updated_at")
        company_values.append("datetime('now')")
    
    # Create or update test company using raw SQL
    db.execute(text(f"""
        INSERT INTO companies ({', '.join(company_fields)})
        VALUES ({', '.join(company_values)})
        ON CONFLICT(id) DO UPDATE SET
            phone_number = :phone
    """), {
        "id": DEFAULT_COMPANY_ID,
        "name": "Test Company (Dev Mode)",
        "phone": DEFAULT_PHONE_NUMBER
    })
    print(f"✓ Created/updated test company: {DEFAULT_COMPANY_ID}")
    print(f"  Phone: {DEFAULT_PHONE_NUMBER}")
    
    # Build user insert based on available columns
    username = DEFAULT_USER_EMAIL.split("@")[0]
    user_fields = ["id", "email", "username", "name", "role", "company_id"]
    user_values = [":id", ":email", ":username", ":name", ":role", ":company_id"]
    
    # Create or update test user using raw SQL
    db.execute(text(f"""
        INSERT INTO users ({', '.join(user_fields)})
        VALUES ({', '.join(user_values)})
        ON CONFLICT(id) DO UPDATE SET
            email = :email,
            name = :name,
            role = :role,
            company_id = :company_id
    """), {
        "id": DEFAULT_USER_ID,
        "email": DEFAULT_USER_EMAIL,
        "username": username,
        "name": DEFAULT_USER_NAME,
        "role": "csr",
        "company_id": DEFAULT_COMPANY_ID
    })
    print(f"✓ Created/updated test user: {DEFAULT_USER_NAME} ({DEFAULT_USER_ID})")
    print(f"  Email: {DEFAULT_USER_EMAIL}")
    print(f"  Role: CSR")
    
    db.commit()
    print("\n✅ Dev data seeded successfully!")
    print(f"\n📋 Test Credentials:")
    print(f"   Company ID: {DEFAULT_COMPANY_ID}")
    print(f"   User ID: {DEFAULT_USER_ID}")
    print(f"   Email: {DEFAULT_USER_EMAIL}")
    print(f"   Role: CSR")
    print(f"\n💡 To use dev mode, set DEV_MODE=true in your environment")


if __name__ == "__main__":
    print("🌱 Seeding development test data...\n")
    
    # Create session and seed data (skip init_db since tables likely exist)
    db = SessionLocal()
    try:
        seed_dev_data(db)
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error seeding dev data: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()



