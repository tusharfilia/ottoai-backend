from sqlalchemy.orm import Session
from ..app.database import SessionLocal
from ..app.models.sales_manager import SalesManager
from ..app.models.sales_rep import SalesRep
from ..app.models.call import Call
from datetime import datetime

def setup_sales_team():
    db = SessionLocal()
    try:
        # Check if manager exists
        manager = db.query(SalesManager).filter_by(phone_number="+12026791522").first()
        
        if not manager:
            manager = SalesManager(
                name="Default Manager",
                phone_number="+12026791522"
            )
            db.add(manager)
            db.commit()
            db.refresh(manager)
            print(f"Created new manager with ID: {manager.id}")
        else:
            print(f"Found existing manager with ID: {manager.id}")

        # Check if sales rep exists
        sales_rep = db.query(SalesRep).filter_by(phone_number="+12026791522").first()
        
        if not sales_rep:
            sales_rep = SalesRep(
                name="Default Sales Rep",
                phone_number="+12026791522",
                manager_id=manager.id
            )
            db.add(sales_rep)
            db.commit()
            db.refresh(sales_rep)
            print(f"Created new sales rep with ID: {sales_rep.id}")
        else:
            print(f"Found existing sales rep with ID: {sales_rep.id}")

        # Get most recent call
        most_recent_call = db.query(Call)\
            .order_by(Call.created_at.desc())\
            .first()
        
        if most_recent_call:
            most_recent_call.assigned_rep_id = sales_rep.id
            db.commit()
            print(f"Assigned call {most_recent_call.id} to sales rep {sales_rep.id}")
        else:
            print("No calls found in the database")

    finally:
        db.close()

if __name__ == "__main__":
    setup_sales_team() 