import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any

import logging

from dotenv import load_dotenv

# Reduce logging noise from external libraries during test runs
logging.basicConfig(level=logging.WARNING)
logging.getLogger("booking_agent").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Environment preparation ---------------------------------------------------
# ---------------------------------------------------------------------------

# The tests live under src/ and are executed with `cd src && python ...` from
# the Makefile targets.  We therefore load env files relative to project root.
load_dotenv("../.env.base", override=True)
load_dotenv("../.env.dev", override=True)

# Persistent test user - DO NOT DELETE, this is used in production
TEST_USER_ID = "user_2zTBVQZOK5QCyxL43QTVOHOw3zK"
TEST_USER_EMAIL = "souravsarkar1729@gmail.com"
TEST_AGENT_EMAIL = "test.dev@bhaang.com"  # Development agent email

# The booking-agent e-mail we are testing with.
BOOKING_EMAIL = TEST_AGENT_EMAIL  # Use the persistent agent email
# No need to set environment variable - booking_email is passed as parameter

# Clerk / Google tokens & other secrets are expected to be present in the
# .env files pulled in above (or via AWS secrets manager inside code).

# DynamoDB user record – create once; user said it is fine to leave it behind.
os.environ.setdefault("USER_EMAILS_TABLE_NAME", "vibes-user-emails-dev")

from booking_agent.agent_executor import run_booking_agent
from calendar_utils.calendar_tools import CalendarAssistant

# ---------------------------------------------------------------------------
# Helper utilities ----------------------------------------------------------
# ---------------------------------------------------------------------------

def _base_parsed_email(subject: str, body: str, to: list = None, cc: list = None) -> Dict[str, Any]:
    """Generate a minimal parsed_email dict for the test cases."""
    return {
        "subject": subject,
        "from": [TEST_USER_EMAIL],  # User is in the thread
        "to": to or [BOOKING_EMAIL],
        "cc": cc or [],
        "body": body,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "message_id": f"test-{uuid.uuid4().hex[:8]}",
    }


# ---------------------------------------------------------------------------
# Test cases ----------------------------------------------------------------
# ---------------------------------------------------------------------------

def test_case_1_share_availability() -> str:
    """Case 1 – User asks for availability for the coming week."""
    start = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print("🧪 TEST CASE 1: Share Availability")
    print(f"{'='*60}")
    print(f"📅 Requesting availability for: {start} to {end}")
    print(f"👤 User: {TEST_USER_EMAIL}")
    print(f"🤖 Agent: {BOOKING_EMAIL}")
    print(f"📧 Recipients: John Doe + Agent")
    print(f"\n📋 EXPECTED BEHAVIOR:")
    print(f"   • Agent should check calendar for {start} to {end}")
    print(f"   • Response should contain available time slots")
    print(f"   • Response should end with 'By VibeCal'")
    print(f"   • Response should be sent to John Doe")
    print(f"{'='*60}")

    # Simulate a realistic email conversation where someone asks for availability
    # and the user (TEST_USER_EMAIL) asks their agent to share slots
    body = (
        f"@{BOOKING_EMAIL} please share my availability for {start} to {end}!\n\n"
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
    # In a realistic scenario, the user would include both the booking agent and John in the email
    parsed_email = _base_parsed_email(
        "Re: Meeting request", 
        body,
        to=[BOOKING_EMAIL, "john.doe@example.com"]  # Both booking agent and John
    )

    response = run_booking_agent(
        parsed_email=parsed_email,
        calendar_user_id=TEST_USER_ID,
        booking_email=BOOKING_EMAIL,
    )

    print(f"\n📧 ACTUAL AGENT RESPONSE:")
    print(f"{'─'*60}")
    print(response)
    print(f"{'─'*60}")
    print(f"\n📋 EXPECTED RESPONSE FORMAT:")
    print(f"   • Should start with greeting (Hi John)")
    print(f"   • Should mention checking calendar for {start} to {end}")
    print(f"   • Should list available time slots")
    print(f"   • Should end with 'By VibeCal'")
    print(f"   • Should be professional and helpful tone")


    return response


def test_case_2_share_availability_other_range() -> str:
    """Case 2 – Ask for a *different* date range after agent has already shared some availability."""
    start = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=16)).strftime("%Y-%m-%d")
    
    # Previous date range that was already shared
    prev_start = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    prev_end = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print("🧪 TEST CASE 2: Share Availability - Different Range")
    print(f"{'='*60}")
    print(f"📅 Previously shared: {prev_start} to {prev_end}")
    print(f"📅 Now requesting: {start} to {end}")
    print(f"👤 User: {TEST_USER_EMAIL}")
    print(f"🤖 Agent: {BOOKING_EMAIL}")
    print(f"📧 From: John Doe (asking for different dates)")
    print(f"\n📋 EXPECTED BEHAVIOR:")
    print(f"   • Agent should recognize this is a follow-up request")
    print(f"   • Agent should check calendar for NEW range: {start} to {end}")
    print(f"   • Response should acknowledge previous availability didn't work")
    print(f"   • Response should contain new available time slots")
    print(f"   • Response should end with 'By VibeCal'")
    print(f"{'='*60}")

    body = (
        f"@{BOOKING_EMAIL} can you check my calendar for {start} to {end}?\n\n"
        f"On Mon, 7 Jul 2025 at 10:15, John Doe <john.doe@example.com> wrote:\n"
        f"> Hi Sourav,\n>\n"
        f"> Thanks for sharing your availability for {prev_start} to {prev_end}. Those times\n"
        f"> don't work for me. Could you please check your calendar for {start} to {end}?\n>\n"
        f"> Best regards,\n"
        f"> John\n>\n"
        f"> On Mon, 7 Jul 2025 at 09:30, {BOOKING_EMAIL} wrote:\n"
        f">> Hi John,\n>>\n"
        f">> Here are Sourav's available slots for {prev_start} to {prev_end}:\n>>\n"
        f">> - {prev_start} 10:00-11:00\n"
        f">> - {prev_start} 14:00-15:00\n"
        f">> - {prev_end} 09:00-10:00\n"
        f">> - {prev_end} 16:00-17:00\n>>\n"
        f">> Let me know which time works best for you!\n>>\n"
        f">> By VibeCal\n>\n"
        f"> On Mon, 7 Jul 2025 at 08:45, {TEST_USER_EMAIL} wrote:\n"
        f">> Hi John,\n>>\n"
        f">> I'll have my assistant check my calendar and share my availability.\n>>\n"
        f">> Thanks,\n"
        f">> Sourav"
    )
    # In this case, John is asking for availability, so the email is from John to Sourav and his agent
    parsed_email = _base_parsed_email(
        "Re: Meeting scheduling", 
        body,
        to=[TEST_USER_EMAIL, BOOKING_EMAIL],  # John is emailing both Sourav and his agent
        cc=[]
    )
    # Override the from field since John is the sender, not Sourav
    parsed_email["from"] = ["john.doe@example.com"]

    response = run_booking_agent(
        parsed_email=parsed_email,
        calendar_user_id=TEST_USER_ID,
        booking_email=BOOKING_EMAIL,
    )

    print(f"\n📧 ACTUAL AGENT RESPONSE:")
    print(f"{'─'*60}")
    print(response)
    print(f"{'─'*60}")
    print(f"\n📋 EXPECTED RESPONSE FORMAT:")
    print(f"   • Should acknowledge previous availability didn't work")
    print(f"   • Should mention checking NEW calendar range: {start} to {end}")
    print(f"   • Should list available time slots for the new dates")
    print(f"   • Should end with 'By VibeCal'")
    print(f"   • Should be professional and understanding tone")

    assert "By VibeCal" in response
    return response


def test_case_3_book_event() -> str:
    """Case 3 – Book a meeting and verify the event exists."""
    meeting_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    start_time = "10:00"
    end_time = "11:00"
    title = f"AI-Book-Test {uuid.uuid4().hex[:4]}"

    print(f"\n{'='*60}")
    print("🧪 TEST CASE 3: Book Event")
    print(f"{'='*60}")
    print(f"📅 Meeting date: {meeting_date}")
    print(f"⏰ Time: {start_time}-{end_time}")
    print(f"📝 Title: {title}")
    print(f"👤 User: {TEST_USER_EMAIL}")
    print(f"🤖 Agent: {BOOKING_EMAIL}")
    print(f"📧 From: Mike Johnson (wanting to book)")
    print(f"\n📋 EXPECTED BEHAVIOR:")
    print(f"   • Agent should recognize Mike's request to book the {start_time} slot")
    print(f"   • Agent should create calendar event for {meeting_date} {start_time}-{end_time}")
    print(f"   • Response should confirm booking was successful")
    print(f"   • Response should include 'Event ID: [some-id]'")
    print(f"   • Response should end with 'By VibeCal'")
    print(f"   • Event should actually exist in Google Calendar")
    print(f"{'='*60}")

    body = (
        f"@{BOOKING_EMAIL} please book {meeting_date} {start_time}-{end_time} for '{title}'\n\n"
        f"On Tue, 8 Jul 2025 at 14:20, Mike Johnson <mike.johnson@startup.com> wrote:\n"
        f"> Hi Sourav,\n>\n"
        f"> Perfect! I'd like to book the {start_time} slot on {meeting_date} for '{title}'.\n"
        f"> Please go ahead and schedule it.\n>\n"
        f"> Thanks,\n"
        f"> Mike\n>\n"
        f"> On Tue, 8 Jul 2025 at 13:45, {BOOKING_EMAIL} wrote:\n"
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
    # In this case, Mike is asking to book a slot, so the email is from Mike to Sourav and his agent
    parsed_email = _base_parsed_email(
        "Re: Meeting booking", 
        body,
        to=[TEST_USER_EMAIL, BOOKING_EMAIL],  # Mike is emailing both Sourav and his agent
        cc=[]
    )
    # Override the from field since Mike is the sender, not Sourav
    parsed_email["from"] = ["mike.johnson@startup.com"]

    response = run_booking_agent(
        parsed_email=parsed_email,
        calendar_user_id=TEST_USER_ID,
        booking_email=BOOKING_EMAIL,
    )

    print(f"\n📧 ACTUAL AGENT RESPONSE:")
    print(f"{'─'*60}")
    print(response)
    print(f"{'─'*60}")
    print(f"\n📋 EXPECTED RESPONSE FORMAT:")
    print(f"   • Should confirm booking was successful")
    print(f"   • Should include 'Event ID: [some-id]'")
    print(f"   • Should mention the meeting details: {title} on {meeting_date} at {start_time}-{end_time}")
    print(f"   • Should end with 'By VibeCal'")
    print(f"   • Should be professional and confirmatory tone")
    print(f"\n⏰ EXPECTED BOOKING TIME: {meeting_date} {start_time}-{end_time}")

    # Extract event-id from the response – per system-prompt the agent should
    # include a line like "Event ID: abc123" after successful booking.
    match = re.search(r"Event ID:\s*([\w-]+)", response)
    assert match, "Agent response did not contain an Event ID"
    event_id = match.group(1)

    # Verify via Google Calendar API that the event exists using high-level function
    calendar_assistant = CalendarAssistant(TEST_USER_ID)
    availability = calendar_assistant.get_availability(meeting_date, meeting_date)
    ids = {e["id"] for e in availability["events"]}
    assert event_id in ids, "Booked event not found in Google Calendar"

    return event_id  # For potential manual inspection


def test_case_4_cancel_event() -> str:
    """Case 4 – Cancel a pre-existing event."""
    # First create an event directly via the high-level helper
    meeting_date = (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d")
    start_time = "14:00"
    end_time = "15:00"
    title = f"AI-Cancel-Test {uuid.uuid4().hex[:4]}"

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

    print(f"\n{'='*60}")
    print("🧪 TEST CASE 4: Cancel Event")
    print(f"{'='*60}")
    print(f"📅 Meeting date: {meeting_date}")
    print(f"⏰ Time: {start_time}-{end_time}")
    print(f"📝 Title: {title}")
    print(f"🆔 Event ID: {event_id}")
    print(f"👤 User: {TEST_USER_EMAIL}")
    print(f"🤖 Agent: {BOOKING_EMAIL}")
    print(f"📧 From: Lisa Chen (wanting to cancel)")
    print(f"\n📋 EXPECTED BEHAVIOR:")
    print(f"   • Agent should recognize Lisa's request to cancel the meeting")
    print(f"   • Agent should cancel calendar event with ID: {event_id}")
    print(f"   • Response should confirm cancellation was successful")
    print(f"   • Response should end with 'By VibeCal'")
    print(f"   • Event should no longer exist in Google Calendar")
    print(f"{'='*60}")

    # Compose e-mail asking the agent to cancel the event
    body = (
        f"@{BOOKING_EMAIL} please cancel the meeting with ID {event_id}\n\n"
        f"On Wed, 9 Jul 2025 at 16:30, Lisa Chen <lisa.chen@techcorp.com> wrote:\n"
        f"> Hi Sourav,\n>\n"
        f"> I'm sorry, but I need to reschedule our meeting. Can you please cancel\n"
        f"> the current booking? I'll reach out again to find a new time.\n>\n"
        f"> Thanks,\n"
        f"> Lisa\n>\n"
        f"> On Wed, 9 Jul 2025 at 15:00, {BOOKING_EMAIL} wrote:\n"
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
        f"> On Wed, 9 Jul 2025 at 13:45, {BOOKING_EMAIL} wrote:\n"
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
    # In this case, Lisa is asking to cancel a slot, so the email is from Lisa to Sourav and his agent
    parsed_email = _base_parsed_email(
        "Re: Meeting cancellation", 
        body,
        to=[TEST_USER_EMAIL, BOOKING_EMAIL],  # Lisa is emailing both Sourav and his agent
        cc=[]
    )
    # Override the from field since Lisa is the sender, not Sourav
    parsed_email["from"] = ["lisa.chen@techcorp.com"]

    response = run_booking_agent(
        parsed_email=parsed_email,
        calendar_user_id=TEST_USER_ID,
        booking_email=BOOKING_EMAIL,
    )

    print(f"\n📧 ACTUAL AGENT RESPONSE:")
    print(f"{'─'*60}")
    print(response)
    print(f"{'─'*60}")
    print(f"\n📋 EXPECTED RESPONSE FORMAT:")
    print(f"   • Should confirm cancellation was successful")
    print(f"   • Should mention the event ID: {event_id}")
    print(f"   • Should end with 'By VibeCal'")
    print(f"   • Should be professional and understanding tone")
    print(f"\n⏰ EXPECTED CANCELLATION: Event ID {event_id} should be cancelled")
    print(f"📅 MANUAL VERIFICATION: Check Google Calendar for date {meeting_date}")
    print(f"   • Look for event: '{title}'")
    print(f"   • Event ID: {event_id}")
    print(f"   • Expected status: 'cancelled' (not deleted)")

    # After agent cancels, verify the event exists but is cancelled
    try:
        event_data = calendar_assistant.get_event(event_id)
        # Check if the event status is 'cancelled'
        assert event_data.get('status') == 'cancelled', f"Event not cancelled, status: {event_data.get('status')}"
        print(f"✅ VERIFICATION: Event {event_id} successfully cancelled (status: cancelled)")
    except Exception as exc:
        if "not found" in str(exc).lower():
            print(f"✅ VERIFICATION: Event {event_id} completely removed from calendar")
        else:
            raise exc

    return event_id


# ---------------------------------------------------------------------------
# Thread ID Tests -----------------------------------------------------------
# ---------------------------------------------------------------------------

def test_thread_id_usage():
    """Test that thread_id is properly used for Langfuse session grouping."""
    from unittest.mock import Mock, patch
    
    print(f"\n{'='*60}")
    print("🧪 TEST: Thread ID Usage for Langfuse Session Grouping")
    print(f"{'='*60}")
    
    # Test with existing thread_id
    metadata_with_thread = {
        "thread_id": "test-thread-123",
        "subject": "Test Email",
        "message_id": "test-message-456"
    }
    
    print(f"📧 Testing with existing thread_id: {metadata_with_thread['thread_id']}")
    
    # Create a simple test email
    parsed_email = _base_parsed_email(
        "Test Thread ID",
        "This is a test email for thread ID functionality.",
        to=[BOOKING_EMAIL]
    )
    
    # Mock the OpenAI client to capture metadata
    with patch('booking_agent.agent_executor.OpenAI') as mock_openai_class:
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        
        # Mock the response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.tool_calls = None
        mock_client.chat.completions.create.return_value = mock_response
        
        # Run the booking agent
        response = run_booking_agent(
            parsed_email=parsed_email,
            calendar_user_id=TEST_USER_ID,
            booking_email=BOOKING_EMAIL,
            metadata=metadata_with_thread
        )
        
        # Verify that langfuse_session_id was set correctly
        call_args = mock_client.chat.completions.create.call_args
        call_metadata = call_args[1]['metadata']
        
        assert call_metadata['langfuse_session_id'] == "test-thread-123", f"Expected langfuse_session_id to be 'test-thread-123', got {call_metadata.get('langfuse_session_id')}"
        assert call_metadata['thread_id'] == "test-thread-123", f"Expected thread_id to be 'test-thread-123', got {call_metadata.get('thread_id')}"
        
        print(f"✅ Thread ID properly used as langfuse_session_id")
        print(f"✅ Metadata contains: {call_metadata}")


def test_thread_id_generation():
    """Test that a new thread_id is generated when not provided."""
    from unittest.mock import Mock, patch
    import uuid
    
    print(f"\n{'='*60}")
    print("🧪 TEST: Thread ID Generation When Missing")
    print(f"{'='*60}")
    
    # Test without thread_id in metadata
    metadata_without_thread = {
        "subject": "Test Email",
        "message_id": "test-message-789"
    }
    
    print(f"📧 Testing without thread_id in metadata")
    
    # Create a simple test email
    parsed_email = _base_parsed_email(
        "Test Thread ID Generation",
        "This is a test email for thread ID generation.",
        to=[BOOKING_EMAIL]
    )
    
    # Mock the OpenAI client to capture metadata
    with patch('booking_agent.agent_executor.OpenAI') as mock_openai_class:
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        
        # Mock the response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.tool_calls = None
        mock_client.chat.completions.create.return_value = mock_response
        
        # Run the booking agent
        response = run_booking_agent(
            parsed_email=parsed_email,
            calendar_user_id=TEST_USER_ID,
            booking_email=BOOKING_EMAIL,
            metadata=metadata_without_thread
        )
        
        # Verify that a new thread_id was generated and used
        call_args = mock_client.chat.completions.create.call_args
        call_metadata = call_args[1]['metadata']
        
        assert 'langfuse_session_id' in call_metadata, "Expected langfuse_session_id to be present in metadata"
        assert call_metadata['langfuse_session_id'] is not None, "Expected langfuse_session_id to not be None"
        assert len(call_metadata['langfuse_session_id']) > 0, "Expected langfuse_session_id to be a non-empty string"
        
        # Verify it's a valid UUID format
        try:
            uuid.UUID(call_metadata['langfuse_session_id'])
            print(f"✅ Generated valid UUID thread_id: {call_metadata['langfuse_session_id']}")
        except ValueError:
            print(f"❌ Generated thread_id is not a valid UUID: {call_metadata['langfuse_session_id']}")
            raise
        
        print(f"✅ Thread ID generation working correctly")
        print(f"✅ Metadata contains: {call_metadata}")


# ---------------------------------------------------------------------------
# Allow execution via `python -m booking_agent.test_agent_executor_integration`
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running agent-executor integration tests…\n")

    test_case_1_share_availability()
    test_case_2_share_availability_other_range()
    test_id = test_case_3_book_event()
    print(f"Booked event id: {test_id}")
    cancel_id = test_case_4_cancel_event()
    print(f"Cancelled event id: {cancel_id}")
    
    # Run thread ID tests
    test_thread_id_usage()
    test_thread_id_generation()

    print("\n✅ All agent-executor tests completed!") 