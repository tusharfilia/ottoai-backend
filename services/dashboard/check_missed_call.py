#!/usr/bin/env python3
"""
Quick script to check if a missed call was received and stored.
Run this after making a test call to verify the webhook flow.
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

def check_missed_calls(database_url: str, company_id: str = None, minutes_ago: int = 5):
    """Check for missed calls in the database."""
    
    if not database_url:
        print("❌ Error: DATABASE_URL is not set.")
        print("   Please set the DATABASE_URL environment variable or pass it as an argument.")
        return

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    engine = None
    try:
        engine = create_engine(database_url)
        
        print("=" * 60)
        print("MISSED CALL VERIFICATION")
        print("=" * 60)
        print()
        
        with engine.connect() as connection:
            # Get recent missed calls (last N minutes)
            time_threshold = datetime.utcnow() - timedelta(minutes=minutes_ago)
            
            if company_id:
                query = text("""
                    SELECT 
                        call_id,
                        phone_number,
                        company_id,
                        missed_call,
                        cancelled,
                        created_at,
                        updated_at,
                        status
                    FROM calls 
                    WHERE missed_call = true 
                    AND cancelled = false
                    AND company_id = :company_id
                    AND created_at >= :time_threshold
                    ORDER BY created_at DESC
                """)
                result = connection.execute(query, {
                    "company_id": company_id,
                    "time_threshold": time_threshold
                })
            else:
                query = text("""
                    SELECT 
                        call_id,
                        phone_number,
                        company_id,
                        missed_call,
                        cancelled,
                        created_at,
                        updated_at,
                        status
                    FROM calls 
                    WHERE missed_call = true 
                    AND cancelled = false
                    AND created_at >= :time_threshold
                    ORDER BY created_at DESC
                """)
                result = connection.execute(query, {
                    "time_threshold": time_threshold
                })
            
            calls = result.fetchall()
            
            if not calls:
                print(f"❌ No missed calls found in the last {minutes_ago} minutes")
                if company_id:
                    print(f"   (filtered by company_id: {company_id})")
                print()
                print("🔍 Checking all recent calls (any status)...")
                
                # Check all recent calls
                if company_id:
                    all_calls_query = text("""
                        SELECT 
                            call_id,
                            phone_number,
                            company_id,
                            missed_call,
                            cancelled,
                            created_at,
                            status
                        FROM calls 
                        WHERE company_id = :company_id
                        AND created_at >= :time_threshold
                        ORDER BY created_at DESC
                        LIMIT 10
                    """)
                    all_calls = connection.execute(all_calls_query, {
                        "company_id": company_id,
                        "time_threshold": time_threshold
                    }).fetchall()
                else:
                    all_calls_query = text("""
                        SELECT 
                            call_id,
                            phone_number,
                            company_id,
                            missed_call,
                            cancelled,
                            created_at,
                            status
                        FROM calls 
                        WHERE created_at >= :time_threshold
                        ORDER BY created_at DESC
                        LIMIT 10
                    """)
                    all_calls = connection.execute(all_calls_query, {
                        "time_threshold": time_threshold
                    }).fetchall()
                
                if all_calls:
                    print(f"   Found {len(all_calls)} recent call(s):")
                    for call in all_calls:
                        missed = "✅ MISSED" if call[3] else "❌ answered"
                        cancelled = "CANCELLED" if call[4] else "active"
                        print(f"   - Call ID: {call[0]} | Phone: {call[1]} | {missed} | {cancelled} | Status: {call[6]}")
                        print(f"     Created: {call[5]}")
                else:
                    print("   ❌ No recent calls found at all!")
                    print()
                    print("   This could mean:")
                    print("   1. CallRail webhook is not configured")
                    print("   2. Webhook URL is incorrect")
                    print("   3. CallRail hasn't sent the webhook yet (wait 30-60 seconds)")
                    print("   4. Webhook failed to reach the backend")
            else:
                print(f"✅ Found {len(calls)} missed call(s) in the last {minutes_ago} minutes:")
                print()
                for call in calls:
                    print(f"📞 Call ID: {call[0]}")
                    print(f"   Phone: {call[1]}")
                    print(f"   Company ID: {call[2]}")
                    print(f"   Missed Call: {call[3]}")
                    print(f"   Cancelled: {call[4]}")
                    print(f"   Status: {call[7]}")
                    print(f"   Created: {call[5]}")
                    print(f"   Updated: {call[6]}")
                    print()
                
                print("✅ This missed call should appear on your dashboard!")
                print()
                print("📋 Next Steps:")
                print("   1. Refresh your dashboard")
                print("   2. Check the 'Missed Calls' section")
                print("   3. The call should appear automatically")
        
        print("=" * 60)
        
    except OperationalError as e:
        print(f"❌ Database connection error: {e}")
        print("   Please ensure your DATABASE_URL is correct and the database is accessible.")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if engine:
            engine.dispose()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check if a missed call was received and stored.")
    parser.add_argument("database_url", nargs="?", 
                        help="Optional: PostgreSQL DATABASE_URL. If not provided, uses DATABASE_URL environment variable.")
    parser.add_argument("--company-id", 
                        help="Optional: Filter by company_id")
    parser.add_argument("--minutes", type=int, default=5,
                        help="How many minutes ago to look back (default: 5)")
    args = parser.parse_args()

    db_url = args.database_url or os.getenv("DATABASE_URL")
    check_missed_calls(db_url, args.company_id, args.minutes)


"""
Quick script to check if a missed call was received and stored.
Run this after making a test call to verify the webhook flow.
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

def check_missed_calls(database_url: str, company_id: str = None, minutes_ago: int = 5):
    """Check for missed calls in the database."""
    
    if not database_url:
        print("❌ Error: DATABASE_URL is not set.")
        print("   Please set the DATABASE_URL environment variable or pass it as an argument.")
        return

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    engine = None
    try:
        engine = create_engine(database_url)
        
        print("=" * 60)
        print("MISSED CALL VERIFICATION")
        print("=" * 60)
        print()
        
        with engine.connect() as connection:
            # Get recent missed calls (last N minutes)
            time_threshold = datetime.utcnow() - timedelta(minutes=minutes_ago)
            
            if company_id:
                query = text("""
                    SELECT 
                        call_id,
                        phone_number,
                        company_id,
                        missed_call,
                        cancelled,
                        created_at,
                        updated_at,
                        status
                    FROM calls 
                    WHERE missed_call = true 
                    AND cancelled = false
                    AND company_id = :company_id
                    AND created_at >= :time_threshold
                    ORDER BY created_at DESC
                """)
                result = connection.execute(query, {
                    "company_id": company_id,
                    "time_threshold": time_threshold
                })
            else:
                query = text("""
                    SELECT 
                        call_id,
                        phone_number,
                        company_id,
                        missed_call,
                        cancelled,
                        created_at,
                        updated_at,
                        status
                    FROM calls 
                    WHERE missed_call = true 
                    AND cancelled = false
                    AND created_at >= :time_threshold
                    ORDER BY created_at DESC
                """)
                result = connection.execute(query, {
                    "time_threshold": time_threshold
                })
            
            calls = result.fetchall()
            
            if not calls:
                print(f"❌ No missed calls found in the last {minutes_ago} minutes")
                if company_id:
                    print(f"   (filtered by company_id: {company_id})")
                print()
                print("🔍 Checking all recent calls (any status)...")
                
                # Check all recent calls
                if company_id:
                    all_calls_query = text("""
                        SELECT 
                            call_id,
                            phone_number,
                            company_id,
                            missed_call,
                            cancelled,
                            created_at,
                            status
                        FROM calls 
                        WHERE company_id = :company_id
                        AND created_at >= :time_threshold
                        ORDER BY created_at DESC
                        LIMIT 10
                    """)
                    all_calls = connection.execute(all_calls_query, {
                        "company_id": company_id,
                        "time_threshold": time_threshold
                    }).fetchall()
                else:
                    all_calls_query = text("""
                        SELECT 
                            call_id,
                            phone_number,
                            company_id,
                            missed_call,
                            cancelled,
                            created_at,
                            status
                        FROM calls 
                        WHERE created_at >= :time_threshold
                        ORDER BY created_at DESC
                        LIMIT 10
                    """)
                    all_calls = connection.execute(all_calls_query, {
                        "time_threshold": time_threshold
                    }).fetchall()
                
                if all_calls:
                    print(f"   Found {len(all_calls)} recent call(s):")
                    for call in all_calls:
                        missed = "✅ MISSED" if call[3] else "❌ answered"
                        cancelled = "CANCELLED" if call[4] else "active"
                        print(f"   - Call ID: {call[0]} | Phone: {call[1]} | {missed} | {cancelled} | Status: {call[6]}")
                        print(f"     Created: {call[5]}")
                else:
                    print("   ❌ No recent calls found at all!")
                    print()
                    print("   This could mean:")
                    print("   1. CallRail webhook is not configured")
                    print("   2. Webhook URL is incorrect")
                    print("   3. CallRail hasn't sent the webhook yet (wait 30-60 seconds)")
                    print("   4. Webhook failed to reach the backend")
            else:
                print(f"✅ Found {len(calls)} missed call(s) in the last {minutes_ago} minutes:")
                print()
                for call in calls:
                    print(f"📞 Call ID: {call[0]}")
                    print(f"   Phone: {call[1]}")
                    print(f"   Company ID: {call[2]}")
                    print(f"   Missed Call: {call[3]}")
                    print(f"   Cancelled: {call[4]}")
                    print(f"   Status: {call[7]}")
                    print(f"   Created: {call[5]}")
                    print(f"   Updated: {call[6]}")
                    print()
                
                print("✅ This missed call should appear on your dashboard!")
                print()
                print("📋 Next Steps:")
                print("   1. Refresh your dashboard")
                print("   2. Check the 'Missed Calls' section")
                print("   3. The call should appear automatically")
        
        print("=" * 60)
        
    except OperationalError as e:
        print(f"❌ Database connection error: {e}")
        print("   Please ensure your DATABASE_URL is correct and the database is accessible.")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if engine:
            engine.dispose()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check if a missed call was received and stored.")
    parser.add_argument("database_url", nargs="?", 
                        help="Optional: PostgreSQL DATABASE_URL. If not provided, uses DATABASE_URL environment variable.")
    parser.add_argument("--company-id", 
                        help="Optional: Filter by company_id")
    parser.add_argument("--minutes", type=int, default=5,
                        help="How many minutes ago to look back (default: 5)")
    args = parser.parse_args()

    db_url = args.database_url or os.getenv("DATABASE_URL")
    check_missed_calls(db_url, args.company_id, args.minutes)


"""
Quick script to check if a missed call was received and stored.
Run this after making a test call to verify the webhook flow.
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

def check_missed_calls(database_url: str, company_id: str = None, minutes_ago: int = 5):
    """Check for missed calls in the database."""
    
    if not database_url:
        print("❌ Error: DATABASE_URL is not set.")
        print("   Please set the DATABASE_URL environment variable or pass it as an argument.")
        return

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    engine = None
    try:
        engine = create_engine(database_url)
        
        print("=" * 60)
        print("MISSED CALL VERIFICATION")
        print("=" * 60)
        print()
        
        with engine.connect() as connection:
            # Get recent missed calls (last N minutes)
            time_threshold = datetime.utcnow() - timedelta(minutes=minutes_ago)
            
            if company_id:
                query = text("""
                    SELECT 
                        call_id,
                        phone_number,
                        company_id,
                        missed_call,
                        cancelled,
                        created_at,
                        updated_at,
                        status
                    FROM calls 
                    WHERE missed_call = true 
                    AND cancelled = false
                    AND company_id = :company_id
                    AND created_at >= :time_threshold
                    ORDER BY created_at DESC
                """)
                result = connection.execute(query, {
                    "company_id": company_id,
                    "time_threshold": time_threshold
                })
            else:
                query = text("""
                    SELECT 
                        call_id,
                        phone_number,
                        company_id,
                        missed_call,
                        cancelled,
                        created_at,
                        updated_at,
                        status
                    FROM calls 
                    WHERE missed_call = true 
                    AND cancelled = false
                    AND created_at >= :time_threshold
                    ORDER BY created_at DESC
                """)
                result = connection.execute(query, {
                    "time_threshold": time_threshold
                })
            
            calls = result.fetchall()
            
            if not calls:
                print(f"❌ No missed calls found in the last {minutes_ago} minutes")
                if company_id:
                    print(f"   (filtered by company_id: {company_id})")
                print()
                print("🔍 Checking all recent calls (any status)...")
                
                # Check all recent calls
                if company_id:
                    all_calls_query = text("""
                        SELECT 
                            call_id,
                            phone_number,
                            company_id,
                            missed_call,
                            cancelled,
                            created_at,
                            status
                        FROM calls 
                        WHERE company_id = :company_id
                        AND created_at >= :time_threshold
                        ORDER BY created_at DESC
                        LIMIT 10
                    """)
                    all_calls = connection.execute(all_calls_query, {
                        "company_id": company_id,
                        "time_threshold": time_threshold
                    }).fetchall()
                else:
                    all_calls_query = text("""
                        SELECT 
                            call_id,
                            phone_number,
                            company_id,
                            missed_call,
                            cancelled,
                            created_at,
                            status
                        FROM calls 
                        WHERE created_at >= :time_threshold
                        ORDER BY created_at DESC
                        LIMIT 10
                    """)
                    all_calls = connection.execute(all_calls_query, {
                        "time_threshold": time_threshold
                    }).fetchall()
                
                if all_calls:
                    print(f"   Found {len(all_calls)} recent call(s):")
                    for call in all_calls:
                        missed = "✅ MISSED" if call[3] else "❌ answered"
                        cancelled = "CANCELLED" if call[4] else "active"
                        print(f"   - Call ID: {call[0]} | Phone: {call[1]} | {missed} | {cancelled} | Status: {call[6]}")
                        print(f"     Created: {call[5]}")
                else:
                    print("   ❌ No recent calls found at all!")
                    print()
                    print("   This could mean:")
                    print("   1. CallRail webhook is not configured")
                    print("   2. Webhook URL is incorrect")
                    print("   3. CallRail hasn't sent the webhook yet (wait 30-60 seconds)")
                    print("   4. Webhook failed to reach the backend")
            else:
                print(f"✅ Found {len(calls)} missed call(s) in the last {minutes_ago} minutes:")
                print()
                for call in calls:
                    print(f"📞 Call ID: {call[0]}")
                    print(f"   Phone: {call[1]}")
                    print(f"   Company ID: {call[2]}")
                    print(f"   Missed Call: {call[3]}")
                    print(f"   Cancelled: {call[4]}")
                    print(f"   Status: {call[7]}")
                    print(f"   Created: {call[5]}")
                    print(f"   Updated: {call[6]}")
                    print()
                
                print("✅ This missed call should appear on your dashboard!")
                print()
                print("📋 Next Steps:")
                print("   1. Refresh your dashboard")
                print("   2. Check the 'Missed Calls' section")
                print("   3. The call should appear automatically")
        
        print("=" * 60)
        
    except OperationalError as e:
        print(f"❌ Database connection error: {e}")
        print("   Please ensure your DATABASE_URL is correct and the database is accessible.")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if engine:
            engine.dispose()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check if a missed call was received and stored.")
    parser.add_argument("database_url", nargs="?", 
                        help="Optional: PostgreSQL DATABASE_URL. If not provided, uses DATABASE_URL environment variable.")
    parser.add_argument("--company-id", 
                        help="Optional: Filter by company_id")
    parser.add_argument("--minutes", type=int, default=5,
                        help="How many minutes ago to look back (default: 5)")
    args = parser.parse_args()

    db_url = args.database_url or os.getenv("DATABASE_URL")
    check_missed_calls(db_url, args.company_id, args.minutes)


