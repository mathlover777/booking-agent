"""
Test the CalendarAssistant memory functionality.
"""
import unittest
from unittest.mock import Mock, patch
import sys
import os

# Mock AWS dependencies before importing calendar_tools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock the AWS utils module
mock_aws_utils = Mock()
mock_aws_utils._secrets = {}
sys.modules['common_utils.aws_utils'] = mock_aws_utils

from .calendar_tools import CalendarAssistant


class TestCalendarAssistantMemory(unittest.TestCase):
    
    def setUp(self):
        self.cal_assistant = CalendarAssistant("test_user_id")
    
    def test_initial_memory_state(self):
        """Test that memory is initially empty."""
        self.assertIsNone(self.cal_assistant.get_last_booking_info())
        self.assertIsNone(self.cal_assistant.get_last_cancellation_info())
        self.assertIsNone(self.cal_assistant.get_booking_confirmation_text())
        self.assertIsNone(self.cal_assistant.get_cancellation_confirmation_text())
    
    @patch.object(CalendarAssistant, 'check_slot_availability')
    @patch('calendar_utils.calendar_tools.book_event_low_level')
    def test_booking_memory_storage(self, mock_book_event, mock_check):
        """Test that successful bookings are stored in memory."""
        # Mock slot availability check to return available
        mock_check.return_value = {
            'is_available': True,
            'conflicting_events': [],
            'requested_slot': {
                'date': '2024-01-15',
                'start_time': '14:00',
                'end_time': '15:00'
            }
        }
        
        # Mock successful booking response
        mock_response = {
            'event_id': 'test_event_123',
            'title': 'Test Meeting',
            'html_link': 'https://calendar.google.com/event/test_event_123',
            'start': '2024-01-15T14:00:00Z',
            'end': '2024-01-15T15:00:00Z'
        }
        mock_book_event.return_value = mock_response
        
        # Perform booking
        result = self.cal_assistant.book_event(
            date="2024-01-15",
            start_time="14:00",
            end_time="15:00",
            title="Test Meeting"
        )
        
        # Verify booking was stored in memory
        self.assertEqual(self.cal_assistant.get_last_booking_info(), mock_response)
        
        # Verify confirmation text
        confirmation_text = self.cal_assistant.get_booking_confirmation_text()
        self.assertIn("Event ID: test_event_123", confirmation_text)
        self.assertIn("Calendar Link: https://calendar.google.com/event/test_event_123", confirmation_text)
    
    @patch('calendar_utils.calendar_tools.cancel_event_low_level')
    def test_cancellation_memory_storage(self, mock_cancel_event):
        """Test that successful cancellations are stored in memory."""
        # Mock successful cancellation response
        mock_response = {
            'event_id': 'test_event_123',
            'status': 'cancelled',
            'notified_attendees': True,
            'message': 'Event successfully cancelled'
        }
        mock_cancel_event.return_value = mock_response
        
        # Perform cancellation
        result = self.cal_assistant.cancel_event("test_event_123")
        
        # Verify cancellation was stored in memory
        self.assertEqual(self.cal_assistant.get_last_cancellation_info(), mock_response)
        
        # Verify confirmation text
        confirmation_text = self.cal_assistant.get_cancellation_confirmation_text()
        self.assertEqual(confirmation_text, "Event test_event_123 has been successfully cancelled.")
    
    @patch.object(CalendarAssistant, 'check_slot_availability')
    @patch('calendar_utils.calendar_tools.book_event_low_level')
    def test_failed_booking_no_memory_storage(self, mock_book_event, mock_check):
        """Test that failed bookings are not stored in memory."""
        # Mock slot availability check to return available
        mock_check.return_value = {
            'is_available': True,
            'conflicting_events': [],
            'requested_slot': {
                'date': '2024-01-15',
                'start_time': '14:00',
                'end_time': '15:00'
            }
        }
        
        # Mock failed booking response (no event_id)
        mock_response = {
            'error': 'Failed to book event'
        }
        mock_book_event.return_value = mock_response
        
        # Perform booking
        result = self.cal_assistant.book_event(
            date="2024-01-15",
            start_time="14:00",
            end_time="15:00",
            title="Test Meeting"
        )
        
        # Verify booking was not stored in memory
        self.assertIsNone(self.cal_assistant.get_last_booking_info())
        self.assertIsNone(self.cal_assistant.get_booking_confirmation_text())
    
    @patch('calendar_utils.calendar_tools.cancel_event_low_level')
    def test_failed_cancellation_no_memory_storage(self, mock_cancel_event):
        """Test that failed cancellations are not stored in memory."""
        # Mock failed cancellation response (status not 'cancelled')
        mock_response = {
            'event_id': 'test_event_123',
            'status': 'failed',
            'message': 'Failed to cancel event'
        }
        mock_cancel_event.return_value = mock_response
        
        # Perform cancellation
        result = self.cal_assistant.cancel_event("test_event_123")
        
        # Verify cancellation was not stored in memory
        self.assertIsNone(self.cal_assistant.get_last_cancellation_info())
        self.assertIsNone(self.cal_assistant.get_cancellation_confirmation_text())
    
    def test_clear_memory(self):
        """Test that clear_memory() clears all stored data."""
        # Set some mock data
        self.cal_assistant._last_booking = {'event_id': 'test_123'}
        self.cal_assistant._last_cancellation = {'event_id': 'test_456'}
        
        # Clear memory
        self.cal_assistant.clear_memory()
        
        # Verify memory is cleared
        self.assertIsNone(self.cal_assistant.get_last_booking_info())
        self.assertIsNone(self.cal_assistant.get_last_cancellation_info())
        self.assertIsNone(self.cal_assistant.get_booking_confirmation_text())
        self.assertIsNone(self.cal_assistant.get_cancellation_confirmation_text())

    @patch('calendar_utils.calendar_tools.get_availability_low_level')
    def test_check_slot_availability_conflict(self, mock_get_availability):
        """Test the slot availability checking with conflicting events."""
        # Mock response with conflicting events
        mock_get_availability.return_value = {
            'events': [
                {
                    'summary': 'Existing Meeting',
                    'start': {'dateTime': '2024-01-15T14:00:00Z'},
                    'end': {'dateTime': '2024-01-15T15:00:00Z'}
                }
            ],
            'timezone': 'America/New_York'
        }
        
        # Test checking a conflicting slot
        result = self.cal_assistant.check_slot_availability('2024-01-15', '14:30', '15:30')
        
        self.assertFalse(result['is_available'])
        self.assertEqual(len(result['conflicting_events']), 1)
        self.assertEqual(result['conflicting_events'][0]['title'], 'Existing Meeting')
        self.assertEqual(result['requested_slot']['date'], '2024-01-15')
        self.assertEqual(result['requested_slot']['start_time'], '14:30')
        self.assertEqual(result['requested_slot']['end_time'], '15:30')

    @patch('calendar_utils.calendar_tools.get_availability_low_level')
    def test_check_slot_availability_available(self, mock_get_availability):
        """Test the slot availability checking with no conflicts."""
        # Mock response with no events
        mock_get_availability.return_value = {
            'events': [],
            'timezone': 'America/New_York'
        }
        
        # Test checking an available slot
        result = self.cal_assistant.check_slot_availability('2024-01-15', '16:00', '17:00')
        
        self.assertTrue(result['is_available'])
        self.assertEqual(len(result['conflicting_events']), 0)
        self.assertEqual(result['requested_slot']['date'], '2024-01-15')
        self.assertEqual(result['requested_slot']['start_time'], '16:00')
        self.assertEqual(result['requested_slot']['end_time'], '17:00')

    @patch.object(CalendarAssistant, 'check_slot_availability')
    def test_book_event_with_conflict(self, mock_check):
        """Test that book_event properly handles slot conflicts."""
        # Mock the check_slot_availability to return conflict
        mock_check.return_value = {
            'is_available': False,
            'conflicting_events': [
                {
                    'title': 'Existing Meeting',
                    'start': '2024-01-15T14:00:00Z',
                    'end': '2024-01-15T15:00:00Z'
                }
            ],
            'requested_slot': {
                'date': '2024-01-15',
                'start_time': '14:30',
                'end_time': '15:30'
            }
        }
        
        # Test booking a conflicting slot
        result = self.cal_assistant.book_event(
            date='2024-01-15',
            start_time='14:30',
            end_time='15:30',
            title='Test Meeting'
        )
        
        self.assertEqual(result['error'], 'slot_not_available')
        self.assertIn('Slot is not available', result['message'])
        self.assertEqual(len(result['conflicting_events']), 1)
        self.assertEqual(result['conflicting_events'][0]['title'], 'Existing Meeting')

    @patch.object(CalendarAssistant, 'check_slot_availability')
    @patch('calendar_utils.calendar_tools.book_event_low_level')
    def test_book_event_with_available_slot(self, mock_book_event, mock_check):
        """Test that book_event proceeds when slot is available."""
        # Mock the check_slot_availability to return available
        mock_check.return_value = {
            'is_available': True,
            'conflicting_events': [],
            'requested_slot': {
                'date': '2024-01-15',
                'start_time': '16:00',
                'end_time': '17:00'
            }
        }
        
        # Mock successful booking response
        mock_response = {
            'event_id': 'test_event_123',
            'title': 'Test Meeting',
            'html_link': 'https://calendar.google.com/event/test_event_123'
        }
        mock_book_event.return_value = mock_response
        
        # Test booking an available slot
        result = self.cal_assistant.book_event(
            date='2024-01-15',
            start_time='16:00',
            end_time='17:00',
            title='Test Meeting'
        )
        
        # Verify the booking proceeded normally
        self.assertEqual(result, mock_response)
        self.assertEqual(self.cal_assistant.get_last_booking_info(), mock_response)


if __name__ == '__main__':
    unittest.main() 