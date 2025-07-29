import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import logging
from typing import Dict, Any

import os
from dotenv import load_dotenv

# Configure logging for tests to reduce noise
logging.basicConfig(level=logging.WARNING)
logging.getLogger('booking_agent.calendar_owner_resolver').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

# Load environment variables BEFORE importing modules that depend on them
# Test runs from src directory, so use relative path to root
load_dotenv('../.env.base', override=True)
load_dotenv('../.env.dev', override=True)

# Set additional required environment variables
os.environ['USER_EMAILS_TABLE_NAME'] = 'vibes-user-emails-dev'

# Mock AWS services before importing modules that use them
with patch('boto3.client') as mock_boto3_client, \
     patch('boto3.resource') as mock_boto3_resource:
    
    # Mock secrets manager response
    mock_secrets_client = Mock()
    mock_secrets_client.get_secret_value.return_value = {
        'SecretString': '{"OPENAI_API_KEY": "test-key", "CLERK_SECRET_KEY": "test-clerk-key"}'
    }
    mock_boto3_client.return_value = mock_secrets_client
    
    # Mock DynamoDB
    mock_dynamodb = Mock()
    mock_table = Mock()
    mock_dynamodb.Table.return_value = mock_table
    mock_boto3_resource.return_value = mock_dynamodb
    
    from .calendar_owner_resolver import resolve_calendar_owner, _list_booking_emails, _lookup_user_records


class TestCalendarOwnerResolver(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_parsed_email = {
            "subject": "Test Meeting",
            "from": ["sender@example.com"],
            "to": ["booking@bhaang.com"],
            "cc": ["other@example.com"],
            "body": "Let's schedule a meeting",
            "date": "2024-01-01",
            "message_id": "test-123"
        }
    
    def test_list_booking_emails_single_booking_email(self):
        """Test finding a single booking email in the conversation."""
        parsed_email = {
            "from": ["user@example.com"],
            "to": ["booking@bhaang.com"],
            "cc": ["other@example.com"]
        }
        
        result = _list_booking_emails(parsed_email)
        self.assertEqual(result, ["booking@bhaang.com"])
    
    def test_list_booking_emails_multiple_booking_emails(self):
        """Test finding multiple booking emails in the conversation."""
        parsed_email = {
            "from": ["user@example.com"],
            "to": ["booking@bhaang.com", "booking2@bhaang.com"],
            "cc": ["other@example.com"]
        }
        
        result = _list_booking_emails(parsed_email)
        self.assertEqual(set(result), {"booking@bhaang.com", "booking2@bhaang.com"})
    
    def test_list_booking_emails_no_booking_emails(self):
        """Test when no booking emails are found."""
        parsed_email = {
            "from": ["user@example.com"],
            "to": ["other@example.com"],
            "cc": ["another@example.com"]
        }
        
        result = _list_booking_emails(parsed_email)
        self.assertEqual(result, [])
    
    def test_list_booking_emails_with_email_formats(self):
        """Test handling different email formats."""
        parsed_email = {
            "from": ["User Name <user@example.com>"],
            "to": ["Booking Agent <booking@bhaang.com>"],
            "cc": ["Other <other@example.com>"]
        }
        
        result = _list_booking_emails(parsed_email)
        self.assertEqual(result, ["booking@bhaang.com"])
    
    @patch('booking_agent.calendar_owner_resolver._user_email_table')
    def test_lookup_user_records_single_user(self, mock_table):
        """Test looking up a single user record."""
        mock_table.query.return_value = {
            "Items": [{"user_id": "user123", "assist_email": "booking@bhaang.com"}]
        }
        
        result = _lookup_user_records(["booking@bhaang.com"])
        
        self.assertEqual(result, {"booking@bhaang.com": {"user_id": "user123", "assist_email": "booking@bhaang.com"}})
        mock_table.query.assert_called_once()
    
    @patch('booking_agent.calendar_owner_resolver._user_email_table')
    def test_lookup_user_records_multiple_users(self, mock_table):
        """Test looking up multiple user records."""
        def mock_query(**kwargs):
            email = kwargs['ExpressionAttributeValues'][':email']
            if email == "booking1@bhaang.com":
                return {"Items": [{"user_id": "user1", "assist_email": "booking1@bhaang.com"}]}
            elif email == "booking2@bhaang.com":
                return {"Items": [{"user_id": "user2", "assist_email": "booking2@bhaang.com"}]}
            return {"Items": []}
        
        mock_table.query.side_effect = mock_query
        
        result = _lookup_user_records(["booking1@bhaang.com", "booking2@bhaang.com"])
        
        expected = {
            "booking1@bhaang.com": {"user_id": "user1", "assist_email": "booking1@bhaang.com"},
            "booking2@bhaang.com": {"user_id": "user2", "assist_email": "booking2@bhaang.com"}
        }
        self.assertEqual(result, expected)
        self.assertEqual(mock_table.query.call_count, 2)
    
    @patch('booking_agent.calendar_owner_resolver._user_email_table')
    def test_lookup_user_records_no_users_found(self, mock_table):
        """Test when no user records are found."""
        mock_table.query.return_value = {"Items": []}
        
        result = _lookup_user_records(["booking@bhaang.com"])
        
        self.assertEqual(result, {})
    
    @patch('booking_agent.calendar_owner_resolver._user_email_table')
    def test_lookup_user_records_dynamodb_error(self, mock_table):
        """Test handling DynamoDB errors."""
        mock_table.query.side_effect = Exception("DynamoDB error")
        
        result = _lookup_user_records(["booking@bhaang.com"])
        
        self.assertEqual(result, {})
    
    @patch('booking_agent.calendar_owner_resolver._list_booking_emails')
    @patch('booking_agent.calendar_owner_resolver._lookup_user_records')
    def test_resolve_calendar_owner_no_booking_emails(self, mock_lookup, mock_list):
        """Test when no booking emails are found in conversation."""
        mock_list.return_value = []
        
        result = resolve_calendar_owner(self.sample_parsed_email)
        
        self.assertEqual(result["status"], "no_mapping")
        self.assertIn("No booking agent emails found", result["reason"])
    
    @patch('booking_agent.calendar_owner_resolver._list_booking_emails')
    @patch('booking_agent.calendar_owner_resolver._lookup_user_records')
    def test_resolve_calendar_owner_no_valid_owners(self, mock_lookup, mock_list):
        """Test when booking emails exist but no valid owners found."""
        mock_list.return_value = ["booking@bhaang.com", "booking2@bhaang.com"]
        mock_lookup.return_value = {}  # No valid owners
        
        result = resolve_calendar_owner(self.sample_parsed_email)
        
        self.assertEqual(result["status"], "no_mapping")
        self.assertIn("No valid calendar owners found", result["reason"])
    
    @patch('booking_agent.calendar_owner_resolver._list_booking_emails')
    @patch('booking_agent.calendar_owner_resolver._lookup_user_records')
    def test_resolve_calendar_owner_single_valid_owner(self, mock_lookup, mock_list):
        """Test when exactly one valid owner is found."""
        mock_list.return_value = ["booking@bhaang.com", "booking2@bhaang.com"]
        mock_lookup.return_value = {
            "booking@bhaang.com": {"user_id": "user123", "assist_email": "booking@bhaang.com"}
        }
        
        result = resolve_calendar_owner(self.sample_parsed_email)
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["user_id"], "user123")
        self.assertEqual(result["assist_email"], "booking@bhaang.com")
    
    @patch('booking_agent.calendar_owner_resolver._list_booking_emails')
    @patch('booking_agent.calendar_owner_resolver._lookup_user_records')
    @patch('booking_agent.calendar_owner_resolver._disambiguate_owner_with_llm')
    def test_resolve_calendar_owner_multiple_valid_owners_llm_success(self, mock_llm, mock_lookup, mock_list):
        """Test when multiple valid owners exist and LLM successfully chooses one."""
        mock_list.return_value = ["booking1@bhaang.com", "booking2@bhaang.com"]
        mock_lookup.return_value = {
            "booking1@bhaang.com": {"user_id": "user1", "assist_email": "booking1@bhaang.com"},
            "booking2@bhaang.com": {"user_id": "user2", "assist_email": "booking2@bhaang.com"}
        }
        mock_llm.return_value = "booking1@bhaang.com"
        
        result = resolve_calendar_owner(self.sample_parsed_email)
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["user_id"], "user1")
        self.assertEqual(result["assist_email"], "booking1@bhaang.com")
        mock_llm.assert_called_once_with(self.sample_parsed_email, ["booking1@bhaang.com", "booking2@bhaang.com"])
    
    @patch('booking_agent.calendar_owner_resolver._list_booking_emails')
    @patch('booking_agent.calendar_owner_resolver._lookup_user_records')
    @patch('booking_agent.calendar_owner_resolver._disambiguate_owner_with_llm')
    def test_resolve_calendar_owner_multiple_valid_owners_llm_failure(self, mock_llm, mock_lookup, mock_list):
        """Test when multiple valid owners exist but LLM cannot choose."""
        mock_list.return_value = ["booking1@bhaang.com", "booking2@bhaang.com"]
        mock_lookup.return_value = {
            "booking1@bhaang.com": {"user_id": "user1", "assist_email": "booking1@bhaang.com"},
            "booking2@bhaang.com": {"user_id": "user2", "assist_email": "booking2@bhaang.com"}
        }
        mock_llm.return_value = None
        
        result = resolve_calendar_owner(self.sample_parsed_email)
        
        self.assertEqual(result["status"], "multiple_not_sure")
        self.assertEqual(result["candidates"], ["booking1@bhaang.com", "booking2@bhaang.com"])
        self.assertIn("LLM could not confidently choose", result["reason"])
    
    @patch('booking_agent.calendar_owner_resolver._list_booking_emails')
    @patch('booking_agent.calendar_owner_resolver._lookup_user_records')
    def test_resolve_calendar_owner_filter_invalid_emails(self, mock_lookup, mock_list):
        """Test that invalid booking emails are filtered out."""
        # Three booking emails in conversation
        mock_list.return_value = ["booking1@bhaang.com", "booking2@bhaang.com", "booking3@bhaang.com"]
        # But only two have valid owners
        mock_lookup.return_value = {
            "booking1@bhaang.com": {"user_id": "user1", "assist_email": "booking1@bhaang.com"},
            "booking2@bhaang.com": {"user_id": "user2", "assist_email": "booking2@bhaang.com"}
        }
        
        result = resolve_calendar_owner(self.sample_parsed_email)
        
        # Should proceed with only the valid emails
        self.assertEqual(result["status"], "multiple_not_sure")
        self.assertEqual(result["candidates"], ["booking1@bhaang.com", "booking2@bhaang.com"])
    
    @patch('booking_agent.calendar_owner_resolver._list_booking_emails')
    @patch('booking_agent.calendar_owner_resolver._lookup_user_records')
    def test_resolve_calendar_owner_all_emails_invalid(self, mock_lookup, mock_list):
        """Test when all booking emails are invalid."""
        mock_list.return_value = ["booking1@bhaang.com", "booking2@bhaang.com"]
        mock_lookup.return_value = {}  # No valid owners
        
        result = resolve_calendar_owner(self.sample_parsed_email)
        
        self.assertEqual(result["status"], "no_mapping")
        self.assertIn("No valid calendar owners found", result["reason"])


if __name__ == '__main__':
    unittest.main() 