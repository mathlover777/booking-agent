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
from clerk_util import get_google_oauth_token_low_level, get_user_by_email, get_availability

# Load environment variables from .env.base (relative to project root)



def test_oauth_token_retrieval():
    """
    Test OAuth token retrieval for a specific user
    """
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


def test_get_user_by_email():
    """
    Test getting user by email address
    """
    email = "souravsarkar1729@gmail.com"  # Hardcoded for dev testing
    
    print(f"🧪 Testing Get User by Email")
    print(f"📧 Email: {email}")
    print(f"🌍 Stage: {os.getenv('STAGE', 'dev')}")
    print("=" * 80)
    
    try:
        # Call the Clerk utility function
        user_id = get_user_by_email(email)
        
        print("✅ Get user by email completed successfully!")
        print(f"\n👤 User ID: {user_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error getting user by email: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_user_by_email_not_found():
    """
    Test getting user by email address that doesn't exist
    """
    email = "nonexistent@example.com"  # Email that doesn't exist
    
    print(f"🧪 Testing Get User by Email (Not Found)")
    print(f"📧 Email: {email}")
    print(f"🌍 Stage: {os.getenv('STAGE', 'dev')}")
    print("=" * 80)
    
    try:
        # Call the Clerk utility function
        user_id = get_user_by_email(email)
        
        if user_id is None:
            print("✅ Get user by email (not found) completed successfully!")
            print(f"\n👤 User ID: {user_id} (None as expected)")
            return True
        else:
            print(f"❌ Expected None but got: {user_id}")
            return False
        
    except Exception as e:
        print(f"❌ Error getting user by email: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_availability_user_not_found():
    """
    Test get_availability with a user that doesn't exist
    """
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
    
    # Test get user by email
    print("\n" + "="*80)
    print("📧 TESTING GET USER BY EMAIL")
    print("=" * 80)
    email_success = test_get_user_by_email()
    
    # Test get user by email (not found)
    print("\n" + "="*80)
    print("📧 TESTING GET USER BY EMAIL (NOT FOUND)")
    print("=" * 80)
    email_not_found_success = test_get_user_by_email_not_found()
    
    # Test get availability (user not found)
    print("\n" + "="*80)
    print("📅 TESTING GET AVAILABILITY (USER NOT FOUND)")
    print("=" * 80)
    availability_not_found_success = test_get_availability_user_not_found()
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    all_tests_passed = oauth_success and email_success and email_not_found_success and availability_not_found_success
    
    if all_tests_passed:
        print("🎉 All Clerk utility tests passed!")
        print("✅ OAuth token retrieval: PASSED")
        print("✅ Get user by email: PASSED")
        print("✅ Get user by email (not found): PASSED")
        print("✅ Get availability (user not found): PASSED")
    else:
        print("💥 Some tests failed!")
        print(f"{'✅' if oauth_success else '❌'} OAuth token retrieval: {'PASSED' if oauth_success else 'FAILED'}")
        print(f"{'✅' if email_success else '❌'} Get user by email: {'PASSED' if email_success else 'FAILED'}")
        print(f"{'✅' if email_not_found_success else '❌'} Get user by email (not found): {'PASSED' if email_not_found_success else 'FAILED'}")
        print(f"{'✅' if availability_not_found_success else '❌'} Get availability (user not found): {'PASSED' if availability_not_found_success else 'FAILED'}")
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    if not success:
        import sys
        sys.exit(1) 