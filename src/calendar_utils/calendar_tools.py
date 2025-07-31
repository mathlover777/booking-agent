from typing import List, Optional, Dict, Any
from .calendar_util import get_availability_low_level, book_event_low_level, cancel_event_low_level, get_event_low_level
from common_utils.log_util import get_logger

# Get logger for this module
logger = get_logger(__name__)


class CalendarAssistant:
    def __init__(self, user_id: str):
        self.user_id = user_id
        # Memory for tracking successful operations
        self._last_booking: Optional[Dict[str, Any]] = None
        self._last_cancellation: Optional[Dict[str, Any]] = None

    # Calendar interaction methods --------------------------
    def get_availability(self, start_date: str, end_date: str):
        return get_availability_low_level(self.user_id, start_date, end_date)

    def check_slot_availability(self, date: str, start_time: str, end_time: str) -> Dict[str, Any]:
        """
        Check if a specific time slot is available for booking.
        
        Args:
            date: Date in YYYY-MM-DD format
            start_time: Start time in HH:MM format (24h)
            end_time: End time in HH:MM format (24h)
            
        Returns:
            Dict containing availability status and details
        """
        try:
            # Get availability for the specific date
            availability = get_availability_low_level(self.user_id, date, date)
            
            # Parse the requested time slot
            start_datetime_str = f"{date}T{start_time}:00"
            end_datetime_str = f"{date}T{end_time}:00"
            
            # Check if there are any conflicting events
            events = availability.get('events', [])
            conflicting_events = []
            
            for event in events:
                # Handle both string and dict formats for start/end times
                event_start = event.get('start')
                event_end = event.get('end')
                
                # If start/end are strings, use them directly
                if isinstance(event_start, str):
                    event_start_str = event_start
                elif isinstance(event_start, dict):
                    event_start_str = event_start.get('dateTime')
                else:
                    event_start_str = None
                
                if isinstance(event_end, str):
                    event_end_str = event_end
                elif isinstance(event_end, dict):
                    event_end_str = event_end.get('dateTime')
                else:
                    event_end_str = None
                
                if event_start_str and event_end_str:
                    # Check for overlap
                    if (start_datetime_str < event_end_str and end_datetime_str > event_start_str):
                        conflicting_events.append({
                            'title': event.get('title', event.get('summary', 'Unknown Event')),
                            'start': event_start_str,
                            'end': event_end_str
                        })
            
            is_available = len(conflicting_events) == 0
            
            return {
                'is_available': is_available,
                'conflicting_events': conflicting_events,
                'requested_slot': {
                    'date': date,
                    'start_time': start_time,
                    'end_time': end_time
                },
                'timezone': availability.get('timezone', 'UTC')
            }
            
        except Exception as e:
            logger.error(f"Error checking slot availability: {e}")
            return {
                'is_available': False,
                'error': str(e),
                'requested_slot': {
                    'date': date,
                    'start_time': start_time,
                    'end_time': end_time
                }
            }

    def book_event(
        self,
        date: str,
        start_time: str,
        end_time: str,
        title: str,
        description: str = "",
        attendees: Optional[List[str]] = None,
        location: str = "",
        reminders: Optional[Dict[str, Any]] = None,
    ):
        # First check if the slot is available
        availability_check = self.check_slot_availability(date, start_time, end_time)
        
        if not availability_check.get('is_available', False):
            # Slot is not available, return error with details
            conflicting_events = availability_check.get('conflicting_events', [])
            error_msg = f"Slot is not available. Conflicting events: {conflicting_events}"
            return {
                'error': 'slot_not_available',
                'message': error_msg,
                'conflicting_events': conflicting_events,
                'requested_slot': availability_check.get('requested_slot')
            }
        
        # Slot is available, proceed with booking
        result = book_event_low_level(
            user_id=self.user_id,
            start_date=date,
            start_time=start_time,
            end_date=date,
            end_time=end_time,
            title=title,
            description=description,
            attendees=attendees,
            location=location,
            reminders=reminders,
        )
        
        # Store successful booking in memory
        if result and result.get('event_id'):
            self._last_booking = result
        
        return result

    def cancel_event(self, event_id: str, notify_attendees: bool = True):
        result = cancel_event_low_level(self.user_id, event_id, notify_attendees)
        
        # Store successful cancellation in memory
        if result and result.get('status') == 'cancelled':
            self._last_cancellation = result
        
        return result

    def get_event(self, event_id: str):
        return get_event_low_level(self.user_id, event_id)

    # Memory retrieval methods ------------------------------
    def get_last_booking_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the last successful booking."""
        return self._last_booking

    def get_last_cancellation_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the last successful cancellation."""
        return self._last_cancellation

    def get_booking_confirmation_text(self) -> Optional[str]:
        """Get formatted confirmation text for the last booking."""
        if not self._last_booking:
            return None
        
        event_id = self._last_booking.get('event_id')
        html_link = self._last_booking.get('html_link')
        title = self._last_booking.get('title')
        
        confirmation_parts = []
        if event_id:
            confirmation_parts.append(f"Event ID: {event_id}")
        if html_link:
            confirmation_parts.append(f"Calendar Link: {html_link}")
        
        if confirmation_parts:
            return "\n".join(confirmation_parts)
        return None

    def get_cancellation_confirmation_text(self) -> Optional[str]:
        """Get formatted confirmation text for the last cancellation."""
        if not self._last_cancellation:
            return None
        
        event_id = self._last_cancellation.get('event_id')
        return f"Event {event_id} has been successfully cancelled."

    def clear_memory(self):
        """Clear all stored memory."""
        self._last_booking = None
        self._last_cancellation = None


def build_calendar_tools() -> List[Dict[str, Any]]:
    """Build calendar tool definitions for AI agent."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_availability",
                "description": "Fetch calendar availability for a date range.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                        "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                    },
                    "required": ["start_date", "end_date"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_slot_availability",
                "description": "Check if a specific time slot is available for booking before attempting to book.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "YYYY-MM-DD"},
                        "start_time": {"type": "string", "description": "HH:MM (24h)"},
                        "end_time": {"type": "string", "description": "HH:MM (24h)"},
                    },
                    "required": ["date", "start_time", "end_time"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "book_event",
                "description": "Book an event in the owner's calendar. This will automatically check availability first.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "YYYY-MM-DD"},
                        "start_time": {"type": "string", "description": "HH:MM (24h)"},
                        "end_time": {"type": "string", "description": "HH:MM (24h)"},
                        "title": {"type": "string"},
                        "description": {"type": "string", "default": ""},
                        "attendees": {"type": "array", "items": {"type": "string"}},
                        "location": {"type": "string", "default": ""},
                        "reminders": {"type": "object"},
                    },
                    "required": ["date", "start_time", "end_time", "title"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "cancel_event",
                "description": "Cancel a calendar event by ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "string"},
                        "notify_attendees": {"type": "boolean", "default": True},
                    },
                    "required": ["event_id"],
                },
            },
        },
    ]


def calendar_tool_executor(calendar_assistant: CalendarAssistant, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute calendar tools for the AI agent.
    
    Args:
        calendar_assistant: CalendarAssistant instance
        tool_name: Name of the tool to execute
        tool_args: Arguments for the tool
    
    Returns:
        Tool execution result
    """
    if tool_name == "get_availability":
        return calendar_assistant.get_availability(**tool_args)
    elif tool_name == "check_slot_availability":
        return calendar_assistant.check_slot_availability(**tool_args)
    elif tool_name == "book_event":
        return calendar_assistant.book_event(**tool_args)
    elif tool_name == "cancel_event":
        return calendar_assistant.cancel_event(**tool_args)
    else:
        return {"error": f"Unknown tool: {tool_name}"} 