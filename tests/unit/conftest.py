"""
Common pytest configuration and fixtures for the Vibes project unit tests.
"""
import pytest
import os
import sys
from unittest.mock import patch, Mock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


@pytest.fixture(autouse=True)
def mock_aws_services():
    """Automatically mock AWS services for all tests"""
    with patch('boto3.client') as mock_boto3_client:
        # Mock Secrets Manager
        mock_secrets = Mock()
        mock_secrets.get_secret_value.return_value = {
            'SecretString': '{"CLERK_SECRET_KEY": "test_clerk_secret"}'
        }
        
        # Mock S3
        mock_s3 = Mock()
        mock_s3.get_object.return_value = {
            'Body': Mock(read=lambda: b'test content')
        }
        
        # Configure boto3.client to return appropriate mocks
        def mock_client(service_name, *args, **kwargs):
            if service_name == 'secretsmanager':
                return mock_secrets
            elif service_name == 's3':
                return mock_s3
            else:
                return Mock()
        
        mock_boto3_client.side_effect = mock_client
        yield mock_boto3_client


@pytest.fixture(autouse=True)
def mock_environment_variables():
    """Automatically mock environment variables for all tests"""
    env_vars = {
        'AWS_REGION': 'us-east-1',
        'AWS_PROFILE': 'test',
        'ENVIRONMENT': 'test',
        'CLERK_SECRET_KEY': 'test_clerk_secret',
        'GOOGLE_CLIENT_ID': 'test_google_client_id',
        'GOOGLE_CLIENT_SECRET': 'test_google_client_secret'
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def mock_requests():
    """Mock requests library for HTTP calls"""
    with patch('requests.get') as mock_get, \
         patch('requests.post') as mock_post, \
         patch('requests.delete') as mock_delete, \
         patch('requests.put') as mock_put:
        
        # Default successful responses
        mock_get.return_value = Mock(status_code=200, json=lambda: {})
        mock_post.return_value = Mock(status_code=200, json=lambda: {})
        mock_delete.return_value = Mock(status_code=204, json=lambda: {})
        mock_put.return_value = Mock(status_code=200, json=lambda: {})
        
        yield {
            'get': mock_get,
            'post': mock_post,
            'delete': mock_delete,
            'put': mock_put
        }


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing"""
    return "user_test_123"


@pytest.fixture
def sample_event_id():
    """Sample event ID for testing"""
    return "event_test_123"


@pytest.fixture
def sample_oauth_token():
    """Sample OAuth token for testing"""
    return "test_oauth_token_12345" 