from typing import List, Optional, Dict, Any
from .calendar_util import get_availability_low_level, book_event_low_level, cancel_event_low_level, get_event_low_level


class CalendarAssistant:
    def __init__(self, user_id: str):
        self.user_id = user_id

    # Calendar interaction methods --------------------------
    def get_availability(self, start_date: str, end_date: str):
        return get_availability_low_level(self.user_id, start_date, end_date)

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
        return book_event_low_level(
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

    def cancel_event(self, event_id: str, notify_attendees: bool = True):
        return cancel_event_low_level(self.user_id, event_id, notify_attendees)

    def get_event(self, event_id: str):
        return get_event_low_level(self.user_id, event_id)


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
                "name": "book_event",
                "description": "Book an event in the owner's calendar.",
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
    elif tool_name == "book_event":
        return calendar_assistant.book_event(**tool_args)
    elif tool_name == "cancel_event":
        return calendar_assistant.cancel_event(**tool_args)
    else:
        return {"error": f"Unknown tool: {tool_name}"} 