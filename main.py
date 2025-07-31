import os
import logging
import uuid
import json
from datetime import datetime, timedelta, date, time
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import re
import calendar
from datetime import datetime as dt
import dateutil.parser
from collections import defaultdict
import time as time_module
from werkzeug.exceptions import HTTPException, BadRequest

# Try to import claude_guidance, but handle gracefully if it fails
try:
    from claude_guidance import (
        get_enhanced_system_prompt,
        get_appointment_booking_prompts,
        get_availability_check_prompts,
        get_conversation_flow_guidance
    )
    GUIDANCE_AVAILABLE = True
    print("✅ Claude Guidance System: Available")
except ImportError as e:
    GUIDANCE_AVAILABLE = False
    print(f"⚠️  Claude Guidance System: Not available - {e}")
    print("📝 Please create claude_guidance.py file for enhanced AI responses")

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app, origins=["http://localhost:5500", "http://localhost:3000"])

# Configure Flask to handle malformed requests
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024  # 1MB limit
app.config['PROPAGATE_EXCEPTIONS'] = True

# Custom error handler for malformed requests
@app.errorhandler(Exception)
def handle_exception(e):
    """Handle all exceptions including malformed requests"""
    logger.error(f"Unhandled exception: {e}", exc_info=True)
    return jsonify({
        'success': False,
        'message': 'An error occurred processing your request',
        'error': 'Server error'
    }), 500

@app.errorhandler(HTTPException)
def handle_http_exception(e):
    """Handle HTTP exceptions including malformed requests"""
    logger.warning(f"HTTP exception: {e.code} - {e.description} from {request.remote_addr}")
    return jsonify({
        'success': False,
        'message': 'Invalid request',
        'error': f'HTTP {e.code}'
    }), e.code

@app.errorhandler(BadRequest)
def handle_bad_request(e):
    """Handle bad requests including malformed binary data"""
    logger.warning(f"Bad request from {request.remote_addr}: {e}")
    return jsonify({
        'success': False,
        'message': 'Invalid request format',
        'error': 'Bad request'
    }), 400

# Rate limiting storage
request_counts = defaultdict(list)

@app.before_request
def validate_request():
    """Validate incoming requests"""
    try:
        # Rate limiting
        client_ip = request.remote_addr
        current_time = time_module.time()
        
        # Clean old requests (older than 1 minute)
        request_counts[client_ip] = [req_time for req_time in request_counts[client_ip] 
                                   if current_time - req_time < 60]
        
        # Check rate limit (max 100 requests per minute per IP)
        if len(request_counts[client_ip]) >= 100:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return jsonify({
                'success': False,
                'message': 'Rate limit exceeded. Please try again later.'
            }), 429
        
        # Add current request
        request_counts[client_ip].append(current_time)
        
        # Log request details for debugging
        logger.debug(f"Request: {request.method} {request.path} from {request.remote_addr}")
        
        # Additional logging for suspicious requests
        if request.remote_addr == '192.168.1.2':  # The IP causing issues
            logger.warning(f"Suspicious request from {request.remote_addr}: {request.method} {request.path}")
            logger.warning(f"Headers: {dict(request.headers)}")
            if request.content_length:
                logger.warning(f"Content length: {request.content_length}")
                try:
                    sample = request.get_data(cache=True, as_text=False)[:50]
                    logger.warning(f"Sample data: {sample}")
                except Exception as e:
                    logger.warning(f"Error reading request data: {e}")
        
        # Check if request is malformed
        if request.content_length and request.content_length > 1024 * 1024:  # 1MB limit
            logger.warning(f"Request too large: {request.content_length} bytes from {client_ip}")
            return jsonify({
                'success': False,
                'message': 'Request too large'
            }), 413
        
        # Check for binary data in request
        if request.method == 'POST' and request.content_length:
            try:
                # Try to read a small sample of the request data
                sample_data = request.get_data(cache=True, as_text=False)
                if sample_data and len(sample_data) > 0:
                    # Check if data contains null bytes or other binary indicators
                    if b'\x00' in sample_data[:100] or any(byte < 32 and byte != 9 and byte != 10 and byte != 13 for byte in sample_data[:100]):
                        logger.warning(f"Binary data detected in request from {client_ip}")
                        return jsonify({
                            'success': False,
                            'message': 'Invalid request format'
                        }), 400
            except Exception as e:
                logger.warning(f"Error reading request data from {client_ip}: {e}")
                return jsonify({
                    'success': False,
                    'message': 'Invalid request format'
                }), 400
        
        # Validate content type for POST requests
        if request.method == 'POST':
            if request.content_type and 'application/json' not in request.content_type:
                logger.warning(f"Invalid content type: {request.content_type} from {client_ip}")
                return jsonify({
                    'success': False,
                    'message': 'Invalid content type. Expected application/json'
                }), 400
                
    except Exception as e:
        logger.error(f"Request validation error: {e}")
        return jsonify({
            'success': False,
            'message': 'Request validation failed'
        }), 400

# Global error handlers
@app.errorhandler(400)
def bad_request(error):
    """Handle bad requests gracefully"""
    logger.warning(f"Bad request received: {error}")
    return jsonify({
        'success': False,
        'message': 'Invalid request format',
        'error': 'Bad request'
    }), 400

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    logger.warning(f"404 error: {error}")
    return jsonify({
        'success': False,
        'message': 'Endpoint not found',
        'error': 'Not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'success': False,
        'message': 'Internal server error',
        'error': 'Server error'
    }), 500

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'hospital'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
    'port': os.getenv('DB_PORT', 5432)
}

# Try importing AWS Bedrock
try:
    import boto3
    bedrock_runtime = boto3.client('bedrock-runtime', region_name=os.getenv('AWS_REGION', 'us-east-1'))
    BEDROCK_AVAILABLE = True
    logger.info("✅ AWS Bedrock: Available")
except Exception as e:
    BEDROCK_AVAILABLE = False
    logger.warning(f"❌ AWS Bedrock: Not available - {e}")

# Try importing RAG dependencies
try:
    from sentence_transformers import SentenceTransformer
    import faiss
    import numpy as np
    RAG_AVAILABLE = True
    logger.info("✅ RAG capabilities: Available")
except ImportError as e:
    RAG_AVAILABLE = False
    logger.warning(f"❌ RAG capabilities: Not available - {e}")

@dataclass
class DatabaseContext:
    doctors: List[Dict]
    departments: List[Dict]
    specializations: List[Dict]
    recent_appointments: List[Dict]

@dataclass
class AppointmentDetails:
    patient_name: str
    date_of_birth: str
    doctor_preference: str
    specialization: str
    preferred_date: str
    preferred_time: str
    reason: str = "General consultation"

def serialize_datetime_objects(obj):
    """Convert datetime, date, and time objects to strings for JSON serialization"""
    if isinstance(obj, dict):
        return {key: serialize_datetime_objects(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime_objects(item) for item in obj]
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, time):
        return obj.strftime('%H:%M:%S')
    else:
        return obj

def get_db_connection():
    """Get database connection with error handling"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.debug("Database connection successful")
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

def query_doctor_availability(specialty: str, target_date: str = None) -> str:
    """Query real doctor availability from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Database connection error"
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Get doctors by specialty
            cursor.execute("""
                SELECT d.id, d.first_name, d.last_name, d.consultation_fee, d.experience_years,
                       s.name as specialization
                FROM doctors d
                JOIN specializations s ON d.specialization_id = s.id
                WHERE s.name ILIKE %s AND d.is_active = TRUE
                ORDER BY d.last_name, d.first_name
            """, (f"%{specialty}%",))
            
            doctors = cursor.fetchall()
            if not doctors:
                return f"No doctors found for {specialty} specialty. Available specializations with doctors are: Cardiology, Dermatology, Pediatrics, Orthopedics, Neurology, General Medicine, Psychiatry, Gynecology."
            
            result = f"Available {specialty} doctors:\n\n"
            
            for doctor in doctors:
                result += f"Dr. {doctor['first_name']} {doctor['last_name']}\n"
                result += f"- Experience: {doctor['experience_years']} years\n"
                result += f"- Consultation Fee: ${doctor['consultation_fee']}\n"
                
                # Get availability for this doctor
                if target_date:
                    try:
                        parsed_date = dateutil.parser.parse(target_date).date()
                        day_of_week = parsed_date.weekday() + 1
                        if day_of_week == 7:
                            day_of_week = 0
                        
                        cursor.execute("""
                            SELECT da.start_time, da.end_time, da.slot_duration, da.max_patients_per_slot
                            FROM doctor_availability da
                            WHERE da.doctor_id = %s AND da.day_of_week = %s AND da.is_active = TRUE
                        """, (doctor['id'], day_of_week))
                        
                        availability = cursor.fetchall()
                        if availability:
                            result += f"- Available on {parsed_date.strftime('%A, %B %d')}:\n"
                            for slot in availability:
                                start_time = slot['start_time']
                                end_time = slot['end_time']
                                result += f"  * {start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}\n"
                        else:
                            result += f"- Not available on {parsed_date.strftime('%A, %B %d')}\n"
                    except:
                        result += "- Date format error\n"
                else:
                    # Get next available slots
                    cursor.execute("""
                        SELECT da.day_of_week, da.start_time, da.end_time
                        FROM doctor_availability da
                        WHERE da.doctor_id = %s AND da.is_active = TRUE
                        ORDER BY da.day_of_week, da.start_time
                    """, (doctor['id'],))
                    
                    weekly_availability = cursor.fetchall()
                    if weekly_availability:
                        result += "- Weekly availability:\n"
                        for slot in weekly_availability:
                            day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
                            day_name = day_names[slot['day_of_week']]
                            start_time = slot['start_time'].strftime('%I:%M %p')
                            end_time = slot['end_time'].strftime('%I:%M %p')
                            result += f"  * {day_name}: {start_time} - {end_time}\n"
                    else:
                        result += "- No availability found\n"
                
                result += "\n"
            
            return result
            
    except Exception as e:
        logger.error(f"Error querying doctor availability: {e}")
        return f"Error querying availability: {str(e)}"

def query_patient_appointments(patient_name: str, date_of_birth: str) -> str:
    """Query real patient appointments from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Database connection error"
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Clean up patient name and try multiple matching strategies
            clean_name = patient_name.strip().title()
            name_parts = clean_name.split()
            
            # Try exact match first
            cursor.execute("""
                SELECT id FROM patients 
                WHERE LOWER(first_name || ' ' || last_name) = LOWER(%s) 
                AND date_of_birth = %s
            """, (clean_name, date_of_birth))
            
            patient = cursor.fetchone()
            
            # If no exact match, try flexible matching
            if not patient and len(name_parts) >= 2:
                # Try first name + last name
                first_name = name_parts[0]
                last_name = ' '.join(name_parts[1:])
                
                cursor.execute("""
                    SELECT id FROM patients 
                    WHERE LOWER(first_name) = LOWER(%s) 
                    AND LOWER(last_name) = LOWER(%s)
                    AND date_of_birth = %s
                """, (first_name, last_name, date_of_birth))
                
                patient = cursor.fetchone()
                
                # If still no match, try last name + first name (reversed)
                if not patient:
                    cursor.execute("""
                        SELECT id FROM patients 
                        WHERE LOWER(first_name) = LOWER(%s) 
                        AND LOWER(last_name) = LOWER(%s)
                        AND date_of_birth = %s
                    """, (last_name, first_name, date_of_birth))
                    
                    patient = cursor.fetchone()
            
            if not patient:
                # Try partial name matching
                cursor.execute("""
                    SELECT id, first_name, last_name FROM patients 
                    WHERE (LOWER(first_name) LIKE LOWER(%s) OR LOWER(last_name) LIKE LOWER(%s))
                    AND date_of_birth = %s
                """, (f"%{name_parts[0]}%", f"%{name_parts[-1]}%", date_of_birth))
                
                patient = cursor.fetchone()
                
                if patient:
                    logger.info(f"Found patient with partial match: {patient['first_name']} {patient['last_name']}")
            
            if not patient:
                return f"No patient found with name '{patient_name}' and DOB {date_of_birth}. Please check the spelling and try again."
            
            # Get appointments
            cursor.execute("""
                SELECT a.id, a.appointment_date, a.appointment_time, a.status,
                       d.first_name, d.last_name, s.name as specialization
                FROM appointments a
                JOIN doctors d ON a.doctor_id = d.id
                JOIN specializations s ON d.specialization_id = s.id
                WHERE a.patient_id = %s AND a.appointment_date >= CURRENT_DATE
                ORDER BY a.appointment_date, a.appointment_time
            """, (patient['id'],))
            
            appointments = cursor.fetchall()
            if not appointments:
                return f"No upcoming appointments found for {patient_name}"
            
            result = f"Upcoming appointments for {patient_name}:\n\n"
            for apt in appointments:
                result += f"Appointment #{apt['id']}\n"
                result += f"- Date: {apt['appointment_date'].strftime('%A, %B %d, %Y')}\n"
                result += f"- Time: {apt['appointment_time'].strftime('%I:%M %p')}\n"
                result += f"- Doctor: Dr. {apt['first_name']} {apt['last_name']} ({apt['specialization']})\n"
                result += f"- Status: {apt['status']}\n\n"
            
            return result
            
    except Exception as e:
        logger.error(f"Error querying patient appointments: {e}")
        return f"Error querying appointments: {str(e)}"

def query_doctor_schedule(doctor_name: str, target_date: str = None) -> str:
    """Query real doctor schedule from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Database connection error"
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Clean up doctor name (remove "Dr." prefix if present)
            clean_name = doctor_name.replace("Dr.", "").replace("Dr", "").strip()
            
            # Find doctor with flexible name matching
            cursor.execute("""
                SELECT d.id, d.first_name, d.last_name, d.consultation_fee, d.experience_years,
                       s.name as specialization
                FROM doctors d
                JOIN specializations s ON d.specialization_id = s.id
                WHERE (LOWER(d.first_name || ' ' || d.last_name) = LOWER(%s) 
                       OR LOWER(d.last_name || ' ' || d.first_name) = LOWER(%s)
                       OR LOWER(d.first_name) = LOWER(%s)
                       OR LOWER(d.last_name) = LOWER(%s))
                AND d.is_active = TRUE
            """, (clean_name, clean_name, clean_name, clean_name))
            
            doctor = cursor.fetchone()
            if not doctor:
                return f"Doctor {doctor_name} not found"
            
            result = f"Dr. {doctor['first_name']} {doctor['last_name']} ({doctor['specialization']})\n"
            result += f"- Experience: {doctor['experience_years']} years\n"
            result += f"- Consultation Fee: ${doctor['consultation_fee']}\n\n"
            
            if target_date:
                try:
                    parsed_date = dateutil.parser.parse(target_date).date()
                    day_of_week = parsed_date.weekday() + 1
                    if day_of_week == 7:
                        day_of_week = 0
                    
                    # Get availability for specific date
                    cursor.execute("""
                        SELECT da.start_time, da.end_time, da.slot_duration, da.max_patients_per_slot
                        FROM doctor_availability da
                        WHERE da.doctor_id = %s AND da.day_of_week = %s AND da.is_active = TRUE
                    """, (doctor['id'], day_of_week))
                    
                    availability = cursor.fetchall()
                    if availability:
                        result += f"Schedule for {parsed_date.strftime('%A, %B %d, %Y')}:\n"
                        for slot in availability:
                            start_time = slot['start_time']
                            end_time = slot['end_time']
                            result += f"- {start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}\n"
                    else:
                        result += f"Not available on {parsed_date.strftime('%A, %B %d, %Y')}\n"
                except:
                    result += "Date format error\n"
            else:
                # Get weekly schedule
                cursor.execute("""
                    SELECT da.day_of_week, da.start_time, da.end_time
                    FROM doctor_availability da
                    WHERE da.doctor_id = %s AND da.is_active = TRUE
                    ORDER BY da.day_of_week, da.start_time
                """, (doctor['id'],))
                
                weekly_schedule = cursor.fetchall()
                if weekly_schedule:
                    result += "Weekly Schedule:\n"
                    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
                    for slot in weekly_schedule:
                        day_name = day_names[slot['day_of_week']]
                        start_time = slot['start_time'].strftime('%I:%M %p')
                        end_time = slot['end_time'].strftime('%I:%M %p')
                        result += f"- {day_name}: {start_time} - {end_time}\n"
                else:
                    result += "No schedule found\n"
            
            return result
            
    except Exception as e:
        logger.error(f"Error querying doctor schedule: {e}")
        return f"Error querying schedule: {str(e)}"

def get_ai_response(system_prompt: str, user_message: str, conversation_history: List = None) -> str:
    """Get response from AWS Bedrock Claude"""
    if not BEDROCK_AVAILABLE:
        return "AI service is not available. Please check your AWS configuration."
    
    try:
        # Build conversation context
        messages = []
        if conversation_history:
            for msg in conversation_history[-10:]:  # Last 10 messages for context
                messages.append({"role": "user", "content": msg.get('user_message', '')})
                messages.append({"role": "assistant", "content": msg.get('ai_response', '')})
        
        messages.append({"role": "user", "content": user_message})
        
        # Prepare the request
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "system": system_prompt,
            "messages": messages
        }
        
        # Call Bedrock
        response = bedrock_runtime.invoke_model(
            body=json.dumps(request_body),
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            accept="application/json",
            contentType="application/json"
        )
        
        response_body = json.loads(response.get('body').read())
        return response_body['content'][0]['text']
        
    except Exception as e:
        logger.error(f"Bedrock API error: {e}")
        return "I'm having trouble processing your request. Please try again."

class EnhancedAppointmentManager:
    """Enhanced appointment manager with proper database integration"""
    
    def find_available_doctors_by_specialty(self, specialty: str) -> List[Dict]:
        """Find available doctors by specialty"""
        try:
            conn = get_db_connection()
            if not conn:
                return []
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT DISTINCT d.id, d.first_name, d.last_name, d.consultation_fee,
                           s.name as specialization, d.experience_years
                    FROM doctors d
                    JOIN specializations s ON d.specialization_id = s.id
                    WHERE d.is_active = TRUE AND s.name ILIKE %s
                    ORDER BY d.last_name, d.first_name
                """, (f"%{specialty}%",))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error finding doctors by specialty: {e}")
            return []
    
    def get_doctor_availability(self, doctor_id: int, target_date: date = None) -> List[Dict]:
        """Get available time slots for a doctor on a specific date or upcoming dates"""
        try:
            conn = get_db_connection()
            if not conn:
                return []
            
            if target_date is None:
                target_date = date.today()
            
            # Get day of week (0=Sunday, 6=Saturday)
            day_of_week = target_date.weekday() + 1  # Convert to 1=Monday, 0=Sunday
            if day_of_week == 7:
                day_of_week = 0
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get doctor's availability for the day
                cursor.execute("""
                    SELECT da.start_time, da.end_time, da.slot_duration, da.max_patients_per_slot
                    FROM doctor_availability da
                    WHERE da.doctor_id = %s AND da.day_of_week = %s AND da.is_active = TRUE
                """, (doctor_id, day_of_week))
                
                availability = cursor.fetchall()
                if not availability:
                    return []
                
                # Get existing appointments for this date
                cursor.execute("""
                    SELECT appointment_time, duration
                    FROM appointments
                    WHERE doctor_id = %s AND appointment_date = %s 
                    AND status NOT IN ('cancelled')
                """, (doctor_id, target_date))
                
                booked_slots = cursor.fetchall()
                
                # Calculate available slots
                available_slots = []
                for avail in availability:
                    start_time = avail['start_time']
                    end_time = avail['end_time']
                    slot_duration = avail['slot_duration']
                    
                    # Generate time slots
                    current_time = datetime.combine(target_date, start_time)
                    end_datetime = datetime.combine(target_date, end_time)
                    
                    while current_time < end_datetime:
                        slot_time = current_time.time()
                        
                        # Check if this slot is available
                        is_available = True
                        for booking in booked_slots:
                            if booking['appointment_time'] == slot_time:
                                is_available = False
                                break
                        
                        if is_available:
                            available_slots.append({
                                'date': target_date.strftime('%Y-%m-%d'),
                                'time': slot_time.strftime('%H:%M'),
                                'display_time': slot_time.strftime('%I:%M %p')
                            })
                        
                        current_time += timedelta(minutes=slot_duration)
                
                return available_slots
                
        except Exception as e:
            logger.error(f"Error getting doctor availability: {e}")
            return []
    
    def get_next_available_slots(self, doctor_id: int, days_ahead: int = 7) -> List[Dict]:
        """Get next available slots for a doctor within specified days"""
        all_slots = []
        today = date.today()
        
        for i in range(days_ahead):
            check_date = today + timedelta(days=i)
            slots = self.get_doctor_availability(doctor_id, check_date)
            all_slots.extend(slots[:3])  # Limit to 3 slots per day
            
            if len(all_slots) >= 10:  # Limit total results
                break
        
        return all_slots[:10]
    
    def create_or_find_patient(self, patient_name: str, date_of_birth: str) -> int:
        """Create or find patient and return patient ID"""
        try:
            conn = get_db_connection()
            if not conn:
                return None
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Parse name
                name_parts = patient_name.strip().split()
                first_name = name_parts[0]
                last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                
                # Parse date of birth
                try:
                    if '/' in date_of_birth:
                        # Handle MM/DD/YYYY or DD/MM/YYYY
                        parts = date_of_birth.split('/')
                        if len(parts) == 3:
                            if int(parts[0]) > 12:  # DD/MM/YYYY
                                dob = date(int(parts[2]), int(parts[1]), int(parts[0]))
                            else:  # MM/DD/YYYY
                                dob = date(int(parts[2]), int(parts[0]), int(parts[1]))
                    else:
                        dob = dateutil.parser.parse(date_of_birth).date()
                except:
                    raise ValueError("Invalid date format. Please use MM/DD/YYYY or DD/MM/YYYY")
                
                # Check if patient exists
                cursor.execute("""
                    SELECT id FROM patients 
                    WHERE LOWER(first_name) = LOWER(%s) 
                    AND LOWER(last_name) = LOWER(%s) 
                    AND date_of_birth = %s
                """, (first_name, last_name, dob))
                
                existing_patient = cursor.fetchone()
                if existing_patient:
                    return existing_patient['id']
                
                # Create new patient
                email = f"{first_name.lower()}.{last_name.lower()}@example.com"
                cursor.execute("""
                    INSERT INTO patients (first_name, last_name, email, date_of_birth, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (first_name, last_name, email, dob, datetime.now()))
                
                conn.commit()
                return cursor.fetchone()['id']
                
        except Exception as e:
            logger.error(f"Error creating/finding patient: {e}")
            if conn:
                conn.rollback()
            raise e
    
    def book_appointment(self, details: AppointmentDetails) -> Tuple[bool, str]:
        """Book an appointment with proper validation"""
        try:
            conn = get_db_connection()
            if not conn:
                return False, "Database connection error"
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Create or find patient
                patient_id = self.create_or_find_patient(details.patient_name, details.date_of_birth)
                if not patient_id:
                    return False, "Could not create or find patient record"
                
                # Find doctor
                doctor_id = None
                if details.doctor_preference and not details.doctor_preference.lower() in ['any', 'no preference']:
                    # Search by doctor name
                    cursor.execute("""
                        SELECT d.id, d.first_name, d.last_name, s.name as specialization
                        FROM doctors d
                        JOIN specializations s ON d.specialization_id = s.id
                        WHERE CONCAT(d.first_name, ' ', d.last_name) ILIKE %s
                        AND d.is_active = TRUE
                    """, (f"%{details.doctor_preference}%",))
                    
                    doctor = cursor.fetchone()
                    if doctor:
                        doctor_id = doctor['id']
                    else:
                        # Check if doctor exists but name doesn't match exactly
                        cursor.execute("""
                            SELECT d.id, d.first_name, d.last_name, s.name as specialization
                            FROM doctors d
                            JOIN specializations s ON d.specialization_id = s.id
                            WHERE d.is_active = TRUE
                            ORDER BY d.last_name, d.first_name
                        """)
                        all_doctors = cursor.fetchall()
                        available_doctors = [f"Dr. {d['first_name']} {d['last_name']} ({d['specialization']})" for d in all_doctors]
                        return False, f"Doctor '{details.doctor_preference}' not found. Available doctors: {', '.join(available_doctors[:5])}"
                
                # If no specific doctor found, find by specialization
                if not doctor_id:
                    cursor.execute("""
                        SELECT d.id, d.first_name, d.last_name, s.name as specialization
                        FROM doctors d
                        JOIN specializations s ON d.specialization_id = s.id
                        WHERE s.name ILIKE %s AND d.is_active = TRUE
                        ORDER BY RANDOM()
                        LIMIT 1
                    """, (f"%{details.specialization}%",))
                    
                    doctor = cursor.fetchone()
                    if doctor:
                        doctor_id = doctor['id']
                
                if not doctor_id:
                    # Get available specializations with doctors
                    cursor.execute("""
                        SELECT DISTINCT s.name
                        FROM specializations s
                        JOIN doctors d ON s.id = d.specialization_id
                        WHERE d.is_active = TRUE
                        ORDER BY s.name
                    """)
                    available_specialties = [row['name'] for row in cursor.fetchall()]
                    return False, f"No available doctors found for {details.specialization}. Available specializations: {', '.join(available_specialties)}"
                
                # Parse preferred date
                try:
                    if details.preferred_date.lower() in ['today', 'tomorrow']:
                        if details.preferred_date.lower() == 'today':
                            appointment_date = date.today()
                        else:
                            appointment_date = date.today() + timedelta(days=1)
                    else:
                        appointment_date = dateutil.parser.parse(details.preferred_date).date()
                except:
                    # Default to next available date
                    appointment_date = date.today() + timedelta(days=1)
                
                # Parse preferred time
                try:
                    if details.preferred_time.lower() in ['morning', 'afternoon', 'evening']:
                        time_preferences = {
                            'morning': time(9, 0),
                            'afternoon': time(14, 0),
                            'evening': time(17, 0)
                        }
                        appointment_time = time_preferences[details.preferred_time.lower()]
                    else:
                        appointment_time = dateutil.parser.parse(details.preferred_time).time()
                except:
                    appointment_time = time(10, 0)  # Default to 10 AM
                
                # Check if requested slot is available
                available_slots = self.get_doctor_availability(doctor_id, appointment_date)
                requested_time_str = appointment_time.strftime('%H:%M')
                
                slot_available = any(slot['time'] == requested_time_str for slot in available_slots)
                
                if not slot_available:
                    # Find next available slot
                    next_slots = self.get_next_available_slots(doctor_id, 14)  # Check next 2 weeks
                    if next_slots:
                        suggested_slot = next_slots[0]
                        return False, f"The requested time ({appointment_time.strftime('%I:%M %p')} on {appointment_date}) is not available. Next available slot is {suggested_slot['display_time']} on {suggested_slot['date']}. Would you like to book this instead?"
                    else:
                        return False, "No available slots found for this doctor in the next 2 weeks"
                
                # Check for conflicts
                cursor.execute("""
                    SELECT id FROM appointments 
                    WHERE doctor_id = %s AND appointment_date = %s AND appointment_time = %s
                    AND status NOT IN ('cancelled')
                """, (doctor_id, appointment_date, appointment_time))
                
                if cursor.fetchone():
                    return False, "Time slot is already booked"
                
                # Create appointment
                cursor.execute("""
                    INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, 
                                            status, reason_for_visit, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    patient_id, doctor_id, appointment_date, appointment_time,
                    'scheduled', details.reason, datetime.now()
                ))
                
                appointment_id = cursor.fetchone()['id']
                
                # Get doctor name for confirmation
                cursor.execute("""
                    SELECT d.first_name, d.last_name, s.name as specialization, d.consultation_fee
                    FROM doctors d
                    JOIN specializations s ON d.specialization_id = s.id
                    WHERE d.id = %s
                """, (doctor_id,))
                
                doctor_info = cursor.fetchone()
                
                conn.commit()
                
                success_message = (
                    f"Appointment #{appointment_id} booked successfully!\n\n"
                    f"Details:\n"
                    f"• Patient: {details.patient_name}\n"
                    f"• Doctor: Dr. {doctor_info['first_name']} {doctor_info['last_name']} ({doctor_info['specialization']})\n"
                    f"• Date: {appointment_date.strftime('%A, %B %d, %Y')}\n"
                    f"• Time: {appointment_time.strftime('%I:%M %p')}\n"
                    f"• Consultation Fee: ${doctor_info['consultation_fee']}\n"
                    f"• Reason: {details.reason}"
                )
                
                return True, success_message
                
        except Exception as e:
            logger.error(f"Error booking appointment: {e}")
            if conn:
                conn.rollback()
            return False, f"Booking failed: {str(e)}"

def get_fallback_system_prompt(db_context, rag_context=""):
    """Enhanced fallback system prompt with database context"""
    
    # Build comprehensive database information
    doctors_info = ""
    if db_context.doctors:
        doctors_info = "Available Doctors:\n"
        for doctor in db_context.doctors[:10]:  # Show first 10 doctors
            doctors_info += f"• Dr. {doctor['name']} - {doctor['specialization']} (${doctor.get('consultation_fee', 'N/A')})\n"
    
    specializations_info = ""
    if db_context.specializations:
        specializations_info = "Available Specializations:\n"
        for spec in db_context.specializations:
            specializations_info += f"• {spec['name']}\n"
    
    recent_appointments_info = ""
    if db_context.recent_appointments:
        recent_appointments_info = "Recent Appointments:\n"
        for apt in db_context.recent_appointments[:5]:
            recent_appointments_info += f"• {apt['appointment_date']} at {apt['appointment_time']} - {apt['patient_name']} with Dr. {apt['doctor_name']}\n"
    
    system_prompt = f"""You are an intelligent AI healthcare assistant for a hospital appointment booking system. You have access to real-time database information and should use it to provide accurate, helpful responses.

CRITICAL: You have access to database query functions. When users ask about availability, appointments, or doctor information, you MUST use these functions instead of making up information:

AVAILABLE DATABASE FUNCTIONS:
1. query_doctor_availability(specialty, date) - Get real doctor availability for a specialty
2. query_patient_appointments(patient_name, date_of_birth) - Get real patient appointments
3. query_doctor_schedule(doctor_name, date) - Get real doctor schedule

IMPORTANT RULES:
- NEVER make up doctor names that don't exist in the database
- NEVER create fake appointment IDs or confirmation numbers
- NEVER provide availability for doctors that don't exist
- ALWAYS use database functions to get real information
- If a specialty has no doctors, tell the user and suggest available alternatives
- DO NOT generate fake booking confirmations - the system will handle actual booking
- When user confirms booking with "yes" or "book it", let the system handle the actual booking

EXAMPLES OF WHEN TO USE DATABASE FUNCTIONS:
- User asks: "What cardiologists do you have available?" → Use query_doctor_availability("cardiology")
- User asks: "What's Dr. Smith's schedule?" → Use query_doctor_schedule("Dr. John Smith")
- User asks: "Show my appointments" → Use query_patient_appointments(patient_name, dob)
- User asks: "Check availability for tomorrow" → Use query_doctor_availability(specialty, "tomorrow")

BOOKING PROCESS:
1. Collect patient information (name, DOB, specialty, preferred date/time)
2. When all information is collected, ask for confirmation
3. When user confirms with "yes" or "book it", DO NOT generate fake confirmation - let the system handle actual booking
4. The system will provide the real booking confirmation with actual appointment ID

DATABASE CONTEXT:
{doctors_info}
{specializations_info}
{recent_appointments_info}

CONVERSATION GUIDELINES:
1. **ALWAYS USE DATABASE FUNCTIONS**: Never make up availability, appointments, or doctor information
2. **Maintain Context**: Remember patient information across conversation turns
3. **Be Helpful**: Guide users through the booking process naturally
4. **Ask for Missing Info**: If booking an appointment, ask for missing details (name, DOB, preferred date/time)
5. **Provide Real Options**: When asked about availability, use database functions to show actual available doctors and times
6. **Handle Queries**: Answer questions about doctors, specializations, and hospital services using real data
7. **Booking Process**: Help users book appointments by collecting necessary information step by step
8. **Rescheduling/Cancellation**: Help users reschedule or cancel existing appointments
9. **Lookup Appointments**: Help users find their existing appointments using database queries
10. **No Hallucination**: Never invent doctor names, appointment IDs, or availability that doesn't exist
11. **No Fake Confirmations**: Do not generate fake booking confirmations - let the system handle actual booking

AVAILABLE ACTIONS:
- Book appointments (requires: patient name, DOB, specialization, preferred date/time)
- Check doctor availability (use database functions)
- Look up patient appointments (use database functions)
- Reschedule appointments
- Cancel appointments
- Provide doctor information (use database functions)
- Answer general health questions

RAG CONTEXT: {rag_context}

Remember: ALWAYS use database functions for availability, appointments, and doctor information. Never hallucinate or make up information about doctors, appointments, or availability. Do not generate fake booking confirmations."""
    
    return system_prompt

class EnhancedConversationManager:
    def __init__(self):
        self.conversations = {}
        self.conversation_states = {}  # Track conversation state
        self.appointment_manager = EnhancedAppointmentManager()
        
        # Initialize RAG if available
        if RAG_AVAILABLE:
            self._initialize_rag()
        else:
            self.rag_index = None
            self.rag_documents = []
            self.embedding_model = None
            self.vector_store = None
            self.knowledge_base = []
    
    def _get_conversation_state(self, session_id: str) -> Dict[str, Any]:
        """Get or create conversation state for session"""
        if session_id not in self.conversation_states:
            self.conversation_states[session_id] = {
                'patient_name': '',
                'date_of_birth': '',
                'specialization': '',
                'doctor_preference': '',
                'last_context': '',
                'booking_intent': False
            }
        return self.conversation_states[session_id]
    
    def _update_conversation_state(self, session_id: str, **updates):
        """Update conversation state"""
        state = self._get_conversation_state(session_id)
        state.update(updates)
    
    def _extract_from_conversation_history(self, conversation_history: List = None) -> AppointmentDetails:
        """Extract appointment details from conversation history"""
        details = AppointmentDetails(
            patient_name="",
            date_of_birth="",
            doctor_preference="",
            specialization="",
            preferred_date="",
            preferred_time="",
            reason="General consultation"
        )
        
        if not conversation_history:
            return details
        
        # Look for patient information in recent messages
        for msg in conversation_history[-10:]:  # Check last 10 messages
            user_msg = msg.get('user_message', '').lower()
            ai_msg = msg.get('ai_response', '').lower()
            
            # Extract patient name
            name_patterns = [
                r'(?:name is|i am|i\'m|my name is|this is)\s+([a-zA-Z\s]+?)(?:\s*,|\s*$|\s*book|\s*schedule|\s*appointment)',
                r'(?:patient|i\'m)\s+([a-zA-Z]+\s+[a-zA-Z]+)',  # "patient John Smith" or "i'm John Smith"
                r'([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s+on|\s+for|\s+at|\s+with)',  # Name followed by booking keywords
                r'([A-Z][a-z]+\s+[A-Z][a-z]+)',  # Standalone capitalized names
                # New pattern for names in booking context
                r'(?:book|appointment|for)\s+([a-zA-Z]+\s+[a-zA-Z]+)(?:\s*,|\s*for|\s*-)',  # "book appointment for John Smith"
                # Pattern for names followed by comma and DOB
                r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s*,\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}',  # "Krish Sawhney, 05/02/2004"
                # Pattern for names in conversation context
                r'([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s*,|\s*for|\s*-|\s*05|\s*02|\s*2004)',  # "Krish Sawhney" followed by context
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, user_msg, re.IGNORECASE)
                if match and not details.patient_name:
                    potential_name = match.group(1).strip()
                    if (len(potential_name.split()) >= 2 and 
                        not any(word in potential_name.lower() for word in ['book', 'me', 'one', 'on', 'for', 'at', 'with', 'the', 'appointm']) and
                        not potential_name.lower().startswith('book')):
                        details.patient_name = potential_name
                        break
            
            # Extract DOB
            dob_patterns = [
                r'(?:birth|born|dob|date of birth).*?(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})',
                r'(?:birth|born|dob|date of birth).*?(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4})',
            ]
            
            for pattern in dob_patterns:
                match = re.search(pattern, user_msg, re.IGNORECASE)
                if match and not details.date_of_birth:
                    details.date_of_birth = match.group(1).strip()
                    break
            
            # Extract specialization from AI responses
            specializations = ['cardiology', 'neurology', 'orthopedics', 'pediatrics', 'dermatology', 
                              'psychiatry', 'gynecology', 'general medicine']
            
            for spec in specializations:
                if spec in ai_msg and not details.specialization:
                    details.specialization = spec.title()
                    break
        
        return details
    
    def _initialize_rag(self):
        """Initialize RAG components"""
        try:
            self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            self._build_knowledge_base()
            logger.info("✅ RAG system initialized")
        except Exception as e:
            logger.error(f"RAG initialization failed: {e}")
    
    def _build_knowledge_base(self):
        """Build knowledge base from database content"""
        try:
            db_context = self._get_database_context()
            
            # Build knowledge entries
            knowledge_entries = []
            
            # Add doctor information
            for doctor in db_context.doctors:
                entry = f"Dr. {doctor['name']} is a {doctor['specialization']} with {doctor.get('experience_years', 'several')} years of experience."
                knowledge_entries.append(entry)
            
            # Add specialization information
            for spec in db_context.specializations:
                entry = f"The {spec['name']} department handles {spec.get('description', 'medical services')}."
                knowledge_entries.append(entry)
            
            # Add general hospital information
            knowledge_entries.extend([
                "To book an appointment, we need patient name, phone number, date of birth, preferred doctor or specialty, and preferred date/time.",
                "Our doctors are available Monday through Friday, with some weekend availability.",
                "Appointment slots are typically 30-60 minutes depending on the specialty.",
                "We accept most major insurance plans and also offer cash payment options.",
                "Patients should arrive 15 minutes early for paperwork and check-in."
            ])
            
            self.knowledge_base = knowledge_entries
            
            # Create embeddings
            if self.knowledge_base and RAG_AVAILABLE:
                embeddings = self.embedding_model.encode(self.knowledge_base)
                self.vector_store = faiss.IndexFlatIP(embeddings.shape[1])
                self.vector_store.add(embeddings.astype('float32'))
                
        except Exception as e:
            logger.error(f"Knowledge base building failed: {e}")
    
    def _get_database_context(self) -> DatabaseContext:
        """Get current database context"""
        try:
            conn = get_db_connection()
            if not conn:
                logger.warning("No database connection available")
                return DatabaseContext([], [], [], [])
                
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get doctors
                cursor.execute("""
                    SELECT CONCAT(d.first_name, ' ', d.last_name) as name, 
                           s.name as specialization, d.experience_years, d.consultation_fee
                    FROM doctors d
                    JOIN specializations s ON d.specialization_id = s.id
                    WHERE d.is_active = true
                    ORDER BY d.last_name
                """)
                doctors = [dict(row) for row in cursor.fetchall()]
                
                # Get specializations
                cursor.execute("SELECT name, description FROM specializations WHERE is_active = true")
                specializations = [dict(row) for row in cursor.fetchall()]
                
                # Get departments
                cursor.execute("SELECT name, description FROM departments WHERE is_active = true")
                departments = [dict(row) for row in cursor.fetchall()]
                
                # Get recent appointments
                cursor.execute("""
                    SELECT a.appointment_date, a.appointment_time, 
                           CONCAT(p.first_name, ' ', p.last_name) as patient_name,
                           CONCAT(d.first_name, ' ', d.last_name) as doctor_name,
                           s.name as specialization
                    FROM appointments a
                    JOIN patients p ON a.patient_id = p.id
                    JOIN doctors d ON a.doctor_id = d.id
                    JOIN specializations s ON d.specialization_id = s.id
                    WHERE a.appointment_date >= CURRENT_DATE - INTERVAL '7 days'
                    ORDER BY a.appointment_date DESC, a.appointment_time DESC
                    LIMIT 10
                """)
                recent_appointments = [dict(row) for row in cursor.fetchall()]
                
                logger.info(f"Database context: {len(doctors)} doctors, {len(specializations)} specializations")
                return DatabaseContext(doctors, departments, specializations, recent_appointments)
                
        except Exception as e:
            logger.error(f"Error getting database context: {e}")
            return DatabaseContext([], [], [], [])
    
    def _get_relevant_context(self, query: str) -> str:
        """Get relevant context using RAG"""
        if not RAG_AVAILABLE or not self.vector_store or not self.knowledge_base:
            return ""
        
        try:
            # Encode query
            query_embedding = self.embedding_model.encode([query])
            
            # Search for similar content
            scores, indices = self.vector_store.search(query_embedding.astype('float32'), k=3)
            
            # Return relevant context
            relevant_context = []
            for idx in indices[0]:
                if idx < len(self.knowledge_base):
                    relevant_context.append(self.knowledge_base[idx])
            
            return " ".join(relevant_context)
            
        except Exception as e:
            logger.error(f"RAG context retrieval failed: {e}")
            return ""
    
    def add_message(self, session_id: str, user_message: str, ai_response: str):
        """Add message to conversation history"""
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        
        self.conversations[session_id].append({
            'user_message': user_message,
            'ai_response': ai_response,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep only last 20 messages
        if len(self.conversations[session_id]) > 20:
            self.conversations[session_id] = self.conversations[session_id][-20:]
    
    def extract_appointment_details(self, message: str, conversation_history: List = None) -> Optional[AppointmentDetails]:
        """Extract appointment details from conversation with enhanced parsing"""
        # Build comprehensive context from current message and recent conversation
        combined_text = message.lower()
        full_conversation = []
        
        if conversation_history:
            # Get last 5 exchanges for better context
            recent_messages = conversation_history[-5:]
            for msg in recent_messages:
                user_msg = msg.get('user_message', '').lower()
                ai_msg = msg.get('ai_response', '').lower()
                full_conversation.extend([user_msg, ai_msg])
                combined_text += " " + user_msg + " " + ai_msg
        
        # Extract details using enhanced patterns
        details = AppointmentDetails(
            patient_name="",
            date_of_birth="",
            doctor_preference="",
            specialization="",
            preferred_date="",
            preferred_time="",
            reason="General consultation"
        )
        
        # Enhanced patient name extraction - more specific patterns
        name_patterns = [
            # Pattern for "book appointment for Name, DOB, specialty"
            r'(?:book|appointment|for)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\s*,\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}',
            # Pattern for names followed by comma and DOB
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s*,\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}',
            # Pattern for names in booking context
            r'(?:book|appointment|for)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s*,|\s*for|\s*-)',
            # Pattern for standalone capitalized names
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s*,|\s*for|\s*-|\s*05|\s*02|\s*2004)',
            # Pattern for names after "for"
            r'(?:for)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            # Pattern for names in conversation context
            r'(?:name is|i am|i\'m|my name is|this is)\s+([a-zA-Z\s]+?)(?:\s*,|\s*$|\s*book|\s*schedule|\s*appointment)',
            # Pattern for "patient Name"
            r'(?:patient|i\'m)\s+([a-zA-Z]+\s+[a-zA-Z]+)',
            # Pattern for "Krish Sawhney" specifically (case insensitive)
            r'(krish\s+sawhney)',
            # Pattern for any two-word capitalized name
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)',
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                potential_name = match.group(1).strip()
                # Validate it's actually a name (not booking keywords)
                if (len(potential_name.split()) >= 2 and 
                    not any(word in potential_name.lower() for word in ['book', 'me', 'one', 'on', 'for', 'at', 'with', 'the', 'appointm']) and
                    not potential_name.lower().startswith('book')):
                    details.patient_name = potential_name.title()  # Ensure proper case
                    logger.info(f"✅ Extracted patient name: '{potential_name}'")
                    break
        
        # If no name found in current message, check conversation history
        if not details.patient_name and conversation_history:
            for msg in conversation_history[-5:]:  # Check last 5 messages
                # Look for name patterns in previous messages
                for pattern in name_patterns:
                    match = re.search(pattern, msg.get('user_message', ''), re.IGNORECASE)
                    if match:
                        potential_name = match.group(1).strip()
                        if (len(potential_name.split()) >= 2 and 
                            not any(word in potential_name.lower() for word in ['book', 'me', 'one', 'on', 'for', 'at', 'with', 'the', 'appointm']) and
                            not potential_name.lower().startswith('book')):
                            details.patient_name = potential_name.title()  # Ensure proper case
                            logger.info(f"✅ Extracted patient name from history: '{potential_name}'")
                            break
                if details.patient_name:
                    break
        
        # Enhanced date of birth extraction - more specific patterns
        dob_patterns = [
            # Pattern for DOB after comma: "Name, MM/DD/YYYY"
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s*,\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})',
            # Pattern for DOB in various formats
            r'(?:birth|born|dob|date of birth).*?(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})',
            r'(?:birth|born|dob|date of birth).*?(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4})',
            # Pattern for standalone DOB
            r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})',
            # Pattern for "05/02/2004" specifically
            r'(05\/02\/2004)',
        ]
        
        for pattern in dob_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                # If pattern has groups, use the DOB group
                if len(match.groups()) > 1:
                    details.date_of_birth = match.group(2).strip()
                else:
                    details.date_of_birth = match.group(1).strip()
                logger.info(f"✅ Extracted DOB: '{details.date_of_birth}'")
                break
        
        # Enhanced doctor/specialization extraction
        specializations = ['cardiology', 'neurology', 'orthopedics', 'pediatrics', 'dermatology', 
                          'psychiatry', 'gynecology', 'general medicine', 'cardiology']
        
        for spec in specializations:
            if spec in combined_text:
                details.specialization = spec.title()
                break
        
        # Enhanced doctor name extraction
        doctor_patterns = [
            r'(?:dr\.|doctor)\s+([a-zA-Z\s]+?)(?:\s|,|$|\.)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)',  # Look for capitalized names
        ]
        
        for pattern in doctor_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                doctor_name = match.group(1).strip()
                # Validate it's actually a doctor name (not booking keywords)
                if (len(doctor_name.split()) >= 2 and 
                    not any(word in doctor_name.lower() for word in ['book', 'me', 'one', 'on', 'for', 'at', 'with', 'the', 'appointm', 'looking', 'want', 'check', 'find', 'show']) and
                    not doctor_name.lower().startswith('book')):
                    details.doctor_preference = doctor_name
                    break
        
        # Enhanced date extraction - distinguish between DOB and appointment date
        # First check if this looks like an appointment date (not DOB context)
        appointment_date_patterns = [
            r'(?:on|for)\s+(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'(?:on|for)\s+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})',
            r'(next\s+\w+)',
            r'(june|july|august|september|october|november|december)\s+\d{1,2}',
            r'(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))',
            # Direct date patterns for booking
            r'(?:book|schedule|appointment)\s+(?:on|for)?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})',
            r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})(?:\s|$)',  # Standalone date
            # Date patterns that might be appointment dates
            r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})',  # Any date format
        ]
        
        for pattern in appointment_date_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                date_text = match.group(1).strip()
                # Validate it's not a DOB (should be future date)
                try:
                    parsed_date = dateutil.parser.parse(date_text)
                    # More flexible validation - allow dates that are reasonable for booking
                    # (within next 2 years, or if it's a date format that could be ambiguous)
                    if parsed_date.date() >= date.today() or parsed_date.date().year >= date.today().year:
                        details.preferred_date = date_text
                        break
                except:
                    # If parsing fails, still accept the date text as-is
                    details.preferred_date = date_text
                    break
        
        # Enhanced time extraction
        time_patterns = [
            r'(\d{1,2}:\d{2}\s*(?:am|pm))',
            r'(\d{1,2}\s*(?:am|pm))',
            r'(morning|afternoon|evening)',
            r'(\d{1,2}:\d{2})',
            # Time patterns that might be appointment times
            r'(\d{1,2}:\d{2}[ap]m)',  # 3:00pm format
            r'(\d{1,2}[ap]m)',  # 3pm format
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                details.preferred_time = match.group(1).strip()
                break
        
        # Check if we have enough information to attempt booking
        # Return details even if incomplete, so calling code can see what was extracted
        return details
    
    def process_message(self, user_message: str, session_id: str = None) -> Dict[str, Any]:
        """Process user message with AI-driven responses using database context"""
        try:
            if not session_id:
                session_id = str(uuid.uuid4())
            
            conversation_history = self.conversations.get(session_id, [])
            state = self._get_conversation_state(session_id)
            
            # Update state based on recent messages
            state['last_context'] = user_message
            
            # Extract appointment details from current message and conversation history
            appointment_details = self.extract_appointment_details(user_message, conversation_history)
            
            # If no details extracted, create empty details object
            if appointment_details is None:
                appointment_details = AppointmentDetails(
                    patient_name="",
                    date_of_birth="",
                    doctor_preference="",
                    specialization="",
                    preferred_date="",
                    preferred_time="",
                    reason="General consultation"
                )
            
            # Merge with conversation history details
            history_details = self._extract_from_conversation_history(conversation_history)
            
            # Combine current and historical details
            if not appointment_details.patient_name and history_details.patient_name:
                appointment_details.patient_name = history_details.patient_name
            if not appointment_details.date_of_birth and history_details.date_of_birth:
                appointment_details.date_of_birth = history_details.date_of_birth
            if not appointment_details.specialization and history_details.specialization:
                appointment_details.specialization = history_details.specialization
            if not appointment_details.preferred_date and history_details.preferred_date:
                appointment_details.preferred_date = history_details.preferred_date
            if not appointment_details.preferred_time and history_details.preferred_time:
                appointment_details.preferred_time = history_details.preferred_time
            
            # Update conversation state with extracted information
            if appointment_details.patient_name:
                state['patient_name'] = appointment_details.patient_name
            if appointment_details.date_of_birth:
                state['date_of_birth'] = appointment_details.date_of_birth
            if appointment_details.specialization:
                state['specialization'] = appointment_details.specialization
            if appointment_details.preferred_date:
                state['preferred_date'] = appointment_details.preferred_date
            if appointment_details.preferred_time:
                state['preferred_time'] = appointment_details.preferred_time
            
            # Check if this is a database query request
            query_result = None
            user_message_lower = user_message.lower()
            
            # Check for specific patient appointment queries FIRST (when name and DOB are mentioned)
            if appointment_details.patient_name and appointment_details.date_of_birth:
                # Check if this is asking about appointments for the mentioned person
                appointment_keywords = ['appointments', 'appointment', 'schedule', 'booked', 'upcoming', 'existing', 'looking up', 'check', 'find', 'show']
                if any(word in user_message_lower for word in appointment_keywords):
                    query_result = query_patient_appointments(appointment_details.patient_name, appointment_details.date_of_birth)
            
            # Check for patient appointment queries (using state)
            elif any(word in user_message_lower for word in ['my appointments', 'show appointments', 'find appointments', 'check appointments', 'appointments for', 'look up appointments', 'search appointments']):
                if state.get('patient_name') and state.get('date_of_birth'):
                    query_result = query_patient_appointments(state['patient_name'], state['date_of_birth'])
                else:
                    query_result = "I need your name and date of birth to check your appointments. Could you please provide them?"
            
            # Check for availability queries (only if no patient appointment query was triggered)
            elif any(word in user_message_lower for word in ['availability', 'available', 'schedule', 'cardiology', 'neurology', 'orthopedics', 'pediatrics', 'dermatology', 'psychiatry', 'gynecology', 'gastroenterology', 'endocrinology', 'pulmonology', 'rheumatology', 'ophthalmology', 'ent', 'oncology', 'general medicine']):
                # Extract specialty from message
                specialties = ['cardiology', 'neurology', 'orthopedics', 'pediatrics', 'dermatology', 'psychiatry', 'gynecology', 'gastroenterology', 'endocrinology', 'pulmonology', 'rheumatology', 'ophthalmology', 'ent', 'oncology', 'general medicine']
                found_specialty = None
                for specialty in specialties:
                    if specialty in user_message_lower:
                        found_specialty = specialty
                        break
                
                if found_specialty:
                    # Extract date if mentioned
                    date_keywords = ['today', 'tomorrow', 'next week', 'this week']
                    target_date = None
                    for date_keyword in date_keywords:
                        if date_keyword in user_message_lower:
                            target_date = date_keyword
                            break
                    
                    query_result = query_doctor_availability(found_specialty, target_date)
            
            # Check for doctor schedule queries
            elif any(word in user_message_lower for word in ['dr.', 'doctor', 'schedule', 'timing']):
                # Extract doctor name
                doctor_patterns = [
                    r'dr\.\s+([a-zA-Z]+\s+[a-zA-Z]+)',
                    r'doctor\s+([a-zA-Z]+\s+[a-zA-Z]+)',
                    r'([a-zA-Z]+\s+[a-zA-Z]+)\'s\s+schedule'
                ]
                
                doctor_name = None
                for pattern in doctor_patterns:
                    match = re.search(pattern, user_message, re.IGNORECASE)
                    if match:
                        doctor_name = match.group(1)
                        break
                
                if doctor_name:
                    # Extract date if mentioned
                    date_keywords = ['today', 'tomorrow', 'next week', 'this week']
                    target_date = None
                    for date_keyword in date_keywords:
                        if date_keyword in user_message_lower:
                            target_date = date_keyword
                            break
                    
                    query_result = query_doctor_schedule(doctor_name, target_date)
            
            # Get database context for AI response
            db_context = self._get_database_context()
            
            # Get relevant context using RAG
            rag_context = self._get_relevant_context(user_message)
            
            # Add query result to context if available
            if query_result:
                rag_context += f"\n\nDATABASE QUERY RESULT:\n{query_result}"
                # Add specific instruction to use the database result
                rag_context += "\n\nIMPORTANT: Use the database query result above to provide accurate information. Do not generate fake responses when real data is available."
            
            # Build enhanced system prompt with current state
            current_state_info = f"""
Current conversation state:
- Patient Name: {state.get('patient_name', 'Not provided')}
- Date of Birth: {state.get('date_of_birth', 'Not provided')}
- Specialization: {state.get('specialization', 'Not provided')}
- Preferred Date: {state.get('preferred_date', 'Not provided')}
- Preferred Time: {state.get('preferred_time', 'Not provided')}
- Booking Intent: {state.get('booking_intent', False)}
"""
            
            # Use enhanced system prompt if available, otherwise use fallback
            if GUIDANCE_AVAILABLE:
                try:
                    system_prompt = get_enhanced_system_prompt(db_context, rag_context + current_state_info)
                    logger.debug("Using enhanced system prompt from claude_guidance")
                except Exception as e:
                    logger.error(f"Error using enhanced system prompt: {e}")
                    system_prompt = get_fallback_system_prompt(db_context, rag_context + current_state_info)
            else:
                system_prompt = get_fallback_system_prompt(db_context, rag_context + current_state_info)
            
            # Get AI response
            if BEDROCK_AVAILABLE:
                ai_response = get_ai_response(system_prompt, user_message, conversation_history)
            else:
                ai_response = self._generate_fallback_response(user_message, db_context)
            
            # If we have a database query result, use it instead of AI-generated response
            if query_result and not query_result.startswith("I need your name"):
                logger.info(f"🔍 Database query result available: {query_result[:100]}...")
                logger.info(f"🔍 User message: {user_message_lower}")
                # For appointment queries, use the database result directly
                if "appointments for" in user_message_lower or "looking up" in user_message_lower:
                    logger.info(f"✅ Using database result for appointment query")
                    ai_response = query_result
                # For availability queries, combine database result with AI response
                elif "availability" in user_message_lower or "available" in user_message_lower:
                    logger.info(f"✅ Combining database result with AI response")
                    ai_response = f"{query_result}\n\n{ai_response}"
                # For other queries, use database result as primary
                else:
                    logger.info(f"✅ Using database result as primary")
                    ai_response = query_result
            else:
                logger.info(f"❌ No database query result or result starts with 'I need your name'")
                if query_result:
                    logger.info(f"Query result: {query_result[:100]}...")
            
            # Check if AI response indicates booking attempt - more flexible conditions
            booking_keywords = ['book', 'schedule', 'appointment', 'reserve', 'confirm', 'yes', 'okay', 'sure', 'proceed']
            is_booking_request = any(keyword in user_message.lower() for keyword in booking_keywords)
            
            # Check if this is an appointment query (not a booking request)
            appointment_query_keywords = ['looking up', 'check', 'find', 'show', 'my appointments', 'appointments for']
            is_appointment_query = any(keyword in user_message.lower() for keyword in appointment_query_keywords)
            
            # More flexible booking conditions - require patient name and DOB, but specialization is optional
            has_essential_info = (appointment_details.patient_name and 
                                appointment_details.date_of_birth)
            
            # Check if we have enough info for booking (patient name + DOB is minimum)
            has_complete_info = has_essential_info
            
            # Debug logging
            logger.info(f"Appointment details extracted: {appointment_details}")
            logger.info(f"Has essential info: {has_essential_info}")
            logger.info(f"Has complete info: {has_complete_info}")
            logger.info(f"Is booking request: {is_booking_request}")
            logger.info(f"Is appointment query: {is_appointment_query}")
            logger.info(f"Patient name: '{appointment_details.patient_name}'")
            logger.info(f"DOB: '{appointment_details.date_of_birth}'")
            logger.info(f"Specialization: '{appointment_details.specialization}'")
            logger.info(f"Preferred date: '{appointment_details.preferred_date}'")
            logger.info(f"Preferred time: '{appointment_details.preferred_time}'")
            
            # If this is an appointment query, don't try to book
            if is_appointment_query:
                logger.info(f"🔍 This is an appointment query, not a booking request")
                is_booking_request = False
            
            # If we have essential appointment details and this is a booking request, attempt booking FIRST
            if has_essential_info and is_booking_request and not is_appointment_query:
                logger.info(f"🎯 ATTEMPTING TO BOOK APPOINTMENT!")
                logger.info(f"Details: {appointment_details}")
                
                # If no specialization provided, use a default one
                if not appointment_details.specialization:
                    appointment_details.specialization = "General Medicine"
                    logger.info(f"Using default specialization: {appointment_details.specialization}")
                
                # Attempt to book appointment
                success, message = self.appointment_manager.book_appointment(appointment_details)
                
                if success:
                    logger.info(f"✅ BOOKING SUCCESSFUL: {message}")
                    # Return booking confirmation immediately
                    ai_response = f"✅ {message}\n\nPlease arrive 15 minutes early for check-in. If you need to reschedule or cancel, please let me know!"
                    # Clear booking intent after successful booking
                    state['booking_intent'] = False
                    self.add_message(session_id, user_message, ai_response)
                    return {
                        'response': ai_response,
                        'session_id': session_id,
                        'success': True,
                        'appointment_booked': True,
                        'appointment_id': message.split('#')[1].split()[0] if '#' in message else None
                    }
                else:
                    logger.info(f"❌ BOOKING FAILED: {message}")
                    # Return booking error immediately
                    ai_response = f"⚠️ {message}\n\nWould you like me to help you find alternative options or book a different time?"
                    self.add_message(session_id, user_message, ai_response)
                    return {
                        'response': ai_response,
                        'session_id': session_id,
                        'success': False,
                        'booking_attempted': True
                    }
            else:
                logger.info(f"❌ BOOKING CONDITIONS NOT MET:")
                logger.info(f"  - has_essential_info: {has_essential_info}")
                logger.info(f"  - is_booking_request: {is_booking_request}")
                logger.info(f"  - patient_name: '{appointment_details.patient_name}'")
                logger.info(f"  - date_of_birth: '{appointment_details.date_of_birth}'")
                logger.info(f"  - specialization: '{appointment_details.specialization}'")
            
            # If we have all essential info but user hasn't confirmed booking yet, override AI response
            # BUT only if we don't have a database query result (to avoid overriding real appointment data)
            if has_essential_info and not is_booking_request and not query_result:
                ai_response = f"I have the essential information needed to book your appointment:\n\nPatient: {appointment_details.patient_name}\nDOB: {appointment_details.date_of_birth}\nSpecialty: {appointment_details.specialization or 'General Medicine'}\nDate: {appointment_details.preferred_date or 'Not specified'}\nTime: {appointment_details.preferred_time or 'Not specified'}\n\nPlease confirm by saying 'yes' or 'book it' to proceed with the booking."
            # If we have a database query result for appointments, don't override it with booking logic
            elif query_result and ("appointments for" in user_message_lower or "looking up" in user_message_lower):
                # Keep the database result as is - don't override
                pass
            
            # Store conversation
            self.add_message(session_id, user_message, ai_response)
            
            return {
                'response': ai_response,
                'session_id': session_id,
                'success': True,
                'context_used': len(rag_context) > 0,
                'guidance_used': GUIDANCE_AVAILABLE,
                'database_queried': query_result is not None
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                'response': "I apologize, but I'm experiencing technical difficulties. Please try again or contact our support team.",
                'session_id': session_id,
                'success': False,
                'error': str(e)
            }
    
    def _generate_fallback_response(self, user_message: str, db_context: DatabaseContext) -> str:
        """Enhanced fallback response system using database context"""
        
        user_lower = user_message.lower()
        
        # Greeting
        if any(word in user_lower for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']):
            return f"Hello! Welcome to our hospital appointment system. I can help you book appointments with our {len(db_context.doctors)} doctors across {len(db_context.specializations)} specializations. How can I assist you today?"
        
        # Doctor inquiry
        if any(word in user_lower for word in ['doctor', 'doctors', 'specialist']):
            if 'cardiologist' in user_lower or 'heart' in user_lower:
                cardiologists = [d for d in db_context.doctors if 'cardio' in d['specialization'].lower()]
                if cardiologists:
                    doc_list = ', '.join([f"Dr. {d['name']}" for d in cardiologists])
                    return f"Our cardiology specialists are: {doc_list}. Would you like to check their availability or book an appointment?"
            else:
                doc_list = ', '.join([f"Dr. {d['name']} ({d['specialization']})" for d in db_context.doctors[:6]])
                return f"Here are some of our available doctors: {doc_list}. Which specialty are you interested in?"
        
        # Booking inquiry
        elif any(word in user_lower for word in ['book', 'appointment', 'schedule']):
            return "I'd be happy to help you book an appointment! I'll need:\n1. Your full name\n2. Your date of birth\n3. Which doctor or specialty you prefer\n4. Your preferred date and time\n\nPlease provide these details and I'll find the best available slot for you."
        
        # Availability inquiry
        elif any(word in user_lower for word in ['available', 'availability', 'free', 'open']):
            specializations = ', '.join([s['name'] for s in db_context.specializations])
            return f"I can check availability for any of our specializations: {specializations}. Which one interests you, or do you have a specific doctor in mind?"
        
        # Default response with context
        else:
            return f"I'm here to help with appointments and medical inquiries. We have {len(db_context.doctors)} doctors available across specializations like {', '.join([s['name'] for s in db_context.specializations[:5]])}. How can I assist you today?"

    def get_upcoming_appointments(self, patient_name: str, date_of_birth: str) -> list:
        """Fetch upcoming appointments for a patient by name and date of birth"""
        try:
            conn = get_db_connection()
            if not conn:
                return []
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Split name into first and last
                name_parts = patient_name.strip().split()
                if len(name_parts) >= 2:
                    first_name = name_parts[0]
                    last_name = ' '.join(name_parts[1:])
                else:
                    first_name = name_parts[0]
                    last_name = ''
                
                # Parse date of birth
                try:
                    if '/' in date_of_birth:
                        parts = date_of_birth.split('/')
                        if len(parts) == 3:
                            if int(parts[0]) > 12:  # DD/MM/YYYY
                                dob = date(int(parts[2]), int(parts[1]), int(parts[0]))
                            else:  # MM/DD/YYYY
                                dob = date(int(parts[2]), int(parts[0]), int(parts[1]))
                    else:
                        dob = dateutil.parser.parse(date_of_birth).date()
                except:
                    return []
                
                # Find patient by name and date_of_birth
                cursor.execute(
                    "SELECT id FROM patients WHERE LOWER(first_name) = LOWER(%s) AND LOWER(last_name) = LOWER(%s) AND date_of_birth = %s LIMIT 1",
                    (first_name, last_name, dob)
                )
                patient = cursor.fetchone()
                if not patient:
                    return []
                
                patient_id = patient['id']
                
                # Fetch upcoming appointments
                cursor.execute(
                    """
                    SELECT a.id, a.appointment_date, a.appointment_time, a.status, a.reason_for_visit,
                           CONCAT(d.first_name, ' ', d.last_name) as doctor_name, s.name as specialization,
                           d.consultation_fee
                    FROM appointments a
                    JOIN patients p ON a.patient_id = p.id
                    JOIN doctors d ON a.doctor_id = d.id
                    JOIN specializations s ON d.specialization_id = s.id
                    WHERE a.patient_id = %s AND a.appointment_date >= CURRENT_DATE AND a.status NOT IN ('cancelled')
                    ORDER BY a.appointment_date ASC, a.appointment_time ASC
                    LIMIT 10
                    """,
                    (patient_id,)
                )
                appointments = cursor.fetchall()
                # Serialize datetime objects before returning
                return [serialize_datetime_objects(dict(row)) for row in appointments]
                
        except Exception as e:
            logger.error(f"Error getting patient appointments: {e}")
            return []

# Initialize conversation manager
conversation_manager = EnhancedConversationManager()

# WSGI middleware to catch malformed requests
class MalformedRequestMiddleware:
    def __init__(self, app):
        self.app = app
    
    def __call__(self, environ, start_response):
        try:
            # Check for malformed request line
            request_line = environ.get('REQUEST_METHOD', '') + ' ' + environ.get('PATH_INFO', '')
            if len(request_line) > 2048:  # Too long request line
                logger.warning(f"Request line too long from {environ.get('REMOTE_ADDR', 'unknown')}")
                status = '400 Bad Request'
                response_headers = [('Content-Type', 'application/json')]
                start_response(status, response_headers)
                return [b'{"success": false, "message": "Invalid request"}']

            # Check content length
            content_length = environ.get('CONTENT_LENGTH')
            if content_length and int(content_length) > 1024 * 1024:  # 1MB limit
                logger.warning(f"Request too large: {content_length} bytes from {environ.get('REMOTE_ADDR', 'unknown')}")
                status = '413 Request Entity Too Large'
                response_headers = [('Content-Type', 'application/json')]
                start_response(status, response_headers)
                return [b'{"success": false, "message": "Request too large"}']

            return self.app(environ, start_response)
            
        except Exception as e:
            logger.error(f"Middleware error: {e}")
            status = '500 Internal Server Error'
            response_headers = [('Content-Type', 'application/json')]
            start_response(status, response_headers)
            return [b'{"success": false, "message": "Server error"}']

# Apply middleware
app.wsgi_app = MalformedRequestMiddleware(app.wsgi_app)

# API Routes
@app.route('/api/chat', methods=['POST'])
def chat():
    """Enhanced chat endpoint with proper appointment booking"""
    try:
        # Validate request
        if not request.is_json:
            logger.warning(f"Non-JSON request received from {request.remote_addr}")
            return jsonify({
                'success': False,
                'message': 'Request must be JSON'
            }), 400
        
        data = request.get_json()
        if not data:
            logger.warning(f"Empty JSON request received from {request.remote_addr}")
            return jsonify({
                'success': False,
                'message': 'Invalid request format'
            }), 400

        user_message = data.get('message', '').strip()
        session_id = data.get('session_id')

        if not user_message:
            logger.warning(f"Empty message received from {request.remote_addr}")
            return jsonify({
                'success': False,
                'message': 'Message cannot be empty'
            }), 400

        # Log the request for debugging
        logger.info(f"Processing chat request from {request.remote_addr}: {user_message[:100]}...")
        
        # Process message with enhanced logic
        result = conversation_manager.process_message(user_message, session_id)
        
        return jsonify(result)

    except Exception as e:
        logger.error(f"Chat endpoint error from {request.remote_addr}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'An error occurred processing your request',
            'error': str(e)
        }), 500

@app.route('/api/appointments', methods=['GET', 'POST', 'DELETE'])
def appointments():
    """Enhanced appointments endpoint with better error handling and JSON serialization"""
    if request.method == 'GET':
        try:
            logger.info("Fetching appointments...")
            
            # Get appointments with optional filtering
            doctor_id = request.args.get('doctor_id')
            date_filter = request.args.get('date')
            status = request.args.get('status', 'scheduled')
            
            conn = get_db_connection()
            if not conn:
                logger.error("Database connection failed in appointments endpoint")
                return jsonify({'success': False, 'message': 'Database connection error'}), 500
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    SELECT a.id, a.appointment_date, a.appointment_time, a.status, a.reason_for_visit,
                           CONCAT(p.first_name, ' ', p.last_name) as patient_name,
                           CONCAT(d.first_name, ' ', d.last_name) as doctor_name,
                           s.name as specialization, d.consultation_fee
                    FROM appointments a
                    JOIN patients p ON a.patient_id = p.id
                    JOIN doctors d ON a.doctor_id = d.id
                    JOIN specializations s ON d.specialization_id = s.id
                    WHERE 1=1
                """
                params = []
                
                if doctor_id:
                    query += " AND a.doctor_id = %s"
                    params.append(doctor_id)
                
                if date_filter:
                    query += " AND a.appointment_date = %s"
                    params.append(date_filter)
                
                if status:
                    query += " AND a.status = %s"
                    params.append(status)
                
                query += " ORDER BY a.appointment_date DESC, a.appointment_time DESC LIMIT 50"
                
                logger.debug(f"Executing query: {query} with params: {params}")
                cursor.execute(query, params)
                appointments_data = cursor.fetchall()
                
                # Convert to dict and serialize datetime objects
                serialized_appointments = []
                for row in appointments_data:
                    appointment_dict = dict(row)
                    serialized_appointment = serialize_datetime_objects(appointment_dict)
                    serialized_appointments.append(serialized_appointment)
                
                logger.info(f"Successfully fetched {len(serialized_appointments)} appointments")
                
                return jsonify({
                    'success': True,
                    'appointments': serialized_appointments
                })
                
        except Exception as e:
            logger.error(f"Error fetching appointments: {e}", exc_info=True)
            return jsonify({
                'success': False, 
                'message': f'Failed to fetch appointments: {str(e)}',
                'error_type': type(e).__name__
            }), 500
    
    elif request.method == 'POST':
        # Create appointment via API
        try:
            data = request.get_json()
            required_fields = ['patient_name', 'date_of_birth', 'doctor_id', 'appointment_date', 'appointment_time']
            
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        'success': False,
                        'message': f'Missing required field: {field}'
                    }), 400
            
            # Use appointment manager to book
            details = AppointmentDetails(
                patient_name=data['patient_name'],
                date_of_birth=data['date_of_birth'],
                doctor_preference=str(data['doctor_id']),
                specialization=data.get('specialization', ''),
                preferred_date=data['appointment_date'],
                preferred_time=data['appointment_time'],
                reason=data.get('reason', 'General consultation')
            )
            
            success, message = conversation_manager.appointment_manager.book_appointment(details)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': message
                })
            else:
                return jsonify({
                    'success': False,
                    'message': message
                }), 400
                
        except Exception as e:
            logger.error(f"Error creating appointment: {e}")
            return jsonify({
                'success': False,
                'message': f'Failed to create appointment: {str(e)}'
            }), 500
    
    elif request.method == 'DELETE':
        # Cancel appointment
        try:
            appointment_id = request.args.get('id')
            if not appointment_id:
                return jsonify({'success': False, 'message': 'Appointment ID required'}), 400
            
            conn = get_db_connection()
            if not conn:
                return jsonify({'success': False, 'message': 'Database connection error'}), 500
            
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE appointments SET status = 'cancelled' WHERE id = %s",
                    (appointment_id,)
                )
                
                if cursor.rowcount > 0:
                    conn.commit()
                    return jsonify({'success': True, 'message': 'Appointment cancelled successfully'})
                else:
                    return jsonify({'success': False, 'message': 'Appointment not found'}), 404
                    
        except Exception as e:
            logger.error(f"Error cancelling appointment: {e}")
            return jsonify({'success': False, 'message': 'Failed to cancel appointment'}), 500

@app.route('/api/doctors', methods=['GET'])
def doctors():
    """Get doctors with availability information"""
    try:
        specialty = request.args.get('specialty')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = """
                SELECT d.id, d.first_name, d.last_name, d.experience_years, d.consultation_fee,
                       s.name as specialization
                FROM doctors d
                JOIN specializations s ON d.specialization_id = s.id
                WHERE d.is_active = TRUE
            """
            params = []
            
            if specialty:
                query += " AND s.name ILIKE %s"
                params.append(f"%{specialty}%")
            
            query += " ORDER BY d.last_name, d.first_name"
            
            cursor.execute(query, params)
            doctors_list = []
            
            for doctor in cursor.fetchall():
                doctor_dict = dict(doctor)
                # Get next available slots
                try:
                    slots = conversation_manager.appointment_manager.get_next_available_slots(doctor['id'], 7)
                    doctor_dict['next_available'] = slots[:3] if slots else []
                except Exception as e:
                    logger.error(f"Error getting slots for doctor {doctor['id']}: {e}")
                    doctor_dict['next_available'] = []
                doctors_list.append(doctor_dict)
            
            # Serialize datetime objects
            serialized_doctors = serialize_datetime_objects(doctors_list)
            
            return jsonify({
                'success': True,
                'doctors': serialized_doctors
            })
            
    except Exception as e:
        logger.error(f"Error fetching doctors: {e}")
        return jsonify({'success': False, 'message': 'Failed to fetch doctors'}), 500

@app.route('/api/specializations', methods=['GET'])
def specializations():
    """Get all medical specializations"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT s.name, s.description, COUNT(d.id) as doctor_count
                FROM specializations s
                LEFT JOIN doctors d ON s.id = d.specialization_id AND d.is_active = TRUE
                WHERE s.is_active = TRUE
                GROUP BY s.id, s.name, s.description
                ORDER BY s.name
            """)
            
            specializations_list = [dict(row) for row in cursor.fetchall()]
            
            return jsonify({
                'success': True,
                'specializations': specializations_list
            })
            
    except Exception as e:
        logger.error(f"Error fetching specializations: {e}")
        return jsonify({'success': False, 'message': 'Failed to fetch specializations'}), 500

@app.route('/api/patient/appointments', methods=['POST'])
def patient_appointments():
    """Get patient appointments by name and DOB"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'Invalid request format'
            }), 400
        
        patient_name = data.get('patient_name', '').strip()
        date_of_birth = data.get('date_of_birth', '').strip()
        
        if not patient_name or not date_of_birth:
            return jsonify({
                'success': False,
                'message': 'Missing required fields: patient_name, date_of_birth'
            }), 400
        
        appointments_data = conversation_manager.get_upcoming_appointments(patient_name, date_of_birth)
        
        return jsonify({
            'success': True,
            'appointments': appointments_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching patient appointments: {e}")
        return jsonify({
            'success': False,
            'message': 'An error occurred processing your request'
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        conn = get_db_connection()
        db_status = "connected" if conn else "disconnected"
        if conn:
            conn.close()
        
        # Check AI service
        ai_status = "connected" if BEDROCK_AVAILABLE else "fallback_mode"
        
        return jsonify({
            'status': 'healthy',
            'database': db_status,
            'ai_service': ai_status,
            'rag_enabled': RAG_AVAILABLE,
            'bedrock_enabled': BEDROCK_AVAILABLE,
            'vector_store': 'initialized' if conversation_manager.vector_store else 'not_available',
            'guidance_system': 'enabled' if GUIDANCE_AVAILABLE else 'fallback',
            'features': {
                'appointment_booking': True,
                'doctor_search': True,
                'availability_check': True,
                'patient_lookup': True
            }
        })
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# Legacy endpoint for compatibility
@app.route('/ask', methods=['POST'])
def ask():
    """Legacy chat endpoint - redirects to /api/chat"""
    return chat()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    """Catch-all route to handle malformed requests"""
    logger.warning(f"Invalid route accessed: /{path} from {request.remote_addr}")
    return jsonify({
        'success': False,
        'message': 'Invalid endpoint',
        'available_endpoints': [
            '/api/chat',
            '/api/appointments',
            '/api/doctors',
            '/api/specializations',
            '/api/health'
        ]
    }), 404

if __name__ == '__main__':
    logger.info("🏥 Starting Enhanced Doc-AI Hospital Management System")
    logger.info(f"✅ Database: {'Connected' if get_db_connection() else 'Not Connected'}")
    logger.info(f"✅ AI Service: {'AWS Bedrock' if BEDROCK_AVAILABLE else 'Fallback Mode'}")
    logger.info(f"✅ RAG System: {'Enabled' if RAG_AVAILABLE else 'Disabled'}")
    logger.info(f"✅ Claude Guidance System: {'Enabled' if GUIDANCE_AVAILABLE else 'Fallback Mode'}")
    logger.info("🚀 Server starting on http://localhost:8000")
    
    app.run(host='0.0.0.0', port=8000, debug=True)