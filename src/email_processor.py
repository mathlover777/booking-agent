import json
import boto3
import logging
from common_utils.email_util import parse_email_from_s3, send_email_via_ses
from booking_agent.agent import process_booking_request
from booking_agent.calendar_owner_resolver import _extract_clean_email
from typing import Dict, Any

# Configure logging
logger = logging.getLogger(__name__)


def load_email_from_s3(s3_bucket: str, s3_key: str) -> str:
    """Load email content from S3."""
    logger.info(f"Loading email from S3: {s3_bucket}/{s3_key}")
    s3_client = boto3.client('s3')
    response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
    email_content = response['Body'].read().decode('utf-8')
    logger.info(f"Retrieved email content, length: {len(email_content)} characters")
    return email_content


def send_clarification_email(parsed_email: Dict[str, Any], message: str) -> Dict[str, Any]:
    """Send clarification email to the sender."""
    from_addresses = parsed_email.get('from', [])
    if not from_addresses:
        return {'success': False, 'error': 'No sender found'}
    
    subject = "Calendar Booking - Need Clarification"
    return send_email_via_ses(
        to_addresses=from_addresses,
        subject=subject,
        body=message
    )


def send_ai_response_to_thread(parsed_email: Dict[str, Any], ai_response_content: str) -> Dict[str, Any]:
    """Send AI response to all participants in the email thread."""
    logger.info("Preparing to send AI response to thread")
    
    # Get all participants from the email thread (excluding sender)
    all_participants = []
    sender_emails = set()
    
    # Get sender emails
    from_addresses = parsed_email.get('from', [])
    for email_addr in from_addresses:
        clean_email = _extract_clean_email(email_addr)
        if clean_email:
            sender_emails.add(clean_email.lower())
    
    # Add all recipients (to + cc) except sender
    to_addresses = parsed_email.get('to', [])
    cc_addresses = parsed_email.get('cc', [])
    
    for email_addr in to_addresses + cc_addresses:
        clean_email = _extract_clean_email(email_addr)
        if clean_email and clean_email.lower() not in sender_emails:
            all_participants.append(clean_email)
    
    if not all_participants:
        return {'success': False, 'error': 'No valid recipients found (only sender in thread)'}
    
    # Get threading information
    message_id = parsed_email.get('message_id', '')
    references = parsed_email.get('references', '')
    
    # If this is a reply, add the current message ID to references
    if message_id and references:
        references = f"{references} {message_id}"
    elif message_id:
        references = message_id
    
    # Determine subject (add Re: if not already present)
    subject = parsed_email.get('subject', '')
    if not subject.lower().startswith('re:'):
        subject = f"Re: {subject}"
    
    logger.info(f"Sending AI response to {len(all_participants)} participants")
    
    return send_email_via_ses(
        to_addresses=all_participants,
        subject=subject,
        body=ai_response_content,
        reply_to_message_id=message_id,
        reply_to_references=references
    )


def lambda_handler(event, context):
    """
    Lambda handler for processing emails stored in S3
    """
    logger.info("Email processor lambda triggered")
    logger.info(f"Event: {json.dumps(event)}")
    
    # Get S3 bucket and key from the event
    s3_bucket = event['Records'][0]['s3']['bucket']['name']
    s3_key = event['Records'][0]['s3']['object']['key']
    
    logger.info(f"Processing email from S3: {s3_bucket}/{s3_key}")
    
    try:
        # Load and parse email from S3
        email_content = load_email_from_s3(s3_bucket, s3_key)
        parsed_email = parse_email_from_s3(email_content)
        logger.info(f"Parsed email with keys: {list(parsed_email.keys())}")
        
        # Process booking request with parsed email data
        result = process_booking_request(parsed_email)
        
        logger.info("=" * 80)
        logger.info("AI PROCESSING RESULT:")
        logger.info("=" * 80)
        logger.info(json.dumps(result, ensure_ascii=False))
        logger.info("=" * 80)
        
        # Handle different actions from the agent
        if result['action'] == 'processed':
            # Send AI response to thread
            send_result = send_ai_response_to_thread(parsed_email, result['ai_response'])
            
            if send_result.get("success"):
                logger.info("Email processing completed successfully")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Email processed successfully by AI agent',
                        'action': result['action'],
                        'ai_response': result['ai_response'],
                        'send_result': send_result,
                        'calendar_user_id': result['calendar_user_id'],
                        'booking_email': result['booking_email']
                    })
                }
            else:
                logger.error(f"Failed to send email: {send_result.get('error')}")
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        'message': 'Failed to send AI response',
                        'action': 'send_failed',
                        'error': send_result.get('error'),
                        'ai_response': result['ai_response']
                    })
                }
                
        elif result['action'] == 'clarification_needed':
            # Send clarification email
            send_result = send_clarification_email(parsed_email, result['clarification_message'])
            
            if send_result.get("success"):
                logger.info("Clarification email sent successfully")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Clarification email sent',
                        'action': result['action'],
                        'status': result['status'],
                        'reason': result['reason'],
                        'send_result': send_result
                    })
                }
            else:
                logger.error(f"Failed to send clarification email: {send_result.get('error')}")
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        'message': 'Failed to send clarification email',
                        'action': 'clarification_send_failed',
                        'error': send_result.get('error'),
                        'status': result['status'],
                        'reason': result['reason']
                    })
                }
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'message': 'Unknown action from booking agent',
                    'action': result['action'],
                    'error': 'Unexpected action type'
                })
            }
            
    except Exception as e:
        logger.error(f"Error in lambda handler: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Error in email processor lambda',
                'error': str(e)
            })
        } 