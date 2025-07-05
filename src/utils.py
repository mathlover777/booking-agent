import json
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Any


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
        'message_id': msg.get('Message-ID', '')
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