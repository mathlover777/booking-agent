import json
import boto3
import os
from common_utils.email_util import parse_email_from_s3, send_email_via_ses, send_response_to_thread
from booking_agent.agent import process_booking_request
from common_utils.log_util import get_logger
from typing import Dict, Any

# Get logger for this module
logger = get_logger(__name__)

# Get domain name from environment
DOMAIN_NAME = os.getenv("DOMAIN_NAME")


def add_debug_info_to_response(response_content: str, s3_bucket: str, s3_key: str, request_id: str) -> str:
    """
    Add debugging information (S3 key and Lambda request ID) to the email response content.
    """
    debug_info = f"""

---
DEBUG INFORMATION:
S3 File: {s3_bucket}/{s3_key}
Lambda Request ID: {request_id}
---
"""
    return response_content + debug_info


def load_email_from_s3(s3_bucket: str, s3_key: str) -> str:
    """Load email content from S3."""
    logger.info(f"Loading email from S3: {s3_bucket}/{s3_key}")
    s3_client = boto3.client('s3')
    response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
    email_content = response['Body'].read().decode('utf-8')
    logger.info(f"Retrieved email content, length: {len(email_content)} characters")
    return email_content


def create_langfuse_metadata(parsed_email: Dict[str, Any], s3_bucket: str, s3_key: str) -> Dict[str, Any]:
    """Create metadata for Langfuse tracing."""
    # Extract thread ID from email headers
    thread_id = parsed_email.get('message_id') or parsed_email.get('in_reply_to') or parsed_email.get('references', '').split()[0] if parsed_email.get('references') else None
    
    # Get email subject for context
    subject = parsed_email.get('subject', '')
    
    # Get sender info
    from_emails = parsed_email.get('from', [])
    sender = from_emails[0] if from_emails else 'unknown'
    
    # Get recipient info
    to_emails = parsed_email.get('to', [])
    recipients = to_emails if to_emails else []
    
    return {
        "thread_id": thread_id,
        "email_reference": f"{s3_bucket}/{s3_key}",
        "subject": subject,
        "sender": sender,
        "recipients": recipients,
        "processing_stage": "email_processing",
        "domain": DOMAIN_NAME,
        "email_date": parsed_email.get('date', ''),
        "message_id": parsed_email.get('message_id', ''),
        "in_reply_to": parsed_email.get('in_reply_to', ''),
    }


def process_email(s3_bucket: str, s3_key: str, context=None) -> dict:
    """
    Process a single email from S3.
    """
    # Get the Lambda request ID for debugging
    request_id = context.aws_request_id if context else "unknown"
    logger.info(f"Lambda Request ID: {request_id}")
    
    logger.info(f"📧 Processing email from S3: {s3_bucket}/{s3_key}")
    
    try:
        logger.info("🔍 Starting email processing...")
        
        # Load and parse email from S3
        logger.info("📥 Loading email from S3...")
        email_content = load_email_from_s3(s3_bucket, s3_key)
        logger.info(f"📥 Email content loaded, length: {len(email_content)} characters")
        
        logger.info("🔍 Parsing email content...")
        parsed_email = parse_email_from_s3(email_content)
        logger.info(f"✅ Email parsed successfully with keys: {list(parsed_email.keys())}")
        
        # Check if email is from bhaang domain - if so, exit doing nothing
        from_emails = parsed_email.get('from', [])
        if DOMAIN_NAME and from_emails:
            for from_email in from_emails:
                if from_email.lower().endswith(f"@{DOMAIN_NAME.lower()}"):
                    logger.info(f"Skipping email from bhaang domain {DOMAIN_NAME}: {from_email}")
                    return {
                        'statusCode': 200,
                        'body': json.dumps({
                            'message': f'Email skipped - from {DOMAIN_NAME} domain',
                            'action': 'skipped',
                            'reason': f'Email from {from_email} is from domain {DOMAIN_NAME}'
                        })
                    }
        
        # Create metadata for Langfuse tracing
        logger.info("🔍 Creating Langfuse metadata...")
        metadata = create_langfuse_metadata(parsed_email, s3_bucket, s3_key)
        logger.info(f"✅ Created Langfuse metadata: {metadata}")
        
        # Run the agent loop
        logger.info("🤖 Starting AI booking agent processing...")
        result = process_booking_request(parsed_email, metadata)
        
        logger.info("=" * 80)
        logger.info("AI PROCESSING RESULT:")
        logger.info("=" * 80)
        logger.info(json.dumps(result, ensure_ascii=False))
        logger.info("=" * 80)
        
        # Handle different actions from the agent
        if result['action'] == 'processed':
            # Add debug information to the AI response
            enhanced_response = add_debug_info_to_response(result['ai_response'], s3_bucket, s3_key, request_id)
            
            # Send AI response to thread from booking email
            send_result = send_response_to_thread(parsed_email, enhanced_response, booking_email=result['booking_email'])
            
            if send_result.get("success"):
                logger.info("Email processing completed successfully")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Email processed successfully by AI agent',
                        'action': result['action'],
                        'ai_response': result['ai_response'],
                        'enhanced_response': enhanced_response,
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
            # Add debug information to the clarification message
            enhanced_clarification = add_debug_info_to_response(result['clarification_message'], s3_bucket, s3_key, request_id)
            
            # Send clarification email from booking email to all participants except booking email and bhaang domain emails
            send_result = send_response_to_thread(
                parsed_email, 
                enhanced_clarification,
                booking_email=result.get('booking_email')
            )
            
            if send_result.get("success"):
                logger.info("Clarification email sent successfully")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Clarification email sent',
                        'action': result['action'],
                        'status': result['status'],
                        'reason': result['reason'],
                        'enhanced_clarification': enhanced_clarification,
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
        logger.error("=" * 80)
        logger.error("❌ ERROR IN EMAIL PROCESSOR LAMBDA")
        logger.error("=" * 80)
        logger.error(f"Error details: {e}", exc_info=True)
        logger.error("=" * 80)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Error in email processor lambda',
                'error': str(e)
            })
        }


def lambda_handler(event, context):
    """
    Lambda handler for processing emails from SQS messages
    """
    logger.info("=" * 80)
    logger.info("🚀 EMAIL PROCESSOR LAMBDA TRIGGERED")
    logger.info("=" * 80)
    logger.info(f"Event: {json.dumps(event)}")
    
    # Process SQS messages
    results = []
    for record in event.get('Records', []):
        try:
            # Parse SQS message
            message_body = json.loads(record['body'])
            s3_bucket = message_body['s3_bucket']
            s3_key = message_body['s3_key']
            stage = message_body['stage']
            
            logger.info(f"Processing SQS message for stage {stage}: {s3_bucket}/{s3_key}")
            
            # Process the email
            result = process_email(s3_bucket, s3_key, context)
            
            # Log the result
            logger.info(f"Email processing result: {result}")
            
            # Store the result for return
            results.append(result)
            
        except Exception as e:
            logger.error(f"Error processing SQS record: {str(e)}", exc_info=True)
            # Don't raise here - let SQS handle retries via DLQ
            results.append({
                'statusCode': 500,
                'body': json.dumps({
                    'message': 'Error processing SQS record',
                    'error': str(e)
                })
            })
    
    # Return the result of the first (and typically only) record
    # This allows tests to see the actual processing results
    if results:
        return results[0]
    else:
        return {
            'statusCode': 200,
            'body': json.dumps('SQS messages processed')
        } 