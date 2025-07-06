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
from clerk_util import get_google_oauth_token, get_user_by_email

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
        token_data = get_google_oauth_token(user_id)
        
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
    print("="*80)
    email_success = test_get_user_by_email()
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    if oauth_success and email_success:
        print("🎉 All Clerk utility tests passed!")
        print("✅ OAuth token retrieval: PASSED")
        print("✅ Get user by email: PASSED")
    else:
        print("💥 Some tests failed!")
        print(f"{'✅' if oauth_success else '❌'} OAuth token retrieval: {'PASSED' if oauth_success else 'FAILED'}")
        print(f"{'✅' if email_success else '❌'} Get user by email: {'PASSED' if email_success else 'FAILED'}")
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    if not success:
        import sys
        sys.exit(1) 