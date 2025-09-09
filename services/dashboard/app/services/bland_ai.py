import requests
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from ..models import sales_rep, sales_manager, call, scheduled_call, company
from datetime import datetime, time
import schedule
import threading
import time as time_lib
import os
import logging
from datetime import datetime, timedelta
import re
import pytz

class BlandAI:
    BASE_URL = "https://api.bland.ai/v1"
    API_KEY = os.getenv("BLAND_API_KEY")
    ENCRYPTED_KEY = os.getenv("BLAND_ENCRYPTED_KEY")
    HOMEOWNER_FOLLOWUP_PATHWAY = os.getenv("BLAND_HOMEOWNER_PATHWAY", "fced9640-c4f7-49ec-a9bb-bf3053d0936c")
    WEBHOOK_BASE_URL = os.getenv("API_URL")
    def __init__(self, auto_start_schedulers=True):
        self.headers = {
            "authorization": self.API_KEY,
            "encrypted_key": self.ENCRYPTED_KEY,
            "Content-Type": "application/json"
        }

    def make_call(
        self,
        phone_number: str,
        pathway: str,
        webhook_url: str = None,
        metadata: Dict = None,
        request_data: Dict = None,
        call_record_id: Optional[int] = None,
        db: Optional[Session] = None,
        start_time: Optional[datetime] = None,
        company_address: Optional[str] = None
    ) -> Dict:
        """Make a call using Bland.ai"""
        try:
            if request_data:
                request_data = request_data.copy()
                for key, value in request_data.items():
                    if isinstance(value, datetime):
                        request_data[key] = value.isoformat()

            payload = {
                "phone_number": phone_number,
                "pathway_id": pathway,
                "request_data": request_data,
                "voice": "maya",
                "model": "enhanced",
                "record": True,
                "webhook": webhook_url,
                "metadata": metadata or {},
                "language": "en"
            }

            if start_time: 
                formatted_time = start_time.strftime("%Y-%m-%d %H:%M:%S +00:00")
                payload["start_time"] = formatted_time
                print(f"Scheduling call for: {formatted_time}")

            print(f"Attempting Bland.ai call with payload: {payload}")

            response = requests.post(
                f"{self.BASE_URL}/calls",
                json=payload,
                headers=self.headers
            )
            
            response.raise_for_status()
            result = response.json()
            print(f"Bland.ai call {'scheduled' if start_time else 'initiated'}. Response: {result}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"Bland.ai API call failed with error: {str(e)}")
            if hasattr(e.response, 'text'):
                print(f"Error response: {e.response.text}")
            raise

        except Exception as e:
            print(f"Unexpected error making Bland.ai call: {str(e)}")
            raise

    def analyze_call(
        self,
        call_id: str,
        questions: List[str],
        goal: str
    ) -> Dict:
        """Analyze a completed call"""
        
        payload = {
            "goal": goal,
            "questions": questions
        }

        response = requests.post(
            f"{self.BASE_URL}/calls/{call_id}/analyze",
            json=payload,
            headers=self.headers
        )
        return response.json()

    def make_followup_call(
        self,
        customer_phone: str,
        request_data: Dict,
        reason_for_lost_sale: str,
        call_record_id: Optional[str] = None,
        scheduled_call_id: Optional[str] = None,
        db: Optional[Session] = None,
        start_time: Optional[datetime] = None
    ) -> Dict:
        """Make a follow-up call to customer who didn't purchase"""
        address = None
        if request_data and request_data.get("address"):
            address = request_data.get("address")
        
        if not start_time and address:
            start_time = self.get_appropriate_call_time(address)
            print(f"Calculated appropriate customer follow-up call time: {start_time}")
            
        return self.make_call(
            phone_number=customer_phone,
            pathway=self.HOMEOWNER_FOLLOWUP_PATHWAY,
            webhook_url=f"https://{self.WEBHOOK_BASE_URL}/webhook/bland-callback",
            metadata={
                "call_type": "homeowner_followup",
                "reason_for_lost_sale": reason_for_lost_sale,
                "original_call_id": call_record_id,
                "scheduled_call_id": scheduled_call_id,
                "request_data": request_data
            },
            request_data=request_data,
            start_time=start_time,
            company_address=address
        )

    def get_timezone_from_address(self, address: str) -> str:
        """
        Get timezone string from address.
        Returns default 'America/New_York' if timezone cannot be determined.
        """
        if not address:
            return 'America/New_York'  # Default timezone
        
        # Extract state from address using regex
        state_match = re.search(r'[,\s]([A-Z]{2})[,\s\d]', address.upper())
        if not state_match:
            return 'America/New_York'  # Default timezone
        
        state = state_match.group(1)
        
        # Map states to timezone strings
        timezone_mapping = {
            # Eastern Time (UTC-5)
            'ME': 'America/New_York', 'NH': 'America/New_York', 'VT': 'America/New_York', 
            'MA': 'America/New_York', 'RI': 'America/New_York', 'CT': 'America/New_York', 
            'NY': 'America/New_York', 'NJ': 'America/New_York', 'DE': 'America/New_York', 
            'MD': 'America/New_York', 'DC': 'America/New_York', 'VA': 'America/New_York', 
            'NC': 'America/New_York', 'SC': 'America/New_York', 'GA': 'America/New_York', 
            'FL': 'America/New_York', 'PA': 'America/New_York', 'WV': 'America/New_York', 
            'OH': 'America/New_York', 'MI': 'America/Detroit', 'IN': 'America/Indiana/Indianapolis',
            'KY': 'America/New_York',
            
            # Central Time (UTC-6)
            'AL': 'America/Chicago', 'TN': 'America/Chicago', 'MS': 'America/Chicago', 
            'IL': 'America/Chicago', 'MO': 'America/Chicago', 'AR': 'America/Chicago', 
            'LA': 'America/Chicago', 'IA': 'America/Chicago', 'MN': 'America/Chicago', 
            'WI': 'America/Chicago', 'OK': 'America/Chicago', 'TX': 'America/Chicago', 
            'NE': 'America/Chicago', 'KS': 'America/Chicago', 'SD': 'America/Chicago', 
            'ND': 'America/Chicago',
            
            # Mountain Time (UTC-7)
            'MT': 'America/Denver', 'WY': 'America/Denver', 'CO': 'America/Denver', 
            'NM': 'America/Denver', 'AZ': 'America/Phoenix', 'UT': 'America/Denver', 
            'ID': 'America/Denver',
            
            # Pacific Time (UTC-8)
            'WA': 'America/Los_Angeles', 'OR': 'America/Los_Angeles', 
            'CA': 'America/Los_Angeles', 'NV': 'America/Los_Angeles',
            
            # Alaska Time (UTC-9)
            'AK': 'America/Anchorage',
            
            # Hawaii Time (UTC-10)
            'HI': 'Pacific/Honolulu'
        }
        
        return timezone_mapping.get(state, 'America/New_York')

    def get_appropriate_call_time(self, address: str) -> datetime:
        """
        Determine appropriate call time between 9am and 9:30pm local time.
        Returns a datetime object with the appropriate call time.
        """
        # Get timezone based on address
        tz_string = self.get_timezone_from_address(address)
        local_tz = pytz.timezone(tz_string)
        
        # Get current time in the local timezone
        current_time = datetime.now(pytz.UTC).astimezone(local_tz)
        
        # Define business hours constraints
        earliest_time = current_time.replace(hour=9, minute=0, second=0, microsecond=0)
        latest_time = current_time.replace(hour=21, minute=30, second=0, microsecond=0)
        
        # If current time is before 9am, schedule for 9am today
        if current_time < earliest_time:
            return earliest_time
        
        # If current time is after 9:30pm, schedule for 9am next day
        if current_time > latest_time:
            next_day = current_time + timedelta(days=1)
            return next_day.replace(hour=9, minute=0, second=0, microsecond=0)
        
        # Otherwise, schedule for current time + 15 minutes
        return current_time + timedelta(minutes=15)
