import json
import email
import os
import boto3
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Any
import re

# Configure logging
logger = logging.getLogger(__name__)


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
        # Parse addresses and extract clean email addresses
        raw_addresses = [addr.strip() for addr in address_string.split(',')]
        clean_addresses = []
        for addr in raw_addresses:
            clean_email = _extract_clean_email(addr)
            if clean_email:
                clean_addresses.append(clean_email)
        return clean_addresses
    
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


def send_response_to_thread(parsed_email: Dict[str, Any], response_content: str, subject_override: str = None, booking_email: str = None) -> Dict[str, Any]:
    """Send response to all participants in the email thread (excluding only the booking email)."""
    logger.info("Preparing to send response to thread")
    
    # Get all participants from the email thread (excluding only the booking email)
    all_participants = []
    excluded_emails = set()
    
    # Add booking email to excluded list if provided
    if booking_email:
        excluded_emails.add(booking_email.lower())
        logger.info(f"Excluding booking email from recipients: {booking_email}")
    
    # Add all participants (sender + to + cc) except booking email
    from_addresses = parsed_email.get('from', [])
    to_addresses = parsed_email.get('to', [])
    cc_addresses = parsed_email.get('cc', [])
    
    for email_addr in from_addresses + to_addresses + cc_addresses:
        clean_email = _extract_clean_email(email_addr)
        if clean_email and clean_email.lower() not in excluded_emails:
            all_participants.append(clean_email)
    
    if not all_participants:
        return {'success': False, 'error': 'No valid recipients found (only booking email in thread)'}
    
    # Get threading information
    message_id = parsed_email.get('message_id', '')
    references = parsed_email.get('references', '')
    
    # If this is a reply, add the current message ID to references
    if message_id and references:
        references = f"{references} {message_id}"
    elif message_id:
        references = message_id
    
    # Determine subject
    if subject_override:
        subject = subject_override
    else:
        subject = parsed_email.get('subject', '')
        if not subject.lower().startswith('re:'):
            subject = f"Re: {subject}"
    
    logger.info(f"Sending response to {len(all_participants)} participants")
    
    return send_email_via_ses(
        to_addresses=all_participants,
        subject=subject,
        body=response_content,
        reply_to_message_id=message_id,
        reply_to_references=references
    )


def _extract_clean_email(email_addr: str) -> str:
    """Extract clean email address from various formats."""
    if not email_addr:
        return None
    
    # Remove angle brackets if present
    email_addr = email_addr.strip()
    if email_addr.startswith('<') and email_addr.endswith('>'):
        email_addr = email_addr[1:-1]
    
    # Extract email from "Name <email@domain.com>" format
    match = re.search(r'<(.+?)>', email_addr)
    if match:
        return match.group(1).strip()
    
    # If it looks like a valid email, return as is
    if '@' in email_addr:
        return email_addr.strip()
    
    return None 