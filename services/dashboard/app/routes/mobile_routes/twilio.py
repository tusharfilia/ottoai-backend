from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from typing import Dict, Optional
import requests
import os
import sys
from app.database import get_db
from app.models import call, company
from app.models.user import User
from datetime import datetime
import logging
from pydantic import BaseModel
from twilio.rest import Client
from twilio.request_validator import RequestValidator
import json
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse, Dial
from app.services.idempotency import with_idempotency

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

router = APIRouter()

# Twilio credentials from environment variables
from app.config import settings

TWILIO_ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
TWILIO_PHONE_NUMBER = settings.TWILIO_FROM_NUMBER

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

class TwilioTextRequest(BaseModel):
    """Structure for text message request data"""
    customer_phone_number: str
    message: str
    company_id: str
    call_id: int

class TwilioCallRequest(BaseModel):
    """Structure for call request data"""
    rep_phone_number: str
    customer_phone_number: str
    company_id: str
    call_id: int

@router.post("/twilio-send-text")
async def send_text_message(
    text_data: TwilioTextRequest,
    db: Session = Depends(get_db)
):
    """Sends a text message via Twilio API and stores it in the text_messages field."""
    try:
        # Initialize Twilio client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        # Send the message
        twilio_message = client.messages.create(
            body=text_data.message,
            from_=TWILIO_PHONE_NUMBER,
            to=text_data.customer_phone_number
        )

        # Find and update the call record
        existing_call = db.query(call.Call).filter_by(call_id=text_data.call_id).first()
        if not existing_call:
            raise HTTPException(status_code=404, detail="Call not found")

        # Update messages
        current_messages = json.loads(existing_call.text_messages) if existing_call.text_messages else []
        current_messages.append({
            "timestamp": datetime.utcnow().isoformat(),
            "message": text_data.message,
            "direction": "outbound",
            "provider": "twilio",
            "message_sid": twilio_message.sid
        })
        existing_call.text_messages = json.dumps(current_messages)
        
        # Increment text message count
        existing_call.mobile_texts_count = (existing_call.mobile_texts_count or 0) + 1
        
        db.commit()

        return {
            "success": True,
            "call_id": existing_call.call_id,
            "message": "Text message sent successfully"
        }

    except Exception as e:
        logger.exception("Error sending text message")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/twilio-initiate-call")
async def initiate_call(
    call_data: TwilioCallRequest,
    db: Session = Depends(get_db)
):
    """Initiates a call using Twilio connecting rep and customer through a Twilio number"""
    try:
        # Initialize Twilio client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Get the base URL for callbacks
        API_URL = os.getenv("API_URL", "https://tv-mvp-test.fly.dev")
        
        # Create a call that first dials the rep
        # When rep answers, the webhook will connect to the customer
        call_instance = client.calls.create(
            to=call_data.rep_phone_number,
            from_=TWILIO_PHONE_NUMBER,
            url=f"{API_URL}/mobile/twilio-call-connect?customer_number={call_data.customer_phone_number}&call_id={call_data.call_id}",
            status_callback=f"{API_URL}/mobile/twilio-call-status",
            status_callback_event=['initiated', 'answered', 'completed'],
            status_callback_method='POST',
        )
        
        # Find and update the call record
        existing_call = db.query(call.Call).filter_by(call_id=call_data.call_id).first()
        if not existing_call:
            raise HTTPException(status_code=404, detail="Call not found")

        # Update call record with call SID
        existing_call.call_sid = call_instance.sid
        existing_call.last_call_status = "initiated"
        existing_call.last_call_timestamp = datetime.utcnow().isoformat()
        
        # Increment mobile call count
        existing_call.mobile_calls_count = (existing_call.mobile_calls_count or 0) + 1
        
        db.commit()
        
        return {
            "success": True,
            "call_id": existing_call.call_id,
            "call_sid": call_instance.sid,
            "status": "initiated",
            "message": "Call initiated successfully"
        }

    except Exception as e:
        logger.exception("Error initiating call")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/twilio-call-connect")
async def connect_call(
    request: Request,
    customer_number: str,
    call_id: int,
    db: Session = Depends(get_db)
):
    """Webhook for when the rep answers - connects to customer"""
    try:
        # Create TwiML response to dial the customer
        response = VoiceResponse()
        
        # Let the rep know who they're calling
        response.say("Connecting you with your customer now.")
        
        # Create a dial element
        dial = Dial(
            caller_id=TWILIO_PHONE_NUMBER,  # Customer will see the Twilio number, not rep's number
            record='record-from-answer',
            timeout=20,
            recording_status_callback=f"{os.getenv('API_URL', 'https://tv-mvp-test.fly.dev')}/mobile/twilio-recording-callback",
            recording_status_callback_method='POST'
        )
        
        # Add the customer's number to the dial
        dial.number(customer_number)
        
        # Add the dial to the response
        response.append(dial)
        
        # Update call status in database
        existing_call = db.query(call.Call).filter_by(call_id=call_id).first()
        if existing_call:
            existing_call.last_call_status = "in-progress"
            existing_call.last_call_timestamp = datetime.utcnow().isoformat()
            db.commit()
            
        return Response(content=str(response), media_type="application/xml")
        
    except Exception as e:
        logger.exception("Error in call connect webhook")
        # Return basic TwiML in case of error
        response = VoiceResponse()
        response.say("We're sorry, there was an error connecting your call.")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

@router.post("/twilio-call-status")
async def call_status_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """Receives and records call status updates from Twilio"""
    # Get form data from the request
    form = await request.form()
    
    # Extract relevant details
    call_sid = form.get('CallSid', '')
    call_status = form.get('CallStatus', '')
    call_duration = form.get('CallDuration', '0')
    
    # Extract tenant_id from middleware (for webhooks, we may need to derive from call_sid)
    tenant_id = getattr(request.state, 'tenant_id', None)
    if not tenant_id:
        # For webhooks, we might need to derive tenant from call_sid or use a default
        # This is a limitation - webhooks don't have JWT tokens
        tenant_id = "webhook_tenant"  # TODO: Implement proper tenant resolution for webhooks
    
    # Derive external_id from Twilio payload - use CallSid for call status
    external_id = call_sid
    
    def process_webhook():
        # Find the call record by call_sid
        call_record = db.query(call.Call).filter_by(call_sid=call_sid).first()
        
        if call_record:
            # Update call status 
            call_record.last_call_status = call_status
            call_record.last_call_timestamp = datetime.utcnow().isoformat()
            
            # If call completed, record duration
            if call_status == 'completed':
                call_record.last_call_duration = int(call_duration)
                
            db.commit()
            logger.info(f"Call status updated for call_id {call_record.call_id}: {call_status}")
            return {"status": "updated", "call_id": call_record.call_id}
        else:
            logger.warning(f"No call record found for call_sid: {call_sid}")
            return {"status": "not_found", "call_sid": call_sid}
    
    # Apply idempotency protection
    response_data, status_code = with_idempotency(
        provider="twilio",
        external_id=external_id,
        tenant_id=tenant_id,
        process_fn=process_webhook,
        trace_id=getattr(request.state, 'trace_id', None)
    )
    
    return Response(status_code=status_code)

@router.post("/twilio-recording-callback")
async def recording_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """Receives recording status and URL from Twilio and processes the transcript using Deepgram"""
    # Get form data from the request
    form = await request.form()
    form_dict = dict(form)
    
    # Log the callback data
    logger.info(f"Received Twilio recording callback: {form_dict}")
    
    # Extract relevant details
    recording_sid = form.get('RecordingSid', '')
    recording_status = form.get('RecordingStatus', '')
    recording_url = form.get('RecordingUrl', '')
    call_sid = form.get('CallSid', '')
    recording_duration = form.get('RecordingDuration', '0')
    
    # Extract tenant_id from middleware
    tenant_id = getattr(request.state, 'tenant_id', None)
    if not tenant_id:
        tenant_id = "webhook_tenant"  # TODO: Implement proper tenant resolution for webhooks
    
    # Derive external_id from Twilio payload - use RecordingSid for recording callbacks
    external_id = recording_sid or f"recording-{call_sid}"
    
    def process_webhook():
        # Only process completed recordings
        if recording_status != 'completed' or not recording_url:
            logger.info(f"Recording not completed or no URL provided. Status: {recording_status}")
            return {"status": "skipped", "reason": "not_completed"}
        
        # Find the call record by call_sid
        call_record = db.query(call.Call).filter_by(call_sid=call_sid).first()
        if not call_record:
            logger.warning(f"No call record found for call_sid: {call_sid}")
            return {"status": "not_found", "call_sid": call_sid}

        # Format time and duration for display
        call_timestamp = datetime.utcnow().isoformat()
        call_duration_mins = int(recording_duration) // 60
        call_duration_secs = int(recording_duration) % 60
        formatted_duration = f"{call_duration_mins}:{call_duration_secs:02d}"
        
        # Download the recording from Twilio
        recording_audio_url = f"{recording_url}.mp3"
        logger.info(f"Downloading recording from: {recording_audio_url}")
        
        recording_response = requests.get(
            recording_audio_url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        )
        
        if not recording_response.ok:
            logger.error(f"Failed to download recording: {recording_response.status_code}")
            
            # Save basic info without transcript
            formatted_transcript = {
                "timestamp": call_timestamp,
                "duration": formatted_duration,
                "call_sid": call_sid,
                "recording_sid": recording_sid,
                "recording_url": recording_url,
                "transcript": "Error downloading recording"
            }
            
            current_transcript = json.loads(call_record.mobile_transcript) if call_record.mobile_transcript else []
            current_transcript.append(formatted_transcript)
            call_record.mobile_transcript = json.dumps(current_transcript)
            db.commit()
            
            return Response(status_code=200)
        
        # Get the Deepgram API key from environment
        DEEPGRAM_API_KEY = settings.DEEPGRAM_API_KEY
            
            # Save recording info without transcript
            formatted_transcript = {
                "timestamp": call_timestamp,
                "duration": formatted_duration,
                "call_sid": call_sid,
                "recording_sid": recording_sid,
                "recording_url": recording_url,
                "transcript": "Deepgram API key not configured"
            }
            
            current_transcript = json.loads(call_record.mobile_transcript) if call_record.mobile_transcript else []
            current_transcript.append(formatted_transcript)
            call_record.mobile_transcript = json.dumps(current_transcript)
            db.commit()
            
            return Response(status_code=200)
        
        try:
            # Send to Deepgram for transcription
            logger.info("Sending recording to Deepgram for transcription")
            
            # Prepare the headers with authentication
            headers = {
                "Authorization": f"Token {DEEPGRAM_API_KEY}",
                "Content-Type": "audio/mp3"
            }
            
            # Set up transcription parameters
            params = {
                "punctuate": "true",
                "diarize": "true", 
                "model": "nova-2",
                "smart_format": "true",
                "utterances": "true"
            }
            
            # Send recording to Deepgram
            deepgram_url = f"{settings.DEEPGRAM_API_BASE_URL}/v1/listen"
            deepgram_response = requests.post(
                deepgram_url,
                headers=headers,
                params=params,
                data=recording_response.content
            )
            
            # Process Deepgram response
            if deepgram_response.ok:
                transcription_data = deepgram_response.json()
                logger.info(f"Received Deepgram response: {transcription_data}")
                
                # Extract transcript
                try:
                    # Try to get the formatted transcript with speaker information
                    transcript_text = transcription_data['results']['channels'][0]['alternatives'][0]['transcript']
                    
                    # If diarization is available, get speaker labels
                    has_speakers = False
                    if 'utterances' in transcription_data['results']:
                        utterances = transcription_data['results']['utterances']
                        speaker_transcript = []
                        
                        for utterance in utterances:
                            speaker = utterance.get('speaker', 'unknown')
                            text = utterance.get('transcript', '')
                            if text.strip():
                                speaker_transcript.append(f"Speaker {speaker}: {text}")
                        
                        if speaker_transcript:
                            has_speakers = True
                            transcript_text = "\n".join(speaker_transcript)
                    
                    logger.info(f"Successfully transcribed recording with{'out' if not has_speakers else ''} speaker diarization")
                except (KeyError, IndexError) as e:
                    logger.warning(f"Error extracting transcript from Deepgram response: {e}")
                    transcript_text = "Error extracting transcript from Deepgram response"
            else:
                logger.error(f"Deepgram transcription failed: {deepgram_response.status_code}, {deepgram_response.text}")
                transcript_text = f"Transcription failed with status code {deepgram_response.status_code}"
                
            # Store the transcript and recording info
            formatted_transcript = {
                "timestamp": call_timestamp,
                "duration": formatted_duration,
                "call_sid": call_sid,
                "recording_sid": recording_sid,
                "recording_url": recording_url,
                "transcript": transcript_text
            }
            
            # Save to database
            current_transcript = json.loads(call_record.mobile_transcript) if call_record.mobile_transcript else []
            current_transcript.append(formatted_transcript)
            call_record.mobile_transcript = json.dumps(current_transcript)
            db.commit()
            
            logger.info(f"Successfully saved transcript for call_id: {call_record.call_id}")
            return {"status": "processed", "call_id": call_record.call_id}
            
        except Exception as transcript_error:
            logger.exception(f"Error during transcription process: {transcript_error}")
            
            # Save recording info with error message
            formatted_transcript = {
                "timestamp": call_timestamp,
                "duration": formatted_duration,
                "call_sid": call_sid,
                "recording_sid": recording_sid,
                "recording_url": recording_url,
                "transcript": f"Error during transcription: {str(transcript_error)}"
            }
            
            current_transcript = json.loads(call_record.mobile_transcript) if call_record.mobile_transcript else []
            current_transcript.append(formatted_transcript)
            call_record.mobile_transcript = json.dumps(current_transcript)
            db.commit()
            
            return {"status": "error", "call_id": call_record.call_id, "error": str(transcript_error)}
    
    # Apply idempotency protection
    response_data, status_code = with_idempotency(
        provider="twilio",
        external_id=external_id,
        tenant_id=tenant_id,
        process_fn=process_webhook,
        trace_id=getattr(request.state, 'trace_id', None)
    )
    
    return Response(status_code=status_code)

@router.post("/twilio-webhook")
async def handle_incoming_message(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handles incoming messages from Twilio webhook"""
    # Validate the request is from Twilio
    url = str(request.url)
    form = await request.form()
    form_dict = dict(form)
    signature = request.headers.get("X-Twilio-Signature", "")
    
    validator = RequestValidator(TWILIO_AUTH_TOKEN)
    is_valid = validator.validate(url, form_dict, signature)
    if not is_valid:
        logger.warning("Invalid Twilio signature")
        return Response(status_code=403)

    # Extract message details
    from_number = form.get('From', '')
    message_body = form.get('Body', '')
    message_sid = form.get('MessageSid', '')
    
    # Extract tenant_id from middleware
    tenant_id = getattr(request.state, 'tenant_id', None)
    if not tenant_id:
        tenant_id = "webhook_tenant"  # TODO: Implement proper tenant resolution for webhooks
    
    # Derive external_id from Twilio payload - use MessageSid for SMS webhooks
    external_id = message_sid
    
    def process_webhook():
        
        # Try different phone number formats
        phone_formats = [
            from_number,
            from_number.lstrip('+'),
            '+' + from_number.lstrip('+'),
            '1' + from_number.lstrip('+').removeprefix('1'),
            '+1' + from_number.lstrip('+').removeprefix('1')
        ]
        
        # Find matching call record
        call_record = None
        for phone_format in phone_formats:
            call_record = db.query(call.Call).filter_by(phone_number=phone_format).order_by(call.Call.created_at.desc()).first()
            if call_record:
                break

        if call_record:
            # Update messages
            current_messages = json.loads(call_record.text_messages) if call_record.text_messages and call_record.text_messages.strip() else []
            current_messages.append({
                "timestamp": datetime.utcnow().isoformat(),
                "message": message_body,
                "direction": "inbound",
                "provider": "twilio",
                "message_sid": message_sid
            })
            call_record.text_messages = json.dumps(current_messages)
            
            # Increment text message count for incoming messages
            call_record.mobile_texts_count = (call_record.mobile_texts_count or 0) + 1
            
            db.commit()
            logger.info(f"Message saved for call_id: {call_record.call_id}")
            return {"status": "processed", "call_id": call_record.call_id}
        else:
            logger.warning(f"No call found for number: {from_number}")
            return {"status": "not_found", "from_number": from_number}
    
    # Apply idempotency protection
    response_data, status_code = with_idempotency(
        provider="twilio",
        external_id=external_id,
        tenant_id=tenant_id,
        process_fn=process_webhook,
        trace_id=getattr(request.state, 'trace_id', None)
    )
    
    # Return empty TwiML response (Twilio expects this format)
    response = MessagingResponse()
    return Response(content=str(response), media_type="application/xml")

@router.get("/messages/{call_id}")
async def get_messages(
    call_id: int,
    db: Session = Depends(get_db)
):
    """Retrieves message history for a specific call"""
    try:
        call_record = db.query(call.Call).filter_by(call_id=call_id).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call not found")
            
        messages = json.loads(call_record.text_messages) if call_record.text_messages else []
        
        formatted_messages = [{
            'message': msg['message'],
            'direction': msg['direction'],
            'timestamp': datetime.fromisoformat(msg['timestamp']).strftime('%Y-%m-%d %I:%M %p'),
            'raw_timestamp': msg['timestamp']
        } for msg in messages]
        
        return {
            'call': {
                'id': call_record.call_id,
                'name': call_record.name,
                'address': call_record.address,
                'phone': call_record.phone_number,
                'mobile_texts_count': call_record.mobile_texts_count or 0,
                'mobile_calls_count': call_record.mobile_calls_count or 0
            },
            'messages': formatted_messages
        }
        
    except Exception as e:
        logger.exception(f"Error getting messages for call_id {call_id}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/call-transcripts/{call_id}")
async def get_call_transcripts(
    call_id: int,
    db: Session = Depends(get_db)
):
    """Retrieves mobile call transcripts for a specific call"""
    try:
        call_record = db.query(call.Call).filter_by(call_id=call_id).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call not found")
            
        transcripts = json.loads(call_record.mobile_transcript) if call_record.mobile_transcript else []
        
        return {
            'call': {
                'id': call_record.call_id,
                'name': call_record.name,
                'phone': call_record.phone_number
            },
            'transcripts': transcripts
        }
        
    except Exception as e:
        logger.exception(f"Error getting call transcripts for call_id {call_id}")
        raise HTTPException(status_code=500, detail=str(e)) 