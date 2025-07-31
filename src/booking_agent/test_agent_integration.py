import os
import re
import uuid
import logging
import boto3
from datetime import datetime, timedelta
from typing import Dict, Any

from dotenv import load_dotenv

# Configure logging for tests to reduce noise
logging.basicConfig(level=logging.WARNING)
logging.getLogger('booking_agent').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

# Load environment variables BEFORE importing modules that depend on them
# Test runs from src directory, so use relative path to root
load_dotenv('../.env.base', override=True)
load_dotenv('../.env.dev', override=True)

# Set additional required environment variables
os.environ['USER_EMAILS_TABLE_NAME'] = 'vibes-user-emails-dev'

# Import the actual module (no mocking)
from .agent import process_booking_request
from calendar_utils.calendar_tools import CalendarAssistant

# Persistent test user - DO NOT DELETE, this is used in production
TEST_USER_ID = "user_2zTBVQZOK5QCyxL43QTVOHOw3zK"
TEST_USER_EMAIL = "souravsarkar1729@gmail.com"
TEST_AGENT_EMAIL = "test.dev@bhaang.com"  # Development agent email

# ---------------------------------------------------------------------------
# Helper utilities ----------------------------------------------------------
# ---------------------------------------------------------------------------

def _base_parsed_email(subject: str, body: str, to: list = None, cc: list = None, from_email: str = None) -> Dict[str, Any]:
    """Generate a minimal parsed_email dict for the test cases."""
    return {
        "subject": subject,
        "from": [from_email] if from_email else [TEST_USER_EMAIL],
        "to": to or [],
        "cc": cc or [],
        "body": body,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "message_id": f"test-{uuid.uuid4().hex[:8]}",
    }


def _setup_test_user(agent_email: str, user_email: str = TEST_USER_EMAIL, user_id: str = TEST_USER_ID):
    """Setup test user in DynamoDB - UPSERT operation to preserve existing data"""
    table = boto3.resource('dynamodb').Table(os.getenv('USER_EMAILS_TABLE_NAME'))
    
    # Convert full email to local part for database storage
    from common_utils.email_helpers import to_local
    assist_local = to_local(agent_email)
    
    test_item = {
        'pk': f"uid:{user_id}",
        'sk': 'data',
        'user_id': user_id,
        'assist_email': agent_email,
        'assist_local': assist_local,
        'user_email': user_email,
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-15T10:00:00'
    }
    
    # Use put_item (upsert) to preserve existing data
    table.put_item(Item=test_item)
    print(f"✅ Updated test user: {user_id} with agent: {agent_email}, user: {user_email}")
    return test_item


def _cleanup_test_user(user_id: str):
    """Cleanup test user from DynamoDB - SKIP for persistent user"""
    if user_id == TEST_USER_ID:
        print(f"⚠️  SKIPPING cleanup for persistent user: {user_id}")
        return
    
    table = boto3.resource('dynamodb').Table(os.getenv('USER_EMAILS_TABLE_NAME'))
    table.delete_item(Key={'pk': f"uid:{user_id}", 'sk': 'data'})
    print(f"🧹 Cleaned up test user: {user_id}")


# ---------------------------------------------------------------------------
# Test cases for calendar owner resolution failures (deterministic) ----------
# ---------------------------------------------------------------------------

def test_case_1_no_booking_agents_found():
    """Case 1: No booking agent emails in conversation = clarification needed"""
    print("\n=== Case 1: No booking agents found ===")
    
    # Synthetic email data with NO booking agent emails
    parsed_email = {
        "subject": "Meeting Request",
        "from": ["client@example.com"],
        "to": ["john.doe@example.com"],
        "cc": ["jane.smith@example.com"],
        "body": "Hi John,\n\nI'd like to schedule a meeting with you. Can you help me find a time?\n\nBest regards,\nClient",
        "date": "2024-01-15",
        "message_id": "case1-123"
    }
    
    print(f"Email: {parsed_email['subject']}")
    print(f"From: {parsed_email['from']}")
    print(f"To: {parsed_email['to']}")
    print(f"CC: {parsed_email['cc']}")
    print(f"Body: {parsed_email['body'][:100]}...")
    
    print(f"\n📋 EXPECTED BEHAVIOR:")
    print(f"   • Agent should detect no booking agent emails in conversation")
    print(f"   • Should return clarification_needed action")
    print(f"   • Should provide helpful message about including booking agent")
    
    result = process_booking_request(parsed_email, metadata={"test_case": "no_booking_agents_found"})
    print(f"\nResult: {result}")
    
    if result["action"] == "clarification_needed" and result["status"] == "no_booking_agents_found":
        print(f"✅ SUCCESS: Correctly identified no booking agents in conversation")
        print(f"📧 Clarification message:")
        print(f"{'─'*60}")
        print(result["clarification_message"])
        print(f"{'─'*60}")
    else:
        print(f"❌ FAILED: Expected clarification_needed, got {result.get('action')}")
    
    return result


def test_case_2_booking_agent_not_registered():
    """Case 2: Booking agent email exists but not in DynamoDB = clarification needed"""
    print("\n=== Case 2: Booking agent not registered ===")
    
    # Generate random non-existent agent email
    non_existent_agent = f"nonexistent-{uuid.uuid4().hex[:8]}@bhaang.com"
    
    # Synthetic email data with non-existent agent
    parsed_email = {
        "subject": "Meeting Request",
        "from": ["client@example.com"],
        "to": [non_existent_agent],  # This agent doesn't exist in DynamoDB
        "cc": ["other@example.com"],
        "body": "Hi,\n\nI need to schedule a meeting. Please help me find a time.\n\nThanks,\nClient",
        "date": "2024-01-15",
        "message_id": "case2-123"
    }
    
    print(f"Email: {parsed_email['subject']}")
    print(f"From: {parsed_email['from']}")
    print(f"To: {parsed_email['to']}")
    print(f"CC: {parsed_email['cc']}")
    print(f"Non-existent agent: {non_existent_agent}")
    
    print(f"\n📋 EXPECTED BEHAVIOR:")
    print(f"   • Agent should detect booking agent email: {non_existent_agent}")
    print(f"   • Should find no mapping in DynamoDB")
    print(f"   • Should return clarification_needed action")
    print(f"   • Should provide helpful message about setup")
    
    result = process_booking_request(parsed_email, metadata={"test_case": "booking_agent_not_registered"})
    print(f"\nResult: {result}")
    
    if result["action"] == "clarification_needed" and result["status"] == "booking_agent_not_registered":
        print(f"✅ SUCCESS: Correctly identified unregistered booking agent")
        print(f"📧 Clarification message:")
        print(f"{'─'*60}")
        print(result["clarification_message"])
        print(f"{'─'*60}")
    else:
        print(f"❌ FAILED: Expected clarification_needed, got {result.get('action')}")
    
    return result


def test_case_3_calendar_owner_not_in_conversation():
    """Case 3: Booking agent exists but user not in conversation = clarification needed"""
    print("\n=== Case 3: Calendar owner not in conversation ===")
    
    # Use persistent test user but with a different agent email
    test_agent_email = f"alice-agent-{uuid.uuid4().hex[:8]}@bhaang.com"
    test_user_email = "alice@example.com"  # Alice's actual email (different from persistent user)
    
    try:
        # Setup DynamoDB test data with different user email
        _setup_test_user(test_agent_email, test_user_email, TEST_USER_ID)
        
        # Synthetic email data where agent exists but user isn't in thread
        parsed_email = {
            "subject": "Meeting with Alice",
            "from": ["bob@example.com"],  # Alice is NOT in conversation
            "to": [test_agent_email],  # Alice's agent
            "cc": ["charlie@example.com"],
            "body": "Hi Alice,\n\nI'd like to schedule a meeting with you. Can you help me find a time?\n\nBest regards,\nBob",
            "date": "2024-01-15",
            "message_id": "case3-123"
        }
        
        print(f"Email: {parsed_email['subject']}")
        print(f"From: {parsed_email['from']}")
        print(f"To: {parsed_email['to']}")
        print(f"CC: {parsed_email['cc']}")
        print(f"Agent: {test_agent_email}")
        print(f"User email: {test_user_email}")
        print(f"User in conversation: No")
        
        print(f"\n📋 EXPECTED BEHAVIOR:")
        print(f"   • Agent should detect booking agent: {test_agent_email}")
        print(f"   • Should find mapping in DynamoDB")
        print(f"   • Should detect user {test_user_email} not in conversation")
        print(f"   • Should return clarification_needed action")
        print(f"   • Should provide helpful message about including user")
        
        result = process_booking_request(parsed_email, metadata={"test_case": "calendar_owner_not_in_conversation"})
        print(f"\nResult: {result}")
        
        if result["action"] == "clarification_needed" and result["status"] == "calendar_owner_not_in_conversation":
            print(f"✅ SUCCESS: Correctly identified that Alice is not in conversation")
            print(f"📧 Clarification message:")
            print(f"{'─'*60}")
            print(result["clarification_message"])
            print(f"{'─'*60}")
        else:
            print(f"❌ FAILED: Expected clarification_needed, got {result.get('action')}")
        
        return result
        
    finally:
        # Restore persistent user data
        _setup_test_user(TEST_AGENT_EMAIL, TEST_USER_EMAIL, TEST_USER_ID)


def test_case_4_missing_user_email_field():
    """Case 4: Agent exists but user_email field is missing = clarification needed"""
    print("\n=== Case 4: Missing user_email field ===")
    
    # Use persistent test user but with missing user_email field
    test_agent_email = f"missing-email-agent-{uuid.uuid4().hex[:8]}@bhaang.com"
    
    # Setup DynamoDB test data WITHOUT user_email field
    table = boto3.resource('dynamodb').Table(os.getenv('USER_EMAILS_TABLE_NAME'))
    
    # Convert full email to local part for database storage
    from common_utils.email_helpers import to_local
    assist_local = to_local(test_agent_email)
    
    test_item = {
        'pk': f"uid:{TEST_USER_ID}",
        'sk': 'data',
        'user_id': TEST_USER_ID,
        'assist_email': test_agent_email,
        'assist_local': assist_local,
        # Missing user_email field
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-15T10:00:00'
    }
    
    try:
        # Insert test data
        table.put_item(Item=test_item)
        print(f"✅ Updated test user: {TEST_USER_ID} with agent: {test_agent_email} (missing user_email)")
        
        # Synthetic email data
        parsed_email = {
            "subject": "Meeting Request",
            "from": ["client@example.com"],
            "to": [test_agent_email],
            "cc": ["other@example.com"],
            "body": "Hi,\n\nI need to schedule a meeting. Please help.\n\nThanks,\nClient",
            "date": "2024-01-15",
            "message_id": "case4-123"
        }
        
        print(f"Email: {parsed_email['subject']}")
        print(f"From: {parsed_email['from']}")
        print(f"To: {parsed_email['to']}")
        print(f"CC: {parsed_email['cc']}")
        print(f"Agent: {test_agent_email}")
        print(f"Database record: Missing user_email field")
        
        print(f"\n📋 EXPECTED BEHAVIOR:")
        print(f"   • Agent should detect booking agent: {test_agent_email}")
        print(f"   • Should find mapping in DynamoDB")
        print(f"   • Should detect missing user_email field")
        print(f"   • Should return clarification_needed action")
        print(f"   • Should provide helpful message about configuration")
        
        result = process_booking_request(parsed_email, metadata={"test_case": "missing_user_email_field"})
        print(f"\nResult: {result}")
        
        if result["action"] == "clarification_needed" and result["status"] == "user_email_missing":
            print(f"✅ SUCCESS: Correctly identified missing user_email field")
            print(f"📧 Clarification message:")
            print(f"{'─'*60}")
            print(result["clarification_message"])
            print(f"{'─'*60}")
        else:
            print(f"❌ FAILED: Expected clarification_needed, got {result.get('action')}")
        
        return result
        
    finally:
        # Restore persistent user data
        _setup_test_user(TEST_AGENT_EMAIL, TEST_USER_EMAIL, TEST_USER_ID)


# ---------------------------------------------------------------------------
# Test cases for successful end-to-end flow (similar to agent_executor) ------
# ---------------------------------------------------------------------------

def test_case_5_share_availability():
    """Case 5: User asks for availability - successful end-to-end flow"""
    print("\n=== Case 5: Share Availability (End-to-End) ===")
    
    # Use persistent test user
    test_agent_email = TEST_AGENT_EMAIL
    
    start = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    
    # Setup DynamoDB test data (already exists, but ensure it's correct)
    _setup_test_user(test_agent_email, TEST_USER_EMAIL, TEST_USER_ID)
    
    # Simulate a realistic email conversation where someone asks for availability
    body = (
        f"@{test_agent_email} please share my availability for {start} to {end}!\n\n"
        f"On Sun, 6 Jul 2025 at 06:48, John Doe <john.doe@example.com> wrote:\n"
        f"> Hi {TEST_USER_EMAIL},\n>\n"
        f"> I'd like to schedule a meeting with you next week. Could you please share\n"
        f"> your availability between {start} and {end}?\n>\n"
        f"> Thanks,\n"
        f"> John\n>\n"
        f"> On Sun, 6 Jul 2025 at 06:31, {TEST_USER_EMAIL} wrote:\n"
        f">> Hi John,\n>>\n"
        f">> Sure, let me check my calendar and get back to you.\n>>\n"
        f">> Best regards,\n"
        f">> Sourav"
    )
    
    parsed_email = _base_parsed_email(
        "Re: Meeting request", 
        body,
        to=[test_agent_email, "john.doe@example.com"],  # Both booking agent and John
        from_email=TEST_USER_EMAIL
    )
    
    print(f"📅 Requesting availability for: {start} to {end}")
    print(f"👤 User: {TEST_USER_EMAIL}")
    print(f"🤖 Agent: {test_agent_email}")
    print(f"📧 Recipients: John Doe + Agent")
    
    print(f"\n📋 EXPECTED BEHAVIOR:")
    print(f"   • Agent should resolve calendar owner successfully")
    print(f"   • Should check calendar for {start} to {end}")
    print(f"   • Response should contain available time slots")
    print(f"   • Response should end with 'By VibeCal'")
    print(f"   • Response should be sent to John Doe")
    
    result = process_booking_request(parsed_email, metadata={"test_case": "share_availability"})
    print(f"\nResult: {result}")
    
    if result["action"] == "processed":
        print(f"✅ SUCCESS: End-to-end flow completed successfully")
        print(f"📧 AI Response:")
        print(f"{'─'*60}")
        print(result["ai_response"])
        print(f"{'─'*60}")
        print(f"\n📋 VERIFICATION:")
        print(f"   • Action: {result['action']}")
        print(f"   • Calendar User ID: {result['calendar_user_id']}")
        print(f"   • Booking Email: {result['booking_email']}")
        print(f"   • Response contains 'By VibeCal': {'By VibeCal' in result['ai_response']}")
    else:
        print(f"❌ FAILED: Expected processed, got {result.get('action')}")
        if result.get("clarification_message"):
            print(f"📧 Clarification message:")
            print(f"{'─'*60}")
            print(result["clarification_message"])
            print(f"{'─'*60}")
    
    return result


def test_case_6_book_event():
    """Case 6: Book a meeting - successful end-to-end flow"""
    print("\n=== Case 6: Book Event (End-to-End) ===")
    
    # Use persistent test user
    test_agent_email = TEST_AGENT_EMAIL
    
    meeting_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    start_time = "10:00"
    end_time = "11:00"
    title = f"AI-Book-Test {uuid.uuid4().hex[:4]}"
    
    # Setup DynamoDB test data (already exists, but ensure it's correct)
    _setup_test_user(test_agent_email, TEST_USER_EMAIL, TEST_USER_ID)
    
    # Simulate a realistic email conversation where someone wants to book
    body = (
        f"@{test_agent_email} please book {meeting_date} {start_time}-{end_time} for '{title}'\n\n"
        f"On Tue, 8 Jul 2025 at 14:20, Mike Johnson <mike.johnson@startup.com> wrote:\n"
        f"> Hi Sourav,\n>\n"
        f"> Perfect! I'd like to book the {start_time} slot on {meeting_date} for '{title}'.\n"
        f"> Please go ahead and schedule it.\n>\n"
        f"> Thanks,\n"
        f"> Mike\n>\n"
        f"> On Tue, 8 Jul 2025 at 13:45, {test_agent_email} wrote:\n"
        f">> Hi Mike,\n>>\n"
        f">> Here are Sourav's available slots for {meeting_date}:\n>>\n"
        f">> - {meeting_date} 09:00-10:00\n"
        f">> - {meeting_date} 10:00-11:00\n"
        f">> - {meeting_date} 14:00-15:00\n"
        f">> - {meeting_date} 16:00-17:00\n>>\n"
        f">> Let me know which time works best for you!\n>>\n"
        f">> By VibeCal\n>\n"
        f"> On Tue, 8 Jul 2025 at 12:30, Mike Johnson <mike.johnson@startup.com> wrote:\n"
        f">> Hi Sourav,\n>>\n"
        f">> I'd like to schedule a meeting with you. Could you please share your\n"
        f">> availability for {meeting_date}?\n>>\n"
        f">> Best regards,\n"
        f">> Mike\n>\n"
        f"> On Tue, 8 Jul 2025 at 12:15, {TEST_USER_EMAIL} wrote:\n"
        f">> Hi Mike,\n>>\n"
        f">> I'll have my assistant check my calendar and share my availability.\n>>\n"
        f">> Thanks,\n"
        f">> Sourav"
    )
    
    parsed_email = _base_parsed_email(
        "Re: Meeting booking", 
        body,
        to=[TEST_USER_EMAIL, test_agent_email],  # Mike is emailing both Sourav and his agent
        from_email="mike.johnson@startup.com"
    )
    
    print(f"📅 Meeting date: {meeting_date}")
    print(f"⏰ Time: {start_time}-{end_time}")
    print(f"📝 Title: {title}")
    print(f"👤 User: {TEST_USER_EMAIL}")
    print(f"🤖 Agent: {test_agent_email}")
    print(f"📧 From: Mike Johnson (wanting to book)")
    
    print(f"\n📋 EXPECTED BEHAVIOR:")
    print(f"   • Agent should resolve calendar owner successfully")
    print(f"   • Should recognize Mike's request to book the {start_time} slot")
    print(f"   • Should create calendar event for {meeting_date} {start_time}-{end_time}")
    print(f"   • Response should confirm booking was successful")
    print(f"   • Response should include 'Event ID: [some-id]'")
    print(f"   • Response should end with 'By VibeCal'")
    
    result = process_booking_request(parsed_email, metadata={"test_case": "book_event"})
    print(f"\nResult: {result}")
    
    if result["action"] == "processed":
        print(f"✅ SUCCESS: End-to-end booking flow completed successfully")
        print(f"📧 AI Response:")
        print(f"{'─'*60}")
        print(result["ai_response"])
        print(f"{'─'*60}")
        
        # Extract event-id from the response
        match = re.search(r"Event ID:\s*([\w-]+)", result["ai_response"])
        if match:
            event_id = match.group(1)
            print(f"\n📋 VERIFICATION:")
            print(f"   • Action: {result['action']}")
            print(f"   • Calendar User ID: {result['calendar_user_id']}")
            print(f"   • Booking Email: {result['booking_email']}")
            print(f"   • Event ID: {event_id}")
            print(f"   • Response contains 'By VibeCal': {'By VibeCal' in result['ai_response']}")
            
            # Verify via Google Calendar API that the event exists
            calendar_assistant = CalendarAssistant(TEST_USER_ID)
            availability = calendar_assistant.get_availability(meeting_date, meeting_date)
            ids = {e["id"] for e in availability["events"]}
            if event_id in ids:
                print(f"   • Event verified in Google Calendar: ✅")
            else:
                print(f"   • Event NOT found in Google Calendar: ❌")
        else:
            print(f"   • Event ID not found in response: ❌")
    else:
        print(f"❌ FAILED: Expected processed, got {result.get('action')}")
        if result.get("clarification_message"):
            print(f"📧 Clarification message:")
            print(f"{'─'*60}")
            print(result["clarification_message"])
            print(f"{'─'*60}")
    
    return result


def test_case_7_cancel_event():
    """Case 7: Cancel a pre-existing event - successful end-to-end flow"""
    print("\n=== Case 7: Cancel Event (End-to-End) ===")
    
    # Use persistent test user
    test_agent_email = TEST_AGENT_EMAIL
    
    meeting_date = (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d")
    start_time = "14:00"
    end_time = "15:00"
    title = f"AI-Cancel-Test {uuid.uuid4().hex[:4]}"
    
    # Setup DynamoDB test data (already exists, but ensure it's correct)
    _setup_test_user(test_agent_email, TEST_USER_EMAIL, TEST_USER_ID)
    
    # First create an event directly via the high-level helper
    calendar_assistant = CalendarAssistant(TEST_USER_ID)
    seed_event = calendar_assistant.book_event(
        date=meeting_date,
        start_time=start_time,
        end_time=end_time,
        title=title,
        attendees=["lisa.chen@techcorp.com", TEST_USER_EMAIL],
    )
    event_id = seed_event["event_id"]
    print(f"Seeded calendar with event {event_id} to be cancelled.")
    
    # Simulate a realistic email conversation where someone wants to cancel
    body = (
        f"@{test_agent_email} please cancel the meeting with ID {event_id}\n\n"
        f"On Wed, 9 Jul 2025 at 16:30, Lisa Chen <lisa.chen@techcorp.com> wrote:\n"
        f"> Hi Sourav,\n>\n"
        f"> I'm sorry, but I need to reschedule our meeting. Can you please cancel\n"
        f"> the current booking? I'll reach out again to find a new time.\n>\n"
        f"> Thanks,\n"
        f"> Lisa\n>\n"
        f"> On Wed, 9 Jul 2025 at 15:00, {test_agent_email} wrote:\n"
        f">> Hi Lisa,\n>>\n"
        f">> I've successfully booked your meeting for {meeting_date} at {start_time}-{end_time}.\n"
        f">> Event ID: {event_id}\n>>\n"
        f">> Looking forward to our discussion!\n>>\n"
        f">> By VibeCal\n>\n"
        f"> On Wed, 9 Jul 2025 at 14:20, Lisa Chen <lisa.chen@techcorp.com> wrote:\n"
        f">> Hi Sourav,\n>>\n"
        f">> Perfect! I'd like to book the {start_time} slot on {meeting_date} for '{title}'.\n"
        f">> Please go ahead and schedule it.\n>>\n"
        f">> Thanks,\n"
        f">> Lisa\n>\n"
        f"> On Wed, 9 Jul 2025 at 13:45, {test_agent_email} wrote:\n"
        f">> Hi Lisa,\n>>\n"
        f">> Here are Sourav's available slots for {meeting_date}:\n>>\n"
        f">> - {meeting_date} 09:00-10:00\n"
        f">> - {meeting_date} 10:00-11:00\n"
        f">> - {meeting_date} 14:00-15:00\n"
        f">> - {meeting_date} 16:00-17:00\n>>\n"
        f">> Let me know which time works best for you!\n>>\n"
        f">> By VibeCal\n>\n"
        f"> On Wed, 9 Jul 2025 at 12:30, Lisa Chen <lisa.chen@techcorp.com> wrote:\n"
        f">> Hi Sourav,\n>>\n"
        f">> I'd like to schedule a meeting with you. Could you please share your\n"
        f">> availability for {meeting_date}?\n>>\n"
        f">> Best regards,\n"
        f">> Lisa\n>\n"
        f"> On Wed, 9 Jul 2025 at 12:15, {TEST_USER_EMAIL} wrote:\n"
        f">> Hi Lisa,\n>>\n"
        f">> I'll have my assistant check my calendar and share my availability.\n>>\n"
        f">> Thanks,\n"
        f">> Sourav"
    )
    
    parsed_email = _base_parsed_email(
        "Re: Meeting cancellation", 
        body,
        to=[TEST_USER_EMAIL, test_agent_email],  # Lisa is emailing both Sourav and his agent
        from_email="lisa.chen@techcorp.com"
    )
    
    print(f"📅 Meeting date: {meeting_date}")
    print(f"⏰ Time: {start_time}-{end_time}")
    print(f"📝 Title: {title}")
    print(f"🆔 Event ID: {event_id}")
    print(f"👤 User: {TEST_USER_EMAIL}")
    print(f"🤖 Agent: {test_agent_email}")
    print(f"📧 From: Lisa Chen (wanting to cancel)")
    
    print(f"\n📋 EXPECTED BEHAVIOR:")
    print(f"   • Agent should resolve calendar owner successfully")
    print(f"   • Should recognize Lisa's request to cancel the meeting")
    print(f"   • Should cancel calendar event with ID: {event_id}")
    print(f"   • Response should confirm cancellation was successful")
    print(f"   • Response should end with 'By VibeCal'")
    print(f"   • Event should no longer exist in Google Calendar")
    
    result = process_booking_request(parsed_email, metadata={"test_case": "cancel_event"})
    print(f"\nResult: {result}")
    
    if result["action"] == "processed":
        print(f"✅ SUCCESS: End-to-end cancellation flow completed successfully")
        print(f"📧 AI Response:")
        print(f"{'─'*60}")
        print(result["ai_response"])
        print(f"{'─'*60}")
        
        print(f"\n📋 VERIFICATION:")
        print(f"   • Action: {result['action']}")
        print(f"   • Calendar User ID: {result['calendar_user_id']}")
        print(f"   • Booking Email: {result['booking_email']}")
        print(f"   • Response contains 'By VibeCal': {'By VibeCal' in result['ai_response']}")
        
        # After agent cancels, verify the event exists but is cancelled
        try:
            event_data = calendar_assistant.get_event(event_id)
            if event_data.get('status') == 'cancelled':
                print(f"   • Event {event_id} successfully cancelled (status: cancelled): ✅")
            else:
                print(f"   • Event not cancelled, status: {event_data.get('status')}: ❌")
        except Exception as exc:
            if "not found" in str(exc).lower():
                print(f"   • Event {event_id} completely removed from calendar: ✅")
            else:
                print(f"   • Error checking event status: {exc}")
    else:
        print(f"❌ FAILED: Expected processed, got {result.get('action')}")
        if result.get("clarification_message"):
            print(f"📧 Clarification message:")
            print(f"{'─'*60}")
            print(result["clarification_message"])
            print(f"{'─'*60}")
    
    return result


def test_case_8_multiple_agents_llm_disambiguation():
    """Case 8: Multiple agents in conversation, LLM should disambiguate"""
    print("\n=== Case 8: Multiple agents, LLM disambiguation ===")
    
    # Create two new test agents and users (don't modify persistent test user)
    test_agent1_email = f"marketing-agent-{uuid.uuid4().hex[:8]}@bhaang.com"
    test_agent2_email = f"sales-agent-{uuid.uuid4().hex[:8]}@bhaang.com"
    test_user1_email = "marketing@example.com"  # Marketing team email
    test_user2_email = "sales@example.com"      # Sales team email
    
    # Setup DynamoDB test data
    table = boto3.resource('dynamodb').Table(os.getenv('USER_EMAILS_TABLE_NAME'))
    
    # Convert full emails to local parts for database storage
    from common_utils.email_helpers import to_local
    assist_local1 = to_local(test_agent1_email)
    assist_local2 = to_local(test_agent2_email)
    
    # Create two temporary test users
    test_user1_id = f"test-user-{uuid.uuid4().hex[:8]}"
    test_user2_id = f"test-user-{uuid.uuid4().hex[:8]}"
    
    test_item1 = {
        'pk': f"uid:{test_user1_id}",
        'sk': 'data',
        'user_id': test_user1_id,
        'assist_email': test_agent1_email,
        'assist_local': assist_local1,
        'user_email': test_user1_email,
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-15T10:00:00'
    }
    test_item2 = {
        'pk': f"uid:{test_user2_id}",
        'sk': 'data',
        'user_id': test_user2_id,
        'assist_email': test_agent2_email,
        'assist_local': assist_local2,
        'user_email': test_user2_email,
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-15T10:00:00'
    }
    
    try:
        # Insert test data
        table.put_item(Item=test_item1)
        table.put_item(Item=test_item2)
        print(f"✅ Updated test users: {TEST_USER_ID} ({test_agent1_email}), {test_user2_id} ({test_agent2_email})")
        
        # Synthetic email data with two agents and clear context
        body = (
            f"@{test_agent1_email} please share our marketing team availability for next week!\n\n"
            f"On Mon, 7 Jul 2025 at 10:15, Client <client@example.com> wrote:\n"
            f"> Hi Marketing Team,\n>\n"
            f"> I need to schedule a meeting with the marketing team to discuss our upcoming campaign.\n"
            f"> We need to go over the budget, timeline, and creative direction.\n>\n"
            f"> Can you help me find a time that works for everyone?\n>\n"
            f"> Best regards,\n"
            f"> Client\n>\n"
            f"> On Mon, 7 Jul 2025 at 09:30, {test_agent1_email} wrote:\n"
            f">> Hi Client,\n>>\n"
            f">> I'll check the marketing team's calendar and get back to you.\n>>\n"
            f">> By VibeCal\n>\n"
            f"> On Mon, 7 Jul 2025 at 09:15, {test_user1_email} wrote:\n"
            f">> Hi Client,\n>>\n"
            f">> I'll have our marketing assistant check our availability.\n>>\n"
            f">> Thanks,\n"
            f">> Marketing Team"
        )
        
        parsed_email = _base_parsed_email(
            "Re: Marketing Campaign Meeting", 
            body,
            to=[test_agent1_email, test_agent2_email],
            cc=["client@example.com", test_user1_email, test_user2_email],  # Both users in conversation
            from_email=test_user1_email
        )
        
        print(f"Email: {parsed_email['subject']}")
        print(f"From: {parsed_email['from']}")
        print(f"To: {parsed_email['to']}")
        print(f"CC: {parsed_email['cc']}")
        print(f"Body preview: {parsed_email['body'][:100]}...")
        
        print(f"\n📋 EXPECTED BEHAVIOR:")
        print(f"   • Agent should detect multiple booking agents: {test_agent1_email}, {test_agent2_email}")
        print(f"   • Should find both mappings in DynamoDB")
        print(f"   • Should detect both users in conversation")
        print(f"   • Should use LLM to disambiguate based on email content")
        print(f"   • Should either succeed or return clarification_needed")
        
        result = process_booking_request(parsed_email, metadata={"test_case": "multiple_agents_llm_disambiguation"})
        print(f"\nResult: {result}")
        
        if result["action"] == "processed":
            print(f"✅ SUCCESS: LLM successfully disambiguated and processed request")
            print(f"📧 AI Response:")
            print(f"{'─'*60}")
            print(result["ai_response"])
            print(f"{'─'*60}")
            print(f"\n📋 VERIFICATION:")
            print(f"   • Action: {result['action']}")
            print(f"   • Calendar User ID: {result['calendar_user_id']}")
            print(f"   • Booking Email: {result['booking_email']}")
            print(f"   • Response contains 'By VibeCal': {'By VibeCal' in result['ai_response']}")
        elif result["action"] == "clarification_needed" and result["status"] == "multiple_owners_ambiguous":
            print(f"⚠️  PARTIAL: LLM couldn't decide between multiple agents")
            print(f"📧 Clarification message:")
            print(f"{'─'*60}")
            print(result["clarification_message"])
            print(f"{'─'*60}")
            print(f"Reason: {result.get('reason', 'No reason provided')}")
        else:
            print(f"❌ FAILED: Unexpected result: {result.get('action')} - {result.get('status')}")
        
        return result
        
    finally:
        # Cleanup both temporary test users
        table.delete_item(Key={'pk': f"uid:{test_user1_id}", 'sk': 'data'})
        table.delete_item(Key={'pk': f"uid:{test_user2_id}", 'sk': 'data'})
        print(f"🧹 Cleaned up temporary test users: {test_user1_id}, {test_user2_id}")


# ---------------------------------------------------------------------------
# Test runner functions ------------------------------------------------------
# ---------------------------------------------------------------------------

def test_all_calendar_owner_failures():
    """Test all deterministic calendar owner resolution failure cases"""
    print("Running all calendar owner resolution failure tests...")
    print("These tests are deterministic and should always fail with clarification_needed.")
    print()
    
    test_case_1_no_booking_agents_found()
    test_case_2_booking_agent_not_registered()
    test_case_3_calendar_owner_not_in_conversation()
    test_case_4_missing_user_email_field()
    
    print("\n✅ All calendar owner resolution failure tests completed!")


def test_all_end_to_end_success():
    """Test all end-to-end successful flows"""
    print("Running all end-to-end success flow tests...")
    print("These tests require real Google Calendar access and may create/cancel events.")
    print()
    
    test_case_5_share_availability()
    test_case_6_book_event()
    test_case_7_cancel_event()
    test_case_8_multiple_agents_llm_disambiguation()
    
    print("\n✅ All end-to-end success flow tests completed!")


# ---------------------------------------------------------------------------
# Allow execution via `python -m booking_agent.test_agent_integration`
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running agent integration tests...")
    print("These tests use real AWS services and Google Calendar - ensure you have proper credentials configured.")
    print()
    
    # Run all tests
    test_all_calendar_owner_failures()
    print("\n" + "="*80 + "\n")
    test_all_end_to_end_success()
    
    print("\n✅ All agent integration tests completed!") 