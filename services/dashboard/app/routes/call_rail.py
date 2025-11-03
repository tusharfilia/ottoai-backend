from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from app.database import get_db
from app.models import call, company
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
import requests
from app.services.bland_ai import BlandAI
from app.utils.date_calculator import DateCalculator
from app.routes.dependencies import client, bland_ai, date_calculator
from app.middleware.rate_limiter import limits
from app.services.idempotency import with_idempotency
from app.realtime.bus import emit

router = APIRouter()

@router.post("/pre-call")
@limits(tenant="30/minute")  # Stricter limit for CallRail webhooks
async def pre_call_webhook(request: Request, db: Session = Depends(get_db)):
    # Get query parameters
    params = dict(request.query_params)
    print(params)
    
    # Extract tenant_id from middleware
    tenant_id = getattr(request.state, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Missing tenant context")
    
    # Derive external_id from CallRail payload - use call ID if available
    external_id = params.get("call_id") or f"pre-call-{params.get('trackingnum')}-{params.get('callernum')}"
    
    def process_webhook():
        # For CallRail webhooks, we can determine company by the tracking number
        tracking_number = params.get("trackingnum")

        company_record = db.query(company.Company).filter_by(phone_number=tracking_number).first()
        if not company_record:
            raise HTTPException(status_code=404, detail=f"No company found for tracking number {tracking_number}")
        
        print(f"Company found: {company_record.name} with ID: {company_record.id}")
        
        # Check if caller exists in leads or customers DB by phone number
        caller_phone = params.get("callernum")
        existing_call = db.query(call.Call).filter_by(
            phone_number=caller_phone,
            company_id=company_record.id
        ).first()
        
        if existing_call:
            print(f"Existing call found for {caller_phone}, updating...")
            # Update existing call record
            existing_call.missed_call = params.get("answered", "true").lower() != "true"
            existing_call.updated_at = datetime.utcnow()
            db.commit()
            call_id = existing_call.call_id
        else:
            print(f"New caller {caller_phone}, creating new call record...")
            # Create new call record (auto-creates lead)
            new_call = call.Call(
                phone_number=caller_phone,
                company_id=company_record.id,
                created_at=datetime.utcnow(),
                missed_call=params.get("answered", "true").lower() != "true",
            )
            db.add(new_call)
            db.commit()
            db.refresh(new_call)
            call_id = new_call.call_id
            print(f"New call created: {call_id}")
        
        # Handle missed call SMS if call was not answered
        is_answered = params.get("answered", "true").lower() == "true"
        if not is_answered:
            print(f"Missed call detected for {caller_phone}, sending auto-SMS...")
            try:
                from app.services.twilio_service import twilio_service
                sms_result = twilio_service.send_sms(
                    to=caller_phone,
                    body="Sorry we missed your call! How can we help you today? Reply with your name and we'll get back to you shortly.",
                    from_number=company_record.phone_number
                )
                if sms_result.get("success"):
                    print(f"Auto-SMS sent successfully to {caller_phone}")
                else:
                    print(f"Failed to send auto-SMS: {sms_result.get('error')}")
            except Exception as e:
                print(f"Error sending missed call SMS: {str(e)}")
        
        # Emit real-time event
        emit(
            event_name="telephony.call.received",
            payload={
                "call_id": call_id,
                "phone_number": caller_phone,
                "company_id": str(company_record.id),
                "answered": is_answered
            },
            tenant_id=tenant_id,
            lead_id=call_id
        )
        
        return {"status": "success", "call_id": call_id}
    
    # Apply idempotency protection
    return with_idempotency(
        provider="callrail",
        external_id=external_id,
        tenant_id=tenant_id,
        process_fn=process_webhook,
        trace_id=getattr(request.state, 'trace_id', None)
    )


@router.post("/call-complete")
@limits(tenant="30/minute")  # Stricter limit for CallRail webhooks
async def call_complete_webhook(call_data: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    print("================= CALL COMPLETE WEBHOOK ==================")
    print(call_data)
    
    # Extract tenant_id from middleware (for webhooks, we may need to derive from call_data)
    tenant_id = "webhook_tenant"  # TODO: Implement proper tenant resolution for webhooks
    
    # Derive external_id from CallRail payload - use call ID from payload
    external_id = call_data.get("call", {}).get("id") or f"call-complete-{call_data.get('trackingnum')}-{call_data.get('customer_phone_number')}"
    
    def process_webhook():
        # Use tracking number to identify relevant company 
        tracking_number = call_data.get("trackingnum")
        company_record = db.query(company.Company).filter_by(phone_number=tracking_number).first()
        if not company_record:
            raise HTTPException(status_code=404, detail=f"No company found for tracking number {tracking_number}")
    
    # Use company_id to filter for the correct record (same customer may have called multiple companies)
    call_record = db.query(call.Call)\
        .filter_by(
            company_id=company_record.id,
            phone_number=call_data.get("customer_phone_number")
        )\
        .order_by(call.Call.created_at.desc())\
        .first()
    
    if not call_record:
        raise HTTPException(status_code=404, detail="Call not found")
    print(f"Call record: {call_record.call_id}")
    # Update the call record with company_id
    call_record.company_id = company_record.id
    call_record.transcript = call_data.get("transcription")
    is_answered = call_data.get("answered", True)
    call_record.missed_call = not is_answered
    
    # Route missed calls to missed call queue service
    if not is_answered:
        print(f"⚠️ MISSED CALL DETECTED - Routing to missed call queue")
        from app.services.missed_call_queue_service import MissedCallQueueService
        missed_call_service = MissedCallQueueService()
        background_tasks.add_task(
            missed_call_service.add_missed_call_to_queue,
            call_record.call_id,
            call_record.phone_number,
            call_record.company_id,
            db
        )
        # Update status
        call_record.status = "missed"
    else:
        call_record.status = "completed"
    
    # Extract information using LLM
    if call_data.get("transcription"):
        # First, check if this is a sales-related call
        sales_check_prompt = f"""
        Analyze this conversation transcript where a customer is booking an appointment.
        Respond with just 'true' if it's an appointment, or 'false' if it's not (e.g., customer support, general question,wrong number, etc.). in JSON with the key 'is_sales_call'.
        cancellations and reschedules are technically sales calls as well.
        Transcript:
        {call_data.get("transcription")}
        """

        try:
            sales_check_response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that analyzes conversation transcripts."},
                    {"role": "user", "content": sales_check_prompt}
                ],
                temperature=0.5,
                top_p=0.01
            )
            
            is_sales_call = json.loads(sales_check_response.choices[0].message.content.replace("```json","").replace("```","").strip())['is_sales_call'] == True
            print(is_sales_call)
            
            # Only proceed with information extraction if it's a sales call
            if is_sales_call:
                # Prepare prompt for OpenAI with current date context
                current_date = datetime.now()
                date_prompt = f"""
                Today's date is {current_date.strftime('%A, %B %d, %Y')}.
                Extract information from this transcript into a JSON format with these fields:
                - relative_day: "next", "this", or "last" if mentioned for the quote date
                - weekday: the specific day of week mentioned for the quote date
                - weeks_offset: number of weeks to add/subtract for the quote date
                - days_offset: number of days to add/subtract for the quote date
                - months_offset: number of months to add/subtract for the quote date
                - time: time mentioned (in HH:MM format or as am/pm) for the quote date
                - specific_date: if a specific date is mentioned (YYYY-MM-DD format) for the quote date
                - address: full address mentioned
                - name: customer's name
                - is_booked: true if an appointment was scheduled, false otherwise
                - round_to: minutes to round to (use 60 for hour, 30 for half hour, 15 for quarter hour)
                - problem: a brief description of the customer's issue or service need
                - cancelled: true if appointment was cancelled, false otherwise
                - rescheduled: true if appointment was rescheduled, false otherwise (cancellations are not reschedules, they are different)
                - reason_for_cancellation: reason given for cancellation or rescheduling (null if not cancelled/rescheduled)

                Use null for any parameters not mentioned.
                
                Example outputs:
                For "I need to cancel my appointment because I'm sick":
                {{
                    "cancelled": true,
                    "rescheduled": false,
                    "reason_for_cancellation": "customer is sick"
                }}

                For "Can we reschedule to next Tuesday because I'll be out of town":
                {{
                    "cancelled": false,
                    "rescheduled": true,
                    "reason_for_cancellation": "customer out of town",
                    "relative_day": "next",
                    "weekday": "tuesday"
                }}

                Transcript:
                {call_record.transcript}
                """

                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that extracts specific information from sales call transcripts. You're especially good at understanding and calculating dates based on context."},
                        {"role": "user", "content": date_prompt}
                    ],
                    temperature=0.1
                )
                # Parse the response and extract date parameters
                extracted_info = json.loads(response.choices[0].message.content.replace("```json","").replace("```","").strip())
                                    # Add these updates to the call record
                if extracted_info.get("cancelled") is not None:
                    call_record.cancelled = extracted_info["cancelled"]
                if extracted_info.get("rescheduled") is not None:
                    call_record.rescheduled = extracted_info["rescheduled"]
                if extracted_info.get("reason_for_cancellation"):
                    call_record.reason_for_cancellation = extracted_info["reason_for_cancellation"]
                
                if call_record.rescheduled:
                    # Get the most recent call for this phone number
                    previous_call = db.query(call.Call)\
                        .filter(
                            call.Call.call_id != call_record.call_id,
                            call.Call.phone_number==call_data.get("customer_phone_number"), 
                            call.Call.cancelled==False,
                            call.Call.company_id==company_record.id)\
                        .order_by(call.Call.created_at.desc())\
                        .first()
                    print("previous call id: ", previous_call.call_id)
                    print("current call id: ", call_record.call_id)
                    if previous_call:
                       
                        # Calculate the new date using the same logic
                        calculated_date = date_calculator.calculate_date(extracted_info)
                        
                        # Get all active Bland AI calls for this customer
                        response = requests.get(
                            f"{bland_ai.BASE_URL}/calls",
                            headers=bland_ai.headers,
                            params={
                                "to_number": previous_call.phone_number,
                                "completed": False,
                                "inbound": False,
                                "limit": 1
                            }
                        )
                        
                        if response.status_code == 200:
                            active_calls = response.json()
                            # Stop all active calls
                            for call_info in active_calls:
                                if call_info.get("call_id"):
                                    try:
                                        # Stop the call
                                        stop_response = requests.post(
                                            f"{bland_ai.BASE_URL}/calls/{call_info['call_id']}/stop",
                                            headers=bland_ai.headers
                                        )
                                        print(f"Stopped call {call_info['call_id']}: {stop_response.json()}")
                                    except Exception as e:
                                        print(f"Error stopping call {call_info['call_id']}: {str(e)}")
                        
                        # Schedule new follow-up call for the new date if available
                        if calculated_date:
                            calculated_date = calculated_date + timedelta(hours=2)
                            
                        # Update all relevant fields from the new conversation
                        if calculated_date:
                            previous_call.quote_date = calculated_date
                            print(f"Updated previous call {previous_call.call_id} quote date to {calculated_date}")
                        
                        # Update all extracted information
                        if extracted_info.get("address"):
                            previous_call.address = extracted_info["address"]
                        if extracted_info.get("name"):
                            previous_call.name = extracted_info["name"]
                        if extracted_info.get("problem"):
                            previous_call.problem = extracted_info["problem"]
                        
                        # Update status flags
                        previous_call.rescheduled = True
                        previous_call.reason_for_cancellation = extracted_info.get("reason_for_cancellation")
                        previous_call.booked = extracted_info.get("is_booked", previous_call.booked)
                        previous_call.still_deciding = extracted_info.get("still_deciding", previous_call.still_deciding)
                        previous_call.reason_for_deciding = extracted_info.get("reason_for_deciding")
                        
                        print(f"Successfully updated all relevant data for rescheduled call {previous_call.call_id}")
                        db.delete(call_record)
                if call_record.cancelled:
                    previous_call = db.query(call.Call)\
                        .filter(
                            call.Call.call_id != call_record.call_id,
                            call.Call.phone_number==call_data.get("customer_phone_number"), 
                            call.Call.cancelled==False, 
                            call.Call.company_id==company_record.id)\
                        .order_by(call.Call.created_at.desc())\
                        .first()
                    if previous_call:
                        # Get all active Bland AI calls for this customer
                        response = requests.get(
                            f"{bland_ai.BASE_URL}/calls",
                            headers=bland_ai.headers,
                            params={
                                "to_number": previous_call.phone_number,
                                "completed": False,
                                "inbound": False,
                                "limit": 1
                            }
                        )
                        
                        if response.status_code == 200:
                            active_calls = response.json().get("calls",[])
                            # Stop all active calls
                            for call_info in active_calls:
                                if call_info.get("call_id"):
                                    try:
                                        # Stop the call
                                        stop_response = requests.post(
                                            f"{bland_ai.BASE_URL}/calls/{call_info['call_id']}/stop",
                                            headers=bland_ai.headers
                                        )
                                        print(f"Stopped call {call_info['call_id']}: {stop_response.json()}")
                                    except Exception as e:
                                        print(f"Error stopping call {call_info['call_id']}: {str(e)}")
                    
                    # Update status flags
                    previous_call.cancelled = True
                    previous_call.rescheduled = False
                    previous_call.reason_for_cancellation = extracted_info.get("reason_for_cancellation")
                    previous_call.booked = extracted_info.get("is_booked", previous_call.booked)
                    previous_call.still_deciding = extracted_info.get("still_deciding", previous_call.still_deciding)
                    previous_call.reason_for_deciding = extracted_info.get("reason_for_deciding")
                    
                    print(f"Successfully updated all relevant data for cancelled call {previous_call.call_id}")
                    db.delete(call_record)
                else:            
                    # Calculate the actual date using DateCalculator
                    calculated_date = date_calculator.calculate_date(extracted_info)
                    if calculated_date:
                        extracted_info["quote_date"] = calculated_date.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        extracted_info["quote_date"] = None
                    
                    # Update call record with extracted information
                    if extracted_info.get("address"):
                        call_record.address = extracted_info["address"]
                        print(f"Address: {call_record.address}")
                    if extracted_info.get("name"):
                        call_record.name = extracted_info["name"]
                        print(f"Name: {call_record.name}")
                    if extracted_info.get("quote_date"):
                        try:
                            call_record.quote_date = datetime.strptime(extracted_info["quote_date"], "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            print(f"Error parsing date: {extracted_info['quote_date']}")
                    if extracted_info.get("problem"):
                        call_record.problem = extracted_info["problem"]
                        print(f"Problem: {call_record.problem}")
                    
                    # Update booking status
                    if extracted_info.get("is_booked"):
                        call_record.booked = True
                        
                        # If the call is now booked and has an address, create a geofence
                        if call_record.address:
                            from app.routes.mobile_routes.location_geofence_stuff import create_geofence_for_call
                            background_tasks.add_task(create_geofence_for_call, call_record.call_id, db)
                        

        except Exception as e:
            print(f"Error processing transcript with LLM: {str(e)}")

    # After extracting information and before committing...
    # Continue with existing commit
    db.commit()
    
    # Emit real-time event for call completion
    emit(
        event_name="telephony.call.completed",
        payload={
            "call_id": call_record.call_id,
            "phone_number": call_record.phone_number,
            "company_id": str(call_record.company_id),
            "booked": call_record.booked,
            "qualified": call_record.qualified,
            "objections": call_record.objections or [],
            "quote_date": call_record.quote_date.isoformat() if call_record.quote_date else None
        },
        tenant_id=tenant_id,
        lead_id=call_record.call_id
    )
    
    # Add detailed logging for debugging
    print(f"=== CALL COMPLETE SUMMARY ===")
    print(f"Call ID: {call_record.call_id}")
    print(f"Name: {call_record.name}")
    print(f"Phone: {call_record.phone_number}")
    print(f"Address: {call_record.address}")
    print(f"Company ID: {call_record.company_id}")
    print(f"Quote Date: {call_record.quote_date}")
    print(f"Booked: {call_record.booked}")
    print(f"Cancelled: {call_record.cancelled}")
    print(f"Rescheduled: {call_record.rescheduled}")
    print(f"Missed Call: {call_record.missed_call}")
    print(f"Still Deciding: {call_record.still_deciding}")
    print(f"Bought: {call_record.bought}")
    print(f"Assigned Rep ID: {call_record.assigned_rep_id}")
    print(f"========================")
    
    return {"status": "processed", "call_id": call_record.call_id}
    
    # Apply idempotency protection
    return with_idempotency(
        provider="callrail",
        external_id=external_id,
        tenant_id=tenant_id,
        process_fn=process_webhook,
        trace_id=getattr(request.state, 'trace_id', None)
    )


@router.post("/call-modified")
async def call_modified_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    params = dict(request.query_params)
    print(f"=================== CALL MODIFIED WEBHOOK ===================")
    print(f"Call modified params: {params}")
    
    # Extract tenant_id from middleware
    tenant_id = "webhook_tenant"  # TODO: Implement proper tenant resolution for webhooks
    
    # Derive external_id from CallRail payload
    external_id = f"call-modified-{params.get('trackingnum')}-{params.get('customer_phone_number')}"
    
    def process_webhook():
        # If params are empty, just return success (all data already processed in call-complete)
        if not params:
            print("No parameters provided in call-modified webhook - this is normal")
            return {"status": "processed", "message": "No parameters provided"}
    
    # Use tracking number to identify relevant company (same as call-complete)
    tracking_number = params.get("trackingnum")
    if not tracking_number:
        print(f"Error: Missing tracking number in request params: {params}")
        return {"status": "success", "message": "Missing tracking number but continuing"}
    
    # Continue with the rest of the processing
    company_record = db.query(company.Company).filter_by(phone_number=tracking_number).first()
    if not company_record:
        print(f"Error: No company found for tracking number: {tracking_number}")
        return {"status": "success", "message": f"No company found for tracking number {tracking_number}"}
    
    print(f"Company found: {company_record.name} with ID: {company_record.id}")
    
    call_record = db.query(call.Call)\
        .filter_by(
            phone_number=params.get("customer_phone_number"),
            company_id=company_record.id
        )\
        .order_by(call.Call.created_at.desc())\
        .first()
    
    if not call_record:
        print(f"Error: No call found for phone: {params.get('customer_phone_number')} and company: {company_record.id}")
        return {"status": "success", "message": "Call not found but continuing"}
    
    print(f"Call record found: {call_record.call_id}")
    
    # Only update transcript if it's not already present
    if not call_record.transcript and params.get("transcription"):
        call_record.transcript = params.get("transcription")
        call_record.missed_call = not params.get("answered", True)
        
        # Extract information using LLM
        if call_record.transcript:
            # First, check if this is a sales-related call
            sales_check_prompt = f"""
            Analyze this conversation transcript and determine if this is a sales-related call where a customer is inquiring about products/services or discussing a potential purchase.
            Respond with just 'true' if it's a sales call, or 'false' if it's not (e.g., customer support, wrong number, etc.).

            Transcript:
            {call_record.transcript}
            """

            try:
              
                sales_check_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that analyzes conversation transcripts."},
                        {"role": "user", "content": sales_check_prompt}
                    ],
                    temperature=0.1
                )
                
                is_sales_call = json.loads(sales_check_response.choices[0].message.content.replace("```json","").replace("```","").strip())['is_sales_call'] == True
                
                # Only proceed with information extraction if it's a sales call
                if is_sales_call:
                    # Prepare prompt for OpenAI with current date context
                    current_date = datetime.now()
                    date_prompt = f"""
                    Today's date is {current_date.strftime('%A, %B %d, %Y')}.
                    Extract information from this transcript into a JSON format with these fields:
                    - relative_day: "next", "this", or "last" if mentioned
                    - weekday: the specific day of week mentioned
                    - weeks_offset: number of weeks to add/subtract
                    - days_offset: number of days to add/subtract
                    - months_offset: number of months to add/subtract
                    - time: time mentioned (in HH:MM format or as am/pm)
                    - specific_date: if a specific date is mentioned (YYYY-MM-DD format)
                    - address: full address mentioned
                    - name: customer's name
                    - is_booked: true if an appointment was scheduled, false otherwise

                    Use null for any parameters not mentioned.
                    
                    Example outputs:
                    For "let's meet next Tuesday at 2pm":
                    {{
                        "relative_day": "next",
                        "weekday": "tuesday",
                        "weeks_offset": null,
                        "days_offset": null,
                        "months_offset": null,
                        "time": "2pm",
                        "specific_date": null,
                        "address": null,
                        "name": null,
                        "is_booked": true
                    }}

                    Transcript:
                    {call_record.transcript}
                    """

                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that extracts specific information from sales call transcripts. You're especially good at understanding and calculating dates based on context."},
                            {"role": "user", "content": date_prompt}
                        ],
                        temperature=0.1
                    )
                    
                    # Parse the response and extract date parameters
                    extracted_info = json.loads(response.choices[0].message.content.replace("```json","").replace("```","").strip())
                    
                    # Calculate the actual date using DateCalculator
                    calculated_date = date_calculator.calculate_date(extracted_info)
                    if calculated_date:
                        extracted_info["quote_date"] = calculated_date.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        extracted_info["quote_date"] = None
                    
                    # Update call record with extracted information
                    if extracted_info.get("address"):
                        call_record.address = extracted_info["address"]
                        print(f"Address: {call_record.address}")
                    if extracted_info.get("name"):
                        call_record.name = extracted_info["name"]
                        print(f"Name: {call_record.name}")
                    if extracted_info.get("quote_date"):
                        try:
                            call_record.quote_date = datetime.strptime(extracted_info["quote_date"], "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            print(f"Error parsing date: {extracted_info['quote_date']}")
                            pass
                    
                    # Update booking status
                    if extracted_info.get("is_booked"):
                        call_record.booked = True
                        # Reset assigned rep as requested when booked
                        call_record.assigned_rep_id = None
                        
                        # If the call is now booked and has an address, create a geofence
                        if call_record.address:
                            from app.routes.mobile_routes.location_geofence_stuff import create_geofence_for_call
                            background_tasks.add_task(create_geofence_for_call, call_record.call_id, db)

            except Exception as e:
                # Log the error but don't fail the request
                print(f"Error processing transcript with LLM: {str(e)}")

        db.commit()
        return {"status": "processed", "message": "Call modified successfully"}
    
    # Apply idempotency protection
    return with_idempotency(
        provider="callrail",
        external_id=external_id,
        tenant_id=tenant_id,
        process_fn=process_webhook,
        trace_id=getattr(request.state, 'trace_id', None)
    ) 
