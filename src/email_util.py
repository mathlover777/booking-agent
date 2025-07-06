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


def extract_conversation_context(email_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract conversation context from email for AI processing
    Returns structured JSON with thread information
    """
    # Extract basic email info
    subject = email_data.get('subject', '')
    current_sender = email_data.get('from', [])
    current_recipients = email_data.get('to', [])
    current_cc = email_data.get('cc', [])
    
    # Get the email body
    email_body = email_data.get('body', '')
    
    # Extract conversation history from body
    conversation_history = extract_conversation_from_body(email_body)
    
    # Determine thread starter and current replier
    thread_starter = determine_thread_starter(email_data, conversation_history)
    current_replier = current_sender[0] if current_sender else "Unknown"
    
    # Get all recipients (to + cc)
    all_recipients = list(set(current_recipients + current_cc))
    
    # Extract current email text (first part before quoted text)
    current_text = extract_current_message(email_body)
    
    return {
        "thread_starter": thread_starter,
        "current_replier": current_replier,
        "recipients": all_recipients,
        "current_email_text": current_text,
        "subject": subject,
        "conversation_history": conversation_history,
        "message_id": email_data.get('message_id', ''),
        "date": email_data.get('date', ''),
        "thread_headers": {
            "in_reply_to": email_data.get('in_reply_to', ''),
            "references": email_data.get('references', '')
        }
    }


def extract_conversation_from_body(email_body: str) -> str:
    """
    Extract the full conversation history from email body
    Returns the conversation as a text block
    """
    print(f"DEBUG: Extracting conversation from body: {email_body}")
    if not email_body:
        return ""
    
    # Split by lines and find where quoted text starts
    lines = email_body.split('\n')
    conversation_lines = []
    
    for line in lines:
        # Include lines that are quoted (start with >) or contain email headers
        if (line.strip().startswith('>') or 
            'On ' in line and ' wrote:' in line or
            line.strip().startswith('From:') or
            line.strip().startswith('To:') or
            line.strip().startswith('Subject:') or
            line.strip().startswith('Date:')):
            conversation_lines.append(line)
    
    return '\n'.join(conversation_lines)


def extract_current_message(email_body: str) -> str:
    """
    Extract the current email text (before quoted text)
    """
    if not email_body:
        return ""
    
    lines = email_body.split('\n')
    current_lines = []
    
    for line in lines:
        # Stop when we hit quoted text or email headers
        if (line.strip().startswith('>') or 
            ('On ' in line and ' wrote:' in line) or
            line.strip().startswith('From:') or
            line.strip().startswith('To:') or
            line.strip().startswith('Subject:') or
            line.strip().startswith('Date:')):
            break
        current_lines.append(line)
    
    return '\n'.join(current_lines).strip()


def determine_thread_starter(email_data: Dict[str, Any], conversation_history: str) -> str:
    """
    Determine who started the thread
    """
    # Check if this is a reply (has in_reply_to header)
    if email_data.get('in_reply_to'):
        # Look for the original sender in conversation history
        # Usually the first email in the thread
        lines = conversation_history.split('\n')
        for line in lines:
            if 'From:' in line:
                # Extract email from "From: Name <email@domain.com>" format
                match = re.search(r'From:\s*.*?<([^>]+)>', line)
                if match:
                    return match.group(1)
                # Fallback for "From: email@domain.com" format
                match = re.search(r'From:\s*([^\s]+@[^\s]+)', line)
                if match:
                    return match.group(1)
    
    # If no reply headers, current sender is the thread starter
    return email_data.get('from', ['Unknown'])[0]


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


def format_email_summary(email_data: Dict[str, Any]) -> str:
    """
    Format email data for printing/logging
    """
    summary = []
    summary.append("=" * 50)
    summary.append("EMAIL RECEIVED")
    summary.append("=" * 50)
    summary.append(f"Subject: {email_data['subject']}")
    summary.append(f"Date: {email_data['date']}")
    summary.append(f"Message ID: {email_data['message_id']}")
    summary.append("")
    
    # Highlight the sender
    summary.append("🔴 SENDER (FROM):")
    for addr in email_data['from']:
        summary.append(f"  → {addr}")
    summary.append("")
    
    # Other participants
    if email_data['to']:
        summary.append("📧 TO:")
        for addr in email_data['to']:
            summary.append(f"  → {addr}")
        summary.append("")
    
    if email_data['cc']:
        summary.append("📋 CC:")
        for addr in email_data['cc']:
            summary.append(f"  → {addr}")
        summary.append("")
    
    if email_data['bcc']:
        summary.append("👁️ BCC:")
        for addr in email_data['bcc']:
            summary.append(f"  → {addr}")
        summary.append("")
    
    summary.append("📄 EMAIL BODY:")
    summary.append("-" * 30)
    summary.append(email_data['body'])
    summary.append("=" * 50)
    
    return "\n".join(summary) 


def get_original_sender_from_email(email_data: Dict[str, Any]) -> str:
    """
    Get the original sender email from the email data
    Uses Return-Path as the most reliable way to get the actual sender
    Falls back to From header if Return-Path is not available
    """
    # Return-Path is the most reliable way to get the actual sender
    # It's set by the sending MTA and can't be easily spoofed
    return_path = email_data.get('return_path', '')
    if return_path:
        # Extract email from Return-Path: <email@domain.com> format
        match = re.search(r'<([^>]+)>', return_path)
        if match:
            return match.group(1)
        # Fallback for Return-Path: email@domain.com format
        match = re.search(r'([^\s]+@[^\s]+)', return_path)
        if match:
            return match.group(1)
    
    # Fallback to From header
    from_addresses = email_data.get('from', [])
    if from_addresses:
        # Extract email from "Name <email@domain.com>" format
        match = re.search(r'<([^>]+)>', from_addresses[0])
        if match:
            return match.group(1)
        # Fallback for "email@domain.com" format
        match = re.search(r'([^\s]+@[^\s]+)', from_addresses[0])
        if match:
            return match.group(1)
    
    return ""


def should_reply_to_email(email_data: Dict[str, Any]) -> bool:
    """
    Determine if we should reply to this email
    Returns True if the sender is not the BOOKING_EMAIL
    """
    booking_email = os.getenv('BOOKING_EMAIL', 'bookdev@bhaang.com')
    original_sender = get_original_sender_from_email(email_data)
    
    # Don't reply if the sender is the booking email itself
    return original_sender.lower() != booking_email.lower()


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


def reply_to_email_thread(email_data: Dict[str, Any], reply_message: str = None) -> Dict[str, Any]:
    """
    Reply to an email thread - sends to all participants except booking email
    
    Args:
        email_data: Parsed email data from parse_email_from_s3
        reply_message: Custom reply message (defaults to "I will get back soon")
    
    Returns:
        Dict with send result
    """
    if reply_message is None:
        reply_message = "I will get back soon"
    
    booking_email = os.getenv('BOOKING_EMAIL', 'bookdev@bhaang.com')
    
    # Get all participants from the email thread
    all_participants = []
    
    # Add original sender
    original_sender = get_original_sender_from_email(email_data)
    if original_sender and original_sender.lower() != booking_email.lower():
        all_participants.append(original_sender)
    
    # Add all recipients (to + cc) except booking email
    to_addresses = email_data.get('to', [])
    cc_addresses = email_data.get('cc', [])
    
    for email_addr in to_addresses + cc_addresses:
        # Clean the email address (remove name part if present)
        clean_email = email_addr
        if '<' in email_addr and '>' in email_addr:
            # Extract email from "Name <email@domain.com>" format
            match = re.search(r'<([^>]+)>', email_addr)
            if match:
                clean_email = match.group(1)
        elif ' ' in email_addr:
            # Extract email from "email@domain.com" format
            match = re.search(r'([^\s]+@[^\s]+)', email_addr)
            if match:
                clean_email = match.group(1)
        
        # Add if not booking email and not already in list
        if (clean_email.lower() != booking_email.lower() and 
            clean_email not in all_participants):
            all_participants.append(clean_email)
    
    if not all_participants:
        return {
            'success': False,
            'error': 'No valid recipients found (all participants are booking email)'
        }
    
    # Get threading information
    message_id = email_data.get('message_id', '')
    references = email_data.get('references', '')
    
    # If this is a reply, add the current message ID to references
    if message_id and references:
        references = f"{references} {message_id}"
    elif message_id:
        references = message_id
    
    # Determine subject (add Re: if not already present)
    subject = email_data.get('subject', '')
    if not subject.lower().startswith('re:'):
        subject = f"Re: {subject}"
    
    print(f"📧 Sending auto-reply to {len(all_participants)} participants:")
    for participant in all_participants:
        print(f"  → {participant}")
    
    # Send the reply to all participants
    return send_email_via_ses(
        to_addresses=all_participants,
        subject=subject,
        body=reply_message,
        reply_to_message_id=message_id,
        reply_to_references=references
    )


def test_send_email():
    """
    Test function to send a simple email via SES
    """
    test_email = "test@example.com"  # Replace with actual test email
    
    result = send_email_via_ses(
        to_addresses=[test_email],
        subject="Test Email from Vibes",
        body="This is a test email sent via SES from the Vibes application."
    )
    
    if result['success']:
        print(f"✅ Test email sent successfully! Message ID: {result['message_id']}")
    else:
        print(f"❌ Failed to send test email: {result['error']}")
    
    return result


def test_reply_to_email_thread():
    """
    Test function to simulate replying to an email thread
    """
    # Simulate email data from S3 with multiple participants
    test_email_data = {
        'subject': 'help me book call',
        'from': ['souravmathlover@gmail.com'],
        'to': ['bookdev@bhaang.com', 'Sourav Sarkar <souravsarkar1729@gmail.com>'],
        'cc': ['team@example.com', 'manager@example.com'],
        'message_id': '<CAATJRY8wTi1y1=cjjPSbUoNMT5WT8A+j=VtXWHisAiDJjw3JKQ@mail.gmail.com>',
        'references': '<CABu2_87WFGYNK5HJTXO7Nw1z62Z-AE3NFBFGvpW=JoUr3iGPbw@mail.gmail.com>',
        'return_path': '<souravmathlover@gmail.com>'
    }
    
    # Check if we should reply
    if should_reply_to_email(test_email_data):
        print("✅ Should reply to this email")
        result = reply_to_email_thread(test_email_data)
        
        if result['success']:
            print(f"✅ Reply sent successfully! Message ID: {result['message_id']}")
        else:
            print(f"❌ Failed to send reply: {result['error']}")
        
        return result
    else:
        print("❌ Should not reply to this email (sender is booking email)")
        return {'success': False, 'error': 'Should not reply'}


if __name__ == "__main__":
    # Run tests
    print("Testing email sending functionality...")
    print("\n1. Testing basic email send:")
    test_send_email()
    
    print("\n2. Testing email thread reply:")
    test_reply_to_email_thread() 