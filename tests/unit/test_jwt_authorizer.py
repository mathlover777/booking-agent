import pytest
import json
import sys
import os
from unittest.mock import patch, Mock
import jwt

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from apis.jwt_authorizer import lambda_handler, validate_jwt_token, generate_policy


class TestJWTAuthorizer:
    """Test suite for JWT authorizer"""
    
    @pytest.fixture
    def sample_jwt_token(self):
        """Sample JWT token for testing"""
        return "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyX3Rlc3RfMTIzIiwiaWF0IjoxNTE2MjM5MDIyfQ.test_signature"
    
    @pytest.fixture
    def sample_event(self):
        """Sample API Gateway event for testing"""
        return {
            'authorizationToken': 'Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyX3Rlc3RfMTIzIiwiaWF0IjoxNTE2MjM5MDIyfQ.test_signature',
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789012:abc123def4/PROD/GET/user/email'
        }
    
    @pytest.fixture
    def mock_jwks_public_key(self):
        """Mock JWKS public key"""
        return "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...\n-----END PUBLIC KEY-----"
    
    @pytest.fixture
    def mock_jwt_payload(self):
        """Mock JWT payload"""
        return {
            'sub': 'user_test_123',
            'iat': 1516239022,
            'exp': 1516242622
        }

    def test_generate_policy_allow(self):
        """Test generating allow policy"""
        policy = generate_policy('user_test_123', 'Allow', 'arn:aws:execute-api:us-east-1:123456789012:abc123def4/PROD/*')
        
        assert policy['principalId'] == 'user_test_123'
        assert policy['policyDocument']['Version'] == '2012-10-17'
        assert len(policy['policyDocument']['Statement']) == 1
        assert policy['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        assert policy['policyDocument']['Statement'][0]['Action'] == 'execute-api:Invoke'
        assert policy['policyDocument']['Statement'][0]['Resource'] == 'arn:aws:execute-api:us-east-1:123456789012:abc123def4/PROD/*'

    def test_generate_policy_deny(self):
        """Test generating deny policy"""
        policy = generate_policy('user_test_123', 'Deny', 'arn:aws:execute-api:us-east-1:123456789012:abc123def4/PROD/*')
        
        assert policy['principalId'] == 'user_test_123'
        assert policy['policyDocument']['Statement'][0]['Effect'] == 'Deny'

    @patch('apis.jwt_authorizer.validate_jwt_token')
    @patch.dict(os.environ, {'JWKS_PUBLIC_KEY': 'test_public_key'})
    def test_lambda_handler_success(self, mock_validate_token, sample_event):
        """Test successful JWT authorization"""
        mock_validate_token.return_value = 'user_test_123'
        
        result = lambda_handler(sample_event, {})
        
        assert result['principalId'] == 'user'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        assert result['context']['user_id'] == 'user_test_123'
        # Check that the resource ARN is properly formatted with wildcard
        assert result['policyDocument']['Statement'][0]['Resource'].endswith('/*')

    @patch('apis.jwt_authorizer.validate_jwt_token')
    @patch.dict(os.environ, {'JWKS_PUBLIC_KEY': 'test_public_key'})
    def test_lambda_handler_invalid_token(self, mock_validate_token, sample_event):
        """Test JWT authorization with invalid token"""
        mock_validate_token.return_value = None
        
        result = lambda_handler(sample_event, {})
        
        assert result['principalId'] == 'user'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'

    @patch.dict(os.environ, {'JWKS_PUBLIC_KEY': 'test_public_key'})
    def test_lambda_handler_no_bearer_token(self, sample_event):
        """Test JWT authorization without Bearer token"""
        event = sample_event.copy()
        event['authorizationToken'] = 'InvalidToken'
        
        result = lambda_handler(event, {})
        
        assert result['principalId'] == 'user'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'

    @patch.dict(os.environ, {'JWKS_PUBLIC_KEY': 'test_public_key'})
    def test_lambda_handler_empty_authorization(self, sample_event):
        """Test JWT authorization with empty authorization header"""
        event = sample_event.copy()
        event['authorizationToken'] = ''
        
        result = lambda_handler(event, {})
        
        assert result['principalId'] == 'user'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'

    @patch('apis.jwt_authorizer.validate_jwt_token')
    @patch.dict(os.environ, {'JWKS_PUBLIC_KEY': 'test_public_key'})
    def test_lambda_handler_exception(self, mock_validate_token, sample_event):
        """Test JWT authorization with exception"""
        mock_validate_token.side_effect = Exception("Test exception")
        
        result = lambda_handler(sample_event, {})
        
        assert result['principalId'] == 'user'
        assert result['policyDocument']['Statement'][0]['Effect'] == 'Deny'

    @patch('jwt.decode')
    @patch('jwt.get_unverified_header')
    def test_validate_jwt_token_success(self, mock_get_header, mock_decode, mock_jwks_public_key, mock_jwt_payload):
        """Test successful JWT token validation"""
        mock_get_header.return_value = {'alg': 'RS256', 'typ': 'JWT'}
        mock_decode.return_value = mock_jwt_payload
        
        with patch.dict(os.environ, {'JWKS_PUBLIC_KEY': mock_jwks_public_key}):
            result = validate_jwt_token('test_token')
        
        assert result == 'user_test_123'
        mock_decode.assert_called_once()

    @patch('jwt.decode')
    @patch('jwt.get_unverified_header')
    def test_validate_jwt_token_missing_jwks_key(self, mock_get_header, mock_decode):
        """Test JWT validation with missing JWKS public key"""
        with patch.dict(os.environ, {}, clear=True):
            result = validate_jwt_token('test_token')
        
        assert result is None
        mock_decode.assert_not_called()

    @patch('jwt.get_unverified_header')
    def test_validate_jwt_token_invalid_header(self, mock_get_header):
        """Test JWT validation with invalid header"""
        mock_get_header.return_value = None
        
        with patch.dict(os.environ, {'JWKS_PUBLIC_KEY': 'test_key'}):
            result = validate_jwt_token('test_token')
        
        assert result is None

    @patch('jwt.decode')
    @patch('jwt.get_unverified_header')
    def test_validate_jwt_token_expired_signature(self, mock_get_header, mock_decode, mock_jwks_public_key):
        """Test JWT validation with expired signature"""
        mock_get_header.return_value = {'alg': 'RS256', 'typ': 'JWT'}
        mock_decode.side_effect = jwt.ExpiredSignatureError("Token has expired")
        
        with patch.dict(os.environ, {'JWKS_PUBLIC_KEY': mock_jwks_public_key}):
            result = validate_jwt_token('test_token')
        
        assert result is None

    @patch('jwt.decode')
    @patch('jwt.get_unverified_header')
    def test_validate_jwt_token_invalid_signature(self, mock_get_header, mock_decode, mock_jwks_public_key):
        """Test JWT validation with invalid signature"""
        mock_get_header.return_value = {'alg': 'RS256', 'typ': 'JWT'}
        mock_decode.side_effect = jwt.InvalidSignatureError("Invalid signature")
        
        with patch.dict(os.environ, {'JWKS_PUBLIC_KEY': mock_jwks_public_key}):
            result = validate_jwt_token('test_token')
        
        assert result is None

    @patch('jwt.decode')
    @patch('jwt.get_unverified_header')
    def test_validate_jwt_token_invalid_token(self, mock_get_header, mock_decode, mock_jwks_public_key):
        """Test JWT validation with invalid token"""
        mock_get_header.return_value = {'alg': 'RS256', 'typ': 'JWT'}
        mock_decode.side_effect = jwt.InvalidTokenError("Invalid token")
        
        with patch.dict(os.environ, {'JWKS_PUBLIC_KEY': mock_jwks_public_key}):
            result = validate_jwt_token('test_token')
        
        assert result is None

    @patch('jwt.decode')
    @patch('jwt.get_unverified_header')
    def test_validate_jwt_token_no_user_id(self, mock_get_header, mock_decode, mock_jwks_public_key):
        """Test JWT validation with payload missing user ID"""
        mock_get_header.return_value = {'alg': 'RS256', 'typ': 'JWT'}
        mock_decode.return_value = {'iat': 1516239022}  # No 'sub' field
        
        with patch.dict(os.environ, {'JWKS_PUBLIC_KEY': mock_jwks_public_key}):
            result = validate_jwt_token('test_token')
        
        assert result is None

    @patch('jwt.decode')
    @patch('jwt.get_unverified_header')
    def test_validate_jwt_token_exception(self, mock_get_header, mock_decode, mock_jwks_public_key):
        """Test JWT validation with general exception"""
        mock_get_header.return_value = {'alg': 'RS256', 'typ': 'JWT'}
        mock_decode.side_effect = Exception("Unexpected error")
        
        with patch.dict(os.environ, {'JWKS_PUBLIC_KEY': mock_jwks_public_key}):
            result = validate_jwt_token('test_token')
        
        assert result is None 