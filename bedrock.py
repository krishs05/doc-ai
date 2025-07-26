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
    """Get response from Claude with enhanced context"""
    
    client = get_bedrock_client()
    
    # Build conversation with system prompt and history
    messages = []
    
    if conversation_history:
        for msg in conversation_history[-5:]:  # Last 5 messages for context
            messages.append({
                "role": "user",
                "content": msg.get('user', '')
            })
            messages.append({
                "role": "assistant", 
                "content": msg.get('ai', '')
            })
    
    messages.append({
        "role": "user",
        "content": user_message
    })
    
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "system": system_prompt,
        "messages": messages,
        "temperature": 0.7
    }
    
    try:
        response = client.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            body=json.dumps(body)
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
        
    except ClientError as e:
        print(f"Bedrock error: {e}")
        return "I apologize, but I'm having trouble connecting to my AI service. Please try again later."
    except Exception as e:
        print(f"Unexpected error: {e}")
        return "An unexpected error occurred. Please try again."

def analyze_appointment_intent(message):
    """Analyze user intent for appointment booking"""
    
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
    
    return get_ai_response(system_prompt, message)