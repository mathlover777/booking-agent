import json
import os
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import pytz
from urllib.parse import quote

from common_utils import aws_utils
from common_utils.log_util import get_logger

# Global variables
_secrets = aws_utils._secrets

# Google Calendar API base URL
GOOGLE_CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"

# Get logger for this module
logger = get_logger(__name__)

def get_google_oauth_token_low_level(user_id: str) -> Optional[str]:
    """Retrieve Google OAuth token for a user from Clerk API"""
    print(f"🔑 [DEBUG] get_google_oauth_token_low_level called with user_id: {user_id}")
    try:
        url = f"https://api.clerk.com/v1/users/{user_id}/oauth_access_tokens/oauth_google"
        headers = {'Authorization': f'Bearer {_secrets["CLERK_SECRET_KEY"]}'}
        params = {'limit': 10, 'offset': 0}
        
        print(f"🔑 [DEBUG] Making Clerk OAuth API request to: {url}")
        response = requests.get(url, headers=headers, params=params, timeout=30)
        print(f"🔑 [DEBUG] Clerk OAuth API response status: {response.status_code}")
        
        response.raise_for_status()
        
        data = response.json()
        print(f"🔑 [DEBUG] Clerk OAuth API response data: {data}")
        
        token = data[0]["token"] if data else None
        print(f"🔑 [DEBUG] Retrieved OAuth token: {'Yes' if token else 'No'}")
        return token
    except Exception as e:
        print(f"❌ [DEBUG] Error getting Google OAuth token for user {user_id}: {e}")
        logger.error(f"Error getting Google OAuth token for user {user_id}: {e}")
        return None


def get_user_timezone_low_level(user_id: str, oauth_token: str) -> str:
    """
    Get the user's calendar timezone.
    
    Args:
        user_id: User identifier
        oauth_token: Google OAuth access token
    
    Returns:
        Timezone identifier (e.g., "America/New_York")
    """
    print(f"🌍 [DEBUG] get_user_timezone_low_level called with user_id: {user_id}")
    try:
        calendar_url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/primary"
        headers = {'Authorization': f'Bearer {oauth_token}'}
        
        print(f"🌍 [DEBUG] Making Google Calendar API request to: {calendar_url}")
        response = requests.get(calendar_url, headers=headers, timeout=30)
        print(f"🌍 [DEBUG] Google Calendar API response status: {response.status_code}")
        
        response.raise_for_status()
        
        calendar_data = response.json()
        timezone_id = calendar_data.get('timeZone', 'UTC')
        print(f"🌍 [DEBUG] Retrieved timezone: {timezone_id}")
        return timezone_id
        
    except Exception as e:
        print(f"❌ [DEBUG] Error getting timezone for user {user_id}: {e}")
        logger.error(f"Error getting timezone for user {user_id}: {e}")
        return 'UTC'  # Fallback to UTC


def get_availability_low_level(user_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Fetch user's calendar availability for a given date range.
    
    Args:
        user_id: User identifier
        start_date: Start date in YYYY-MM-DD format (e.g., "2024-01-01")
        end_date: End date in YYYY-MM-DD format (e.g., "2024-01-31")
    
    Returns:
        Dict containing:
        - events: List of existing events in the time range
        - timezone: User's calendar timezone
        - available_slots: List of available time slots (simplified)
    """
    print(f"📅 [DEBUG] get_availability_low_level called with user_id: {user_id}, start_date: {start_date}, end_date: {end_date}")
    try:
        # Get OAuth token internally
        print(f"📅 [DEBUG] Getting OAuth token for user: {user_id}")
        oauth_token = get_google_oauth_token_low_level(user_id)
        if not oauth_token:
            print(f"❌ [DEBUG] Could not retrieve Google OAuth token for user: {user_id}")
            raise Exception("Could not retrieve Google OAuth token for user")
        
        # Get user's timezone
        print(f"📅 [DEBUG] Getting timezone for user: {user_id}")
        user_timezone = get_user_timezone_low_level(user_id, oauth_token)
        
        # Convert dates to timestamps in user's timezone
        # Start of day in user's timezone
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        start_timestamp = start_datetime.replace(tzinfo=timezone.utc).isoformat()
        
        # End of day in user's timezone (next day at 00:00)
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        end_timestamp = end_datetime.replace(tzinfo=timezone.utc).isoformat()
        
        print(f"📅 [DEBUG] Converted timestamps - start: {start_timestamp}, end: {end_timestamp}")
        
        # Get user's primary calendar
        calendar_url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/primary"
        headers = {'Authorization': f'Bearer {oauth_token}'}
        
        print(f"📅 [DEBUG] Making calendar info request to: {calendar_url}")
        calendar_response = requests.get(calendar_url, headers=headers, timeout=30)
        print(f"📅 [DEBUG] Calendar info response status: {calendar_response.status_code}")
        
        calendar_response.raise_for_status()
        calendar_data = calendar_response.json()
        timezone_id = calendar_data.get('timeZone', 'UTC')
        print(f"📅 [DEBUG] Calendar timezone: {timezone_id}")
        
        # Get events in the specified time range
        events_url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/primary/events"
        params = {
            'timeMin': start_timestamp,
            'timeMax': end_timestamp,
            'singleEvents': True,
            'orderBy': 'startTime'
        }
        
        print(f"📅 [DEBUG] Making events request to: {events_url} with params: {params}")
        events_response = requests.get(events_url, headers=headers, params=params, timeout=30)
        print(f"📅 [DEBUG] Events response status: {events_response.status_code}")
        
        events_response.raise_for_status()
        events_data = events_response.json()
        
        events = events_data.get('items', [])
        print(f"📅 [DEBUG] Found {len(events)} events in date range")
        
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
        
        result = {
            'events': formatted_events,
            'timezone': timezone_id,
            'total_events': len(formatted_events),
            'date_range': {
                'start_date': start_date,
                'end_date': end_date
            }
        }
        
        print(f"📅 [DEBUG] Returning availability result: {result}")
        return result
        
    except Exception as e:
        print(f"❌ [DEBUG] Error fetching availability for user {user_id}: {e}")
        logger.error(f"Error fetching availability for user {user_id}: {e}")
        raise Exception(f"Failed to fetch calendar availability: {str(e)}")


def book_event_low_level(
    user_id: str, 
    start_date: str,
    start_time: str,
    end_date: str,
    end_time: str,
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
        start_date: Start date in YYYY-MM-DD format (e.g., "2024-01-01")
        start_time: Start time in military format (e.g., "14:30" for 2:30 PM)
        end_date: End date in YYYY-MM-DD format (e.g., "2024-01-01")
        end_time: End time in military format (e.g., "15:30" for 3:30 PM)
        title: Event title
        description: Event description
        attendees: List of attendee email addresses
        location: Event location
        reminders: Reminder settings (optional)
    
    Returns:
        Dict containing the created event details
    """
    print(f"📝 [DEBUG] book_event_low_level called with user_id: {user_id}")
    print(f"📝 [DEBUG] Event details - start_date: {start_date}, start_time: {start_time}, end_date: {end_date}, end_time: {end_time}")
    print(f"📝 [DEBUG] Event details - title: {title}, attendees: {attendees}")
    
    try:
        # Get OAuth token internally
        print(f"📝 [DEBUG] Getting OAuth token for user: {user_id}")
        oauth_token = get_google_oauth_token_low_level(user_id)
        if not oauth_token:
            print(f"❌ [DEBUG] Could not retrieve Google OAuth token for user: {user_id}")
            raise Exception("Could not retrieve Google OAuth token for user")
        
        # Get user's timezone
        print(f"📝 [DEBUG] Getting timezone for user: {user_id}")
        user_timezone = get_user_timezone_low_level(user_id, oauth_token)
        
        # Convert date and time to datetime in user's timezone
        start_datetime_str = f"{start_date}T{start_time}:00"
        end_datetime_str = f"{end_date}T{end_time}:00"
        
        print(f"📝 [DEBUG] DateTime strings - start: {start_datetime_str}, end: {end_datetime_str}")
        
        # Parse datetime as if it's in user's timezone
        start_datetime = datetime.strptime(start_datetime_str, "%Y-%m-%dT%H:%M:%S")
        end_datetime = datetime.strptime(end_datetime_str, "%Y-%m-%dT%H:%M:%S")
        
        # Create timezone-aware datetime in user's timezone
        user_tz = pytz.timezone(user_timezone)
        start_datetime_tz = user_tz.localize(start_datetime)
        end_datetime_tz = user_tz.localize(end_datetime)
        
        # Convert to UTC timestamps for Google Calendar API
        start_timestamp = start_datetime_tz.astimezone(pytz.UTC).isoformat()
        end_timestamp = end_datetime_tz.astimezone(pytz.UTC).isoformat()
        
        print(f"📝 [DEBUG] UTC timestamps - start: {start_timestamp}, end: {end_timestamp}")
        
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
        print(f"📝 [DEBUG] Using reminders: {event_reminders}")
        
        # Prepare event data
        event_data = {
            'summary': title,
            'description': description,
            'start': {
                'dateTime': start_timestamp,
                'timeZone': user_timezone
            },
            'end': {
                'dateTime': end_timestamp,
                'timeZone': user_timezone
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
        
        print(f"📝 [DEBUG] Event data to send: {event_data}")
        
        # Create the event
        events_url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/primary/events"
        headers = {
            'Authorization': f'Bearer {oauth_token}',
            'Content-Type': 'application/json'
        }
        
        print(f"📝 [DEBUG] Making POST request to: {events_url}")
        response = requests.post(
            events_url, 
            headers=headers, 
            json=event_data, 
            timeout=30
        )
        print(f"📝 [DEBUG] POST response status: {response.status_code}")
        
        response.raise_for_status()
        
        created_event = response.json()
        print(f"📝 [DEBUG] Created event response: {created_event}")
        
        result = {
            'event_id': created_event.get('id'),
            'title': created_event.get('summary'),
            'start': created_event.get('start', {}).get('dateTime'),
            'end': created_event.get('end', {}).get('dateTime'),
            'description': created_event.get('description'),
            'location': created_event.get('location'),
            'attendees': [attendee.get('email') for attendee in created_event.get('attendees', [])],
            'html_link': created_event.get('htmlLink'),
            'status': created_event.get('status'),
            'timezone': user_timezone
        }
        
        print(f"📝 [DEBUG] Returning booking result: {result}")
        return result
        
    except Exception as e:
        print(f"❌ [DEBUG] Error booking event for user {user_id}: {e}")
        logger.error(f"Error booking event for user {user_id}: {e}")
        raise Exception(f"Failed to book event: {str(e)}")


def cancel_event_low_level(user_id: str, event_id: str, notify_attendees: bool = True) -> Dict[str, Any]:
    """
    Cancel/delete an event from the user's Google Calendar.
    
    Args:
        user_id: User identifier
        event_id: Google Calendar event ID
        notify_attendees: Whether to notify attendees about the cancellation
    
    Returns:
        Dict containing cancellation status
    """
    print(f"❌ [DEBUG] cancel_event_low_level called with user_id: {user_id}, event_id: {event_id}, notify_attendees: {notify_attendees}")
    try:
        # Get OAuth token internally
        print(f"❌ [DEBUG] Getting OAuth token for user: {user_id}")
        oauth_token = get_google_oauth_token_low_level(user_id)
        if not oauth_token:
            print(f"❌ [DEBUG] Could not retrieve Google OAuth token for user: {user_id}")
            raise Exception("Could not retrieve Google OAuth token for user")
        
        events_url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/primary/events/{event_id}"
        headers = {'Authorization': f'Bearer {oauth_token}'}
        params = {'sendUpdates': 'all' if notify_attendees else 'none'}
        
        print(f"❌ [DEBUG] Making DELETE request to: {events_url}")
        print(f"❌ [DEBUG] DELETE request params: {params}")
        print(f"❌ [DEBUG] DELETE request headers: {headers}")
        
        response = requests.delete(events_url, headers=headers, params=params, timeout=30)
        print(f"❌ [DEBUG] DELETE response status: {response.status_code}")
        print(f"❌ [DEBUG] DELETE response headers: {dict(response.headers)}")
        
        if response.status_code != 204:
            print(f"❌ [DEBUG] DELETE response content: {response.text}")
        
        response.raise_for_status()
        
        result = {
            'event_id': event_id,
            'status': 'cancelled',
            'notified_attendees': notify_attendees,
            'message': 'Event successfully cancelled'
        }
        
        print(f"❌ [DEBUG] Returning cancellation result: {result}")
        return result
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ [DEBUG] HTTP error cancelling event {event_id} for user {user_id}: {e}")
        print(f"❌ [DEBUG] HTTP error response status: {e.response.status_code}")
        print(f"❌ [DEBUG] HTTP error response content: {e.response.text}")
        
        if e.response.status_code == 404:
            print(f"❌ [DEBUG] Event with ID {event_id} not found")
            raise Exception(f"Event with ID {event_id} not found")
        else:
            logger.error(f"Error cancelling event {event_id} for user {user_id}: {e}")
            raise Exception(f"Failed to cancel event: {str(e)}")
    except Exception as e:
        print(f"❌ [DEBUG] General error cancelling event {event_id} for user {user_id}: {e}")
        logger.error(f"Error cancelling event {event_id} for user {user_id}: {e}")
        raise Exception(f"Failed to cancel event: {str(e)}") 


def get_event_low_level(user_id: str, event_id: str) -> Dict[str, Any]:
    """
    Get a specific event from the user's Google Calendar by ID.
    
    Args:
        user_id: User identifier
        event_id: Google Calendar event ID
    
    Returns:
        Dict containing event details or raises Exception if not found
    """
    print(f"🔍 [DEBUG] get_event_low_level called with user_id: {user_id}, event_id: {event_id}")
    try:
        # Get OAuth token internally
        print(f"🔍 [DEBUG] Getting OAuth token for user: {user_id}")
        oauth_token = get_google_oauth_token_low_level(user_id)
        if not oauth_token:
            print(f"🔍 [DEBUG] Could not retrieve Google OAuth token for user: {user_id}")
            raise Exception("Could not retrieve Google OAuth token for user")
        
        events_url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/primary/events/{event_id}"
        headers = {'Authorization': f'Bearer {oauth_token}'}
        
        print(f"🔍 [DEBUG] Making GET request to: {events_url}")
        response = requests.get(events_url, headers=headers, timeout=30)
        print(f"🔍 [DEBUG] GET response status: {response.status_code}")
        
        if response.status_code == 404:
            print(f"🔍 [DEBUG] Event with ID {event_id} not found")
            raise Exception(f"Event with ID {event_id} not found")
        
        response.raise_for_status()
        
        event_data = response.json()
        print(f"🔍 [DEBUG] Retrieved event data: {event_data}")
        
        result = {
            'event_id': event_data.get('id'),
            'title': event_data.get('summary'),
            'start': event_data.get('start', {}).get('dateTime'),
            'end': event_data.get('end', {}).get('dateTime'),
            'description': event_data.get('description'),
            'location': event_data.get('location'),
            'attendees': [attendee.get('email') for attendee in event_data.get('attendees', [])],
            'html_link': event_data.get('htmlLink'),
            'status': event_data.get('status'),
            'timezone': event_data.get('start', {}).get('timeZone') if event_data.get('start') else None
        }
        
        print(f"🔍 [DEBUG] Returning event result: {result}")
        return result
        
    except requests.exceptions.HTTPError as e:
        print(f"🔍 [DEBUG] HTTP error getting event {event_id} for user {user_id}: {e}")
        if e.response.status_code == 404:
            print(f"🔍 [DEBUG] Event with ID {event_id} not found")
            raise Exception(f"Event with ID {event_id} not found")
        else:
            logger.error(f"Error getting event {event_id} for user {user_id}: {e}")
            raise Exception(f"Failed to get event: {str(e)}")
    except Exception as e:
        print(f"🔍 [DEBUG] General error getting event {event_id} for user {user_id}: {e}")
        logger.error(f"Error getting event {event_id} for user {user_id}: {e}")
        raise Exception(f"Failed to get event: {str(e)}") 