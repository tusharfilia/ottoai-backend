from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import logging
import os
from typing import List, Optional
import json
from ..database import get_db
from ..models import company, user, call, sales_manager, sales_rep, scheduled_call
from datetime import datetime

router = APIRouter(tags=["database cleanup"])

# Helper functions for Clerk operations
async def clerk_request(method, url, json_data=None):
    """Send a request to the Clerk API
    
    Args:
        method: HTTP method to use (GET, POST, DELETE, etc.)
        url: URL path to request (e.g., "/users")
        json_data: JSON data to send with the request
        
    Returns:
        Response object from the Clerk API
    """
    import httpx
    from httpx import RequestError
    
    clerk_api_key = os.environ.get("CLERK_SECRET_KEY")
    if not clerk_api_key:
        raise ValueError("CLERK_SECRET_KEY environment variable not set")
    
    clerk_base_url = "https://api.clerk.dev/v1"
    headers = {
        "Authorization": f"Bearer {clerk_api_key}",
        "Content-Type": "application/json"
    }
    
    url = f"{clerk_base_url}{url}"
    
    try:
        async with httpx.AsyncClient() as client:
            if method == "GET":
                return await client.get(url, headers=headers)
            elif method == "POST":
                return await client.post(url, headers=headers, json=json_data)
            elif method == "DELETE":
                return await client.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
    except RequestError as e:
        logging.error(f"Error making Clerk request: {str(e)}")
        raise

async def list_clerk_organizations(limit: int = 100, offset: int = 0) -> list:
    """List all Clerk organizations
    
    Args:
        limit: Maximum number of organizations to return (default: 100)
        offset: Offset for pagination (default: 0)
        
    Returns:
        list: List of organization objects
    """
    try:
        logging.info(f"Listing Clerk organizations (limit: {limit}, offset: {offset})")
        response = await clerk_request("GET", f"/organizations?limit={limit}&offset={offset}")
        
        if response.status_code == 200:
            data = response.json()
            return data.get("data", [])
        else:
            logging.error(f"Failed to list Clerk organizations. Status: {response.status_code}, Response: {response.text}")
            return []
    except Exception as e:
        logging.error(f"Error listing Clerk organizations: {str(e)}")
        return []

async def delete_clerk_organization(org_id: str) -> bool:
    """Delete a Clerk organization by ID
    
    Args:
        org_id: The ID of the organization to delete
        
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        logging.info(f"Deleting Clerk organization: {org_id}")
        response = await clerk_request("DELETE", f"/organizations/{org_id}")
        
        if response.status_code == 200:
            logging.info(f"Successfully deleted Clerk organization: {org_id}")
            return True
        else:
            logging.error(f"Failed to delete Clerk organization. Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        logging.error(f"Error deleting Clerk organization: {str(e)}")
        return False

async def list_clerk_users(limit: int = 100, offset: int = 0) -> list:
    """List all Clerk users
    
    Args:
        limit: Maximum number of users to return (default: 100)
        offset: Offset for pagination (default: 0)
        
    Returns:
        list: List of user objects
    """
    try:
        logging.info(f"Listing Clerk users (limit: {limit}, offset: {offset})")
        response = await clerk_request("GET", f"/users?limit={limit}&offset={offset}")
        
        if response.status_code == 200:
            # The response is already a list of users
            return response.json()
        else:
            logging.error(f"Failed to list Clerk users. Status: {response.status_code}, Response: {response.text}")
            return []
    except Exception as e:
        logging.error(f"Error listing Clerk users: {str(e)}")
        return []

#####################################################
# DATABASE PURGE ENDPOINTS                          #
#####################################################

@router.post("/purge-database")
async def purge_database(secret_code: str = Query(...)):
    """Delete all data from the database
    
    This is a dangerous operation that will delete ALL data from the database.
    It requires a secret code for protection.
    """
    # Simple protection to prevent accidental calls
    if secret_code != "CONFIRM_DELETE_ALL_DATA":
        return {"status": "error", "message": "Invalid secret code"}
    
    try:
        db = next(get_db())
        
        # Delete records in correct order to avoid foreign key constraint errors
        # First delete scheduled calls (since they reference calls)
        scheduled_calls_deleted = db.query(scheduled_call.ScheduledCall).delete()
        
        # Then delete calls (since they reference sales_reps)
        calls_deleted = db.query(call.Call).delete()
        
        # Then delete sales reps and managers
        sales_reps_deleted = db.query(sales_rep.SalesRep).delete()
        sales_managers_deleted = db.query(sales_manager.SalesManager).delete()
        
        # Then delete users
        users_deleted = db.query(user.User).delete()
        
        # Finally delete companies
        companies_deleted = db.query(company.Company).delete()
        
        db.commit()
        
        return {
            "status": "success",
            "message": "Database purged successfully",
            "deleted": {
                "scheduled_calls": scheduled_calls_deleted,
                "calls": calls_deleted,
                "sales_reps": sales_reps_deleted,
                "sales_managers": sales_managers_deleted,
                "users": users_deleted,
                "companies": companies_deleted
            }
        }
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error purging database: {str(e)}"}

#####################################################
# CALLS ENDPOINTS                                   #
#####################################################

@router.delete("/calls")
async def delete_all_calls(db: Session = Depends(get_db)):
    """Delete all calls from the database"""
    try:
        # First delete scheduled calls that reference these calls
        scheduled_calls_deleted = db.query(scheduled_call.ScheduledCall).delete()
        
        # Delete all transcript analyses
        from app.models.transcript_analysis import TranscriptAnalysis
        transcript_analyses_deleted = db.query(TranscriptAnalysis).delete()
        
        # Then delete the calls themselves
        calls_deleted = db.query(call.Call).delete()
        
        db.commit()
        return {
            "status": "success", 
            "message": f"Deleted {calls_deleted} calls, {scheduled_calls_deleted} scheduled calls, and {transcript_analyses_deleted} transcript analyses"
        }
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error deleting calls: {str(e)}"}

@router.delete("/call/{call_id}")
async def delete_call(call_id: int, db: Session = Depends(get_db)):
    """Delete a specific call from the database"""
    try:
        # First delete any scheduled calls related to this call
        scheduled_calls_deleted = db.query(scheduled_call.ScheduledCall).filter_by(call_id=str(call_id)).delete()
        
        # Delete any transcript analyses related to this call
        from app.models.transcript_analysis import TranscriptAnalysis
        transcript_analyses_deleted = db.query(TranscriptAnalysis).filter_by(call_id=call_id).delete()
        
        # Then delete the call
        call_record = db.query(call.Call).filter_by(call_id=call_id).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call not found")
        
        db.delete(call_record)
        db.commit()
        
        return {
            "status": "success", 
            "message": f"Deleted call {call_id}, {scheduled_calls_deleted} related scheduled calls, and {transcript_analyses_deleted} transcript analyses"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error deleting call: {str(e)}"}

#####################################################
# SCHEDULED CALLS ENDPOINTS                         #
#####################################################

@router.delete("/scheduled-calls")
async def delete_all_scheduled_calls(db: Session = Depends(get_db)):
    """Delete all scheduled calls from the database"""
    try:
        count = db.query(scheduled_call.ScheduledCall).delete()
        db.commit()
        return {"status": "success", "message": f"Deleted {count} scheduled calls"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error deleting scheduled calls: {str(e)}"}

@router.delete("/scheduled-call/{scheduled_call_id}")
async def delete_scheduled_call(scheduled_call_id: int, db: Session = Depends(get_db)):
    """Delete a specific scheduled call from the database"""
    try:
        scheduled_call_record = db.query(scheduled_call.ScheduledCall).filter_by(id=scheduled_call_id).first()
        if not scheduled_call_record:
            raise HTTPException(status_code=404, detail="Scheduled call not found")
        
        db.delete(scheduled_call_record)
        db.commit()
        
        return {"status": "success", "message": f"Deleted scheduled call {scheduled_call_id}"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error deleting scheduled call: {str(e)}"}

#####################################################
# USERS ENDPOINTS                                   #
#####################################################

@router.delete("/users")
async def delete_all_users(db: Session = Depends(get_db)):
    """Delete all users from the database"""
    try:
        # First delete calls that reference users
        calls_deleted = db.query(call.Call).delete()
        
        # Then delete scheduled calls
        scheduled_calls_deleted = db.query(scheduled_call.ScheduledCall).delete()
        
        # Then delete sales reps and sales managers
        sales_reps_deleted = db.query(sales_rep.SalesRep).delete()
        sales_managers_deleted = db.query(sales_manager.SalesManager).delete()
        
        # Then delete users
        users_deleted = db.query(user.User).delete()
        
        db.commit()
        return {
            "status": "success", 
            "message": f"Deleted {users_deleted} users, {sales_reps_deleted} sales reps, and {sales_managers_deleted} sales managers"
        }
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error deleting users: {str(e)}"}

@router.delete("/user/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Delete a specific user from the database"""
    try:
        user_record = db.query(user.User).filter_by(id=user_id).first()
        if not user_record:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Delete associated profiles
        if user_record.role == "manager":
            manager = db.query(sales_manager.SalesManager).filter_by(user_id=user_id).first()
            if manager:
                db.delete(manager)
        else:
            rep = db.query(sales_rep.SalesRep).filter_by(user_id=user_id).first()
            if rep:
                db.delete(rep)
        
        # Delete Clerk account if exists
        if user_record.clerk_id:
            try:
                response = await clerk_request("DELETE", f"/users/{user_record.clerk_id}")
                if response.status_code != 200 and response.status_code != 204:
                    logging.warning(f"Failed to delete Clerk user {user_record.clerk_id}: {response.text}")
            except Exception as e:
                logging.error(f"Error deleting Clerk user: {str(e)}")
        
        # Delete user record
        db.delete(user_record)
        db.commit()
        
        return {"status": "success", "message": f"Deleted user {user_id}"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error deleting user: {str(e)}"}

#####################################################
# COMPANIES ENDPOINTS                               #
#####################################################

@router.delete("/companies")
async def delete_all_companies(db: Session = Depends(get_db)):
    """Delete all companies from the database"""
    try:
        # Need to delete in correct order to avoid foreign key constraint errors
        # First delete scheduled calls
        scheduled_calls_deleted = db.query(scheduled_call.ScheduledCall).delete()
        
        # Then delete calls
        calls_deleted = db.query(call.Call).delete()
        
        # Then delete sales reps and managers
        sales_reps_deleted = db.query(sales_rep.SalesRep).delete()
        sales_managers_deleted = db.query(sales_manager.SalesManager).delete()
        
        # Then delete users
        users_deleted = db.query(user.User).delete()
        
        # Finally delete companies
        companies_deleted = db.query(company.Company).delete()
        
        db.commit()
        return {
            "status": "success", 
            "message": f"Deleted {companies_deleted} companies and all related data"
        }
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error deleting companies: {str(e)}"}

@router.delete("/company/{company_id}")
async def delete_company(company_id: str, db: Session = Depends(get_db)):
    """Delete a specific company from the database"""
    try:
        company_record = db.query(company.Company).filter_by(id=company_id).first()
        if not company_record:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Need to delete all associated data first
        # First delete scheduled calls
        scheduled_calls_deleted = db.query(scheduled_call.ScheduledCall).filter_by(company_id=company_id).delete()
        
        # Then delete calls
        calls_deleted = db.query(call.Call).filter_by(company_id=company_id).delete()
        
        # Get all users for this company
        user_ids = [u.id for u in db.query(user.User).filter_by(company_id=company_id).all()]
        
        # Then delete sales reps and managers
        sales_reps_deleted = db.query(sales_rep.SalesRep).filter_by(company_id=company_id).delete()
        sales_managers_deleted = db.query(sales_manager.SalesManager).filter_by(company_id=company_id).delete()
        
        # Then delete users
        users_deleted = db.query(user.User).filter_by(company_id=company_id).delete()
        
        # Finally delete company
        db.delete(company_record)
        db.commit()
        
        return {
            "status": "success", 
            "message": f"Deleted company {company_id} and all related data",
            "deleted": {
                "scheduled_calls": scheduled_calls_deleted,
                "calls": calls_deleted,
                "sales_reps": sales_reps_deleted,
                "sales_managers": sales_managers_deleted,
                "users": users_deleted
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error deleting company: {str(e)}"}

#####################################################
# SALES REPS ENDPOINTS                              #
#####################################################

@router.delete("/sales-reps")
async def delete_all_sales_reps(db: Session = Depends(get_db)):
    """Delete all sales reps from the database"""
    try:
        # First update calls to remove references to sales reps
        db.query(call.Call).update({call.Call.assigned_rep_id: None})
        
        # Then delete sales reps
        count = db.query(sales_rep.SalesRep).delete()
        db.commit()
        return {"status": "success", "message": f"Deleted {count} sales reps"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error deleting sales reps: {str(e)}"}

@router.delete("/sales-rep/{rep_id}")
async def delete_sales_rep(rep_id: int, db: Session = Depends(get_db)):
    """Delete a specific sales rep from the database"""
    try:
        rep = db.query(sales_rep.SalesRep).filter_by(id=rep_id).first()
        if not rep:
            raise HTTPException(status_code=404, detail="Sales rep not found")
        
        # Update calls to remove references to this sales rep
        user_id = rep.user_id
        db.query(call.Call).filter_by(assigned_rep_id=user_id).update({call.Call.assigned_rep_id: None})
        
        # Delete the sales rep
        db.delete(rep)
        db.commit()
        return {"status": "success", "message": f"Deleted sales rep {rep_id}"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error deleting sales rep: {str(e)}"}

#####################################################
# SALES MANAGERS ENDPOINTS                          #
#####################################################

@router.delete("/sales-managers")
async def delete_all_sales_managers(db: Session = Depends(get_db)):
    """Delete all sales managers from the database"""
    try:
        # First update sales reps to remove references to managers
        db.query(sales_rep.SalesRep).update({sales_rep.SalesRep.manager_id: None})
        
        # Then delete sales managers
        count = db.query(sales_manager.SalesManager).delete()
        db.commit()
        return {"status": "success", "message": f"Deleted {count} sales managers"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error deleting sales managers: {str(e)}"}

@router.delete("/sales-manager/{manager_id}")
async def delete_sales_manager(manager_id: int, db: Session = Depends(get_db)):
    """Delete a specific sales manager from the database"""
    try:
        manager = db.query(sales_manager.SalesManager).filter_by(id=manager_id).first()
        if not manager:
            raise HTTPException(status_code=404, detail="Sales manager not found")
        
        # Update sales reps to remove references to this manager
        db.query(sales_rep.SalesRep).filter_by(manager_id=manager_id).update({sales_rep.SalesRep.manager_id: None})
        
        # Delete the sales manager
        db.delete(manager)
        db.commit()
        return {"status": "success", "message": f"Deleted sales manager {manager_id}"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error deleting sales manager: {str(e)}"}

#####################################################
# CLERK PURGE ENDPOINTS                             #
#####################################################

@router.post("/purge-organizations")
async def purge_all_organizations(secret_code: str = Query(...)):
    """Delete all organizations from Clerk
    
    This is a dangerous operation that will delete ALL organizations in your Clerk instance.
    It requires a secret code for protection.
    """
    # Simple protection to prevent accidental calls
    if secret_code != "CONFIRM_DELETE_ALL_ORGS":
        return {"status": "error", "message": "Invalid secret code"}
    
    try:
        # Get all organizations
        all_orgs = await list_clerk_organizations(limit=500)
        
        if not all_orgs:
            return {"status": "success", "message": "No organizations found to delete"}
        
        # Get all org IDs
        org_ids = [org["id"] for org in all_orgs]
        
        # Delete each organization
        results = []
        for org_id in org_ids:
            success = await delete_clerk_organization(org_id)
            if success:
                results.append({"org_id": org_id, "status": "success"})
            else:
                results.append({"org_id": org_id, "status": "error"})
        
        return {
            "status": "complete", 
            "total": len(org_ids),
            "successful": sum(1 for r in results if r["status"] == "success"),
            "failed": sum(1 for r in results if r["status"] == "error"),
            "results": results
        }
    except Exception as e:
        logging.error(f"Error in purge_all_organizations: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.post("/purge-users")
async def purge_all_users(secret_code: str = Query(...)):
    """Delete all users from Clerk
    
    This is a dangerous operation that will delete ALL users in your Clerk instance.
    It requires a secret code for protection.
    """
    # Simple protection to prevent accidental calls
    if secret_code != "CONFIRM_DELETE_ALL_USERS":
        return {"status": "error", "message": "Invalid secret code"}
    
    try:
        # Get all users
        all_users = await list_clerk_users(limit=500)
        
        if not all_users:
            return {"status": "success", "message": "No users found to delete"}
        
        # Get all user IDs
        user_ids = [user["id"] for user in all_users]
        
        # Delete each user
        results = []
        for user_id in user_ids:
            try:
                response = await clerk_request("DELETE", f"/users/{user_id}")
                if response.status_code == 200 or response.status_code == 204:
                    results.append({"user_id": user_id, "status": "success"})
                else:
                    results.append({"user_id": user_id, "status": "error", "message": response.text})
            except Exception as e:
                results.append({"user_id": user_id, "status": "error", "message": str(e)})
        
        return {
            "status": "complete", 
            "total": len(user_ids),
            "successful": sum(1 for r in results if r["status"] == "success"),
            "failed": sum(1 for r in results if r["status"] == "error"),
            "results": results
        }
    except Exception as e:
        logging.error(f"Error in purge_all_users: {str(e)}")
        return {"status": "error", "message": str(e)}

#####################################################
# TRANSCRIPT ANALYSIS ENDPOINTS                     #
#####################################################

@router.delete("/transcript-analysis/{analysis_id}")
async def delete_transcript_analysis(analysis_id: int, db: Session = Depends(get_db)):
    """Delete a specific transcript analysis by its ID"""
    try:
        from app.models.transcript_analysis import TranscriptAnalysis
        
        analysis = db.query(TranscriptAnalysis).filter_by(analysis_id=analysis_id).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Transcript analysis not found")
        
        # Get call details for reference in the return message
        call_id = analysis.call_id
        version = analysis.analysis_version
        
        # Delete the analysis
        db.delete(analysis)
        db.commit()
        
        return {
            "status": "success", 
            "message": f"Deleted transcript analysis ID {analysis_id} for call {call_id} (version {version})"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error deleting transcript analysis: {str(e)}"}

@router.delete("/transcript-analyses/call/{call_id}")
async def delete_call_transcript_analyses(call_id: int, db: Session = Depends(get_db)):
    """Delete all transcript analyses for a specific call"""
    try:
        from app.models.transcript_analysis import TranscriptAnalysis
        
        # Check if the call exists
        from app.models.call import Call
        call_record = db.query(Call).filter_by(call_id=call_id).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call not found")
        
        # Delete all analyses for this call
        deleted_count = db.query(TranscriptAnalysis).filter_by(call_id=call_id).delete()
        db.commit()
        
        return {
            "status": "success", 
            "message": f"Deleted {deleted_count} transcript analyses for call {call_id}"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error deleting transcript analyses: {str(e)}"} 