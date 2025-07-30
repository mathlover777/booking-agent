import json
import email
import os
import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Any
import re


def parse_email_from_s3(s3_content: str) -> Dict[str, Any]:
    """
    Parse email content from S3 and extract relevant information
    """
    # Parse the email message
    msg = email.message_from_string(s3_content)
    
    # Extract email body
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                break
    else:
        body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
    
    # Extract email addresses
    from_address = msg.get('From', '')
    to_addresses = msg.get('To', '')
    cc_addresses = msg.get('Cc', '')
    bcc_addresses = msg.get('Bcc', '')
    
    # Parse multiple addresses
    def parse_addresses(address_string: str) -> List[str]:
        if not address_string:
            return []
        # Simple parsing - in production you'd want more robust parsing
        addresses = [addr.strip() for addr in address_string.split(',')]
        return addresses
    
    return {
        'subject': msg.get('Subject', ''),
        'body': body,
        'from': parse_addresses(from_address),
        'to': parse_addresses(to_addresses),
        'cc': parse_addresses(cc_addresses),
        'bcc': parse_addresses(bcc_addresses),
        'date': msg.get('Date', ''),
        'message_id': msg.get('Message-ID', ''),
        'in_reply_to': msg.get('In-Reply-To', ''),
        'references': msg.get('References', ''),
        'return_path': msg.get('Return-Path', '')
    }


def send_email_via_ses(
    to_addresses: List[str],
    subject: str,
    body: str,
    from_address: str = None,
    reply_to_message_id: str = None,
    reply_to_references: str = None,
    cc_addresses: List[str] = None,
    region: str = 'ap-south-1'
) -> Dict[str, Any]:
    """
    Send email via AWS SES
    
    Args:
        to_addresses: List of recipient email addresses
        subject: Email subject
        body: Email body (plain text)
        from_address: Sender email address (defaults to BOOKING_EMAIL env var)
        reply_to_message_id: Message-ID to reply to (for threading)
        reply_to_references: References header for threading
        cc_addresses: List of CC email addresses
        region: AWS region for SES
    
    Returns:
        Dict with SES response
    """
    if from_address is None:
        from_address = os.getenv('BOOKING_EMAIL', 'bookdev@bhaang.com')
    
    # Create SES client
    ses_client = boto3.client('ses', region_name=region)
    
    # Create email message
    msg = MIMEMultipart()
    msg['From'] = from_address
    msg['To'] = ', '.join(to_addresses)
    msg['Subject'] = subject
    
    # Add threading headers if replying
    if reply_to_message_id:
        msg['In-Reply-To'] = reply_to_message_id
    if reply_to_references:
        msg['References'] = reply_to_references
    
    # Add CC if provided
    if cc_addresses:
        msg['Cc'] = ', '.join(cc_addresses)
    
    # Add body
    msg.attach(MIMEText(body, 'plain'))
    
    # Prepare recipients
    all_recipients = to_addresses.copy()
    if cc_addresses:
        all_recipients.extend(cc_addresses)
    
    try:
        # Send email via SES
        response = ses_client.send_raw_email(
            Source=from_address,
            Destinations=all_recipients,
            RawMessage={'Data': msg.as_string()}
        )
        
        return {
            'success': True,
            'message_id': response['MessageId'],
            'response': response
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'response': None
        } 