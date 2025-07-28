import os
import json
import boto3
from openai import OpenAI
from typing import List, Optional, Dict, Any
from datetime import datetime
from calendar.calendar_util import _secrets, get_availability_low_level, book_event_low_level, cancel_event_low_level
from email_util import parse_email_from_s3, send_email_via_ses
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Helper utilities for resolving which user's calendar should be used
# -----------------------------------------------------------------------------

# Domain that identifies booking-agent addresses (e.g. "booking.vibecal.com")
DOMAIN_NAME = os.getenv("DOMAIN_NAME", "booking.bhaang.com")

# DynamoDB table used by user_email_api -> reuse same env var
_DDB_TABLE_NAME = os.getenv("USER_EMAILS_TABLE_NAME")
dynamodb = boto3.resource("dynamodb")
_user_email_table = dynamodb.Table(_DDB_TABLE_NAME) if _DDB_TABLE_NAME else None


def _extract_clean_email(email_addr: str) -> str:
    """Existing helper is moved lower; keep a reference here for reuse."""
    if not email_addr:
        return ""
    if "<" in email_addr and ">" in email_addr:
        match = re.search(r"<([^>]+)>", email_addr)
        if match:
            return match.group(1)
    match = re.search(r"([^\s]+@[^\s]+)", email_addr)
    if match:
        return match.group(1)
    return email_addr


def _list_booking_emails(parsed_email: Dict[str, Any]) -> List[str]:
    """Return all addresses in thread that belong to our booking-agent domain."""
    all_fields = parsed_email.get("from", []) + parsed_email.get("to", []) + parsed_email.get("cc", [])
    emails = {_extract_clean_email(a).lower() for a in all_fields}
    return [e for e in emails if e.endswith(f"@{DOMAIN_NAME}".lower())]


def _lookup_user_records(agent_emails: List[str]) -> Dict[str, Dict[str, Any]]:
    """Query DynamoDB to map assist_email -> item. Returns dict for hits."""
    if not _user_email_table:
        return {}
    results: Dict[str, Dict[str, Any]] = {}
    for addr in agent_emails:
        try:
            resp = _user_email_table.query(
                IndexName="assist_email-index",
                KeyConditionExpression="assist_email = :email",
                ExpressionAttributeValues={":email": addr}
            )
            if resp.get("Items"):
                results[addr] = resp["Items"][0]
        except Exception as e:
            logger.error(f"DynamoDB lookup failed for {addr}: {e}")
    return results


def _disambiguate_owner_with_llm(parsed_email: Dict[str, Any], candidate_emails: List[str]) -> Optional[str]:
    """Use LLM to pick correct booking agent when >1 mapping found.
    Returns chosen booking-agent email or None if not confident."""
    try:
        client = OpenAI(api_key=_secrets.get("OPENAI_API_KEY"))
        system_msg = {
            "role": "system",
            "content": (
                "You are an assistant that decides which concierge email (booking agent) should handle a thread. "
                "Return a JSON with either {\"result\":\"done\", \"booking_agent\":\"email@domain\"} or {\"result\":\"not_sure\"}. "
                "Pick only from this list: " + ", ".join(candidate_emails)
            )
        }
        user_msg = {
            "role": "user",
            "content": (
                "Here is the parsed email data:\n" + json.dumps({
                    "subject": parsed_email.get("subject"),
                    "from": parsed_email.get("from"),
                    "to": parsed_email.get("to"),
                    "cc": parsed_email.get("cc"),
                    "body": parsed_email.get("body")[:1000]  # cap tokens
                })
            )
        }
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[system_msg, user_msg],
            response_format={"type": "json_object"}
        )
        raw_content = response.choices[0].message.content
        data = json.loads(raw_content)
        if data.get("result") == "done" and data.get("booking_agent") in candidate_emails:
            return data["booking_agent"]
        return None
    except Exception as e:
        logger.error(f"LLM disambiguation failed: {e}")
        return None


def _resolve_calendar_owner(parsed_email: Dict[str, Any]) -> Dict[str, Any]:
    """Determine which user's calendar to use. Returns dict with status.
    Possible statuses: success, no_mapping, multiple_not_sure"""
    agent_emails = _list_booking_emails(parsed_email)
    logger.debug(f"Booking agent emails in thread: {agent_emails}")

    records = _lookup_user_records(agent_emails)
    logger.debug(f"DynamoDB records found: {list(records.keys())}")

    if not records:
        return {"status": "no_mapping"}

    if len(records) == 1:
        email, item = next(iter(records.items()))
        return {"status": "success", "user_id": item["user_id"], "assist_email": email}

    # multiple mappings – use LLM to decide
    chosen = _disambiguate_owner_with_llm(parsed_email, list(records.keys()))
    if chosen and chosen in records:
        return {"status": "success", "user_id": records[chosen]["user_id"], "assist_email": chosen}
    return {"status": "multiple_not_sure", "candidates": list(records.keys())}


# -----------------------------------------------------------------------------
# Calendar tools and assistant (imported from calendar package)
# -----------------------------------------------------------------------------

from calendar.calendar_tools import CalendarAssistant, build_calendar_tools, calendar_tool_executor

# -----------------------------------------------------------------------------
# Simplified system prompt (calendar owner already resolved)
# -----------------------------------------------------------------------------


def get_booking_agent_system_prompt():
    booking_email = os.getenv("BOOKING_EMAIL", "book@bhaang.com")
    today_date = datetime.now().strftime("%Y-%m-%d")

    return f"""
SYSTEM:
You are a calendar assistant processing parsed email data. Today's date is {today_date}.

You represent the booking agent address {booking_email}. The calendar owner has already been determined; you do NOT need to figure out whose calendar to use.

Your goals:
1. Analyze the parsed email data (subject, sender, recipients, body) and understand the user's intent.
2. When asked for availability → immediately call get_availability showing 5-6 available 1-hour slots (always include timezone).
3. When the user explicitly confirms a specific slot → call book_event. Always include ALL human emails from the thread (from + to + cc minus {booking_email}) as attendees.
4. When cancelling → call cancel_event with the provided event_id.
5. Never proactively book or cancel without explicit confirmation.
6. After tool calls, reply with a human-readable email starting with "TO: [email]" line indicating greeting recipient, and end with "By VibeCal".
7. When booking succeeds, include "Event ID: [id]" and calendar link.
"""


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

def run_ai_agent_loop(
    client: OpenAI,
    system_prompt: str,
    user_message: str,
    tools: List[Dict[str, Any]],
    tool_executor: callable,
    max_iterations: int = 10
) -> str:
    """
    Generic AI agent loop that can be used with any tool set and executor.
    
    Args:
        client: OpenAI client instance
        system_prompt: System prompt for the AI
        user_message: Initial user message
        tools: List of tool definitions
        tool_executor: Function that executes tools (tool_name, tool_args) -> result
        max_iterations: Maximum number of AI iterations
    
    Returns:
        Final AI response content
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    for iteration in range(max_iterations):
        print(f"🤖 [DEBUG] AI iteration {iteration + 1}")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        assistant_message = response.choices[0].message
        messages.append(assistant_message)

        if assistant_message.tool_calls:
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                try:
                    result = tool_executor(tool_name, tool_args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    })
                except Exception as e:
                    error_result = {"error": str(e)}
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(error_result),
                    })
            continue  # let AI use tool results
        else:
            break  # final answer obtained

    return messages[-1].content





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


def prepare_email_data_for_ai(parsed_email: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare structured email data for AI processing.
    
    Args:
        parsed_email: Parsed email data
    
    Returns:
        Structured data for AI
    """
    return {
        'subject': parsed_email.get('subject', ''),
        'from': parsed_email.get('from', []),
        'to': parsed_email.get('to', []),
        'cc': parsed_email.get('cc', []),
        'body': parsed_email.get('body', ''),
        'date': parsed_email.get('date', ''),
        'message_id': parsed_email.get('message_id', ''),
        'in_reply_to': parsed_email.get('in_reply_to', ''),
        'references': parsed_email.get('references', ''),
        'return_path': parsed_email.get('return_path', '')
    }


def handle_calendar_owner_resolution(parsed_email: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle calendar owner resolution and return appropriate response.
    
    Args:
        parsed_email: Parsed email data
    
    Returns:
        Dict with resolution result or error response
    """
    owner_resolution = _resolve_calendar_owner(parsed_email)
    
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