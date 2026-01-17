"""
Integration tests for the booking agent executor.

These tests use real services (AWS, Google Calendar) and should be run
with proper environment variables and credentials configured.
"""
import os
import re
import uuid
import pytest
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

# Reduce logging noise from external libraries during test runs
logging.basicConfig(level=logging.WARNING)
logging.getLogger("booking_agent").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.ERROR)
logging.getLogger("boto3").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

# Persistent test user - DO NOT DELETE, this is used in production
TEST_USER_ID = "user_2zTBVQZOK5QCyxL43QTVOHOw3zK"
TEST_USER_EMAIL = "souravsarkar1729@gmail.com"
TEST_AGENT_EMAIL = "test.dev@bhaang.com"  # Development agent email

# The booking-agent e-mail we are testing with.
BOOKING_EMAIL = TEST_AGENT_EMAIL  # Use the persistent agent email

from booking_agent.agent_executor import run_booking_agent
from calendar_utils.calendar_tools import CalendarAssistant


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


def _evaluate_agent_response_with_llm(request_description: str, agent_response: str, test_type: str = "general") -> None:
    """
    Use LLM to evaluate if the agent response is appropriate for the given request.
    
    Args:
        request_description: Description of what the user requested
        agent_response: The agent's response to evaluate
        test_type: Type of test for more specific evaluation criteria
    """
    # Define evaluation criteria based on test type
    criteria_map = {
        "general": [
            "It provides a clear and appropriate response to the request, OR",
            "It explains why the request cannot be fulfilled, OR",
            "It offers helpful alternatives or next steps"
        ],
        "availability": [
            "It shows available time slots for the requested date range, OR",
            "It clearly indicates that no slots are available for the requested dates, OR",
            "It provides a clear explanation of why availability cannot be shown"
        ],
        "booking": [
            "It confirms the booking was successful, OR",
            "It clearly explains why the booking failed (e.g., slot not available), OR",
            "It provides a clear explanation of what went wrong"
        ],
        "cancellation": [
            "It confirms the cancellation was successful, OR",
            "It clearly explains why the cancellation failed, OR",
            "It provides a clear explanation of what went wrong"
        ],
        "conflict": [
            "It clearly explains that the requested time slot is not available due to a conflict, OR",
            "It offers alternative available time slots, OR",
            "It provides a clear explanation of why the booking cannot proceed"
        ]
    }
    
    criteria = criteria_map.get(test_type, criteria_map["general"])
    criteria_text = "\n".join(f"    {i+1}. {criterion}" for i, criterion in enumerate(criteria))
    
    evaluation_prompt = f"""
    Evaluate if this agent response is appropriate for the request.

    REQUEST: {request_description}
    AGENT RESPONSE: {agent_response}

    The response should be considered appropriate if:
{criteria_text}

    Respond with only "APPROPRIATE" or "INAPPROPRIATE" and a brief reason.
    """

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        evaluation_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a test evaluator. Respond with only APPROPRIATE or INAPPROPRIATE followed by a brief reason."},
                {"role": "user", "content": evaluation_prompt}
            ],
            max_tokens=100
        )
        
        evaluation = evaluation_response.choices[0].message.content.strip()
        print(f"\n🤖 LLM EVALUATION: {evaluation}")
        
        assert evaluation.startswith("APPROPRIATE"), f"Agent response was evaluated as inappropriate: {evaluation}"
        
    except Exception as e:
        print(f"⚠️  LLM evaluation failed: {e}")
        # Fallback to basic checks
        assert "By VibeCal" in agent_response, "Response should end with 'By VibeCal'"
        assert len(agent_response) > 50, "Response should be substantial"


@pytest.mark.integration
def test_share_availability():
    """Test sharing availability for the coming week."""
    start = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print("🧪 TEST: Share Availability")
    print(f"{'='*60}")
    print(f"📅 Requesting availability for: {start} to {end}")
    print(f"👤 User: {TEST_USER_EMAIL}")
    print(f"🤖 Agent: {BOOKING_EMAIL}")
    print(f"📧 Recipients: John Doe + Agent")
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

    # Use LLM to evaluate if the response is appropriate
    _evaluate_agent_response_with_llm(
        request_description=f"User asked for availability for {start} to {end}",
        agent_response=response,
        test_type="availability"
    )


@pytest.mark.integration
def test_share_availability_other_range():
    """Test sharing availability for a different date range after agent has already shared some availability."""
    start = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=16)).strftime("%Y-%m-%d")
    
    # Previous date range that was already shared
    prev_start = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    prev_end = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print("🧪 TEST: Share Availability - Different Range")
    print(f"{'='*60}")
    print(f"📅 Previously shared: {prev_start} to {prev_end}")
    print(f"📅 Now requesting: {start} to {end}")
    print(f"👤 User: {TEST_USER_EMAIL}")
    print(f"🤖 Agent: {BOOKING_EMAIL}")
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

    # Use LLM to evaluate if the response is appropriate
    _evaluate_agent_response_with_llm(
        request_description=f"User asked for availability for {start} to {end} (different range from previous)",
        agent_response=response,
        test_type="availability"
    )


@pytest.mark.integration
def test_book_event():
    """Test booking a meeting and verify the event exists."""
    meeting_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    start_time = "10:00"
    end_time = "11:00"
    title = f"AI-Book-Test {uuid.uuid4().hex[:4]}"

    print(f"\n{'='*60}")
    print("🧪 TEST: Book Event")
    print(f"{'='*60}")
    print(f"📅 Meeting date: {meeting_date}")
    print(f"⏰ Time: {start_time}-{end_time}")
    print(f"📝 Title: {title}")
    print(f"👤 User: {TEST_USER_EMAIL}")
    print(f"🤖 Agent: {BOOKING_EMAIL}")
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

    # Use LLM to evaluate if the response is appropriate
    _evaluate_agent_response_with_llm(
        request_description=f"User asked to book {meeting_date} {start_time}-{end_time} for '{title}'",
        agent_response=response,
        test_type="booking"
    )
    
    # If LLM evaluation passes, also verify the event was actually created
    match = re.search(r"Event ID:\s*([\w-]+)", response)
    if match:
        event_id = match.group(1)
        # Verify via Google Calendar API that the event exists
        calendar_assistant = CalendarAssistant(TEST_USER_ID)
        availability = calendar_assistant.get_availability(meeting_date, meeting_date)
        ids = {e["id"] for e in availability["events"]}
        assert event_id in ids, "Booked event not found in Google Calendar"
        print(f"✅ Event {event_id} successfully created and verified")
        return event_id


@pytest.mark.integration
def test_cancel_event():
    """Test cancelling a pre-existing event."""
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
    print("🧪 TEST: Cancel Event")
    print(f"{'='*60}")
    print(f"📅 Meeting date: {meeting_date}")
    print(f"⏰ Time: {start_time}-{end_time}")
    print(f"📝 Title: {title}")
    print(f"🆔 Event ID: {event_id}")
    print(f"👤 User: {TEST_USER_EMAIL}")
    print(f"🤖 Agent: {BOOKING_EMAIL}")
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
        f">> Please go ahead and schedule it.\n>\n"
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

    # Use LLM to evaluate if the response is appropriate
    _evaluate_agent_response_with_llm(
        request_description=f"User asked to cancel event with ID {event_id}",
        agent_response=response,
        test_type="cancellation"
    )
    
    # If LLM evaluation passes, also verify the event was actually cancelled
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


@pytest.mark.integration
def test_slot_conflict_handling():
    """Test slot conflict handling when user tries to book an occupied time."""
    meeting_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
    start_time = "16:00"  # Use a time that's likely to be available
    end_time = "17:00"
    conflicting_title = f"AI-Conflict-Test {uuid.uuid4().hex[:4]}"
    
    # First, create a conflicting event directly via the calendar assistant
    calendar_assistant = CalendarAssistant(TEST_USER_ID)
    conflicting_event = calendar_assistant.book_event(
        date=meeting_date,
        start_time=start_time,
        end_time=end_time,
        title=conflicting_title,
        attendees=[TEST_USER_EMAIL],
    )
    
    # Handle the case where booking fails due to conflict
    if conflicting_event.get('error') == 'slot_not_available':
        # There's already a conflict, get the event ID from availability data
        availability = calendar_assistant.get_availability(meeting_date, meeting_date)
        for event in availability.get('events', []):
            event_start = event.get('start')
            event_end = event.get('end')
            
            # Handle both string and dict formats
            if isinstance(event_start, str):
                event_start_str = event_start
            elif isinstance(event_start, dict):
                event_start_str = event_start.get('dateTime', '')
            else:
                event_start_str = ''
                
            if isinstance(event_end, str):
                event_end_str = event_end
            elif isinstance(event_end, dict):
                event_end_str = event_end.get('dateTime', '')
            else:
                event_end_str = ''
            
            # Check if this event overlaps with our target time
            if event_start_str and event_end_str:
                if (f"{meeting_date}T{start_time}:00" < event_end_str and 
                    f"{meeting_date}T{end_time}:00" > event_start_str):
                    conflicting_event_id = event.get('id')
                    conflicting_title = event.get('title', event.get('summary', 'Unknown Event'))
                    break
        else:
            conflicting_event_id = 'unknown'
            conflicting_title = 'Unknown Event'
        print(f"Using existing conflicting event at {meeting_date} {start_time}-{end_time}")
    else:
        conflicting_event_id = conflicting_event["event_id"]
        print(f"Created conflicting event {conflicting_event_id} at {meeting_date} {start_time}-{end_time}")

    print(f"\n{'='*60}")
    print("🧪 TEST: Slot Conflict Handling")
    print(f"{'='*60}")
    print(f"📅 Meeting date: {meeting_date}")
    print(f"⏰ Conflicting time: {start_time}-{end_time}")
    print(f"📝 Conflicting title: {conflicting_title}")
    print(f"🆔 Conflicting Event ID: {conflicting_event_id}")
    print(f"👤 User: {TEST_USER_EMAIL}")
    print(f"🤖 Agent: {BOOKING_EMAIL}")
    print(f"{'='*60}")

    # Compose email asking the agent to book the conflicting slot
    body = (
        f"@{BOOKING_EMAIL} please book {meeting_date} {start_time}-{end_time} for 'Project Discussion'\n\n"
        f"On Thu, 10 Jul 2025 at 11:30, Sarah Wilson <sarah.wilson@company.com> wrote:\n"
        f"> Hi Sourav,\n>\n"
        f"> I'd like to schedule a project discussion meeting for {meeting_date} at {start_time}-{end_time}.\n"
        f"> Please go ahead and book that time slot.\n>\n"
        f"> Thanks,\n"
        f"> Sarah\n>\n"
        f"> On Thu, 10 Jul 2025 at 10:45, {BOOKING_EMAIL} wrote:\n"
        f">> Hi Sarah,\n>>\n"
        f">> Here are Sourav's available slots for {meeting_date}:\n>>\n"
        f">> - {meeting_date} 09:00-10:00\n"
        f">> - {meeting_date} 10:00-11:00\n"
        f">> - {meeting_date} 14:00-15:00\n"
        f">> - {meeting_date} 16:00-17:00\n>>\n"
        f">> Let me know which time works best for you!\n>>\n"
        f">> By VibeCal\n>\n"
        f"> On Thu, 10 Jul 2025 at 10:20, Sarah Wilson <sarah.wilson@company.com> wrote:\n"
        f">> Hi Sourav,\n>>\n"
        f">> I need to schedule a project discussion meeting. Could you please share your\n"
        f">> availability for {meeting_date}?\n>>\n"
        f">> Best regards,\n"
        f">> Sarah\n>\n"
        f"> On Thu, 10 Jul 2025 at 10:15, {TEST_USER_EMAIL} wrote:\n"
        f">> Hi Sarah,\n>>\n"
        f">> I'll have my assistant check my calendar and share my availability.\n>>\n"
        f">> Thanks,\n"
        f">> Sourav"
    )
    
    # Sarah is trying to book a conflicting slot
    parsed_email = _base_parsed_email(
        "Re: Project Discussion Booking", 
        body,
        to=[TEST_USER_EMAIL, BOOKING_EMAIL],
        cc=[]
    )
    parsed_email["from"] = ["sarah.wilson@company.com"]

    response = run_booking_agent(
        parsed_email=parsed_email,
        calendar_user_id=TEST_USER_ID,
        booking_email=BOOKING_EMAIL,
    )

    print(f"\n📧 ACTUAL AGENT RESPONSE:")
    print(f"{'─'*60}")
    print(response)
    print(f"{'─'*60}")

    # Use LLM to evaluate if the response is appropriate
    _evaluate_agent_response_with_llm(
        request_description=f"User tried to book {meeting_date} {start_time}-{end_time} but there's already a conflicting event",
        agent_response=response,
        test_type="conflict"
    )
    
    # If LLM evaluation passes, also verify that no new event was created (no double booking)
    availability = calendar_assistant.get_availability(meeting_date, meeting_date)
    events_at_time = []
    
    for event in availability["events"]:
        # Handle both string and dict formats for start/end times
        event_start = event.get("start")
        event_end = event.get("end")
        
        # If start/end are strings, use them directly
        if isinstance(event_start, str):
            event_start_str = event_start
        elif isinstance(event_start, dict):
            event_start_str = event_start.get("dateTime", "")
        else:
            event_start_str = ""
        
        if isinstance(event_end, str):
            event_end_str = event_end
        elif isinstance(event_end, dict):
            event_end_str = event_end.get("dateTime", "")
        else:
            event_end_str = ""
        
        event_title = event.get("title", event.get("summary", ""))
        
        # Check if this event overlaps with our target time slot
        if event_start_str and event_end_str:
            # Simple overlap check
            if (f"{meeting_date}T{start_time}:00" < event_end_str and 
                f"{meeting_date}T{end_time}:00" > event_start_str):
                events_at_time.append({
                    "id": event.get("id"),
                    "title": event_title,
                    "start": event_start_str,
                    "end": event_end_str
                })
    
    # Should only have the original conflicting event, no new events
    assert len(events_at_time) == 1, f"Expected 1 event at {start_time}-{end_time}, found {len(events_at_time)}"
    assert events_at_time[0]["id"] == conflicting_event_id, f"Expected conflicting event {conflicting_event_id}, found {events_at_time[0]['id']}"
    assert events_at_time[0]["title"] == conflicting_title, f"Expected title '{conflicting_title}', found '{events_at_time[0]['title']}'"
    
    print(f"✅ VERIFICATION: No double booking occurred")
    print(f"✅ VERIFICATION: Only the original conflicting event exists")

    # Clean up the conflicting event
    calendar_assistant.cancel_event(conflicting_event_id)
    print(f"🧹 Cleaned up conflicting event {conflicting_event_id}")

    return conflicting_event_id


@pytest.mark.integration
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


@pytest.mark.integration
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