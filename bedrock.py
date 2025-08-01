import boto3
import json
import os
from botocore.exceptions import ClientError

def get_bedrock_client():
    """Initialize Bedrock client with enhanced configuration"""
    return boto3.client(
        'bedrock-runtime',
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )

def get_ai_response(system_prompt, user_message, conversation_history=None, db_context=None):
    """Get response from Claude with enhanced context, larger token window, and strict validation"""
    
    # Validate inputs
    if not user_message or not user_message.strip():
        return "I didn't receive a message. Could you please ask me something?"
    
    if not system_prompt or not system_prompt.strip():
        system_prompt = "You are a helpful AI assistant for a hospital appointment booking system."
    
    client = get_bedrock_client()
    
    # Build conversation with system prompt and extended history
    messages = []
    
    if conversation_history:
        # Include more conversation history for better context (up to 15 messages)
        for msg in conversation_history[-15:]:
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
    
    # Enhanced anti-hallucination system prompt with database context
    db_context_str = ""
    if db_context:
        db_context_str = f"""

CURRENT DATABASE CONTEXT:
- Active Doctors: {len(db_context.get('doctors', []))}
- Available Specializations: {len(db_context.get('specializations', []))}
- Recent Appointments: {len(db_context.get('recent_appointments', []))}

REAL DOCTOR DATA:
{format_doctor_context(db_context.get('doctors', []))}

AVAILABLE SPECIALIZATIONS:
{', '.join([s.get('name', '') for s in db_context.get('specializations', [])])}
"""

    enhanced_system_prompt = system_prompt + f"""

🚨 CRITICAL ANTI-HALLUCINATION RULES - MUST FOLLOW:

1. **ZERO FAKE DATA GENERATION**: 
   - NEVER create fictional doctor names, appointment times, or availability
   - NEVER generate fake appointment IDs or confirmation numbers
   - NEVER make up patient information or medical records
   - NEVER invent consultation fees or medical procedures

2. **DATABASE-FIRST APPROACH**:
   - ALL appointment data MUST come from actual database queries
   - Use ONLY the provided database tools: query_doctor_availability, query_patient_appointments, book_appointment
   - If you don't have database access for a query, clearly state: "Let me check our system for that information"
   - Wait for actual database results before providing any specific information

3. **HONEST CAPABILITY DISCLOSURE**:
   - If information isn't available in your context, say: "I need to check our database for current information"
   - Never pretend to have access to information you don't have
   - Be transparent about what you can and cannot do

4. **INTELLIGENT CONVERSATION FLOW**:
   - Guide users to provide information needed for database queries
   - For booking: Name → DOB → Specialty/Doctor → Date/Time preferences
   - For queries: Name → DOB → What information they need
   - Remember information provided earlier in the conversation

5. **DATABASE TOOL USAGE REQUIREMENTS**:
   - When asked about doctor availability: MUST use query_doctor_availability()
   - When asked about appointments: MUST use query_patient_appointments() 
   - When booking appointments: MUST use book_appointment()
   - Never provide specific doctor schedules without checking the database

6. **RESPONSE VALIDATION**:
   - Before mentioning any specific doctor, verify they exist in the database
   - Before stating availability, confirm with actual schedule data
   - Before confirming appointments, ensure successful database booking
   - All medical information must be generic/educational only

{db_context_str}

REMEMBER: Your role is to facilitate intelligent conversation and coordinate database operations. You are NOT a source of medical appointment data - that comes from the database only.
"""
    
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4000,  # Increased for more comprehensive responses
        "system": enhanced_system_prompt.strip(),
        "messages": messages,
        "temperature": 0.3,  # Lower temperature for more consistent, factual responses
        "top_p": 0.9,
        "top_k": 250
    }
    
    try:
        # Use Claude 3.5 Sonnet for better reasoning and larger context window
        response = client.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',  # Latest Claude 3.5 Sonnet with 200K context
            body=json.dumps(body)
        )
        
        response_body = json.loads(response['body'].read())
        
        # Extract and validate response
        if 'content' in response_body and len(response_body['content']) > 0:
            ai_response = response_body['content'][0].get('text', '')
            
            # Validate response for potential hallucinations
            if ai_response and ai_response.strip():
                validated_response = validate_response_for_hallucinations(ai_response, user_message)
                return validated_response
        
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

def format_doctor_context(doctors):
    """Format doctor data for context"""
    if not doctors:
        return "No doctors currently available"
    
    context = ""
    for doctor in doctors[:10]:  # Limit to avoid context overflow
        context += f"- Dr. {doctor.get('first_name', '')} {doctor.get('last_name', '')} "
        context += f"({doctor.get('specialization', 'General')}, "
        context += f"{doctor.get('experience_years', 0)} years, "
        context += f"${doctor.get('consultation_fee', 0)})\n"
    
    if len(doctors) > 10:
        context += f"... and {len(doctors) - 10} more doctors\n"
    
    return context

def validate_response_for_hallucinations(response, user_message):
    """Validate AI response for potential hallucinations"""
    
    # Check for specific patterns that might indicate hallucination
    hallucination_patterns = [
        r'Dr\.\s+[A-Z][a-z]+\s+[A-Z][a-z]+.*(?:available|appointment|schedule)',  # Specific doctor mentions
        r'appointment.*#[A-Z0-9]+',  # Fake appointment IDs
        r'(?:tomorrow|monday|tuesday|wednesday|thursday|friday).*(?:\d{1,2}:\d{2}|am|pm)',  # Specific times without database check
        r'\$\d+.*consultation',  # Specific fees without database verification
    ]
    
    # Check if response contains concerning patterns
    for pattern in hallucination_patterns:
        import re
        if re.search(pattern, response, re.IGNORECASE):
            # If suspicious pattern found, add disclaimer
            if "let me check" not in response.lower() and "database" not in response.lower():
                return response + "\n\n*Please note: I need to verify this information with our current database.*"
    
    return response

def analyze_appointment_intent(message, enhanced_context=None):
    """Analyze user intent for appointment booking with enhanced validation and context"""
    
    if not message or not message.strip():
        return json.dumps({
            "intent": "unclear",
            "error": "Empty message provided",
            "confidence": 0.0
        })
    
    system_prompt = f"""
    You are an expert intent analyzer for a hospital appointment system. Analyze the user's message and extract appointment-related intent and information with high accuracy.
    
    {enhanced_context or ""}
    
    CRITICAL RULES:
    1. NEVER make up doctor names, appointment times, or availability information
    2. Extract only information explicitly mentioned by the user
    3. For ambiguous requests, flag them for clarification
    4. Be conservative in your confidence scores
    
    Return a JSON object with:
    {{
        "intent": "book_appointment|reschedule|cancel|inquiry|availability_check|greeting|unclear",
        "extracted_info": {{
            "patient_name": "full name if clearly provided",
            "date_of_birth": "DOB if provided in format MM/DD/YYYY or DD/MM/YYYY",
            "phone": "phone number if provided", 
            "email": "email if provided"
        }},
        "appointment_preferences": {{
            "specialty": "medical specialty if mentioned",
            "doctor_name": "specific doctor name if mentioned",
            "preferred_date": "date preference if mentioned",
            "preferred_time": "time preference if mentioned",
            "urgency": "urgent|routine|flexible"
        }},
        "context_clues": {{
            "keywords_found": ["list", "of", "relevant", "keywords"],
            "medical_terms": ["any", "medical", "conditions", "mentioned"],
            "time_indicators": ["temporal", "expressions", "found"]
        }},
        "confidence": 0.0-1.0,
        "requires_clarification": ["list", "of", "items", "needing", "clarification"],
        "suggested_next_question": "What question should we ask next to proceed?"
    }}
    
    Focus on accurate extraction over completeness. If you're unsure about any information, mark it for clarification.
    """
    
    try:
        response = get_ai_response(system_prompt, message)
        
        # Attempt to parse as JSON, fallback gracefully
        try:
            parsed_response = json.loads(response)
            return json.dumps(parsed_response, indent=2)
        except json.JSONDecodeError:
            # If response isn't valid JSON, create a basic structure
            return json.dumps({
                "intent": "unclear",
                "error": "Could not parse intent properly",
                "raw_response": response,
                "confidence": 0.3
            })
            
    except Exception as e:
        print(f"Error analyzing intent: {e}")
        return json.dumps({
            "intent": "error",
            "error": str(e),
            "confidence": 0.0
        })

def get_enhanced_claude_response(prompt, context_data=None, conversation_history=None):
    """
    Get enhanced Claude response with comprehensive context and strict validation
    """
    
    # Build comprehensive context
    enhanced_prompt = prompt
    
    if context_data:
        enhanced_prompt += f"\n\nCURRENT SYSTEM CONTEXT:\n{format_context_data(context_data)}"
    
    return get_ai_response(
        enhanced_prompt,
        "",  # User message embedded in prompt
        conversation_history,
        context_data
    )

def format_context_data(context_data):
    """Format context data for Claude"""
    if not context_data:
        return "No additional context available"
    
    formatted = ""
    
    if 'doctors' in context_data:
        formatted += f"Available Doctors: {len(context_data['doctors'])}\n"
    
    if 'specializations' in context_data:
        specialties = [s.get('name', '') for s in context_data['specializations']]
        formatted += f"Medical Specialties: {', '.join(specialties[:5])}\n"
    
    if 'recent_appointments' in context_data:
        formatted += f"Recent Appointments: {len(context_data['recent_appointments'])}\n"
    
    return formatted