import os
import json
import re
import logging
from typing import List, Optional, Dict, Any
from openai import OpenAI

from common_utils import aws_utils

# Configure logging
logger = logging.getLogger(__name__)

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


def resolve_calendar_owner(parsed_email: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determine which user's calendar to use with improved logic.
    
    Logic:
    1. Find all booking agent emails in the conversation
    2. Look up user records for those emails
    3. Filter out emails that don't have valid owners (drop them)
    4. If no valid owners remain -> return no_mapping
    5. If exactly one valid owner -> return success
    6. If multiple valid owners -> use LLM to disambiguate
    
    Returns:
        Dict with status and data:
        - status: "success", "no_mapping", "multiple_not_sure"
        - user_id: (if success) the user ID
        - assist_email: (if success) the booking agent email
        - candidates: (if multiple_not_sure) list of candidate emails
    """
    # Step 1: Find all booking agent emails in the conversation
    agent_emails = _list_booking_emails(parsed_email)
    logger.debug(f"Booking agent emails in thread: {agent_emails}")
    
    if not agent_emails:
        return {"status": "no_mapping", "reason": "No booking agent emails found in conversation"}
    
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
        return {"status": "no_mapping", "reason": "No valid calendar owners found for booking agent emails"}
    
    # Step 5: If exactly one valid owner
    if len(valid_emails) == 1:
        email = valid_emails[0]
        item = records[email]
        return {
            "status": "success", 
            "user_id": item["user_id"], 
            "assist_email": email
        }
    
    # Step 6: If multiple valid owners -> use LLM to disambiguate
    logger.info(f"Multiple valid owners found: {valid_emails}, using LLM to disambiguate")
    chosen = _disambiguate_owner_with_llm(parsed_email, valid_emails)
    
    if chosen and chosen in records:
        return {
            "status": "success", 
            "user_id": records[chosen]["user_id"], 
            "assist_email": chosen
        }
    
    return {
        "status": "multiple_not_sure", 
        "candidates": valid_emails,
        "reason": "LLM could not confidently choose between multiple valid owners"
    } 