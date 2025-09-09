import json
import os
from typing import Dict, Any, List, Optional
import openai
from app.services.transcript_analysis.processes.base_process import BaseAnalysisProcess

class V0AnalysisProcess(BaseAnalysisProcess):
    """
    V0 transcript analysis process.
    
    This is the initial version that uses a single OpenAI API call to analyze 
    the entire transcript and extract all the required information in one go.
    """
    
    def __init__(self):
        """Initialize the V0AnalysisProcess."""
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    @property
    def name(self) -> str:
        return "v0"
    
    @property
    def description(self) -> str:
        return "Initial version (v0) that extracts all information in a single pass"
    
    def analyze(self, transcript_data: Dict[Any, Any], call_metadata: Dict[Any, Any]) -> Dict[Any, Any]:
        """
        Analyze the transcript using a single OpenAI API call.
        
        Args:
            transcript_data: Preprocessed transcript data
            call_metadata: Metadata about the call
            
        Returns:
            Dict with structured analysis results
        """
        if not transcript_data or not transcript_data.get("text"):
            return {"error": "No transcript text provided"}
        
        # Format the system prompt with the requirements and context
        system_prompt = """
You are an expert call analysis system specializing in sales calls.
Analyze the provided transcript from a sales appointment between a sales representative and a customer.
Extract key information and generate a structured JSON summary.

Focus on the following categories:
1. Greeting & Introduction
- Did the rep greet the customer?
- Did the rep introduce themselves by name?
- Did the rep mention their company name?

2. Customer Engagement & Outcome
- Did the customer make a purchase?
- Is the customer still deciding?
- Did the customer reject the offer?
- Was a signature or verbal agreement mentioned?

3. Quoted Price
- Was a price or price range quoted?
- Was financing, insurance, or payment discussed?
- Were discounts mentioned?

4. Company Name Mentions
- Was the company name mentioned at all?
- Was it mentioned more than once?

5. Farewell & Next Steps
- Did the rep say goodbye professionally?
- Was a follow-up scheduled?
- Did the rep mention sending anything (quote, photos, etc.)?
- Was there any mention of paperwork to sign?

For each identified item, include the relevant quote from the transcript and the timestamp.
Analyze thoroughly but be concise in your output.

The output should be structured as a JSON object with the following format:
{
  "greeting": {
    "rep_greeted_customer": true/false,
    "rep_introduced_self": true/false,
    "company_name_mentioned": true/false,
    "greeting_quote": "...",
    "introduction_quote": "...",
    "company_mention_quote": "...",
    "greeting_timestamp": "00:00:00",
    "introduction_timestamp": "00:00:00",
    "company_mention_timestamp": "00:00:00"
  },
  "customer_decision": {
    "status": "bought"/"deciding"/"rejected",
    "quote": "...",
    "timestamp": "00:00:00",
    "agreement_mentioned": true/false,
    "agreement_quote": "...",
    "agreement_timestamp": "00:00:00"
  },
  "quoted_price": {
    "price_quoted": true/false,
    "price": "$X,XXX",
    "quote": "...",
    "timestamp": "00:00:00",
    "payment_discussed": true/false,
    "payment_quote": "...",
    "payment_timestamp": "00:00:00",
    "discount_mentioned": true/false,
    "discount_quote": "...",
    "discount_timestamp": "00:00:00"
  },
  "company_mentions": {
    "mentioned": true/false,
    "mention_count": X,
    "quotes": ["..."],
    "timestamps": ["00:00:00"]
  },
  "farewell": {
    "professional_goodbye": true/false,
    "goodbye_quote": "...",
    "goodbye_timestamp": "00:00:00",
    "follow_up_scheduled": true/false,
    "follow_up_quote": "...",
    "follow_up_timestamp": "00:00:00",
    "follow_up_date": "...",
    "document_sending_mentioned": true/false,
    "document_type": "quote"/"photos"/etc.,
    "document_quote": "...",
    "document_timestamp": "00:00:00",
    "paperwork_mentioned": true/false,
    "paperwork_quote": "...",
    "paperwork_timestamp": "00:00:00"
  }
}
"""
            
        # Prepare metadata for context
        metadata_text = f"""
CALL CONTEXT:
Date and time: {call_metadata.get('quote_date', 'Unknown')}
Sales rep: {call_metadata.get('rep_name', 'Unknown')}, {call_metadata.get('rep_phone', 'Unknown')}, {call_metadata.get('rep_email', 'Unknown')}, {call_metadata.get('company_name', 'Unknown')}
Customer: {call_metadata.get('customer_name', 'Unknown')}, {call_metadata.get('customer_address', 'Unknown')}, {call_metadata.get('customer_phone', 'Unknown')}
Roofing issue: {call_metadata.get('problem', 'Unknown')}
"""

        transcript_text = transcript_data.get("text", "")

        # Call OpenAI to analyze the transcript
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{metadata_text}\n\nTRANSCRIPT:\n{transcript_text}"}
                ],
                response_format={"type": "json_object"}
            )
            
            # Parse the JSON response
            result = json.loads(response.choices[0].message.content)
            
            # Ensure the result has the expected structure
            self._validate_response(result)
            
            return result
        except Exception as e:
            print(f"Error analyzing transcript: {str(e)}")
            return {"error": str(e)}
    
    def _validate_response(self, result: Dict[Any, Any]) -> None:
        """
        Validate that the response has the expected structure.
        Add default sections if they're missing.
        """
        expected_sections = [
            "greeting", "customer_decision", "quoted_price", 
            "company_mentions", "farewell"
        ]
        
        for section in expected_sections:
            if section not in result:
                result[section] = {} 