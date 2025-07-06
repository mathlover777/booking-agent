#!/usr/bin/env python3
"""
Test file for the booking agent AI integration.
Tests with real S3 email.
"""

from dotenv import load_dotenv
load_dotenv('../.env.base', override=True)
load_dotenv('../.env.dev', override=True)

import os
from booking_agent import process_email_with_ai


def test_real_s3_email():
    """Test with actual S3 email path"""
    
    print("=== Test Real S3 Email ===\n")
    
    # Get bucket name from env
    bucket_name = os.getenv('EMAIL_BUCKET_NAME', 'vibes-email-bucket-dev')
    s3_key = "dev/emails/8m5bkklpcn2v8b98gj81633qgdhcj64ucqh3c201"
    
    print(f"Testing with bucket: {bucket_name}")
    print(f"Testing with key: {s3_key}")
    print()
    
    try:
        result = process_email_with_ai(bucket_name, s3_key)
        
        print("✅ AI Processing Result:")
        print(f"   Action: {result.get('action', 'none')}")
        print(f"   Owner Email: {result.get('owner_email', 'None')}")
        print(f"   Email IDs: {result.get('email_ids', [])}")
        print(f"   Tool Calls: {len(result.get('tool_calls', []))}")
        
        print("\n📧 AI Response:")
        print("-" * 50)
        print(result.get('email_response', 'No response'))
        print("-" * 50)
        
        return result
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


if __name__ == "__main__":
    test_real_s3_email() 