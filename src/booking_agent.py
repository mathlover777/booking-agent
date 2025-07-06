import os
import json
import boto3
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from clerk_util import CALENDAR_TOOLS, get_availability, book_event
from email_util import parse_email_from_s3, send_email_via_ses
import re

def get_booking_agent_system_prompt():
    """
    Get the booking agent system prompt with the booking email from environment variable.
    
    Returns:
        str: The system prompt with the booking email substituted from BOOKING_EMAIL env var
    """
    booking_email = os.getenv('BOOKING_EMAIL', 'book@bhaang.com')
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    return f"""
SYSTEM:
You are a calendar assistant that processes parsed email data. Today's date is {today_date}.

Your goals:

1. **Analyze the parsed email data**:
   - Review the subject, sender, recipients, and email body
   - Identify the current message content (ignore quoted text, signatures)
   - Find all email addresses in the thread
   - Determine if this email is from `{booking_email}` (if so, do nothing)

2. **Determine calendar owner**:
   - Look for the first message in the thread that mentions `{booking_email}`; the **sender** is the owner
   - Fallback: use the sender of the **earliest** message in the thread
   - If the **last message** is from `{booking_email}`, **do nothing** to avoid loops
   - If unclear, ask for clarification

3. **Handle intent**:
   - If asking for availability or booking help → automatically use the get_availability tool to check calendar for the next 7-14 days and show 5-6 available 1-hour slots
   - If confirming a specific slot → use the book_event tool to create the event
   - If cancelling → acknowledge the cancellation request
   - If unclear → proactively offer to check availability for the next week and show available slots

4. **Final response**:
   - Provide a human-readable email reply that addresses the user's request
   - **Dynamically determine who to address in the greeting**:
     * If this is a direct reply to someone asking for availability/booking → address greeting to that person
     * If this is a group conversation → address greeting to the person who initiated the booking request
     * If someone is confirming a specific time slot → address greeting to that person
     * If unclear → address greeting to the sender of the most recent relevant message (not from `{booking_email}`)
   - **IMPORTANT**: Start your response with "TO: [email_address]" on a separate line to specify who the greeting should address
   - When showing availability, present 5-6 specific 1-hour time slots that are free
   - Make it easy for the user to choose a slot by clearly listing the available times
   - Include all email addresses found in the email thread in the `email_ids` array
   - Exclude `{booking_email}` from the `email_ids` array since you'll be sending from that address
   - **Always end your response with**: "By VibeCal" as the signature

5. **Email analysis tips**:
   - Use Return-Path as the most reliable sender identifier
   - Extract current message (before quoted text starting with ">")
   - Remove email signatures (lines starting with "--" or containing "Regards,")
   - Parse email addresses from "Name <email@domain.com>" format

Remember: You're working with already parsed email data, so focus on understanding the content and responding appropriately.
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


def _extract_clean_email(email_addr: str) -> str:
    """
    Extract clean email address from various formats.
    
    Args:
        email_addr: Email address in various formats (e.g., "Name <email@domain.com>", "email@domain.com")
    
    Returns:
        Clean email address
    """
    if not email_addr:
        return ""
    
    # Extract email from "Name <email@domain.com>" format
    if '<' in email_addr and '>' in email_addr:
        match = re.search(r'<([^>]+)>', email_addr)
        if match:
            return match.group(1)
    
    # Extract email from "email@domain.com" format (handle spaces)
    match = re.search(r'([^\s]+@[^\s]+)', email_addr)
    if match:
        return match.group(1)
    
    return email_addr


def process_email_with_ai(s3_bucket: str, s3_key: str) -> dict:
    """
    Process an email from S3 through the AI agent using parsed email data.
    
    Args:
        s3_bucket: S3 bucket name
        s3_key: S3 object key
    
    Returns:
        Dict containing AI agent response with structured data
    """
    try:
        # Get email content from S3
        s3_client = boto3.client('s3')
        response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        email_content = response['Body'].read().decode('utf-8')
        
        # Parse email using standard library
        parsed_email = parse_email_from_s3(email_content)
        
        # Initialize OpenAI client
        client = OpenAI()
        
        # Get system prompt
        system_prompt = get_booking_agent_system_prompt()
        
        # Prepare structured data for AI
        email_data_for_ai = {
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

        print(f"Email data for AI: {json.dumps(email_data_for_ai)}")
        
        # Initialize conversation
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"PARSED EMAIL DATA:\n{json.dumps(email_data_for_ai, indent=2)}\n\nPlease process this parsed email data and respond according to the system prompt."}
        ]
        
        
        # Tool calling loop
        max_iterations = 5  # Prevent infinite loops
        for iteration in range(max_iterations):
            print(f"AI iteration {iteration + 1}")
            
            # Call OpenAI with tools
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=CALENDAR_TOOLS,
                tool_choice="auto"
            )
            
            # Get the assistant's message
            assistant_message = response.choices[0].message
            messages.append(assistant_message)

            print(f"Assistant message: {assistant_message}")
            
            # Check if there are tool calls
            if assistant_message.tool_calls:
                print(f"Processing {len(assistant_message.tool_calls)} tool calls")
                
                # Process each tool call
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    print(f"Executing tool: {tool_name} with args: {tool_args}")
                    
                    # Execute the tool
                    try:
                        if tool_name == "get_availability":
                            result = get_availability(
                                owner_email=tool_args["owner_email"],
                                start_date=tool_args["start_date"],
                                end_date=tool_args["end_date"]
                            )
                            print(f"Availability result: {result}")
                        elif tool_name == "book_event":
                            result = book_event(
                                owner_email=tool_args["owner_email"],
                                date=tool_args["date"],
                                start_time=tool_args["start_time"],
                                end_time=tool_args["end_time"],
                                title=tool_args["title"],
                                description=tool_args.get("description", ""),
                                attendees=tool_args.get("attendees"),
                                location=tool_args.get("location", ""),
                                reminders=tool_args.get("reminders")
                            )
                        else:
                            result = {"error": f"Unknown tool: {tool_name}"}
                        
                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result)
                        })
                        
                    except Exception as e:
                        error_result = {"error": str(e)}
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(error_result)
                        })
                        print(f"Tool execution error: {e}")
                
                # Continue the loop to let AI process tool results
                continue
            else:
                # No tool calls, AI has provided final response
                print("AI provided final response without tool calls")
                break
        
        # Extract the final response from the last assistant message
        final_response = messages[-1].content

        print(f"Final response: {final_response}")
        
        # Send the AI response to all participants in the thread
        send_result = send_ai_response_to_thread(parsed_email, final_response)
        
        if send_result['success']:
            print(f"✅ AI response sent successfully! Message ID: {send_result['message_id']}")
            return {
                'action': 'processed',
                'email_response': final_response,
                'send_result': send_result,
                'parsed_email_data': email_data_for_ai
            }
        else:
            print(f"❌ Failed to send AI response: {send_result['error']}")
            return {
                'action': 'error',
                'error': send_result['error'],
                'email_response': final_response,
                'send_result': send_result,
                'parsed_email_data': email_data_for_ai
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