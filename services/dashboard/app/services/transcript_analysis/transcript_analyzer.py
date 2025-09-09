import json
import os
from typing import Dict, Any, List, Optional, Type
from sqlalchemy.orm import Session
from app.models.call import Call
from app.models.transcript_analysis import TranscriptAnalysis
from app.services.transcript_analysis.processes.base_process import BaseAnalysisProcess
from app.services.transcript_analysis.processes.v0_process import V0AnalysisProcess
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class TranscriptAnalyzer:
    """
    Main service for analyzing call transcripts using LLM and extracting structured data.
    
    This class serves as the entry point for transcript analysis and handles:
    1. Loading the appropriate analysis process implementation
    2. Database interactions for storing results
    3. Transcript data preprocessing
    
    It delegates the actual analysis logic to the selected process implementation.
    """
    
    # Registry of available analysis processes
    _process_registry = {
        "v0": V0AnalysisProcess
    }
    
    def __init__(self, process_name: str = "v0"):
        """
        Initialize the TranscriptAnalyzer with a specific analysis process.
        
        Args:
            process_name: Name of the analysis process to use (default: "v0")
                          Must be a key in the _process_registry
        """
        if process_name not in self._process_registry:
            raise ValueError(f"Unknown analysis process: {process_name}. "
                             f"Available processes: {list(self._process_registry.keys())}")
        
        # Initialize the selected analysis process
        self.process_class = self._process_registry[process_name]
        self.process = self.process_class()
        
    @classmethod
    def register_process(cls, name: str, process_class: Type[BaseAnalysisProcess]) -> None:
        """
        Register a new analysis process implementation.
        
        Args:
            name: Name to register the process under
            process_class: Class implementing the analysis process
        """
        cls._process_registry[name] = process_class
    
    @classmethod
    def get_available_processes(cls) -> List[str]:
        """
        Get a list of available analysis process names.
        
        Returns:
            List of process names that can be used
        """
        return list(cls._process_registry.keys())
    
    def analyze_transcript(self, transcript_data: Dict[Any, Any], call_metadata: Dict[Any, Any]) -> Dict[Any, Any]:
        """
        Analyze a transcript using the selected process.
        
        Args:
            transcript_data: Transcript data to analyze
            call_metadata: Metadata about the call
            
        Returns:
            Structured analysis results
        """
        # Preprocess the transcript data
        preprocessed_data = self._preprocess_transcript(transcript_data)
        
        # Delegate to the selected process
        return self.process.analyze(preprocessed_data, call_metadata)
    
    def analyze_and_store(self, call_id: int, db: Session, process_name: Optional[str] = None) -> Dict[Any, Any]:
        """
        Analyze a call transcript and store the results in the database.
        
        Args:
            call_id: ID of the call to analyze
            db: Database session
            process_name: Optional process name to use for this specific analysis
                          (overrides the one set during initialization)
            
        Returns:
            Analysis results
        """
        # Switch process if a different one is specified
        original_process = None
        if process_name and process_name != self.process.__class__.__name__:
            if process_name not in self._process_registry:
                raise ValueError(f"Unknown analysis process: {process_name}")
            
            # Store the current process and create the new one
            original_process = self.process
            self.process = self._process_registry[process_name]()
        
        try:
            # Get call from database
            call = db.query(Call).filter(Call.call_id == call_id).first()
            if not call:
                return {"error": f"Call with ID {call_id} not found"}
            
            # Get transcript data from any available transcript field
            transcript_data = self._get_transcript_data(call)
            if not transcript_data:
                return {"error": "No in-person transcript available for analysis. Please make sure the call has an in_person_transcript field populated."}
            
            # Get metadata about the call
            call_metadata = self._get_call_metadata(call, db)
            
            # Analyze the transcript
            analysis_result = self.analyze_transcript(transcript_data, call_metadata)
            
            # Check for errors
            if "error" in analysis_result:
                return analysis_result
            
            # Create a new TranscriptAnalysis record
            # This now also updates the call table fields directly
            analysis = self._create_analysis_record(
                call_id, 
                analysis_result, 
                db, 
                process_name=self.process.__class__.__name__
            )
            
            return analysis_result
            
        finally:
            # Restore the original process if we switched
            if original_process:
                self.process = original_process
    
    def _preprocess_transcript(self, transcript_data: Dict[Any, Any]) -> Dict[Any, Any]:
        """
        Preprocess the transcript data before analysis.
        
        Args:
            transcript_data: Raw transcript data
            
        Returns:
            Preprocessed transcript data ready for analysis
        """
        # Extract and format transcript text
        transcript_text = ""
        timestamps = {}
        
        # Handle both Deepgram and basic transcripts
        if "results" in transcript_data and "channels" in transcript_data["results"]:
            # Process Deepgram format
            for channel in transcript_data["results"]["channels"]:
                for alternative in channel["alternatives"]:
                    # Check if we have paragraphs
                    if "paragraphs" in alternative and "paragraphs" in alternative["paragraphs"]:
                        paragraphs = alternative["paragraphs"]["paragraphs"]
                        for paragraph in paragraphs:
                            if "text" in paragraph and "start" in paragraph:
                                text = paragraph["text"]
                                start_time = paragraph["start"]
                                transcript_text += text + " "
                                timestamps[text] = self._format_timestamp(start_time)
                    # Fall back to word-by-word parsing
                    elif "words" in alternative:
                        for word in alternative["words"]:
                            word_text = word.get("word", "")
                            start_time = word.get("start", 0)
                            transcript_text += word_text + " "
                            timestamps[word_text] = self._format_timestamp(start_time)
                    # Fall back to full transcript if no words or paragraphs
                    elif "transcript" in alternative:
                        transcript_text = alternative["transcript"]
        else:
            # Handle simple transcript text
            transcript_text = transcript_data.get("text", "")
        
        return {
            "text": transcript_text,
            "timestamps": timestamps,
            "raw_data": transcript_data
        }
    
    def _get_transcript_data(self, call: Call) -> Dict[Any, Any]:
        """
        Extract transcript data from a call record.
        Only uses the in_person_transcript field.
        
        Args:
            call: Call record
            
        Returns:
            Transcript data or empty dict if none available
        """
        transcript_data = {}
        
        # Only use in_person_transcript
        if call.in_person_transcript:
            # Try to parse as JSON first
            try:
                transcript_data = json.loads(call.in_person_transcript)
            except json.JSONDecodeError:
                # If not valid JSON, use as plain text
                transcript_data = {"text": call.in_person_transcript}
        
        return transcript_data
    
    def _get_call_metadata(self, call: Call, db: Session) -> Dict[Any, Any]:
        """
        Extract metadata about the call for context in the analysis.
        
        Args:
            call: Call record
            db: Database session
            
        Returns:
            Dict with call metadata
        """
        from app.models.user import User
        from app.models.sales_rep import SalesRep
        
        metadata = {
            "call_id": call.call_id,
            "quote_date": call.quote_date.isoformat() if call.quote_date else None,
            "customer_name": call.name,
            "customer_address": call.address,
            "customer_phone": call.phone_number,
            "problem": call.problem,
            "company_id": call.company_id
        }
        
        # Get rep info if available
        if call.assigned_rep_id:
            rep = db.query(SalesRep).filter(SalesRep.user_id == call.assigned_rep_id).first()
            if rep:
                user = db.query(User).filter(User.id == rep.user_id).first()
                if user:
                    metadata.update({
                        "rep_name": user.name,
                        "rep_email": user.email,
                        "rep_phone": user.phone_number,
                        "company_name": rep.company.name if rep.company else None
                    })
        
        return metadata
    
    def _create_analysis_record(
        self, 
        call_id: int, 
        analysis_result: Dict[Any, Any], 
        db: Session,
        process_name: str
    ) -> TranscriptAnalysis:
        """
        Create a TranscriptAnalysis record from the analysis result.
        
        Args:
            call_id: ID of the call
            analysis_result: Analysis result from the LLM
            db: Database session
            process_name: Name of the process that generated this analysis
            
        Returns:
            The created TranscriptAnalysis record
        """
        # Check if we already have an analysis for this call
        existing_analysis = db.query(TranscriptAnalysis).filter(
            TranscriptAnalysis.call_id == call_id
        ).order_by(TranscriptAnalysis.analysis_version.desc()).first()
        
        # Set the version number
        version = 1
        if existing_analysis:
            version = existing_analysis.analysis_version + 1
        
        # Extract fields from analysis_result
        greeting_data = analysis_result.get("greeting", {})
        customer_decision_data = analysis_result.get("customer_decision", {})
        quoted_price_data = analysis_result.get("quoted_price", {})
        company_mentions_data = analysis_result.get("company_mentions", {})
        farewell_data = analysis_result.get("farewell", {})
        
        # Create new analysis record
        analysis = TranscriptAnalysis(
            call_id=call_id,
            analysis_version=version,
            model_version=process_name,  # Store process name as model version
            raw_analysis=analysis_result,
            
            # Store section data
            greeting=greeting_data,
            customer_decision=customer_decision_data,
            quoted_price=quoted_price_data,
            company_mentions=company_mentions_data,
            farewell=farewell_data,
            
            # Extract specific fields from greeting
            rep_greeting_quote=greeting_data.get("greeting_quote"),
            rep_greeting_timestamp=greeting_data.get("greeting_timestamp"),
            rep_introduction_quote=greeting_data.get("introduction_quote"),
            rep_introduction_timestamp=greeting_data.get("introduction_timestamp"),
            company_mention_quote=greeting_data.get("company_mention_quote"),
            company_mention_timestamp=greeting_data.get("company_mention_timestamp"),
            
            # Extract specific fields from company mentions
            company_mention_count=company_mentions_data.get("mention_count", 0),
            
            # Extract specific fields from quoted price
            price_quote=quoted_price_data.get("quote"),
            price_quote_timestamp=quoted_price_data.get("timestamp"),
            price_amount=quoted_price_data.get("price"),
            payment_discussion_quote=quoted_price_data.get("payment_quote"),
            payment_discussion_timestamp=quoted_price_data.get("payment_timestamp"),
            discount_mention_quote=quoted_price_data.get("discount_quote"),
            discount_mention_timestamp=quoted_price_data.get("discount_timestamp"),
            
            # Extract specific fields from customer decision
            customer_decision_quote=customer_decision_data.get("quote"),
            customer_decision_timestamp=customer_decision_data.get("timestamp"),
            customer_decision_status=customer_decision_data.get("status"),
            agreement_mention_quote=customer_decision_data.get("agreement_quote"),
            agreement_mention_timestamp=customer_decision_data.get("agreement_timestamp"),
            
            # Extract specific fields from farewell
            goodbye_quote=farewell_data.get("goodbye_quote"),
            goodbye_timestamp=farewell_data.get("goodbye_timestamp"),
            follow_up_quote=farewell_data.get("follow_up_quote"),
            follow_up_timestamp=farewell_data.get("follow_up_timestamp"),
            follow_up_date=farewell_data.get("follow_up_date"),
            document_sending_quote=farewell_data.get("document_quote"),
            document_sending_timestamp=farewell_data.get("document_timestamp"),
            document_type=farewell_data.get("document_type"),
            paperwork_mention_quote=farewell_data.get("paperwork_quote"),
            paperwork_mention_timestamp=farewell_data.get("paperwork_timestamp")
        )
        
        # Add to database
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        
        # Immediately update the call record with the decision information
        try:
            # Get the call record
            call = db.query(Call).filter(Call.call_id == call_id).first()
            if call:
                logger.info(f"Updating call fields for call ID {call_id} immediately after analysis")
                
                # Update call fields based on analysis data
                customer_decision_status = analysis.customer_decision_status
                
                # Update bought and still_deciding based on decision status
                if customer_decision_status:
                    if customer_decision_status.lower() == "bought":
                        call.bought = True
                        call.still_deciding = False
                        logger.info(f"Customer decision: BOUGHT")
                    elif customer_decision_status.lower() == "deciding":
                        call.bought = False
                        call.still_deciding = True
                        logger.info(f"Customer decision: STILL DECIDING")
                    elif customer_decision_status.lower() == "rejected":
                        call.bought = False
                        call.still_deciding = False
                        logger.info(f"Customer decision: REJECTED")
                
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
                            logger.info(f"Updated price_if_bought to {price_value}")
                    except (ValueError, AttributeError, TypeError):
                        logger.warning(f"Could not convert price to float: {analysis.price_amount}")
                
                # Update reason_for_lost_sale
                if not call.bought and not call.still_deciding and analysis.customer_decision_quote:
                    call.reason_for_lost_sale = analysis.customer_decision_quote
                    logger.info(f"Updated reason_for_lost_sale: {call.reason_for_lost_sale}")
                
                # Update reason_for_deciding
                if call.still_deciding and analysis.customer_decision_quote:
                    call.reason_for_deciding = analysis.customer_decision_quote
                    logger.info(f"Updated reason_for_deciding: {call.reason_for_deciding}")
                
                # Update the timestamp
                call.updated_at = datetime.utcnow()
                
                # Commit changes to database
                db.commit()
                logger.info(f"Successfully updated call record with decision information immediately after analysis")
        except Exception as e:
            logger.error(f"Error updating call record after analysis: {e}", exc_info=True)
        
        return analysis
    
    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Format seconds into HH:MM:SS timestamp."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}" 