import json
import boto3
from utils import parse_email_from_s3, extract_conversation_context


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
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Email processed successfully',
            'conversation_context': conversation_context
        })
    } 