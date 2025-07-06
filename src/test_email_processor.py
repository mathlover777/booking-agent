#!/usr/bin/env python3
"""
Test script to simulate Lambda email processing locally
"""

import json
import boto3
import os
from dotenv import load_dotenv
from email_processor import lambda_handler
from clerk_util import get_google_oauth_token

# Load environment variables from .env.base (relative to project root)
load_dotenv('../.env.base')


def test_email_processing(s3_key: str):
    """
    Test email processing with a specific S3 key
    """
    print(f"🧪 Testing Email Processing")
    print(f"📧 S3 Key: {s3_key}")
    print("=" * 80)

    print(f"🪣 S3 Bucket: {os.getenv('EMAIL_BUCKET_NAME')}")
    
    # Create a mock event similar to what Lambda receives
    mock_event = {
        'Records': [
            {
                's3': {
                    'bucket': {
                        'name': os.getenv('EMAIL_BUCKET_NAME')
                    },
                    'object': {
                        'key': s3_key
                    }
                }
            }
        ]
    }
    
    # Create a mock context (not used in our function but required)
    mock_context = type('MockContext', (), {
        'function_name': 'test-email-processor',
        'function_version': 'test',
        'invoked_function_arn': 'arn:aws:lambda:ap-south-1:123456789012:function:test-email-processor',
        'memory_limit_in_mb': '256',
        'remaining_time_in_millis': lambda: 30000,
        'aws_request_id': 'test-request-id'
    })()
    
    try:
        # Call the lambda handler
        result = lambda_handler(mock_event, mock_context)
        
        print("\n✅ Email processing completed successfully!")
        print(f"📊 Status Code: {result['statusCode']}")
        
        # Parse and pretty print the response body
        response_body = json.loads(result['body'])
        print("\n📋 RESPONSE BODY:")
        print(json.dumps(response_body, indent=2, ensure_ascii=False))
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error processing email: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_clerk_oauth_token(user_id: str = None):
    """
    Test Clerk OAuth token retrieval
    """
    if user_id is None:
        user_id = "user_2zTBVQZOK5QCyxL43QTVOHOw3zK"  # Hardcoded for dev testing
    
    print(f"🧪 Testing Clerk OAuth Token Retrieval")
    print(f"👤 User ID: {user_id}")
    print(f"🌍 Stage: {os.getenv('STAGE', 'dev')}")
    print("=" * 80)
    
    try:
        # Call the Clerk utility function
        token_data = get_google_oauth_token(user_id)
        
        print("\n✅ OAuth token retrieval completed successfully!")
        
        # Parse and pretty print the response
        print("\n📋 TOKEN DATA:")
        print(json.dumps(token_data, indent=2, ensure_ascii=False))
        
        # Extract useful information
        if 'data' in token_data and len(token_data['data']) > 0:
            token_info = token_data['data'][0]
            print(f"\n🔑 Token ID: {token_info.get('id', 'N/A')}")
            print(f"📅 Created: {token_info.get('created_at', 'N/A')}")
            print(f"📅 Updated: {token_info.get('updated_at', 'N/A')}")
            print(f"🏷️ Provider: {token_info.get('provider', 'N/A')}")
            print(f"👤 User ID: {token_info.get('user_id', 'N/A')}")
            
            # Check if token has scopes
            if 'scopes' in token_info:
                print(f"🔍 Scopes: {', '.join(token_info['scopes'])}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error retrieving OAuth token: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """
    Main function to run the test
    """
    import sys
    
    # Default S3 key if none provided
    default_s3_key = "dev/emails/c14q29i0kbth1r5g76g5srvdilqdv3fugcsap4g1"
    
    # Get S3 key from command line argument or use default
    s3_key = sys.argv[1] if len(sys.argv) > 1 else default_s3_key
    
    print("🚀 Starting Email Processor Test")
    print(f"🔧 Using S3 Key: {s3_key}")
    print(f"🪣 S3 Bucket: {os.getenv('EMAIL_BUCKET_NAME', 'vibes-email-bucket-dev')}")
    print("=" * 80)
    
    # Check if AWS credentials are configured
    try:
        boto3.client('sts').get_caller_identity()
        print("✅ AWS credentials configured")
    except Exception as e:
        print(f"❌ AWS credentials not configured: {e}")
        print("Please configure AWS credentials before running the test")
        return False
    
    # Run the email processing test
    print("\n" + "="*80)
    print("📧 TESTING EMAIL PROCESSING")
    print("="*80)
    email_success = test_email_processing(s3_key)
    
    # Run the Clerk OAuth token test
    print("\n" + "="*80)
    print("🔐 TESTING CLERK OAUTH TOKEN")
    print("="*80)
    oauth_success = test_clerk_oauth_token()
    
    if email_success and oauth_success:
        print("\n🎉 All tests completed successfully!")
    else:
        print("\n💥 Some tests failed!")
        if not email_success:
            print("❌ Email processing test failed")
        if not oauth_success:
            print("❌ OAuth token test failed")
        sys.exit(1)


if __name__ == "__main__":
    main() 