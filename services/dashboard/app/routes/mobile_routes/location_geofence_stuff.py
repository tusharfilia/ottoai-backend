from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.sales_rep import SalesRep
from app.models.call import Call
import logging
import json
from datetime import datetime, timedelta
import httpx
import os
from sqlalchemy import desc

# Setup logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/location", tags=["location"])

# Function to handle geocoding addresses to coordinates
async def geocode_address(address: str) -> Optional[Dict[str, float]]:
    """Convert address to coordinates using a geocoding service"""
    try:
        # Using Nominatim, a free geocoding service (can be replaced with Google Maps or other service)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": address,
                    "format": "json",
                    "limit": 1
                },
                headers={"User-Agent": "TrueView-App"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                    return {"latitude": lat, "longitude": lon}
            
            logger.warning(f"Failed to geocode address: {address}")
            return None
    except Exception as e:
        logger.error(f"Error geocoding address: {e}")
        return None

async def create_geofence_for_call(call_id: int, db: Session):
    """
    Create a geofence for a call when it's booked.
    
    This will be called automatically when a call is booked or assigned
    to populate the geofence field with coordinates from the address.
    """
    # Get the call
    call = db.query(Call).filter(Call.call_id == call_id).first()
    if not call or not call.address:
        logger.warning(f"Cannot create geofence for call {call_id}: Call not found or no address")
        return None
    
    # Check if geofence already exists
    if call.geofence:
        logger.info(f"Geofence already exists for call {call_id}")
        return call.geofence
    
    # Convert address to coordinates
    coordinates = await geocode_address(call.address)
    if not coordinates:
        # Log the failure but don't raise an exception
        logger.warning(f"Could not geocode address for call {call_id}: {call.address}")
        return None
    
    # Create geofence with default radius of 250 meters
    geofence = {
        "latitude": coordinates["latitude"],
        "longitude": coordinates["longitude"],
        "radius": 250,  # Default radius in meters
        "call_id": call_id,
        "address": call.address,
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Update call's geofence information
    call.geofence = geofence
    db.commit()
    
    logger.info(f"Created geofence for call {call_id}")
    return geofence

async def sync_rep_geofences(rep_id: str, db: Session):
    """
    Sync a sales rep's active_geofences based on all their assigned calls.
    
    This ensures the rep has all the geofences they should be monitoring.
    """
    # Get the sales rep
    sales_rep = db.query(SalesRep).filter(SalesRep.user_id == rep_id).first()
    if not sales_rep:
        logger.warning(f"Sales rep with ID {rep_id} not found")
        return False
    
    # Get all active calls assigned to this rep
    active_calls = db.query(Call).filter(
        Call.assigned_rep_id == rep_id,
        Call.booked.is_(True),
        Call.cancelled.is_(False)
    ).all()
    
    if not active_calls:
        logger.info(f"No active calls found for rep {rep_id}")
        # Clear active geofences if there are no active calls
        sales_rep.active_geofences = []
        db.commit()
        return True
    
    # Create a new list of geofences from scratch
    new_geofences = []
    
    # Process each call
    for call in active_calls:
        # Skip if no address
        if not call.address:
            continue
        
        # If call has a geofence, add it to the list
        if call.geofence:
            new_geofences.append(call.geofence)
        else:
            # Try to create a geofence if needed
            try:
                geofence = await create_geofence_for_call(call.call_id, db)
                if geofence:
                    new_geofences.append(geofence)
            except Exception as e:
                logger.error(f"Error creating geofence for call {call.call_id}: {e}")
    
    # Update sales rep with new list of geofences
    sales_rep.active_geofences = new_geofences
    db.commit()
    
    logger.info(f"Synced {len(new_geofences)} geofences for rep {rep_id}")
    return True

# Calculate time difference in minutes
def calculate_time_difference_minutes(start_time: datetime, end_time: datetime) -> int:
    """Calculate the time difference in minutes between two timestamps"""
    if not start_time or not end_time:
        return 0
    
    diff = end_time - start_time
    return int(diff.total_seconds() / 60)

@router.post("/update-geofences")
async def update_geofences(
    data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Update active geofences for a sales rep
    When a new call is assigned, convert the address to coordinates and add to active geofences
    Maintains max number of active geofences by removing oldest if necessary
    """
    rep_id = data.get("rep_id")
    call_id = data.get("call_id")
    
    if not rep_id or not call_id:
        raise HTTPException(status_code=400, detail="Both rep_id and call_id are required")
    
    # Get the sales rep
    sales_rep = db.query(SalesRep).filter(SalesRep.user_id == rep_id).first()
    if not sales_rep:
        raise HTTPException(status_code=404, detail=f"Sales rep with ID {rep_id} not found")
    
    # Get the call
    call = db.query(Call).filter(Call.call_id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail=f"Call with ID {call_id} not found")
    
    # Get call address
    address = call.address
    if not address:
        raise HTTPException(status_code=400, detail=f"Call with ID {call_id} has no address")
    
    # Convert address to coordinates
    coordinates = await geocode_address(address)
    if not coordinates:
        raise HTTPException(status_code=400, detail=f"Could not geocode address: {address}")
    
    # Create geofence with default radius of 250 meters
    geofence = {
        "latitude": coordinates["latitude"],
        "longitude": coordinates["longitude"],
        "radius": 250,  # Default radius in meters
        "call_id": call_id,
        "address": address,
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Update call's geofence information
    call.geofence = geofence
    
    # Update sales rep's active geofences
    active_geofences = sales_rep.active_geofences or []
    
    # If not a list, initialize as empty list
    if not isinstance(active_geofences, list):
        active_geofences = []
    
    # Add new geofence
    active_geofences.append(geofence)
    
    # Keep only the most recent geofences (max 20)
    if len(active_geofences) > 20:
        active_geofences = sorted(active_geofences, key=lambda g: g.get("created_at", ""), reverse=True)[:20]
    
    # Update sales rep
    sales_rep.active_geofences = active_geofences
    
    # Commit changes
    db.commit()
    
    return {"message": "Geofence added successfully", "geofence": geofence}

@router.post("/geofence-event")
async def log_geofence_event(
    data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Log geofence entry/exit events
    Track first two entries/exits, time spent in geofence, battery status, etc.
    """
    event_type = data.get("event_type")  # "entry" or "exit"
    call_id = data.get("call_id")
    rep_id = data.get("rep_id")
    timestamp = data.get("timestamp")
    battery_percentage = data.get("battery_percentage")
    is_charging = data.get("is_charging")
    
    # Validate required fields
    if not all([event_type, call_id, rep_id, timestamp]):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    if event_type not in ["entry", "exit"]:
        raise HTTPException(status_code=400, detail="Event type must be 'entry' or 'exit'")
    
    # Get the call
    call = db.query(Call).filter(Call.call_id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail=f"Call with ID {call_id} not found")
    
    # Parse timestamp if it's a string
    if isinstance(timestamp, str):
        try:
            event_timestamp = datetime.fromisoformat(timestamp)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid timestamp format. Use ISO format.")
    else:
        event_timestamp = datetime.utcnow()
    
    # Process entry event
    if event_type == "entry":
        # Increment entry count
        call.geofence_entry_count = (call.geofence_entry_count or 0) + 1
        
        # Check if this is first or second entry
        if not call.geofence_entry_1_ts:
            # First entry
            call.geofence_entry_1_ts = event_timestamp
            call.battery_at_geofence_entry = battery_percentage
            call.charging_at_geofence_entry = is_charging
        elif not call.geofence_entry_2_ts and call.geofence_exit_1_ts:
            # Second entry (only log if there was a first exit)
            call.geofence_entry_2_ts = event_timestamp
        
        # Multiple entries flag
        if call.geofence_entry_count > 1:
            call.geofence_multiple_entries = True
    
    # Process exit event
    elif event_type == "exit":
        # Check if this is first or second exit
        if call.geofence_entry_1_ts and not call.geofence_exit_1_ts:
            # First exit
            call.geofence_exit_1_ts = event_timestamp
            # Calculate time spent in geofence
            call.geofence_time_1_m = calculate_time_difference_minutes(
                call.geofence_entry_1_ts, event_timestamp
            )
            
            # If recording is still running, stop it
            if call.recording_started_ts and not call.recording_stopped_ts:
                call.recording_stopped_ts = event_timestamp
                if call.recording_started_ts:
                    call.recording_duration_s = int((event_timestamp - call.recording_started_ts).total_seconds())
                
        elif call.geofence_entry_2_ts and not call.geofence_exit_2_ts:
            # Second exit
            call.geofence_exit_2_ts = event_timestamp
            # Calculate time spent in geofence for second visit
            call.geofence_time_2_m = calculate_time_difference_minutes(
                call.geofence_entry_2_ts, event_timestamp
            )
            
            # If recording is still running, stop it
            if call.recording_started_ts and not call.recording_stopped_ts:
                call.recording_stopped_ts = event_timestamp
                if call.recording_started_ts:
                    call.recording_duration_s = int((event_timestamp - call.recording_started_ts).total_seconds())
    
    # Commit changes
    db.commit()
    
    return {
        "message": f"Geofence {event_type} logged successfully",
        "call_id": call_id,
        "event_type": event_type,
        "timestamp": event_timestamp.isoformat()
    }

@router.post("/recording-event")
async def record_audio_event(
    data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Log recording start/stop events and update call record accordingly
    Tracks time to start recording, battery status, recording duration
    """
    event_type = data.get("event_type")  # "start" or "stop"
    call_id = data.get("call_id")
    rep_id = data.get("rep_id")
    timestamp = data.get("timestamp")
    battery_percentage = data.get("battery_percentage")
    is_charging = data.get("is_charging")
    
    # Validate required fields
    if not all([event_type, call_id, rep_id]):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    if event_type not in ["start", "stop"]:
        raise HTTPException(status_code=400, detail="Event type must be 'start' or 'stop'")
    
    # Get the call
    call = db.query(Call).filter(Call.call_id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail=f"Call with ID {call_id} not found")
    
    # Parse timestamp if it's a string
    if isinstance(timestamp, str):
        try:
            event_timestamp = datetime.fromisoformat(timestamp)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid timestamp format. Use ISO format.")
    else:
        event_timestamp = datetime.utcnow()
    
    # Process start event
    if event_type == "start":
        call.recording_started_ts = event_timestamp
        call.battery_at_recording_start = battery_percentage
        call.charging_at_recording_start = is_charging
        
        # Calculate time to start recording after entering geofence
        if call.geofence_entry_1_ts:
            time_diff_seconds = (event_timestamp - call.geofence_entry_1_ts).total_seconds()
            call.time_to_start_recording_s = int(time_diff_seconds)
    
    # Process stop event
    elif event_type == "stop":
        call.recording_stopped_ts = event_timestamp
        
        # Calculate recording duration
        if call.recording_started_ts:
            duration_seconds = (event_timestamp - call.recording_started_ts).total_seconds()
            call.recording_duration_s = int(duration_seconds)
    
    # Commit changes
    db.commit()
    
    return {
        "message": f"Recording {event_type} event logged successfully",
        "call_id": call_id,
        "event_type": event_type,
        "timestamp": event_timestamp.isoformat()
    }

@router.post("/remove-geofence")
async def remove_geofence(
    data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Remove a geofence when a sale is closed (either sold or customer decided not to purchase)
    """
    rep_id = data.get("rep_id")
    call_id = data.get("call_id")
    reason = data.get("reason", "Sale closed")
    
    if not rep_id or not call_id:
        raise HTTPException(status_code=400, detail="Both rep_id and call_id are required")
    
    # Get the sales rep
    sales_rep = db.query(SalesRep).filter(SalesRep.user_id == rep_id).first()
    if not sales_rep:
        raise HTTPException(status_code=404, detail=f"Sales rep with ID {rep_id} not found")
    
    # Get the call
    call = db.query(Call).filter(Call.call_id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail=f"Call with ID {call_id} not found")
    
    # Check if we need to update the call status
    if data.get("bought") is not None:
        call.bought = data.get("bought")
        
    # If we have a price and the call was bought
    if data.get("price_if_bought") and call.bought:
        call.price_if_bought = data.get("price_if_bought")
    
    # If not bought and we have a reason
    if not call.bought and data.get("reason_not_bought_homeowner"):
        call.reason_not_bought_homeowner = data.get("reason_not_bought_homeowner")
        
    # Remove the geofence from the sales rep's active list
    active_geofences = sales_rep.active_geofences or []
    
    if not isinstance(active_geofences, list):
        active_geofences = []
    
    # Check if we have a geofence for this call before removing
    had_geofence = any(g.get("call_id") == call_id for g in active_geofences)
        
    # Filter out the geofence for this call
    active_geofences = [g for g in active_geofences if g.get("call_id") != call_id]
    
    # Update sales rep
    sales_rep.active_geofences = active_geofences
    
    # Clear geofence data from the call
    call.geofence = None
    
    # Commit changes
    db.commit()
    
    return {
        "message": f"Geofence for call {call_id} removed successfully",
        "had_geofence": had_geofence,
        "active_geofences_count": len(active_geofences)
    }

@router.post("/bulk-geocode-calls")
async def bulk_geocode_calls(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    company_id: Optional[str] = None,
    limit: int = 100
):
    """
    Admin endpoint to geocode all existing calls with addresses that don't have geofences yet.
    Can be filtered by company_id and limited to a specific number of calls.
    """
    try:
        # Build the query
        query = db.query(Call).filter(
            Call.address.isnot(None),  # Has address
            Call.geofence.is_(None),   # Doesn't have geofence
            Call.booked.is_(True),     # Is booked
            Call.cancelled.is_(False)  # Not cancelled
        )
        
        # Add company filter if provided
        if company_id:
            query = query.filter(Call.company_id == company_id)
        
        # Get calls to geocode
        calls_to_geocode = query.limit(limit).all()
        
        if not calls_to_geocode:
            return {
                "status": "success",
                "message": "No calls found that need geocoding",
                "geocoded_count": 0
            }
        
        # Queue the geocoding tasks in the background
        geocoded_count = 0
        
        # For immediate feedback, geocode the first 10 synchronously
        immediate_count = min(10, len(calls_to_geocode))
        immediate_calls = calls_to_geocode[:immediate_count]
        
        for call_record in immediate_calls:
            result = await create_geofence_for_call(call_record.call_id, db)
            if result:
                geocoded_count += 1
                
                # Also add the geofence to the assigned rep if one exists
                if call_record.assigned_rep_id:
                    try:
                        # Get the sales rep
                        sales_rep = db.query(SalesRep).filter(SalesRep.user_id == call_record.assigned_rep_id).first()
                        if sales_rep:
                            # Update sales rep's active geofences
                            active_geofences = sales_rep.active_geofences or []
                            
                            # If not a list, initialize as empty list
                            if not isinstance(active_geofences, list):
                                active_geofences = []
                            
                            # Add new geofence if not already in the list
                            if not any(g.get("call_id") == str(call_record.call_id) for g in active_geofences):
                                active_geofences.append(result)
                                
                                # Keep only the most recent geofences (max 20)
                                if len(active_geofences) > 20:
                                    active_geofences = sorted(active_geofences, key=lambda g: g.get("created_at", ""), reverse=True)[:20]
                                
                                # Update sales rep
                                sales_rep.active_geofences = active_geofences
                                db.commit()
                    except Exception as rep_error:
                        logger.error(f"Error updating rep geofences for call {call_record.call_id}: {rep_error}")
        
        # Process the rest in the background
        remaining_calls = calls_to_geocode[immediate_count:]
        for call_record in remaining_calls:
            background_tasks.add_task(create_geofence_for_call, call_record.call_id, db)
        
        return {
            "status": "success",
            "message": f"Geocoding {len(calls_to_geocode)} calls ({immediate_count} immediate, {len(remaining_calls)} in background)",
            "immediate_geocoded_count": geocoded_count,
            "total_queued": len(calls_to_geocode)
        }
    except Exception as e:
        logger.error(f"Error in bulk geocoding: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing bulk geocoding: {str(e)}")

@router.post("/sync-rep-geofences")
async def sync_sales_rep_geofences(
    data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Sync a sales rep's active_geofences list to match all their assigned calls.
    
    This ensures a rep has all the geofences they should be monitoring and no extras.
    """
    try:
        rep_id = data.get("rep_id")
        if not rep_id:
            raise HTTPException(status_code=400, detail="rep_id is required")
        
        success = await sync_rep_geofences(rep_id, db)
        if not success:
            raise HTTPException(status_code=404, detail=f"Failed to sync geofences for rep {rep_id}")
        
        # Get updated sales rep to return current geofence count
        sales_rep = db.query(SalesRep).filter(SalesRep.user_id == rep_id).first()
        geofence_count = len(sales_rep.active_geofences) if sales_rep.active_geofences else 0
        
        return {
            "status": "success",
            "message": f"Successfully synced geofences for rep {rep_id}",
            "geofence_count": geofence_count
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing rep geofences: {e}")
        raise HTTPException(status_code=500, detail=f"Error syncing rep geofences: {str(e)}")

@router.post("/sync-all-reps-geofences")
async def sync_all_reps_geofences(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    company_id: Optional[str] = None
):
    """
    Sync active_geofences for all sales reps based on their assigned calls.
    
    This ensures all reps have the correct geofences they should be monitoring.
    """
    try:
        # Build query for sales reps
        query = db.query(SalesRep)
        
        # Add company filter if provided
        if company_id:
            query = query.filter(SalesRep.company_id == company_id)
        
        # Get all sales reps
        sales_reps = query.all()
        
        if not sales_reps:
            return {
                "status": "success",
                "message": "No sales reps found to sync",
                "reps_count": 0
            }
        
        # Sync first few reps immediately for feedback
        immediate_count = min(5, len(sales_reps))
        immediate_reps = sales_reps[:immediate_count]
        synced_count = 0
        
        for rep in immediate_reps:
            success = await sync_rep_geofences(rep.user_id, db)
            if success:
                synced_count += 1
        
        # Process the rest in the background
        remaining_reps = sales_reps[immediate_count:]
        for rep in remaining_reps:
            background_tasks.add_task(sync_rep_geofences, rep.user_id, db)
        
        return {
            "status": "success",
            "message": f"Syncing geofences for {len(sales_reps)} reps ({immediate_count} immediate, {len(remaining_reps)} in background)",
            "immediate_synced_count": synced_count,
            "total_reps": len(sales_reps)
        }
    except Exception as e:
        logger.error(f"Error syncing all reps geofences: {e}")
        raise HTTPException(status_code=500, detail=f"Error syncing all reps geofences: {str(e)}") 