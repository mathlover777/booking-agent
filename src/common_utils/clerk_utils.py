import requests
import logging
from typing import Dict, Any, Optional
from .aws_utils import _secrets

logger = logging.getLogger(__name__)

def get_user_info(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch user information from Clerk API using the user ID.
    
    Args:
        user_id: The Clerk user ID
        
    Returns:
        User information dictionary or None if failed
    """
    try:
        clerk_secret_key = _secrets.get("CLERK_SECRET_KEY")
        if not clerk_secret_key:
            logger.error("CLERK_SECRET_KEY not found in secrets")
            return None
            
        url = f"https://api.clerk.com/v1/users/{user_id}"
        headers = {
            'Authorization': f'Bearer {clerk_secret_key}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        user_data = response.json()
        logger.debug(f"Retrieved user data for {user_id}: {user_data.get('email_addresses', [])}")
        
        return user_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch user info from Clerk API: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching user info: {str(e)}")
        return None

def get_user_primary_email(user_id: str) -> Optional[str]:
    """
    Get the primary email address for a user from Clerk.
    
    Args:
        user_id: The Clerk user ID
        
    Returns:
        Primary email address or None if not found
    """
    user_info = get_user_info(user_id)
    if not user_info:
        return None
    
    email_addresses = user_info.get('email_addresses', [])
    if not email_addresses:
        logger.warning(f"No email addresses found for user {user_id}")
        return None
    
    # Get the first email address (primary)
    primary_email = email_addresses[0].get('email_address')
    if not primary_email:
        logger.warning(f"Primary email address is empty for user {user_id}")
        return None
    
    logger.info(f"Retrieved primary email {primary_email} for user {user_id}")
    return primary_email 