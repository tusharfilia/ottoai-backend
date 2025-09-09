from sqlalchemy.orm import Session
from ..models import call, sales_rep, user
from datetime import datetime, timedelta
import requests
import json
import os
import logging
import asyncio
from sqlalchemy import or_

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Expo Push Notification API configuration
EXPO_PUSH_API_URL = "https://exp.host/--/api/v2/push/send"

# In-memory store for keeping track of sent notifications
# This avoids needing to store the state in the database
# Format: {call_id: timestamp}
SENT_NOTIFICATIONS = {}

def check_missing_reports(db: Session):
    """
    Check for appointments in the past that should have reports by now.
    Send notifications to sales reps to complete the reports.
    Only checks appointments that are at least 4 hours old to allow time for processing.
    """
    try:
        # Look for appointments in the past 48 hours
        cutoff_time = datetime.utcnow() - timedelta(hours=48)
        
        # Add a grace period - only check appointments at least 4 hours old
        grace_period = datetime.utcnow() - timedelta(hours=4)
        
        # Find appointments where recording is missing and no sales outcome is recorded
        missing_reports = db.query(call.Call).filter(
            call.Call.quote_date < grace_period,  # Only check appointments at least 4 hours old
            call.Call.quote_date > cutoff_time,
            call.Call.assigned_rep_id.isnot(None),
            call.Call.booked == True,
            call.Call.bought.is_(None),
            call.Call.still_deciding.is_(None),
            or_(
                call.Call.recording_duration_s.is_(None),
                call.Call.recording_duration_s < 60
            )
        ).all()
        
        logger.info(f"Found {len(missing_reports)} appointments with missing reports")
        
        # Current time
        now = datetime.utcnow()
        
        # Filter out appointments where we've already sent a notification recently
        # (within the last 12 hours)
        filtered_reports = []
        for report in missing_reports:
            call_id = str(report.call_id)
            
            # Check if we've sent a notification for this call recently
            if call_id in SENT_NOTIFICATIONS:
                last_sent = SENT_NOTIFICATIONS[call_id]
                time_diff = now - last_sent
                
                # Skip if notification was sent less than 12 hours ago
                if time_diff.total_seconds() < 12 * 3600:
                    logger.info(f"Skipping call {call_id} - notification sent recently")
                    continue
            
            filtered_reports.append(report)
        
        logger.info(f"After filtering recently notified calls: {len(filtered_reports)} appointments need notifications")
        
        # Count of notifications sent
        notifications_sent = 0
        
        # Group by sales rep to avoid sending too many notifications
        reports_by_rep = {}
        for report in filtered_reports:
            if report.assigned_rep_id not in reports_by_rep:
                reports_by_rep[report.assigned_rep_id] = []
            reports_by_rep[report.assigned_rep_id].append(report)
        
        # Send notifications to each sales rep
        for rep_id, reports in reports_by_rep.items():
            # Get the sales rep's device token for push notifications
            rep_user = db.query(user.User).filter_by(id=rep_id).first()
            if not rep_user:
                logger.warning(f"No user found for rep ID {rep_id}, skipping notifications")
                continue
                
            sales_rep_record = db.query(sales_rep.SalesRep).filter_by(user_id=rep_id).first()
            if not sales_rep_record or not sales_rep_record.expo_push_token:
                logger.warning(f"No Expo push token found for rep ID {rep_id}, skipping notifications")
                continue
            
            # Send a max of 3 notifications per rep
            for report in reports[:3]:
                notification_sent = send_report_notification(
                    expo_push_token=sales_rep_record.expo_push_token,
                    call_id=report.call_id,
                    customer_name=report.name,
                    appointment_date=report.quote_date.isoformat() if report.quote_date else None
                )
                
                if notification_sent:
                    notifications_sent += 1
                    
                    # Record that we sent a notification for this call
                    SENT_NOTIFICATIONS[str(report.call_id)] = now
        
        # Clean up old entries from the notifications dict
        # (anything older than 24 hours)
        cleanup_time = now - timedelta(hours=24)
        for call_id in list(SENT_NOTIFICATIONS.keys()):
            if SENT_NOTIFICATIONS[call_id] < cleanup_time:
                del SENT_NOTIFICATIONS[call_id]
        
        logger.info(f"Sent {notifications_sent} notifications for missing reports")
        return notifications_sent
        
    except Exception as e:
        logger.error(f"Error checking missing reports: {str(e)}")
        return 0

def send_report_notification(expo_push_token: str, call_id: str, customer_name: str, appointment_date: str = None) -> bool:
    """
    Send a push notification to a sales rep's device using Expo Push Notifications
    
    Args:
        expo_push_token: Expo Push Token from the device
        call_id: ID of the call needing a report
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
            'title': 'Sales Report Required',
            'body': f'Please complete your sales report for {customer_name}{display_date}.',
            'data': {
                'type': 'sales_report',
                'callId': call_id,
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
            result = response.json()
            # Check for errors in the response
            if not result.get('errors') and len(result.get('data', [])) > 0:
                status = result['data'][0].get('status')
                if status == 'ok':
                    logger.info(f"Successfully sent Expo notification for call {call_id}")
                    return True
                else:
                    logger.error(f"Expo Push API error: {status}")
                    return False
            else:
                logger.error(f"Expo Push API returned errors: {result.get('errors')}")
                return False
        else:
            logger.error(f"Error sending notification, status code: {response.status_code}, response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Exception sending notification: {str(e)}")
        return False 