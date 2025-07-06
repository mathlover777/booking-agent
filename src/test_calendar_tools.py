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
    
    # Calculate date range for next week
    start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    try:
        availability = fetch_availability(user_id, start_date, end_date)
        print(f"User timezone: {availability['timezone']}")
        print(f"Found {availability['total_events']} events from {start_date} to {end_date}")
        
        if availability['events']:
            print("\nEvents:")
            for event in availability['events']:
                event_id = event.get('id', 'No ID')
                print(f"- {event['title']} ({event['start']} to {event['end']}) [ID: {event_id}]")
        else:
            print("No events found in the date range")
            
    except Exception as e:
        print(f"❌ Error: {e}")


def test_book_event():
    """Test 2: Book a new event"""
    user_id = "user_2zTBVQZOK5QCyxL43QTVOHOw3zK"
    
    print("=== Test 2: Booking New Event ===\n")
    
    # Book event for tomorrow at 8 PM
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    try:
        booked_event = book_event(
            user_id=user_id,
            start_date=tomorrow,
            start_time="20:00",
            end_date=tomorrow,
            end_time="21:00",
            title="Test Event - Automated Booking",
            description="This event was created by the test script",
            attendees=["test@example.com"],
            location="Virtual Meeting"
        )
        
        print(f"✅ Event booked successfully!")
        print(f"Event ID: {booked_event['event_id']}")
        print(f"Title: {booked_event['title']}")
        print(f"Time: {booked_event['start']} to {booked_event['end']}")
        print(f"Timezone: {booked_event['timezone']}")
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
    
    # Try to read event ID from file, or use a default
    event_id = "2c187f2272pjvd9hvvi8d38jog"
    
    try:
        with open('/tmp/test_event_id.txt', 'r') as f:
            event_id = f.read().strip()
    except FileNotFoundError:
        print("No saved event ID found, using default")
    
    if event_id == "REPLACE_WITH_ACTUAL_EVENT_ID":
        print("❌ Please run test_book_event first or manually set event_id")
        return
    
    try:
        cancel_result = cancel_event(
            user_id=user_id,
            event_id=event_id,
            notify_attendees=True
        )
        
        print(f"✅ Event cancelled: {cancel_result['message']}")
        print(f"Event ID: {cancel_result['event_id']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def test_calendar_tools():
    """Example usage of the calendar tools"""
    
    # Example user ID (replace with actual user ID)
    user_id = "user_2zTBVQZOK5QCyxL43QTVOHOw3zK"
    
    print("=== Google Calendar Tools Demo ===\n")
    
    # 1. Fetch availability for next week
    print("1. Fetching availability for next week...")
    start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    try:
        availability = fetch_availability(user_id, start_date, end_date)
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
    
    # 2. Book a test event
    print("2. Booking a test event...")
    test_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    
    try:
        booked_event = book_event(
            user_id=user_id,
            start_date=test_date,
            start_time="10:00",
            end_date=test_date,
            end_time="11:00",
            title="Test Meeting - Scheduling Agent",
            description="This is a test event created by the scheduling agent",
            attendees=["test@example.com"],
            location="Virtual Meeting"
        )
        
        print(f"✅ Event booked successfully!")
        print(f"   Event ID: {booked_event['event_id']}")
        print(f"   Title: {booked_event['title']}")
        print(f"   Time: {booked_event['start']} to {booked_event['end']}")
        print(f"   Timezone: {booked_event['timezone']}")
        print(f"   Link: {booked_event['html_link']}")
        print()
        
        # 3. Cancel the test event
        print("3. Cancelling the test event...")
        cancel_result = cancel_event(
            user_id=user_id,
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
    
    # Agent checks availability for tomorrow
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    try:
        availability = fetch_availability(user_id, tomorrow, tomorrow)
        
        print(f"Agent detected user timezone: {availability['timezone']}")
        print(f"Agent found {availability['total_events']} events tomorrow")
        
        # Agent can now make intelligent scheduling decisions
        if availability['total_events'] < 3:
            print("Agent: User has availability tomorrow, can schedule meetings")
            
            # Agent books a meeting
            booked_event = book_event(
                user_id=user_id,
                start_date=tomorrow,
                start_time="14:00",
                end_date=tomorrow,
                end_time="15:00",
                title="AI Scheduled Meeting",
                description="This meeting was scheduled by the AI agent"
            )
            print(f"Agent: Booked meeting at {booked_event['start']}")
        else:
            print("Agent: User is busy tomorrow, should look for other days")
            
    except Exception as e:
        print(f"Agent error: {e}")


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