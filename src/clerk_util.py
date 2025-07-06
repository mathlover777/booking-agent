import json
import boto3
import os
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import logging
import pytz
from urllib.parse import quote

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



def get_user_by_email(email: str) -> str:
    """
    Fetch a user object from Clerk API by email address.
    
    Args:
        email: Email address to search for
    
    Returns:
        User ID if found
    
    Raises:
        Exception: If no user is found with the given email
    """
    try:
        # URL encode the email address
        encoded_email = quote(email)
        url = f"https://api.clerk.com/v1/users?limit=10&offset=0&order_by=-created_at&email_address={encoded_email}"
        headers = {'Authorization': f'Bearer {_secrets["CLERK_SECRET_KEY"]}'}
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if not data:
            raise Exception(f"No user found with email: {email}")
        
        # Return the first user's ID (assuming at most one return as specified)
        return data[0]["id"]
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error getting user by email {email}: {e}")
        raise Exception(f"Failed to fetch user by email: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting user by email {email}: {e}")
        raise Exception(f"Failed to fetch user by email: {str(e)}")


def get_google_oauth_token_low_level(user_id: str) -> Optional[str]:
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


def get_user_timezone_low_level(user_id: str, oauth_token: str) -> str:
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
    try:
        # Get OAuth token internally
        oauth_token = get_google_oauth_token_low_level(user_id)
        if not oauth_token:
            raise Exception("Could not retrieve Google OAuth token for user")
        
        # Get user's timezone
        user_timezone = get_user_timezone_low_level(user_id, oauth_token)
        
        # Convert dates to timestamps in user's timezone
        # Start of day in user's timezone
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        start_timestamp = start_datetime.replace(tzinfo=timezone.utc).isoformat()
        
        # End of day in user's timezone (next day at 00:00)
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        end_timestamp = end_datetime.replace(tzinfo=timezone.utc).isoformat()
        
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
            'date_range': {
                'start_date': start_date,
                'end_date': end_date
            }
        }
        
    except Exception as e:
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
    try:
        # Get OAuth token internally
        oauth_token = get_google_oauth_token_low_level(user_id)
        if not oauth_token:
            raise Exception("Could not retrieve Google OAuth token for user")
        
        # Get user's timezone
        user_timezone = get_user_timezone_low_level(user_id, oauth_token)
        
        # Convert date and time to datetime in user's timezone
        start_datetime_str = f"{start_date}T{start_time}:00"
        end_datetime_str = f"{end_date}T{end_time}:00"
        
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
            'status': created_event.get('status'),
            'timezone': user_timezone
        }
        
    except Exception as e:
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
    try:
        # Get OAuth token internally
        oauth_token = get_google_oauth_token_low_level(user_id)
        if not oauth_token:
            raise Exception("Could not retrieve Google OAuth token for user")
        
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


# High-level wrapper functions that take email addresses
def get_availability(owner_email: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Fetch calendar availability for a given date range using email address.
    
    Args:
        owner_email: Email address of the calendar owner
        start_date: Start date in YYYY-MM-DD format (e.g., "2024-01-01")
        end_date: End date in YYYY-MM-DD format (e.g., "2024-01-31")
    
    Returns:
        Dict containing calendar availability information
    """
    try:
        user_id = get_user_by_email(owner_email)
        return get_availability_low_level(user_id, start_date, end_date)
    except Exception as e:
        logger.error(f"Error in get_availability for {owner_email}: {e}")
        raise Exception(f"Failed to get availability for {owner_email}: {str(e)}")


def book_event(
    owner_email: str,
    date: str,
    start_time: str,
    end_time: str,
    title: str,
    description: str = "",
    attendees: List[str] = None,
    location: str = "",
    reminders: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Book an event in the calendar using email address.
    
    Args:
        owner_email: Email address of the calendar owner
        date: Date in YYYY-MM-DD format (e.g., "2024-01-01")
        start_time: Start time in military format (e.g., "14:30" for 2:30 PM)
        end_time: End time in military format (e.g., "15:30" for 3:30 PM)
        title: Event title
        description: Event description
        attendees: List of attendee email addresses
        location: Event location
        reminders: Reminder settings (optional)
    
    Returns:
        Dict containing the created event details
    """
    try:
        user_id = get_user_by_email(owner_email)
        return book_event_low_level(
            user_id=user_id,
            start_date=date,
            start_time=start_time,
            end_date=date,
            end_time=end_time,
            title=title,
            description=description,
            attendees=attendees,
            location=location,
            reminders=reminders
        )
    except Exception as e:
        logger.error(f"Error in book_event for {owner_email}: {e}")
        raise Exception(f"Failed to book event for {owner_email}: {str(e)}")


def cancel_event(owner_email: str, event_id: str, notify_attendees: bool = True) -> Dict[str, Any]:
    """
    Cancel/delete an event from the calendar using email address.
    
    Args:
        owner_email: Email address of the calendar owner
        event_id: Google Calendar event ID
        notify_attendees: Whether to notify attendees about the cancellation
    
    Returns:
        Dict containing cancellation status
    """
    try:
        user_id = get_user_by_email(owner_email)
        return cancel_event_low_level(user_id, event_id, notify_attendees)
    except Exception as e:
        logger.error(f"Error in cancel_event for {owner_email}: {e}")
        raise Exception(f"Failed to cancel event for {owner_email}: {str(e)}") 


# Calendar Tool Schemas for OpenAI Responses API
CALENDAR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_availability",
            "description": "Fetch calendar availability for a given date range using email address",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner_email": {
                        "type": "string",
                        "description": "Email address of the calendar owner"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format (e.g., '2024-01-01')"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format (e.g., '2024-01-31')"
                    }
                },
                "required": ["owner_email", "start_date", "end_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_event",
            "description": "Book an event in the calendar using email address",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner_email": {
                        "type": "string",
                        "description": "Email address of the calendar owner"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (e.g., '2024-01-01')"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time in military format (e.g., '14:30' for 2:30 PM)"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in military format (e.g., '15:30' for 3:30 PM)"
                    },
                    "title": {
                        "type": "string",
                        "description": "Event title"
                    },
                    "description": {
                        "type": "string",
                        "description": "Event description",
                        "default": ""
                    },
                    "attendees": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "List of attendee email addresses"
                    },
                    "location": {
                        "type": "string",
                        "description": "Event location",
                        "default": ""
                    },
                    "reminders": {
                        "type": "object",
                        "description": "Reminder settings (optional)",
                        "properties": {
                            "useDefault": {
                                "type": "boolean",
                                "description": "Whether to use default reminders"
                            },
                            "overrides": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "method": {
                                            "type": "string",
                                            "enum": ["email", "popup"]
                                        },
                                        "minutes": {
                                            "type": "integer",
                                            "description": "Minutes before event"
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "required": ["owner_email", "date", "start_time", "end_time", "title"]
            }
        }
    }
]
