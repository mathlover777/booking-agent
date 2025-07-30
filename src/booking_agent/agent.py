import os
import json
import boto3
from openai import OpenAI
from typing import List, Optional, Dict, Any
from datetime import datetime
from email_util import parse_email_from_s3, send_email_via_ses
import re
import logging

from common_utils import aws_utils

# Configure logging
logger = logging.getLogger(__name__)

# Get secrets
_secrets = aws_utils._secrets

# -----------------------------------------------------------------------------
# Calendar owner resolution (imported from separate module)
# -----------------------------------------------------------------------------

from .calendar_owner_resolver import resolve_calendar_owner, _extract_clean_email


# -----------------------------------------------------------------------------
# Calendar tools and assistant (imported from calendar package)
# -----------------------------------------------------------------------------

from calendar_utils.calendar_tools import CalendarAssistant, build_calendar_tools, calendar_tool_executor

# -----------------------------------------------------------------------------
# Simplified system prompt (calendar owner already resolved)
# -----------------------------------------------------------------------------

# Import helper functions from agent_executor module
from .agent_executor import (
    get_booking_agent_system_prompt,
    prepare_email_data_for_ai,
    run_ai_agent_loop,
)


def send_ai_response_to_thread(parsed_email: dict, ai_response_content: str) -> dict:
    """
    Send the AI response to all participants in the email thread (reply all).
    
    Args:
        parsed_email: Parsed email data from parse_email_from_s3
        ai_response_content: The AI-generated response content to send
    
    Returns:
        Dict with send result
    """
    import re
    import os
    
    booking_email = os.getenv('BOOKING_EMAIL', 'book@bhaang.com')
    
    # Parse the "TO:" line from AI response to determine greeting recipient
    lines = ai_response_content.strip().split('\n')
    greeting_recipient = None
    cleaned_response_content = ai_response_content
    
    # Look for "TO: [email]" at the beginning of the response
    if lines and lines[0].strip().upper().startswith('TO:'):
        to_line = lines[0].strip()
        email_match = re.search(r'TO:\s*([^\s]+@[^\s]+)', to_line, re.IGNORECASE)
        if email_match:
            greeting_recipient = email_match.group(1)
            # Remove the TO: line from the response content
            cleaned_response_content = '\n'.join(lines[1:]).strip()
            print(f"🎯 AI specified greeting recipient: {greeting_recipient}")
    
    # Get all participants from the email thread
    all_participants = []
    
    # Add sender (from field)
    from_addresses = parsed_email.get('from', [])
    for email_addr in from_addresses:
        clean_email = _extract_clean_email(email_addr)
        if clean_email and clean_email.lower() != booking_email.lower():
            all_participants.append(clean_email)
    
    # Add all recipients (to + cc) except booking email
    to_addresses = parsed_email.get('to', [])
    cc_addresses = parsed_email.get('cc', [])
    
    for email_addr in to_addresses + cc_addresses:
        clean_email = _extract_clean_email(email_addr)
        if (clean_email and 
            clean_email.lower() != booking_email.lower() and 
            clean_email not in all_participants):
            all_participants.append(clean_email)
    
    if not all_participants:
        return {
            'success': False,
            'error': 'No valid recipients found (all participants are booking email)'
        }
    
    # Get threading information
    message_id = parsed_email.get('message_id', '')
    references = parsed_email.get('references', '')
    
    # If this is a reply, add the current message ID to references
    if message_id and references:
        references = f"{references} {message_id}"
    elif message_id:
        references = message_id
    
    # Determine subject (add Re: if not already present)
    subject = parsed_email.get('subject', '')
    if not subject.lower().startswith('re:'):
        subject = f"Re: {subject}"
    
    print(f"📧 Sending AI response to {len(all_participants)} participants:")
    for participant in all_participants:
        print(f"  → {participant}")
    
    # Send the AI response to all participants
    return send_email_via_ses(
        to_addresses=all_participants,
        subject=subject,
        body=cleaned_response_content,
        reply_to_message_id=message_id,
        reply_to_references=references
    )


def get_all_email_addresses_from_thread(parsed_email: dict) -> List[str]:
    """
    Extract all unique email addresses from the email thread.
    
    Args:
        parsed_email: Parsed email data from parse_email_from_s3
    
    Returns:
        List of clean email addresses (excluding booking email)
    """
    booking_email = os.getenv('BOOKING_EMAIL', 'book@bhaang.com')
    all_emails = set()
    
    # Add sender (from field)
    from_addresses = parsed_email.get('from', [])
    for email_addr in from_addresses:
        clean_email = _extract_clean_email(email_addr)
        if clean_email and clean_email.lower() != booking_email.lower():
            all_emails.add(clean_email)
    
    # Add all recipients (to + cc) except booking email
    to_addresses = parsed_email.get('to', [])
    cc_addresses = parsed_email.get('cc', [])
    
    for email_addr in to_addresses + cc_addresses:
        clean_email = _extract_clean_email(email_addr)
        if (clean_email and 
            clean_email.lower() != booking_email.lower()):
            all_emails.add(clean_email)
    
    return list(all_emails)


# -----------------------------------------------------------------------------
# Generic AI agent loop function
# -----------------------------------------------------------------------------

# This function has been moved to agent_executor.py

# -----------------------------------------------------------------------------
# Email processing helper functions
# -----------------------------------------------------------------------------

def load_email_from_s3(s3_bucket: str, s3_key: str) -> str:
    """
    Load email content from S3.
    
    Args:
        s3_bucket: S3 bucket name
        s3_key: S3 object key
    
    Returns:
        Email content as string
    """
    print(f"📧 [DEBUG] Getting email content from S3")
    s3_client = boto3.client('s3')
    response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
    email_content = response['Body'].read().decode('utf-8')
    print(f"📧 [DEBUG] Retrieved email content, length: {len(email_content)} characters")
    return email_content


def handle_calendar_owner_resolution(parsed_email: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle calendar owner resolution and return appropriate response.
    
    Args:
        parsed_email: Parsed email data
    
    Returns:
        Dict with resolution result or error response
    """
    owner_resolution = resolve_calendar_owner(parsed_email)
    
    if owner_resolution.get("status") == "no_mapping":
        error_msg = (
            "TO: unknown\n"
            "Hello,\n\n"
            "I couldn't find a calendar linked to this concierge address. "
            "Please configure your booking agent.\n\nBy VibeCal"
        )
        send_email_via_ses(parsed_email.get("from", []), "Concierge not configured", error_msg)
        return {"action": "error", "error": "No concierge mapping found"}

    if owner_resolution.get("status") == "multiple_not_sure":
        candidates = ", ".join(owner_resolution["candidates"])
        clar_msg = (
            f"TO: unknown\nHello,\n\nI found multiple booking agents in this conversation ({candidates}) "
            "and I'm not sure which calendar to use. Please clarify which one I should reference.\n\nBy VibeCal"
        )
        send_email_via_ses(parsed_email.get("from", []), "Need clarification", clar_msg)
        return {"action": "clarification_requested"}

    return {"action": "success", "user_id": owner_resolution["user_id"]}


def process_email_with_ai(s3_bucket: str, s3_key: str) -> dict:
    """
    Process an email from S3 through the AI agent using parsed email data.
    
    Args:
        s3_bucket: S3 bucket name
        s3_key: S3 object key
    
    Returns:
        Dict containing AI agent response with structured data
    """
    print(f"📧 [DEBUG] process_email_with_ai called with s3_bucket: {s3_bucket}, s3_key: {s3_key}")
    try:
        # Load and parse email
        email_content = load_email_from_s3(s3_bucket, s3_key)
        parsed_email = parse_email_from_s3(email_content)
        print(f"📧 [DEBUG] Parsed email keys: {list(parsed_email.keys())}")
        
        # Initialize OpenAI client
        print(f"📧 [DEBUG] Initializing OpenAI client")
        api_key = _secrets.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in secrets")
        client = OpenAI(api_key=api_key)
        
        # Prepare email data for AI
        email_data_for_ai = prepare_email_data_for_ai(parsed_email)
        print(f"📧 [DEBUG] Email data for AI: {json.dumps(email_data_for_ai)}")
        
        # Handle calendar owner resolution
        owner_result = handle_calendar_owner_resolution(parsed_email)
        if owner_result.get("action") != "success":
            return owner_result

        calendar_user_id = owner_result["user_id"]
        cal = CalendarAssistant(calendar_user_id)

        # Run AI agent loop
        tools = build_calendar_tools()
        system_prompt = get_booking_agent_system_prompt()
        user_message = (
            "PARSED EMAIL DATA:\n" + json.dumps(email_data_for_ai, indent=2) +
            "\n\nPlease process this parsed email data and respond accordingly."
        )
        
        # Create tool executor bound to this calendar assistant
        def tool_executor(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
            return calendar_tool_executor(cal, tool_name, tool_args)

        final_response = run_ai_agent_loop(
            client=client,
            system_prompt=system_prompt,
            user_message=user_message,
            tools=tools,
            tool_executor=tool_executor
        )

        # Send the AI response to all participants
        send_result = send_ai_response_to_thread(parsed_email, final_response)

        if send_result.get("success"):
            return {
                "action": "processed",
                "email_response": final_response,
                "send_result": send_result,
                "parsed_email_data": email_data_for_ai,
            }
        else:
            return {
                "action": "error",
                "error": send_result.get("error"),
                "email_response": final_response,
                "parsed_email_data": email_data_for_ai,
            }
        
    except Exception as e:
        print(f"❌ Error processing email with AI: {e}")
        return {
            'action': 'error',
            'error': str(e),
            'owner_email': None,
            'email_response': f"Sorry, I encountered an error processing your request: {str(e)}",
            'email_ids': []
        } 