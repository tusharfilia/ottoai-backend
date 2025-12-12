#!/usr/bin/env python3
"""
Cleanup script to remove all seed/demo data from the database.

This script removes:
- Demo company (otto-demo-co)
- Demo users (csr@otto-demo.com, salesrep@otto-demo.com, manager@otto-demo.com)
- All associated data (calls, appointments, leads, contact cards, etc.)

It preserves:
- Real companies and users
- Database structure
- Any data not created by seed scripts

Usage:
    python scripts/cleanup_seed_data.py
    
    or
    
    python -m scripts.cleanup_seed_data

Environment Variables:
    DATABASE_URL: Database connection string (required)
"""

import os
import sys
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import inspect

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models import (
    company,
    user,
    contact_card,
    lead,
    call,
    appointment,
    task,
    message_thread,
    sales_rep,
    sales_manager,
    rep_shift,
    recording_session,
    recording_transcript,
    recording_analysis,
    call_transcript,
    call_analysis,
    missed_call_queue,
)

# Demo identifiers
DEMO_COMPANY_NAME = "otto-demo-co"
DEMO_USER_EMAILS = [
    "csr@otto-demo.com",
    "salesrep@otto-demo.com",
    "manager@otto-demo.com",
]

Company = company.Company
User = user.User
ContactCard = contact_card.ContactCard
Lead = lead.Lead
Call = call.Call
Appointment = appointment.Appointment
Task = task.Task
MessageThread = message_thread.MessageThread
SalesRep = sales_rep.SalesRep
SalesManager = sales_manager.SalesManager
RepShift = rep_shift.RepShift
RecordingSession = recording_session.RecordingSession
RecordingTranscript = recording_transcript.RecordingTranscript
RecordingAnalysis = recording_analysis.RecordingAnalysis
CallTranscript = call_transcript.CallTranscript
CallAnalysis = call_analysis.CallAnalysis
MissedCallQueue = missed_call_queue.MissedCallQueue


def cleanup_seed_data(db: Session):
    """Remove all seed/demo data from the database."""
    print("🧹 Cleaning up seed/demo data...\n")
    
    # Find demo company
    demo_company = db.query(Company).filter(Company.name == DEMO_COMPANY_NAME).first()
    
    if not demo_company:
        print("✅ No demo company found. Nothing to clean up.")
        return
    
    print(f"Found demo company: {demo_company.id} ({demo_company.name})")
    
    # Find demo users
    demo_users = db.query(User).filter(
        User.company_id == demo_company.id,
        User.email.in_(DEMO_USER_EMAILS)
    ).all()
    
    print(f"Found {len(demo_users)} demo users")
    
    # Delete in correct order to respect foreign key constraints
    inspector = inspect(db.bind)
    table_names = inspector.get_table_names()
    
    deleted_counts = {}
    
    # 1. Delete missed call queue entries
    if "missed_call_queue" in table_names:
        count = db.query(MissedCallQueue).filter(MissedCallQueue.company_id == demo_company.id).delete(synchronize_session=False)
        deleted_counts["missed_call_queue"] = count
        print(f"  Deleted {count} missed call queue entries")
    
    # 2. Delete tasks
    if "tasks" in table_names:
        count = db.query(Task).filter(Task.company_id == demo_company.id).delete(synchronize_session=False)
        deleted_counts["tasks"] = count
        print(f"  Deleted {count} tasks")
    
    # 3. Delete message threads
    if "message_threads" in table_names:
        count = db.query(MessageThread).filter(MessageThread.company_id == demo_company.id).delete(synchronize_session=False)
        deleted_counts["message_threads"] = count
        print(f"  Deleted {count} message threads")
    
    # 4. Delete call analyses and transcripts (by finding calls first)
    if "calls" in table_names:
        call_ids = [c.call_id for c in db.query(Call).filter(Call.company_id == demo_company.id).all()]
        if call_ids:
            if "call_analysis" in table_names or "call_analyses" in table_names:
                count = db.query(CallAnalysis).filter(CallAnalysis.call_id.in_(call_ids)).delete(synchronize_session=False)
                deleted_counts["call_analyses"] = count
                print(f"  Deleted {count} call analyses")
            if "call_transcript" in table_names or "call_transcripts" in table_names:
                count = db.query(CallTranscript).filter(CallTranscript.call_id.in_(call_ids)).delete(synchronize_session=False)
                deleted_counts["call_transcripts"] = count
                print(f"  Deleted {count} call transcripts")
    
    # 5. Delete calls
    if "calls" in table_names:
        count = db.query(Call).filter(Call.company_id == demo_company.id).delete(synchronize_session=False)
        deleted_counts["calls"] = count
        print(f"  Deleted {count} calls")
    
    # 6. Delete recording analyses and transcripts
    if "recording_sessions" in table_names:
        session_ids = [s.id for s in db.query(RecordingSession).filter(RecordingSession.company_id == demo_company.id).all()]
        if session_ids:
            if "recording_analyses" in table_names:
                count = db.query(RecordingAnalysis).filter(RecordingAnalysis.recording_session_id.in_(session_ids)).delete(synchronize_session=False)
                deleted_counts["recording_analyses"] = count
                print(f"  Deleted {count} recording analyses")
            if "recording_transcripts" in table_names:
                count = db.query(RecordingTranscript).filter(RecordingTranscript.recording_session_id.in_(session_ids)).delete(synchronize_session=False)
                deleted_counts["recording_transcripts"] = count
                print(f"  Deleted {count} recording transcripts")
    
    # 7. Delete recording sessions
    if "recording_sessions" in table_names:
        count = db.query(RecordingSession).filter(RecordingSession.company_id == demo_company.id).delete(synchronize_session=False)
        deleted_counts["recording_sessions"] = count
        print(f"  Deleted {count} recording sessions")
    
    # 8. Delete rep shifts
    if "rep_shifts" in table_names:
        count = db.query(RepShift).filter(RepShift.company_id == demo_company.id).delete(synchronize_session=False)
        deleted_counts["rep_shifts"] = count
        print(f"  Deleted {count} rep shifts")
    
    # 9. Delete appointments
    if "appointments" in table_names:
        count = db.query(Appointment).filter(Appointment.company_id == demo_company.id).delete(synchronize_session=False)
        deleted_counts["appointments"] = count
        print(f"  Deleted {count} appointments")
    
    # 10. Delete leads
    if "leads" in table_names:
        count = db.query(Lead).filter(Lead.company_id == demo_company.id).delete(synchronize_session=False)
        deleted_counts["leads"] = count
        print(f"  Deleted {count} leads")
    
    # 11. Delete contact cards
    if "contact_cards" in table_names:
        count = db.query(ContactCard).filter(ContactCard.company_id == demo_company.id).delete(synchronize_session=False)
        deleted_counts["contact_cards"] = count
        print(f"  Deleted {count} contact cards")
    
    # 12. Delete sales reps and managers
    if "sales_reps" in table_names:
        count = db.query(SalesRep).filter(SalesRep.company_id == demo_company.id).delete(synchronize_session=False)
        deleted_counts["sales_reps"] = count
        print(f"  Deleted {count} sales reps")
    
    if "sales_managers" in table_names:
        count = db.query(SalesManager).filter(SalesManager.company_id == demo_company.id).delete(synchronize_session=False)
        deleted_counts["sales_managers"] = count
        print(f"  Deleted {count} sales managers")
    
    # 13. Delete demo users
    if demo_users:
        for demo_user in demo_users:
            db.delete(demo_user)
        deleted_counts["users"] = len(demo_users)
        print(f"  Deleted {len(demo_users)} demo users")
    
    # 14. Delete demo company
    db.delete(demo_company)
    deleted_counts["companies"] = 1
    print(f"  Deleted demo company")
    
    # Commit all deletions
    db.commit()
    
    print("\n✅ Cleanup complete!")
    print("\nDeleted:")
    for table, count in deleted_counts.items():
        print(f"  - {table}: {count}")
    
    print("\n💡 The database is now clean. APIs will return empty results until real data is added.")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        cleanup_seed_data(db)
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during cleanup: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


