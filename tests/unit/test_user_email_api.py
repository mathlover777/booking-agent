import pytest
import json
import sys
import os
from unittest.mock import patch, Mock
from datetime import datetime, timezone

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from apis.user_email_api import (
    lambda_handler, 
    get_user_email, 
    update_user_email, 
    check_email_availability,
    create_error_response
)


class TestUserEmailAPI:
    """Test suite for user email API"""
    
    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID for testing"""
        return "user_test_123"
    
    @pytest.fixture
    def sample_event_base(self, sample_user_id):
        """Base API Gateway event for testing"""
        return {
            'requestContext': {
                'authorizer': {
                    'user_id': sample_user_id
                }
            },
            'httpMethod': 'GET',
            'headers': {
                'Content-Type': 'application/json'
            }
        }
    
    @pytest.fixture
    def sample_dynamodb_item(self, sample_user_id):
        """Sample DynamoDB item for testing"""
        return {
            'pk': f'uid:{sample_user_id}',
            'sk': 'data',
            'user_id': sample_user_id,
            'assist_local': 'testuser',
            'user_email': 'test@example.com',
            'created_at': '2024-01-15T10:00:00Z',
            'updated_at': '2024-01-15T10:00:00Z'
        }
    
    @pytest.fixture
    def mock_table(self):
        """Mock DynamoDB table"""
        with patch('apis.user_email_api.table') as mock_table:
            yield mock_table

    def test_create_error_response(self):
        """Test creating error response"""
        response = create_error_response(400, "Bad Request")
        
        assert response['statusCode'] == 400
        assert response['headers']['Content-Type'] == 'application/json'
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
        
        body = json.loads(response['body'])
        assert body['error'] == "Bad Request"

    def test_lambda_handler_get_success(self, sample_event_base, sample_dynamodb_item, mock_table):
        """Test successful GET request"""
        mock_table.get_item.return_value = {'Item': sample_dynamodb_item}
        
        result = lambda_handler(sample_event_base, {})
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['user_id'] == 'user_test_123'
        assert body['assist_local'] == 'testuser'
        assert body['user_email'] == 'test@example.com'

    def test_lambda_handler_put_success(self, sample_event_base, sample_dynamodb_item, mock_table):
        """Test successful PUT request"""
        event = sample_event_base.copy()
        event['httpMethod'] = 'PUT'
        event['body'] = json.dumps({'assist_local': 'newuser'})
        
        mock_table.get_item.return_value = {'Item': sample_dynamodb_item}
        mock_table.update_item.return_value = {'Attributes': sample_dynamodb_item}
        
        with patch('apis.user_email_api.get_user_primary_email') as mock_get_email:
            mock_get_email.return_value = 'test@example.com'
            result = lambda_handler(event, {})
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['message'] == 'User email updated successfully'

    def test_lambda_handler_post_success(self, sample_event_base, mock_table):
        """Test successful POST request for email availability check"""
        event = sample_event_base.copy()
        event['httpMethod'] = 'POST'
        event['body'] = json.dumps({'assist_local': 'newuser'})
        
        mock_table.query.return_value = {'Items': []}
        
        result = lambda_handler(event, {})
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['available'] is True

    def test_lambda_handler_no_user_id(self, sample_event_base):
        """Test request without user ID in authorizer context"""
        event = sample_event_base.copy()
        event['requestContext']['authorizer'] = {}
        
        result = lambda_handler(event, {})
        
        assert result['statusCode'] == 401
        body = json.loads(result['body'])
        assert "Unauthorized" in body['error']

    def test_lambda_handler_method_not_allowed(self, sample_event_base):
        """Test request with unsupported HTTP method"""
        event = sample_event_base.copy()
        event['httpMethod'] = 'DELETE'
        
        result = lambda_handler(event, {})
        
        assert result['statusCode'] == 405
        body = json.loads(result['body'])
        assert "Method DELETE not allowed" in body['error']

    def test_lambda_handler_exception(self, sample_event_base, mock_table):
        """Test handler with exception"""
        mock_table.get_item.side_effect = Exception("DynamoDB error")
        
        result = lambda_handler(sample_event_base, {})
        
        assert result['statusCode'] == 500
        body = json.loads(result['body'])
        assert "Error retrieving user email" in body['error']

    def test_get_user_email_success(self, sample_user_id, sample_dynamodb_item, mock_table):
        """Test successful get user email"""
        mock_table.get_item.return_value = {'Item': sample_dynamodb_item}
        
        result = get_user_email(sample_user_id)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['user_id'] == sample_user_id
        assert body['assist_local'] == 'testuser'
        assert body['user_email'] == 'test@example.com'

    def test_get_user_email_not_found(self, sample_user_id, mock_table):
        """Test get user email when user doesn't exist"""
        mock_table.get_item.return_value = {}
        
        result = get_user_email(sample_user_id)
        
        assert result['statusCode'] == 404
        body = json.loads(result['body'])
        assert "User email not found" in body['error']

    def test_get_user_email_exception(self, sample_user_id, mock_table):
        """Test get user email with exception"""
        mock_table.get_item.side_effect = Exception("DynamoDB error")
        
        result = get_user_email(sample_user_id)
        
        assert result['statusCode'] == 500
        body = json.loads(result['body'])
        assert "Error retrieving user email" in body['error']

    @patch('apis.user_email_api.get_user_primary_email')
    def test_update_user_email_success_new_user(self, mock_get_email, sample_user_id, sample_dynamodb_item, mock_table):
        """Test successful update for new user"""
        mock_get_email.return_value = 'test@example.com'
        mock_table.get_item.return_value = {}  # User doesn't exist
        mock_table.put_item.return_value = {}
        mock_table.get_item.side_effect = [
            {},  # First call returns empty (user doesn't exist)
            {'Item': sample_dynamodb_item}  # Second call returns the created item
        ]
        
        event = {'body': json.dumps({'assist_local': 'newuser'})}
        
        result = update_user_email(sample_user_id, event)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['message'] == 'User email updated successfully'
        mock_table.put_item.assert_called_once()

    @patch('apis.user_email_api.get_user_primary_email')
    def test_update_user_email_success_existing_user(self, mock_get_email, sample_user_id, sample_dynamodb_item, mock_table):
        """Test successful update for existing user"""
        mock_get_email.return_value = 'test@example.com'
        mock_table.get_item.return_value = {'Item': sample_dynamodb_item}
        mock_table.update_item.return_value = {'Attributes': sample_dynamodb_item}
        
        event = {'body': json.dumps({'assist_local': 'updateduser'})}
        
        result = update_user_email(sample_user_id, event)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['message'] == 'User email updated successfully'
        mock_table.update_item.assert_called_once()

    def test_update_user_email_missing_assist_local(self, sample_user_id):
        """Test update with missing assist_local"""
        event = {'body': json.dumps({})}
        
        result = update_user_email(sample_user_id, event)
        
        assert result['statusCode'] == 400
        body = json.loads(result['body'])
        assert "assist_local is required" in body['error']

    def test_update_user_email_invalid_assist_local(self, sample_user_id):
        """Test update with invalid assist_local"""
        event = {'body': json.dumps({'assist_local': ''})}
        
        result = update_user_email(sample_user_id, event)
        
        assert result['statusCode'] == 400
        body = json.loads(result['body'])
        assert "assist_local is required" in body['error']

    @patch('apis.user_email_api.get_user_primary_email')
    def test_update_user_email_email_conflict(self, mock_get_email, sample_user_id, mock_table):
        """Test update with email already in use by another user"""
        mock_get_email.return_value = 'test@example.com'
        mock_table.query.return_value = {
            'Items': [
                {'user_id': 'other_user', 'assist_local': 'newuser'}
            ]
        }
        
        event = {'body': json.dumps({'assist_local': 'newuser'})}
        
        result = update_user_email(sample_user_id, event)
        
        assert result['statusCode'] == 409
        body = json.loads(result['body'])
        assert "Email already exists for another user" in body['error']

    def test_update_user_email_invalid_json(self, sample_user_id):
        """Test update with invalid JSON"""
        event = {'body': 'invalid json'}
        
        result = update_user_email(sample_user_id, event)
        
        assert result['statusCode'] == 400
        body = json.loads(result['body'])
        assert "Invalid JSON in request body" in body['error']

    @patch('apis.user_email_api.get_user_primary_email')
    def test_update_user_email_exception(self, mock_get_email, sample_user_id, mock_table):
        """Test update with exception"""
        mock_get_email.return_value = 'test@example.com'
        mock_table.get_item.side_effect = Exception("DynamoDB error")
        
        event = {'body': json.dumps({'assist_local': 'newuser'})}
        
        result = update_user_email(sample_user_id, event)
        
        assert result['statusCode'] == 500
        body = json.loads(result['body'])
        assert "Error updating user email" in body['error']

    def test_check_email_availability_success_available(self, sample_user_id, mock_table):
        """Test successful email availability check - available"""
        mock_table.query.return_value = {'Items': []}
        
        event = {'body': json.dumps({'assist_local': 'newuser'})}
        
        result = check_email_availability(sample_user_id, event)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['available'] is True
        assert "Email is available" in body['message']

    def test_check_email_availability_success_not_available(self, sample_user_id, mock_table):
        """Test successful email availability check - not available"""
        mock_table.query.return_value = {
            'Items': [
                {'user_id': 'other_user', 'assist_local': 'newuser'}
            ]
        }
        
        event = {'body': json.dumps({'assist_local': 'newuser'})}
        
        result = check_email_availability(sample_user_id, event)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['available'] is False
        assert "Email is already in use" in body['message']

    def test_check_email_availability_own_email(self, sample_user_id, mock_table):
        """Test email availability check for user's own email"""
        mock_table.query.return_value = {
            'Items': [
                {'user_id': sample_user_id, 'assist_local': 'newuser'}
            ]
        }
        
        event = {'body': json.dumps({'assist_local': 'newuser'})}
        
        result = check_email_availability(sample_user_id, event)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['available'] is True  # Should be available since it's their own email

    def test_check_email_availability_missing_assist_local(self, sample_user_id):
        """Test availability check with missing assist_local"""
        event = {'body': json.dumps({})}
        
        result = check_email_availability(sample_user_id, event)
        
        assert result['statusCode'] == 400
        body = json.loads(result['body'])
        assert "assist_local is required" in body['error']

    def test_check_email_availability_invalid_assist_local(self, sample_user_id):
        """Test availability check with invalid assist_local"""
        event = {'body': json.dumps({'assist_local': ''})}
        
        result = check_email_availability(sample_user_id, event)
        
        assert result['statusCode'] == 400
        body = json.loads(result['body'])
        assert "assist_local is required" in body['error']

    def test_check_email_availability_invalid_json(self, sample_user_id):
        """Test availability check with invalid JSON"""
        event = {'body': 'invalid json'}
        
        result = check_email_availability(sample_user_id, event)
        
        assert result['statusCode'] == 400
        body = json.loads(result['body'])
        assert "Invalid JSON in request body" in body['error']

    def test_check_email_availability_exception(self, sample_user_id, mock_table):
        """Test availability check with exception"""
        mock_table.query.side_effect = Exception("DynamoDB error")
        
        event = {'body': json.dumps({'assist_local': 'newuser'})}
        
        result = check_email_availability(sample_user_id, event)
        
        assert result['statusCode'] == 500
        body = json.loads(result['body'])
        assert "Error checking email availability" in body['error'] 