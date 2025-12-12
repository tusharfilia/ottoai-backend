"""
Shunya Integration Service for OttoAI backend.

Handles the full Shunya integration pipeline:
1. Transcription (ASR + diarization)
2. Analysis (qualification, objections, SOP compliance)
3. Persistence into Otto domain models
4. Property intelligence triggering
5. Task creation from pending actions
6. Event emission

IMPORTANT: Property intelligence is Otto-owned, NOT Shunya.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import uuid4
import asyncio

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.services.uwc_client import UWCClient, get_uwc_client
from app.services.property_intelligence_service import maybe_trigger_property_scrape, update_contact_address
from app.models.call import Call
from app.models.lead import Lead, LeadStatus
from app.models.appointment import Appointment, AppointmentOutcome, AppointmentStatus
from app.models.contact_card import ContactCard
from app.models.call_transcript import CallTranscript
from app.models.call_analysis import CallAnalysis
from app.models.recording_session import RecordingSession, RecordingMode
from app.models.recording_transcript import RecordingTranscript
from app.models.recording_analysis import RecordingAnalysis
from app.models.task import Task, TaskSource, TaskAssignee, TaskStatus
from app.models.lead_status_history import LeadStatusHistory
from app.models.event_log import EventLog, EventType
from app.models.key_signal import KeySignal, SignalType, SignalSeverity
from app.database import SessionLocal
from app.realtime.bus import emit
from app.core.pii_masking import PIISafeLogger
from app.config import settings

logger = PIISafeLogger(__name__)


class ShunyaIntegrationService:
    """
    Service for integrating Shunya intelligence into Otto domain models.
    
    Responsibilities:
    - Call Shunya endpoints for transcription and analysis
    - Persist Shunya results into Otto models
    - Update Lead/Appointment status based on Shunya classification
    - Create Tasks from Shunya pending actions
    - Trigger property intelligence when address is extracted
    - Emit domain events for downstream consumers
    """
    
    def __init__(self):
        self.uwc_client = get_uwc_client()
    
    async def process_csr_call(
        self,
        call_id: int,
        audio_url: str,
        company_id: str,
        call_type: str = "csr_call"
    ) -> Dict[str, Any]:
        """
        Process a CSR call through Shunya pipeline.
        
        Flow:
        1. Transcribe audio via Shunya
        2. Start analysis pipeline
        3. Poll for complete analysis (or wait for webhook)
        4. Persist transcript and analysis
        5. Update Lead status from Shunya classification
        6. Create Appointment if booked
        7. Create Tasks from pending actions
        8. Trigger property intelligence if address extracted
        9. Emit events
        
        Args:
            call_id: Call ID
            audio_url: Publicly accessible audio URL
            company_id: Company/tenant ID
            call_type: "csr_call" or "sales_call"
            
        Returns:
            Dict with processing status and results
        """
        db = SessionLocal()
        request_id = str(uuid4())
        
        try:
            # Get call record
            call = db.query(Call).filter(Call.call_id == call_id).first()
            if not call:
                logger.error(f"Call {call_id} not found")
                return {"success": False, "error": "Call not found"}
            
            # Step 1: Transcribe audio
            logger.info(f"Transcribing call {call_id} via Shunya")
            # Use the existing transcribe_audio method
            transcript_request_payload = {
                "call_id": call_id,
                "audio_url": audio_url,
                "call_type": call_type
            }
            
            # Call Shunya transcription endpoint
            transcript_result = await self.uwc_client._make_request(
                "POST",
                "/api/v1/transcription/transcribe",
                company_id,
                request_id,
                transcript_request_payload
            )
            
            if not transcript_result.get("success"):
                logger.error(f"Shunya transcription failed for call {call_id}: {transcript_result.get('message')}")
                return {"success": False, "error": "Transcription failed"}
            
            transcript_id = transcript_result.get("transcript_id")
            task_id = transcript_result.get("task_id")
            
            # Poll for transcription to complete (or wait for webhook)
            # For now, wait a bit then fetch
            await asyncio.sleep(5)
            
            # Get actual transcript
            transcript_response = await self.uwc_client.get_transcript(
                company_id=company_id,
                request_id=request_id,
                call_id=call_id
            )
            
            # Normalize transcript response
            from app.services.shunya_response_normalizer import shunya_normalizer
            normalized_transcript = shunya_normalizer.normalize_transcript_response(transcript_response)
            transcript_text = normalized_transcript["transcript_text"]
            speaker_labels = normalized_transcript["speaker_labels"]
            confidence_score = normalized_transcript["confidence_score"] or 0.0
            
            # Step 2: Store transcript
            await self._store_call_transcript(
                db=db,
                call_id=call_id,
                company_id=company_id,
                transcript_text=transcript_text,
                speaker_labels=speaker_labels,
                confidence_score=confidence_score,
                uwc_job_id=task_id or str(transcript_id)
            )
            
            # Also update Call model transcript field (for backward compatibility)
            call.transcript = transcript_text
            
            # Step 3: Start analysis pipeline
            logger.info(f"Starting Shunya analysis for call {call_id}")
            analysis_result = await self.uwc_client.start_analysis(
                company_id=company_id,
                request_id=request_id,
                call_id=call_id
            )
            
            # Analysis may be async - poll or wait for webhook
            # For now, immediately fetch complete analysis (may need polling)
            await asyncio.sleep(2)  # Brief delay for processing
            
            complete_analysis = await self.uwc_client.get_complete_analysis(
                company_id=company_id,
                request_id=request_id,
                call_id=call_id
            )
            
            # Step 4: Normalize analysis response
            from app.services.shunya_response_normalizer import shunya_normalizer
            normalized_analysis = shunya_normalizer.normalize_complete_analysis(complete_analysis)
            
            # Step 5: Persist analysis and update domain models
            await self._process_shunya_analysis_for_call(
                db=db,
                call=call,
                company_id=company_id,
                complete_analysis=normalized_analysis,
                transcript_text=transcript_text
            )
            
            db.commit()
            
            # Step 5: Emit events
            emit(
                event_name="call.transcribed",
                payload={
                    "call_id": call_id,
                    "transcript_id": transcript_id,
                    "confidence_score": confidence_score,
                    "word_count": len(transcript_text.split()) if transcript_text else 0
                },
                tenant_id=company_id,
                lead_id=str(call.lead_id) if call.lead_id else None
            )
            
            logger.info(f"Successfully processed CSR call {call_id} via Shunya")
            return {"success": True, "call_id": call_id, "transcript_id": transcript_id}
            
        except Exception as e:
            logger.error(f"Error processing CSR call {call_id}: {str(e)}", exc_info=True)
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()
    
    async def process_sales_visit(
        self,
        recording_session_id: str,
        audio_url: str,
        company_id: str
    ) -> Dict[str, Any]:
        """
        Process a sales visit recording through Shunya pipeline.
        
        Flow:
        1. Transcribe audio (if not ghost mode)
        2. Analyze visit (outcome, objections, SOP compliance)
        3. Update Appointment and Lead status
        4. Create Tasks from visit actions
        5. Emit events
        
        Args:
            recording_session_id: RecordingSession ID
            audio_url: Publicly accessible audio URL (may be None in ghost mode)
            company_id: Company/tenant ID
            
        Returns:
            Dict with processing status
        """
        db = SessionLocal()
        request_id = str(uuid4())
        
        try:
            # Get recording session
            session = db.query(RecordingSession).filter(
                RecordingSession.id == recording_session_id
            ).first()
            
            if not session:
                logger.error(f"Recording session {recording_session_id} not found")
                return {"success": False, "error": "Recording session not found"}
            
            # Check ghost mode
            is_ghost = session.mode == RecordingMode.GHOST
            
            # Step 1: Transcribe (if not ghost mode and audio_url exists)
            transcript_text = None
            transcript_id = None
            
            if not is_ghost and audio_url:
                logger.info(f"Transcribing visit {recording_session_id} via Shunya")
                transcript_result = await self.uwc_client.transcribe_audio(
                    company_id=company_id,
                    request_id=request_id,
                    audio_url=audio_url,
                    language="en-US"
                )
                
                if transcript_result.get("success"):
                    transcript_text = transcript_result.get("transcript_text", "")
                    transcript_id = transcript_result.get("transcript_id")
                    
                    # Store transcript
                    await self._store_recording_transcript(
                        db=db,
                        recording_session_id=recording_session_id,
                        company_id=company_id,
                        transcript_text=transcript_text,
                        uwc_job_id=transcript_result.get("task_id") or transcript_id
                    )
            else:
                logger.info(f"Skipping transcript storage for ghost mode session {recording_session_id}")
            
            # Step 2: Analyze visit
            # Use call_id from recording session's appointment (if available)
            appointment = session.appointment
            call_id_for_analysis = None
            
            if appointment and appointment.lead_id:
                # Find a related call for this lead
                from app.models.call import Call
                related_call = db.query(Call).filter(
                    Call.lead_id == appointment.lead_id
                ).order_by(Call.created_at.desc()).first()
                
                if related_call:
                    call_id_for_analysis = related_call.call_id
            
            # For visit analysis, use meeting segmentation endpoint
            # Shunya's meeting segmentation endpoint analyzes sales appointments
            if call_id_for_analysis:
                # Start meeting segmentation analysis
                await self.uwc_client.analyze_meeting_segmentation(
                    company_id=company_id,
                    request_id=request_id,
                    call_id=call_id_for_analysis,
                    analysis_type="full"
                )
                
                # Wait a bit for processing
                await asyncio.sleep(5)
                
                # Get complete meeting segmentation
                meeting_seg = await self.uwc_client.get_meeting_segmentation_analysis(
                    company_id=company_id,
                    request_id=request_id,
                    call_id=call_id_for_analysis
                )
                
                # Also get complete analysis for objections/compliance
                try:
                    complete_analysis = await self.uwc_client.get_complete_analysis(
                        company_id=company_id,
                        request_id=request_id,
                        call_id=call_id_for_analysis
                    )
                except Exception as e:
                    logger.warning(f"Could not fetch complete analysis: {e}, using meeting segmentation only")
                    complete_analysis = {}
                
                # Merge meeting segmentation into complete analysis
                if meeting_seg:
                    complete_analysis.update(meeting_seg)
                    
                    # Extract outcome from part2 if available
                    if "part2" in meeting_seg and isinstance(meeting_seg["part2"], dict):
                        part2_content = meeting_seg["part2"].get("content", "") or meeting_seg["part2"].get("key_points", [])
                        if isinstance(part2_content, str):
                            # Infer outcome from part2 content (proposal/close phase)
                            if any(word in part2_content.lower() for word in ["signed", "agreed", "closed", "deal", "won"]):
                                complete_analysis["outcome"] = "won"
                            elif any(word in part2_content.lower() for word in ["declined", "not interested", "pass", "lost"]):
                                complete_analysis["outcome"] = "lost"
            elif transcript_text:
                # Fallback: analyze using transcript directly (if no call_id)
                # Use summarization endpoint to get key insights
                summary_result = await self.uwc_client.summarize_call(
                    company_id=company_id,
                    request_id=request_id,
                    call_id=0,  # Not applicable for visit-only
                    options={"transcript": transcript_text}  # Pass transcript directly if endpoint supports
                )
                complete_analysis = summary_result or {}
            else:
                logger.warning(f"No transcript available for visit {recording_session_id}")
                complete_analysis = {}
            
            # Step 3: Normalize analysis response
            from app.services.shunya_response_normalizer import shunya_normalizer
            normalized_analysis = shunya_normalizer.normalize_complete_analysis(complete_analysis)
            
            # If this was a meeting segmentation response, merge it
            if "part1" in complete_analysis or "part2" in complete_analysis:
                meeting_seg = shunya_normalizer.normalize_meeting_segmentation(complete_analysis)
                normalized_analysis.update(meeting_seg)
            
            # Step 4: Process analysis and update domain models
            await self._process_shunya_analysis_for_visit(
                db=db,
                recording_session=session,
                company_id=company_id,
                complete_analysis=normalized_analysis,
                transcript_text=transcript_text
            )
            
            db.commit()
            
            # Step 4: Emit events
            emit(
                event_name="recording_session.analyzed",
                payload={
                    "recording_session_id": recording_session_id,
                    "appointment_id": session.appointment_id,
                    "outcome": complete_analysis.get("outcome"),
                    "ghost_mode": is_ghost
                },
                tenant_id=company_id,
                lead_id=str(appointment.lead_id) if appointment and appointment.lead_id else None
            )
            
            logger.info(f"Successfully processed sales visit {recording_session_id} via Shunya")
            return {"success": True, "recording_session_id": recording_session_id}
            
        except Exception as e:
            logger.error(f"Error processing sales visit {recording_session_id}: {str(e)}", exc_info=True)
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()
    
    async def _store_call_transcript(
        self,
        db: Session,
        call_id: int,
        company_id: str,
        transcript_text: str,
        speaker_labels: Optional[List[Dict[str, Any]]],
        confidence_score: Optional[float],
        uwc_job_id: str
    ):
        """Store Shunya transcript into CallTranscript model."""
        from uuid import uuid4
        
        # Check if transcript already exists
        existing = db.query(CallTranscript).filter(
            CallTranscript.call_id == call_id,
            CallTranscript.uwc_job_id == uwc_job_id
        ).first()
        
        if existing:
            # Update existing
            existing.transcript_text = transcript_text
            existing.speaker_labels = speaker_labels
            existing.confidence_score = confidence_score
            existing.word_count = len(transcript_text.split()) if transcript_text else 0
            existing.updated_at = datetime.utcnow()
        else:
            # Create new
            transcript = CallTranscript(
                id=str(uuid4()),
                call_id=call_id,
                tenant_id=company_id,
                uwc_job_id=uwc_job_id,
                transcript_text=transcript_text,
                speaker_labels=speaker_labels or [],
                confidence_score=confidence_score,
                word_count=len(transcript_text.split()) if transcript_text else 0,
                language="en-US"
            )
            db.add(transcript)
    
    async def _store_recording_transcript(
        self,
        db: Session,
        recording_session_id: str,
        company_id: str,
        transcript_text: str,
        uwc_job_id: str
    ):
        """Store Shunya transcript into RecordingTranscript model."""
        from uuid import uuid4
        
        # Check if transcript already exists
        existing = db.query(RecordingTranscript).filter(
            RecordingTranscript.recording_session_id == recording_session_id,
            RecordingTranscript.uwc_job_id == uwc_job_id
        ).first()
        
        if existing:
            existing.transcript_text = transcript_text
            existing.word_count = len(transcript_text.split()) if transcript_text else 0
            existing.updated_at = datetime.utcnow()
        else:
            transcript = RecordingTranscript(
                id=str(uuid4()),
                recording_session_id=recording_session_id,
                company_id=company_id,
                uwc_job_id=uwc_job_id,
                transcript_text=transcript_text,
                word_count=len(transcript_text.split()) if transcript_text else 0,
                language="en-US"
            )
            db.add(transcript)
    
    async def _process_shunya_analysis_for_call(
        self,
        db: Session,
        call: Call,
        company_id: str,
        complete_analysis: Dict[str, Any],
        transcript_text: str,
        shunya_job: Optional[Any] = None  # Optional ShunyaJob for idempotency checking
    ):
        """
        Process Shunya analysis results for a CSR call.
        
        Maps Shunya outputs to:
        - CallAnalysis model
        - Lead status updates
        - Appointment creation (if booked)
        - Task creation (from pending actions)
        - Property intelligence trigger (if address extracted)
        
        Idempotency: This method is safe to call multiple times with the same analysis.
        Uses natural keys for tasks/signals and checks existing state before mutating.
        """
        from uuid import uuid4
        from app.utils.idempotency import (
            generate_output_payload_hash,
            generate_task_unique_key,
            generate_signal_unique_key,
            task_exists_by_unique_key,
            signal_exists_by_unique_key,
        )
        from app.models.shunya_job import ShunyaJobStatus
        
        # Idempotency guard: Check if this output has already been processed
        if shunya_job:
            output_hash = generate_output_payload_hash(complete_analysis)
            if (
                shunya_job.job_status == ShunyaJobStatus.SUCCEEDED
                and shunya_job.processed_output_hash == output_hash
            ):
                logger.info(
                    f"Shunya output for call {call.call_id} already processed (hash: {output_hash[:8]}...)",
                    extra={"call_id": call.call_id, "job_id": shunya_job.id}
                )
                return  # Already processed, no-op
        
        # Extract normalized fields (already normalized by normalizer)
        qualification = complete_analysis.get("qualification", {})
        qualification_status = (qualification.get("qualification_status") or "").lower()
        
        # DEBUG: Log what Shunya returned for qualification and booking status
        booking_status_raw = qualification.get("booking_status")
        call_outcome_category_computed = qualification.get("call_outcome_category")
        logger.info(
            f"Shunya response for call {call.call_id}: "
            f"qualification_status='{qualification_status}', "
            f"booking_status='{booking_status_raw}', "
            f"call_outcome_category='{call_outcome_category_computed}'",
            extra={
                "call_id": call.call_id,
                "qualification_status": qualification_status,
                "booking_status": booking_status_raw,
                "call_outcome_category": call_outcome_category_computed,
                "qualification_full": qualification
            }
        )
        
        # Get objections (normalized)
        objections_response = complete_analysis.get("objections", {})
        objections_list = objections_response.get("objections", [])
        objection_texts = [
            obj.get("objection_text") if isinstance(obj, dict) else str(obj)
            for obj in objections_list
        ]
        
        # Get compliance (normalized)
        compliance = complete_analysis.get("compliance", {})
        sop_stages_completed = compliance.get("stages_followed", [])
        sop_stages_missed = compliance.get("stages_missed", [])
        sop_compliance_score = compliance.get("compliance_score")
        
        # Get summary (normalized)
        summary_response = complete_analysis.get("summary", {})
        summary_text = summary_response.get("summary", "")
        
        # Get sentiment
        sentiment_score = complete_analysis.get("sentiment_score")
        
        # Get pending actions (normalized)
        pending_actions = complete_analysis.get("pending_actions", [])
        
        # Get missed opportunities (normalized)
        missed_opportunities = complete_analysis.get("missed_opportunities", [])
        
        # Store CallAnalysis
        analysis_id = str(uuid4())
        call_analysis = CallAnalysis(
            id=analysis_id,
            call_id=call.call_id,
            tenant_id=company_id,
            uwc_job_id=complete_analysis.get("job_id", ""),
            objections=objection_texts,
            sentiment_score=sentiment_score,
            sop_stages_completed=sop_stages_completed,
            sop_stages_missed=sop_stages_missed,
            sop_compliance_score=sop_compliance_score,
            lead_quality=qualification_status,
            analyzed_at=datetime.utcnow()
        )
        db.add(call_analysis)
        db.flush()  # Flush to get ID before fetching follow-up recommendations
        
        # Fetch follow-up recommendations from Shunya (non-blocking)
        # Only if feature flag is enabled
        if settings.ENABLE_FOLLOWUP_RECOMMENDATIONS:
            try:
                # Determine target_role based on call type or user context
                # Default to customer_rep for CSR calls
                target_role = self.uwc_client._map_otto_role_to_shunya_target_role("csr")
                
                # Fetch follow-up recommendations
                followup_request_id = str(uuid4())
                followup_recommendations = await self.uwc_client.get_followup_recommendations(
                    call_id=call.call_id,
                    company_id=company_id,
                    request_id=followup_request_id,
                    target_role=target_role
                )
                
                # Store recommendations in CallAnalysis
                if followup_recommendations and (
                    followup_recommendations.get("recommendations") or
                    followup_recommendations.get("next_steps") or
                    followup_recommendations.get("priority_actions")
                ):
                    call_analysis.followup_recommendations = followup_recommendations
                    logger.info(
                        f"Stored follow-up recommendations for call {call.call_id}",
                        extra={"call_id": call.call_id, "recommendations_count": len(followup_recommendations.get("recommendations", []))}
                    )
                else:
                    logger.debug(f"No follow-up recommendations returned for call {call.call_id}")
                    
            except Exception as e:
                # Non-blocking: log error but continue processing
                logger.warning(
                    f"Failed to fetch follow-up recommendations for call {call.call_id}: {str(e)}",
                    extra={"call_id": call.call_id},
                    exc_info=True
                )
                # Continue without recommendations (call_analysis.followup_recommendations remains None)
        
        # Run SOP compliance check from Shunya (non-blocking)
        # Only if feature flag is enabled
        if settings.ENABLE_SOP_COMPLIANCE_PIPELINE:
            try:
                # Determine target_role based on call type or user context
                # Default to customer_rep for CSR calls
                target_role = self.uwc_client._map_otto_role_to_shunya_target_role("csr")
                
                # Run compliance check
                compliance_request_id = str(uuid4())
                compliance_result = await self.uwc_client.run_compliance_check(
                    call_id=call.call_id,
                    company_id=company_id,
                    request_id=compliance_request_id,
                    target_role=target_role
                )
                
                # Merge compliance results into CallAnalysis
                if compliance_result and (
                    compliance_result.get("compliance_score") is not None or
                    compliance_result.get("violations") or
                    compliance_result.get("positive_behaviors") or
                    compliance_result.get("recommendations")
                ):
                    # Update compliance score if provided
                    if compliance_result.get("compliance_score") is not None:
                        call_analysis.sop_compliance_score = compliance_result["compliance_score"]
                    
                    # Update stages (merge with existing if any)
                    if compliance_result.get("stages_followed"):
                        existing_stages = call_analysis.sop_stages_completed or []
                        # Merge and deduplicate
                        merged_stages = list(set(existing_stages + compliance_result["stages_followed"]))
                        call_analysis.sop_stages_completed = merged_stages
                    
                    if compliance_result.get("stages_missed"):
                        existing_missed = call_analysis.sop_stages_missed or []
                        # Merge and deduplicate
                        merged_missed = list(set(existing_missed + compliance_result["stages_missed"]))
                        call_analysis.sop_stages_missed = merged_missed
                    
                    # Store detailed compliance data
                    call_analysis.compliance_violations = compliance_result.get("violations", [])
                    call_analysis.compliance_positive_behaviors = compliance_result.get("positive_behaviors", [])
                    call_analysis.compliance_recommendations = compliance_result.get("recommendations", [])
                    
                    logger.info(
                        f"Stored compliance check results for call {call.call_id}",
                        extra={
                            "call_id": call.call_id,
                            "compliance_score": compliance_result.get("compliance_score"),
                            "violations_count": len(compliance_result.get("violations", []))
                        }
                    )
                else:
                    logger.debug(f"No compliance results returned for call {call.call_id}")
                    
            except Exception as e:
                # Non-blocking: log error but continue processing
                logger.warning(
                    f"Failed to run compliance check for call {call.call_id}: {str(e)}",
                    extra={"call_id": call.call_id},
                    exc_info=True
                )
                # Continue without compliance check (existing compliance fields remain unchanged)
        
        # Update Lead based on qualification (idempotent: only if status changed)
        lead = None
        lead_status_changed = False
        if call.lead_id:
            lead = db.query(Lead).filter(Lead.id == call.lead_id).first()
            if lead:
                old_status = lead.status
                
                # Map Shunya qualification to LeadStatus
                status_mapping = {
                    "qualified_booked": LeadStatus.QUALIFIED_BOOKED,
                    "qualified_unbooked": LeadStatus.QUALIFIED_UNBOOKED,
                    "qualified_service_not_offered": LeadStatus.QUALIFIED_SERVICE_NOT_OFFERED,
                    "not_qualified": LeadStatus.CLOSED_LOST,
                }
                
                new_status_value = status_mapping.get(qualification_status)
                if new_status_value and old_status != new_status_value:
                    # Only update if status actually changed
                    lead.status = new_status_value
                    lead.last_qualified_at = datetime.utcnow()
                    lead_status_changed = True
                    
                    # Record status history (only if changed)
                    await self._record_lead_status_change(
                        db=db,
                        lead_id=lead.id,
                        company_id=company_id,
                        from_status=old_status.value if old_status else None,
                        to_status=new_status_value.value,
                        reason="Shunya classification",
                        triggered_by="shunya"
                    )
                    logger.info(
                        f"Updated lead {lead.id} status: {old_status.value if old_status else None} -> {new_status_value.value}",
                        extra={"lead_id": lead.id, "old_status": old_status.value if old_status else None, "new_status": new_status_value.value}
                    )
        
        # Create Appointment if booked (idempotent: check for existing)
        appointment_created = False
        if qualification_status == "qualified_booked":
            # Extract appointment details from transcript or analysis
            appointment_details = self._extract_appointment_details(transcript_text, complete_analysis)
            
            if appointment_details and call.contact_card_id:
                # Check for existing appointment (idempotency: don't create duplicate)
                existing_appointment = db.query(Appointment).filter(
                    Appointment.lead_id == call.lead_id,
                    Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED])
                ).first()
                
                if not existing_appointment:
                    appointment_address = appointment_details.get("address")
                    
                    # Update ContactCard.address if provided (triggers property enrichment)
                    contact = db.query(ContactCard).filter(ContactCard.id == call.contact_card_id).first()
                    previous_address = None
                    if contact and appointment_address:
                        previous_address = contact.address
                        # Update contact card address (this will trigger property enrichment via update_contact_address)
                        update_contact_address(
                            db=db,
                            contact=contact,
                            new_address=appointment_address,
                            city=None,
                            state=None,
                            postal_code=None
                        )
                        # Refresh to get updated property snapshot if available
                        db.refresh(contact)
                    
                    # Create appointment with address from Shunya
                    appointment = Appointment(
                        id=str(uuid4()),
                        lead_id=call.lead_id,
                        contact_card_id=call.contact_card_id,
                        company_id=company_id,
                        scheduled_start=appointment_details.get("scheduled_start"),
                        scheduled_end=appointment_details.get("scheduled_end"),
                        location=appointment_address,  # Legacy field
                        location_address=appointment_address,  # New field from Shunya
                        status=AppointmentStatus.SCHEDULED
                    )
                    
                    # Sync lat/lng from contact card property snapshot if available
                    if contact and contact.property_snapshot:
                        # Property enrichment may have geocoded the address
                        # Check if property snapshot has lat/lng (format may vary)
                        prop_snapshot = contact.property_snapshot
                        if isinstance(prop_snapshot, dict):
                            # Try common geocoding field names
                            lat = prop_snapshot.get("latitude") or prop_snapshot.get("lat") or prop_snapshot.get("geo_lat")
                            lng = prop_snapshot.get("longitude") or prop_snapshot.get("lng") or prop_snapshot.get("geo_lng")
                            if lat and lng:
                                try:
                                    appointment.location_lat = float(lat)
                                    appointment.location_lng = float(lng)
                                    appointment.geo_lat = float(lat)  # Also populate legacy field
                                    appointment.geo_lng = float(lng)  # Also populate legacy field
                                except (ValueError, TypeError):
                                    pass  # Skip if not numeric
                    
                    db.add(appointment)
                    db.flush()  # Get ID
                    appointment_created = True
                    
                    emit(
                        event_name="appointment.created",
                        payload={
                            "appointment_id": appointment.id,
                            "lead_id": call.lead_id,
                            "scheduled_start": appointment.scheduled_start.isoformat() if appointment.scheduled_start else None
                        },
                        tenant_id=company_id,
                        lead_id=str(call.lead_id)
                    )
        
        # Create Tasks from pending actions (idempotent: use unique keys)
        if pending_actions and call.contact_card_id:
            for action in pending_actions:
                action_text = action.get("action") if isinstance(action, dict) else str(action)
                due_at = action.get("due_at") if isinstance(action, dict) else None
                
                # Generate unique key for this task
                task_unique_key = generate_task_unique_key(
                    source=TaskSource.SHUNYA,
                    description=action_text,
                    contact_card_id=call.contact_card_id,
                )
                
                # Check if task already exists (idempotency)
                if not task_exists_by_unique_key(db, company_id, task_unique_key):
                    task = Task(
                        id=str(uuid4()),
                        company_id=company_id,
                        contact_card_id=call.contact_card_id,
                        lead_id=call.lead_id,
                        call_id=call.call_id,
                        description=action_text,
                        assigned_to=TaskAssignee.CSR,  # Default to CSR
                        source=TaskSource.SHUNYA,
                        unique_key=task_unique_key,
                        due_at=datetime.fromisoformat(due_at) if due_at and isinstance(due_at, str) else None,
                        status=TaskStatus.OPEN
                    )
                    db.add(task)
                    logger.debug(
                        f"Created task from Shunya action for call {call.call_id}",
                        extra={"call_id": call.call_id, "task_description": action_text[:50]}
                    )
                else:
                    logger.debug(
                        f"Task already exists for call {call.call_id}, skipping duplicate",
                        extra={"call_id": call.call_id, "task_description": action_text[:50]}
                    )
        
        # Extract and update address (trigger property intelligence)
        # Use normalized entities
        entities = complete_analysis.get("entities", {})
        address = entities.get("address")
        if address and call.contact_card_id:
            contact = db.query(ContactCard).filter(ContactCard.id == call.contact_card_id).first()
            if contact:
                previous_address = contact.address
                update_contact_address(
                    db=db,
                    contact=contact,
                    new_address=address,
                    city=None,  # Could extract from analysis
                    state=None,
                    postal_code=None
                )
                # maybe_trigger_property_scrape is called inside update_contact_address
        
        # Create key signals
        await self._create_key_signals_from_analysis(
            db=db,
            call=call,
            company_id=company_id,
            complete_analysis=complete_analysis
        )
        
        # Emit lead.updated event (only if status changed)
        if call.lead_id and lead_status_changed:
            emit(
                event_name="lead.updated",
                payload={
                    "lead_id": call.lead_id,
                    "status": lead.status.value if lead else None,
                    "classification": qualification_status,
                    "status_changed": True
                },
                tenant_id=company_id,
                lead_id=str(call.lead_id)
            )
        
        # Note: processed_output_hash is already set in shunya_job_service.mark_succeeded()
        # This method is idempotent and safe to call multiple times
    
    async def _process_shunya_analysis_for_visit(
        self,
        db: Session,
        recording_session: RecordingSession,
        company_id: str,
        complete_analysis: Dict[str, Any],
        transcript_text: Optional[str],
        shunya_job: Optional[Any] = None  # Optional ShunyaJob for idempotency checking
    ):
        """
        Process Shunya analysis results for a sales visit.
        
        Maps Shunya outputs to:
        - RecordingAnalysis model
        - Appointment outcome
        - Lead status updates
        - Task creation
        
        Idempotency: This method is safe to call multiple times with the same analysis.
        Uses natural keys for tasks/signals and checks existing state before mutating.
        """
        from uuid import uuid4
        from app.utils.idempotency import (
            generate_output_payload_hash,
            generate_task_unique_key,
            generate_signal_unique_key,
            task_exists_by_unique_key,
            signal_exists_by_unique_key,
        )
        from app.models.shunya_job import ShunyaJobStatus
        
        # Idempotency guard: Check if this output has already been processed
        if shunya_job:
            output_hash = generate_output_payload_hash(complete_analysis)
            if (
                shunya_job.job_status == ShunyaJobStatus.SUCCEEDED
                and shunya_job.processed_output_hash == output_hash
            ):
                logger.info(
                    f"Shunya output for visit {recording_session.id} already processed (hash: {output_hash[:8]}...)",
                    extra={"recording_session_id": recording_session.id, "job_id": shunya_job.id}
                )
                return  # Already processed, no-op
        
        appointment = recording_session.appointment
        if not appointment:
            logger.warning(f"No appointment linked to recording session {recording_session.id}")
            return
        
        # Update appointment address from Shunya entities if provided
        entities = complete_analysis.get("entities", {})
        if isinstance(entities, dict):
            address = entities.get("address")
            if address and appointment.contact_card_id:
                # Update appointment location_address
                appointment.location_address = address
                appointment.location = address  # Also update legacy field
                
                # Update ContactCard.address (triggers property enrichment)
                contact = db.query(ContactCard).filter(ContactCard.id == appointment.contact_card_id).first()
                if contact:
                    previous_address = contact.address
                    update_contact_address(
                        db=db,
                        contact=contact,
                        new_address=address,
                        city=None,
                        state=None,
                        postal_code=None
                    )
                    # Refresh to get updated property snapshot if available
                    db.refresh(contact)
                    
                    # Sync lat/lng from contact card property snapshot if available
                    if contact.property_snapshot:
                        prop_snapshot = contact.property_snapshot
                        if isinstance(prop_snapshot, dict):
                            lat = prop_snapshot.get("latitude") or prop_snapshot.get("lat") or prop_snapshot.get("geo_lat")
                            lng = prop_snapshot.get("longitude") or prop_snapshot.get("lng") or prop_snapshot.get("geo_lng")
                            if lat and lng:
                                try:
                                    appointment.location_lat = float(lat)
                                    appointment.location_lng = float(lng)
                                    appointment.geo_lat = float(lat)
                                    appointment.geo_lng = float(lng)
                                except (ValueError, TypeError):
                                    pass
                
                # Also update scheduled_start if provided
                date_time = entities.get("appointment_date") or entities.get("scheduled_time")
                if date_time:
                    if isinstance(date_time, str):
                        try:
                            from dateutil import parser
                            parsed_datetime = parser.parse(date_time)
                        except (ValueError, ImportError):
                            try:
                                parsed_datetime = datetime.fromisoformat(date_time.replace('Z', '+00:00'))
                            except ValueError:
                                parsed_datetime = None
                    elif isinstance(date_time, datetime):
                        parsed_datetime = date_time
                    else:
                        parsed_datetime = None
                    
                    if parsed_datetime:
                        appointment.scheduled_start = parsed_datetime
        
        # Get outcome classification (normalized)
        # Check multiple sources for outcome
        outcome_classification = (
            complete_analysis.get("outcome") or
            complete_analysis.get("appointment_outcome") or
            "pending"
        )
        if isinstance(outcome_classification, str):
            outcome_classification = outcome_classification.lower().strip()
        else:
            outcome_classification = "pending"
        
        # DEBUG: Log what Shunya returned for visit outcome
        logger.info(
            f"Shunya response for visit {recording_session.id}: "
            f"outcome='{outcome_classification}' (from complete_analysis.outcome='{complete_analysis.get('outcome')}' "
            f"or appointment_outcome='{complete_analysis.get('appointment_outcome')}')",
            extra={
                "recording_session_id": recording_session.id,
                "outcome": outcome_classification,
                "outcome_raw": complete_analysis.get("outcome"),
                "appointment_outcome_raw": complete_analysis.get("appointment_outcome"),
                "complete_analysis_keys": list(complete_analysis.keys())
            }
        )
        
        # Map to AppointmentOutcome enum
        outcome_mapping = {
            "won": AppointmentOutcome.WON,
            "lost": AppointmentOutcome.LOST,
            "pending": AppointmentOutcome.PENDING,
            "no_show": AppointmentOutcome.NO_SHOW,
        }
        appointment_outcome = outcome_mapping.get(outcome_classification, AppointmentOutcome.PENDING)
        
        # Update appointment (idempotent: only if outcome changed)
        outcome_changed = False
        old_outcome = appointment.outcome
        if old_outcome != appointment_outcome:
            appointment.outcome = appointment_outcome
            outcome_changed = True
            
            if appointment_outcome in [AppointmentOutcome.WON, AppointmentOutcome.LOST]:
                appointment.status = AppointmentStatus.COMPLETED
                if not appointment.closed_at:
                    appointment.closed_at = datetime.utcnow()
            
            # Add last_outcome_update timestamp if field exists
            if hasattr(appointment, 'last_outcome_update'):
                appointment.last_outcome_update = datetime.utcnow()
            
            logger.info(
                f"Updated appointment {appointment.id} outcome: {old_outcome.value if old_outcome else None} -> {appointment_outcome.value}",
                extra={
                    "appointment_id": appointment.id,
                    "old_outcome": old_outcome.value if old_outcome else None,
                    "new_outcome": appointment_outcome.value
                }
            )
        
        # Update lead status (idempotent: only if status changed)
        lead_status_changed = False
        if appointment.lead_id:
            lead = db.query(Lead).filter(Lead.id == appointment.lead_id).first()
            if lead:
                old_status = lead.status
                new_status_value = None
                
                if appointment_outcome == AppointmentOutcome.WON:
                    new_status_value = LeadStatus.CLOSED_WON
                elif appointment_outcome == AppointmentOutcome.LOST:
                    new_status_value = LeadStatus.CLOSED_LOST
                
                # Only update if status actually changed
                if new_status_value and old_status != new_status_value:
                    lead.status = new_status_value
                    lead.deal_status = appointment_outcome.value
                    if not lead.closed_at:
                        lead.closed_at = datetime.utcnow()
                    lead_status_changed = True
                    
                    # Record status change (only if changed)
                    await self._record_lead_status_change(
                        db=db,
                        lead_id=lead.id,
                        company_id=company_id,
                        from_status=old_status.value if old_status else None,
                        to_status=new_status_value.value,
                        reason=f"Shunya visit analysis: {outcome_classification}",
                        triggered_by="shunya"
                    )
                    logger.info(
                        f"Updated lead {lead.id} status: {old_status.value if old_status else None} -> {new_status_value.value}",
                        extra={
                            "lead_id": lead.id,
                            "old_status": old_status.value if old_status else None,
                            "new_status": new_status_value.value
                        }
                    )
        
        # Store RecordingAnalysis
        analysis_id = str(uuid4())
        recording_analysis = RecordingAnalysis(
            id=analysis_id,
            recording_session_id=recording_session.id,
            appointment_id=appointment.id,
            lead_id=appointment.lead_id,
            company_id=company_id,
            outcome=outcome_classification,
            sentiment_score=complete_analysis.get("sentiment_score"),
            sop_compliance_score=complete_analysis.get("compliance", {}).get("compliance_score") if isinstance(complete_analysis.get("compliance"), dict) else None,
            analyzed_at=datetime.utcnow()
        )
        db.add(recording_analysis)
        
        # Create tasks from visit actions (idempotent: use unique keys)
        # Visit actions may be in pending_actions or visit_actions
        visit_actions = complete_analysis.get("visit_actions", []) or complete_analysis.get("pending_actions", [])
        if visit_actions and appointment.contact_card_id:
            for action in visit_actions:
                action_text = action.get("action") if isinstance(action, dict) else str(action)
                
                # Generate unique key for this task
                task_unique_key = generate_task_unique_key(
                    source=TaskSource.SHUNYA,
                    description=action_text,
                    contact_card_id=appointment.contact_card_id,
                )
                
                # Check if task already exists (idempotency)
                if not task_exists_by_unique_key(db, company_id, task_unique_key):
                    task = Task(
                        id=str(uuid4()),
                        company_id=company_id,
                        contact_card_id=appointment.contact_card_id,
                        lead_id=appointment.lead_id,
                        appointment_id=appointment.id,
                        description=action_text,
                        assigned_to=TaskAssignee.REP,
                        source=TaskSource.SHUNYA,
                        unique_key=task_unique_key,
                        status=TaskStatus.OPEN
                    )
                    db.add(task)
                    logger.debug(
                        f"Created task from Shunya visit action for appointment {appointment.id}",
                        extra={"appointment_id": appointment.id, "task_description": action_text[:50]}
                    )
                else:
                    logger.debug(
                        f"Task already exists for appointment {appointment.id}, skipping duplicate",
                        extra={"appointment_id": appointment.id, "task_description": action_text[:50]}
                    )
        
        # Create key signals from visit analysis (idempotent: use unique keys)
        if appointment.contact_card_id:
            await self._create_key_signals_from_visit_analysis(
                db=db,
                appointment=appointment,
                company_id=company_id,
                complete_analysis=complete_analysis
            )
        
        # Emit appointment outcome event (only if outcome changed)
        if outcome_changed:
            emit(
                event_name="appointment.outcome_updated",
                payload={
                    "appointment_id": appointment.id,
                    "outcome": appointment_outcome.value,
                    "lead_id": appointment.lead_id,
                    "outcome_changed": True
                },
                tenant_id=company_id,
                lead_id=str(appointment.lead_id) if appointment.lead_id else None
            )
        
        # Emit lead.updated event (only if status changed)
        if appointment.lead_id and lead_status_changed:
            emit(
                event_name="lead.updated",
                payload={
                    "lead_id": appointment.lead_id,
                    "status": lead.status.value if lead else None,
                    "outcome": appointment_outcome.value,
                    "status_changed": True
                },
                tenant_id=company_id,
                lead_id=str(appointment.lead_id)
            )
        
        # Note: processed_output_hash is already set in shunya_job_service.mark_succeeded()
        # This method is idempotent and safe to call multiple times
    
    async def _record_lead_status_change(
        self,
        db: Session,
        lead_id: str,
        company_id: str,
        from_status: Optional[str],
        to_status: str,
        reason: Optional[str],
        triggered_by: str
    ):
        """Record a lead status change in LeadStatusHistory."""
        history_entry = LeadStatusHistory(
            id=str(uuid4()),
            lead_id=lead_id,
            company_id=company_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            triggered_by=triggered_by
        )
        db.add(history_entry)
    
    def _extract_address_from_analysis(
        self,
        analysis: Dict[str, Any],
        transcript_text: str
    ) -> Optional[str]:
        """Extract address from Shunya analysis or transcript."""
        # Check analysis first
        entities = analysis.get("entities", {})
        if isinstance(entities, dict):
            address = entities.get("address")
            if address:
                return address
        
        # Fallback: extract from transcript (simple pattern matching)
        # In production, could use NER or regex patterns
        # For now, return None if not found in entities
        return None
    
    def _extract_appointment_details(
        self,
        transcript_text: str,
        analysis: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract appointment scheduling details from Shunya analysis.
        
        Uses Shunya contract fields:
        - entities.appointment_date or entities.scheduled_time for datetime
        - entities.address for customer address
        """
        # Check entities for date/time/address (using exact Shunya contract keys)
        entities = analysis.get("entities", {})
        if isinstance(entities, dict):
            # Use Shunya contract fields: appointment_date or scheduled_time
            date_time = entities.get("appointment_date") or entities.get("scheduled_time")
            # Use Shunya contract field: address
            address = entities.get("address")
            
            if date_time or address:
                # Parse date_time if it's a string
                parsed_datetime = None
                if date_time:
                    if isinstance(date_time, str):
                        try:
                            from dateutil import parser
                            parsed_datetime = parser.parse(date_time)
                        except (ValueError, ImportError):
                            # Fallback: try ISO format
                            try:
                                parsed_datetime = datetime.fromisoformat(date_time.replace('Z', '+00:00'))
                            except ValueError:
                                logger.warning(f"Could not parse appointment datetime: {date_time}")
                                parsed_datetime = None
                    elif isinstance(date_time, datetime):
                        parsed_datetime = date_time
                
                return {
                    "scheduled_start": parsed_datetime,
                    "scheduled_end": None,
                    "address": address
                }
        return None
    
    async def _analyze_visit_transcript(
        self,
        company_id: str,
        request_id: str,
        transcript_text: str,
        recording_session_id: str
    ) -> Dict[str, Any]:
        """Analyze visit transcript using Shunya meeting segmentation."""
        # Use meeting segmentation endpoint
        # Note: This endpoint expects call_id, but we can use a workaround
        # For now, return empty dict - actual implementation may need adaptation
        return {}
    
    async def _create_key_signals_from_analysis(
        self,
        db: Session,
        call: Call,
        company_id: str,
        complete_analysis: Dict[str, Any]
    ):
        """
        Create KeySignal entries from Shunya CSR call analysis.
        
        Idempotent: Uses unique keys to prevent duplicate signals.
        """
        from uuid import uuid4
        from app.utils.idempotency import (
            generate_signal_unique_key,
            signal_exists_by_unique_key,
        )
        
        if not call.contact_card_id:
            return  # Cannot create signals without contact card
        
        signals = []
        
        # High urgency signal
        urgency_signals = complete_analysis.get("urgency_signals", [])
        if urgency_signals:
            signals.append({
                "type": SignalType.OPPORTUNITY,
                "severity": SignalSeverity.HIGH,
                "title": "High urgency detected",
                "description": ", ".join(urgency_signals[:3])
            })
        
        # Multiple objections signal
        objections_count = len(complete_analysis.get("objections", {}).get("objections", []) if isinstance(complete_analysis.get("objections"), dict) else [])
        if objections_count >= 3:
            signals.append({
                "type": SignalType.RISK,
                "severity": SignalSeverity.MEDIUM,
                "title": f"{objections_count} objections raised",
                "description": "Multiple customer objections detected"
            })
        
        # Service not offered signal
        qualification = complete_analysis.get("qualification", {})
        if qualification.get("qualification_status", "").lower() == "qualified_service_not_offered":
            signals.append({
                "type": SignalType.OPPORTUNITY,
                "severity": SignalSeverity.HIGH,
                "title": "Service not offered",
                "description": "Customer qualified but service was not offered during call"
            })
        
        # Create signal records (idempotent: use unique keys)
        for signal_data in signals:
            # Generate unique key for this signal
            signal_unique_key = generate_signal_unique_key(
                signal_type=signal_data["type"],
                title=signal_data["title"],
                contact_card_id=call.contact_card_id,
            )
            
            # Check if signal already exists (idempotency)
            if not signal_exists_by_unique_key(db, company_id, signal_unique_key):
                signal = KeySignal(
                    id=str(uuid4()),
                    company_id=company_id,
                    contact_card_id=call.contact_card_id,
                    lead_id=call.lead_id,
                    signal_type=signal_data["type"],
                    severity=signal_data["severity"],
                    title=signal_data["title"],
                    description=signal_data.get("description"),
                    unique_key=signal_unique_key,
                    acknowledged=False
                )
                db.add(signal)
                logger.debug(
                    f"Created key signal for call {call.call_id}",
                    extra={"call_id": call.call_id, "signal_title": signal_data["title"]}
                )
            else:
                logger.debug(
                    f"Key signal already exists for call {call.call_id}, skipping duplicate",
                    extra={"call_id": call.call_id, "signal_title": signal_data["title"]}
                )
    
    async def _create_key_signals_from_visit_analysis(
        self,
        db: Session,
        appointment: Appointment,
        company_id: str,
        complete_analysis: Dict[str, Any]
    ):
        """
        Create KeySignal entries from Shunya sales visit analysis.
        
        Idempotent: Uses unique keys to prevent duplicate signals.
        """
        from uuid import uuid4
        from app.utils.idempotency import (
            generate_signal_unique_key,
            signal_exists_by_unique_key,
        )
        
        if not appointment.contact_card_id:
            return  # Cannot create signals without contact card
        
        signals = []
        
        # Missed opportunities from visit analysis
        missed_opportunities = complete_analysis.get("missed_opportunities", [])
        if missed_opportunities:
            for opp_text in missed_opportunities[:3]:  # Limit to first 3
                opp_text_str = opp_text if isinstance(opp_text, str) else str(opp_text)
                signals.append({
                    "type": SignalType.OPPORTUNITY,
                    "severity": SignalSeverity.MEDIUM,
                    "title": f"Missed Opportunity: {opp_text_str[:50]}",
                    "description": opp_text_str
                })
        
        # Create signal records (idempotent: use unique keys)
        for signal_data in signals:
            # Generate unique key for this signal
            signal_unique_key = generate_signal_unique_key(
                signal_type=signal_data["type"],
                title=signal_data["title"],
                contact_card_id=appointment.contact_card_id,
            )
            
            # Check if signal already exists (idempotency)
            if not signal_exists_by_unique_key(db, company_id, signal_unique_key):
                signal = KeySignal(
                    id=str(uuid4()),
                    company_id=company_id,
                    contact_card_id=appointment.contact_card_id,
                    lead_id=appointment.lead_id,
                    appointment_id=appointment.id,
                    signal_type=signal_data["type"],
                    severity=signal_data["severity"],
                    title=signal_data["title"],
                    description=signal_data.get("description"),
                    unique_key=signal_unique_key,
                    acknowledged=False
                )
                db.add(signal)
                logger.debug(
                    f"Created key signal for visit appointment {appointment.id}",
                    extra={"appointment_id": appointment.id, "signal_title": signal_data["title"]}
                )
            else:
                logger.debug(
                    f"Key signal already exists for visit appointment {appointment.id}, skipping duplicate",
                    extra={"appointment_id": appointment.id, "signal_title": signal_data["title"]}
                )


# Global service instance
shunya_integration_service = ShunyaIntegrationService()





