#!/usr/bin/env python3
"""
Test script to simulate Lambda email processing locally
"""
from dotenv import load_dotenv
load_dotenv('../.env.base')
load_dotenv('../.env.dev')

import json
import boto3
import os

from email_processor import lambda_handler

# Load environment variables from .env.base (relative to project root)



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

    
    if email_success:
        print("\n🎉 Email processing test completed successfully!")
    else:
        print("\n💥 Email processing test failed!")
        sys.exit(1)


if __name__ == "__main__":
    main() 