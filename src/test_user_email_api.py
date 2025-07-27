#!/usr/bin/env python3
"""
Test script for user email API Lambda function
"""
from dotenv import load_dotenv
load_dotenv('../.env.base', override=True)
load_dotenv('../.env.dev', override=True)
import os
STAGE = os.environ.get('STAGE', 'dev')
os.environ['USER_EMAILS_TABLE_NAME'] = f'vibes-user-emails-{STAGE}'

import json

import requests
from user_email_api import lambda_handler


user_id = "user_2zTBVQZOK5QCyxL43QTVOHOw3zK" #souravsarkar1729

def generate_clerk_jwt_token(user_id: str) -> str:
    """
    Generate a JWT token using Clerk's API for testing purposes
    
    Args:
        user_id: The user ID to create a session for
        
    Returns:
        JWT token string
    """
    print(f"🔑 [DEBUG] Generating JWT token for user: {user_id}")
    
    try:
        # Get secrets from the same source as clerk_util
        import boto3
        secrets_client = boto3.client('secretsmanager')
        response = secrets_client.get_secret_value(SecretId=f"{STAGE}/vibecal")
        secrets = json.loads(response['SecretString'])
        clerk_secret_key = secrets["CLERK_SECRET_KEY"]
        
        # Step 1: Create a session
        session_url = "https://api.clerk.com/v1/sessions"
        session_headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {clerk_secret_key}'
        }
        session_data = {
            'user_id': user_id
        }
        
        print(f"🔑 [DEBUG] Creating session for user: {user_id}")
        session_response = requests.post(
            session_url, 
            headers=session_headers, 
            json=session_data, 
            timeout=30
        )
        session_response.raise_for_status()
        session_data = session_response.json()
        session_id = session_data['id']
        print(f"🔑 [DEBUG] Created session with ID: {session_id}")
        
        # Step 2: Create a JWT token
        token_url = f"https://api.clerk.com/v1/sessions/{session_id}/tokens"
        token_headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {clerk_secret_key}'
        }
        token_data = {
            'expires_in_seconds': 3600  # 1 hour
        }
        
        print(f"🔑 [DEBUG] Creating JWT token for session: {session_id}")
        token_response = requests.post(
            token_url, 
            headers=token_headers, 
            json=token_data, 
            timeout=30
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        jwt_token = token_data['jwt']
        print(f"🔑 [DEBUG] Successfully generated JWT token")
        
        return jwt_token
        
    except Exception as e:
        print(f"❌ [DEBUG] Error generating JWT token: {e}")
        raise Exception(f"Failed to generate JWT token: {str(e)}")


def test_get_user_email():
    """Test GET /user/email endpoint"""
    print("Testing GET /user/email...")
    
    # Mock event for GET request
    event = {
        'httpMethod': 'GET',
        'requestContext': {
            'authorizer': {
                'user_id': user_id
            }
        }
    }
    
    # Set environment variables for testing
    os.environ['USER_EMAILS_TABLE_NAME'] = 'vibes-user-emails-dev'
    os.environ['LOG_LEVEL'] = 'INFO'
    
    try:
        response = lambda_handler(event, None)
        print(f"Response: {json.dumps(response, indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")


def test_update_user_email():
    """Test PUT /user/email endpoint"""
    print("\nTesting PUT /user/email...")
    
    # Mock event for PUT request
    event = {
        'httpMethod': 'PUT',
        'requestContext': {
            'authorizer': {
                'user_id': user_id
            }
        },
        'body': json.dumps({
            'assist_email': 'test@example.com'
        })
    }
    
    os.environ['LOG_LEVEL'] = 'INFO'
    
    try:
        response = lambda_handler(event, None)
        print(f"Response: {json.dumps(response, indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")


def test_jwt_authorizer():
    """Test JWT authorizer function"""
    print("\nTesting JWT Authorizer...")
    
    from jwt_authorizer import lambda_handler as auth_handler
    
    try:
        # Generate a proper JWT token using Clerk's API
        print(f"🔑 [DEBUG] Generating JWT token for user: {user_id}")
        jwt_token = generate_clerk_jwt_token(user_id)
        print(f"🔑 [DEBUG] Generated JWT token: {jwt_token[:50]}...")
        
        # Mock event for authorizer with real JWT token
        event = {
            'headers': {
                'Authorization': f'Bearer {jwt_token}'
            },
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:api123/test/GET/user/email'
        }
        
        # Set environment variables for testing
        # Note: We need to get the actual JWKS public key from Clerk
        # For now, we'll use a placeholder - in production this should be fetched from Clerk's JWKS endpoint
        os.environ['LOG_LEVEL'] = 'INFO'
        
        response = auth_handler(event, None)
        print(f"Response: {json.dumps(response, indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    print("Testing User Email API Lambda Functions")
    print("=" * 50)
    
    test_get_user_email()
    test_update_user_email()
    test_jwt_authorizer()
    
    print("\nTests completed!") 