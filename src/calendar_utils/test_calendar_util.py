#!/usr/bin/env python3
"""
Test script specifically for Clerk utility functions
"""
from dotenv import load_dotenv
load_dotenv('../.env.base',override=True)
load_dotenv('../.env.dev', override=True)

import json
import boto3
import os
from datetime import datetime, timedelta

# Load environment variables from .env.base (relative to project root)


def test_oauth_token_retrieval():
    """
    Test OAuth token retrieval for a specific user
    """
    from .calendar_util import get_google_oauth_token_low_level
    
    user_id = "user_2zTBVQZOK5QCyxL43QTVOHOw3zK"  # Hardcoded for dev testing
    
    print(f"🧪 Testing OAuth Token Retrieval")
    print(f"👤 User ID: {user_id}")
    print(f"🌍 Stage: {os.getenv('STAGE', 'dev')}")
    print("=" * 80)
    
    try:
        # Call the Clerk utility function
        token_data = get_google_oauth_token_low_level(user_id)
        
        print("✅ OAuth token retrieval completed successfully!")
        
        # Display the token
        if token_data:
            print(f"\n🎫 Access token (first 10 chars): {token_data[:10]}...")
            print(f"🎫 Full token: {token_data}")
        else:
            print("⚠️ No token found")
        
        return True
        
    except Exception as e:
        print(f"❌ Error retrieving OAuth token: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_availability_user_not_found():
    """
    Test get_availability with a user that doesn't exist
    """
    from .calendar_util import get_availability_low_level as get_availability
    
    email = "nonexistent@example.com"  # Email that doesn't exist
    
    print(f"🧪 Testing Get Availability (User Not Found)")
    print(f"📧 Email: {email}")
    print(f"🌍 Stage: {os.getenv('STAGE', 'dev')}")
    print("=" * 80)
    
    try:
        # Call the get_availability function
        result = get_availability(email, "2024-01-01", "2024-01-31")
        
        # Check if it returns the expected error structure
        if isinstance(result, dict) and result.get("error") == "User not found":
            print("✅ Get availability (user not found) completed successfully!")
            print(f"\n📋 Result: {result}")
            return True
        else:
            print(f"❌ Expected error structure but got: {result}")
            return False
        
    except Exception as e:
        print(f"❌ Error in get_availability: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_calendar_workflow():
    """
    Test complete calendar workflow: get availability, book event, delete event
    """
    from .calendar_tools import CalendarAssistant
    
    user_id = "user_2zTBVQZOK5QCyxL43QTVOHOw3zK"  # Hardcoded for dev testing
    
    print(f"🧪 Testing Complete Calendar Workflow")
    print(f"👤 User ID: {user_id}")
    print(f"🌍 Stage: {os.getenv('STAGE', 'dev')}")
    print("=" * 80)
    
    try:
        # Initialize CalendarAssistant
        calendar = CalendarAssistant(user_id)
        
        # Calculate dates for testing
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        day_after_tomorrow = today + timedelta(days=2)
        
        start_date = tomorrow.strftime("%Y-%m-%d")
        end_date = day_after_tomorrow.strftime("%Y-%m-%d")
        event_date = tomorrow.strftime("%Y-%m-%d")
        
        print(f"📅 Test Date Range: {start_date} to {end_date}")
        print(f"📅 Event Date: {event_date}")
        
        # Step 1: Get Availability
        print(f"\n🔍 STEP 1: Getting Calendar Availability")
        print(f"   📅 Date Range: {start_date} to {end_date}")
        
        availability = calendar.get_availability(start_date, end_date)
        
        print(f"   ✅ Availability Retrieved Successfully!")
        print(f"   📊 Total Events: {availability.get('total_events', 0)}")
        print(f"   🌍 Timezone: {availability.get('timezone', 'Unknown')}")
        print(f"   📋 Events: {len(availability.get('events', []))}")
        
        # Step 2: Book Event
        print(f"\n📝 STEP 2: Booking Test Event")
        print(f"   📅 Date: {event_date}")
        print(f"   ⏰ Time: 14:00-15:00")
        print(f"   📋 Title: Test Event - Calendar Workflow")
        print(f"   📝 Description: Automated test event for calendar workflow")
        
        booking_result = calendar.book_event(
            date=event_date,
            start_time="14:00",
            end_time="15:00",
            title="Test Event - Calendar Workflow",
            description="Automated test event for calendar workflow",
            attendees=["test@example.com"],
            location="Virtual Meeting"
        )
        
        event_id = booking_result.get('event_id')
        print(f"   ✅ Event Booked Successfully!")
        print(f"   🆔 Event ID: {event_id}")
        print(f"   📋 Title: {booking_result.get('title')}")
        print(f"   ⏰ Start: {booking_result.get('start')}")
        print(f"   ⏰ End: {booking_result.get('end')}")
        print(f"   🌍 Timezone: {booking_result.get('timezone')}")
        print(f"   🔗 Link: {booking_result.get('html_link')}")
        
        # Step 3: Delete Event
        print(f"\n🗑️ STEP 3: Deleting Test Event")
        print(f"   🆔 Event ID: {event_id}")
        print(f"   📢 Notify Attendees: True")
        
        delete_result = calendar.cancel_event(event_id, notify_attendees=True)
        
        print(f"   ✅ Event Deleted Successfully!")
        print(f"   🆔 Event ID: {delete_result.get('event_id')}")
        print(f"   📊 Status: {delete_result.get('status')}")
        print(f"   📢 Attendees Notified: {delete_result.get('notified_attendees')}")
        print(f"   💬 Message: {delete_result.get('message')}")
        
        print(f"\n🎉 Complete Calendar Workflow Test Passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error in calendar workflow test: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """
    Main function to run all Clerk utility tests
    """
    print("🚀 Starting Clerk Utility Tests")
    print("=" * 80)
    
    # Check if AWS credentials are configured
    try:
        boto3.client('sts').get_caller_identity()
        print("✅ AWS credentials configured")
    except Exception as e:
        print(f"❌ AWS credentials not configured: {e}")
        print("Please configure AWS credentials before running the test")
        return False
    
    # Test OAuth token retrieval (includes secret key retrieval)
    print("\n" + "="*80)
    print("🔑 TESTING OAUTH TOKEN RETRIEVAL")
    print("="*80)
    oauth_success = test_oauth_token_retrieval()
    
    # Test get availability (user not found)
    print("\n" + "="*80)
    print("📅 TESTING GET AVAILABILITY (USER NOT FOUND)")
    print("=" * 80)
    availability_not_found_success = test_get_availability_user_not_found()
    
    # Test complete calendar workflow
    print("\n" + "="*80)
    print("🔄 TESTING COMPLETE CALENDAR WORKFLOW")
    print("=" * 80)
    workflow_success = test_calendar_workflow()
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    all_tests_passed = oauth_success and availability_not_found_success and workflow_success
    
    if all_tests_passed:
        print("🎉 All Clerk utility tests passed!")
        print("✅ OAuth token retrieval: PASSED")
        print("✅ Get availability (user not found): PASSED")
        print("✅ Complete calendar workflow: PASSED")
    else:
        print("💥 Some tests failed!")
        print(f"{'✅' if oauth_success else '❌'} OAuth token retrieval: {'PASSED' if oauth_success else 'FAILED'}")
        print(f"{'✅' if availability_not_found_success else '❌'} Get availability (user not found): {'PASSED' if availability_not_found_success else 'FAILED'}")
        print(f"{'✅' if workflow_success else '❌'} Complete calendar workflow: {'PASSED' if workflow_success else 'FAILED'}")
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    if not success:
        import sys
        sys.exit(1) 