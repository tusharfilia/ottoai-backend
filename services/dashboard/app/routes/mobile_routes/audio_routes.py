from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
import os
import uuid
from datetime import datetime
import asyncio
from deepgram import Deepgram
import json
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models.call import Call
from app.models.transcript_analysis import TranscriptAnalysis
from app.services.transcript_analysis import TranscriptAnalyzer
import logging

router = APIRouter(prefix="/audio", tags=["audio"])

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Deepgram client with environment variable
DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')
if not DEEPGRAM_API_KEY:
    raise ValueError("DEEPGRAM_API_KEY environment variable is not set")

deepgram = Deepgram(DEEPGRAM_API_KEY)

# In-memory storage for transcripts (replace with database in production)
transcripts = {}

@router.post("/start-recording")
async def start_recording(
    trigger_type: str,  # "location", "time", "both", or "manual"
    call_id: int,
    scheduled_time: Optional[datetime] = None,
    location_trigger: Optional[dict] = None,
    battery_percentage: Optional[int] = None,
    is_charging: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    Initialize a recording session
    """
    recording_id = str(uuid.uuid4())
    
    logger.info(f"Starting recording with trigger_type={trigger_type}, call_id={call_id}")
    
    # Store recording info in memory
    transcripts[recording_id] = {
        "status": "pending",
        "trigger_type": trigger_type,
        "scheduled_time": scheduled_time,
        "location_trigger": location_trigger,
        "call_id": call_id,
        "created_at": datetime.utcnow()
    }
    
    # Update the call record to track recording started
    try:
        call = db.query(Call).filter(Call.call_id == call_id).first()
        if call:
            # Set recording start time
            now = datetime.utcnow()
            call.recording_started_ts = now
            
            # Track battery status
            if battery_percentage is not None:
                call.battery_at_recording_start = battery_percentage
            if is_charging is not None:
                call.charging_at_recording_start = is_charging
                
            # Calculate time to start recording if there was a geofence entry
            if call.geofence_entry_1_ts:
                time_diff_seconds = (now - call.geofence_entry_1_ts).total_seconds()
                call.time_to_start_recording_s = int(time_diff_seconds)
                
            db.commit()
            logger.info(f"Updated call {call_id} with recording start info")
    except Exception as e:
        logger.error(f"Error updating call record: {e}")
    
    return {"recording_id": recording_id}

@router.post("/upload/{recording_id}")
async def upload_audio(
    recording_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload audio file and process it with Deepgram
    """
    if recording_id not in transcripts:
        raise HTTPException(status_code=404, detail="Recording session not found")
    
    # Save the uploaded file temporarily
    temp_path = f"/tmp/{recording_id}_{file.filename}"
    try:
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Process audio in background
        background_tasks.add_task(process_audio, recording_id, temp_path, db)
        
        # Update call with recording stopped timestamp
        try:
            call_id = transcripts[recording_id].get("call_id")
            if call_id:
                call = db.query(Call).filter(Call.call_id == call_id).first()
                if call:
                    now = datetime.utcnow()
                    call.recording_stopped_ts = now
                    
                    # Calculate recording duration if we have a start time
                    if call.recording_started_ts:
                        duration_seconds = (now - call.recording_started_ts).total_seconds()
                        call.recording_duration_s = int(duration_seconds)
                        
                    db.commit()
                    logger.info(f"Updated call {call_id} with recording stop info")
        except Exception as e:
            logger.error(f"Error updating call record on upload: {e}")
        
        return {"status": "processing", "recording_id": recording_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def format_transcript_for_llm(transcript: dict) -> str:
    """
    Format the Deepgram transcript into a clean format for LLM processing
    Returns a conversation in a clear speaker-by-speaker format with timestamps
    """
    try:
        formatted_transcript = []
        
        # Log the structure of the transcript for debugging
        logger.info(f"Transcript structure: Keys at top level: {list(transcript.keys())}")
        if 'results' in transcript:
            logger.info(f"Results keys: {list(transcript['results'].keys())}")
        
        # Check if we have utterances in the response
        if 'results' in transcript and 'utterances' in transcript['results']:
            utterances = transcript['results']['utterances']
            logger.info(f"Processing {len(utterances)} utterances from Deepgram response")
            
            for i, utterance in enumerate(utterances):
                speaker = f"Speaker {utterance.get('speaker', i)}"
                start_time = utterance.get('start', 0)
                end_time = utterance.get('end', 0)
                duration = end_time - start_time
                
                formatted_transcript.append(
                    f"{speaker} [{format_timestamp(start_time)} - {format_timestamp(end_time)}, duration: {duration:.2f}s]: {utterance.get('transcript', '')}"
                )
        # Fall back to paragraphs if utterances aren't available
        elif 'results' in transcript and 'channels' in transcript['results']:
            logger.info("No utterances found, falling back to paragraphs")
            
            # First try to get paragraphs
            try:
                paragraphs = transcript['results']['channels'][0]['alternatives'][0].get('paragraphs', {}).get('paragraphs', [])
                if paragraphs:
                    logger.info(f"Found {len(paragraphs)} paragraphs")
                    for i, paragraph in enumerate(paragraphs):
                        speaker = f"Speaker {paragraph.get('speaker', i)}"
                        start_time = paragraph.get('start', 0)
                        end_time = paragraph.get('end', 0)
                        duration = end_time - start_time
                        
                        formatted_transcript.append(
                            f"{speaker} [{format_timestamp(start_time)} - {format_timestamp(end_time)}, duration: {duration:.2f}s]: {paragraph.get('text', '')}"
                        )
                else:
                    # If no paragraphs, try to get the full transcript text
                    logger.info("No paragraphs found, falling back to full transcript")
                    text = transcript['results']['channels'][0]['alternatives'][0].get('transcript', '')
                    formatted_transcript.append(f"Transcript: {text}")
            except (KeyError, IndexError) as e:
                logger.warning(f"Error extracting paragraphs: {e}")
                # Try to get the full transcript
                try:
                    text = transcript['results']['channels'][0]['alternatives'][0].get('transcript', '')
                    formatted_transcript.append(f"Transcript: {text}")
                except (KeyError, IndexError):
                    formatted_transcript.append("Could not extract transcript text")
        # Fall back to raw transcript if all else fails
        else:
            logger.warning("Could not find expected structure in Deepgram response")
            try:
                text = transcript.get('results', {}).get('channels', [{}])[0].get('alternatives', [{}])[0].get('transcript', '')
                formatted_transcript.append(f"Transcript: {text}")
            except (KeyError, IndexError):
                formatted_transcript.append("Could not extract any transcript text from response")
        
        result = "\n\n".join(formatted_transcript)
        return result
    except Exception as e:
        logger.error(f"Error formatting transcript: {e}", exc_info=True)
        # Return a simplified version of the transcript if formatting fails
        try:
            return json.dumps(transcript, indent=2)
        except:
            return "Error formatting transcript"

def format_timestamp(seconds: float) -> str:
    """Format seconds into MM:SS format"""
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes:02d}:{seconds:02d}"

async def process_audio(recording_id: str, audio_path: str, db: Session):
    """
    Process audio with Deepgram and store results
    """
    try:
        with open(audio_path, "rb") as audio:
            source = {"buffer": audio, "mimetype": "audio/wav"}
            response = await deepgram.transcription.prerecorded(
                source,
                {
                    "model": "nova-2",
                    "punctuate": True,
                    "diarize": True,
                    "smart_format": True,
                    "numerals": True,
                    "paragraphs": True
                }
            )
            
            # Log the raw Deepgram response
            logger.info(f"Raw Deepgram response for recording {recording_id}: {json.dumps(response)}")
            
            # Store raw transcript
            transcripts[recording_id]["transcript"] = response
            
            # Extract the formatted transcript with speaker information
            transcript_text = ""
            if 'results' in response and 'channels' in response['results']:
                alternatives = response['results']['channels'][0]['alternatives']
                if alternatives and 'paragraphs' in alternatives[0]:
                    # Get the nicely formatted transcript with speaker information
                    transcript_text = alternatives[0]['paragraphs']['transcript']
                else:
                    # Fall back to regular transcript
                    transcript_text = alternatives[0].get('transcript', '')
            else:
                transcript_text = "Could not extract transcript text"
            
            transcripts[recording_id]["formatted_transcript"] = transcript_text
            
            # Log the transcript
            logger.info(f"Transcript for recording {recording_id}: {transcript_text}")
            
            # Update status
            transcripts[recording_id]["status"] = "completed"
            
            # If this recording is associated with a call, store it in the database
            call_id = transcripts[recording_id].get("call_id")
            logger.info(f"Looking for call with ID: {call_id}")
            
            if call_id:
                try:
                    # Find the call record
                    logger.info(f"Attempting to find call with ID {call_id} in the database")
                    call = db.query(Call).filter(Call.call_id == call_id).first()
                    
                    if call:
                        logger.info(f"Found call with ID {call_id}, updating with transcript")
                        # Update existing call record with in-person transcript
                        call.in_person_transcript = transcript_text
                        call.updated_at = datetime.utcnow()
                        
                        db.commit()
                        logger.info(f"Database updated successfully for call ID {call_id}")
                        transcripts[recording_id]["call_id"] = call.call_id
                        
                        # Automatically analyze the transcript and update call fields
                        try:
                            logger.info(f"Automatically analyzing transcript and updating call fields for call ID {call_id}")
                            
                            # Initialize the analyzer with the default process
                            analyzer = TranscriptAnalyzer(process_name="v0")
                            
                            # Run the analysis
                            analysis_result = analyzer.analyze_and_store(call_id, db)
                            
                            if "error" not in analysis_result:
                                logger.info(f"Successfully analyzed transcript for call ID {call_id}")
                            else:
                                logger.error(f"Error analyzing transcript: {analysis_result['error']}")
                                
                        except Exception as e:
                            logger.error(f"Error in automatic transcript analysis: {e}", exc_info=True)
                    else:
                        logger.warning(f"Call with ID {call_id} not found in database")
                        transcripts[recording_id]["error"] = f"Call with ID {call_id} not found"
                except Exception as db_error:
                    logger.error(f"Database error for call ID {call_id}: {db_error}", exc_info=True)
                    transcripts[recording_id]["db_error"] = str(db_error)
            else:
                logger.warning(f"No call_id provided for recording {recording_id}")
            
            # TODO: Add LLM processing for fraud detection/summarization
            
    except Exception as e:
        transcripts[recording_id]["status"] = "error"
        transcripts[recording_id]["error"] = str(e)
    finally:
        # Clean up temporary file
        if os.path.exists(audio_path):
            os.remove(audio_path)

@router.get("/status/{recording_id}")
async def get_status(recording_id: str):
    """
    Get the status and transcript of a recording
    """
    if recording_id not in transcripts:
        raise HTTPException(status_code=404, detail="Recording session not found")
    
    return transcripts[recording_id]

@router.get("/raw-data/{recording_id}")
async def get_raw_transcript(recording_id: str):
    """
    Get the raw deepgram transcript data for debugging purposes
    """
    if recording_id not in transcripts:
        raise HTTPException(status_code=404, detail="Recording session not found")
    
    if "transcript" not in transcripts[recording_id]:
        return {"status": "no_transcript", "message": "No transcript data available yet"}
    
    # Return the raw transcript data
    return {
        "raw_transcript": transcripts[recording_id]["transcript"],
        "formatted_transcript": transcripts[recording_id].get("formatted_transcript"),
        "status": transcripts[recording_id]["status"]
    }

@router.post("/analyze-transcript/{call_id}")
async def analyze_transcript(
    call_id: int,
    company_id: str,
    background_tasks: BackgroundTasks,
    process_name: str = "v0",
    run_in_background: bool = False,
    db: Session = Depends(get_db)
):
    """
    Analyze the transcript for a call using LLM and store the structured data.
    
    Args:
        call_id: ID of the call to analyze
        company_id: ID of the company that owns the call
        background_tasks: FastAPI background tasks handler
        process_name: Name of the analysis process to use (default: "v0")
        run_in_background: Whether to run the analysis as a background task
        
    Returns:
        The analysis result or a status message if running in the background
    """
    # Get call details
    call = db.query(Call).filter(Call.call_id == call_id, Call.company_id == company_id).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Check if we have any transcript to analyze
    has_transcript = bool(call.transcript or call.in_person_transcript or call.mobile_transcript)
    if not has_transcript:
        raise HTTPException(status_code=400, detail="No transcript available for analysis")
    
    # Initialize the analyzer with the specified process
    try:
        analyzer = TranscriptAnalyzer(process_name=process_name)
    except ValueError as e:
        # Handle invalid process name
        available_processes = TranscriptAnalyzer.get_available_processes()
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid analysis process: {process_name}. Available processes: {available_processes}"
        )
    
    # Handle as background task if requested
    if run_in_background:
        # Schedule the analysis as a background task
        background_tasks.add_task(analyzer.analyze_and_store, call_id, db, process_name)
        return {
            "status": "processing", 
            "message": f"Analysis scheduled as background task using process: {process_name}",
            "call_id": call_id
        }
    else:
        # Run analysis immediately
        result = analyzer.analyze_and_store(call_id, db, process_name)
        
        # Check for errors
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "status": "success",
            "call_id": call_id,
            "process": process_name,
            "analysis": result
        }

@router.get("/analysis-processes")
async def get_available_analysis_processes():
    """
    Get a list of available transcript analysis processes.
    
    Returns:
        List of available process names
    """
    from app.services.transcript_analysis import TranscriptAnalyzer
    
    processes = TranscriptAnalyzer.get_available_processes()
    
    # Get descriptions for each process
    process_details = []
    for process_name in processes:
        try:
            analyzer = TranscriptAnalyzer(process_name=process_name)
            description = analyzer.process.description
        except:
            description = "No description available"
            
        process_details.append({
            "name": process_name,
            "description": description
        })
    
    return {"processes": process_details}

@router.get("/transcript-analysis/{call_id}")
async def get_transcript_analysis(
    call_id: int,
    company_id: str,
    version: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Get the transcript analysis for a call.
    
    Args:
        call_id: ID of the call
        company_id: ID of the company that owns the call
        version: Optional specific version of the analysis to retrieve
        
    Returns:
        The analysis result
    """
    # Verify the call exists and belongs to the company
    call = db.query(Call).filter(Call.call_id == call_id, Call.company_id == company_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Build query for the analysis
    query = db.query(TranscriptAnalysis).filter(TranscriptAnalysis.call_id == call_id)
    
    # If version is specified, filter by version
    if version is not None:
        query = query.filter(TranscriptAnalysis.analysis_version == version)
        analysis = query.first()
        if not analysis:
            raise HTTPException(status_code=404, detail=f"Analysis version {version} not found")
    else:
        # Otherwise, get the latest version
        analysis = query.order_by(TranscriptAnalysis.analysis_version.desc()).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="No analysis found for this call")
    
    # Format the response
    response = {
        "analysis_id": analysis.analysis_id,
        "call_id": analysis.call_id,
        "created_at": analysis.created_at.isoformat(),
        "model_version": analysis.model_version,
        "analysis_version": analysis.analysis_version,
        "greeting": analysis.greeting,
        "customer_decision": analysis.customer_decision,
        "quoted_price": analysis.quoted_price,
        "company_mentions": analysis.company_mentions,
        "farewell": analysis.farewell,
        # Include detailed fields
        "details": {
            "rep_greeting": {
                "quote": analysis.rep_greeting_quote,
                "timestamp": analysis.rep_greeting_timestamp
            },
            "rep_introduction": {
                "quote": analysis.rep_introduction_quote,
                "timestamp": analysis.rep_introduction_timestamp
            },
            "company_mention": {
                "quote": analysis.company_mention_quote,
                "timestamp": analysis.company_mention_timestamp,
                "count": analysis.company_mention_count
            },
            "price_quote": {
                "quote": analysis.price_quote,
                "timestamp": analysis.price_quote_timestamp,
                "amount": analysis.price_amount
            },
            "payment_discussion": {
                "quote": analysis.payment_discussion_quote,
                "timestamp": analysis.payment_discussion_timestamp
            },
            "discount_mention": {
                "quote": analysis.discount_mention_quote,
                "timestamp": analysis.discount_mention_timestamp
            },
            "customer_decision": {
                "quote": analysis.customer_decision_quote,
                "timestamp": analysis.customer_decision_timestamp,
                "status": analysis.customer_decision_status
            },
            "agreement_mention": {
                "quote": analysis.agreement_mention_quote,
                "timestamp": analysis.agreement_mention_timestamp
            },
            "goodbye": {
                "quote": analysis.goodbye_quote,
                "timestamp": analysis.goodbye_timestamp
            },
            "follow_up": {
                "quote": analysis.follow_up_quote,
                "timestamp": analysis.follow_up_timestamp,
                "date": analysis.follow_up_date
            },
            "document_sending": {
                "quote": analysis.document_sending_quote,
                "timestamp": analysis.document_sending_timestamp,
                "type": analysis.document_type
            },
            "paperwork_mention": {
                "quote": analysis.paperwork_mention_quote,
                "timestamp": analysis.paperwork_mention_timestamp
            }
        }
    }
    
    return response

@router.get("/transcript-analyses/{call_id}/versions")
async def get_analysis_versions(
    call_id: int, 
    company_id: str,
    db: Session = Depends(get_db)
):
    """
    Get all available analysis versions for a call.
    
    Args:
        call_id: ID of the call
        company_id: ID of the company that owns the call
        
    Returns:
        List of available analysis versions with metadata
    """
    # Verify the call exists and belongs to the company
    call = db.query(Call).filter(Call.call_id == call_id, Call.company_id == company_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Get all analyses for this call
    analyses = db.query(TranscriptAnalysis).filter(
        TranscriptAnalysis.call_id == call_id
    ).order_by(TranscriptAnalysis.analysis_version.desc()).all()
    
    if not analyses:
        return {"versions": []}
    
    # Format response
    versions = [
        {
            "analysis_id": analysis.analysis_id,
            "version": analysis.analysis_version,
            "created_at": analysis.created_at.isoformat(),
            "model_version": analysis.model_version
        }
        for analysis in analyses
    ]
    
    return {"versions": versions}

@router.post("/sync-call-fields-from-analysis/{call_id}")
async def sync_call_fields_from_analysis(
    call_id: int,
    company_id: str,
    analysis_version: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Synchronize call table fields with data from the transcript analysis.
    Updates the following call fields:
    - bought
    - price_if_bought
    - reason_for_lost_sale
    - still_deciding
    - reason_for_deciding
    
    Args:
        call_id: ID of the call to update
        company_id: ID of the company that owns the call
        analysis_version: Optional specific version of the analysis to use (uses latest if not specified)
        
    Returns:
        Status of the update operation
    """
    # Verify the call exists and belongs to the company
    call = db.query(Call).filter(Call.call_id == call_id, Call.company_id == company_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Get the appropriate analysis record
    query = db.query(TranscriptAnalysis).filter(TranscriptAnalysis.call_id == call_id)
    if analysis_version:
        # Use the specified version
        analysis = query.filter(TranscriptAnalysis.analysis_version == analysis_version).first()
        if not analysis:
            raise HTTPException(status_code=404, detail=f"Analysis version {analysis_version} not found")
    else:
        # Use the latest version
        analysis = query.order_by(TranscriptAnalysis.analysis_version.desc()).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="No analysis found for this call")
    
    # Get customer decision data
    customer_decision_status = analysis.customer_decision_status
    original_bought = call.bought
    original_still_deciding = call.still_deciding
    
    # Update the fields based on analysis data
    if customer_decision_status:
        if customer_decision_status.lower() == "bought":
            call.bought = True
            call.still_deciding = False
        elif customer_decision_status.lower() == "deciding":
            call.bought = False
            call.still_deciding = True
        elif customer_decision_status.lower() == "rejected":
            call.bought = False
            call.still_deciding = False
    
    # Update price_if_bought if bought
    original_price = call.price_if_bought
    if call.bought and analysis.price_amount:
        try:
            # Remove currency symbols and commas
            price_str = analysis.price_amount.replace("$", "").replace(",", "")
            # Find and extract the numeric part
            import re
            price_match = re.search(r'\d+(\.\d+)?', price_str)
            if price_match:
                price_value = float(price_match.group(0))
                call.price_if_bought = price_value
        except (ValueError, AttributeError, TypeError):
            logger.warning(f"Could not convert price to float: {analysis.price_amount}")
    
    # Update reason_for_lost_sale
    original_lost_reason = call.reason_for_lost_sale
    if not call.bought and not call.still_deciding and analysis.customer_decision_quote:
        call.reason_for_lost_sale = analysis.customer_decision_quote
    
    # Update reason_for_deciding
    original_deciding_reason = call.reason_for_deciding
    if call.still_deciding and analysis.customer_decision_quote:
        call.reason_for_deciding = analysis.customer_decision_quote
    
    # Update timestamp
    call.updated_at = datetime.utcnow()
    
    # Commit changes
    db.commit()
    
    # Return status with changes made
    return {
        "status": "success",
        "call_id": call_id,
        "changes": {
            "bought": {
                "before": original_bought,
                "after": call.bought
            },
            "still_deciding": {
                "before": original_still_deciding,
                "after": call.still_deciding
            },
            "price_if_bought": {
                "before": original_price,
                "after": call.price_if_bought
            },
            "reason_for_lost_sale": {
                "before": original_lost_reason,
                "after": call.reason_for_lost_sale
            },
            "reason_for_deciding": {
                "before": original_deciding_reason,
                "after": call.reason_for_deciding
            }
        },
        "analysis_version": analysis.analysis_version
    }

@router.post("/batch-sync-call-fields")
async def batch_sync_call_fields(
    company_id: str,
    call_ids: Optional[List[int]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: Optional[int] = 100,
    db: Session = Depends(get_db)
):
    """
    Batch update call records with data from their transcript analyses.
    Can filter by specific call IDs, date range, or both.
    
    Args:
        company_id: ID of the company
        call_ids: Optional list of specific call IDs to update
        start_date: Optional start date for filtering calls
        end_date: Optional end date for filtering calls
        limit: Maximum number of calls to process (default: 100)
        
    Returns:
        Summary of the update operation
    """
    # Start with a base query for calls belonging to the company
    query = db.query(Call).filter(Call.company_id == company_id)
    
    # Apply call_ids filter if provided
    if call_ids:
        query = query.filter(Call.call_id.in_(call_ids))
    
    # Apply date range filters if provided
    if start_date:
        query = query.filter(Call.created_at >= start_date)
    if end_date:
        query = query.filter(Call.created_at <= end_date)
    
    # Get calls with in-person transcripts
    query = query.filter(Call.in_person_transcript.isnot(None))
    
    # Apply limit
    calls = query.limit(limit).all()
    
    # Track results
    results = {
        "total_calls": len(calls),
        "updated_calls": 0,
        "skipped_calls": 0,
        "errors": []
    }
    
    # Process each call
    for call in calls:
        try:
            # Find the latest analysis for this call
            analysis = db.query(TranscriptAnalysis).filter(
                TranscriptAnalysis.call_id == call.call_id
            ).order_by(TranscriptAnalysis.analysis_version.desc()).first()
            
            # Skip if no analysis exists
            if not analysis:
                results["skipped_calls"] += 1
                continue
            
            # Store original values
            original_values = {
                "bought": call.bought,
                "still_deciding": call.still_deciding,
                "price_if_bought": call.price_if_bought,
                "reason_for_lost_sale": call.reason_for_lost_sale,
                "reason_for_deciding": call.reason_for_deciding
            }
            
            # Update bought and still_deciding based on customer_decision_status
            customer_decision_status = analysis.customer_decision_status
            if customer_decision_status:
                if customer_decision_status.lower() == "bought":
                    call.bought = True
                    call.still_deciding = False
                elif customer_decision_status.lower() == "deciding":
                    call.bought = False
                    call.still_deciding = True
                elif customer_decision_status.lower() == "rejected":
                    call.bought = False
                    call.still_deciding = False
            
            # Update price_if_bought if bought
            if call.bought and analysis.price_amount:
                try:
                    # Remove currency symbols and commas
                    price_str = analysis.price_amount.replace("$", "").replace(",", "")
                    # Find and extract the numeric part
                    import re
                    price_match = re.search(r'\d+(\.\d+)?', price_str)
                    if price_match:
                        price_value = float(price_match.group(0))
                        call.price_if_bought = price_value
                except (ValueError, AttributeError, TypeError):
                    logger.warning(f"Could not convert price to float for call {call.call_id}: {analysis.price_amount}")
            
            # Update reason_for_lost_sale
            if not call.bought and not call.still_deciding and analysis.customer_decision_quote:
                call.reason_for_lost_sale = analysis.customer_decision_quote
            
            # Update reason_for_deciding
            if call.still_deciding and analysis.customer_decision_quote:
                call.reason_for_deciding = analysis.customer_decision_quote
            
            # Check if any changes were made
            changes_made = False
            for key, original_value in original_values.items():
                current_value = getattr(call, key)
                if current_value != original_value:
                    changes_made = True
                    break
            
            if changes_made:
                # Update timestamp and commit
                call.updated_at = datetime.utcnow()
                results["updated_calls"] += 1
            else:
                results["skipped_calls"] += 1
                
        except Exception as e:
            logger.error(f"Error updating call {call.call_id}: {str(e)}", exc_info=True)
            results["errors"].append({
                "call_id": call.call_id,
                "error": str(e)
            })
    
    # Commit all changes in a single transaction
    db.commit()
    
    return results 