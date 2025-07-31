import os
import json
import re
from typing import List, Optional, Dict, Any
from langfuse.openai import OpenAI

from common_utils import aws_utils
from common_utils.email_helpers import to_local
from common_utils.log_util import get_logger

# Get logger for this module
logger = get_logger(__name__)

# Get secrets
_secrets = aws_utils._secrets

# Domain that identifies booking-agent addresses (e.g. "booking.vibecal.com")
DOMAIN_NAME = os.getenv("DOMAIN_NAME")

logger.info(f"DOMAIN_NAME: {DOMAIN_NAME}")

# Get table from aws_utils
_user_email_table = aws_utils.user_emails_table


def _extract_clean_email(email_addr: str) -> str:
    """Extract clean email address from various formats."""
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
    if not DOMAIN_NAME:
        return []
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
            # Convert full email to local part for database query
            local_part = to_local(addr)
            resp = _user_email_table.query(
                IndexName="assist_local-index",
                KeyConditionExpression="assist_local = :local",
                ExpressionAttributeValues={":local": local_part}
            )
            if resp.get("Items"):
                results[addr] = resp["Items"][0]
        except Exception as e:
            logger.error(f"DynamoDB lookup failed for {addr}: {e}")
    return results


def _is_user_in_conversation(user_email: str, parsed_email: Dict[str, Any]) -> bool:
    """Check if the actual user email is present in the conversation (case-insensitive)."""
    if not user_email:
        return False
    
    # Get all emails from the conversation
    all_fields = parsed_email.get("from", []) + parsed_email.get("to", []) + parsed_email.get("cc", [])
    conversation_emails = {_extract_clean_email(a).lower() for a in all_fields}
    
    # Check if user email is in conversation (case-insensitive)
    return user_email.lower() in conversation_emails


def _disambiguate_owner_with_llm(parsed_email: Dict[str, Any], candidate_emails: List[str], metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
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
        
        # Add disambiguation-specific metadata with thread ID for session grouping
        call_metadata = metadata.copy() if metadata else {}
        call_metadata.update({
            "stage": "calendar_owner_disambiguation",
            "candidate_count": len(candidate_emails),
            "candidates": candidate_emails
        })
        
        # Use thread_id as langfuse_session_id if available
        thread_id = metadata.get('thread_id') if metadata else None
        if thread_id:
            call_metadata["langfuse_session_id"] = thread_id
        
        response = client.chat.completions.create(
            name="calendar-owner-disambiguation",
            model="gpt-4o",
            messages=[system_msg, user_msg],
            response_format={"type": "json_object"},
            metadata=call_metadata,
        )
        raw_content = response.choices[0].message.content
        data = json.loads(raw_content)
        if data.get("result") == "done" and data.get("booking_agent") in candidate_emails:
            return data["booking_agent"]
        return None
    except Exception as e:
        logger.error(f"LLM disambiguation failed: {e}")
        return None


def resolve_calendar_owner(parsed_email: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Determine which user's calendar to use with security checks.
    
    Logic:
    1. Find all booking agent emails in the conversation
    2. Look up user records for those emails
    3. Filter out emails that don't have valid owners
    4. For each valid owner, check if the actual user email is in the conversation
    5. If no valid owners remain -> return booking_agent_not_registered
    6. If no owners are in conversation -> return calendar_owner_not_in_conversation
    7. If exactly one valid owner in conversation -> return success
    8. If multiple valid owners in conversation -> use LLM to disambiguate
    
    Returns:
        Dict with status and data:
        - status: "success", "no_booking_agents_found", "booking_agent_not_registered", 
                 "calendar_owner_not_in_conversation", "user_email_missing", "multiple_owners_ambiguous"
        - user_id: (if success) the user ID
        - assist_email: (if success) the booking agent email
        - candidates: (if multiple_owners_ambiguous) list of candidate emails
    """
    # Step 1: Find all booking agent emails in the conversation
    agent_emails = _list_booking_emails(parsed_email)
    logger.debug(f"Booking agent emails in thread: {agent_emails}")
    
    if not agent_emails:
        return {"status": "no_booking_agents_found", "reason": "No booking agent emails found in conversation"}
    
    # Step 2: Look up user records for those emails
    records = _lookup_user_records(agent_emails)
    logger.debug(f"DynamoDB records found: {list(records.keys())}")
    
    # Step 3: Filter out emails that don't have valid owners
    valid_emails = list(records.keys())
    invalid_emails = [email for email in agent_emails if email not in valid_emails]
    
    if invalid_emails:
        logger.info(f"Dropping invalid booking agent emails: {invalid_emails}")
    
    # Step 4: If no valid owners remain
    if not valid_emails:
        return {"status": "booking_agent_not_registered", "reason": "No valid calendar owners found for booking agent emails"}
    
    # Step 5: Check if actual users are in conversation and handle missing user_email
    owners_in_conversation = []
    missing_user_emails = []
    
    for email in valid_emails:
        item = records[email]
        user_email = item.get("user_email")
        
        if not user_email:
            missing_user_emails.append(email)
            logger.warning(f"Missing user_email for booking agent: {email}")
            continue
        
        if _is_user_in_conversation(user_email, parsed_email):
            owners_in_conversation.append(email)
        else:
            logger.info(f"User {user_email} not in conversation for booking agent: {email}")
    
    # Step 6: Handle missing user_email cases
    if missing_user_emails:
        return {
            "status": "user_email_missing", 
            "reason": f"Booking agents found but user_email field missing: {missing_user_emails}"
        }
    
    # Step 7: If no owners are in conversation
    if not owners_in_conversation:
        return {
            "status": "calendar_owner_not_in_conversation", 
            "reason": "Booking agents found but actual calendar owners not in conversation"
        }
    
    # Step 8: If exactly one valid owner in conversation
    if len(owners_in_conversation) == 1:
        email = owners_in_conversation[0]
        item = records[email]
        return {
            "status": "success", 
            "user_id": item["user_id"], 
            "assist_email": email
        }
    
    # Step 9: If multiple valid owners in conversation -> use LLM to disambiguate
    logger.info(f"Multiple valid owners in conversation: {owners_in_conversation}, using LLM to disambiguate")
    chosen = _disambiguate_owner_with_llm(parsed_email, owners_in_conversation, metadata)
    
    if chosen and chosen in records:
        return {
            "status": "success", 
            "user_id": records[chosen]["user_id"], 
            "assist_email": chosen
        }
    
    return {
        "status": "multiple_owners_ambiguous", 
        "candidates": owners_in_conversation,
        "reason": "LLM could not confidently choose between multiple valid owners in conversation"
    } 