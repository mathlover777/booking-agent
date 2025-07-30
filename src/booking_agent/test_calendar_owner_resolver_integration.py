import os
import json
import logging
import uuid
import boto3
from typing import Dict, Any

from dotenv import load_dotenv

# Configure logging for tests to reduce noise
logging.basicConfig(level=logging.WARNING)
logging.getLogger('booking_agent.calendar_owner_resolver').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

# Load environment variables BEFORE importing modules that depend on them
# Test runs from src directory, so use relative path to root
load_dotenv('../.env.base', override=True)
load_dotenv('../.env.dev', override=True)

# Set additional required environment variables
os.environ['USER_EMAILS_TABLE_NAME'] = 'vibes-user-emails-dev'

# Import the actual module (no mocking)
from .calendar_owner_resolver import resolve_calendar_owner


# Real integration tests with synthetic data
def test_case_1_single_agent_user_in_thread():
    """Case 1: Email with only one bhaang email and its mapped user is one of the users in the email thread"""
    print("\n=== Case 1: Single agent, user in thread ===")
    
    # Generate random test data
    test_user_id = f"test-user-{uuid.uuid4().hex[:8]}"
    test_agent_email = f"test-agent-{uuid.uuid4().hex[:8]}@bhaang.com"
    test_user_email = "john.doe@example.com"  # User email that will be in conversation
    
    # Setup DynamoDB test data
    table = boto3.resource('dynamodb').Table(os.getenv('USER_EMAILS_TABLE_NAME'))
    
    # Convert full email to local part for database storage
    from common_utils.email_helpers import to_local
    assist_local = to_local(test_agent_email)
    
    test_item = {
        'pk': f"uid:{test_user_id}",
        'sk': 'data',
        'user_id': test_user_id,
        'assist_email': test_agent_email,
        'assist_local': assist_local,  # Add assist_local field for GSI lookup
        'user_email': test_user_email,  # Add user_email field
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-15T10:00:00'
    }
    
    try:
        # Insert test data
        table.put_item(Item=test_item)
        print(f"✅ Created test user: {test_user_id} with agent: {test_agent_email}, user: {test_user_email}")
        
        # Synthetic email data with user in conversation
        parsed_email = {
            "subject": "Meeting with John Doe",
            "from": ["john.doe@example.com"],  # User is in conversation
            "to": [test_agent_email],
            "cc": ["jane.smith@example.com"],
            "body": "Hi, I'd like to schedule a meeting with John Doe. Can you help me find a time?",
            "date": "2024-01-15",
            "message_id": "case1-123"
        }
        
        print(f"Email: {parsed_email['subject']}")
        print(f"From: {parsed_email['from']}")
        print(f"To: {parsed_email['to']}")
        print(f"CC: {parsed_email['cc']}")
        
        result = resolve_calendar_owner(parsed_email)
        print(f"Result: {result}")
        
        if result["status"] == "success":
            print(f"✅ SUCCESS: Resolved to user {result['user_id']} with agent {result['assist_email']}")
        else:
            print(f"❌ FAILED: {result['status']} - {result.get('reason', 'No reason provided')}")
        
        return result
        
    finally:
        # Cleanup test data
        table.delete_item(Key={'pk': f"uid:{test_user_id}", 'sk': 'data'})
        print(f"🧹 Cleaned up test user: {test_user_id}")


def test_case_2_agent_not_found_in_dynamodb():
    """Case 2: Email with agent email not found in DynamoDB"""
    print("\n=== Case 2: Agent not found in DynamoDB ===")
    
    # Generate random non-existent agent email
    non_existent_agent = f"nonexistent-{uuid.uuid4().hex[:8]}@bhaang.com"
    
    # Synthetic email data with non-existent agent
    parsed_email = {
        "subject": "Meeting Request",
        "from": ["client@example.com"],
        "to": [non_existent_agent],  # This agent doesn't exist in DynamoDB
        "cc": ["other@example.com"],
        "body": "I need to schedule a meeting. Please help.",
        "date": "2024-01-15",
        "message_id": "case2-123"
    }
    
    print(f"Email: {parsed_email['subject']}")
    print(f"From: {parsed_email['from']}")
    print(f"To: {parsed_email['to']}")
    print(f"CC: {parsed_email['cc']}")
    
    result = resolve_calendar_owner(parsed_email)
    print(f"Result: {result}")
    
    if result["status"] == "booking_agent_not_registered":
        print(f"✅ SUCCESS: Correctly identified no mapping for non-existent agent")
    else:
        print(f"❌ FAILED: Expected booking_agent_not_registered, got {result['status']}")
    
    return result


def test_case_3_agent_typo_wrong_person():
    """Case 3: Agent email exists but user is not in the email thread (typo case)"""
    print("\n=== Case 3: Agent typo - wrong person ===")
    
    # Generate random test data
    test_user_id = f"test-user-{uuid.uuid4().hex[:8]}"
    test_agent_email = f"alice-agent-{uuid.uuid4().hex[:8]}@bhaang.com"
    test_user_email = "alice@example.com"  # Alice's actual email
    
    # Setup DynamoDB test data
    table = boto3.resource('dynamodb').Table(os.getenv('USER_EMAILS_TABLE_NAME'))
    
    # Convert full email to local part for database storage
    from common_utils.email_helpers import to_local
    assist_local = to_local(test_agent_email)
    
    test_item = {
        'pk': f"uid:{test_user_id}",
        'sk': 'data',
        'user_id': test_user_id,
        'assist_email': test_agent_email,
        'assist_local': assist_local,  # Add assist_local field for GSI lookup
        'user_email': test_user_email,  # Add user_email field
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-15T10:00:00'
    }
    
    try:
        # Insert test data
        table.put_item(Item=test_item)
        print(f"✅ Created test user: {test_user_id} with agent: {test_agent_email}, user: {test_user_email}")
        
        # Synthetic email data where agent exists but user isn't in thread
        parsed_email = {
            "subject": "Meeting with Alice",
            "from": ["bob@example.com"],  # Alice is NOT in conversation
            "to": [test_agent_email],  # Alice's agent
            "cc": ["charlie@example.com"],
            "body": "Hi Alice, I'd like to schedule a meeting with you. Can you help me find a time?",
            "date": "2024-01-15",
            "message_id": "case3-123"
        }
        
        print(f"Email: {parsed_email['subject']}")
        print(f"From: {parsed_email['from']}")
        print(f"To: {parsed_email['to']}")
        print(f"CC: {parsed_email['cc']}")
        
        result = resolve_calendar_owner(parsed_email)
        print(f"Result: {result}")
        
        if result["status"] == "calendar_owner_not_in_conversation":
            print(f"✅ SUCCESS: Correctly identified that Alice is not in conversation")
        else:
            print(f"❌ FAILED: Expected calendar_owner_not_in_conversation, got {result['status']}")
        
        return result
        
    finally:
        # Cleanup test data
        table.delete_item(Key={'pk': f"uid:{test_user_id}", 'sk': 'data'})
        print(f"🧹 Cleaned up test user: {test_user_id}")


def test_case_4_two_agents_llm_disambiguation():
    """Case 4: Two agents in conversation, LLM should disambiguate based on email content"""
    print("\n=== Case 4: Two agents, LLM disambiguation ===")
    
    # Generate random test data for two agents
    test_user1_id = f"test-user-{uuid.uuid4().hex[:8]}"
    test_user2_id = f"test-user-{uuid.uuid4().hex[:8]}"
    test_agent1_email = f"marketing-agent-{uuid.uuid4().hex[:8]}@bhaang.com"
    test_agent2_email = f"sales-agent-{uuid.uuid4().hex[:8]}@bhaang.com"
    test_user1_email = "marketing@example.com"  # Marketing team email
    test_user2_email = "sales@example.com"      # Sales team email
    
    # Setup DynamoDB test data
    table = boto3.resource('dynamodb').Table(os.getenv('USER_EMAILS_TABLE_NAME'))
    
    # Convert full emails to local parts for database storage
    from common_utils.email_helpers import to_local
    assist_local1 = to_local(test_agent1_email)
    assist_local2 = to_local(test_agent2_email)
    
    test_item1 = {
        'pk': f"uid:{test_user1_id}",
        'sk': 'data',
        'user_id': test_user1_id,
        'assist_email': test_agent1_email,
        'assist_local': assist_local1,  # Add assist_local field for GSI lookup
        'user_email': test_user1_email,  # Add user_email field
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-15T10:00:00'
    }
    test_item2 = {
        'pk': f"uid:{test_user2_id}",
        'sk': 'data',
        'user_id': test_user2_id,
        'assist_email': test_agent2_email,
        'assist_local': assist_local2,  # Add assist_local field for GSI lookup
        'user_email': test_user2_email,  # Add user_email field
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-15T10:00:00'
    }
    
    try:
        # Insert test data
        table.put_item(Item=test_item1)
        table.put_item(Item=test_item2)
        print(f"✅ Created test users: {test_user1_id} ({test_agent1_email}), {test_user2_id} ({test_agent2_email})")
        
        # Synthetic email data with two agents and clear context
        parsed_email = {
            "subject": "Meeting with Marketing Team",
            "from": ["client@example.com"],
            "to": [test_agent1_email, test_agent2_email],
            "cc": ["manager@example.com", test_user1_email, test_user2_email],  # Both users in conversation
            "body": """
            Hi there,
            
            I need to schedule a meeting with the marketing team to discuss our upcoming campaign.
            We need to go over the budget, timeline, and creative direction.
            
            Can you help me find a time that works for everyone?
            
            Best regards,
            Client
            """,
            "date": "2024-01-15",
            "message_id": "case4-123"
        }
        
        print(f"Email: {parsed_email['subject']}")
        print(f"From: {parsed_email['from']}")
        print(f"To: {parsed_email['to']}")
        print(f"CC: {parsed_email['cc']}")
        print(f"Body preview: {parsed_email['body'][:100]}...")
        
        result = resolve_calendar_owner(parsed_email)
        print(f"Result: {result}")
        
        if result["status"] == "success":
            print(f"✅ SUCCESS: LLM successfully disambiguated to user {result['user_id']} with agent {result['assist_email']}")
        elif result["status"] == "multiple_owners_ambiguous":
            print(f"⚠️  PARTIAL: LLM couldn't decide between {result['candidates']}")
            print(f"Reason: {result.get('reason', 'No reason provided')}")
        else:
            print(f"❌ FAILED: {result['status']} - {result.get('reason', 'No reason provided')}")
        
        return result
        
    finally:
        # Cleanup test data
        table.delete_item(Key={'pk': f"uid:{test_user1_id}", 'sk': 'data'})
        table.delete_item(Key={'pk': f"uid:{test_user2_id}", 'sk': 'data'})
        print(f"🧹 Cleaned up test users: {test_user1_id}, {test_user2_id}")


def test_case_5_missing_user_email_field():
    """Case 5: Agent exists but user_email field is missing from database"""
    print("\n=== Case 5: Missing user_email field ===")
    
    # Generate random test data
    test_user_id = f"test-user-{uuid.uuid4().hex[:8]}"
    test_agent_email = f"missing-email-agent-{uuid.uuid4().hex[:8]}@bhaang.com"
    
    # Setup DynamoDB test data WITHOUT user_email field
    table = boto3.resource('dynamodb').Table(os.getenv('USER_EMAILS_TABLE_NAME'))
    
    # Convert full email to local part for database storage
    from common_utils.email_helpers import to_local
    assist_local = to_local(test_agent_email)
    
    test_item = {
        'pk': f"uid:{test_user_id}",
        'sk': 'data',
        'user_id': test_user_id,
        'assist_email': test_agent_email,
        'assist_local': assist_local,  # Add assist_local field for GSI lookup
        # Missing user_email field
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-15T10:00:00'
    }
    
    try:
        # Insert test data
        table.put_item(Item=test_item)
        print(f"✅ Created test user: {test_user_id} with agent: {test_agent_email} (missing user_email)")
        
        # Synthetic email data
        parsed_email = {
            "subject": "Meeting Request",
            "from": ["client@example.com"],
            "to": [test_agent_email],
            "cc": ["other@example.com"],
            "body": "I need to schedule a meeting. Please help.",
            "date": "2024-01-15",
            "message_id": "case5-123"
        }
        
        print(f"Email: {parsed_email['subject']}")
        print(f"From: {parsed_email['from']}")
        print(f"To: {parsed_email['to']}")
        print(f"CC: {parsed_email['cc']}")
        
        result = resolve_calendar_owner(parsed_email)
        print(f"Result: {result}")
        
        if result["status"] == "user_email_missing":
            print(f"✅ SUCCESS: Correctly identified missing user_email field")
        else:
            print(f"❌ FAILED: Expected user_email_missing, got {result['status']}")
        
        return result
        
    finally:
        # Cleanup test data
        table.delete_item(Key={'pk': f"uid:{test_user_id}", 'sk': 'data'})
        print(f"🧹 Cleaned up test user: {test_user_id}")


def test_case_6_typo_with_valid_agent():
    """Case 6: One typo agent + one valid agent with user in conversation = SUCCESS"""
    print("\n=== Case 6: Typo with valid agent ===")
    
    # Generate random test data
    test_user_id = f"test-user-{uuid.uuid4().hex[:8]}"
    test_agent_email = f"valid-agent-{uuid.uuid4().hex[:8]}@bhaang.com"
    test_user_email = "john.doe@example.com"  # User will be in conversation
    
    # Setup DynamoDB test data
    table = boto3.resource('dynamodb').Table(os.getenv('USER_EMAILS_TABLE_NAME'))
    
    # Convert full email to local part for database storage
    from common_utils.email_helpers import to_local
    assist_local = to_local(test_agent_email)
    
    test_item = {
        'pk': f"uid:{test_user_id}",
        'sk': 'data',
        'user_id': test_user_id,
        'assist_email': test_agent_email,
        'assist_local': assist_local,  # Add assist_local field for GSI lookup
        'user_email': test_user_email,
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-15T10:00:00'
    }
    
    try:
        # Insert test data
        table.put_item(Item=test_item)
        print(f"✅ Created test user: {test_user_id} with agent: {test_agent_email}, user: {test_user_email}")
        
        # Synthetic email data with typo + valid agent
        parsed_email = {
            "subject": "Meeting Request",
            "from": ["john.doe@example.com"],  # Valid user in conversation
            "to": [test_agent_email],  # Valid agent
            "cc": ["typo-agent@bhaang.com"],  # Typo agent (doesn't exist in DB)
            "body": "Hi, I'd like to schedule a meeting. Can you help?",
            "date": "2024-01-15",
            "message_id": "case6-123"
        }
        
        print(f"Email: {parsed_email['subject']}")
        print(f"From: {parsed_email['from']}")
        print(f"To: {parsed_email['to']}")
        print(f"CC: {parsed_email['cc']}")
        
        result = resolve_calendar_owner(parsed_email)
        print(f"Result: {result}")
        
        if result["status"] == "success":
            print(f"✅ SUCCESS: Correctly resolved to valid agent despite typo")
        else:
            print(f"❌ FAILED: Expected success, got {result['status']}")
        
        return result
        
    finally:
        # Cleanup test data
        table.delete_item(Key={'pk': f"uid:{test_user_id}", 'sk': 'data'})
        print(f"🧹 Cleaned up test user: {test_user_id}")


def test_case_7_two_agents_one_typo():
    """Case 7: Two agents, one typo (user not in conversation), one valid = SUCCESS"""
    print("\n=== Case 7: Two agents, one typo ===")
    
    # Generate random test data for two agents
    test_user1_id = f"test-user-{uuid.uuid4().hex[:8]}"
    test_user2_id = f"test-user-{uuid.uuid4().hex[:8]}"
    test_agent1_email = f"typo-agent-{uuid.uuid4().hex[:8]}@bhaang.com"
    test_agent2_email = f"valid-agent-{uuid.uuid4().hex[:8]}@bhaang.com"
    test_user1_email = "alice@example.com"  # Not in conversation (typo)
    test_user2_email = "bob@example.com"    # In conversation (valid)
    
    # Setup DynamoDB test data
    table = boto3.resource('dynamodb').Table(os.getenv('USER_EMAILS_TABLE_NAME'))
    
    # Convert full emails to local parts for database storage
    from common_utils.email_helpers import to_local
    assist_local1 = to_local(test_agent1_email)
    assist_local2 = to_local(test_agent2_email)
    
    test_item1 = {
        'pk': f"uid:{test_user1_id}",
        'sk': 'data',
        'user_id': test_user1_id,
        'assist_email': test_agent1_email,
        'assist_local': assist_local1,  # Add assist_local field for GSI lookup
        'user_email': test_user1_email,  # Alice not in conversation
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-15T10:00:00'
    }
    test_item2 = {
        'pk': f"uid:{test_user2_id}",
        'sk': 'data',
        'user_id': test_user2_id,
        'assist_email': test_agent2_email,
        'assist_local': assist_local2,  # Add assist_local field for GSI lookup
        'user_email': test_user2_email,  # Bob in conversation
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-15T10:00:00'
    }
    
    try:
        # Insert test data
        table.put_item(Item=test_item1)
        table.put_item(Item=test_item2)
        print(f"✅ Created test users: {test_user1_id} ({test_agent1_email}), {test_user2_id} ({test_agent2_email})")
        
        # Synthetic email data
        parsed_email = {
            "subject": "Meeting Request",
            "from": ["client@example.com"],
            "to": [test_agent1_email, test_agent2_email],  # Both agents
            "cc": ["bob@example.com"],  # Only Bob in conversation
            "body": "Hi, I need to schedule a meeting with Bob. Can you help?",
            "date": "2024-01-15",
            "message_id": "case7-123"
        }
        
        print(f"Email: {parsed_email['subject']}")
        print(f"From: {parsed_email['from']}")
        print(f"To: {parsed_email['to']}")
        print(f"CC: {parsed_email['cc']}")
        
        result = resolve_calendar_owner(parsed_email)
        print(f"Result: {result}")
        
        if result["status"] == "success":
            print(f"✅ SUCCESS: Correctly resolved to valid agent (Bob) despite typo agent (Alice)")
        else:
            print(f"❌ FAILED: Expected success, got {result['status']}")
        
        return result
        
    finally:
        # Cleanup test data
        table.delete_item(Key={'pk': f"uid:{test_user1_id}", 'sk': 'data'})
        table.delete_item(Key={'pk': f"uid:{test_user2_id}", 'sk': 'data'})
        print(f"🧹 Cleaned up test users: {test_user1_id}, {test_user2_id}")


def test_case_8_case_insensitive_email_matching():
    """Case 8: Test case-insensitive email matching in conversation"""
    print("\n=== Case 8: Case insensitive email matching ===")
    
    # Generate random test data
    test_user_id = f"test-user-{uuid.uuid4().hex[:8]}"
    test_agent_email = f"case-test-agent-{uuid.uuid4().hex[:8]}@bhaang.com"
    test_user_email = "John.Doe@Example.COM"  # Mixed case email
    
    # Setup DynamoDB test data
    table = boto3.resource('dynamodb').Table(os.getenv('USER_EMAILS_TABLE_NAME'))
    
    # Convert full email to local part for database storage
    from common_utils.email_helpers import to_local
    assist_local = to_local(test_agent_email)
    
    test_item = {
        'pk': f"uid:{test_user_id}",
        'sk': 'data',
        'user_id': test_user_id,
        'assist_email': test_agent_email,
        'assist_local': assist_local,  # Add assist_local field for GSI lookup
        'user_email': test_user_email,  # Mixed case
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-15T10:00:00'
    }
    
    try:
        # Insert test data
        table.put_item(Item=test_item)
        print(f"✅ Created test user: {test_user_id} with agent: {test_agent_email}, user: {test_user_email}")
        
        # Synthetic email data with different case
        parsed_email = {
            "subject": "Meeting Request",
            "from": ["john.doe@example.com"],  # Lower case version
            "to": [test_agent_email],
            "cc": ["other@example.com"],
            "body": "Hi, I'd like to schedule a meeting. Can you help?",
            "date": "2024-01-15",
            "message_id": "case8-123"
        }
        
        print(f"Email: {parsed_email['subject']}")
        print(f"From: {parsed_email['from']}")
        print(f"To: {parsed_email['to']}")
        print(f"CC: {parsed_email['cc']}")
        print(f"DB user_email: {test_user_email}")
        print(f"Conversation email: {parsed_email['from'][0]}")
        
        result = resolve_calendar_owner(parsed_email)
        print(f"Result: {result}")
        
        if result["status"] == "success":
            print(f"✅ SUCCESS: Case-insensitive matching worked correctly")
        else:
            print(f"❌ FAILED: Expected success, got {result['status']}")
        
        return result
        
    finally:
        # Cleanup test data
        table.delete_item(Key={'pk': f"uid:{test_user_id}", 'sk': 'data'})
        print(f"🧹 Cleaned up test user: {test_user_id}")


def test_case_9_email_with_display_name():
    """Case 9: Test email extraction from display name format"""
    print("\n=== Case 9: Email with display name ===")
    
    # Generate random test data
    test_user_id = f"test-user-{uuid.uuid4().hex[:8]}"
    test_agent_email = f"display-name-agent-{uuid.uuid4().hex[:8]}@bhaang.com"
    test_user_email = "john.doe@example.com"
    
    # Setup DynamoDB test data
    table = boto3.resource('dynamodb').Table(os.getenv('USER_EMAILS_TABLE_NAME'))
    
    # Convert full email to local part for database storage
    from common_utils.email_helpers import to_local
    assist_local = to_local(test_agent_email)
    
    test_item = {
        'pk': f"uid:{test_user_id}",
        'sk': 'data',
        'user_id': test_user_id,
        'assist_email': test_agent_email,
        'assist_local': assist_local,  # Add assist_local field for GSI lookup
        'user_email': test_user_email,
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-15T10:00:00'
    }
    
    try:
        # Insert test data
        table.put_item(Item=test_item)
        print(f"✅ Created test user: {test_user_id} with agent: {test_agent_email}, user: {test_user_email}")
        
        # Synthetic email data with display name format
        parsed_email = {
            "subject": "Meeting Request",
            "from": ["John Doe <john.doe@example.com>"],  # Display name format
            "to": [test_agent_email],
            "cc": ["Jane Smith <jane.smith@example.com>"],
            "body": "Hi, I'd like to schedule a meeting. Can you help?",
            "date": "2024-01-15",
            "message_id": "case9-123"
        }
        
        print(f"Email: {parsed_email['subject']}")
        print(f"From: {parsed_email['from']}")
        print(f"To: {parsed_email['to']}")
        print(f"CC: {parsed_email['cc']}")
        
        result = resolve_calendar_owner(parsed_email)
        print(f"Result: {result}")
        
        if result["status"] == "success":
            print(f"✅ SUCCESS: Email extraction from display name worked correctly")
        else:
            print(f"❌ FAILED: Expected success, got {result['status']}")
        
        return result
        
    finally:
        # Cleanup test data
        table.delete_item(Key={'pk': f"uid:{test_user_id}", 'sk': 'data'})
        print(f"🧹 Cleaned up test user: {test_user_id}")


def test_case_10_all_agents_typos():
    """Case 10: All agents are typos (users not in conversation) = FAILURE"""
    print("\n=== Case 10: All agents are typos ===")
    
    # Generate random test data for two agents
    test_user1_id = f"test-user-{uuid.uuid4().hex[:8]}"
    test_user2_id = f"test-user-{uuid.uuid4().hex[:8]}"
    test_agent1_email = f"typo1-agent-{uuid.uuid4().hex[:8]}@bhaang.com"
    test_agent2_email = f"typo2-agent-{uuid.uuid4().hex[:8]}@bhaang.com"
    test_user1_email = "alice@example.com"  # Not in conversation
    test_user2_email = "bob@example.com"    # Not in conversation
    
    # Setup DynamoDB test data
    table = boto3.resource('dynamodb').Table(os.getenv('USER_EMAILS_TABLE_NAME'))
    
    # Convert full emails to local parts for database storage
    from common_utils.email_helpers import to_local
    assist_local1 = to_local(test_agent1_email)
    assist_local2 = to_local(test_agent2_email)
    
    test_item1 = {
        'pk': f"uid:{test_user1_id}",
        'sk': 'data',
        'user_id': test_user1_id,
        'assist_email': test_agent1_email,
        'assist_local': assist_local1,  # Add assist_local field for GSI lookup
        'user_email': test_user1_email,
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-15T10:00:00'
    }
    test_item2 = {
        'pk': f"uid:{test_user2_id}",
        'sk': 'data',
        'user_id': test_user2_id,
        'assist_email': test_agent2_email,
        'assist_local': assist_local2,  # Add assist_local field for GSI lookup
        'user_email': test_user2_email,
        'created_at': '2024-01-15T10:00:00',
        'updated_at': '2024-01-15T10:00:00'
    }
    
    try:
        # Insert test data
        table.put_item(Item=test_item1)
        table.put_item(Item=test_item2)
        print(f"✅ Created test users: {test_user1_id} ({test_agent1_email}), {test_user2_id} ({test_agent2_email})")
        
        # Synthetic email data where neither user is in conversation
        parsed_email = {
            "subject": "Meeting Request",
            "from": ["client@example.com"],  # Neither Alice nor Bob in conversation
            "to": [test_agent1_email, test_agent2_email],
            "cc": ["other@example.com"],
            "body": "Hi, I need to schedule a meeting. Can you help?",
            "date": "2024-01-15",
            "message_id": "case10-123"
        }
        
        print(f"Email: {parsed_email['subject']}")
        print(f"From: {parsed_email['from']}")
        print(f"To: {parsed_email['to']}")
        print(f"CC: {parsed_email['cc']}")
        
        result = resolve_calendar_owner(parsed_email)
        print(f"Result: {result}")
        
        if result["status"] == "calendar_owner_not_in_conversation":
            print(f"✅ SUCCESS: Correctly identified that no calendar owners are in conversation")
        else:
            print(f"❌ FAILED: Expected calendar_owner_not_in_conversation, got {result['status']}")
        
        return result
        
    finally:
        # Cleanup test data
        table.delete_item(Key={'pk': f"uid:{test_user1_id}", 'sk': 'data'})
        table.delete_item(Key={'pk': f"uid:{test_user2_id}", 'sk': 'data'})
        print(f"🧹 Cleaned up test users: {test_user1_id}, {test_user2_id}")


if __name__ == '__main__':
    print("Running calendar owner resolver integration tests...")
    print("These tests use real AWS services - ensure you have proper credentials configured.")
    print()
    
    # Run all integration tests
    test_case_1_single_agent_user_in_thread()
    test_case_2_agent_not_found_in_dynamodb()
    test_case_3_agent_typo_wrong_person()
    test_case_4_two_agents_llm_disambiguation()
    test_case_5_missing_user_email_field()
    test_case_6_typo_with_valid_agent()
    test_case_7_two_agents_one_typo()
    test_case_8_case_insensitive_email_matching()
    test_case_9_email_with_display_name()
    test_case_10_all_agents_typos()
    
    print("\n✅ All integration tests completed!") 