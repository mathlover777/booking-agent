import json
import email
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
        'references': msg.get('References', '')
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