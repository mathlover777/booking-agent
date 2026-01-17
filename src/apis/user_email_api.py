import json
import os
import boto3
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from common_utils.clerk_utils import get_user_primary_email

from common_utils import aws_utils

# Configure logging
logger = logging.getLogger(__name__)

# Get table from aws_utils
table = aws_utils.user_emails_table

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for user email API
    Supports GET and PUT operations for user concierge emails
    """
    try:
        # Extract user ID from the authorizer context
        user_id = event.get('requestContext', {}).get('authorizer', {}).get('user_id')
        if not user_id:
            return create_error_response(401, "Unauthorized - No user ID found")

        # Get HTTP method
        http_method = event.get('httpMethod', '').upper()
        
        if http_method == 'GET':
            return get_user_email(user_id)
        elif http_method == 'PUT':
            return update_user_email(user_id, event)
        elif http_method == 'POST':
            return check_email_availability(user_id, event)
        else:
            return create_error_response(405, f"Method {http_method} not allowed")
            
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return create_error_response(500, "Internal server error")


def get_user_email(user_id: str) -> Dict[str, Any]:
    """
    Get user's concierge email from DynamoDB
    """
    try:
        pk = f"uid:{user_id}"
        sk = "data"
        
        response = table.get_item(
            Key={
                'pk': pk,
                'sk': sk
            }
        )
        
        item = response.get('Item')
        if not item:
            return create_error_response(404, "User email not found")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'GET,PUT,POST,OPTIONS'
            },
            'body': json.dumps({
                'user_id': user_id,
                'assist_local': item.get('assist_local'),
                'user_email': item.get('user_email'),
                'created_at': item.get('created_at'),
                'updated_at': item.get('updated_at')
            })
        }
        
    except Exception as e:
        logger.error(f"Error getting user email: {str(e)}")
        return create_error_response(500, "Error retrieving user email")


def update_user_email(user_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update user's concierge email in DynamoDB
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        assist_local = body.get('assist_local')

        if not assist_local:
            return create_error_response(400, "assist_local is required")

        # Basic validation for local part
        if not assist_local.strip() or len(assist_local.strip()) < 1:
            return create_error_response(400, "Invalid assist_local format")

        # Clean and normalize the local part
        assist_local = assist_local.strip().lower()

        # Get user's primary email from Clerk
        user_email = get_user_primary_email(user_id)
        if not user_email:
            logger.warning(f"Could not fetch primary email for user {user_id}, proceeding without it")
            # Continue without user_email - it can be added later

        # Prepare keys and timestamp
        pk = f"uid:{user_id}"
        sk = "data"
        now = datetime.now(timezone.utc).isoformat()
        
        # Check if email already exists for another user using GSI
        email_check_response = table.query(
            IndexName="assist_local-index",
            KeyConditionExpression="assist_local = :local",
            ExpressionAttributeValues={
                ':local': assist_local
            }
        )
        
        existing_email_items = email_check_response.get('Items', [])
        
        # Filter out the current user's record if it exists
        other_users_with_email = [
            item for item in existing_email_items 
            if item.get('user_id') != user_id
        ]
        
        if other_users_with_email:
            return create_error_response(409, "Email already exists for another user")
        
        # Check if user already exists
        existing_response = table.get_item(
            Key={
                'pk': pk,
                'sk': sk
            }
        )
        
        existing_item = existing_response.get('Item')
        
        if existing_item:
            # Update existing user
            update_expression = 'SET assist_local = :local, updated_at = :updated_at'
            expression_values = {
                ':local': assist_local,
                ':updated_at': now
            }
            
            # Add user_email to update if we have it
            if user_email:
                update_expression += ', user_email = :user_email'
                expression_values[':user_email'] = user_email
            
            response = table.update_item(
                Key={
                    'pk': pk,
                    'sk': sk
                },
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values,
                ReturnValues='ALL_NEW'
            )
        else:
            # Create new user
            item_data = {
                'pk': pk,
                'sk': sk,
                'user_id': user_id,
                'assist_local': assist_local,
                'created_at': now,
                'updated_at': now
            }
            
            # Add user_email if we have it
            if user_email:
                item_data['user_email'] = user_email
            
            response = table.put_item(Item=item_data)
            # For put_item, we need to get the item back
            response = table.get_item(
                Key={
                    'pk': pk,
                    'sk': sk
                }
            )
        
        item = response.get('Item') or response.get('Attributes')
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'GET,PUT,POST,OPTIONS'
            },
            'body': json.dumps({
                'user_id': user_id,
                'assist_local': item.get('assist_local'),
                'user_email': item.get('user_email'),
                'created_at': item.get('created_at'),
                'updated_at': item.get('updated_at'),
                'message': 'User email updated successfully'
            })
        }
        
    except json.JSONDecodeError:
        return create_error_response(400, "Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Error updating user email: {str(e)}")
        return create_error_response(500, "Error updating user email")


def check_email_availability(user_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check if an email is available for use by the current user
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        assist_local = body.get('assist_local')
        
        if not assist_local:
            return create_error_response(400, "assist_local is required")
        
        # Basic validation for local part
        if not assist_local.strip() or len(assist_local.strip()) < 1:
            return create_error_response(400, "Invalid assist_local format")
        
        # Clean and normalize the local part
        assist_local = assist_local.strip().lower()
        
        # Check if email already exists for another user using GSI
        email_check_response = table.query(
            IndexName="assist_local-index",
            KeyConditionExpression="assist_local = :local",
            ExpressionAttributeValues={
                ':local': assist_local
            }
        )
        
        existing_email_items = email_check_response.get('Items', [])
        
        # Filter out the current user's record if it exists
        other_users_with_email = [
            item for item in existing_email_items 
            if item.get('user_id') != user_id
        ]
        
        is_available = len(other_users_with_email) == 0
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'GET,PUT,POST,OPTIONS'
            },
            'body': json.dumps({
                'assist_local': assist_local,
                'available': is_available,
                'message': 'Email is available' if is_available else 'Email is already in use by another user'
            })
        }
        
    except json.JSONDecodeError:
        return create_error_response(400, "Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Error checking email availability: {str(e)}")
        return create_error_response(500, "Error checking email availability")


def create_error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Create a standardized error response
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,PUT,POST,OPTIONS'
        },
        'body': json.dumps({
            'error': message
        })
    } 