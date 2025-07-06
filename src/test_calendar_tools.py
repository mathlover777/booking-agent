#!/usr/bin/env python3
"""
Test file demonstrating the Google Calendar tools for the scheduling agent.
This file shows how to use the calendar functions in practice.
"""

from dotenv import load_dotenv
load_dotenv('../.env.base',override=True)
load_dotenv('../.env.dev', override=True)

import os
from datetime import datetime, timedelta, timezone
import pytz
from clerk_util import (
    get_google_oauth_token,
    fetch_availability,
    book_event,
    cancel_event,
    get_calendar_timezone
)


def test_get_bookings():
    """Test 1: Get user's calendar bookings for next week"""
    user_id = "user_2zTBVQZOK5QCyxL43QTVOHOw3zK"
    
    print("=== Test 1: Getting Calendar Bookings ===\n")
    
    # Get OAuth token
    oauth_token = get_google_oauth_token(user_id)
    if not oauth_token:
        print("❌ Failed to get OAuth token")
        return
    
    # Get timezone
    timezone_id = get_calendar_timezone(user_id, oauth_token)
    print(f"User timezone: {timezone_id}")
    
    # Fetch availability for next week
    start_time = datetime.now() + timedelta(days=1)
    end_time = start_time + timedelta(days=7)
    
    start_iso = start_time.isoformat() + 'Z'
    end_iso = end_time.isoformat() + 'Z'
    
    try:
        availability = fetch_availability(user_id, oauth_token, start_iso, end_iso)
        print(f"Found {availability['total_events']} events in the next week")
        
        if availability['events']:
            print("\nEvents:")
            for event in availability['events']:
                event_id = event.get('id', 'No ID')
                print(f"- {event['title']} ({event['start']} to {event['end']}) [ID: {event_id}]")
        else:
            print("No events found in the next week")
            
    except Exception as e:
        print(f"❌ Error: {e}")


def test_book_event():
    """Test 2: Book a new event"""
    user_id = "user_2zTBVQZOK5QCyxL43QTVOHOw3zK"
    
    print("=== Test 2: Booking New Event ===\n")
    
    # Get OAuth token
    oauth_token = get_google_oauth_token(user_id)
    if not oauth_token:
        print("❌ Failed to get OAuth token")
        return
    
    # Get user's timezone first
    timezone_id = get_calendar_timezone(user_id, oauth_token)
    print(f"User timezone: {timezone_id}")
    
    # Book event for tomorrow at 8 PM in user's timezone
    user_tz = pytz.timezone(timezone_id)
    tomorrow = datetime.now(user_tz) + timedelta(days=1)
    start_time = tomorrow.replace(hour=20, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=1)
    
    # Format in user's timezone
    start_iso = start_time.isoformat()
    end_iso = end_time.isoformat()
    
    try:
        booked_event = book_event(
            user_id=user_id,
            oauth_token=oauth_token,
            start_timestamp=start_iso,
            end_timestamp=end_iso,
            title="Test Event - Automated Booking",
            description="This event was created by the test script",
            attendees=["test@example.com"],
            location="Virtual Meeting"
        )
        
        print(f"✅ Event booked successfully!")
        print(f"Event ID: {booked_event['event_id']}")
        print(f"Title: {booked_event['title']}")
        print(f"Time: {booked_event['start']} to {booked_event['end']}")
        print(f"Link: {booked_event['html_link']}")
        
        # Save event ID for cancellation test
        with open('/tmp/test_event_id.txt', 'w') as f:
            f.write(booked_event['event_id'])
            
    except Exception as e:
        print(f"❌ Error: {e}")


def test_cancel_event():
    """Test 3: Cancel an event"""
    user_id = "user_2zTBVQZOK5QCyxL43QTVOHOw3zK"
    
    print("=== Test 3: Canceling Event ===\n")
    
    # Get OAuth token
    oauth_token = get_google_oauth_token(user_id)
    if not oauth_token:
        print("❌ Failed to get OAuth token")
        return
    
    event_id = "h7oh8i63ov91vqdg5fev34703g"

    
    if event_id == "REPLACE_WITH_ACTUAL_EVENT_ID":
        print("❌ Please run test_book_event first or manually set event_id")
        return
    
    try:
        cancel_result = cancel_event(
            user_id=user_id,
            oauth_token=oauth_token,
            event_id=event_id,
            notify_attendees=True
        )
        
        print(f"✅ Event cancelled: {cancel_result['message']}")
        print(f"Event ID: {cancel_result['event_id']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


# Keep the original functions for reference
def test_calendar_tools():
    """Example usage of the calendar tools"""
    
    # Example user ID (replace with actual user ID)
    user_id = "user_2zTBVQZOK5QCyxL43QTVOHOw3zK"
    
    print("=== Google Calendar Tools Demo ===\n")
    
    # 1. Get OAuth token
    print("1. Getting OAuth token...")
    oauth_token = get_google_oauth_token(user_id)
    if not oauth_token:
        print("❌ Failed to get OAuth token")
        return
    print("✅ OAuth token retrieved successfully\n")
    
    # 2. Get calendar timezone
    print("2. Getting calendar timezone...")
    timezone_id = get_calendar_timezone(user_id, oauth_token)
    print(f"✅ Calendar timezone: {timezone_id}\n")
    
    # 3. Fetch availability for next week
    print("3. Fetching availability for next week...")
    start_time = datetime.now() + timedelta(days=1)
    end_time = start_time + timedelta(days=7)
    
    start_iso = start_time.isoformat() + 'Z'
    end_iso = end_time.isoformat() + 'Z'
    
    try:
        availability = fetch_availability(user_id, oauth_token, start_iso, end_iso)
        print(f"✅ Found {availability['total_events']} events in the time range")
        print(f"   Timezone: {availability['timezone']}")
        
        if availability['events']:
            print("   Events found:")
            for event in availability['events'][:3]:  # Show first 3 events
                print(f"   - {event['title']} ({event['start']} to {event['end']})")
        else:
            print("   No events found in this time range")
        print()
        
    except Exception as e:
        print(f"❌ Error fetching availability: {e}\n")
    
    # 4. Book a test event
    print("4. Booking a test event...")
    test_start = (datetime.now() + timedelta(days=2, hours=10)).isoformat() + 'Z'
    test_end = (datetime.now() + timedelta(days=2, hours=11)).isoformat() + 'Z'
    
    try:
        booked_event = book_event(
            user_id=user_id,
            oauth_token=oauth_token,
            start_timestamp=test_start,
            end_timestamp=test_end,
            title="Test Meeting - Scheduling Agent",
            description="This is a test event created by the scheduling agent",
            attendees=["test@example.com"],
            location="Virtual Meeting"
        )
        
        print(f"✅ Event booked successfully!")
        print(f"   Event ID: {booked_event['event_id']}")
        print(f"   Title: {booked_event['title']}")
        print(f"   Time: {booked_event['start']} to {booked_event['end']}")
        print(f"   Link: {booked_event['html_link']}")
        print()
        
        # 5. Cancel the test event
        print("5. Cancelling the test event...")
        cancel_result = cancel_event(
            user_id=user_id,
            oauth_token=oauth_token,
            event_id=booked_event['event_id'],
            notify_attendees=True
        )
        
        print(f"✅ Event cancelled: {cancel_result['message']}")
        print()
        
    except Exception as e:
        print(f"❌ Error with event booking/cancellation: {e}\n")


def agent_usage_example():
    """Example of how an agent would use these tools"""
    
    print("=== Agent Usage Example ===\n")
    
    # Simulate agent workflow
    user_id = "user_2abc123def456"
    
    # Agent gets OAuth token
    oauth_token = get_google_oauth_token(user_id)
    if not oauth_token:
        print("Agent cannot proceed without OAuth token")
        return
    
    # Agent checks user's timezone
    timezone = get_calendar_timezone(user_id, oauth_token)
    print(f"Agent detected user timezone: {timezone}")
    
    # Agent checks availability for tomorrow (9 AM to 5 PM in user's timezone)
    tomorrow = datetime.now() + timedelta(days=1)
    start_time = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
    end_time = tomorrow.replace(hour=17, minute=0, second=0, microsecond=0)
    
    availability = fetch_availability(
        user_id, 
        oauth_token, 
        start_time.isoformat() + 'Z',
        end_time.isoformat() + 'Z'
    )
    
    print(f"Agent found {availability['total_events']} events tomorrow")
    
    # Agent can now make intelligent scheduling decisions
    if availability['total_events'] < 3:
        print("Agent: User has availability tomorrow, can schedule meetings")
    else:
        print("Agent: User is busy tomorrow, should look for other days")


if __name__ == "__main__":
    # Set STAGE environment variable if not set
    if 'STAGE' not in os.environ:
        os.environ['STAGE'] = 'dev'
    
    print("Running calendar tools demo...")
    print("Note: This demo requires valid OAuth tokens and proper setup")
    print("=" * 50)
    
    # Uncomment the function you want to run:
    # test_calendar_tools()
    # agent_usage_example()
    
    print("Demo completed. Uncomment the function calls above to run actual tests.") 