import boto3
import json
import os
from botocore.exceptions import ClientError

def get_bedrock_client():
    """Initialize Bedrock client"""
    return boto3.client(
        'bedrock-runtime',
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )

def get_ai_response(system_prompt, user_message, conversation_history=None):
    """Get response from Claude with enhanced context and validation"""
    
    # Validate inputs
    if not user_message or not user_message.strip():
        return "I didn't receive a message. Could you please ask me something?"
    
    if not system_prompt or not system_prompt.strip():
        system_prompt = "You are a helpful AI assistant for a hospital appointment booking system."
    
    client = get_bedrock_client()
    
    # Build conversation with system prompt and history
    messages = []
    
    if conversation_history:
        for msg in conversation_history[-5:]:  # Last 5 messages for context
            user_content = msg.get('user', '').strip()
            ai_content = msg.get('ai', '').strip()
            
            # Only add messages with non-empty content
            if user_content:
                messages.append({
                    "role": "user",
                    "content": user_content
                })
            if ai_content:
                messages.append({
                    "role": "assistant", 
                    "content": ai_content
                })
    
    # Add current user message (already validated above)
    messages.append({
        "role": "user",
        "content": user_message.strip()
    })
    
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "system": system_prompt.strip(),
        "messages": messages,
        "temperature": 0.7
    }
    
    try:
        response = client.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            body=json.dumps(body)
        )
        
        response_body = json.loads(response['body'].read())
        
        # Extract and validate response
        if 'content' in response_body and len(response_body['content']) > 0:
            ai_response = response_body['content'][0].get('text', '')
            if ai_response and ai_response.strip():
                return ai_response.strip()
        
        # Fallback if response is empty
        return "I apologize, but I couldn't generate a proper response. Please try rephrasing your question."
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        print(f"Bedrock error ({error_code}): {error_message}")
        
        if error_code == 'ValidationException':
            return "I'm having trouble processing your request. Please try asking your question in a different way."
        elif error_code == 'AccessDeniedException':
            return "I'm currently unable to access my AI service. Please contact support if this continues."
        else:
            return "I apologize, but I'm having trouble connecting to my AI service. Please try again later."
            
    except Exception as e:
        print(f"Unexpected error: {e}")
        return "An unexpected error occurred. Please try again."

def analyze_appointment_intent(message):
    """Analyze user intent for appointment booking with validation"""
    
    if not message or not message.strip():
        return json.dumps({
            "intent": "unclear",
            "error": "Empty message provided",
            "confidence": 0.0
        })
    
    system_prompt = """
    Analyze the user's message and extract appointment booking intent and information.
    
    Return a JSON object with:
    {
        "intent": "book_appointment|reschedule|cancel|inquiry",
        "patient_info": {
            "name": "extracted name if present",
            "phone": "extracted phone if present", 
            "email": "extracted email if present"
        },
        "appointment_details": {
            "specialty": "medical specialty mentioned",
            "reason": "reason for visit",
            "preferred_date": "date mentioned",
            "preferred_time": "time mentioned",
            "doctor_preference": "specific doctor mentioned"
        },
        "confidence": 0.8
    }
    """
    
    try:
        response = get_ai_response(system_prompt, message)
        return response
    except Exception as e:
        print(f"Error analyzing intent: {e}")
        return json.dumps({
            "intent": "error",
            "error": str(e),
            "confidence": 0.0
        })