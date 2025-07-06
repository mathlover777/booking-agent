import os
import json
import boto3
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from clerk_util import CALENDAR_TOOLS, get_availability, book_event
from email_util import parse_email_from_s3

class BookingAgentResponse(BaseModel):
    """Response format for the booking agent"""
    owner_email: Optional[str] = Field(None, description="Email address of the calendar owner")
    email_response: str = Field(..., description="Human readable response to send back")
    email_ids: List[str] = Field(default_factory=list, description="List of email addresses found in the thread (excluding booking email)")

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
   - **Always address the response to whoever sent the last message in the thread**
   - When showing availability, present 5-6 specific 1-hour time slots that are free
   - Make it easy for the user to choose a slot by clearly listing the available times
   - Include all email addresses found in the email thread in the `email_ids` array
   - Exclude `{booking_email}` from the `email_ids` array since you'll be sending from that address

5. **Email analysis tips**:
   - Use Return-Path as the most reliable sender identifier
   - Extract current message (before quoted text starting with ">")
   - Remove email signatures (lines starting with "--" or containing "Regards,")
   - Parse email addresses from "Name <email@domain.com>" format

Remember: You're working with already parsed email data, so focus on understanding the content and responding appropriately.
"""


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
        
        # Parse the response to extract structured data
        # For now, we'll extract email addresses and owner email from the response
        # In a more sophisticated implementation, you might want to use a structured output format
        
        # Extract email addresses from the email data
        # email_ids = []
        # for field in ['from', 'to', 'cc']:
        #     for email_entry in email_data_for_ai.get(field, []):
        #         # Extract email from "Name <email@domain.com>" format
        #         if '<' in email_entry and '>' in email_entry:
        #             email = email_entry.split('<')[1].split('>')[0]
        #         else:
        #             email = email_entry
                
        #         # Exclude the booking email
        #         booking_email = os.getenv('BOOKING_EMAIL', 'book@bhaang.com')
        #         if email != booking_email:
        #             email_ids.append(email)
        
        # # Remove duplicates while preserving order
        # email_ids = list(dict.fromkeys(email_ids))
        
        # # Try to extract owner email from the response or use a fallback
        # owner_email = None
        # # Look for the first email in 'from' field as a fallback
        # if email_data_for_ai.get('from'):
        #     from_entry = email_data_for_ai['from'][0]
        #     if '<' in from_entry and '>' in from_entry:
        #         owner_email = from_entry.split('<')[1].split('>')[0]
        #     else:
        #         owner_email = from_entry
        
        # return {
        #     'action': 'processed',
        #     'owner_email': owner_email,
        #     'email_response': final_response,
        #     'email_ids': email_ids,
        #     'parsed_email_data': email_data_for_ai
        # }
        
    except Exception as e:
        print(f"❌ Error processing email with AI: {e}")
        return {
            'action': 'error',
            'error': str(e),
            'owner_email': None,
            'email_response': f"Sorry, I encountered an error processing your request: {str(e)}",
            'email_ids': []
        }