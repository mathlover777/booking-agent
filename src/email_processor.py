import json
import boto3
from booking_agent import process_email_with_ai


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
    
    # Process email with AI booking agent
    result = process_email_with_ai(s3_bucket, s3_key)
    
    print("=" * 80)
    print("AI PROCESSING RESULT:")
    print("=" * 80)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("=" * 80)
    
    if result['action'] == 'processed':
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Email processed successfully by AI agent',
                'action': result['action'],
                'email_response': result['email_response'],
                'send_result': result['send_result']
            })
        }
    else:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Error processing email with AI agent',
                'action': result['action'],
                'error': result.get('error', 'Unknown error')
            })
        } 