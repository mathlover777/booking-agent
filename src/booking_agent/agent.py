import logging
from typing import Dict, Any, Optional

from common_utils import aws_utils
from .calendar_owner_resolver import resolve_calendar_owner
from .agent_executor import run_booking_agent

# Configure logging
logger = logging.getLogger(__name__)

# Get secrets
_secrets = aws_utils._secrets


def process_booking_request(parsed_email: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Process a booking request from parsed email data.
    
    Assumption: Email is NEVER from the booking agent email, some human made the email.
    We will try to disambiguate which calendar owner to use.
    
    Args:
        parsed_email: Parsed email data from parse_email_from_s3
        metadata: Optional metadata for Langfuse tracing
    
    Returns:
        Dict with processing result:
        - action: "processed", "clarification_needed", "error"
        - ai_response: (if processed) the AI response content
        - clarification_message: (if clarification_needed) message to send
        - status: (if clarification_needed) resolution status
        - reason: (if clarification_needed) reason for failure
        - calendar_user_id: (if processed) the resolved user ID
        - booking_email: (if processed) the booking agent email
    """
    logger.info("Processing booking request")
    logger.info(f"Parsed email with keys: {list(parsed_email.keys())}")
    
    # Resolve calendar owner
    logger.info("Resolving calendar owner")
    owner_resolution = resolve_calendar_owner(parsed_email, metadata)
    logger.info(f"Owner resolution status: {owner_resolution.get('status')}")
    
    # Handle unsuccessful resolution
    if owner_resolution.get("status") != "success":
        status = owner_resolution.get("status")
        reason = owner_resolution.get("reason", "Unknown error")
        
        logger.warning(f"Calendar owner resolution failed: {status} - {reason}")
        
        # Create clarification message based on status
        if status == "no_booking_agents_found":
            message = (
                "Hello,\n\n"
                "I couldn't find any booking agent addresses in this conversation. "
                "Please make sure to include a booking agent email address.\n\n"
                "By VibeCal"
            )
        elif status == "booking_agent_not_registered":
            message = (
                "Hello,\n\n"
                "I found booking agent addresses but they're not properly configured. "
                "Please set up your booking agent first.\n\n"
                "By VibeCal"
            )
        elif status == "calendar_owner_not_in_conversation":
            message = (
                "Hello,\n\n"
                "I found booking agents but the actual calendar owner is not in this conversation. "
                "Please make sure the calendar owner is included in the email thread.\n\n"
                "By VibeCal"
            )
        elif status == "user_email_missing":
            message = (
                "Hello,\n\n"
                "I found booking agents but they're missing user email configuration. "
                "Please contact support to fix this.\n\n"
                "By VibeCal"
            )
        elif status == "multiple_owners_ambiguous":
            candidates = ", ".join(owner_resolution.get("candidates", []))
            message = (
                f"Hello,\n\n"
                f"I found multiple booking agents in this conversation ({candidates}) "
                f"and I'm not sure which calendar to use. Please clarify which one I should reference.\n\n"
                f"By VibeCal"
            )
        else:
            message = (
                "Hello,\n\n"
                "I encountered an issue processing your request. Please try again or contact support.\n\n"
                "By VibeCal"
            )
        
        return {
            "action": "clarification_needed",
            "clarification_message": message,
            "status": status,
            "reason": reason
        }
    
    # Success - run the booking agent
    logger.info(f"Calendar owner resolved: {owner_resolution['user_id']}")
    calendar_user_id = owner_resolution["user_id"]
    booking_email = owner_resolution["assist_email"]
    
    # Run the booking agent
    logger.info("Running booking agent")
    ai_response = run_booking_agent(
        parsed_email=parsed_email,
        calendar_user_id=calendar_user_id,
        booking_email=booking_email,
        metadata=metadata
    )
    
    logger.info("Booking agent completed successfully")
    return {
        "action": "processed",
        "ai_response": ai_response,
        "calendar_user_id": calendar_user_id,
        "booking_email": booking_email
    } 