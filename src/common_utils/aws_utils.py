import json
import boto3
import os
import logging

# Global variables
STAGE = os.environ['STAGE']
secrets_client = boto3.client('secretsmanager')
response = secrets_client.get_secret_value(SecretId=f"{STAGE}/vibecal")
_secrets = json.loads(response['SecretString'])

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
user_emails_table_name = os.getenv('USER_EMAILS_TABLE_NAME')
user_emails_table = dynamodb.Table(user_emails_table_name) if user_emails_table_name else None

# Configure logging globally
log_level = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
