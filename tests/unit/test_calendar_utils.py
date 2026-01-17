import pytest
import json
import sys
import os
from unittest.mock import patch, Mock
from datetime import datetime, timezone

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from calendar_utils.calendar_tools import CalendarAssistant, calendar_tool_executor, build_calendar_tools
from calendar_utils.calendar_util import (
    get_google_oauth_token_low_level,
    get_user_timezone_low_level,
    get_availability_low_level,
    book_event_low_level,
    cancel_event_low_level,
    get_event_low_level
)


class TestCalendarUtils:
    """Test suite for calendar utilities"""
    
    @pytest.fixture
    def mock_secrets(self):
        """Mock AWS secrets"""
        with patch('calendar_utils.calendar_util._secrets', {
            'CLERK_SECRET_KEY': 'test_clerk_secret'
        }):
            yield
    
    @pytest.fixture
    def mock_requests_get(self):
        """Mock requests.get for HTTP calls"""
        with patch('requests.get') as mock_get:
            yield mock_get
    
    @pytest.fixture
    def mock_requests_post(self):
        """Mock requests.post for HTTP calls"""
        with patch('requests.post') as mock_post:
            yield mock_post
    
    @pytest.fixture
    def mock_requests_delete(self):
        """Mock requests.delete for HTTP calls"""
        with patch('requests.delete') as mock_delete:
            yield mock_delete
    
    @pytest.fixture
    def sample_oauth_token(self):
        """Sample OAuth token for testing"""
        return "test_oauth_token_12345"
    
    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID for testing"""
        return "user_test_123"
    
    @pytest.fixture
    def sample_event_id(self):
        """Sample event ID for testing"""
        return "event_test_123"
    
    @pytest.fixture
    def sample_calendar_events(self):
        """Sample calendar events response"""
        return {
            "items": [
                {
                    "id": "event1",
                    "summary": "Meeting 1",
                    "start": {"dateTime": "2024-01-15T10:00:00Z"},
                    "end": {"dateTime": "2024-01-15T11:00:00Z"}
                },
                {
                    "id": "event2", 
                    "summary": "Meeting 2",
                    "start": {"dateTime": "2024-01-15T14:00:00Z"},
                    "end": {"dateTime": "2024-01-15T15:00:00Z"}
                }
            ]
        }
    
    @pytest.fixture
    def sample_calendar_info(self):
        """Sample calendar info response"""
        return {
            "timeZone": "America/New_York"
        }

    def test_get_google_oauth_token_low_level_success(self, mock_secrets, mock_requests_get):
        """Test successful OAuth token retrieval from Clerk"""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"token": "test_token_123"}]
        mock_requests_get.return_value = mock_response
        
        # Test
        result = get_google_oauth_token_low_level("user123")
        
        # Assertions
        assert result == "test_token_123"
        mock_requests_get.assert_called_once()
        call_args = mock_requests_get.call_args
        assert "api.clerk.com" in call_args[0][0]
        assert call_args[1]["headers"]["Authorization"] == "Bearer test_clerk_secret"

    def test_get_google_oauth_token_low_level_no_token(self, mock_secrets, mock_requests_get):
        """Test OAuth token retrieval when no token is available"""
        # Mock response with empty data
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_requests_get.return_value = mock_response
        
        # Test
        result = get_google_oauth_token_low_level("user123")
        
        # Assertions
        assert result is None

    def test_get_google_oauth_token_low_level_error(self, mock_secrets, mock_requests_get):
        """Test OAuth token retrieval with API error"""
        # Mock response with error
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("Not found")
        mock_requests_get.return_value = mock_response
        
        # Test
        result = get_google_oauth_token_low_level("user123")
        
        # Assertions
        assert result is None

    def test_get_user_timezone_low_level_success(self, mock_requests_get):
        """Test successful timezone retrieval from Google Calendar"""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"timeZone": "America/New_York"}
        mock_requests_get.return_value = mock_response
        
        # Test
        result = get_user_timezone_low_level("user123", "test_token")
        
        # Assertions
        assert result == "America/New_York"
        mock_requests_get.assert_called_once()
        call_args = mock_requests_get.call_args
        assert "googleapis.com" in call_args[0][0]
        assert call_args[1]["headers"]["Authorization"] == "Bearer test_token"

    def test_get_user_timezone_low_level_fallback(self, mock_requests_get):
        """Test timezone retrieval with error falls back to UTC"""
        # Mock response with error
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("Server error")
        mock_requests_get.return_value = mock_response
        
        # Test
        result = get_user_timezone_low_level("user123", "test_token")
        
        # Assertions
        assert result == "UTC"

    def test_get_availability_low_level_success(self, mock_secrets, mock_requests_get, sample_calendar_events, sample_calendar_info):
        """Test successful availability retrieval"""
        # Mock OAuth token response
        mock_oauth_response = Mock()
        mock_oauth_response.status_code = 200
        mock_oauth_response.json.return_value = [{"token": "test_token"}]
        
        # Mock calendar info response
        mock_calendar_response = Mock()
        mock_calendar_response.status_code = 200
        mock_calendar_response.json.return_value = sample_calendar_info
        
        # Mock events response
        mock_events_response = Mock()
        mock_events_response.status_code = 200
        mock_events_response.json.return_value = sample_calendar_events
        
        # Configure mock to return different responses for different URLs
        def mock_get_side_effect(url, *args, **kwargs):
            if "api.clerk.com" in url:
                return mock_oauth_response
            elif "calendars/primary" in url and "events" not in url:
                return mock_calendar_response
            elif "events" in url:
                return mock_events_response
            else:
                return mock_oauth_response  # fallback
        
        mock_requests_get.side_effect = mock_get_side_effect
        
        # Test
        result = get_availability_low_level("user123", "2024-01-15", "2024-01-15")
        
        # Assertions
        assert result["timezone"] == "America/New_York"
        assert len(result["events"]) == 2
        assert result["events"][0]["title"] == "Meeting 1"  # Note: function returns 'title' not 'summary'
        assert result["events"][1]["title"] == "Meeting 2"

    def test_get_availability_low_level_no_oauth_token(self, mock_secrets, mock_requests_get):
        """Test availability retrieval when OAuth token is not available"""
        # Mock OAuth response with no token
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_requests_get.return_value = mock_response
        
        # Test
        with pytest.raises(Exception, match="Could not retrieve Google OAuth token"):
            get_availability_low_level("user123", "2024-01-15", "2024-01-15")

    def test_book_event_low_level_success(self, mock_secrets, mock_requests_get, mock_requests_post):
        """Test successful event booking"""
        # Mock OAuth token response
        mock_oauth_response = Mock()
        mock_oauth_response.status_code = 200
        mock_oauth_response.json.return_value = [{"token": "test_token"}]
        
        # Mock calendar info response
        mock_calendar_response = Mock()
        mock_calendar_response.status_code = 200
        mock_calendar_response.json.return_value = {"timeZone": "America/New_York"}
        
        # Mock event creation response
        mock_create_response = Mock()
        mock_create_response.status_code = 200
        mock_create_response.json.return_value = {
            "id": "new_event_123",
            "htmlLink": "https://calendar.google.com/event/123",
            "summary": "Test Meeting"
        }
        
        # Configure mock responses
        def mock_get_side_effect(url, *args, **kwargs):
            if "api.clerk.com" in url:
                return mock_oauth_response
            elif "calendars/primary" in url and "events" not in url:
                return mock_calendar_response
            else:
                return mock_oauth_response  # fallback
        
        mock_requests_get.side_effect = mock_get_side_effect
        mock_requests_post.return_value = mock_create_response
        
        # Test
        result = book_event_low_level(
            user_id="user123",
            start_date="2024-01-15",
            start_time="10:00",
            end_date="2024-01-15", 
            end_time="11:00",
            title="Test Meeting",
            description="Test description",
            attendees=["test@example.com"],
            location="Test Location"
        )
        
        # Assertions
        assert result["event_id"] == "new_event_123"
        assert result["html_link"] == "https://calendar.google.com/event/123"
        assert result["title"] == "Test Meeting"
        
        # Verify POST request was made with correct data
        mock_requests_post.assert_called_once()
        call_args = mock_requests_post.call_args
        assert "googleapis.com" in call_args[0][0]
        assert call_args[1]["headers"]["Authorization"] == "Bearer test_token"
        
        # Verify event data structure
        event_data = call_args[1]["json"]  # The function uses json parameter, which is already a dict
        assert event_data["summary"] == "Test Meeting"
        assert event_data["description"] == "Test description"
        assert event_data["location"] == "Test Location"
        assert "test@example.com" in [attendee["email"] for attendee in event_data["attendees"]]

    def test_cancel_event_low_level_success(self, mock_secrets, mock_requests_get, mock_requests_delete):
        """Test successful event cancellation"""
        # Mock OAuth token response
        mock_oauth_response = Mock()
        mock_oauth_response.status_code = 200
        mock_oauth_response.json.return_value = [{"token": "test_token"}]
        
        # Mock delete response
        mock_delete_response = Mock()
        mock_delete_response.status_code = 204
        mock_delete_response.json.return_value = {}
        mock_delete_response.headers = {}  # Add empty headers to avoid Mock.keys() error
        
        # Configure mock responses
        def mock_get_side_effect(url, *args, **kwargs):
            if "api.clerk.com" in url:
                return mock_oauth_response
            else:
                return mock_oauth_response  # fallback
        
        mock_requests_get.side_effect = mock_get_side_effect
        mock_requests_delete.return_value = mock_delete_response
        
        # Test
        result = cancel_event_low_level("user123", "event_123", notify_attendees=True)
        
        # Assertions
        assert result["status"] == "cancelled"
        assert result["event_id"] == "event_123"
        
        # Verify DELETE request was made
        mock_requests_delete.assert_called_once()
        call_args = mock_requests_delete.call_args
        assert "googleapis.com" in call_args[0][0]
        assert call_args[1]["headers"]["Authorization"] == "Bearer test_token"

    def test_get_event_low_level_success(self, mock_secrets, mock_requests_get):
        """Test successful event retrieval"""
        # Mock OAuth token response
        mock_oauth_response = Mock()
        mock_oauth_response.status_code = 200
        mock_oauth_response.json.return_value = [{"token": "test_token"}]
        
        # Mock event response
        mock_event_response = Mock()
        mock_event_response.status_code = 200
        mock_event_response.json.return_value = {
            "id": "event_123",
            "summary": "Test Event",
            "start": {"dateTime": "2024-01-15T10:00:00Z"},
            "end": {"dateTime": "2024-01-15T11:00:00Z"}
        }
        
        # Configure mock responses
        def mock_get_side_effect(url, *args, **kwargs):
            if "api.clerk.com" in url:
                return mock_oauth_response
            elif "events" in url:
                return mock_event_response
            else:
                return mock_oauth_response  # fallback
        
        mock_requests_get.side_effect = mock_get_side_effect
        
        # Test
        result = get_event_low_level("user123", "event_123")
        
        # Assertions
        assert result["event_id"] == "event_123"  # Function returns 'event_id' not 'id'
        assert result["title"] == "Test Event"  # Function returns 'title' not 'summary'
        
        # Verify GET request was made
        assert mock_requests_get.call_count == 2  # OAuth + event


class TestCalendarAssistant:
    """Test suite for CalendarAssistant class"""
    
    @pytest.fixture
    def calendar_assistant(self):
        """Create a CalendarAssistant instance for testing"""
        return CalendarAssistant("user123")
    
    @pytest.fixture
    def mock_availability_response(self):
        """Mock availability response"""
        return {
            "events": [
                {
                    "title": "Existing Meeting",
                    "start": "2024-01-15T10:00:00Z",
                    "end": "2024-01-15T11:00:00Z"
                }
            ],
            "timezone": "America/New_York"
        }
    
    @pytest.fixture
    def mock_booking_response(self):
        """Mock booking response"""
        return {
            "event_id": "new_event_123",
            "html_link": "https://calendar.google.com/event/123",
            "title": "Test Meeting"
        }

    def test_calendar_assistant_initialization(self, calendar_assistant):
        """Test CalendarAssistant initialization"""
        assert calendar_assistant.user_id == "user123"
        assert calendar_assistant._last_booking is None
        assert calendar_assistant._last_cancellation is None

    @patch('calendar_utils.calendar_tools.get_availability_low_level')
    def test_get_availability(self, mock_get_availability, calendar_assistant, mock_availability_response):
        """Test get_availability method"""
        mock_get_availability.return_value = mock_availability_response
        
        result = calendar_assistant.get_availability("2024-01-15", "2024-01-15")
        
        assert result == mock_availability_response
        mock_get_availability.assert_called_once_with("user123", "2024-01-15", "2024-01-15")

    @patch('calendar_utils.calendar_tools.get_availability_low_level')
    def test_check_slot_availability_available(self, mock_get_availability, calendar_assistant):
        """Test check_slot_availability when slot is available"""
        mock_get_availability.return_value = {
            "events": [],
            "timezone": "America/New_York"
        }
        
        result = calendar_assistant.check_slot_availability("2024-01-15", "14:00", "15:00")
        
        assert result["is_available"] is True
        assert result["conflicting_events"] == []
        assert result["requested_slot"]["date"] == "2024-01-15"
        assert result["requested_slot"]["start_time"] == "14:00"
        assert result["requested_slot"]["end_time"] == "15:00"

    @patch('calendar_utils.calendar_tools.get_availability_low_level')
    def test_check_slot_availability_conflict(self, mock_get_availability, calendar_assistant):
        """Test check_slot_availability when slot has conflicts"""
        mock_get_availability.return_value = {
            "events": [
                {
                    "title": "Conflicting Meeting",
                    "start": "2024-01-15T14:30:00Z",
                    "end": "2024-01-15T15:30:00Z"
                }
            ],
            "timezone": "America/New_York"
        }
        
        result = calendar_assistant.check_slot_availability("2024-01-15", "14:00", "15:00")
        
        assert result["is_available"] is False
        assert len(result["conflicting_events"]) == 1
        assert result["conflicting_events"][0]["title"] == "Conflicting Meeting"

    @patch('calendar_utils.calendar_tools.get_availability_low_level')
    @patch('calendar_utils.calendar_tools.book_event_low_level')
    def test_book_event_success(self, mock_book_event, mock_get_availability, calendar_assistant, mock_booking_response):
        """Test successful event booking"""
        # Mock availability check - slot is available
        mock_get_availability.return_value = {
            "events": [],
            "timezone": "America/New_York"
        }
        
        # Mock booking response
        mock_book_event.return_value = mock_booking_response
        
        result = calendar_assistant.book_event(
            date="2024-01-15",
            start_time="14:00",
            end_time="15:00",
            title="Test Meeting",
            description="Test description",
            attendees=["test@example.com"],
            location="Test Location"
        )
        
        assert result == mock_booking_response
        assert calendar_assistant._last_booking == mock_booking_response
        
        # Verify book_event_low_level was called with correct parameters
        mock_book_event.assert_called_once_with(
            user_id="user123",
            start_date="2024-01-15",
            start_time="14:00",
            end_date="2024-01-15",
            end_time="15:00",
            title="Test Meeting",
            description="Test description",
            attendees=["test@example.com"],
            location="Test Location",
            reminders=None
        )

    @patch('calendar_utils.calendar_tools.get_availability_low_level')
    def test_book_event_slot_not_available(self, mock_get_availability, calendar_assistant):
        """Test event booking when slot is not available"""
        # Mock availability check - slot has conflicts
        mock_get_availability.return_value = {
            "events": [
                {
                    "title": "Conflicting Meeting",
                    "start": "2024-01-15T14:30:00Z",
                    "end": "2024-01-15T15:30:00Z"
                }
            ],
            "timezone": "America/New_York"
        }
        
        result = calendar_assistant.book_event(
            date="2024-01-15",
            start_time="14:00",
            end_time="15:00",
            title="Test Meeting"
        )
        
        assert result["error"] == "slot_not_available"
        assert "Conflicting events" in result["message"]
        assert len(result["conflicting_events"]) == 1
        assert calendar_assistant._last_booking is None

    @patch('calendar_utils.calendar_tools.cancel_event_low_level')
    def test_cancel_event_success(self, mock_cancel_event, calendar_assistant):
        """Test successful event cancellation"""
        mock_cancel_event.return_value = {
            "status": "cancelled",
            "event_id": "event_123"
        }
        
        result = calendar_assistant.cancel_event("event_123", notify_attendees=True)
        
        assert result["status"] == "cancelled"
        assert result["event_id"] == "event_123"
        assert calendar_assistant._last_cancellation == result
        
        mock_cancel_event.assert_called_once_with("user123", "event_123", True)

    @patch('calendar_utils.calendar_tools.get_event_low_level')
    def test_get_event(self, mock_get_event, calendar_assistant):
        """Test get_event method"""
        mock_get_event.return_value = {
            "id": "event_123",
            "summary": "Test Event"
        }
        
        result = calendar_assistant.get_event("event_123")
        
        assert result["id"] == "event_123"
        assert result["summary"] == "Test Event"
        mock_get_event.assert_called_once_with("user123", "event_123")

    def test_memory_methods(self, calendar_assistant):
        """Test memory-related methods"""
        # Initially no memory
        assert calendar_assistant.get_last_booking_info() is None
        assert calendar_assistant.get_last_cancellation_info() is None
        assert calendar_assistant.get_booking_confirmation_text() is None
        assert calendar_assistant.get_cancellation_confirmation_text() is None
        
        # Set some memory
        calendar_assistant._last_booking = {
            "event_id": "event_123",
            "html_link": "https://calendar.google.com/event/123",
            "title": "Test Meeting"
        }
        calendar_assistant._last_cancellation = {
            "event_id": "event_456"
        }
        
        # Test memory retrieval
        assert calendar_assistant.get_last_booking_info()["event_id"] == "event_123"
        assert calendar_assistant.get_last_cancellation_info()["event_id"] == "event_456"
        
        # Test confirmation text
        confirmation_text = calendar_assistant.get_booking_confirmation_text()
        assert "Event ID: event_123" in confirmation_text
        assert "Calendar Link: https://calendar.google.com/event/123" in confirmation_text
        
        assert calendar_assistant.get_cancellation_confirmation_text() == "Event event_456 has been successfully cancelled."
        
        # Test memory clearing
        calendar_assistant.clear_memory()
        assert calendar_assistant.get_last_booking_info() is None
        assert calendar_assistant.get_last_cancellation_info() is None


class TestCalendarTools:
    """Test suite for calendar tools utilities"""
    
    def test_build_calendar_tools(self):
        """Test build_calendar_tools function"""
        tools = build_calendar_tools()
        
        # Verify we have the expected tools
        tool_names = [tool["function"]["name"] for tool in tools]
        expected_tools = ["get_availability", "check_slot_availability", "book_event", "cancel_event"]
        
        assert len(tools) == 4
        for expected_tool in expected_tools:
            assert expected_tool in tool_names
        
        # Verify tool structure
        for tool in tools:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]

    def test_calendar_tool_executor(self):
        """Test calendar_tool_executor function"""
        calendar_assistant = CalendarAssistant("user123")
        
        # Test get_availability
        with patch.object(calendar_assistant, 'get_availability') as mock_get_availability:
            mock_get_availability.return_value = {"events": []}
            
            result = calendar_tool_executor(
                calendar_assistant,
                "get_availability",
                {"start_date": "2024-01-15", "end_date": "2024-01-15"}
            )
            
            assert result == {"events": []}
            mock_get_availability.assert_called_once_with(start_date="2024-01-15", end_date="2024-01-15")
        
        # Test unknown tool
        result = calendar_tool_executor(calendar_assistant, "unknown_tool", {})
        assert result["error"] == "Unknown tool: unknown_tool" 