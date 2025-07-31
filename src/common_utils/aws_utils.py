import json
import boto3
import os
from .log_util import get_logger

# Get logger for this module
logger = get_logger(__name__)

# Global variables
STAGE = os.getenv('STAGE')
logger.info(f"STAGE: {STAGE}")

try:
    secrets_client = boto3.client('secretsmanager')
    response = secrets_client.get_secret_value(SecretId=f"{STAGE}/vibecal")
    _secrets = json.loads(response['SecretString'])
    logger.info("✅ Successfully loaded secrets from AWS Secrets Manager")
except Exception as e:
    logger.error(f"❌ Failed to load secrets from AWS Secrets Manager: {e}")
    # Initialize with empty dict to prevent import errors
    _secrets = {}

# Initialize Langfuse environment variables from secrets
def _init_langfuse():
    """Initialize Langfuse environment variables from AWS secrets."""
    langfuse_secret_key = _secrets.get("LANGFUSE_SECRET_KEY")
    langfuse_public_key = _secrets.get("LANGFUSE_PUBLIC_KEY")
    langfuse_host = _secrets.get("LANGFUSE_HOST")
    
    if langfuse_secret_key:
        os.environ["LANGFUSE_SECRET_KEY"] = langfuse_secret_key
    if langfuse_public_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = langfuse_public_key
    if langfuse_host:
        os.environ["LANGFUSE_HOST"] = langfuse_host

# Initialize Langfuse on module import
_init_langfuse()

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
user_emails_table_name = os.getenv('USER_EMAILS_TABLE_NAME')
user_emails_table = dynamodb.Table(user_emails_table_name) if user_emails_table_name else None
