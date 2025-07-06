import os
import json
import boto3
from openai import OpenAI
from typing import List, Optional
from datetime import datetime
from clerk_util import CALENDAR_TOOLS, get_availability, book_event, cancel_event
from email_util import parse_email_from_s3, send_email_via_ses
import re
from clerk_util import _secrets

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

**CRITICAL RULE**: When someone asks about availability or scheduling, you MUST immediately use the get_availability tool. Do not just say you'll check - actually make the tool call.

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
   - **MANDATORY**: When someone asks about availability, booking, or scheduling → IMMEDIATELY use the get_availability tool to check calendar and show 5-6 available 1-hour slots
   - **DO NOT** just say you'll check - actually call the get_availability tool right away
   - If explicitly confirming a specific slot (e.g., "Yes, book me for 2pm tomorrow", "Please schedule it for Friday 3pm") → use the book_event tool to create the event
   - **CRITICAL**: When booking an event, ALWAYS include ALL human users from the email thread as attendees (excluding the booking email address). This ensures everyone in the conversation gets invited to the meeting.
   - **ATTENDEE EXTRACTION**: You MUST extract ALL email addresses from the parsed email data: from the "from" field, "to" field, and "cc" field. Add ALL of these as attendees to the book_event tool call.
   - **EXAMPLE**: If email has from: ["john@example.com"], to: ["book@bhaang.com"], cc: ["jane@example.com", "bob@example.com"], then attendees should be ["john@example.com", "jane@example.com", "bob@example.com"] (excluding book@bhaang.com).
   - If the request is unclear or ambiguous → show availability and ask for explicit confirmation before booking
   - If cancelling → use the cancel_event tool if you can identify the event ID from the conversation
   - If cancelling but no event ID found → ask the user to provide the event ID or share the calendar link
   - **NEVER proactively book or cancel** - only do these actions when explicitly requested
   - **IMPORTANT**: Only book events when there's clear, explicit confirmation from a human. If in doubt, ask for confirmation rather than booking.
   - **IMPORTANT**: If a tool returns an error with "User not found", try with a different email address from the thread. This means the calendar owner you selected doesn't have their calendar connected. Try other participants in the email thread until you find one with a connected calendar.

4. **Final response**:
   - Provide a human-readable email reply that addresses the user's request
   - **Dynamically determine who to address in the greeting**:
     * If this is a direct reply to someone asking for availability/booking → address greeting to that person
     * If this is a group conversation → address greeting to the person who initiated the booking request
     * If someone is confirming a specific time slot → address greeting to that person
     * If unclear → address greeting to the sender of the most recent relevant message (not from `{booking_email}`)
   - **IMPORTANT**: Start your response with "TO: [email_address]" on a separate line to specify who the greeting should address
   - When showing availability, present 5-6 specific 1-hour time slots that are free
   - **Always display timezone in human-readable format** when showing available slots (e.g., "2:00 PM - 3:00 PM (EST)" or "10:00 AM - 11:00 AM (PST)")
   - Make it easy for the user to choose a slot by clearly listing the available times with timezone
   - **When booking an appointment**: Always include the event ID and calendar link in your response (e.g., "I've booked your appointment. Event ID: abc123xyz. Calendar link: https://calendar.google.com/...")
   - Include all email addresses found in the email thread in the `email_ids` array
   - Exclude `{booking_email}` from the `email_ids` array since you'll be sending from that address
   - **Always end your response with**: "By VibeCal" as the signature

5. **Error handling for calendar tools**:
   - If get_availability or book_event returns {{"error": "User not found", "message": "..."}}, this means the email address you tried doesn't have a calendar connected
   - In this case, try the same operation with a different email address from the email thread
   - Look at all email addresses in the thread (from, to, cc fields) and try them one by one until you find one that works
   - Do NOT try the booking email ({booking_email}) - it's the AI assistant's email
   - Only give up if you've tried all email addresses in the thread and none have connected calendars
   - This is NOT a system error - it's a normal case where someone's calendar isn't connected
   - When you find a working calendar, proceed with the normal response flow

6. **Booking confirmation guidelines**:
   - **Your responsibility**: Always proactively suggest available time slots - humans will only select among your suggestions
   - **Example workflow**: User asks "What's your availability?" → You MUST call get_availability tool → Show results → Ask for confirmation
   - **Explicit confirmation examples**: "Yes, book me for 2pm tomorrow", "Please schedule it for Friday 3pm", "That works, please book it", "I confirm for 10am on Tuesday"
   - **NOT explicit confirmation**: "That time looks good", "I'm available then", "That should work", "Sounds good" - these require follow-up confirmation
   - When showing availability, always ask for explicit confirmation before booking
   - If someone suggests a time but doesn't explicitly confirm, ask "Would you like me to book you for [specific time]?"
   - **ATTENDEE REQUIREMENT**: When booking an event, you MUST include ALL human participants from the email thread as attendees (excluding the booking email address). Extract all email addresses from the from, to, and cc fields and add them to the attendees list.
   - **MANDATORY ATTENDEE LIST**: Before calling book_event, create a complete list of all email addresses found in the parsed email data (from + to + cc fields), remove the booking email address, and pass this complete list as the attendees parameter.
   - **VERIFICATION**: Double-check that you've included every human email address from the thread before booking. Missing attendees means people won't get invited to the meeting.
   - **After booking**: Always include the event ID and calendar link in your response so users can reference it for cancellations
   - **For cancellations**: Look for event IDs in the conversation history. If not found, ask user to provide the event ID or share the calendar link

7. **Email analysis tips**:
   - Use Return-Path as the most reliable sender identifier
   - Extract current message (before quoted text starting with ">")
   - Remove email signatures (lines starting with "--" or containing "Regards,")
   - Parse email addresses from "Name <email@domain.com>" format

Remember: You're working with already parsed email data, so focus on understanding the content and responding appropriately. When in doubt about booking, ask for confirmation rather than proceeding.
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
        # Get email content from S3
        print(f"📧 [DEBUG] Getting email content from S3")
        s3_client = boto3.client('s3')
        response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        email_content = response['Body'].read().decode('utf-8')
        print(f"📧 [DEBUG] Retrieved email content, length: {len(email_content)} characters")
        
        # Parse email using standard library
        print(f"📧 [DEBUG] Parsing email content")
        parsed_email = parse_email_from_s3(email_content)
        print(f"📧 [DEBUG] Parsed email keys: {list(parsed_email.keys())}")
        
        # Initialize OpenAI client
        print(f"📧 [DEBUG] Initializing OpenAI client")
        api_key = _secrets.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in secrets")
        client = OpenAI(api_key=api_key)
        
        # Get system prompt
        print(f"📧 [DEBUG] Getting system prompt")
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

        print(f"📧 [DEBUG] Email data for AI: {json.dumps(email_data_for_ai)}")
        
        # Initialize conversation
        print(f"📧 [DEBUG] Initializing conversation with system prompt")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"PARSED EMAIL DATA:\n{json.dumps(email_data_for_ai, indent=2)}\n\nPlease process this parsed email data and respond according to the system prompt."}
        ]
        
        
        # Tool calling loop
        max_iterations = 5  # Prevent infinite loops
        for iteration in range(max_iterations):
            print(f"🤖 [DEBUG] AI iteration {iteration + 1}")
            
            # Call OpenAI with tools
            print(f"🤖 [DEBUG] Making OpenAI API call with {len(messages)} messages")
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=CALENDAR_TOOLS,
                tool_choice="auto"
            )
            
            # Get the assistant's message
            assistant_message = response.choices[0].message
            messages.append(assistant_message)

            print(f"🤖 [DEBUG] Assistant message: {assistant_message}")
            
            # Check if there are tool calls
            if assistant_message.tool_calls:
                print(f"🤖 [DEBUG] Processing {len(assistant_message.tool_calls)} tool calls")
                
                # Process each tool call
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    print(f"🤖 [DEBUG] Tool call - name: {tool_name}, args: {tool_args}")
                    
                    # Execute the tool
                    try:
                        print(f"🤖 [DEBUG] Executing tool: {tool_name}")
                        print(f"🤖 [DEBUG] Tool arguments: {tool_args}")
                        
                        if tool_name == "get_availability":
                            print(f"🤖 [DEBUG] Calling get_availability with owner_email: {tool_args['owner_email']}")
                            result = get_availability(
                                owner_email=tool_args["owner_email"],
                                start_date=tool_args["start_date"],
                                end_date=tool_args["end_date"]
                            )
                            print(f"🤖 [DEBUG] get_availability result: {result}")
                        elif tool_name == "book_event":
                            print(f"🤖 [DEBUG] Calling book_event with owner_email: {tool_args['owner_email']}")
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
                            print(f"🤖 [DEBUG] book_event result: {result}")
                        elif tool_name == "cancel_event":
                            print(f"🤖 [DEBUG] Calling cancel_event with owner_email: {tool_args['owner_email']}, event_id: {tool_args['event_id']}")
                            result = cancel_event(
                                owner_email=tool_args["owner_email"],
                                event_id=tool_args["event_id"],
                                notify_attendees=tool_args.get("notify_attendees", True)
                            )
                            print(f"🤖 [DEBUG] cancel_event result: {result}")
                        else:
                            print(f"🤖 [DEBUG] Unknown tool: {tool_name}")
                            result = {"error": f"Unknown tool: {tool_name}"}
                        
                        # Add tool result to messages
                        print(f"🤖 [DEBUG] Adding tool result to messages: {result}")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result)
                        })
                        
                    except Exception as e:
                        print(f"❌ [DEBUG] Tool execution error: {e}")
                        error_result = {"error": str(e)}
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(error_result)
                        })
                        print(f"🤖 [DEBUG] Added error result to messages: {error_result}")
                
                # Continue the loop to let AI process tool results
                print(f"🤖 [DEBUG] Continuing loop to let AI process tool results")
                continue
            else:
                # No tool calls, AI has provided final response
                print(f"🤖 [DEBUG] AI provided final response without tool calls")
                break
        
        # Extract the final response from the last assistant message
        final_response = messages[-1].content

        print(f"📧 [DEBUG] Final response: {final_response}")
        
        # Send the AI response to all participants in the thread
        print(f"📧 [DEBUG] Sending AI response to thread")
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