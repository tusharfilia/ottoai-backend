#!/usr/bin/env python3
"""
Quick script to verify company_id matches CallRail tracking number.
Run this before testing missed calls to ensure everything is aligned.

Usage:
    python3 verify_company_id.py                    # Uses local DATABASE_URL from .env
    python3 verify_company_id.py <DATABASE_URL>      # Uses provided DATABASE_URL
    DATABASE_URL="..." python3 verify_company_id.py  # Uses env var DATABASE_URL
"""

import os
import sys
from sqlalchemy import create_engine, text

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings

def verify_company_setup(database_url=None):
    """Verify company_id and CallRail tracking number alignment."""
    
    # Get database URL (from parameter, env var, or settings)
    if not database_url:
        database_url = os.getenv("DATABASE_URL") or settings.DATABASE_URL
    
    if not database_url:
        print("❌ Error: No DATABASE_URL provided!")
        print("   Usage: python3 verify_company_id.py <DATABASE_URL>")
        print("   Or set: DATABASE_URL='...' python3 verify_company_id.py")
        return
    
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    # Create database connection
    engine = create_engine(database_url)
    
    try:
        print("=" * 60)
        print("COMPANY_ID VERIFICATION")
        print("=" * 60)
        print()
        
        # Use raw SQL to avoid relationship loading issues
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, name, phone_number FROM companies"))
            companies = result.fetchall()
        
        if not companies:
            print("❌ No companies found in database!")
            print("   You need to create a company record first.")
            return
        
        print(f"Found {len(companies)} company(ies) in database:\n")
        
        for comp_row in companies:
            comp_id, comp_name, comp_phone = comp_row
            print(f"📋 Company: {comp_name}")
            print(f"   Company ID: {comp_id}")
            print(f"   Phone Number (CallRail tracking): {comp_phone or 'NOT SET'}")
            print()
            
            if not comp_phone:
                print("   ⚠️  WARNING: Phone number is not set!")
                print("   This company will NOT receive CallRail webhooks.")
                print()
            else:
                # Check if phone number format matches expected CallRail format
                phone = comp_phone.strip()
                if phone.startswith("+1"):
                    print(f"   ✅ Phone number format looks correct: {phone}")
                else:
                    print(f"   ⚠️  Phone number format: {phone}")
                    print(f"      Expected format: +1XXXXXXXXXX (e.g., +15205232772)")
                print()
        
        print("=" * 60)
        print("VERIFICATION CHECKLIST")
        print("=" * 60)
        print()
        print("Before making a test call, verify:")
        print()
        print("1. ✅ Company exists in database")
        print("2. ✅ Company.phone_number matches your CallRail tracking number")
        print("3. ✅ Phone number format is correct (+1XXXXXXXXXX)")
        print("4. ✅ Your frontend uses the same company_id")
        print()
        print("=" * 60)
        print()
        
        # Interactive check
        if len(companies) == 1:
            comp_id, comp_name, comp_phone = companies[0]
            print(f"🎯 Your company_id is: {comp_id}")
            print(f"📞 Your CallRail tracking number should be: {comp_phone or 'NOT SET'}")
            print()
            
            if comp_phone:
                print("To verify in your frontend:")
                print(f"   1. Open browser console")
                print(f"   2. Check localStorage or API response for company_id")
                print(f"   3. It should match: {comp_id}")
                print()
                print("To verify CallRail:")
                print(f"   1. Go to CallRail dashboard")
                print(f"   2. Check your tracking number")
                print(f"   3. It should match: {comp_phone}")
            else:
                print("⚠️  ACTION REQUIRED:")
                print(f"   Update company phone_number to your CallRail tracking number:")
                print(f"   UPDATE companies SET phone_number = '+1YOUR_NUMBER' WHERE id = '{comp_id}';")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Allow DATABASE_URL as command line argument
    db_url = None
    if len(sys.argv) > 1:
        db_url = sys.argv[1]
    
    verify_company_setup(database_url=db_url)

