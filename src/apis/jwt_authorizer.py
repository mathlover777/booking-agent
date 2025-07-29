import json
import os
import jwt
import logging
from typing import Dict, Any, Optional

from common_utils import aws_utils

# Configure logging
logger = logging.getLogger(__name__)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda authorizer for JWT token validation
    Validates Clerk JWT tokens and returns user information
    """
    try:
        # Extract token from authorizationToken
        auth_header = event.get('authorizationToken', '')
        if not auth_header.startswith('Bearer '):
            logger.warning("No Bearer token found in authorizationToken")
            return generate_policy('user', 'Deny', event['methodArn'])
        
        token = auth_header.split(' ')[1]
        
        # Validate JWT token
        user_id = validate_jwt_token(token)
        if not user_id:
            logger.warning("Invalid JWT token")
            return generate_policy('user', 'Deny', event['methodArn'])
        
        # Generate allow policy with user context
        # Extract the base ARN and add wildcard for all resources
        method_arn = event['methodArn']
        base_arn = '/'.join(method_arn.split('/')[:-3]) + '/*'
        
        policy = generate_policy('user', 'Allow', base_arn)
        policy['context'] = {
            'user_id': user_id
        }
        
        logger.info(f"Successfully authorized user: {user_id}")
        return policy
        
    except Exception as e:
        logger.error(f"Error in JWT authorizer: {str(e)}")
        return generate_policy('user', 'Deny', event['methodArn'])


def validate_jwt_token(token: str) -> Optional[str]:
    """
    Validate JWT token using Clerk JWKS
    Returns user_id if valid, None otherwise
    """
    try:
        # Get JWKS public key from environment
        jwks_public_key = os.getenv('JWKS_PUBLIC_KEY')
        if not jwks_public_key:
            logger.error("JWKS_PUBLIC_KEY not found in environment")
            return None
        
        # Decode token without verification first to get header
        unverified_header = jwt.get_unverified_header(token)
        if not unverified_header:
            logger.error("Could not decode JWT header")
            return None
        
        # Verify and decode the token
        # Note: In production, you should fetch the JWKS from Clerk's endpoint
        # and verify against the correct key based on the 'kid' in the header
        # For now, we'll use the provided public key
        try:
            payload = jwt.decode(
                token,
                jwks_public_key,
                algorithms=['RS256'],
                audience=None,  # Add your Clerk audience if needed
                issuer=None,    # Add your Clerk issuer if needed
                options={
                    'verify_signature': True,
                    'verify_exp': True,
                    'verify_iat': True
                }
            )
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except jwt.InvalidSignatureError:
            logger.warning("JWT token has invalid signature")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {str(e)}")
            return None
        
        # Extract user ID from payload
        # Clerk typically stores user ID in 'sub' claim
        user_id = payload.get('sub')
        if not user_id:
            logger.warning("No user ID found in JWT payload")
            return None
        
        logger.info(f"Successfully validated JWT for user: {user_id}")
        return user_id
        
    except Exception as e:
        logger.error(f"Error validating JWT token: {str(e)}")
        return None


def generate_policy(principal_id: str, effect: str, resource: str) -> Dict[str, Any]:
    """
    Generate IAM policy for API Gateway authorizer
    """
    policy = {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': resource
                }
            ]
        }
    }
    
    return policy 