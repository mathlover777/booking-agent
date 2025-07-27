import json
import os
import boto3
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')))
logger = logging.getLogger(__name__)

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table_name = os.getenv('USER_EMAILS_TABLE_NAME')
table = dynamodb.Table(table_name)


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
                'Access-Control-Allow-Methods': 'GET,PUT,OPTIONS'
            },
            'body': json.dumps({
                'user_id': user_id,
                'assist_email': item.get('assist_email'),
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
        assist_email = body.get('assist_email')
        
        if not assist_email:
            return create_error_response(400, "assist_email is required")
        
        # Validate email format (basic validation)
        if '@' not in assist_email or '.' not in assist_email:
            return create_error_response(400, "Invalid email format")
        
        pk = f"uid:{user_id}"
        sk = "data"
        now = datetime.utcnow().isoformat()
        
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
            response = table.update_item(
                Key={
                    'pk': pk,
                    'sk': sk
                },
                UpdateExpression='SET assist_email = :email, updated_at = :updated_at',
                ExpressionAttributeValues={
                    ':email': assist_email,
                    ':updated_at': now
                },
                ReturnValues='ALL_NEW'
            )
        else:
            # Create new user
            response = table.put_item(
                Item={
                    'pk': pk,
                    'sk': sk,
                    'user_id': user_id,
                    'assist_email': assist_email,
                    'created_at': now,
                    'updated_at': now
                }
            )
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
                'Access-Control-Allow-Methods': 'GET,PUT,OPTIONS'
            },
            'body': json.dumps({
                'user_id': user_id,
                'assist_email': item.get('assist_email'),
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
            'Access-Control-Allow-Methods': 'GET,PUT,OPTIONS'
        },
        'body': json.dumps({
            'error': message
        })
    } 