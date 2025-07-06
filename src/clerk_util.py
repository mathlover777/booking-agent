import json
import boto3
import os
import requests
from typing import Dict, Any

# Global variables
STAGE = os.environ['STAGE']
secrets_client = boto3.client('secretsmanager')
response = secrets_client.get_secret_value(SecretId=f"{STAGE}/vibecal")
_secrets = json.loads(response['SecretString'])


def get_google_oauth_token(user_id: str) -> Dict[str, Any]:
    """Retrieve Google OAuth token for a user from Clerk API"""
    url = f"https://api.clerk.com/v1/users/{user_id}/oauth_access_tokens/oauth_google"
    headers = {'Authorization': f'Bearer {_secrets["CLERK_SECRET_KEY"]}'}
    params = {'limit': 10, 'offset': 0}
    
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    return data[0]["token"] if data else None 