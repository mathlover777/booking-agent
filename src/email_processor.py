import json
import boto3
from email_util import parse_email_from_s3, extract_conversation_context, should_reply_to_email, reply_to_email_thread


def lambda_handler(event, context):
    """
    Lambda handler for processing emails stored in S3
    """
    print("Email processor lambda triggered")
    print(f"Event: {json.dumps(event)}")
    
    # Get S3 bucket and key from the event
    s3_bucket = event['Records'][0]['s3']['bucket']['name']
    s3_key = event['Records'][0]['s3']['object']['key']
    
    print(f"Processing email from S3: {s3_bucket}/{s3_key}")
    
    # Get the email content from S3
    s3_client = boto3.client('s3')
    response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
    email_content = response['Body'].read().decode('utf-8')
    
    # Parse the email
    email_data = parse_email_from_s3(email_content)
    
    # Extract conversation context for AI processing
    conversation_context = extract_conversation_context(email_data)
    
    # Print the conversation context as JSON for easy reading in CloudWatch
    print("=" * 80)
    print("CONVERSATION CONTEXT FOR AI:")
    print("=" * 80)
    print(json.dumps(conversation_context, ensure_ascii=False))
    print("=" * 80)
    
    # Auto-reply logic
    print("=" * 80)
    print("AUTO-REPLY CHECK:")
    print("=" * 80)
    
    if should_reply_to_email(email_data):
        print("✅ Email should be replied to. Sending auto-reply...")
        reply_result = reply_to_email_thread(email_data)
        
        if reply_result['success']:
            print(f"✅ Auto-reply sent successfully! Message ID: {reply_result['message_id']}")
        else:
            print(f"❌ Failed to send auto-reply: {reply_result['error']}")
    else:
        print("❌ Email does not meet reply criteria. No reply sent.")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Email processed successfully',
            'conversation_context': conversation_context,
            'auto_reply_sent': should_reply_to_email(email_data)
        })
    } 