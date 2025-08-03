import json
import os
import boto3
import logging
from typing import List, Set
from email import message_from_bytes
from email.utils import getaddresses

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

# Initialize AWS clients
s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')
bucket_name = os.getenv('EMAIL_BUCKET_NAME')


def extract_stage_from_email(email: str) -> str:
    """
    Extract stage from email address.
    Pattern: local_part(.stage)?@domain.com
    Examples:
    - alice@bhaang.com -> "prod"
    - alice.dev@bhaang.com -> "dev"
    - alice.qa@bhaang.com -> "qa"
    """
    if not email or '@' not in email:
        return None
    
    local_part, domain = email.split('@', 1)
    
    # Get domain name from environment
    domain_name = os.getenv('DOMAIN_NAME')
    
    # Check if domain matches our target domain
    if not domain_name or domain.lower() != domain_name.lower():
        return None
    
    # Check if local_part contains a stage suffix
    if '.' in local_part:
        # Split by '.' and take the last part as stage
        parts = local_part.split('.')
        if len(parts) >= 2:
            stage = parts[-1]  # Last part is the stage
            return stage
    
    # No stage suffix means prod
    return "prod"


def get_unique_stages_from_recipients(recipients: List[str]) -> Set[str]:
    """
    Extract unique stages from a list of email recipients.
    """
    stages = set()
    
    for recipient in recipients:
        stage = extract_stage_from_email(recipient)
        if stage:
            stages.add(stage)
    
    return stages


def send_email_to_stage_queues(source_key: str, stages: Set[str]) -> None:
    """
    Send email processing messages to stage-specific SQS queues.
    """
    for stage in stages:
        try:
            # Construct the queue name based on the pattern
            queue_name = f"email-processor-queue-{stage}"
            
            # Get the queue URL
            queue_url = sqs_client.get_queue_url(QueueName=queue_name)['QueueUrl']
            
            # Prepare the message
            message_body = {
                "s3_bucket": bucket_name,
                "s3_key": source_key,
                "stage": stage
            }
            
            # Send message to SQS
            response = sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_body)
            )
            
            logger.info(f"Sent email to {queue_name} for stage {stage}, MessageId: {response['MessageId']}")
        except Exception as e:
            logger.error(f"Failed to send email to queue for stage {stage}: {str(e)}")


def parse_ses_notification(record: dict) -> List[str]:
    """
    Parse SES notification to extract all recipients.
    """
    try:
        # Get the S3 object key
        s3_key = record['s3']['object']['key']
        
        # Download the email from S3
        response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        email_content = response['Body'].read()
        
        # Parse the email
        msg = message_from_bytes(email_content)
        
        # Extract all recipients (To, Cc, Bcc)
        recipients = []
        
        # Get To recipients
        to_header = msg.get('To', '')
        if to_header:
            to_addresses = getaddresses([to_header])
            recipients.extend([email for name, email in to_addresses if email])
        
        # Get Cc recipients
        cc_header = msg.get('Cc', '')
        if cc_header:
            cc_addresses = getaddresses([cc_header])
            recipients.extend([email for name, email in cc_addresses if email])
        
        # Get Bcc recipients (if available in headers)
        bcc_header = msg.get('Bcc', '')
        if bcc_header:
            bcc_addresses = getaddresses([bcc_header])
            recipients.extend([email for name, email in bcc_addresses if email])
        
        logger.info(f"Extracted recipients: {recipients}")
        return recipients
        
    except Exception as e:
        logger.error(f"Failed to parse SES notification: {str(e)}")
        return []


def lambda_handler(event, context):
    """
    Lambda handler for EmailRouter.
    
    This function:
    1. Receives S3 notifications for emails stored in 'incoming/' prefix
    2. Parses the email to extract all recipients
    3. Identifies unique stages from recipient email addresses
    4. Sends email processing messages to stage-specific SQS queues
    """
    try:
        logger.info(f"EmailRouter triggered with event: {json.dumps(event)}")
        
        # Process each S3 record
        for record in event.get('Records', []):
            if record.get('eventSource') == 'aws:s3':
                # Extract the S3 object key
                s3_key = record['s3']['object']['key']
                logger.info(f"Processing email: {s3_key}")
                
                # Parse the email to get recipients
                recipients = parse_ses_notification(record)
                
                if not recipients:
                    logger.warning(f"No recipients found in email: {s3_key}")
                    continue
                
                # Extract unique stages from recipients
                stages = get_unique_stages_from_recipients(recipients)
                
                if not stages:
                    logger.info(f"No valid stages found in recipients for email: {s3_key}")
                    continue
                
                logger.info(f"Found stages: {stages} for email: {s3_key}")
                
                # Send email to stage-specific queues
                send_email_to_stage_queues(s3_key, stages)
        
        return {
            'statusCode': 200,
            'body': json.dumps('Email routing completed successfully')
        }
        
    except Exception as e:
        logger.error(f"Error in EmailRouter: {str(e)}")
        raise 