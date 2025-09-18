from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from app.database import get_db
from app.models import call, company, sales_rep, sales_manager
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
from app.services.bland_ai import BlandAI
from app.routes.dependencies import bland_ai, client
from app.services.twilio_service import twilio_service
from app.services.idempotency import with_idempotency

router = APIRouter()


@router.post("/make-homeowner-followup-call")
async def make_homeowner_followup_call(
    request: Request,
    db: Session = Depends(get_db)
):
    params = dict(request.query_params)

    call_record = db.query(call.Call)\
        .filter_by(id=1)\
        .first()

    if not call_record:
        raise HTTPException(status_code=404, detail="Customer call record not found")

    # Get company name from company_id
    company_name = None
    if call_record.company_id:
        company_record = db.query(company.Company).filter_by(id=call_record.company_id).first()
        if company_record:
            company_name = company_record.name

   
    sales_rep_record = db.query(sales_rep.SalesRep)\
        .filter_by(id=1)\
        .first()

    if not sales_rep_record:
        raise HTTPException(status_code=404, detail="Sales rep not found")
    
    # Make the call using BlandAI service
    bland_ai_service = BlandAI()
    result = bland_ai_service.make_followup_call(
        customer_phone="+12408488294",
        reason_for_lost_sale=params.get("reason", "General followup"),
        request_data={
            "name": call_record.name,
            "phone": call_record.phone_number,
            "address": call_record.address,
            "quote_date": call_record.quote_date.isoformat() if call_record.quote_date else None,
            "company_name": company_name,
            "sales_rep_name": sales_rep_record.name
        }
    )

    return {
        "status": "success",
        "call_id": result.get("call_id"),
        "message": "Homeowner followup call initiated"
        ""
    }


def check_if_pickedup(data: dict):
    try:
        
        # Extract relevant fields
        disposition_tag = data.get("disposition_tag")
        call_length = data.get("call_length")
        concatenated_transcript = data.get("concatenated_transcript")
        
        print(f"Call length: {call_length}")
        print(f"Concatenated transcript: {concatenated_transcript}")
        print(f"Disposition tag: {disposition_tag}")

        # Check if call was picked up
        picked_up = True
        
        # call_length is in minutes
        if disposition_tag == "NO_CONTACT_MADE" or float(call_length) < 0.3 or "voicemail" in str(concatenated_transcript).lower():
            picked_up = False
        
        return picked_up
    except Exception as e:
        print(f"Error checking if call was picked up: {str(e)}")
        return True

def extract_customer_name_from_transcript(data: dict):
    try:
        transcript = data.get("concatenated_transcript")
        if not transcript:
            return None
        
        prompt = f"""
            Analyze this post-sale conversation transcript and extract the customer's name from the transcript. Only a first name may be provided.
            Return in JSON format:
            - customer_name: the name of the customer, otherwise None
            - reason: the reason you are unable to determine the customer's name if you cannot determine the customer's name, otherwise None

            Example output:
            {{
                "customer_name": "John Doe",
                "reason": "The customer's name is not mentioned in the transcript"
            }}

            {{
                "customer_name": "Carla",
                "reason": None
            }}

            Transcript:
            {transcript}
            """

        print("Sending prompt to OpenAI")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes sales call transcripts."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        
        # Parse the response
        extracted_info = json.loads(response.choices[0].message.content.replace("```json","").replace("```","").strip())
        print(f"Extracted customer name information: {extracted_info}")
        return extracted_info.get("customer_name")

    except Exception as e:
        print(f"Error extracting customer name from transcript: {str(e)}")
        return None


@router.post("/bland-callback")
async def bland_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    print("=== BLAND.AI WEBHOOK CALLBACK START ===")
    # Log incoming request data
    data = await request.json()
    print(f"Received webhook data: {data}")
    
    # Extract and log metadata
    metadata = data.get("metadata", {})
    print(f"Extracted metadata: {metadata}")
    
    # Extract tenant_id from metadata or use default
    tenant_id = metadata.get("tenant_id") or "default_tenant"
    
    # Derive external_id from Bland AI payload - use call_id or session_id
    external_id = data.get("call_id") or data.get("session_id") or f"bland-{data.get('id', 'unknown')}"
    
    def process_webhook():
        
        # scheduled_call_id = metadata.get("scheduled_call_id")
        try:
            call_type = metadata.get("call_type")   
        except:
            call_type = None

        try: 
            inbound_call = bool(data.get("inbound"))
            destination_number = data.get("to")
            from_number = data.get("from")
        except:
            inbound_call = None
            destination_number = None
            from_number = None
        # print(f"Call type: {call_type}, Scheduled call ID: {scheduled_call_id}")

        picked_up = check_if_pickedup(data)
        print(f"This is an inbound call: {inbound_call} and the number called was {destination_number}")
        
        if call_type == "homeowner_followup" or (inbound_call and destination_number == "+15205232772"): # Destination number must be unique to homeowner callback here
            print("Processing homeowner follow-up call")
            if not picked_up and not inbound_call:
                print(f"Call not picked up, sending text message to callback {data.get('to')}")
                # Send SMS using our Twilio service
                sms_result = twilio_service.send_customer_callback_message(
                    phone_number=data.get("to")
                )
                print(f"SMS notification result: {sms_result}")
                return {"status": "homeowner_callback_message_sent"}
            
            if inbound_call:
                from_number = data.get("from")
                print(f"Looking up call record for {from_number}")
                # To-Do: Add company_id to the query, need customer to confirm which company they are calling about. 
                call_record = db.query(call.Call).filter_by(phone_number=from_number).first()
                if not call_record:
                    print(f"ERROR: Call record for {from_number} not found")
                    raise HTTPException(status_code=404, detail="Call record not found")
                
                original_call_id = call_record.call_id
            else:
                original_call_id = metadata.get("original_call_id")
                if not original_call_id:
                    print("ERROR: Missing original call ID")
                    raise HTTPException(status_code=400, detail="Missing original call ID")

                print(f"Looking up original call with ID: {original_call_id}")
                call_record = db.query(call.Call).filter_by(call_id=original_call_id).first()
                if not call_record:
                    print(f"ERROR: Call record {original_call_id} not found")
                    raise HTTPException(status_code=404, detail="Call record not found")
        
  
            if data.get("concatenated_transcript"):
                call_record.homeowner_followup_call_id = data.get("call_id")
                print(f"Analyzing call with ID: {call_record.call_id}") 

                call_record.homeowner_followup_transcript = data.get("concatenated_transcript")
                print(f"Stored homeowner follow-up transcript for call {original_call_id}")

            
                prompt = f"""
                Analyze this post-sale conversation transcript and extract the following information.
                Return in JSON format:
                - reason_for_not_buying: the specific reason they didn't buy (null if they bought)

                Transcript:
                {data.get("concatenated_transcript")}
                """

                print("Sending prompt to OpenAI")
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that analyzes sales call transcripts."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1
                )
                
                # Parse the response
                extracted_info = json.loads(response.choices[0].message.content.replace("```json","").replace("```","").strip())
                print(f"Extracted sale information: {extracted_info}")
                
                # Update call record
                call_record.reason_not_bought_homeowner = extracted_info.get("reason_for_not_buying", False)

                # Analyze transcripts for discrepancies if both transcripts exist
                if call_record.transcript and call_record.homeowner_followup_transcript:
                    try:
                        discrepancy_prompt = f"""
                        These are two conversation transcripts from automated calls to a customer and their assigned sales rep. Please analyze these transcripts objectively and identify any inconsistencies between what was reported in each call. Focus on differences in:
                        - Pricing discussed
                        - Services or products mentioned
                        - Agreements or commitments made
                        - Reasons given for decisions
                        
                        Examples of discrepancies:
                        - Different purchase decisions reported (purchased vs. not purchased)
                        - Different price quotes mentioned
                        - Different services or products discussed
                        - Different reasons given for the customer's decision

                        Sales Call Transcript:
                        {call_record.transcript}

                        Homeowner Follow-up Transcript:
                        {call_record.homeowner_followup_transcript}

                        Return the analysis in JSON format with these fields:
                        - has_discrepancies: boolean
                        - sales_rep_claim: string of either PURCHASED, STILL DECIDING, or NOT PURCHASED (use NOT_MENTIONED if unclear)
                        - homeowner_claim: string of either PURCHASED, STILL DECIDING, or NOT PURCHASED (use NOT_MENTIONED if unclear)
                        - sales_rep_quote: float of the price quoted by the sales rep, 0 if not mentioned
                        - homeowner_quote: float of the price the homeowner claims to have been quoted, 0 if not mentioned
                        - summary: brief summary of key differences

                        If no significant discrepancies are found, return has_discrepancies as false.
                        If either transcript is too short or unclear to make a determination, note this in the summary.
                        """

                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": "You are a helpful assistant that analyzes conversation transcripts for inconsistencies."},
                                {"role": "user", "content": discrepancy_prompt}
                            ],
                            temperature=0.1
                        )
                        
                        # Parse the response and store the analysis
                        analysis = json.loads(response.choices[0].message.content.replace("```json","").replace("```","").strip())
                        call_record.transcript_discrepancies = json.dumps(analysis)
                        print(f"Stored transcript discrepancy analysis for call {original_call_id}")

                    except Exception as e:
                        print(f"Error analyzing transcripts for discrepancies: {str(e)}")

        print("Committing database changes")
        db.commit()
        print("=== BLAND.AI WEBHOOK CALLBACK COMPLETE ===")
        return {"status": "processed", "call_type": call_type}
    
    # Apply idempotency protection
    response_data, status_code = with_idempotency(
        provider="bland",
        external_id=external_id,
        tenant_id=tenant_id,
        process_fn=process_webhook,
        trace_id=getattr(request.state, 'trace_id', None)
    )
    
    return response_data
