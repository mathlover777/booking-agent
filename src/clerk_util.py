import json
import boto3
import os
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging

# Global variables
STAGE = os.environ['STAGE']
secrets_client = boto3.client('secretsmanager')
response = secrets_client.get_secret_value(SecretId=f"{STAGE}/vibecal")
_secrets = json.loads(response['SecretString'])

# Google Calendar API base URL
GOOGLE_CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_google_oauth_token(user_id: str) -> Optional[str]:
    """Retrieve Google OAuth token for a user from Clerk API"""
    try:
        url = f"https://api.clerk.com/v1/users/{user_id}/oauth_access_tokens/oauth_google"
        headers = {'Authorization': f'Bearer {_secrets["CLERK_SECRET_KEY"]}'}
        params = {'limit': 10, 'offset': 0}
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        return data[0]["token"] if data else None
    except Exception as e:
        logger.error(f"Error getting Google OAuth token for user {user_id}: {e}")
        return None


def fetch_availability(user_id: str, oauth_token: str, start_timestamp: str, end_timestamp: str) -> Dict[str, Any]:
    """
    Fetch user's calendar availability for a given time range.
    
    Args:
        user_id: User identifier
        oauth_token: Google OAuth access token
        start_timestamp: Start time in ISO format (e.g., "2024-01-01T00:00:00Z")
        end_timestamp: End time in ISO format (e.g., "2024-01-01T23:59:59Z")
    
    Returns:
        Dict containing:
        - events: List of existing events in the time range
        - timezone: User's calendar timezone
        - available_slots: List of available time slots (simplified)
    """
    try:
        # Get user's primary calendar
        calendar_url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/primary"
        headers = {'Authorization': f'Bearer {oauth_token}'}
        
        calendar_response = requests.get(calendar_url, headers=headers, timeout=30)
        calendar_response.raise_for_status()
        calendar_data = calendar_response.json()
        timezone_id = calendar_data.get('timeZone', 'UTC')
        
        # Get events in the specified time range
        events_url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/primary/events"
        params = {
            'timeMin': start_timestamp,
            'timeMax': end_timestamp,
            'singleEvents': True,
            'orderBy': 'startTime'
        }
        
        events_response = requests.get(events_url, headers=headers, params=params, timeout=30)
        events_response.raise_for_status()
        events_data = events_response.json()
        
        events = events_data.get('items', [])
        
        # Extract event details
        formatted_events = []
        for event in events:
            start = event.get('start', {}).get('dateTime') or event.get('start', {}).get('date')
            end = event.get('end', {}).get('dateTime') or event.get('end', {}).get('date')
            
            formatted_events.append({
                'id': event.get('id'),
                'title': event.get('summary', 'No title'),
                'start': start,
                'end': end,
                'description': event.get('description', ''),
                'attendees': [attendee.get('email') for attendee in event.get('attendees', [])]
            })
        
        return {
            'events': formatted_events,
            'timezone': timezone_id,
            'total_events': len(formatted_events),
            'time_range': {
                'start': start_timestamp,
                'end': end_timestamp
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching availability for user {user_id}: {e}")
        raise Exception(f"Failed to fetch calendar availability: {str(e)}")


def book_event(
    user_id: str, 
    oauth_token: str, 
    start_timestamp: str, 
    end_timestamp: str, 
    title: str,
    description: str = "",
    attendees: List[str] = None,
    location: str = "",
    reminders: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Book an event in the user's Google Calendar.
    
    Args:
        user_id: User identifier
        oauth_token: Google OAuth access token
        start_timestamp: Start time in ISO format
        end_timestamp: End time in ISO format
        title: Event title
        description: Event description
        attendees: List of attendee email addresses
        location: Event location
        reminders: Reminder settings (optional)
    
    Returns:
        Dict containing the created event details
    """
    try:
        # Default reminder settings (follow Google Calendar best practices)
        default_reminders = {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                {'method': 'popup', 'minutes': 30},       # 30 minutes before
                {'method': 'popup', 'minutes': 10}        # 10 minutes before
            ]
        }
        
        # Use provided reminders or defaults
        event_reminders = reminders if reminders else default_reminders
        
        # Prepare event data
        event_data = {
            'summary': title,
            'description': description,
            'start': {
                'dateTime': start_timestamp,
                'timeZone': 'UTC'  # Will be converted to user's timezone
            },
            'end': {
                'dateTime': end_timestamp,
                'timeZone': 'UTC'
            },
            'reminders': event_reminders
        }
        
        # Add location if provided
        if location:
            event_data['location'] = location
        
        # Add attendees if provided
        if attendees:
            event_data['attendees'] = [{'email': email} for email in attendees]
            # Send updates to attendees
            event_data['guestsCanModify'] = False
            event_data['guestsCanInviteOthers'] = False
        
        # Create the event
        events_url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/primary/events"
        headers = {
            'Authorization': f'Bearer {oauth_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(
            events_url, 
            headers=headers, 
            json=event_data, 
            timeout=30
        )
        response.raise_for_status()
        
        created_event = response.json()
        
        return {
            'event_id': created_event.get('id'),
            'title': created_event.get('summary'),
            'start': created_event.get('start', {}).get('dateTime'),
            'end': created_event.get('end', {}).get('dateTime'),
            'description': created_event.get('description'),
            'location': created_event.get('location'),
            'attendees': [attendee.get('email') for attendee in created_event.get('attendees', [])],
            'html_link': created_event.get('htmlLink'),
            'status': created_event.get('status')
        }
        
    except Exception as e:
        logger.error(f"Error booking event for user {user_id}: {e}")
        raise Exception(f"Failed to book event: {str(e)}")


def cancel_event(user_id: str, oauth_token: str, event_id: str, notify_attendees: bool = True) -> Dict[str, Any]:
    """
    Cancel/delete an event from the user's Google Calendar.
    
    Args:
        user_id: User identifier
        oauth_token: Google OAuth access token
        event_id: Google Calendar event ID
        notify_attendees: Whether to notify attendees about the cancellation
    
    Returns:
        Dict containing cancellation status
    """
    try:
        events_url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/primary/events/{event_id}"
        headers = {'Authorization': f'Bearer {oauth_token}'}
        params = {'sendUpdates': 'all' if notify_attendees else 'none'}
        
        response = requests.delete(events_url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        return {
            'event_id': event_id,
            'status': 'cancelled',
            'notified_attendees': notify_attendees,
            'message': 'Event successfully cancelled'
        }
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise Exception(f"Event with ID {event_id} not found")
        else:
            logger.error(f"Error cancelling event {event_id} for user {user_id}: {e}")
            raise Exception(f"Failed to cancel event: {str(e)}")
    except Exception as e:
        logger.error(f"Error cancelling event {event_id} for user {user_id}: {e}")
        raise Exception(f"Failed to cancel event: {str(e)}")


def get_calendar_timezone(user_id: str, oauth_token: str) -> str:
    """
    Get the user's calendar timezone.
    
    Args:
        user_id: User identifier
        oauth_token: Google OAuth access token
    
    Returns:
        Timezone identifier (e.g., "America/New_York")
    """
    try:
        calendar_url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/primary"
        headers = {'Authorization': f'Bearer {oauth_token}'}
        
        response = requests.get(calendar_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        calendar_data = response.json()
        return calendar_data.get('timeZone', 'UTC')
        
    except Exception as e:
        logger.error(f"Error getting timezone for user {user_id}: {e}")
        return 'UTC'  # Fallback to UTC 