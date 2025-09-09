import requests
import logging
import json
from datetime import datetime
from typing import Dict
from sqlalchemy.orm import Session
from app.models import sales_rep, call, user

# Configure logging
logger = logging.getLogger(__name__)

# Expo push API URL
EXPO_PUSH_API_URL = 'https://exp.host/--/api/v2/push/send'

def send_appointment_assignment_notification(
    db: Session,
    call_id: int,
    sales_rep_id: str,
    customer_name: str,
    appointment_date: str = None,
    address: str = None
) -> Dict:
    """
    Send a notification to a sales rep when they are assigned to an appointment
    
    Args:
        db: Database session
        call_id: ID of the call/appointment
        sales_rep_id: ID of the sales rep to notify
        customer_name: Name of the customer
        appointment_date: ISO string of appointment date (optional)
        address: Customer address (optional)
        
    Returns:
        dict: Result of the notification attempt
    """
    try:
        # Get the sales rep record
        rep = db.query(sales_rep.SalesRep).filter_by(user_id=sales_rep_id).first()
        
        if not rep:
            logger.warning(f"Sales rep with ID {sales_rep_id} not found")
            return {
                "success": False,
                "message": "Sales rep not found",
                "sent": False
            }
        
        # If the rep doesn't have a push token registered, we can't send a notification
        if not rep.expo_push_token:
            logger.info(f"Sales rep {sales_rep_id} has no push token registered")
            return {
                "success": True,
                "message": "Sales rep has no push token registered",
                "sent": False
            }
        
        # Get the user's name for better log messages
        user_record = db.query(user.User).filter_by(id=sales_rep_id).first()
        rep_name = user_record.name if user_record else "Unknown"
        
        # Send the notification
        result = send_sales_rep_notification(
            expo_push_token=rep.expo_push_token,
            call_id=call_id,
            customer_name=customer_name,
            appointment_date=appointment_date,
            address=address,
            rep_name=rep_name
        )
        
        if result:
            logger.info(f"Successfully sent appointment notification to sales rep {rep_name} ({sales_rep_id})")
            return {
                "success": True,
                "message": "Notification sent successfully",
                "sent": True
            }
        else:
            logger.warning(f"Failed to send appointment notification to sales rep {rep_name} ({sales_rep_id})")
            return {
                "success": False,
                "message": "Failed to send notification",
                "sent": False
            }
    
    except Exception as e:
        logger.error(f"Error sending sales rep notification: {str(e)}")
        return {
            "success": False,
            "message": f"Error sending notification: {str(e)}",
            "sent": False
        }

def send_sales_rep_notification(
    expo_push_token: str, 
    call_id: int, 
    customer_name: str, 
    appointment_date: str = None,
    address: str = None,
    rep_name: str = "Sales Rep"
) -> bool:
    """
    Send a push notification to a sales rep's device using Expo Push Notifications
    
    Args:
        expo_push_token: Expo Push Token from the device
        call_id: ID of the call/appointment
        customer_name: Name of the customer
        appointment_date: ISO string of appointment date (optional)
        address: Customer address (optional)
        rep_name: Name of the sales rep (for logging purposes)
        
    Returns:
        bool: True if the notification was sent successfully
    """
    try:
        headers = {
            'Content-Type': 'application/json',
        }
        
        # Format the date and time for display if provided
        day_name = ""
        month_name = ""
        day_of_month = ""
        time_str = ""
        
        if appointment_date:
            try:
                date_obj = datetime.fromisoformat(appointment_date.replace('Z', '+00:00'))
                day_name = date_obj.strftime("%A")  # Day name (Monday, Tuesday, etc.)
                month_name = date_obj.strftime("%B")  # Month name (January, February, etc.)
                day_of_month = date_obj.strftime("%-d")  # Day of month (1-31) without leading zero
                time_str = date_obj.strftime("%I:%M %p")  # Hour:Minute AM/PM
            except ValueError:
                logger.warning(f"Failed to parse appointment date: {appointment_date}")
        
        # Create the notification message
        if address and day_name and month_name and day_of_month and time_str:
            body = f"You have a new appointment with {customer_name} at {address} on {day_name}, {month_name} {day_of_month} at {time_str}"
        elif day_name and month_name and day_of_month and time_str:
            body = f"You have a new appointment with {customer_name} on {day_name}, {month_name} {day_of_month} at {time_str}"
        elif address:
            body = f"You have a new appointment with {customer_name} at {address}"
        else:
            body = f"You have a new appointment with {customer_name}"
        
        # Prepare the notification payload for Expo Push API
        payload = [{
            'to': expo_push_token,
            'title': 'New Appointment Assigned',
            'body': body,
            'data': {
                'type': 'appointment_assignment',
                'callId': str(call_id),
                'customerName': customer_name,
                'appointmentDate': appointment_date,
                'address': address,
                'timestamp': datetime.utcnow().isoformat()
            },
            'sound': 'default',
            'priority': 'high'
        }]
        
        logger.info(f"Sending notification to {rep_name}: {body}")
        
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
                    logger.info(f"Successfully sent notification to {rep_name} for call {call_id}")
                    return True
                else:
                    error = response_data[0].get('message', 'Unknown error')
                    logger.error(f"Failed to send notification to {rep_name} for call {call_id}: {error}")
            else:
                logger.error(f"Empty response when sending notification to {rep_name} for call {call_id}")
        else:
            logger.error(f"Failed to send notification to {rep_name} for call {call_id}, status code: {response.status_code}")
        
        return False
        
    except Exception as e:
        logger.error(f"Error sending sales rep notification: {str(e)}")
        return False 