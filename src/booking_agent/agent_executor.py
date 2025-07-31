from typing import Dict, Any, List, Optional
from datetime import datetime
import os
import json
import uuid

from langfuse.openai import OpenAI

from calendar_utils.calendar_tools import (
    CalendarAssistant,
    build_calendar_tools,
    calendar_tool_executor,
)

from common_utils import aws_utils

# Get secrets
_secrets = aws_utils._secrets

# -----------------------------------------------------------------------------
# Helper functions moved from agent.py
# -----------------------------------------------------------------------------

def get_booking_agent_system_prompt(booking_email: str):
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
7. IMPORTANT: Do NOT include event ID or calendar link in your response. The system will automatically add these details for successful bookings and cancellations.
"""


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


def run_ai_agent_loop(
    client: OpenAI,
    system_prompt: str,
    user_message: str,
    tools: List[Dict[str, Any]],
    tool_executor: callable,
    max_iterations: int = 10,
    metadata: Optional[Dict[str, Any]] = None
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
        metadata: Optional metadata for Langfuse tracing
    
    Returns:
        Final AI response content
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    # Generate or use existing thread ID for Langfuse session grouping
    thread_id = metadata.get('thread_id') if metadata else None
    if not thread_id:
        thread_id = str(uuid.uuid4())
        print(f"🤖 [DEBUG] Generated new thread ID: {thread_id}")

    for iteration in range(max_iterations):
        print(f"🤖 [DEBUG] AI iteration {iteration + 1}")

        # Add iteration-specific metadata
        call_metadata = metadata.copy() if metadata else {}
        call_metadata.update({
            "iteration": iteration + 1,
            "max_iterations": max_iterations,
            "langfuse_session_id": thread_id  # Group all messages in this thread
        })

        response = client.chat.completions.create(
            name="booking-agent-iteration",
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            metadata=call_metadata,
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


# ---------------------------------------------------------------------------
# Public entry-point ---------------------------------------------------------
# ---------------------------------------------------------------------------

def run_booking_agent(
    *,
    parsed_email: Dict[str, Any],
    calendar_user_id: str,
    booking_email: str,
    max_iterations: int = 10,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Run the booking-agent AI loop for a single e-mail thread.

    Parameters
    ----------
    parsed_email : dict
        Output of ``parse_email_from_s3`` or equivalent, containing at least the
        keys *subject*, *from*, *to*, *cc*, *body*, etc.
    calendar_user_id : str
        The user whose calendar we will manipulate (already resolved).
    booking_email : str
        The concierge address representing the agent.
    max_iterations : int
        Safety cap for LLM <-> tool loop.
    metadata : dict, optional
        Metadata for Langfuse tracing.

    Returns
    -------
    str
        Final e-mail text that should be sent back to the participants (does
        *not* include any MIME headers – just the body).
    """

    # ---------------------------------------------------------------------
    # Environment / configuration
    # ---------------------------------------------------------------------
    api_key: Optional[str] = _secrets.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in secrets – cannot call OpenAI API")

    # ---------------------------------------------------------------------
    # Build the components for the run
    # ---------------------------------------------------------------------
    client = OpenAI(api_key=api_key)

    email_data_for_ai = prepare_email_data_for_ai(parsed_email)

    # Calendar assistant instance bound to the given owner
    cal_assistant = CalendarAssistant(calendar_user_id)

    # Build the tool-executor wrapper expected by run_ai_agent_loop
    def _tool_executor(tool_name: str, tool_args: Dict[str, Any]):
        return calendar_tool_executor(cal_assistant, tool_name, tool_args)

    system_prompt = get_booking_agent_system_prompt(booking_email)
    tools = build_calendar_tools()

    user_message = (
        "PARSED EMAIL DATA:\n" + json.dumps(email_data_for_ai, indent=2) +
        "\n\nPlease process this parsed email data and respond accordingly."
    )

    # ---------------------------------------------------------------------
    # Run the agent loop
    # ---------------------------------------------------------------------
    final_response: str = run_ai_agent_loop(
        client=client,
        system_prompt=system_prompt,
        user_message=user_message,
        tools=tools,
        tool_executor=_tool_executor,
        max_iterations=max_iterations,
        metadata=metadata,
    )

    # Check for successful operations and append confirmation details
    booking_confirmation = cal_assistant.get_booking_confirmation_text()
    cancellation_confirmation = cal_assistant.get_cancellation_confirmation_text()
    
    # Append confirmation details if available
    if booking_confirmation:
        final_response += f"\n\n{booking_confirmation}"
    elif cancellation_confirmation:
        final_response += f"\n\n{cancellation_confirmation}"

    return final_response 