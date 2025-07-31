#!/usr/bin/env python3
"""
End-to-end test for email processor pipeline
Tests the full flow: S3 → parsing → agent processing → SES sending
Similar to test_agent_integration.py but tests the entire pipeline
"""

import json
import boto3
import os
import sys
import uuid
import logging
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any

from dotenv import load_dotenv

# Configure logging for tests to reduce noise
logging.basicConfig(level=logging.WARNING)
logging.getLogger('email_processor').setLevel(logging.WARNING)
logging.getLogger('booking_agent').setLevel(logging.WARNING)

# Load environment variables BEFORE importing modules that depend on them
# Test runs from src directory, so use relative path to root
load_dotenv('../.env.base', override=True)
load_dotenv('../.env.dev', override=True)

# Set additional required environment variables
os.environ['USER_EMAILS_TABLE_NAME'] = 'vibes-user-emails-dev'

# Add current directory to path since we're now in src/
sys.path.insert(0, '.')

from email_processor import lambda_handler
from common_utils.email_util import parse_email_from_s3

# Persistent test user - DO NOT DELETE, this is used in production
TEST_USER_ID = "user_2zTBVQZOK5QCyxL43QTVOHOw3zK"
TEST_USER_EMAIL = "souravsarkar1729@gmail.com"
TEST_AGENT_EMAIL = "test.dev@bhaang.com"  # Development agent email

# ---------------------------------------------------------------------------
# Global email template ------------------------------------------------------
# ---------------------------------------------------------------------------

# Global email template that can be customized per test
GLOBAL_EMAIL_TEMPLATE = """Return-Path: <{from_email}>
Received: from mail-lj1-f176.google.com (mail-lj1-f176.google.com [209.85.208.176])
 by inbound-smtp.ap-south-1.amazonaws.com with SMTP id 4q8pbe8n9tu1bjvj0mrj1hdsq8pphi5ln5qe1ng1
 for bookdev@bhaang.com;
 Sun, 06 Jul 2025 12:29:03 +0000 (UTC)
X-SES-Spam-Verdict: PASS
X-SES-Virus-Verdict: PASS
MIME-Version: 1.0
References: <CABu2_85u6d9s3EMHU3iVOJ3x63BksZ3MYQY8zJPAx_ag0HQMOA@mail.gmail.com>
In-Reply-To: <01090197dfb549f7-ae5362bf-c207-4598-9295-6bf355a29238-000000@ap-south-1.amazonses.com>
From: {from_name} <{from_email}>
Date: Sun, 6 Jul 2025 16:28:48 +0400
Message-ID: <CAATJRY_M03D4Lckc7dQV5SH8whJY=Jsrb7N4FHBco+DG7u0VJw@mail.gmail.com>
Subject: {subject}
To: {to_emails}
Cc: {cc_emails}
Content-Type: multipart/alternative; boundary="00000000000028004f063941dfae"
X-SES-RECEIPT-RULE: email-processor-dev

--00000000000028004f063941dfae
Content-Type: text/plain; charset="UTF-8"

{body}

--00000000000028004f063941dfae
Content-Type: text/html; charset="UTF-8"
Content-Transfer-Encoding: quoted-printable

<div dir=3D"ltr">{body_html}</div>

--00000000000028004f063941dfae--"""


# ---------------------------------------------------------------------------
# Helper utilities ----------------------------------------------------------
# ---------------------------------------------------------------------------

def _setup_test_user(agent_email: str, user_email: str = TEST_USER_EMAIL, user_id: str = TEST_USER_ID):
    """Setup test user in DynamoDB - UPSERT operation to preserve existing data"""
    table = boto3.resource('dynamodb').Table(os.getenv('USER_EMAILS_TABLE_NAME'))
    
    # Convert full email to local part for database storage
    from common_utils.email_helpers import to_local
    assist_local = to_local(agent_email)
    
    test_item = {
        'pk': f"uid:{user_id}",
        'sk': 'data',
        'user_id': user_id,
        'assist_email': agent_email,
        'assist_local': assist_local,
        'user_email': user_email,
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-15T10:00:00'
    }
    
    # Use put_item (upsert) to preserve existing data
    table.put_item(Item=test_item)
    print(f"✅ Updated test user: {user_id} with agent: {agent_email}, user: {user_email}")
    return test_item


def _create_synthetic_email(from_name: str, from_email: str, to_emails: list, cc_emails: list, 
                           subject: str, body: str, body_html: str = None) -> str:
    """Create synthetic email using the global template"""
    if body_html is None:
        body_html = body
    
    return GLOBAL_EMAIL_TEMPLATE.format(
        from_name=from_name,
        from_email=from_email,
        to_emails=", ".join(to_emails) if to_emails else "",
        cc_emails=", ".join(cc_emails) if cc_emails else "",
        subject=subject,
        body=body,
        body_html=body_html
    )


def _upload_to_s3_test_bucket(email_content: str, bucket_name: str = "vibecal-test-bucket-dca839fhjo"):
    """Upload synthetic email to test S3 bucket"""
    
    # Create S3 client
    s3_client = boto3.client('s3')
    
    # Generate a unique key for this test
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    s3_key = f"test-emails/synthetic_email_{timestamp}.eml"
    
    try:
        # Upload the email content
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=email_content.encode('utf-8'),
            ContentType='message/rfc822'
        )
        
        print(f"✅ Uploaded synthetic email to S3: {bucket_name}/{s3_key}")
        return s3_key
        
    except Exception as e:
        print(f"❌ Failed to upload to S3: {e}")
        return None


def _create_lambda_event(s3_bucket: str, s3_key: str):
    """Create a Lambda event that mimics S3 trigger"""
    return {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "awsRegion": "ap-south-1",
                "eventTime": "2025-07-06T12:29:03.000Z",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "s3SchemaVersion": "1.0",
                    "configurationId": "email-processor-dev",
                    "bucket": {
                        "name": s3_bucket,
                        "ownerIdentity": {
                            "principalId": "A3NL1KOZZKExample"
                        },
                        "arn": f"arn:aws:s3:::{s3_bucket}"
                    },
                    "object": {
                        "key": s3_key,
                        "size": 1024,
                        "eTag": "d41d8cd98f00b204e9800998ecf8427e",
                        "sequencer": "0A1B2C3D4E5F678901"
                    }
                }
            }
        ]
    }


def _mock_ses_send_raw_email(*args, **kwargs):
    """Mock SES send_raw_email to show parameters instead of actually sending"""
    
    print("\n" + "="*80)
    print("📧 MOCKED SES SEND_RAW_EMAIL CALL")
    print("="*80)
    print(f"Source: {kwargs.get('Source')}")
    print(f"Destinations: {kwargs.get('Destinations')}")
    
    # Parse the raw message to show headers
    raw_message = kwargs.get('RawMessage', {})
    if 'Data' in raw_message:
        raw_data = raw_message['Data']
        print(f"\nRaw message headers:")
        lines = raw_data.split('\n')
        for line in lines[:20]:  # Show first 20 lines
            if line.strip() and ':' in line:
                print(f"  {line}")
            elif not line.strip():
                break
    
    print("="*80)
    
    # Return a mock successful response
    return {
        'MessageId': 'mock-message-id-12345',
        'ResponseMetadata': {
            'RequestId': 'mock-request-id',
            'HTTPStatusCode': 200
        }
    }


# ---------------------------------------------------------------------------
# Test cases for email processor pipeline -----------------------------------
# ---------------------------------------------------------------------------

def test_case_1_share_availability_e2e():
    """Case 1: Share availability - full email processor pipeline test"""
    print("\n=== Case 1: Share Availability (Full Pipeline) ===")
    
    # Use persistent test user
    test_agent_email = TEST_AGENT_EMAIL
    
    start = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    
    # Setup DynamoDB test data (already exists, but ensure it's correct)
    _setup_test_user(test_agent_email, TEST_USER_EMAIL, TEST_USER_ID)
    
    # Create synthetic email content
    body = (
        f"@{test_agent_email} please share my availability for {start} to {end}!\n\n"
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
    
    # Create synthetic email using template
    email_content = _create_synthetic_email(
        from_name="Sourav Sarkar",
        from_email=TEST_USER_EMAIL,
        to_emails=[test_agent_email, "john.doe@example.com"],
        cc_emails=[],
        subject="Re: Meeting request",
        body=body
    )
    
    print(f"📅 Requesting availability for: {start} to {end}")
    print(f"👤 User: {TEST_USER_EMAIL}")
    print(f"🤖 Agent: {test_agent_email}")
    print(f"📧 Recipients: John Doe + Agent")
    
    print(f"\n📋 EXPECTED BEHAVIOR:")
    print(f"   • Email should be uploaded to S3 (real)")
    print(f"   • Lambda should be triggered")
    print(f"   • Email should be parsed correctly")
    print(f"   • Agent should resolve calendar owner successfully")
    print(f"   • Should check calendar for {start} to {end}")
    print(f"   • Response should contain available time slots")
    print(f"   • Response should end with 'By VibeCal'")
    print(f"   • SES should be called to send response (mocked)")
    
    # Upload to S3
    s3_key = _upload_to_s3_test_bucket(email_content)
    
    if not s3_key:
        print("❌ Failed to upload to S3, aborting test")
        return None
    
    # Create Lambda event
    event = _create_lambda_event("vibecal-test-bucket-dca839fhjo", s3_key)
    
    # Mock only the SES send_raw_email function to prevent actual email sending
    with patch('common_utils.email_util.send_email_via_ses') as mock_send_email:
        mock_send_email.return_value = {
            'success': True,
            'message_id': 'mock-message-id-12345',
            'response': {
                'MessageId': 'mock-message-id-12345',
                'ResponseMetadata': {
                    'RequestId': 'mock-request-id',
                    'HTTPStatusCode': 200
                }
            }
        }
        
        print(f"\n🎯 Testing Lambda handler with event:")
        print(json.dumps(event, indent=2))
        
        # Call the Lambda handler
        try:
            result = lambda_handler(event, {})
            
            print(f"\n✅ Lambda handler completed successfully!")
            print(f"Status Code: {result.get('statusCode')}")
            print(f"Response: {json.dumps(result.get('body', {}), indent=2)}")
            
            if result.get('statusCode') == 200:
                print(f"✅ SUCCESS: Full pipeline completed successfully")
                response_body = json.loads(result.get('body', '{}'))
                if response_body.get('action') == 'processed':
                    print(f"📧 AI Response:")
                    print(f"{'─'*60}")
                    print(response_body.get('ai_response', ''))
                    print(f"{'─'*60}")
                    print(f"\n📋 VERIFICATION:")
                    print(f"   • Action: {response_body.get('action')}")
                    print(f"   • Calendar User ID: {response_body.get('calendar_user_id')}")
                    print(f"   • Booking Email: {response_body.get('booking_email')}")
                    print(f"   • Response contains 'By VibeCal': {'By VibeCal' in response_body.get('ai_response', '')}")
                else:
                    print(f"⚠️  Agent returned: {response_body.get('action')}")
                    if response_body.get('clarification_message'):
                        print(f"📧 Clarification message:")
                        print(f"{'─'*60}")
                        print(response_body.get('clarification_message'))
                        print(f"{'─'*60}")
            else:
                print(f"❌ FAILED: Lambda returned status {result.get('statusCode')}")
            
            return result
            
        except Exception as e:
            print(f"\n❌ Lambda handler failed: {e}")
            import traceback
            traceback.print_exc()
            return None


def test_case_2_book_event_e2e():
    """Case 2: Book event - full email processor pipeline test"""
    print("\n=== Case 2: Book Event (Full Pipeline) ===")
    
    # Use persistent test user
    test_agent_email = TEST_AGENT_EMAIL
    
    meeting_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    start_time = "10:00"
    end_time = "11:00"
    title = f"AI-Book-Test {uuid.uuid4().hex[:4]}"
    
    # Setup DynamoDB test data (already exists, but ensure it's correct)
    _setup_test_user(test_agent_email, TEST_USER_EMAIL, TEST_USER_ID)
    
    # Create synthetic email content
    body = (
        f"@{test_agent_email} please book {meeting_date} {start_time}-{end_time} for '{title}'\n\n"
        f"On Tue, 8 Jul 2025 at 14:20, Mike Johnson <mike.johnson@startup.com> wrote:\n"
        f"> Hi Sourav,\n>\n"
        f"> Perfect! I'd like to book the {start_time} slot on {meeting_date} for '{title}'.\n"
        f"> Please go ahead and schedule it.\n>\n"
        f"> Thanks,\n"
        f"> Mike\n>\n"
        f"> On Tue, 8 Jul 2025 at 13:45, {test_agent_email} wrote:\n"
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
    
    # Create synthetic email using template
    email_content = _create_synthetic_email(
        from_name="Mike Johnson",
        from_email="mike.johnson@startup.com",
        to_emails=[TEST_USER_EMAIL, test_agent_email],
        cc_emails=[],
        subject="Re: Meeting booking",
        body=body
    )
    
    print(f"📅 Meeting date: {meeting_date}")
    print(f"⏰ Time: {start_time}-{end_time}")
    print(f"📝 Title: {title}")
    print(f"👤 User: {TEST_USER_EMAIL}")
    print(f"🤖 Agent: {test_agent_email}")
    print(f"📧 From: Mike Johnson (wanting to book)")
    
    print(f"\n📋 EXPECTED BEHAVIOR:")
    print(f"   • Email should be uploaded to S3 (real)")
    print(f"   • Lambda should be triggered")
    print(f"   • Email should be parsed correctly")
    print(f"   • Agent should resolve calendar owner successfully")
    print(f"   • Should recognize Mike's request to book the {start_time} slot")
    print(f"   • Should create calendar event for {meeting_date} {start_time}-{end_time}")
    print(f"   • Response should confirm booking was successful")
    print(f"   • Response should include 'Event ID: [some-id]'")
    print(f"   • Response should end with 'By VibeCal'")
    print(f"   • SES should be called to send response (mocked)")
    
    # Upload to S3
    s3_key = _upload_to_s3_test_bucket(email_content)
    
    if not s3_key:
        print("❌ Failed to upload to S3, aborting test")
        return None
    
    # Create Lambda event
    event = _create_lambda_event("vibecal-test-bucket-dca839fhjo", s3_key)
    
    # Mock only the SES send_raw_email function to prevent actual email sending
    with patch('common_utils.email_util.send_email_via_ses') as mock_send_email:
        mock_send_email.return_value = {
            'success': True,
            'message_id': 'mock-message-id-12345',
            'response': {
                'MessageId': 'mock-message-id-12345',
                'ResponseMetadata': {
                    'RequestId': 'mock-request-id',
                    'HTTPStatusCode': 200
                }
            }
        }
        
        print(f"\n🎯 Testing Lambda handler with event:")
        print(json.dumps(event, indent=2))
        
        # Call the Lambda handler
        try:
            result = lambda_handler(event, {})
            
            print(f"\n✅ Lambda handler completed successfully!")
            print(f"Status Code: {result.get('statusCode')}")
            print(f"Response: {json.dumps(result.get('body', {}), indent=2)}")
            
            if result.get('statusCode') == 200:
                print(f"✅ SUCCESS: Full pipeline completed successfully")
                response_body = json.loads(result.get('body', '{}'))
                if response_body.get('action') == 'processed':
                    print(f"📧 AI Response:")
                    print(f"{'─'*60}")
                    print(response_body.get('ai_response', ''))
                    print(f"{'─'*60}")
                    print(f"\n📋 VERIFICATION:")
                    print(f"   • Action: {response_body.get('action')}")
                    print(f"   • Calendar User ID: {response_body.get('calendar_user_id')}")
                    print(f"   • Booking Email: {response_body.get('booking_email')}")
                    print(f"   • Response contains 'By VibeCal': {'By VibeCal' in response_body.get('ai_response', '')}")
                else:
                    print(f"⚠️  Agent returned: {response_body.get('action')}")
                    if response_body.get('clarification_message'):
                        print(f"📧 Clarification message:")
                        print(f"{'─'*60}")
                        print(response_body.get('clarification_message'))
                        print(f"{'─'*60}")
            else:
                print(f"❌ FAILED: Lambda returned status {result.get('statusCode')}")
            
            return result
            
        except Exception as e:
            print(f"\n❌ Lambda handler failed: {e}")
            import traceback
            traceback.print_exc()
            return None


# ---------------------------------------------------------------------------
# Test runner functions ------------------------------------------------------
# ---------------------------------------------------------------------------

def test_all_e2e_flows():
    """Test all end-to-end email processor flows"""
    print("Running all end-to-end email processor pipeline tests...")
    print("These tests use real AWS services (S3, DynamoDB) but mock SES to prevent email sending.")
    print("Calendar events may be created during testing.")
    print()
    
    test_case_1_share_availability_e2e()
    print("\n" + "="*80 + "\n")
    test_case_2_book_event_e2e()
    
    print("\n✅ All end-to-end email processor pipeline tests completed!")


# ---------------------------------------------------------------------------
# Allow execution via `python test_email_processor_e2e.py`
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running email processor end-to-end tests...")
    print("These tests use real AWS services (S3, DynamoDB) and Google Calendar but mock SES to prevent email sending.")
    print("Ensure you have proper AWS and Google Calendar credentials configured.")
    print()
    
    # Run all tests
    test_all_e2e_flows()
    
    print("\n✅ All email processor end-to-end tests completed!") 