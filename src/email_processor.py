import json
import boto3
from utils import parse_email_from_s3, format_email_summary


def lambda_handler(event, context):
    """
    Lambda handler for processing emails stored in S3
    """
    print("Email processor lambda triggered")
    
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
    
    # Format and print the email summary
    summary = format_email_summary(email_data)
    print(summary)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Email processed successfully',
            'subject': email_data['subject'],
            'from': email_data['from']
        })
    } 