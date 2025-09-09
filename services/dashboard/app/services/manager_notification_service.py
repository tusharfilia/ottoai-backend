import requests
import logging
import json
from datetime import datetime
from typing import Dict, List
from sqlalchemy.orm import Session
from app.models import sales_manager, call

# Configure logging
logger = logging.getLogger(__name__)

# Expo push API URL
EXPO_PUSH_API_URL = 'https://exp.host/--/api/v2/push/send'

# Keep track of which calls we've already sent notifications for
SENT_NOTIFICATIONS = {}  # call_id -> timestamp

def send_unassigned_appointment_notification(
    db: Session,
    company_id: str,
    call_id: int,
    customer_name: str,
    appointment_date: str = None
) -> Dict:
    """
    Send notifications to all managers in a company about a new unassigned appointment
    
    Args:
        db: Database session
        company_id: Company ID
        call_id: ID of the call/appointment
        customer_name: Name of the customer
        appointment_date: ISO string of appointment date (optional)
        
    Returns:
        dict: Summary of notification results
    """
    try:
        # Get all managers for the company
        managers = db.query(sales_manager.SalesManager).filter_by(company_id=company_id).all()
        
        if not managers:
            logger.warning(f"No managers found for company {company_id}")
            return {
                "success": False,
                "message": "No managers found for company",
                "sent_count": 0,
                "total_managers": 0
            }
        
        # Keep track of successful notifications
        success_count = 0
        
        # Send notification to each manager
        for manager in managers:
            if not manager.expo_push_token:
                logger.info(f"Manager {manager.user_id} has no push token registered")
                continue
            
            # Send the notification
            result = send_manager_notification(
                expo_push_token=manager.expo_push_token,
                call_id=call_id,
                customer_name=customer_name,
                appointment_date=appointment_date
            )
            
            if result:
                success_count += 1
                # Mark this call as having been notified
                SENT_NOTIFICATIONS[str(call_id)] = datetime.utcnow()
        
        logger.info(f"Sent unassigned appointment notifications to {success_count}/{len(managers)} managers")
        
        return {
            "success": True,
            "message": f"Sent notifications to {success_count}/{len(managers)} managers",
            "sent_count": success_count,
            "total_managers": len(managers)
        }
    
    except Exception as e:
        logger.error(f"Error sending manager notifications: {str(e)}")
        return {
            "success": False,
            "message": f"Error sending notifications: {str(e)}",
            "sent_count": 0,
            "total_managers": 0
        }

def send_manager_notification(
    expo_push_token: str, 
    call_id: int, 
    customer_name: str, 
    appointment_date: str = None
) -> bool:
    """
    Send a push notification to a manager's device using Expo Push Notifications
    
    Args:
        expo_push_token: Expo Push Token from the device
        call_id: ID of the call/appointment
        customer_name: Name of the customer
        appointment_date: ISO string of appointment date (optional)
        
    Returns:
        bool: True if the notification was sent successfully
    """
    try:
        headers = {
            'Content-Type': 'application/json',
        }
        
        # Format the date for display if provided
        display_date = ""
        if appointment_date:
            try:
                date_obj = datetime.fromisoformat(appointment_date.replace('Z', '+00:00'))
                display_date = date_obj.strftime("%b %d")
                display_date = f" on {display_date}"
            except ValueError:
                pass
        
        # Prepare the notification payload for Expo Push API
        payload = [{
            'to': expo_push_token,
            'title': 'New Appointment Needs Assignment',
            'body': f'New appointment with {customer_name}{display_date} needs to be assigned to a rep.',
            'data': {
                'type': 'unassigned_appointment',
                'callId': str(call_id),
                'customerName': customer_name,
                'appointmentDate': appointment_date,
                'timestamp': datetime.utcnow().isoformat()
            },
            'sound': 'default',
            'priority': 'high'
        }]
        
        # Send the notification
        response = requests.post(
            EXPO_PUSH_API_URL,
            headers=headers,
            data=json.dumps(payload)
        )
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data and len(response_data) > 0:
                if response_data[0].get('status') == 'ok':
                    logger.info(f"Successfully sent notification for call {call_id}")
                    return True
                else:
                    error = response_data[0].get('message', 'Unknown error')
                    logger.error(f"Failed to send notification for call {call_id}: {error}")
            else:
                logger.error(f"Empty response when sending notification for call {call_id}")
        else:
            logger.error(f"Failed to send notification for call {call_id}, status code: {response.status_code}")
        
        return False
        
    except Exception as e:
        logger.error(f"Error sending manager notification: {str(e)}")
        return False 